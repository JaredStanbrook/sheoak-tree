from datetime import datetime, timedelta

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import desc

from app.extensions import db
from app.models import Device, DeviceAssociation, NetworkSnapshot, PresenceEvent

# Create blueprint (add this to your app/__init__.py if you don't have one)
devices_bp = Blueprint("devices", __name__, url_prefix="/api/devices")


@devices_bp.route("/", methods=["GET"])
def get_all_devices():
    """
    Get all registered devices and their presence status

    Returns:
        JSON with list of devices including:
        - Basic info (id, mac, name, vendor)
        - Presence status (is_home, last_seen)
        - Network details (IP, hostname)
        - Tracking info
        - Associated devices
    """
    try:
        devices = Device.query.all()

        result = []
        for device in devices:
            # Get linked device info if exists
            linked_device = None
            if device.linked_to_device_id:
                linked = Device.query.get(device.linked_to_device_id)
                if linked:
                    linked_device = {
                        "id": linked.id,
                        "name": linked.name,
                        "mac_address": linked.mac_address,
                    }

            # Get associated devices (co-occurrence)
            associations = DeviceAssociation.query.filter(
                (DeviceAssociation.device1_id == device.id)
                | (DeviceAssociation.device2_id == device.id)
            ).all()

            associated_devices = []
            for assoc in associations:
                other_id = assoc.device2_id if assoc.device1_id == device.id else assoc.device1_id
                other = Device.query.get(other_id)
                if other:
                    associated_devices.append(
                        {
                            "id": other.id,
                            "name": other.name,
                            "mac_address": other.mac_address,
                            "co_occurrence_count": assoc.co_occurrence_count,
                            "last_seen_together": assoc.last_seen_together.isoformat()
                            if assoc.last_seen_together
                            else None,
                        }
                    )

            # Get latest presence event
            latest_event = (
                PresenceEvent.query.filter_by(device_id=device.id)
                .order_by(PresenceEvent.timestamp.desc())
                .first()
            )

            device_data = {
                "id": device.id,
                "mac_address": device.mac_address,
                "name": device.name,
                "hostname": device.hostname,
                "vendor": device.vendor,
                # Presence info
                "is_home": device.is_home,
                "last_seen": device.last_seen.isoformat() if device.last_seen else None,
                "first_seen": device.first_seen.isoformat() if device.first_seen else None,
                # Network info
                "last_ip": device.last_ip,
                "ip_history": device.ip_history or [],
                # Device characteristics
                "is_randomized_mac": device.is_randomized_mac,
                "track_presence": device.track_presence,
                "mdns_services": device.mdns_services or [],
                "device_metadata": device.device_metadata or {},
                "typical_connection_times": device.typical_connection_times or [],
                # Relationships
                "linked_to_device": linked_device,
                "link_confidence": device.link_confidence,
                "associated_devices": associated_devices,
                # Latest event
                "latest_event": {
                    "type": latest_event.event_type,
                    "timestamp": latest_event.timestamp.isoformat(),
                    "ip_address": latest_event.ip_address,
                }
                if latest_event
                else None,
            }

            result.append(device_data)

        return jsonify({"success": True, "count": len(result), "devices": result}), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@devices_bp.route("/", methods=["POST"])
