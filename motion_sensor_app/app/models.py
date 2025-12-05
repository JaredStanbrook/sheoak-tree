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
