import os

from dotenv import load_dotenv

from app import create_app
from app.extensions import socketio
from config import get_config

load_dotenv()

app = create_app(get_config())
socketio_app = socketio

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
