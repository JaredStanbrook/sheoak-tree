# app/config.py
import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-secret-key-change-in-production"

    # Database Configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL"
    ) or "sqlite:///" + os.path.join(basedir, "app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Motion sensor settings
    MOTION_SENSOR_DEBOUNCE_MS = int(os.environ.get("MOTION_SENSOR_DEBOUNCE_MS", 300))
    SENSOR_LOG_FILE = os.environ.get("SENSOR_LOG_FILE", "sensor_activity.csv")

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
