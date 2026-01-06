import logging
import multiprocessing
import queue
import threading
import time
from datetime import datetime, timedelta

from app.extensions import socketio, db
from app.models import Device, PresenceEvent
from netaddr import EUI

# Import the isolated worker function
from app.services.scanner_worker import scanner_process_entry

logger = logging.getLogger(__name__)


class PresenceMonitor:
    def __init__(self, app, target_ip, community, scan_interval=60):
        self.app = app
        self.target_ip = target_ip
        self.community = community
        self.scan_interval = scan_interval
        self.socketio = socketio
        self.running = False

        self.result_queue = None
        self.stop_event = None
        self.scan_process = None
        self.consumer_thread = None

    def start(self):
        if self.running:
            return
        self.running = True

        logger.info("Starting PresenceMonitor Process...")

        # Use standard multiprocessing primitives
        self.result_queue = multiprocessing.Queue()
        self.stop_event = multiprocessing.Event()

        # Spawn the isolated process
        self.scan_process = multiprocessing.Process(
            target=scanner_process_entry,
            args=(
                self.target_ip,
                self.community,
                self.scan_interval,
                self.result_queue,
                self.stop_event,
            ),
            daemon=True,
        )
        self.scan_process.start()

        # Start local consumer thread
        self.consumer_thread = threading.Thread(
            target=self._consume_results, daemon=True
        )
        self.consumer_thread.start()

    def stop(self):
        if not self.running:
            return
        self.running = False
        logger.info("Stopping PresenceMonitor...")

        if self.stop_event:
            self.stop_event.set()

        if self.scan_process:
            self.scan_process.join(timeout=2)
            if self.scan_process.is_alive():
                self.scan_process.terminate()
            self.scan_process = None

    def cleanup(self):
        self.stop()

    def _consume_results(self):
        """
        GEVENT-SAFE CONSUMER:
        Uses get_nowait() + time.sleep() to avoid blocking the Gevent loop.
        """
        while self.running:
            try:
                # 1. Non-blocking check
                results = self.result_queue.get_nowait()
                self._process_presence_batch(results)
            except queue.Empty:
                # 2. Yield control to Gevent (time.sleep is patched by Gevent)
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"Consumer error: {e}")
                time.sleep(1)

    def _process_presence_batch(self, active_devices):
        with self.app.app_context():
            try:
                db_devices = Device.query.all()
                device_map = {d.mac_address: d for d in db_devices}
                current_active_macs = set()

                # ... (Same logic as before for DB updates) ...
                new_arrivals = []
                for data in active_devices:
                    mac = data["mac"]
                    current_active_macs.add(mac)
                    if mac in device_map:
                        device = device_map[mac]
                        self._update_meta(device, data)
                        if not device.is_home:
                            self._handle_change(device, True)
                            new_arrivals.append(device)
                        else:
                            device.last_seen = datetime.now()
                    else:
                        new_dev = self._register_new(data)
                        device_map[mac] = new_dev
                        self._handle_change(new_dev, True)
                        new_arrivals.append(new_dev)

                for mac, device in device_map.items():
                    if mac not in current_active_macs and device.is_home:
                        self._handle_change(device, False)

                db.session.commit()
                if new_arrivals:
                    self._correlate(new_arrivals)

            except Exception as e:
                logger.error(f"DB Update Error: {e}")
                db.session.rollback()

    # ... (Keep existing helper methods: _update_meta, _register_new, _handle_change, etc.) ...

    def _update_meta(self, device, data):
        if data["ip"]:
            device.last_ip = data["ip"]
        if data["hostname"]:
            device.hostname = data["hostname"]
        device.is_randomized_mac = data["is_random"]
        if not device.vendor and not device.is_randomized_mac:
            try:
                device.vendor = EUI(device.mac_address).oui.registration().org
            except:
                pass

    def _register_new(self, data):
        name = f"Unknown ({data['mac'][-5:]})"
        if data["hostname"]:
            name = f"{data['hostname']} (Auto)"

        dev = Device(
            mac_address=data["mac"],
            name=name,
            hostname=data["hostname"],
            is_randomized_mac=data["is_random"],
            last_ip=data["ip"],
            is_home=True,
            track_presence=False,
        )
        db.session.add(dev)
        db.session.flush()
        return dev

    def _handle_change(self, device, is_home):
        event = "arrived" if is_home else "left"
        device.is_home = is_home
        device.last_seen = datetime.now()

        if device.track_presence:
            db.session.add(PresenceEvent(device_id=device.id, event_type=event))

            # UPDATED: Use bus.emit instead of socketio.emit
            bus.emit(
                "presence_update",
                {
                    "device_id": device.id,
                    "name": device.name,
                    "event": event,
                    "is_home": is_home,
                },
            )
            logger.info(f"PRESENCE: {device.name} {event}")

    def _correlate(self, new_devices):
        pass

    # --- API PASS-THROUGHS ---
    def get_devices(self):
        with self.app.app_context():
            return [d.to_dict() for d in Device.query.all()]

    def get_status(self):
        return {
            "monitoring": self.running,
            "target_ip": self.target_ip,
            "scanner_alive": (
                self.scan_process.is_alive() if self.scan_process else False
            ),
        }

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

    def add_device(self, mac_address, name, owner=None):
        with self.app.app_context():
            if Device.query.filter_by(mac_address=mac_address).first():
                return False, "Device already exists"
            dev = Device(
                mac_address=mac_address,
                name=name,
                owner=owner,
                track_presence=True,
                is_home=False,
            )
            db.session.add(dev)
            db.session.commit()
            return True, "Device registered successfully"

    def get_presence_history(self, hours=24):
        with self.app.app_context():
            cutoff = datetime.now() - timedelta(hours=hours)
            events = (
                PresenceEvent.query.filter(PresenceEvent.timestamp >= cutoff)
                .order_by(PresenceEvent.timestamp.desc())
                .all()
            )
            return [e.to_dict() for e in events]
