"""Module providing api."""

from datetime import datetime

from flask import Blueprint, current_app, jsonify, request

from app.services.manager import get_services

bp = Blueprint("api", __name__)
logger = current_app.logger if current_app else None


@bp.route("/sensors")
def api_sensors():
    """api sensor endpoint."""
    motion_app = get_services().get_motion_app()
    if not motion_app:
        return jsonify({"success": False, "error": "Sensor service unavailable"}), 503

    return jsonify(
        {
            "success": True,
            "sensors": motion_app.get_sensor_data(),
            "timestamp": datetime.now().isoformat(),
        }
    )


@bp.route("/activity/<int:hours>")
def api_activity(hours):
    motion_app = get_services().get_motion_app()
    if not motion_app:
        return jsonify({"success": False, "error": "Sensor service unavailable"}), 503

    return jsonify(
        {
            "success": True,
            "activity": motion_app.get_activity_data(hours),
            "timestamp": datetime.now().isoformat(),
            "hours": hours,
        }
    )


@bp.route("/frequency/<int:hours>/<int:interval>")
def api_frequency(hours, interval):
    motion_app = get_services().get_motion_app()
    if not motion_app:
        return jsonify({"success": False, "error": "Service unavailable"}), 503

    data = motion_app.get_frequency_data(hours, interval)

    return jsonify(
        {
            "success": True,
            "frequency": data,
            "timestamp": datetime.now().isoformat(),
            "hours": hours,
            "interval_minutes": interval,
        }
    )


@bp.route("/sensors/<int:sensor_id>/toggle", methods=["POST"])
def toggle_sensor(sensor_id):
    motion_app = get_services().get_motion_app()
    if not motion_app:
        return jsonify({"success": False, "error": "Service unavailable"}), 503

    success, result = motion_app.toggle_sensor(sensor_id)

    if success:
        return jsonify(
            {
                "success": True,
                "new_state": result,  # True = On, False = Off
                "message": "Relay toggled",
            }
        )
    else:
        return jsonify({"success": False, "error": result}), 400


# --- Sequence Processing Routes ---


