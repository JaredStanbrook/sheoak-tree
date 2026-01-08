import logging
import os

from flask import current_app

logger = logging.getLogger(__name__)


class ServiceManager:
    _instance = None
    _hardware_manager = None
    _processor = None
    _presence_monitor = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = ServiceManager()
        return cls._instance

    def get_hardware_manager(self):
        """Lazy load the Universal Hardware Manager"""
        if self._hardware_manager is None:
            is_reloader = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
            is_debug = os.environ.get("FLASK_DEBUG") == "1"
            is_production = os.environ.get("FLASK_ENV") == "production"

            # Load if we are in reloader, OR if we are NOT in debug mode (Gunicorn)
            should_load = is_reloader or (not is_debug) or is_production

            if should_load:
                try:
                    logger.info("Initializing HardwareManager...")
                    from app.services.hardware_manager import HardwareManager

                    real_app = current_app._get_current_object()

                    # HardwareManager loads config/strategies from DB, so no args needed here
                    self._hardware_manager = HardwareManager(app=real_app)
                    logger.info("HardwareManager initialized successfully")
                except Exception as e:
                    logger.error(f"Failed to initialize HardwareManager: {e}")
            else:
                logger.info("Skipping HardwareManager initialization (Main process in Debug mode)")

        return self._hardware_manager

    def get_processor(self):
        """Lazy load the Sequence Processor"""
        if self._processor is None:
            from app.services.label_advanced import hardwaresequenceProcessor

            # Note: Ensure hardware_activity.csv is still being populated or update this
            # to read from the new DB Events table in the future.
            self._processor = hardwaresequenceProcessor("hardware_activity.csv")
            try:
                self._processor.load_persistent_state()
            except Exception:
                pass
        return self._processor

    def get_presence_monitor(self):
        """Lazy load the Presence Monitor using Multiprocessing"""
        if self._presence_monitor is None:
            is_reloader = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
            is_debug = os.environ.get("FLASK_DEBUG") == "1"

            should_load = not is_debug or is_reloader

            if should_load:
                try:
                    logger.info("Initializing PresenceMonitor (Lazy Load)...")
                    from app.services.presence_monitor import PresenceMonitor

                    real_app = current_app._get_current_object()

                    # Get config from app
                    target_ip = real_app.config.get("SNMP_TARGET_IP", "192.168.1.1")
                    community = real_app.config.get("SNMP_COMMUNITY", "public")
                    interval = real_app.config.get("PRESENCE_SCAN_INTERVAL", 60)

                    self._presence_monitor = PresenceMonitor(
                        app=real_app,
                        target_ip=target_ip,
                        community=community,
                        scan_interval=interval,
                    )

                    # Start the isolated process
                    self._presence_monitor.start()

                except Exception as e:
                    logger.error(f"Failed to initialize PresenceMonitor: {e}")
            else:
                logger.info("Skipping PresenceMonitor initialization (Main process in Debug mode)")

        return self._presence_monitor

    def cleanup(self):
        """Cleanup all services"""
        if self._hardware_manager:
            logger.info("Cleaning up HardwareManager...")
            self._hardware_manager.cleanup()

        if self._presence_monitor:
            logger.info("Cleaning up PresenceMonitor...")
            self._presence_monitor.stop()


def get_services():
    return ServiceManager.get_instance()
