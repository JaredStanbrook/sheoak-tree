# app/services/sensor_monitor.py
import RPi.GPIO as GPIO
import time
import threading
import logging
from datetime import datetime, timedelta
from app.extensions import socketio, db
from app.models import Sensor, Event
from sqlalchemy import func

logger = logging.getLogger(__name__)


class MotionSensorApp:

    def __init__(self, app, debounce_ms=300):
        self.app = app  # Keep reference to Flask App for DB Context
        self.socketio = socketio
        self.debounce_ms = debounce_ms
        self._lock = threading.Lock()

        # Runtime Cache (To avoid hitting DB 20 times a second)
        self.sensors_cache = []
        self.last_activity_map = {}

        self._load_sensors_to_cache()
        self._setup_gpio()

        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

    def _load_sensors_to_cache(self):
        """Load sensors from DB into memory for fast loop access"""
        with self.app.app_context():
            # Create default sensors if DB is empty
            if Sensor.query.count() == 0:
                self._seed_defaults()

            # Load enabled sensors
            sensors = Sensor.query.filter_by(enabled=True).all()

            # Transform into simple objects for the loop
            self.sensors_cache = []
            for s in sensors:
                self.sensors_cache.append(
                    {
                        "id": s.id,
                        "pin": s.pin,
                        "name": s.name,
                        "type": s.type,
                        "current_state": False,
                        "last_change": datetime.min,
                    }
                )
            logger.info(f"Loaded {len(self.sensors_cache)} sensors from DB.")

    def _seed_defaults(self):
        """Initial Setup if fresh DB"""
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
        for s in self.sensors_cache:
            try:
                # NEW: Check type to decide Input vs Output
                if s["type"] == "relay":
                    GPIO.setup(s["pin"], GPIO.OUT)
                    # Default to OFF (Low) on boot
                    GPIO.output(s["pin"], GPIO.LOW)
                    s["current_state"] = False
                else:
                    # Standard Sensors (Motion/Door)
                    GPIO.setup(s["pin"], GPIO.IN, pull_up_down=GPIO.PUD_UP)
            except Exception as e:
                logger.error(f"GPIO Setup Error Pin {s['pin']}: {e}")

    def set_relay(self, state: bool):
        """
        Controls the 5V Relay.
        state: True for ON (High), False for OFF (Low)
        """
        with self._lock:
            self.relay_state = state
            GPIO.output(self.relay_pin, GPIO.HIGH if state else GPIO.LOW)

            # Optional: Emit socket event so UI updates immediately
            self.socketio.emit(
                "relay_event",
                {
                    "pin": self.relay_pin,
                    "state": "ON" if state else "OFF",
                    "timestamp": datetime.now().isoformat(),
                },
            )

            logger.info(f"Relay on Pin {self.relay_pin} set to {state}")
            return self.relay_state

    def _monitor_loop(self):
        logger.info("Starting DB-backed Monitor Loop")
        while self.monitoring:
            try:
                current_time = datetime.now()

                # We iterate over the CACHE, not the DB (Speed!)
                with self._lock:
                    for s in self.sensors_cache:
                        if s["type"] == "relay":
                            continue
                        try:
                            # Read Hardware
                            raw_val = GPIO.input(s["pin"])
                            is_active = raw_val == GPIO.HIGH

                            if is_active != s["current_state"]:
                                # Debounce
                                elapsed = (
                                    current_time - s["last_change"]
                                ).total_seconds() * 1000
                                if elapsed > self.debounce_ms:
                                    self._handle_state_change(
                                        s, is_active, current_time
                                    )
                        except Exception as e:
                            logger.error(f"Pin Read Error: {e}")

                time.sleep(0.05)
            except Exception as e:
                logger.error(f"Loop Error: {e}")
                time.sleep(1)

    def toggle_sensor(self, sensor_id):
        with self._lock:
            # Find the sensor in memory cache
            target = next((s for s in self.sensors_cache if s["id"] == sensor_id), None)

            if not target or target["type"] != "relay":
                return False, "Invalid sensor or not a relay"

            # Toggle State
            new_state = not target["current_state"]

            # Hardware Actuation
            GPIO.output(target["pin"], GPIO.HIGH if new_state else GPIO.LOW)

            # Update Cache
            target["current_state"] = new_state
            target["last_change"] = datetime.now()

            # Emit event so Frontend updates the button color immediately
            self.socketio.emit(
                "sensor_event",
                {
                    "sensor_id": target["id"],
                    "name": target["name"],
                    "event": "Relay Toggled",
                    "value": 1 if new_state else 0,
                    "timestamp": datetime.now().isoformat(),
                },
            )
            return True, new_state

    def _handle_state_change(self, sensor_obj, new_state, timestamp):
        # Update Cache
        sensor_obj["current_state"] = new_state
        sensor_obj["last_change"] = timestamp

        if new_state:
            self.last_activity_map[sensor_obj["name"]] = timestamp

        # Determine Event Details
        event_name = ""
        should_log = False

        if sensor_obj["type"] == "door":
            event_name = "Door Opened" if new_state else "Door Closed"
            should_log = True
        elif sensor_obj["type"] == "motion":
            if new_state:
                event_name = "Motion Detected"
                should_log = True
            else:
                event_name = "Motion Cleared"
                should_log = False  # Don't log clears to DB to save space

        # 1. Write to DB (Requires Context)
        if should_log:
            with self.app.app_context():
                new_event = Event(
                    sensor_id=sensor_obj["id"],
                    value=1 if new_state else 0,
                    event_type=event_name,
                    timestamp=timestamp,
                )
                db.session.add(new_event)
                db.session.commit()

        # 2. Emit Realtime
        self.socketio.emit(
            "sensor_event",
            {
                "sensor_id": sensor_obj["id"],
                "name": sensor_obj["name"],
                "event": event_name,
                "value": 1 if new_state else 0,
                "timestamp": timestamp.isoformat(),
            },
        )

    # --- Data Access Methods (Used by API) ---

    def get_sensor_data(self):
        # Return combination of DB config + Memory state
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
                for s in self.sensors_cache
            ]

    def add_sensor(self, name, pin, s_type):
        with self.app.app_context():
            if Sensor.query.filter_by(pin=pin).first():
                return False

            s = Sensor(name=name, pin=pin, type=s_type)
            db.session.add(s)
            db.session.commit()

            # Refresh Cache
            self._load_sensors_to_cache()
            self._setup_gpio()  # Setup new pin
            return True

    def remove_sensor(self, sensor_id):
        with self.app.app_context():
            s = Sensor.query.get(sensor_id)
            if s:
                db.session.delete(s)
                db.session.commit()
                self._load_sensors_to_cache()
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
                db.session.query(Event.sensor_id, Event.timestamp, Event.value)
                .filter(Event.timestamp >= start_time)
                .filter(Event.timestamp <= end_time)
                .order_by(Event.timestamp.asc())
                .all()
            )

            sensors = Sensor.query.all()
            sensor_map = {s.id: s for s in sensors}

            results = {}

            # 3. Setup State Tracker
            # This dictionary will store the last known value (0 or 1) for each sensor
            # Format: { "Front Door": 1, "Back Door": 0 }
            last_states = {}

            # Initialize result lists
            for s in sensors:
                if "door" not in (s.type or "motion").lower():
                    results[s.name] = [0] * len(timestamps)
                else:
                    results[s.name] = []

            start_ts = start_time.timestamp()
            interval_seconds = interval_minutes * 60

            for sensor_id, evt_time, evt_value in events:
                if sensor_id not in sensor_map:
                    continue

                sensor = sensor_map[sensor_id]
                s_type = (sensor.type or "motion").lower()

                # --- DOORS: Deduplication Logic ---
                if "door" in s_type or "contact" in s_type:

                    # Check what the previous value for THIS sensor was
                    prev_val = last_states.get(sensor.name)

                    # ONLY add if the value has changed (or if it's the first time we see it)
                    if evt_value != prev_val:
                        results[sensor.name].append(
                            {
                                "x": evt_time.isoformat(),
                                "y": 1,
                                "state": "open" if evt_value == 1 else "closed",
                            }
                        )

                        # Update the tracker with the new current value
                        last_states[sensor.name] = evt_value

                # --- MOTION: Standard Binning ---
                else:
                    if evt_value == 1:
                        evt_ts = evt_time.timestamp()
                        index = int((evt_ts - start_ts) / interval_seconds)
                        if 0 <= index < len(timestamps):
                            results[sensor.name][index] += 1

            return {
                "sensors": results,
                "timestamps": [t.isoformat() for t in timestamps],
                "interval_minutes": interval_minutes,
                "total_intervals": len(timestamps),
            }

    def get_activity_data(self, hours=24):
        with self.app.app_context():
            cutoff = datetime.now() - timedelta(hours=hours)
            # SQL Query is much faster than Pandas CSV read
            events = (
                Event.query.filter(Event.timestamp >= cutoff)
                .order_by(Event.timestamp.desc())
                .all()
            )
            return [e.to_dict() for e in events]

    def cleanup(self):
        self.monitoring = False
        GPIO.cleanup()
