def test_config(app):
    """Test that testing config is loaded correctly."""
    assert app.config["TESTING"] is True
    assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:"
    assert app.config["SOCKETIO_ENABLED"] is False


def test_version_constant():
    from app import __version__

    assert __version__ == "1.0.0"


def test_hardware_model(app):
    """Test Hardware model creation and retrieval."""
    from app.extensions import db
    from app.models import Hardware

    hardware = Hardware(
        name="Test Kitchen",
        driver_interface="gpio_binary",
        type="motion_sensor",
        configuration={},
    )
    db.session.add(hardware)
    db.session.commit()

    retrieved = Hardware.query.first()
    assert retrieved is not None
    assert retrieved.name == "Test Kitchen"
    assert retrieved.driver_interface == "gpio_binary"