@bp.route("/sequences/process", methods=["POST"])
def process_sequences():
    try:
        processor = get_services().get_processor()
        data = request.json or {}

        result = processor.process_sequences(
            window_size=data.get("window_size", 60),
            sequence_gap_threshold=data.get("sequence_gap_threshold", 300),
            incremental=data.get("incremental", False),
        )
        processor.save_persistent_state()

        return jsonify(
            {
                "success": True,
                "result": result,
                "message": "Processing completed",
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        current_app.logger.error(f"Sequence processing error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/sequences/list")
def get_sequences_list():
    try:
        processor = get_services().get_processor()
        # State loading is handled in ServiceManager automatically
        result = processor.get_sequence_list(
            page=request.args.get("page", 1, type=int),
            per_page=request.args.get("per_page", 20, type=int),
        )
        return jsonify({"success": True, **result, "timestamp": datetime.now().isoformat()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/sequences/<int:sequence_id>")
def get_sequence_detail(sequence_id):
    try:
        processor = get_services().get_processor()
        sequence = processor.get_sequence(sequence_id)
        if not sequence:
            return jsonify({"success": False, "error": "Sequence not found"}), 404

        return jsonify(
            {
                "success": True,
                "sequence": sequence,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/sequences/<int:sequence_id>/label", methods=["PUT"])
def update_sequence_label(sequence_id):
    try:
        processor = get_services().get_processor()
        label = request.json.get("label")
        if not label:
            return jsonify({"success": False, "error": "Label is required"}), 400

        if processor.update_sequence_label(sequence_id, label):
            processor.save_persistent_state()
            return jsonify(
                {
                    "success": True,
                    "message": f"Label updated to {label}",
                    "timestamp": datetime.now().isoformat(),
                }
            )
        return jsonify({"success": False, "error": "Update failed"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/sequences/statistics")
def get_label_statistics():
    try:
        processor = get_services().get_processor()
        return jsonify(
            {
                "success": True,
                "statistics": processor.get_label_statistics(),
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/health")
def health_check():
    motion_app = get_services().get_motion_app()
    status = "healthy"
    services = {}

    if motion_app:
        try:
            motion_app.get_sensor_data()
            services["motion_sensor"] = "operational"
        except Exception as e:
            services["motion_sensor"] = f"error: {str(e)}"
            status = "degraded"
    else:
        services["motion_sensor"] = "not_initialized"
        status = "degraded"

    return jsonify(
        {
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "services": services,
        }
    ), (200 if status == "healthy" else 503)


# ================================
# PRESENCE MONITORING ENDPOINTS
# ================================


@bp.route("/presence/devices", methods=["GET"])
def get_presence_devices():
    """Get all registered devices and their presence status"""
    try:
        services = get_services()
        monitor = services.get_presence_monitor()

        if not monitor:
            return (
                jsonify({"success": False, "error": "Presence monitor not available"}),
                503,
            )

        devices = monitor.get_devices()
        return jsonify({"success": True, "devices": devices})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/presence/devices", methods=["POST"])
def add_presence_device():
    """
    Register a new device for presence monitoring

    Expected JSON body:
    {
        "mac_address": "AA:BB:CC:DD:EE:FF",
        "name": "Jared's iPhone",
        "owner": "Jared"
    }
    """
    try:
        data = request.get_json()

        if not data or "mac_address" not in data or "name" not in data:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Missing required fields: mac_address, name",
                    }
                ),
                400,
            )

        services = get_services()
        monitor = services.get_presence_monitor()

        if not monitor:
            return (
                jsonify({"success": False, "error": "Presence monitor not available"}),
                503,
            )

        success, message = monitor.add_device(
            mac_address=data["mac_address"], name=data["name"], owner=data.get("owner")
        )

        if success:
            return jsonify({"success": True, "message": message})
        else:
            return jsonify({"success": False, "error": message}), 400

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/presence/devices/<int:device_id>", methods=["PUT"])
def update_presence_device(device_id):
    """
    Update device information

    Expected JSON body:
    {
        "name": "New Name",
        "owner": "New Owner"
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        services = get_services()
        monitor = services.get_presence_monitor()

        if not monitor:
            return (
                jsonify({"success": False, "error": "Presence monitor not available"}),
                503,
            )

        success, message = monitor.update_device(
            device_id=device_id,
            name=data.get("name"),
            owner=data.get("owner"),
            track_presence=data.get("track_presence"),
        )

        if success:
            return jsonify({"success": True, "message": message})
        else:
            return jsonify({"success": False, "error": message}), 400

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/presence/devices/<int:device_id>", methods=["DELETE"])
def remove_presence_device(device_id):
    """Remove a device from monitoring"""
    try:
        services = get_services()
        monitor = services.get_presence_monitor()

        if not monitor:
            return (
                jsonify({"success": False, "error": "Presence monitor not available"}),
                503,
            )

        success, message = monitor.remove_device(device_id)

        if success:
            return jsonify({"success": True, "message": message})
        else:
            return jsonify({"success": False, "error": message}), 404

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/presence/history", methods=["GET"])
def get_presence_history():
    """
    Get presence event history

    Query params:
        hours (int): Number of hours to look back (default: 24)
    """
    try:
        hours = request.args.get("hours", 24, type=int)

        services = get_services()
        monitor = services.get_presence_monitor()

        if not monitor:
            return (
                jsonify({"success": False, "error": "Presence monitor not available"}),
                503,
            )

        events = monitor.get_presence_history(hours=hours)

        return jsonify({"success": True, "events": events, "hours": hours})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/presence/status", methods=["GET"])
def get_presence_status():
    """Get presence monitoring system status"""
    try:
        services = get_services()
        monitor = services.get_presence_monitor()

        if not monitor:
            return (
                jsonify({"success": False, "error": "Presence monitor not available"}),
                503,
            )

        status = monitor.get_status()

        return jsonify({"success": True, "status": status})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/presence/who-is-home", methods=["GET"])
def who_is_home():
    """
    Quick endpoint to see who is currently home.
    ONLY counts devices where track_presence is True.
    """
    try:
        services = get_services()
        monitor = services.get_presence_monitor()

        if not monitor:
            return jsonify({"success": False, "error": "Monitor not available"}), 503

        # Get all devices
        all_devices = monitor.get_devices()

        # FILTER: Only get devices that are home AND represent a person (track_presence=True)
        present_devices = [d for d in all_devices if d["is_home"] and d.get("track_presence", True)]

        # Group by owner
        people_home = {}
        for device in present_devices:
            owner = device.get("owner", "Unknown")
            if owner not in people_home:
                people_home[owner] = []
            people_home[owner].append(device["name"])

        return jsonify(
            {
                "success": True,
                "people_home": list(people_home.keys()),
                "devices_home": present_devices,
                "count": len(present_devices),  # Count only meaningful devices
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
