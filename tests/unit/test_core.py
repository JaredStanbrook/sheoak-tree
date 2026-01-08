def test_config(app):
    """Test that testing config is loaded correctly."""
    assert app.config["TESTING"] is True
    assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:"


def test_hardware_model(app):
    """Test Sensor model creation and retrieval."""
    from app.extensions import db
    from app.models import Sensor

    s = Sensor(name="Test Kitchen", pin=99, type="motion")
    db.session.add(s)
    db.session.commit()

    retrieved = Sensor.query.first()
    assert retrieved is not None
    assert retrieved.name == "Test Kitchen"
    assert retrieved.pin == 99
