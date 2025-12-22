import time
import threading
import logging
import asyncio
import socket
from datetime import datetime, timedelta
from collections import defaultdict

# SNMP Imports (v7+)
from pysnmp.hlapi.v3arch.asyncio import (
    SnmpEngine,
    CommunityData,
    UdpTransportTarget,
    ContextData,
    ObjectType,
    ObjectIdentity,
    walk_cmd,
)

# mDNS Imports (Hostname Discovery)
from zeroconf import Zeroconf, ServiceBrowser, ServiceStateChange

# Vendor Analysis
from netaddr import EUI, mac_unix_expanded

from app.extensions import socketio, db
from app.models import Device, PresenceEvent

logger = logging.getLogger(__name__)

# --- HELPER CLASSES ---


class MDNSListener:
    """Passively listens for mDNS broadcasts to resolve Hostnames"""

    def __init__(self):
        self.cache = {}  # Map IP -> Hostname

    def remove_service(self, zeroconf, type, name):
        pass

    def add_service(self, zeroconf, type, name):
        pass

    def update_service(self, zeroconf, type, name):
        """Called when a service is updated/found"""
        try:
            info = zeroconf.get_service_info(type, name)
            if info and info.addresses:
                ip = socket.inet_ntoa(info.addresses[0])
                # Clean up name (e.g. "Kaias-iPhone.local." -> "Kaias-iPhone")
                clean_name = info.server.replace(".local.", "")
                self.cache[ip] = clean_name
        except Exception:
            pass


# --- MAIN SERVICE ---


