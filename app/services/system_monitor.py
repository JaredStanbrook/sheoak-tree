import os
import subprocess
from datetime import datetime

from app.services.core import ThreadedService
from app.services.event_service import bus


class SystemMonitor(ThreadedService):
    def __init__(self, app):
        # Run every 60 seconds
        super().__init__("SystemMonitor", interval=60.0)
        self.app = app
        self.log_file = os.path.join(self.app.instance_path, "system_events.txt")
        self.last_internet_state = True

        os.makedirs(self.app.instance_path, exist_ok=True)

    def run(self):
        """Periodic logic called by ThreadedService."""
        self.check_connectivity()

    def check_connectivity(self):
        # Ping Google DNS
        try:
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
            # Just log, ThreadedService wrapper handles the loop
            print(f"Connectivity check failed: {e}")

    def _log_event(self, component, status):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(self.log_file, "a") as f:
                f.write(f"[{ts}] {component}: {status}\n")
        except Exception:
            pass