def register_device():
    """
    Register a new device for presence monitoring

    Body (JSON):
        {
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "name": "My iPhone",
            "track_presence": true,
            "hostname": "optional",
            "is_randomized_mac": false
        }
    """
    try:
        data = request.get_json()

        if not data or "mac_address" not in data:
            return jsonify({"success": False, "error": "mac_address is required"}), 400

        mac = data["mac_address"].upper()

        # Check if device already exists
        existing = Device.query.filter_by(mac_address=mac).first()
        if existing:
            return jsonify(
                {
                    "success": False,
                    "error": "Device with this MAC address already exists",
                    "device_id": existing.id,
                }
            ), 409

        # Create new device
        device = Device(
            mac_address=mac,
            name=data.get("name", f"Device {mac[-5:]}"),
            hostname=data.get("hostname"),
            track_presence=data.get("track_presence", False),
            is_randomized_mac=data.get("is_randomized_mac", False),
            first_seen=datetime.now(),
            last_seen=datetime.now(),
            is_home=False,
        )

        # Try to get vendor for stable MACs
        if not device.is_randomized_mac:
            try:
                from netaddr import EUI

                device.vendor = EUI(mac).oui.registration().org
            except:
                pass

        db.session.add(device)
        db.session.commit()

        return jsonify(
            {
                "success": True,
                "message": "Device registered successfully",
                "device": {
                    "id": device.id,
                    "mac_address": device.mac_address,
                    "name": device.name,
                    "track_presence": device.track_presence,
                },
            }
        ), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


@devices_bp.route("/<int:device_id>", methods=["PUT", "PATCH"])
def update_device(device_id):
    """
    Update device information

    Body (JSON):
        {
            "name": "Updated Name",
            "track_presence": true,
            "hostname": "new-hostname"
        }
    """
    try:
        device = Device.query.get(device_id)
        if not device:
            return jsonify({"success": False, "error": "Device not found"}), 404

        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        # Update allowed fields
        if "name" in data:
            device.name = data["name"]
        if "track_presence" in data:
            device.track_presence = data["track_presence"]
        if "hostname" in data:
            device.hostname = data["hostname"]
        if "is_randomized_mac" in data:
            device.is_randomized_mac = data["is_randomized_mac"]

        db.session.commit()

        return jsonify(
            {
                "success": True,
                "message": "Device updated successfully",
                "device": {
                    "id": device.id,
                    "mac_address": device.mac_address,
                    "name": device.name,
                    "track_presence": device.track_presence,
                    "hostname": device.hostname,
                },
            }
        ), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


@devices_bp.route("/<int:device_id>", methods=["DELETE"])
def remove_device(device_id):
    """
    Remove a device from monitoring

    Query params:
        ?delete_events=true - Also delete all presence events (default: false)
    """
    try:
        device = Device.query.get(device_id)
        if not device:
            return jsonify({"success": False, "error": "Device not found"}), 404

        delete_events = request.args.get("delete_events", "false").lower() == "true"

        # Delete associations
        DeviceAssociation.query.filter(
            (DeviceAssociation.device1_id == device_id)
            | (DeviceAssociation.device2_id == device_id)
        ).delete()

        # Delete presence events if requested
        if delete_events:
            PresenceEvent.query.filter_by(device_id=device_id).delete()

        # Unlink any devices linked to this one
        Device.query.filter_by(linked_to_device_id=device_id).update(
            {"linked_to_device_id": None, "link_confidence": None}
        )

        mac = device.mac_address
        name = device.name

        db.session.delete(device)
        db.session.commit()

        return jsonify(
            {"success": True, "message": f"Device {name} ({mac}) removed successfully"}
        ), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