class PresenceMonitor:
    def __init__(self, app, target_ip, community, scan_interval=60):
        self.app = app
        self.target_ip = target_ip
        self.community = community
        self.scan_interval = scan_interval
        self.socketio = socketio
        self._lock = threading.Lock()

        # runtime state
        self.monitoring = True
        self.last_scan_time = None

        # 1. Start mDNS Listener (Continuous)
        self.mdns = MDNSListener()
        self.zeroconf = Zeroconf()
        # Listen for Apple devices & standard workstations
        self.browser = ServiceBrowser(
            self.zeroconf,
            ["_device-info._tcp.local.", "_workstation._tcp.local."],
            self.mdns,
        )

        # 2. Start Main Scan Loop
        self.monitor_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self.monitor_thread.start()

        logger.info(f"PresenceMonitor v2 (Correlated) initialized on {target_ip}")

    # ===========================
    # CORE LOOP
    # ===========================
    def _scan_loop(self):
        """Orchestrates the data gathering and analysis"""
        while self.monitoring:
            try:
                self.last_scan_time = datetime.now()

                # A. Fetch raw ARP table (MAC <-> IP) via SNMP
                raw_arp_data = self._run_snmp_scan()

                if raw_arp_data:
                    # B. Fusion: Merge ARP data with mDNS Hostnames
                    enriched_data = self._enrich_data(raw_arp_data)

                    # C. Update DB & Analyze
                    self._process_presence(enriched_data)

                time.sleep(self.scan_interval)

            except Exception as e:
                logger.error(f"Scan loop error: {e}")
                time.sleep(self.scan_interval)

    # ===========================
    # SCANNING LOGIC
    # ===========================
    def _run_snmp_scan(self):
        """Wrapper to run async SNMP in sync context"""
        try:
            return asyncio.run(self._get_arp_table_async())
        except Exception as e:
            logger.error(f"Async Bridge Error: {e}")
            return {}

    async def _get_arp_table_async(self):
        """
        Retrieves ARP Table mapping IP -> MAC
        Returns dict: {'192.168.1.5': 'AA:BB:CC...', ...}
        """
        arp_map = {}  # IP -> MAC
        try:
            transport = await UdpTransportTarget.create(
                (self.target_ip, 161), timeout=2.0, retries=1
            )

            # Walk the ipNetToMediaPhysAddress table
            iterator = walk_cmd(
                SnmpEngine(),
                CommunityData(self.community),
                transport,
                ContextData(),
                ObjectType(ObjectIdentity("1.3.6.1.2.1.4.22.1.2")),
                lexicographicMode=False,
            )

            async for errorIndication, errorStatus, errorIndex, varBinds in iterator:
                if errorIndication or errorStatus:
                    continue

                for varBind in varBinds:
                    # OID ends with the IP address. Value is the MAC.
                    # OID format: ...1.3.6.1.2.1.4.22.1.2.INTERFACE.IP.IP.IP.IP
                    oid_parts = varBind[0].getOid().asTuple()
                    ip_parts = oid_parts[-4:]  # Last 4 are the IP
                    ip_addr = ".".join(str(x) for x in ip_parts)

                    try:
                        mac_bytes = varBind[1].asNumbers()
                        if len(mac_bytes) == 6:
                            mac_str = ":".join([f"{b:02X}" for b in mac_bytes])
                            arp_map[ip_addr] = mac_str
                    except:
                        pass
            return arp_map
        except Exception as e:
            logger.error(f"SNMP Failure: {e}")
            return {}

    def _enrich_data(self, arp_map):
        """
        Combines SNMP MACs with mDNS Hostnames
        Returns list of dicts: [{'mac': '...', 'ip': '...', 'hostname': '...'}]
        """
        results = []
        for ip, mac in arp_map.items():
            # Check if we found a hostname for this IP via mDNS
            hostname = self.mdns.cache.get(ip)

            # Determine if MAC is randomized (2nd char is 2, 6, A, E)
            # E.g. x2:..., x6:..., xA:..., xE:...
            is_random = mac[1] in ["2", "6", "A", "E"]

            results.append(
                {"mac": mac, "ip": ip, "hostname": hostname, "is_random": is_random}
            )
        return results

    # ===========================
    # INTELLIGENCE ENGINE
    # ===========================
    def _process_presence(self, active_devices_data):
        with self.app.app_context():
            try:
                # 1. Load Knowledge Base
                db_devices = Device.query.all()
                device_map = {d.mac_address: d for d in db_devices}

                current_active_macs = set()
                new_arrivals = []

                for data in active_devices_data:
                    mac = data["mac"]
                    current_active_macs.add(mac)

                    # --- IDENTIFICATION LOGIC ---
                    if mac in device_map:
                        # Existing Device
                        device = device_map[mac]
                        self._update_device_metadata(device, data)

                        if not device.is_home:
                            self._handle_change(device, True)
                            new_arrivals.append(device)
                        else:
                            # Heartbeat update
                            device.last_seen = datetime.now()
                    else:
                        # New / Unknown Device
                        new_device = self._register_new_device(data)
                        device_map[mac] = new_device  # Add to local map
                        self._handle_change(new_device, True)
                        new_arrivals.append(new_device)

                # 2. Handle Departures
                for mac, device in device_map.items():
                    if mac not in current_active_macs and device.is_home:
                        self._handle_change(device, False)

                db.session.commit()

                # 3. Run Temporal Correlation on New Arrivals
                if new_arrivals:
                    self._analyze_correlations(new_arrivals)

            except Exception as e:
                logger.error(f"Processing Error: {e}")
                db.session.rollback()

    def _update_device_metadata(self, device, data):
        """Updates IP, Hostname, and Random flag"""
        if data["ip"]:
            device.last_ip = data["ip"]
        if data["hostname"]:
            device.hostname = data["hostname"]
        device.is_randomized_mac = data["is_random"]

        # OUI Vendor Lookup (Simple Heuristic)
        if not device.vendor and not device.is_randomized_mac:
            try:
                # Basic check, or integration with local OUI file
                oui = EUI(device.mac_address).oui.registration().org
                device.vendor = oui
            except:
                pass

    def _register_new_device(self, data):
        """Auto-adds new device with intelligent naming"""
        name = f"Unknown ({data['mac'][-5:]})"

        # Logic: If we found a hostname like "Kaias-iPhone", USE IT
        if data["hostname"]:
            name = f"{data['hostname']} (Auto)"
        elif data["is_random"]:
            name = f"Private MAC Device ({data['mac'][-2:]})"

        new_dev = Device(
            mac_address=data["mac"],
            name=name,
            hostname=data["hostname"],
            is_randomized_mac=data["is_random"],
            last_ip=data["ip"],
            is_home=True,
            track_presence=False,  # Default to False for unknowns to prevent noise
        )
        db.session.add(new_dev)
        # Flush to get ID
        db.session.flush()
        return new_dev

    def _analyze_correlations(self, new_devices):
        """
        TEMPORAL CORRELATION:
        If an unknown device arrives at the same time as a known person,
        log a suggestion.
        """
        try:
            # Look for devices that arrived in the last 5 minutes
            window = datetime.now() - timedelta(minutes=5)

            # Find KNOWN people who arrived recently
            recent_known_events = (
                db.session.query(PresenceEvent, Device)
                .join(Device)
                .filter(PresenceEvent.timestamp >= window)
                .filter(PresenceEvent.event_type == "arrived")
                .filter(Device.owner != None)  # Only look at assigned owners
                .all()
            )

            owners_arrived = set(dev.owner for evt, dev in recent_known_events)

            for unknown_dev in new_devices:
                if unknown_dev.owner:
                    continue  # Skip if already owned

                # CORRELATION 1: Hostname Match
                # If hostname is "Ethans-iPhone", and we know an "Ethan", suggest it.
                if unknown_dev.hostname:
                    for owner in ["Kaia", "Karys", "Ethan", "Jared"]:
                        if owner.lower() in unknown_dev.hostname.lower():
                            logger.info(
                                f"CORRELATION: {unknown_dev.mac_address} matches name {owner}"
                            )
                            # Auto-assign? Or just log? Let's auto-assign if strong match
                            unknown_dev.owner = owner
                            unknown_dev.track_presence = True
                            unknown_dev.name = f"{owner}'s Device (Auto)"

                # CORRELATION 2: Temporal Co-occurrence
                # If "Unknown" arrived with "Karys", note it.
                if owners_arrived:
                    owners_str = ", ".join(owners_arrived)
                    logger.info(
                        f"CORRELATION: {unknown_dev.name} arrived with {owners_str}"
                    )
                    # In a robust system, we would increment a 'score' in a separate table.
                    # For now, we rename the device to give the user a hint
                    if "Unknown" in unknown_dev.name:
                        unknown_dev.name = (
                            f"Unknown (Arrived w/ {list(owners_arrived)[0]})"
                        )

            db.session.commit()

        except Exception as e:
            logger.error(f"Correlation Logic Error: {e}")

    def _handle_change(self, device, is_now_home):
        now = datetime.now()
        event_type = "arrived" if is_now_home else "left"
        device.is_home = is_now_home
        device.last_seen = now if is_now_home else device.last_seen

        # Only log event if we are actually tracking presence or debugging
        if device.track_presence:
            presence_event = PresenceEvent(
                device_id=device.id, event_type=event_type, timestamp=now
            )
            db.session.add(presence_event)

            # Real-time Push
            self.socketio.emit(
                "presence_update",
                {
                    "device_id": device.id,
                    "name": device.name,
                    "owner": device.owner,
                    "event": event_type,
                    "is_home": is_now_home,
                },
            )
            logger.info(f"PRESENCE: {device.name} has {event_type}")

    # --- API PASS-THROUGHS ---
    def get_devices(self):
        with self.app.app_context():
            return [d.to_dict() for d in Device.query.all()]

    def update_device(self, device_id, **kwargs):
        with self.app.app_context():
            dev = Device.query.get(device_id)
            if not dev:
                return False, "Not found"
            for k, v in kwargs.items():
                if hasattr(dev, k) and v is not None:
                    setattr(dev, k, v)
            db.session.commit()
            return True, "Updated"

    def remove_device(self, device_id):
        with self.app.app_context():
            Device.query.filter_by(id=device_id).delete()
            db.session.commit()
            return True, "Deleted"

    def get_status(self):
        return {
            "monitoring": self.monitoring,
            "target_ip": self.target_ip,
            "mdns_cache_size": len(self.mdns.cache),
        }

    def cleanup(self):
        self.monitoring = False
        self.zeroconf.close()
