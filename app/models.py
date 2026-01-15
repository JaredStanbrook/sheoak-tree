from datetime import datetime

from app.extensions import db

HARDWARE_INTERFACES = {
    "gpio_binary": "Binary Sensor",
    "gpio_relay": "Relay Switch",
    "dht_22": "DHT22",
    "i2c_generic": "I2C",
}
HARDWARE_TYPES = [
    "camera",
    "motion_sensor",
    "doorbell",
    "thermostat",
    "relay",
    "display",
    "contact_sensor",
    "system_status",
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
    driver_interface = db.Column(db.String(50), nullable=False, default="gpio_binary")
    type = db.Column(db.String(50), nullable=True)
    # Flexible configuration (pins, addresses, thresholds)
    configuration = db.Column(db.JSON, nullable=False, default={})

    events = db.relationship("Event", backref="hardware", lazy="dynamic")

    from sqlalchemy.orm import validates

    @validates("driver_interface")
    def validate_driver(self, key, driver_interface):
        if driver_interface not in HARDWARE_INTERFACES:
            raise ValueError(
                f"Invalid driver type. Must be one of: {list(HARDWARE_INTERFACES.keys())}"
            )
        return driver_interface

    @validates("type")
    def validate_type(self, key, type):
        if type not in HARDWARE_TYPES:
            raise ValueError(f"Invalid hardware type. Must be one of: {HARDWARE_TYPES}")
        return type

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "driver_interface": self.driver_interface,
            "type": self.type,
            "configuration": self.configuration,
            "enabled": self.enabled,
        }


class Event(db.Model):
    """Generic Event Log for any Hardware"""

    id = db.Column(db.Integer, primary_key=True)
    hardware_id = db.Column(db.Integer, db.ForeignKey("hardware.id"))

    value = db.Column(db.Float)  # 1.0, 0.0, 24.5, 1024.0
    unit = db.Column(db.String(20))  # "boolean", "celsius", "lux"

    timestamp = db.Column(db.DateTime, default=datetime.now, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "hardware_name": self.hardware.name if self.hardware else "Unknown",
            "value": self.value,
            "unit": self.unit,
            "timestamp": self.timestamp.isoformat(),
        }


class Device(db.Model):
    """Device model with fingerprinting support"""

    __tablename__ = "device"

    id = db.Column(db.Integer, primary_key=True)
    mac_address = db.Column(db.String(17), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    owner = db.Column(db.String(100))

    # Network information
    last_ip = db.Column(db.String(15))
    hostname = db.Column(db.String(100))
    vendor = db.Column(db.String(100))

    # Status
    is_home = db.Column(db.Boolean, default=False, index=True)
    is_randomized_mac = db.Column(db.Boolean, default=False, index=True)
    track_presence = db.Column(db.Boolean, default=False, index=True)

    # Timestamps
    last_seen = db.Column(db.DateTime, default=datetime.now, index=True)
    first_seen = db.Column(db.DateTime, default=datetime.now)
    created_at = db.Column(db.DateTime, default=datetime.now)

    # Device linking (for randomized MACs)
    linked_to_device_id = db.Column(db.Integer, db.ForeignKey("device.id"), nullable=True)
    link_confidence = db.Column(db.Float)  # 0.0 to 1.0
    linked_to = db.relationship("Device", remote_side=[id], backref="linked_devices")

    # Device fingerprinting data (stored as JSON)
    ip_history = db.Column(db.JSON, default=list)  # [{ip, timestamp}]
    mdns_services = db.Column(db.JSON, default=list)  # List of mDNS service types
    device_metadata = db.Column(db.JSON, default=dict)  # OS, model, open ports, etc.

    # Behavioral patterns
    typical_connection_times = db.Column(db.JSON, default=list)  # [hour_of_day]
    co_occurring_devices = db.Column(db.JSON, default=list)  # [device_ids]

    def to_dict(self):
        return {
            "id": self.id,
            "mac_address": self.mac_address,
            "name": self.name,
            "owner": self.owner,
            "is_home": self.is_home,
            "is_randomized_mac": self.is_randomized_mac,
            "track_presence": self.track_presence,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "last_ip": self.last_ip,
            "hostname": self.hostname,
            "vendor": self.vendor,
            "linked_to_device_id": self.linked_to_device_id,
            "link_confidence": self.link_confidence,
            "device_metadata": self.device_metadata,
        }


class PresenceEvent(db.Model):
    """Presence event log"""

    __tablename__ = "presence_event"

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey("device.id"), nullable=False, index=True)
    event_type = db.Column(db.String(20), nullable=False)  # 'arrived' or 'left'
    timestamp = db.Column(db.DateTime, default=datetime.now, index=True)

    # Additional context
    ip_address = db.Column(db.String(15))
    hostname = db.Column(db.String(100))

    device = db.relationship("Device", backref=db.backref("events", lazy="dynamic"))

    def to_dict(self):
        return {
            "id": self.id,
            "device_id": self.device_id,
            "device_name": self.device.name if self.device else None,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "ip_address": self.ip_address,
            "hostname": self.hostname,
        }


class DeviceAssociation(db.Model):
    """
    Track associations between devices (e.g., iPhone and Mac belonging to same person)
    This helps with correlation
    """

    __tablename__ = "device_association"

    id = db.Column(db.Integer, primary_key=True)
    device1_id = db.Column(db.Integer, db.ForeignKey("device.id"), nullable=False)
    device2_id = db.Column(db.Integer, db.ForeignKey("device.id"), nullable=False)

    association_type = db.Column(db.String(50))  # 'same_owner', 'co_occurrence', 'network_pair'
    confidence = db.Column(db.Float)  # 0.0 to 1.0

    created_at = db.Column(db.DateTime, default=datetime.now)
    last_seen_together = db.Column(db.DateTime, default=datetime.now)
    co_occurrence_count = db.Column(db.Integer, default=1)

    device1 = db.relationship("Device", foreign_keys=[device1_id])
    device2 = db.relationship("Device", foreign_keys=[device2_id])

    __table_args__ = (db.UniqueConstraint("device1_id", "device2_id", name="unique_device_pair"),)


class NetworkSnapshot(db.Model):
    """
    Periodic snapshots of entire network state.
    Useful for analyzing patterns over time.
    """

    __tablename__ = "network_snapshot"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.now, index=True)

    # JSON snapshot of all devices present
    devices_present = db.Column(db.JSON, default=list)  # [{'mac': ..., 'ip': ..., ...}]
    device_count = db.Column(db.Integer)

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "device_count": self.device_count,
            "devices_present": self.devices_present,
        }
