import sys
from unittest.mock import MagicMock

import pytest

# --- 1. Global Hardware Mocks (Must run before app import) ---
# This prevents ImportError on non-Raspberry Pi devices (CI/Dev laptops)
mock_gpio = MagicMock()
mock_gpio.BCM = "BCM"
mock_gpio.IN = "IN"
mock_gpio.OUT = "OUT"
mock_gpio.HIGH = 1
mock_gpio.LOW = 0
mock_gpio.PUD_UP = "PUD_UP"

sys.modules["RPi"] = MagicMock()
sys.modules["RPi.GPIO"] = mock_gpio

# --- 2. App & DB Fixtures ---
from app import create_app, db
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    # Disable background threads for tests
    PRESENCE_SCAN_INTERVAL = 0


@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    app = create_app(TestConfig)

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """A test runner for the app's CLI commands."""
    return app.test_cli_runner()
