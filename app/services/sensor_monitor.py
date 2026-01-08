"""Sensor Monitoring Service"""

import logging
import random
import threading
import time
from datetime import datetime, timedelta

from app.extensions import db
from app.models import Event, Sensor
from app.services.event_service import bus

logger = logging.getLogger(__name__)

try:
    import RPi.GPIO as GPIO
except (ImportError, RuntimeError):
    logger.warning("RPi.GPIO not found. Using Mock GPIO with Random Simulation.")

    class MockGPIO:
        """Mock GPIO for Non-Raspberry Pi Environments with Random Simulation"""

        BCM = "BCM"
        OUT = "OUT"
        IN = "IN"
        HIGH = 1
        LOW = 0
        PUD_UP = "PUD_UP"

        # Simulation State
        _pin_states = {}
        _input_pins = []
        _sim_running = False

        @classmethod
        def _start_sim(cls):
            if cls._sim_running:
                return
            cls._sim_running = True
            threading.Thread(target=cls._sim_loop, daemon=True).start()

        @classmethod
        def _sim_loop(cls):
            while cls._sim_running:
                time.sleep(random.uniform(2.0, 8.0))  # Random event every 2-8s
                if not cls._input_pins:
                    continue

                # Pick random pin and toggle it
                pin = random.choice(cls._input_pins)
                cls._pin_states[pin] = 1 if cls._pin_states.get(pin, 0) == 0 else 0
                logger.info(f"[MOCK SIM] Toggling Pin {pin} to {cls._pin_states[pin]}")

        @staticmethod
        def setmode(mode):
            pass

        @staticmethod
        def setwarnings(flag):
            pass

        @staticmethod
        def cleanup():
            MockGPIO._sim_running = False

        @staticmethod
        def setup(pin, mode, pull_up_down=None):
            if mode == MockGPIO.IN:
                if pin not in MockGPIO._input_pins:
                    MockGPIO._input_pins.append(pin)
                MockGPIO._pin_states[pin] = 0
                MockGPIO._start_sim()

        @staticmethod
        def output(pin, state):
            MockGPIO._pin_states[pin] = state

        @staticmethod
        def input(pin):
            return MockGPIO._pin_states.get(pin, 0)

    GPIO = MockGPIO


