"""
SERVICE LIFECYCLE RULES:

1. __init__(self, app):
   - MUST be side-effect free.
   - MUST NOT query the database.
   - MUST NOT start threads or network listeners.
   - ONLY store configuration and dependencies.

2. start(self):
   - Executed explicitly by the ServiceManager at runtime.
   - perform I/O initialization here (GPIO, DB, Network).
   - Wrap DB calls in `with self.app.app_context():`.
   - Call `super().start()` last to spawn the worker thread.

3. run(self):
   - The logic that repeats in the background loop.
   - Will stop automatically when `self.running` becomes False.
"""

import logging
import threading
from abc import ABC, abstractmethod
from typing import Dict

logger = logging.getLogger("ServiceManager")


class BaseService(ABC):
    """Interface for all background services."""

    def __init__(self, name: str):
        self.name = name
        self.running = False

    @abstractmethod
    def start(self):
        """Start the service (non-blocking)."""
        pass

    @abstractmethod
    def stop(self):
        """Stop the service gracefully."""
        pass

    @property
    def health(self) -> dict:
        """Return health status."""
        return {"name": self.name, "running": self.running}


class ThreadedService(BaseService):
    """Helper for services that run a loop in a thread."""

    def __init__(self, name: str, interval: float = 1.0):
        super().__init__(name)
        self.interval = interval
        self._thread = None
        self._stop_event = threading.Event()

    def start(self):
        if self.running:
            return

        logger.info(f"Starting service: {self.name}")
        self.running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name=self.name, daemon=True)
        self._thread.start()

    def stop(self):
        if not self.running:
            return

        logger.info(f"Stopping service: {self.name}")
        self.running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            if self._thread.is_alive():
                logger.warning(f"Service {self.name} did not stop gracefully")

    def _run_loop(self):
        """Wrapper to handle crashes and loops."""
        logger.info(f"Service loop started: {self.name}")
        while self.running and not self._stop_event.is_set():
            try:
                self.run()
            except Exception as e:
                logger.error(f"Error in {self.name}: {e}", exc_info=True)
                # Prevent tight loop on error
                self._stop_event.wait(5.0)

            # Wait for interval or stop event
            self._stop_event.wait(self.interval)

    @abstractmethod
    def run(self):
        """Implement the periodic logic here."""
        pass


class ServiceManager:
    """Central registry for application services."""

    def __init__(self):
        self._services: Dict[str, BaseService] = {}
        self._is_active = False

    def register(self, service: BaseService):
        if service.name in self._services:
            logger.warning(f"Service {service.name} already registered")
            return
        self._services[service.name] = service
        logger.debug(f"Registered service: {service.name}")

    def get_service(self, name: str):
        return self._services.get(name)

    def start_all(self):
        """Start all services in order."""
        if self._is_active:
            return

        logger.info(">>> ORCHESTRATOR: Starting all background services")
        self._is_active = True
        for name, service in self._services.items():
            try:
                service.start()
            except Exception as e:
                logger.error(f"Failed to start {name}: {e}")

    def stop_all(self):
        """Stop all services in reverse order."""
        logger.info(">>> ORCHESTRATOR: Stopping all background services")
        self._is_active = False
        # Stop in reverse order of registration (LIFO)
        for name, service in reversed(list(self._services.items())):
            try:
                service.stop()
            except Exception as e:
                logger.error(f"Failed to stop {name}: {e}")

    def health_check(self):
        return {name: svc.health for name, svc in self._services.items()}
