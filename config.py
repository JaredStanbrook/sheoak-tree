# app/config.py
import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-secret-key-change-in-production"

    # Database Configuration
    # For SQLite, Flask automatically uses instance folder for relative paths
    # So DATABASE_URL=sqlite:///app.db will resolve to instance/app.db
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get("DATABASE_URL") or "sqlite:///app.db"
    )  # This will automatically use instance/app.db

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Motion hardware settings
    MOTION_HARDWARE_DEBOUNCE_MS = int(os.environ.get("MOTION_HARDWARE_DEBOUNCE_MS", 300))
    HARDWARE_LOG_FILE = os.environ.get("HARDWARE_LOG_FILE", "hardware_activity.csv")

    # SocketIO settings
    SOCKETIO_PATH = "/sheoak/socket.io"

    # --- SNMP Presence Monitoring Settings ---
    SNMP_TARGET_IP = os.environ.get("SNMP_TARGET_IP", "192.168.1.1")
    SNMP_COMMUNITY = os.environ.get("SNMP_COMMUNITY", "public")
    PRESENCE_SCAN_INTERVAL = int(os.environ.get("PRESENCE_SCAN_INTERVAL", 60))


class DevelopmentConfig(Config):
    DEBUG = True
    ENV = "development"


class ProductionConfig(Config):
    DEBUG = False
    ENV = "production"


def get_config():
    env = os.environ.get("FLASK_ENV", "production")
    if env == "development":
        return DevelopmentConfig
    return ProductionConfig
