# Database Models

This document maps SQLAlchemy models in `app/models.py` to their tables, columns, and relationships.

## Hardware (table: `hardware`)
**Columns**
- `id` (Integer, PK)
- `name` (String(64), required)
- `enabled` (Boolean, default true)
- `driver_interface` (String(50), required, default `gpio_binary`)
- `type` (String(50), nullable)
- `configuration` (JSON, required, default `{}`)

**Relationships**
- One-to-many: `Hardware.events` -> `Event` (backref `hardware`, lazy `dynamic`)

## Event (table: `event`)
**Columns**
- `id` (Integer, PK)
- `hardware_id` (Integer, FK -> `hardware.id`)
- `value` (Float)
- `unit` (String(20))
- `timestamp` (DateTime, default `datetime.now`, indexed)

**Relationships**
- Many-to-one: `Event.hardware` (backref from `Hardware.events`)

## Device (table: `device`)
**Columns**
- `id` (Integer, PK)
- `mac_address` (String(17), unique, indexed, required)
- `name` (String(100), required)
- `owner` (String(100))
- `last_ip` (String(15))
- `hostname` (String(100))
- `vendor` (String(100))
- `is_home` (Boolean, default false, indexed)
- `is_randomized_mac` (Boolean, default false, indexed)
- `track_presence` (Boolean, default false, indexed)
- `last_seen` (DateTime, default `datetime.now`, indexed)
- `first_seen` (DateTime, default `datetime.now`)
- `created_at` (DateTime, default `datetime.now`)
- `linked_to_device_id` (Integer, FK -> `device.id`, nullable)
- `link_confidence` (Float)
- `ip_history` (JSON, default list)
- `mdns_services` (JSON, default list)
- `device_metadata` (JSON, default dict)
- `typical_connection_times` (JSON, default list)
- `co_occurring_devices` (JSON, default list)

**Relationships**
- Self-referential many-to-one: `Device.linked_to` -> parent `Device` (remote_side `id`)
- One-to-many backref: `Device.linked_devices` -> child devices linked to this device

## PresenceEvent (table: `presence_event`)
**Columns**
- `id` (Integer, PK)
- `device_id` (Integer, FK -> `device.id`, indexed, required)
- `event_type` (String(20), required)
- `timestamp` (DateTime, default `datetime.now`, indexed)
- `ip_address` (String(15))
- `hostname` (String(100))

**Relationships**
- Many-to-one: `PresenceEvent.device` -> `Device`
- One-to-many backref: `Device.events` -> `PresenceEvent` (lazy `dynamic`)

## DeviceAssociation (table: `device_association`)
**Columns**
- `id` (Integer, PK)
- `device1_id` (Integer, FK -> `device.id`, required)
- `device2_id` (Integer, FK -> `device.id`, required)
- `association_type` (String(50))
- `confidence` (Float)
- `created_at` (DateTime, default `datetime.now`)
- `last_seen_together` (DateTime, default `datetime.now`)
- `co_occurrence_count` (Integer, default 1)

**Relationships**
- Many-to-one: `DeviceAssociation.device1` -> `Device` (foreign key `device1_id`)
- Many-to-one: `DeviceAssociation.device2` -> `Device` (foreign key `device2_id`)

**Constraints**
- Unique constraint on (`device1_id`, `device2_id`)

## NetworkSnapshot (table: `network_snapshot`)
**Columns**
- `id` (Integer, PK)
- `timestamp` (DateTime, default `datetime.now`, indexed)
- `devices_present` (JSON, default list)
- `device_count` (Integer)

**Relationships**
- None declared
