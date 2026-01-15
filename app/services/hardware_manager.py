"""
Universal Hardware Service Layer
Orchestrates hardware strategies and provides data access for the API.
"""

import logging
import threading
import time
from datetime import datetime, timedelta

from app.extensions import db
from app.models import Event, Hardware
from app.services.event_service import bus
from app.services.hardware_strategies import GPIO, HardwareFactory

logger = logging.getLogger(__name__)


class HardwareManager:
    def __init__(self, app):
        self.app = app
        self._lock = threading.Lock()

        # Maps hardware_id -> Strategy Instance
        self.strategies = {}
        self.last_activity_map = {}

        # Initialize Hardware
        GPIO.setmode(GPIO.BCM)
        self._load_hardware()

        # Start Loop
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()

    def _load_hardware(self):
        """Loads hardware definitions from DB and instantiates strategies"""
        with self.app.app_context():
            if Hardware.query.count() == 0:
                self._seed_defaults()

            items = Hardware.query.filter_by(enabled=True).all()
            self.strategies = {}

            for item in items:
                strategy = HardwareFactory.create_strategy(item)
                if strategy:
                    strategy.setup()
                    self.strategies[item.id] = strategy
                    logger.info(f"Loaded hardware strategy: {item.name}")

    def _seed_defaults(self):
        defaults = [
            Hardware(
                name="Living Room",
                type="motion_sensor",
                driver_interface="gpio_binary",
                configuration={"pin": 6},
            ),
            Hardware(
                name="Hallway",
                type="motion_sensor",
                driver_interface="gpio_binary",
                configuration={"pin": 2},
            ),
            Hardware(
                name="Front Door",
                type="contact_sensor",
                driver_interface="gpio_binary",
                configuration={"pin": 3},
            ),
            Hardware(
                name="Kitchen Relay", driver_interface="gpio_relay", configuration={"pin": 18}
            ),
        ]
        db.session.add_all(defaults)
        db.session.commit()

    def _monitor_loop(self):
        """Universal Event Loop"""
        while self.running:
            try:
                # Iterate over strategies
                # Assuming self.strategies is Dict[int, HardwareStrategy]
                for hw_id, strategy in list(self.strategies.items()):
                    try:
                        result = strategy.read()

                        if result:
                            val, unit = result
                            # PASS THE STRATEGY OBJECT, NOT JUST ID
                            self._handle_event(strategy, val, unit)

                    except Exception as e:
                        logger.error(f"Error reading hw {hw_id}: {e}")

                time.sleep(0.1)  # Polling Interval TODO make configurable
            except Exception as e:
                logger.error(f"Hardware Loop Critical Error: {e}")
                time.sleep(1)  # Backoff on critical error

    def _handle_event(self, strategy, value, unit):
        """
        Processes a change in hardware state.
        :param strategy: The HardwareStrategy instance
        :param value: The new value
        :param unit: The unit of measurement
        """
        now = datetime.now()

        # 1. Update internal state tracking
        if value > 0:
            self.last_activity_map[strategy.name] = now

        # 2. Generate the Rich Payload using our new method
        # This resolves icons/labels on the SERVER side
        payload = strategy.get_snapshot(value)
        payload["unit"] = unit  # Add unit explicitly if needed

        # 3. Persist to DB
        with self.app.app_context():
            db.session.add(Event(hardware_id=strategy.id, value=value, unit=unit, timestamp=now))
            db.session.commit()

        # 4. Emit Enriched Data to Frontend
        # Frontend logic becomes very dumb: just display payload['ui']['icon']
        bus.emit("hardware_event", payload)

    # --- API Support Methods ---

    def get_hardware_data(self):
        """Returns current state of all hardware for the dashboard."""
        with self._lock:
            data = []
            for hw_id, strategy in self.strategies.items():
                data.append(
                    {
                        "id": hw_id,
                        "name": strategy.name,
                        "type": strategy.type,
                        "value": strategy.current_value,
                        "config": strategy.config,
                        "last_activity": self.last_activity_map.get(
                            strategy.name, datetime.min
                        ).isoformat(),
                    }
                )
            return data

    def toggle_hardware(self, hardware_id):
        """
        API Alias for execute_command('toggle').
        Maintains compatibility with /api/hardwares/<id>/toggle
        """
        success, msg = self.execute_command(hardware_id, "toggle")
        # API expects (success, result/state)
        # We need to return the new boolean state if successful, or error msg
        if success:
            # Check the new value from the strategy
            strategy = self.strategies.get(hardware_id)
            return True, (strategy.current_value == 1.0)
        return False, msg

    def execute_command(self, hw_id, command):
        """Generic command interface"""
        with self._lock:
            strategy = self.strategies.get(hw_id)
            if not strategy:
                return False, "Hardware not found"

            if command == "toggle" and hasattr(strategy, "toggle"):
                new_state_int = strategy.toggle()

                # Update strategy state immediately so get_hardware_data is correct
                strategy.current_value = 1.0 if new_state_int == GPIO.HIGH else 0.0

                # Emit event
                bus.emit(
                    "hardware_event",
                    {
                        "hardware_id": hw_id,
                        "name": strategy.name,
                        "event": "Toggled",
                        "value": strategy.current_value,
                        "timestamp": datetime.now().isoformat(),
                    },
                )
                return True, "Toggled"

            return False, "Command not supported"

    def get_activity_data(self, hours=24):
        """Returns raw event history."""
        with self.app.app_context():
            cutoff = datetime.now() - timedelta(hours=hours)
            events = (
                Event.query.filter(Event.timestamp >= cutoff).order_by(Event.timestamp.desc()).all()
            )
            # Map new 'hardware' relation to old 'hardware' dict keys if needed by frontend
            return [e.to_dict() for e in events]

    def get_frequency_data(self, hours=24, interval_minutes=30):
        """
        Aggregates events for the frequency graph.
        Adapted for the new Hardware/Event models.
        """
        with self.app.app_context():
            # 1. Setup Time Range
            end_time = datetime.now()
            # Align to nearest interval
            delta_min = end_time.minute % interval_minutes
            end_time = end_time - timedelta(
                minutes=delta_min, seconds=end_time.second, microseconds=end_time.microsecond
            )
            start_time = end_time - timedelta(hours=hours)

            timestamps = []
            current = start_time
            while current <= end_time:
                timestamps.append(current)
                current += timedelta(minutes=interval_minutes)

            # 2. Fetch Events
            events = (
                db.session.query(Event.hardware_id, Event.timestamp, Event.value)
                .filter(Event.timestamp >= start_time)
                .filter(Event.timestamp <= end_time)
                .order_by(Event.timestamp.asc())
                .all()
            )

            # 3. Process Data
            hardware_list = Hardware.query.all()
            hw_map = {h.id: h for h in hardware_list}
            results = {}
            last_states = {}

            # Initialize buckets
            for h in hardware_list:
                config_type = h.configuration.get("type", "generic")
                if config_type == "door":
                    results[h.name] = []
                else:
                    results[h.name] = [0] * len(timestamps)

            start_ts = start_time.timestamp()
            interval_seconds = interval_minutes * 60

            for hw_id, evt_time, evt_value in events:
                if hw_id not in hw_map:
                    continue

                hw = hw_map[hw_id]
                config_type = hw.configuration.get("type", "generic")

                # Door Logic (State Changes)
                if config_type == "door":
                    prev_val = last_states.get(hw.name)
                    # Deduplicate: only log if state changed
                    if evt_value != prev_val:
                        results[hw.name].append(
                            {
                                "x": evt_time.isoformat(),
                                "y": 1,
                                "state": "open" if evt_value > 0 else "closed",
                            }
                        )
                        last_states[hw.name] = evt_value

                # Motion/Generic Logic (Counts)
                else:
                    if evt_value > 0:  # Count "Active" events
                        evt_ts = evt_time.timestamp()
                        index = int((evt_ts - start_ts) / interval_seconds)
                        if 0 <= index < len(timestamps):
                            results[hw.name][index] += 1

            return {
                "hardwares": results,  # API expects "hardwares" key
                "timestamps": [t.isoformat() for t in timestamps],
                "interval_minutes": interval_minutes,
                "total_intervals": len(timestamps),
            }

    def cleanup(self):
        self.running = False
        GPIO.cleanup()
