from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Initialize SocketIO
socketio = SocketIO(cors_allowed_origins="*", async_mode='gevent')

# Initialize Database
db = SQLAlchemy()
migrate = Migrate()
