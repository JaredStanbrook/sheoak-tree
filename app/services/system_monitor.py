import logging
import os
import shutil
import subprocess
import time
from datetime import datetime

from app.services.core import ThreadedService
from app.services.event_service import bus

logger = logging.getLogger(__name__)


class SystemMonitor(ThreadedService):
    def __init__(self, app):
        # Run every 60 seconds
        super().__init__("SystemMonitor", interval=60.0)
        self.app = app
        self.log_file = os.path.join(self.app.instance_path, "system_events.txt")
        self.last_internet_state = True
        self._last_warn = {}

        os.makedirs(self.app.instance_path, exist_ok=True)

    def run(self):
        """Periodic logic called by ThreadedService."""
        self.check_connectivity()

    def check_connectivity(self):
        # Ping Google DNS
        try:
            if shutil.which("ping") is None:
                self._warn_once(
                    "ping_missing", "ping command not found; skipping connectivity check"
                )
                return
            # subprocess.run is cleaner than os.system
            ret = subprocess.run(
                ["ping", "-c", "1", "-W", "2", "8.8.8.8"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            is_up = ret.returncode == 0

            if is_up != self.last_internet_state:
                self.last_internet_state = is_up
                status_str = "Online" if is_up else "Offline"
                self._log_event("Internet", status_str)

                bus.emit(
                    "system_event",
                    {
                        "name": "System Internet",
                        "event": "Connected" if is_up else "Disconnected",
                        "value": 1.0 if is_up else 0.0,
                        "timestamp": datetime.now().isoformat(),
                    },
                )
        except Exception as e:
            logger.warning("Connectivity check failed: %s", e)

    def _log_event(self, component, status):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(self.log_file, "a") as f:
                f.write(f"[{ts}] {component}: {status}\n")
        except Exception:
            pass

    def _warn_once(self, key, message, interval_seconds=300):
        now = time.time()
        last = self._last_warn.get(key, 0)
        if now - last >= interval_seconds:
            logger.warning(message)
            self._last_warn[key] = now
