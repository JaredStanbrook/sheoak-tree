import logging
import os

from flask import current_app

logger = logging.getLogger(__name__)


class ServiceManager:
    _instance = None

    def __init__(self):
        self._hardware_manager = None
        self._processor = None
        self._presence_monitor = None
        self._system_monitor = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = ServiceManager()
        return cls._instance

    @property
    def _should_run_services(self):
        """
        Determines if background services should start.
        Returns True if:
        1. We are in Production (Debug is off), OR
        2. We are in the Flask Reloader subprocess (Debug is on, but we are the child)
        """
        is_debug = os.environ.get("FLASK_DEBUG") == "1"
        is_reloader = os.environ.get("WERKZEUG_RUN_MAIN") == "true"

        # If not debugging, always run. If debugging, only run in the reloader sub-process.
        return (not is_debug) or is_reloader

    def _get_app_object(self):
        """Helper to get the real app object for threads"""
        return current_app._get_current_object()

    def get_hardware_manager(self):
        if self._hardware_manager is None:
            if self._should_run_services:
                try:
                    logger.info("Initializing HardwareManager...")
                    from app.services.hardware_manager import HardwareManager

                    self._hardware_manager = HardwareManager(app=self._get_app_object())
                except Exception as e:
                    logger.error(f"Failed to init HardwareManager: {e}")
            else:
                logger.debug("Skipping HardwareManager (Parent Process)")
        return self._hardware_manager

    def get_presence_monitor(self):
        if self._presence_monitor is None:
            if self._should_run_services:
                try:
                    logger.info("Initializing IntelligentPresenceMonitor...")
                    # Update import to the new consolidated service file
                    from app.services.presence_monitor import IntelligentPresenceMonitor

                    app = self._get_app_object()
                    self._presence_monitor = IntelligentPresenceMonitor(
                        app=app,
                        target_ip=app.config.get("SNMP_TARGET_IP", "192.168.1.1"),
                        community=app.config.get("SNMP_COMMUNITY", "public"),
                        scan_interval=app.config.get("PRESENCE_SCAN_INTERVAL", 60),
                    )
                    self._presence_monitor.start()
                except Exception as e:
                    logger.error(f"Failed to init PresenceMonitor: {e}")
            else:
                logger.debug("Skipping PresenceMonitor (Parent Process)")
        return self._presence_monitor

    def get_system_monitor(self):
        if self._system_monitor is None:
            if self._should_run_services:
                try:
                    logger.info("Initializing SystemMonitor...")
                    from app.services.system_monitor import SystemMonitor

                    self._system_monitor = SystemMonitor(app=self._get_app_object())
                except Exception as e:
                    logger.error(f"Failed to init SystemMonitor: {e}")
        return self._system_monitor

    def get_processor(self):
        if self._processor is None:
            if self._should_run_services:
                try:
                    from app.services.label_advanced import hardwaresequenceProcessor

                    self._processor = hardwaresequenceProcessor("hardware_activity.csv")
                    self._processor.load_persistent_state()
                except Exception as e:
                    logger.error(f"Failed to init Processor: {e}")
            return self._processor

    def cleanup(self):
        """Gracefully stop all services"""
        if self._should_run_services:
            logger.info("Stopping all background services...")
            if self._hardware_manager:
                self._hardware_manager.cleanup()
            if self._presence_monitor:
                self._presence_monitor.stop()
            if self._system_monitor:
                self._system_monitor.stop()


def get_services():
    return ServiceManager.get_instance()
