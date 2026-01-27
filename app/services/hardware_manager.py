"""
Universal Hardware Service Layer
Orchestrates hardware strategies and provides data access for the API.
"""

import json
import logging
import threading
from datetime import datetime, timedelta

from app.extensions import db
from app.models import Event, Hardware
from app.services.core import ThreadedService
from app.services.event_service import bus
from app.services.hardware_strategies import GPIO, HardwareFactory

logger = logging.getLogger(__name__)


class HardwareManager(ThreadedService):
    def __init__(self, app):
        # High frequency poll (0.1s)
        super().__init__("HardwareManager", interval=0.1)
        self.app = app
        self._lock = threading.RLock()

        # Maps hardware_id -> Strategy Instance
        self.strategies = {}

        # Global GPIO Setup (done once)
        try:
            GPIO.setmode(GPIO.BCM)
        except Exception as e:
            logger.error(f"GPIO Global Setup Failed: {e}")

    def start(self):
        """Initial startup: Load config and start thread."""
        if self.running:
            return

        # Load initial config synchronously
        self.reload_config()

        # Start the polling loop
        super().start()

    def run(self):
        """The main polling loop (Hot Path)."""
        # Acquire lock to ensure we don't iterate while reloading
        with self._lock:
            # Create a shallow copy of values to iterate safely if lock granularity needs reduction
            # However, for 0.1s interval, holding lock during lightweight GPIO read is safest.
            active_strategies = list(self.strategies.values())

        for strategy in active_strategies:
            try:
                # Read hardware state
                result = strategy.read()
                if result:
                    val, unit = result
                    self._handle_event(strategy, val, unit)
            except Exception as e:
                logger.error(f"Error reading hardware {strategy.name}: {e}")

    def reload_config(self):
        """
        Thread-safe hot reload of hardware configuration.
        Call this explicitly after DB changes.
        """
        logger.info("Reloading hardware configuration...")

        with self.app.app_context():
            # 1. Fetch enabled hardware definitions
            hw_definitions = Hardware.query.filter_by(enabled=True).all()

            # 2. Pre-calculate strategies (Prepare Phase)
            # We do this OUTSIDE the lock to minimize blocking the run loop
            new_strategies = {}

            for hw_model in hw_definitions:
                try:
                    # Create the strategy (this parses config, but doesn't touch GPIO yet)
                    strategy = HardwareFactory.create_strategy(hw_model)
                    if strategy:
                        # Store config hash for diffing
                        strategy._config_hash = self._compute_config_hash(hw_model)
                        new_strategies[hw_model.id] = strategy
                except Exception as e:
                    logger.error(f"Failed to factory strategy for {hw_model.name}: {e}")

            # 3. Swap and Setup (Critical Section)
            with self._lock:
                changes = {"added": 0, "updated": 0, "removed": 0, "kept": 0}
                final_map = {}

                for hw_id, new_strat in new_strategies.items():
                    existing_strat = self.strategies.get(hw_id)

                    # Check if we can preserve the existing instance
                    if (
                        existing_strat
                        and existing_strat.driver_interface == new_strat.driver_interface
                        and getattr(existing_strat, "_config_hash", None) == new_strat._config_hash
                    ):
                        # CONFIG UNCHANGED: Keep existing (preserves debouncing/state)
                        final_map[hw_id] = existing_strat
                        changes["kept"] += 1
                    else:
                        # NEW or CHANGED: Initialize new strategy
                        try:
                            # Safe to call setup() on active pins (re-configures them)
                            new_strat.setup()
                            final_map[hw_id] = new_strat

                            if existing_strat:
                                changes["updated"] += 1
                            else:
                                changes["added"] += 1
                        except Exception as e:
                            logger.error(f"Failed to setup hardware {new_strat.name}: {e}")
                            # If setup fails, try to keep old one or drop? Drop to be safe.
                            continue

                # Identify removed hardware
                for old_id in self.strategies:
                    if old_id not in final_map:
                        changes["removed"] += 1
                        # Optional: strategy.teardown() if we implemented it

                # Atomic Swap
                self.strategies = final_map

                logger.info(f"Hardware Reload Complete: {changes}")
                return changes

    def _compute_config_hash(self, hw_model):
        """Helper to detect configuration changes."""
        # Simple string representation of relevant fields
        fingerprint = {
            "driver": hw_model.driver_interface,
            "type": hw_model.type,
            "name": hw_model.name,
            "enabled": hw_model.enabled,
            "config": hw_model.configuration,
        }
        return json.dumps(fingerprint, sort_keys=True)

    def _handle_event(self, strategy, value, unit):
        """Processes valid hardware events."""
        now = datetime.now()

        # Emit Payload (UI update)
        payload = strategy.get_snapshot(value)
        payload["unit"] = unit
        bus.emit("hardware_event", payload)

        # Persist Event
        # Note: ThreadedService runs in main process context, but we need fresh app context for DB
        try:
            with self.app.app_context():
                db.session.add(
                    Event(hardware_id=strategy.id, value=value, unit=unit, timestamp=now)
                )
                db.session.commit()
        except Exception as e:
            logger.error(f"DB Write Failed: {e}")

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
        """Custom cleanup hook called by ServiceManager on shutdown."""
        GPIO.cleanup()
