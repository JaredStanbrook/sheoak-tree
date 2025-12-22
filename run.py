import os
import atexit
from config import get_config
from app import create_app
from app.extensions import socketio
from app.services.manager import get_services

app = create_app(get_config())

def main():
    # Register cleanup for the singleton service manager
    atexit.register(lambda: get_services().cleanup())

    # Environment Setup
    debug_mode = os.environ.get("FLASK_ENV") == "development"
    port = int(os.environ.get("PORT", 5000))
    host = "127.0.0.1" if debug_mode else "0.0.0.0"

    print(f"Starting Server on {host}:{port} (Debug: {debug_mode})")

    # Run SocketIO (Wraps Flask)
    socketio.run(
        app,
        host=host,
        port=port,
        debug=debug_mode,
        use_reloader=debug_mode,
        allow_unsafe_werkzeug=not debug_mode,  # Only needed if not using Gunicorn
    )

if __name__ == "__main__":
    main()
