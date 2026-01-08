from datetime import datetime

from app.extensions import db

HARDWARE_INTERFACES = {
    "gpio_binary": "Binary Sensor (Motion/Door)",
    "gpio_relay": "Relay Switch (Light/Fan)",
    "dht_22": "DHT22 Temp/Humidity",
    "i2c_generic": "I2C Display/Sensor",
}
HARDWARE_PROFILES = [
    {
        "ui_value": "motion",  # The value in the <option> tag
        "label": "Motion Sensor",  # What the user sees
        "driver_type": "gpio_binary",  # What gets saved to DB driver_type
        "config_type": "motion",  # What gets saved to DB configuration['type']
    },
    {
        "ui_value": "door",
        "label": "Door Contact",
        "driver_type": "gpio_binary",
        "config_type": "door",
    },
    {
        "ui_value": "relay",
        "label": "Relay / Switch",
        "driver_type": "gpio_relay",
        "config_type": "relay",
    },
]


class Hardware(db.Model):
    """
    Represents any physical component attached to the Pi.
    Examples: Motion Sensor (Input), Relay (Output), DHT22 (Temp), I2C Display.
    """

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    enabled = db.Column(db.Boolean, default=True)

    # 'gpio_binary', 'gpio_relay', 'i2c_generic', 'dht_temp'
    driver_type = db.Column(db.String(50), nullable=False, default="gpio_binary")

    # Flexible configuration (pins, addresses, thresholds)
    configuration = db.Column(db.JSON, nullable=False, default={})

    events = db.relationship("Event", backref="hardware", lazy="dynamic")

    from sqlalchemy.orm import validates

    @validates("driver_type")
    def validate_driver(self, key, driver_type):
        if driver_type not in HARDWARE_INTERFACES:
            raise ValueError(
                f"Invalid driver type. Must be one of: {list(HARDWARE_INTERFACES.keys())}"
            )
        return driver_type

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "driver_type": self.driver_type,
            # Helper to send the 'Pretty Name' to the UI
            "driver_label": HARDWARE_INTERFACES.get(self.driver_type, "Unknown"),
            "configuration": self.configuration,
            "enabled": self.enabled,
        }


class Event(db.Model):
    """Generic Event Log for any Hardware"""

    id = db.Column(db.Integer, primary_key=True)
    hardware_id = db.Column(db.Integer, db.ForeignKey("hardware.id"))

    value = db.Column(db.Float)  # 1.0, 0.0, 24.5, 1024.0
    formatted_value = db.Column(db.String(50))  # "Active", "24.5°C", "On"
    unit = db.Column(db.String(20))  # "boolean", "celsius", "lux"

    timestamp = db.Column(db.DateTime, default=datetime.now, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "hardware_name": self.hardware.name if self.hardware else "Unknown",
            "value": self.value,
            "formatted": self.formatted_value,
            "unit": self.unit,
            "timestamp": self.timestamp.isoformat(),
        }


class Device(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mac_address = db.Column(db.String(17), unique=True, nullable=False)

    # Identification
    name = db.Column(db.String(64), default="Unknown Device")
    owner = db.Column(db.String(64))
    hostname = db.Column(db.String(128))  # NEW: Scanned Hostname (e.g., 'Kaias-iPhone')
    vendor = db.Column(db.String(64))  # NEW: Manufacturer (e.g., 'Apple')

    # Settings
    track_presence = db.Column(db.Boolean, default=False)
    is_randomized_mac = db.Column(db.Boolean, default=False)  # NEW

    # State
    is_home = db.Column(db.Boolean, default=False)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    last_ip = db.Column(db.String(15))  # NEW: Helps correlation

    def to_dict(self):
        return {
            "id": self.id,
            "mac_address": self.mac_address,
            "name": self.name,
            "owner": self.owner,
            "hostname": self.hostname,
            "vendor": self.vendor,
            "is_home": self.is_home,
            "track_presence": self.track_presence,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
        }


class PresenceEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey("device.id"), nullable=False)
    event_type = db.Column(db.String(20))  # 'arrived', 'left'
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "event": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "device_id": self.device_id,
        }
