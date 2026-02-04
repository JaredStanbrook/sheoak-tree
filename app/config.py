import os


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


class Config:
    ENV = os.environ.get("FLASK_ENV", "production")
    DEBUG = _env_bool("FLASK_DEBUG", False)

    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-secret-key-change-in-production"

    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or "sqlite:///app.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    LOG_DIR = os.environ.get("LOG_DIR", "./logs")
    LOG_FORMAT = os.environ.get("LOG_FORMAT", "text")

    GPIO_MODE = os.environ.get("GPIO_MODE", "mock")

    TIMEZONE = os.environ.get("TIMEZONE", "Australia/Perth")
    LOCALE = os.environ.get("LOCALE", "en-AU")

    PRESENCE_SCAN_INTERVAL = _env_int("PRESENCE_SCAN_INTERVAL", 60)
    DISABLE_PRESENCE_MONITOR = _env_bool("DISABLE_PRESENCE_MONITOR", False)
    DISABLE_MDNS = _env_bool("DISABLE_MDNS", False)
    PRESENCE_SNAPSHOT_RETENTION_DAYS = _env_int("PRESENCE_SNAPSHOT_RETENTION_DAYS", 30)

    SNMP_TARGET_IP = os.environ.get("SNMP_TARGET_IP", "192.168.1.1")
    SNMP_COMMUNITY = os.environ.get("SNMP_COMMUNITY", "public")
    ENABLE_SNMP_PRESENCE = _env_bool("ENABLE_SNMP_PRESENCE", False)
    SNMP_POLL_INTERVAL = _env_int("SNMP_POLL_INTERVAL", 60)
    SNMP_AUTHORITATIVE = _env_bool("SNMP_AUTHORITATIVE", False)
    SNMP_IPNETTOMEDIA_PHYS_OID = os.environ.get(
        "SNMP_IPNETTOMEDIA_PHYS_OID", "1.3.6.1.2.1.4.22.1.2"
    )
    SNMP_IPNETTOMEDIA_NET_OID = os.environ.get("SNMP_IPNETTOMEDIA_NET_OID", "1.3.6.1.2.1.4.22.1.3")
    SNMP_CLIENT_HOSTNAME_OID = os.environ.get("SNMP_CLIENT_HOSTNAME_OID")
    SNMP_CLIENT_SIGNAL_OID = os.environ.get("SNMP_CLIENT_SIGNAL_OID")
    SNMP_CLIENT_BAND_OID = os.environ.get("SNMP_CLIENT_BAND_OID")

    MOTION_HARDWARE_DEBOUNCE_MS = _env_int("MOTION_HARDWARE_DEBOUNCE_MS", 300)
    HARDWARE_LOG_FILE = os.environ.get("HARDWARE_LOG_FILE", "hardware_activity.csv")

    DEMO_MODE = _env_bool("DEMO_MODE", False)
    DEMO_REPLAY_DELAY_MS = _env_int("DEMO_REPLAY_DELAY_MS", 800)
    DEMO_REPLAY_BATCH = _env_int("DEMO_REPLAY_BATCH", 20)

    # ML/AI workbench is intentionally gated while the storage migration is in progress.
    AI_WORKBENCH_ENABLED = _env_bool("AI_WORKBENCH_ENABLED", False)


class DevelopmentConfig(Config):
    DEBUG = True
    ENV = "development"


class ProductionConfig(Config):
    DEBUG = False
    ENV = "production"


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    DISABLE_PRESENCE_MONITOR = True


def get_config():
    env = os.environ.get("FLASK_ENV", "production")
    if env == "development":
        return DevelopmentConfig
    if env == "testing":
        return TestingConfig
    return ProductionConfig
