import time
import threading
import logging
import asyncio
from datetime import datetime, timedelta

from pysnmp.hlapi.v3arch.asyncio import *

from app.extensions import socketio, db
from app.models import Device, PresenceEvent

logger = logging.getLogger(__name__)


class PresenceMonitor:
    """
    Monitors network presence by querying a router's ARP table via SNMP.
    Updated for PySNMP v7+ (AsyncIO).
    """

    def __init__(self, app, target_ip, community, scan_interval=60):
        self.app = app
        self.target_ip = target_ip
        self.community = community
        self.scan_interval = scan_interval
        self.socketio = socketio
        self._lock = threading.Lock()

        # Runtime state
        self.monitoring = True
        self.last_scan_time = None

        # Start background monitoring thread
        self.monitor_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self.monitor_thread.start()

        logger.info(
            f"PresenceMonitor initialized - scanning {target_ip} every {scan_interval}s"
        )

    def _scan_loop(self):
        """Background thread that periodically scans for active devices"""
        logger.info("Starting Presence Monitor scan loop")

        while self.monitoring:
            try:
                self.last_scan_time = datetime.now()

                # We use a helper to run the async SNMP task in this synchronous thread
                active_macs = self._run_async_scan()

                if active_macs is not None:
                    self._process_presence(active_macs)
                else:
                    logger.warning("Failed to retrieve active MACs from router")

                time.sleep(self.scan_interval)

            except Exception as e:
                logger.error(f"Error in presence scan loop: {e}")
                time.sleep(self.scan_interval)

    def _run_async_scan(self):
        """Helper to run the async SNMP walker in a synchronous context"""
        try:
            return asyncio.run(self.get_active_macs_async())
        except Exception as e:
            logger.error(f"AsyncIO Loop Error: {e}")
            return None

    async def get_active_macs_async(self):
        """
        Async implementation of SNMP Walk using PySNMP v7 walk_cmd.
        OID: 1.3.6.1.2.1.4.22.1.2 (ipNetToMediaPhysAddress)
        """
        try:
            active_macs = set()

            # Create the transport target (Async in v7)
            # Note: We must await the creation of the transport
            transport = await UdpTransportTarget.create(
                (self.target_ip, 161), timeout=2.0, retries=1
            )

            # Use walk_cmd generator (replaces nextCmd)
            # lexicographicMode=False stops the walk when we leave the OID subtree
            iterator = walk_cmd(
                SnmpEngine(),
                CommunityData(self.community),
                transport,
                ContextData(),
                ObjectType(ObjectIdentity("1.3.6.1.2.1.4.22.1.2")),
                lexicographicMode=False,
            )

            async for errorIndication, errorStatus, errorIndex, varBinds in iterator:
                if errorIndication:
                    logger.error(f"SNMP error: {errorIndication}")
                    return None

                elif errorStatus:
                    logger.error(f"SNMP error: {errorStatus.prettyPrint()}")
                    return None

                else:
                    for varBind in varBinds:
                        try:
                            # varBind[1] is the value object
                            mac_bytes = varBind[1].asNumbers()

                            if len(mac_bytes) == 6:
                                mac_address = ":".join([f"{b:02X}" for b in mac_bytes])
                                active_macs.add(mac_address)
                        except AttributeError:
                            continue

            logger.info(f"Found {len(active_macs)} active devices on network")
            return active_macs

        except Exception as e:
            logger.error(f"Error querying SNMP: {e}")
            return None

    def _process_presence(self, active_macs):
        """
        Compare active MACs with database and update presence status.
        AUTO-DISCOVERY ENABLED: Adds unknown devices automatically.
        """
        with self.app.app_context():
            try:
                # 1. Get all known devices from DB
                devices = Device.query.all()
                device_map = {d.mac_address: d for d in devices}

                # 2. Process all Active MACs (Arriving or Staying)
                for mac in active_macs:
                    # Normalize MAC to uppercase to avoid mismatch
                    mac = mac.upper()

                    if mac in device_map:
                        # CASE A: Known device is online
                        device = device_map[mac]
                        if not device.is_home:
                            # It just arrived
                            self._handle_presence_change(device, is_now_home=True)
                        else:
                            # It's still here, just update timestamp
                            device.last_seen = datetime.now()
                    else:
                        # CASE B: Auto-Discover new device
                        self._add_discovered_device(mac)

                # 3. Process devices NOT in active list (Leaving)
                for mac, device in device_map.items():
                    if mac not in active_macs and device.is_home:
                        self._handle_presence_change(device, is_now_home=False)

                db.session.commit()

            except Exception as e:
                logger.error(f"Error processing presence: {e}")
                db.session.rollback()

    def _add_discovered_device(self, mac_address):
        """Helper to register a new device found during scan"""
        try:
            logger.info(f"Auto-discovering new device: {mac_address}")

            # Create generic name
            new_device = Device(
                mac_address=mac_address,
                name=f"Unknown Device ({mac_address[-5:]})",  # e.g. "Unknown Device (A1:B2)"
                owner="Unknown",
                is_home=True,
                last_seen=datetime.now(),
            )

            db.session.add(new_device)
            # We commit immediately so it gets an ID and we can log the event
            db.session.commit()

            # Log the arrival event
            self._handle_presence_change(new_device, is_now_home=True)

        except Exception as e:
            logger.error(f"Failed to auto-add device {mac_address}: {e}")

    def _handle_presence_change(self, device, is_now_home):
        """Handle a device arriving or leaving."""
        now = datetime.now()
        event_type = "arrived" if is_now_home else "left"

        device.is_home = is_now_home
        device.last_seen = now if is_now_home else device.last_seen

        presence_event = PresenceEvent(
            device_id=device.id, event_type=event_type, timestamp=now
        )

        db.session.add(presence_event)
        db.session.commit()

        self.socketio.emit(
            "presence_update",
            {
                "device_id": device.id,
                "device_name": device.name,
                "owner": device.owner,
                "event_type": event_type,
                "is_home": is_now_home,
                "timestamp": now.isoformat(),
            },
        )

        logger.info(f"{device.name} ({device.owner}) has {event_type}")

    # --- API Helper Methods (unchanged) ---

    def get_devices(self):
        with self.app.app_context():
            devices = Device.query.all()
            return [d.to_dict() for d in devices]

    def add_device(self, mac_address, name, owner=None):
        with self.app.app_context():
            try:
                existing = Device.query.filter_by(mac_address=mac_address).first()
                if existing:
                    return False, "Device with this MAC address already exists"

                device = Device(
                    mac_address=mac_address.upper(),
                    name=name,
                    owner=owner,
                    is_home=False,
                )

                db.session.add(device)
                db.session.commit()
                return True, "Device added successfully"

            except Exception as e:
                db.session.rollback()
                return False, str(e)

    def remove_device(self, device_id):
        with self.app.app_context():
            try:
                device = Device.query.get(device_id)
                if not device:
                    return False, "Device not found"

                db.session.delete(device)
                db.session.commit()
                return True, "Device removed successfully"

            except Exception as e:
                db.session.rollback()
                return False, str(e)

    def update_device(self, device_id, name=None, owner=None, track_presence=None):
        with self.app.app_context():
            try:
                device = Device.query.get(device_id)
                if not device:
                    return False, "Device not found"

                if name:
                    device.name = name
                if owner:
                    device.owner = owner

                # Handle boolean flag update
                if track_presence is not None:
                    device.track_presence = track_presence

                db.session.commit()
                return True, "Device updated successfully"
            except Exception as e:
                db.session.rollback()
                return False, str(e)

    def get_presence_history(self, hours=24):
        with self.app.app_context():
            cutoff = datetime.now() - timedelta(hours=hours)
            events = (
                PresenceEvent.query.filter(PresenceEvent.timestamp >= cutoff)
                .order_by(PresenceEvent.timestamp.desc())
                .all()
            )
            return [e.to_dict() for e in events]

    def get_status(self):
        with self._lock:
            return {
                "monitoring": self.monitoring,
                "target_ip": self.target_ip,
                "scan_interval": self.scan_interval,
                "last_scan": (
                    self.last_scan_time.isoformat() if self.last_scan_time else None
                ),
            }

    def cleanup(self):
        logger.info("Stopping PresenceMonitor...")
        self.monitoring = False
        if self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
