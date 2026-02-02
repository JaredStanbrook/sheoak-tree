from flask_migrate import Migrate
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy

# Initialize Database
db = SQLAlchemy()
migrate = Migrate()
socketio = SocketIO()
