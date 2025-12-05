# app/services/manager.py
import os
import logging
from flask import current_app

logger = logging.getLogger(__name__)


class ServiceManager:
    _instance = None
    _motion_app = None
    _processor = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = ServiceManager()
        return cls._instance

    def get_motion_app(self):
        """Lazy load the Motion Sensor App"""
        if self._motion_app is None:
            is_reloader = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
            is_debug = os.environ.get("FLASK_DEBUG") == "1"
            is_production = os.environ.get("FLASK_ENV") == "production"

            # Load if we are in reloader, OR if we are NOT in debug mode (Gunicorn)
            should_load = is_reloader or (not is_debug) or is_production

            if should_load:
                try:
                    logger.info("Initializing MotionSensorApp...")
                    from app.services.sensor_monitor import MotionSensorApp

                    real_app = current_app._get_current_object()
                    self._motion_app = MotionSensorApp(app=real_app, debounce_ms=300)
                    logger.info("MotionSensorApp initialized successfully")
                except Exception as e:
                    logger.error(f"Failed to initialize MotionSensorApp: {e}")
            else:
                logger.info(
                    "Skipping MotionSensorApp initialization (Main process in Debug mode)"
                )

        return self._motion_app

    def get_processor(self):
        """Lazy load the Sequence Processor"""
        if self._processor is None:
            from app.services.label_advanced import SensorSequenceProcessor

            self._processor = SensorSequenceProcessor("sensor_activity.csv")
            try:
                self._processor.load_persistent_state()
            except Exception:
                pass
        return self._processor

    def cleanup(self):
        if self._motion_app:
            logger.info("Cleaning up MotionSensorApp...")
            self._motion_app.cleanup()


def get_services():
    return ServiceManager.get_instance()
