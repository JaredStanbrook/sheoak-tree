from datetime import datetime
from app.extensions import db

class Sensor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    pin = db.Column(db.Integer, unique=True, nullable=False)
    type = db.Column(db.String(20), default='motion') # 'motion', 'door'
    enabled = db.Column(db.Boolean, default=True)

    # Backref allows us to get all events for a sensor: sensor.events
    events = db.relationship('Event', backref='sensor', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'pin': self.pin,
            'type': self.type,
            'enabled': self.enabled
        }

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sensor_id = db.Column(db.Integer, db.ForeignKey('sensor.id'))
    value = db.Column(db.Integer) # 1 for Active, 0 for Inactive
    event_type = db.Column(db.String(50)) # "Motion Detected", "Door Open"
    timestamp = db.Column(db.DateTime, default=datetime.now, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'sensor_name': self.sensor.name if self.sensor else "Unknown",
            'type': self.event_type,
            'value': self.value,
            'timestamp': self.timestamp.isoformat()
        }

class Device(db.Model):
    """Represents a device (phone, laptop) that can be tracked via network presence"""
    id = db.Column(db.Integer, primary_key=True)
    mac_address = db.Column(db.String(17), unique=True, nullable=False)  # Format: AA:BB:CC:DD:EE:FF
    name = db.Column(db.String(64), nullable=False)  # e.g., "Jared's iPhone"
    owner = db.Column(db.String(64))  # e.g., "Jared"
    is_home = db.Column(db.Boolean, default=False)
    last_seen = db.Column(db.DateTime)

    # Backref allows us to get all presence events for a device: device.presence_events
    presence_events = db.relationship('PresenceEvent', backref='device', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'mac_address': self.mac_address,
            'name': self.name,
            'owner': self.owner,
            'is_home': self.is_home,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None
        }


class PresenceEvent(db.Model):
    """Logs presence changes (arrivals/departures)"""
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey('device.id'), nullable=False)
    event_type = db.Column(db.String(20), nullable=False)  # "arrived" or "left"
    timestamp = db.Column(db.DateTime, default=datetime.now, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'device_name': self.device.name if self.device else "Unknown",
            'device_owner': self.device.owner if self.device else None,
            'event_type': self.event_type,
            'timestamp': self.timestamp.isoformat()
        }
