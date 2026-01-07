from flask_migrate import Migrate
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy

# Initialize SocketIO
socketio = SocketIO(cors_allowed_origins="*", async_mode="gevent")

# Initialize Database
db = SQLAlchemy()
migrate = Migrate()
