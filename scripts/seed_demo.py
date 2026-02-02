import argparse
import random
from datetime import datetime, timedelta

from dotenv import load_dotenv

from app import create_app
from app.extensions import db
from app.models import Device, Event, Hardware, PresenceEvent
from config import get_config


def seed_hardware():
    hardware_defs = [
        {
            "name": "Front Door",
            "driver_interface": "gpio_binary",
            "type": "contact_sensor",
            "configuration": {"pin": 17, "type": "door"},
        },
        {
            "name": "Kitchen Motion",
            "driver_interface": "gpio_binary",
            "type": "motion_sensor",
            "configuration": {"pin": 27, "type": "motion"},
        },
        {
            "name": "Hall Motion",
            "driver_interface": "gpio_binary",
            "type": "motion_sensor",
            "configuration": {"pin": 22, "type": "motion"},
        },
        {
            "name": "Living Room Temp",
            "driver_interface": "dht_22",
            "type": "temperature_sensor",
            "configuration": {"pin": 4, "type": "temperature"},
        },
        {
            "name": "Garden Relay",
            "driver_interface": "gpio_relay",
            "type": "relay",
            "configuration": {"pin": 6, "type": "relay"},
        },
    ]

    records = []
    for item in hardware_defs:
        record = Hardware.query.filter_by(name=item["name"]).first()
        if not record:
            record = Hardware(**item)
            db.session.add(record)
        records.append(record)
    return records


def seed_devices():
    device_defs = [
        {
            "name": "Alex iPhone",
            "mac_address": "AA:BB:CC:DD:EE:01",
            "owner": "Alex",
            "track_presence": True,
            "is_home": True,
        },
        {
            "name": "Sam Laptop",
            "mac_address": "AA:BB:CC:DD:EE:02",
            "owner": "Sam",
            "track_presence": True,
            "is_home": False,
        },
        {
            "name": "Living Room Speaker",
            "mac_address": "AA:BB:CC:DD:EE:03",
            "owner": "Sheoak",
            "track_presence": False,
            "is_home": True,
        },
    ]

    records = []
    for item in device_defs:
        record = Device.query.filter_by(mac_address=item["mac_address"]).first()
        if not record:
            record = Device(**item)
            db.session.add(record)
        records.append(record)
    return records


def seed_events(hardware):
    now = datetime.now()
    events = []
    for hours_ago in range(24, 0, -1):
        timestamp = now - timedelta(hours=hours_ago)
        for hw in hardware:
            if hw.type == "temperature_sensor":
                value = 18 + random.random() * 6
                unit = "celsius"
            elif hw.type == "relay":
                value = 1.0 if random.random() > 0.7 else 0.0
                unit = "boolean"
            else:
                value = 1.0 if random.random() > 0.8 else 0.0
                unit = "boolean"

            events.append(
                Event(
                    hardware_id=hw.id,
                    value=value,
                    unit=unit,
                    timestamp=timestamp + timedelta(minutes=random.randint(0, 59)),
                )
            )

    db.session.add_all(events)


def seed_presence(devices):
    now = datetime.now()
    events = []
    for device in devices:
        events.append(
            PresenceEvent(
                device_id=device.id,
                event_type="arrived" if device.is_home else "left",
                timestamp=now - timedelta(minutes=random.randint(5, 120)),
            )
        )
    db.session.add_all(events)


def reset_data():
    db.session.query(Event).delete()
    db.session.query(PresenceEvent).delete()
    db.session.query(Device).delete()
    db.session.query(Hardware).delete()


def main():
    parser = argparse.ArgumentParser(description="Seed demo data for Sheoak Tree")
    parser.add_argument("--reset", action="store_true", help="Clear existing demo data")
    args = parser.parse_args()

    load_dotenv()
    app = create_app(get_config())

    with app.app_context():
        if args.reset:
            reset_data()

        hardware = seed_hardware()
        devices = seed_devices()
        db.session.commit()

        seed_events(hardware)
        seed_presence(devices)
        db.session.commit()

    print("Demo data seeded.")


if __name__ == "__main__":
    main()
