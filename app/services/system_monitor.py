import logging
import os
import threading
import time
from datetime import datetime

from app.services.event_service import bus

logger = logging.getLogger(__name__)


class SystemMonitor:
    def __init__(self, app):
        self.app = app
        self.log_file = os.path.join(self.app.instance_path, "system_events.txt")
        os.makedirs(self.app.instance_path, exist_ok=True)

        self.last_internet_state = True
        self.running = True

        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        logger.info(f"System Monitor started. Logging to: {self.log_file}")

    def _monitor_loop(self):
        while self.running:
            try:
                self.check_connectivity()
            except Exception as e:
                logger.error(f"System Monitor Error: {e}")
            time.sleep(60)

    def check_connectivity(self):
        """Checks internet by pinging Google DNS"""
        # -c 1: one packet, -W 2: 2 second timeout
        response = os.system("ping -c 1 -W 2 8.8.8.8 > /dev/null 2>&1")
        is_up = response == 0

        # Only act if the state has changed
        if is_up != self.last_internet_state:
            self.last_internet_state = is_up
            self._log_event("Internet", "Online" if is_up else "Offline")

            bus.emit(
                "system_event",
                {
                    "name": "System Internet",
                    "event": "Connected" if is_up else "Disconnected",
                    "value": 1.0 if is_up else 0.0,
                    "timestamp": datetime.now().isoformat(),
                },
            )

    def _log_event(self, component, status):
        """Writes the event to the file in the Flask instance folder"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {component}: {status}\n"

        try:
            with open(self.log_file, "a") as f:
                f.write(log_entry)
            logger.info(f"Logged System Event: {component} is {status}")
        except Exception as e:
            logger.error(f"Failed to write to system log at {self.log_file}: {e}")

    def stop(self):
        self.running = False