class MotionSensorApp:
    def __init__(self, app, debounce_ms=300):
        self.app = app
        self.debounce_ms = debounce_ms
        self._lock = threading.Lock()
        self.hardwares_cache = []
        self.last_activity_map = {}

        self._load_hardwares_to_cache()
        self._setup_gpio()

        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

    def _load_hardwares_to_cache(self):
        with self.app.app_context():
            if Sensor.query.count() == 0:
                self._seed_defaults()
            hardwares = Sensor.query.filter_by(enabled=True).all()
            self.hardwares_cache = []
            for s in hardwares:
                self.hardwares_cache.append(
                    {
                        "id": s.id,
                        "pin": s.pin,
                        "name": s.name,
                        "type": s.type,
                        "current_state": False,
                        "last_change": datetime.min,
                    }
                )

    def _seed_defaults(self):
        defaults = [
            Sensor(name="Living Room", pin=6, type="motion"),
            Sensor(name="Hallway", pin=2, type="motion"),
            Sensor(name="Front Door", pin=3, type="door"),
            Sensor(name="Kitchen", pin=18, type="motion"),
        ]
        db.session.add_all(defaults)
        db.session.commit()

    def _setup_gpio(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        for s in self.hardwares_cache:
            try:
                if s["type"] == "relay":
                    GPIO.setup(s["pin"], GPIO.OUT)
                    GPIO.output(s["pin"], GPIO.LOW)
                else:
                    GPIO.setup(s["pin"], GPIO.IN, pull_up_down=GPIO.PUD_UP)
            except Exception as e:
                logger.error(f"GPIO Error: {e}")

    def _monitor_loop(self):
        while self.monitoring:
            try:
                current_time = datetime.now()
                with self._lock:
                    for s in self.hardwares_cache:
                        if s["type"] == "relay":
                            continue

                        raw_val = GPIO.input(s["pin"])
                        is_active = raw_val == GPIO.HIGH

                        if is_active != s["current_state"]:
                            elapsed = (current_time - s["last_change"]).total_seconds() * 1000
                            if elapsed > self.debounce_ms:
                                self._handle_state_change(s, is_active, current_time)
                time.sleep(0.05)
            except Exception as e:
                logger.error(f"Loop Error: {e}")
                time.sleep(1)

    def _handle_state_change(self, hardware, new_state, timestamp):
        hardware["current_state"] = new_state
        hardware["last_change"] = timestamp

        event_name = "Activated"
        if hardware["type"] == "door":
            event_name = "Door Opened" if new_state else "Door Closed"
        elif hardware["type"] == "motion":
            event_name = "Motion Detected" if new_state else "Motion Cleared"
        if new_state:
            self.last_activity_map[hardware["name"]] = timestamp

        # 1. DB Log (Only significant events)
        should_log = True
        if hardware["type"] == "motion" and not new_state:
            should_log = False

        if should_log:
            with self.app.app_context():
                db.session.add(
                    Event(
                        hardware_id=hardware["id"],
                        value=1 if new_state else 0,
                        event_type=event_name,
                        timestamp=timestamp,
                    )
                )
                db.session.commit()

        # 2. SSE Emit (Replaces SocketIO)
        bus.emit(
            "hardware_event",
            {
                "hardware_id": hardware["id"],
                "name": hardware["name"],
                "event": event_name,
                "value": 1 if new_state else 0,
                "timestamp": timestamp.isoformat(),
            },
        )

    def toggle_hardware(self, hardware_id):
        with self._lock:
            target = next((s for s in self.hardwares_cache if s["id"] == hardware_id), None)
            if not target or target["type"] != "relay":
                return False, "Invalid"

            new_state = not target["current_state"]
            GPIO.output(target["pin"], GPIO.HIGH if new_state else GPIO.LOW)
            target["current_state"] = new_state

            # Emit SSE
            bus.emit(
                "hardware_event",
                {
                    "hardware_id": target["id"],
                    "name": target["name"],
                    "event": "Relay Toggled",
                    "value": 1 if new_state else 0,
                    "timestamp": datetime.now().isoformat(),
                },
            )
            return True, new_state

    # Data Access (Getters)
    def get_hardware_data(self):
        with self._lock:
            return [
                {
                    "id": s["id"],
                    "name": s["name"],
                    "type": s["type"],
                    "value": 1 if s["current_state"] else 0,
                    "last_activity": self.last_activity_map.get(
                        s["name"], datetime.min
                    ).isoformat(),
                }
                for s in self.hardwares_cache
            ]

    def add_hardware(self, name, pin, s_type):
        with self.app.app_context():
            if Sensor.query.filter_by(pin=pin).first():
                return False

            s = Sensor(name=name, pin=pin, type=s_type)
            db.session.add(s)
            db.session.commit()

            # Refresh Cache
            self._load_hardwares_to_cache()
            self._setup_gpio()  # Setup new pin
            return True

    def remove_hardware(self, hardware_id):
        with self.app.app_context():
            s = Sensor.query.get(hardware_id)
            if s:
                db.session.delete(s)
                db.session.commit()
                self._load_hardwares_to_cache()
                return True
            return False

    def get_frequency_data(self, hours=24, interval_minutes=30):
        with self.app.app_context():
            # 1. Setup Time Range (Standard)
            end_time = datetime.now()
            delta_min = end_time.minute % interval_minutes
            end_time = end_time - timedelta(
                minutes=delta_min,
                seconds=end_time.second,
                microseconds=end_time.microsecond,
            )
            start_time = end_time - timedelta(hours=hours)

            timestamps = []
            current = start_time
            while current <= end_time:
                timestamps.append(current)
                current += timedelta(minutes=interval_minutes)

            # 2. Fetch All Events (Ordered by Time is Critical here)
            events = (
                db.session.query(Event.hardware_id, Event.timestamp, Event.value)
                .filter(Event.timestamp >= start_time)
                .filter(Event.timestamp <= end_time)
                .order_by(Event.timestamp.asc())
                .all()
            )

            hardwares = Sensor.query.all()
            hardware_map = {s.id: s for s in hardwares}

            results = {}

            # 3. Setup State Tracker
            # This dictionary will store the last known value (0 or 1) for each hardware
            # Format: { "Front Door": 1, "Back Door": 0 }
            last_states = {}

            # Initialize result lists
            for s in hardwares:
                if "door" not in (s.type or "motion").lower():
                    results[s.name] = [0] * len(timestamps)
                else:
                    results[s.name] = []

            start_ts = start_time.timestamp()
            interval_seconds = interval_minutes * 60

            for hardware_id, evt_time, evt_value in events:
                if hardware_id not in hardware_map:
                    continue

                hardware = hardware_map[hardware_id]
                s_type = (hardware.type or "motion").lower()

                # --- DOORS: Deduplication Logic ---
                if "door" in s_type or "contact" in s_type:
                    # Check what the previous value for THIS hardware was
                    prev_val = last_states.get(hardware.name)

                    # ONLY add if the value has changed (or if it's the first time we see it)
                    if evt_value != prev_val:
                        results[hardware.name].append(
                            {
                                "x": evt_time.isoformat(),
                                "y": 1,
                                "state": "open" if evt_value == 1 else "closed",
                            }
                        )

                        # Update the tracker with the new current value
                        last_states[hardware.name] = evt_value

                # --- MOTION: Standard Binning ---
                else:
                    if evt_value == 1:
                        evt_ts = evt_time.timestamp()
                        index = int((evt_ts - start_ts) / interval_seconds)
                        if 0 <= index < len(timestamps):
                            results[hardware.name][index] += 1

            return {
                "hardwares": results,
                "timestamps": [t.isoformat() for t in timestamps],
                "interval_minutes": interval_minutes,
                "total_intervals": len(timestamps),
            }

    def get_activity_data(self, hours=24):
        with self.app.app_context():
            cutoff = datetime.now() - timedelta(hours=hours)
            # SQL Query is much faster than Pandas CSV read
            events = (
                Event.query.filter(Event.timestamp >= cutoff).order_by(Event.timestamp.desc()).all()
            )
            return [e.to_dict() for e in events]

    def cleanup(self):
        self.monitoring = False
        GPIO.cleanup()
