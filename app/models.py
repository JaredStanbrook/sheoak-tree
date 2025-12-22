from datetime import datetime
from app.extensions import db


class Sensor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    pin = db.Column(db.Integer, unique=True, nullable=False)
    type = db.Column(db.String(20), default="motion")  # 'motion', 'door'
    enabled = db.Column(db.Boolean, default=True)

    # Backref allows us to get all events for a sensor: sensor.events
    events = db.relationship("Event", backref="sensor", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "pin": self.pin,
            "type": self.type,
            "enabled": self.enabled,
        }


class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sensor_id = db.Column(db.Integer, db.ForeignKey("sensor.id"))
    value = db.Column(db.Integer)  # 1 for Active, 0 for Inactive
    event_type = db.Column(db.String(50))  # "Motion Detected", "Door Open"
    timestamp = db.Column(db.DateTime, default=datetime.now, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "sensor_name": self.sensor.name if self.sensor else "Unknown",
            "type": self.event_type,
            "value": self.value,
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
