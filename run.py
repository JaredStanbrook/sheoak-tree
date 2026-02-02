import os

from dotenv import load_dotenv

from app import create_app
from app.extensions import socketio
from config import get_config

load_dotenv()

app = create_app(get_config())


def main():
    # 1. Determine execution mode
    debug_mode = os.environ.get("FLASK_ENV") == "development"

    # Reloader Check
    should_start_services = True
    if debug_mode and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        should_start_services = False
        print(">>> Main process detected. Waiting for reloader worker to start services...")

    if should_start_services:
        app.start_services()

    # Run Server (dev only; production uses gunicorn with wsgi.py)
    port = int(os.environ.get("PORT", 5000))
    host = "127.0.0.1" if debug_mode else "0.0.0.0"

    print(f"Starting Server on {host}:{port} (Debug: {debug_mode})")

    socketio.run(
        app,
        host=host,
        port=port,
        debug=debug_mode,
        use_reloader=debug_mode,
        allow_unsafe_werkzeug=debug_mode,
    )


if __name__ == "__main__":
    main()
