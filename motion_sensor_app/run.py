# run.py
#!/usr/bin/env python3
"""
Flask Application Entry Point
"""
import os
import atexit
from config import get_config
from app import create_app, socketio


def create_motion_app():
    """Factory function to create MotionSensorApp"""
    from app.services.sensor_monitor import MotionSensorApp

    return MotionSensorApp(debounce_ms=300)


def main():
    app = create_app(get_config())

    # Initialize motion sensor app only in main process
    if (
        os.environ.get("WERKZEUG_RUN_MAIN") == "true"
        or os.environ.get("FLASK_ENV") != "development"
    ):
        motion_app = create_motion_app()
        app.motion_app = motion_app

        # Register cleanup on exit
        def cleanup():
            if hasattr(app, "motion_app"):
                app.logger.info("Cleaning up MotionSensorApp...")
                app.motion_app.cleanup()

        atexit.register(cleanup)
    else:
        # In development reloader process, set placeholder
        app.motion_app = None

    # Get configuration
    config_name = os.environ.get("FLASK_ENV", "production")

    if config_name == "development":
        socketio.run(
            app,
            host="127.0.0.1",
            port=int(os.environ.get("PORT", 5000)),
            debug=True,
        )
    else:
        socketio.run(
            app,
            host="0.0.0.0",
            port=int(os.environ.get("PORT", 5000)),
            debug=False,
            allow_unsafe_werkzeug=True,
        )


if __name__ == "__main__":
    main()
