import logging
import multiprocessing
import queue
import re
import threading
from datetime import datetime, timedelta

from netaddr import EUI

from app.extensions import db
from app.models import Device, DeviceAssociation, NetworkSnapshot, PresenceEvent
from app.services.core import BaseService
from app.services.event_service import bus
from app.services.scanner_worker import scanner_process_entry

logger = logging.getLogger(__name__)


class IntelligentPresenceMonitor(BaseService):
    def __init__(self, app, target_ip, community, scan_interval=60):
        super().__init__("PresenceMonitor")

        self.app = app
        self.target_ip = target_ip
        # Community string kept for config compatibility, but logic uses ARP/Ping
        self.community = community
        self.scan_interval = scan_interval

        # Threading/Process State
        self.result_queue = None
        self.stop_event = None
        self.scan_process = None
        self.consumer_thread = None

        # Logic Configuration
        self.correlation_threshold = 0.65
        self.scan_count = 0
        self.snapshot_interval = 10

    def start(self):
        """Start the scanner process and consumer thread."""
        if self.running:
            return

        logger.info(f"Starting {self.name} (Interval: {self.scan_interval}s)...")
        self.running = True

        # 1. Setup IPC
        self.result_queue = multiprocessing.Queue()
        self.stop_event = multiprocessing.Event()

        # 2. Start Scanner (Isolated Process)
        # This prevents network I/O blocking the main web thread
        self.scan_process = multiprocessing.Process(
            target=scanner_process_entry,
            args=(
                self.target_ip,
                self.community,
                self.scan_interval,
                self.result_queue,
                self.stop_event,
            ),
            name="SheoakScanner",
            daemon=True,
        )
        self.scan_process.start()

        # 3. Start Consumer (Background Thread)
        # Ingests results and writes to SQLite
        self.consumer_thread = threading.Thread(
            target=self._consume_results, name="PresenceConsumer", daemon=True
        )
        self.consumer_thread.start()

    def stop(self):
        """Graceful shutdown."""
        if not self.running:
            return

        logger.info(f"Stopping {self.name}...")
        self.running = False

        if self.stop_event:
            self.stop_event.set()

        if self.scan_process:
            self.scan_process.join(timeout=2)
            if self.scan_process.is_alive():
                self.scan_process.terminate()

    def _consume_results(self):
        """Loop: Read Queue -> Write DB."""
        while self.running:
            try:
                # Block for 1s to allow checking 'self.running' periodically
                results = self.result_queue.get(timeout=1)

                # CRITICAL: DB Operations must happen in App Context
                with self.app.app_context():
                    self._process_presence_batch(results)

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Presence Consumer Error: {e}", exc_info=True)

    def _process_presence_batch(self, active_devices):
        """
        Reconcile scan results with Database state.
        This is the only place logic determines 'Who is Home'.
        """
        try:
            # 1. Load State
            db_devices = Device.query.all()
            device_map = {d.mac_address: d for d in db_devices}
            current_active_macs = set()

            # 2. Update Active Devices
            for data in active_devices:
                mac = data["mac"]
                current_active_macs.add(mac)

                device = device_map.get(mac)
                if device:
                    self._update_device_metadata(device, data)
                    if not device.is_home:
                        self._handle_presence_change(device, True, data)
                    else:
                        device.last_seen = datetime.now()
                else:
                    # New Device Discovery
                    new_dev = self._register_new_device(data)
                    device_map[mac] = new_dev
                    self._handle_presence_change(new_dev, True, data)

            # 3. Handle Departures
            # (Devices in DB marked 'home' but NOT in current scan)
            for mac, device in device_map.items():
                if mac not in current_active_macs and device.is_home:
                    self._handle_presence_change(device, False, {})

            # 4. Save Heartbeat (Network Snapshot)
            # This allows the Frontend to know the monitor is alive
            self._save_network_snapshot(active_devices)

            db.session.commit()

        except Exception as e:
            db.session.rollback()
            logger.error(f"Batch Processing Failed: {e}")

    def _register_new_device(self, data):
        """Creates a new Device entry."""
        mac = data["mac"]
        hostname = data.get("hostname", "")
        name = f"{hostname} (Auto)" if hostname else f"Unknown ({mac[-5:]})"

        dev = Device(
            mac_address=mac,
            name=name,
            hostname=hostname,
            is_randomized_mac=data.get("is_random", False),
            last_ip=data.get("ip"),
            is_home=True,
            track_presence=False,
            first_seen=datetime.now(),
            last_seen=datetime.now(),
            mdns_services=data.get("mdns_services", []),
            device_metadata=data.get("device_info", {}),
        )

        if not dev.is_randomized_mac:
            try:
                dev.vendor = EUI(mac).oui.registration().org
            except:
                pass

        db.session.add(dev)
        db.session.flush()
        return dev

    def _update_device_metadata(self, device, data):
        """Updates device details from scan data."""
        if data.get("ip") and data["ip"] != device.last_ip:
            hist = list(device.ip_history or [])
            hist.append({"ip": data["ip"], "ts": datetime.now().isoformat()})
            device.ip_history = hist[-50:]
            device.last_ip = data["ip"]

        if data.get("hostname"):
            device.hostname = data["hostname"]

        meta = dict(device.device_metadata or {})
        if data.get("device_info"):
            meta.update(data["device_info"])
        device.device_metadata = meta

        hour = datetime.now().hour
        times = list(device.typical_connection_times or [])
        if hour not in times:
            times.append(hour)
            device.typical_connection_times = times

    def _handle_presence_change(self, device, is_home, data):
        event_type = "arrived" if is_home else "left"
        device.is_home = is_home
        device.last_seen = datetime.now()

        if device.track_presence or device.linked_to_device_id:
            event = PresenceEvent(
                device_id=device.id,
                event_type=event_type,
                ip_address=data.get("ip") or device.last_ip,
                hostname=data.get("hostname") or device.hostname,
            )
            db.session.add(event)

            bus.emit(
                "presence_update",
                {"id": device.id, "name": device.name, "event": event_type, "is_home": is_home},
            )
            logger.info(f"PRESENCE: {device.name} {event_type}")

    def _correlate_mac_addresses(self, new_devices):
        tracked_candidates = Device.query.filter(
            Device.track_presence == True,
            Device.is_randomized_mac == False,
        ).all()

        for new_dev in new_devices:
            if not new_dev.is_randomized_mac:
                continue

            fp_new = self._build_fingerprint(new_dev)
            best_match = None
            best_score = 0.0

            for candidate in tracked_candidates:
                fp_candidate = self._build_fingerprint(candidate)
                score = self._calculate_similarity(fp_new, fp_candidate)

                if score > best_score and score >= self.correlation_threshold:
                    best_score = score
                    best_match = candidate

            if best_match:
                logger.info(f"Linked {new_dev.mac_address} -> {best_match.name} ({best_score:.2f})")
                new_dev.linked_to_device_id = best_match.id
                new_dev.link_confidence = best_score
                new_dev.name = f"{best_match.name} (Random MAC)"
                new_dev.track_presence = True

    def _build_fingerprint(self, device):
        return {
            "hostname_pattern": self._extract_hostname_pattern(device.hostname),
            "vendor": device.vendor,
            "mdns_services": set(device.mdns_services or []),
            "connection_times": set(device.typical_connection_times or []),
        }

    def _extract_hostname_pattern(self, hostname):
        if not hostname:
            return None
        hostname = hostname.lower()
        patterns = ["iphone", "ipad", "watch", "macbook", "android", "galaxy", "pixel"]
        for p in patterns:
            if p in hostname:
                return p
        return re.sub(r"[\d\-]+", "", hostname).strip()

    def _calculate_similarity(self, fp1, fp2):
        score = 0.0
        weights = 0.0

        if fp1["hostname_pattern"] and fp2["hostname_pattern"]:
            if fp1["hostname_pattern"] == fp2["hostname_pattern"]:
                score += 0.5
                weights += 0.5

        if fp1["mdns_services"] and fp2["mdns_services"]:
            overlap = len(fp1["mdns_services"] & fp2["mdns_services"])
            if overlap > 0:
                score += 0.3
                weights += 0.3

        if fp1["connection_times"] and fp2["connection_times"]:
            overlap = len(fp1["connection_times"] & fp2["connection_times"])
            total = len(fp1["connection_times"] | fp2["connection_times"])
            if total > 0:
                score += (overlap / total) * 0.2
                weights += 0.2

        return score / weights if weights > 0 else 0.0

    def _update_co_occurrences(self, active_devices):
        if len(active_devices) < 2:
            return

        for i, d1 in enumerate(active_devices):
            for d2 in active_devices[i + 1 :]:
                assoc = DeviceAssociation.query.filter(
                    (
                        (DeviceAssociation.device1_id == d1.id)
                        & (DeviceAssociation.device2_id == d2.id)
                    )
                    | (
                        (DeviceAssociation.device1_id == d2.id)
                        & (DeviceAssociation.device2_id == d1.id)
                    )
                ).first()

                if assoc:
                    assoc.co_occurrence_count += 1
                    assoc.last_seen_together = datetime.now()
                else:
                    assoc = DeviceAssociation(
                        device1_id=d1.id,
                        device2_id=d2.id,
                        association_type="co_occurrence",
                        confidence=0.5,
                    )
                    db.session.add(assoc)

    def _save_network_snapshot(self, active_devices):
        """Save a snapshot for history and health checks."""
        snap = NetworkSnapshot(
            device_count=len(active_devices),
            devices_present=[{"mac": d["mac"], "ip": d["ip"]} for d in active_devices],
            timestamp=datetime.now(),
        )
        db.session.add(snap)

        # Cleanup old snapshots (keep 3 days)
        cutoff = datetime.now() - timedelta(days=3)
        NetworkSnapshot.query.filter(NetworkSnapshot.timestamp < cutoff).delete()