@devices_bp.route("/status", methods=["GET"])
def get_monitoring_status():
    """
    Get presence monitoring system status.

    ARCHITECTURAL NOTE:
    This endpoint is a DATA CONSUMER. It does not touch the background service.
    It infers system health by checking the recency of data in the DB.
    """
    try:
        # 1. Config Context (Static)
        scan_interval = current_app.config.get("PRESENCE_SCAN_INTERVAL", 60)

        # 2. Liveness Check (Data-Driven)
        # We define "healthy" as having a snapshot within (Interval * 3) seconds
        latest_snapshot = NetworkSnapshot.query.order_by(desc(NetworkSnapshot.timestamp)).first()

        monitor_running = False
        last_scan_time = None

        if latest_snapshot:
            last_scan_time = latest_snapshot.timestamp
            # Allow for some delay/jitter (e.g. 3 missed scans = offline)
            threshold = datetime.now() - timedelta(seconds=scan_interval * 3)
            monitor_running = last_scan_time > threshold

        # 3. Statistics (Read-Only)
        stats = {
            "total_devices": Device.query.count(),
            "tracked_devices": Device.query.filter_by(track_presence=True).count(),
            "currently_home": Device.query.filter_by(is_home=True).count(),
            "randomized_macs": Device.query.filter_by(is_randomized_mac=True).count(),
            "linked_devices": Device.query.filter(Device.linked_to_device_id.isnot(None)).count(),
        }

        # 4. Recent Activity
        recent_events = PresenceEvent.query.order_by(desc(PresenceEvent.timestamp)).limit(10).all()

        events_list = [
            {
                "device_name": e.device.name if e.device else "Unknown",
                "event_type": e.event_type,
                "timestamp": e.timestamp.isoformat(),
                "ip_address": e.ip_address,
            }
            for e in recent_events
        ]

        return jsonify(
            {
                "success": True,
                "system": {
                    "monitor_running": monitor_running,
                    "scan_interval": scan_interval,
                    "last_scan": last_scan_time.isoformat() if last_scan_time else None,
                    "status": "online" if monitor_running else "stalled",
                },
                "statistics": stats,
                "latest_snapshot": {
                    "timestamp": latest_snapshot.timestamp.isoformat(),
                    "device_count": latest_snapshot.device_count,
                    "devices": latest_snapshot.devices_present,
                }
                if latest_snapshot
                else None,
                "recent_events": events_list,
            }
        ), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@devices_bp.route("/home", methods=["GET"])
def who_is_home():
    """
    Quick endpoint to see who is currently home

    Returns simplified list of present devices with owner information
    """
    try:
        devices = Device.query.filter_by(is_home=True).all()

        result = []
        people_home = []
        seen_people = set()

        for device in devices:
            # Calculate how long they've been home
            time_home = None
            if device.last_seen:
                delta = datetime.now() - device.last_seen
                if delta.total_seconds() < 60:
                    time_home = f"{int(delta.total_seconds())} seconds"
                elif delta.total_seconds() < 3600:
                    time_home = f"{int(delta.total_seconds() / 60)} minutes"
                elif delta.total_seconds() < 86400:
                    time_home = f"{int(delta.total_seconds() / 3600)} hours"
                else:
                    time_home = f"{int(delta.total_seconds() / 86400)} days"

            result.append(
                {
                    "id": device.id,
                    "name": device.name,
                    "owner": device.owner,
                    "mac_address": device.mac_address,
                    "last_ip": device.last_ip,
                    "last_seen": device.last_seen.isoformat() if device.last_seen else None,
                    "time_home": time_home,
                    "is_tracked": device.track_presence,
                    "is_random_mac": device.is_randomized_mac,
                }
            )

            # Track unique people (owners) who are home
            if device.owner and device.owner not in seen_people:
                people_home.append(device.owner)
                seen_people.add(device.owner)

        return jsonify(
            {
                "success": True,
                "count": len(result),
                "timestamp": datetime.now().isoformat(),
                "devices_home": result,
                "people_home": people_home,  # List of unique owners/people
            }
        ), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@devices_bp.route("/present", methods=["GET"])
def get_present_devices():
    """Get only devices currently present (is_home=True) - alias for /home"""
    return who_is_home()


@devices_bp.route("/tracked", methods=["GET"])
def get_tracked_devices():
    """Get only devices being tracked for presence (track_presence=True)"""
    try:
        devices = Device.query.filter_by(track_presence=True).all()

        result = []
        for device in devices:
            result.append(
                {
                    "id": device.id,
                    "mac_address": device.mac_address,
                    "name": device.name,
                    "is_home": device.is_home,
                    "last_seen": device.last_seen.isoformat() if device.last_seen else None,
                    "is_randomized_mac": device.is_randomized_mac,
                }
            )

        return jsonify({"success": True, "count": len(result), "devices": result}), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# Register the blueprint in your app/__init__.py or wherever you create the app:
# from app.routes.devices import devices_bp
# app.register_blueprint(devices_bp)
