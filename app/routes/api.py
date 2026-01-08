from datetime import datetime

from flask import Blueprint, current_app, jsonify, request

from app.services.manager import get_services

bp = Blueprint("api", __name__)
logger = current_app.logger if current_app else None


@bp.route("/hardwares")
def api_hardwares():
    """Get current state of all hardware hardwares/relays."""
    hardware = get_services().get_hardware_manager()
    if not hardware:
        return jsonify({"success": False, "error": "Hardware service unavailable"}), 503

    return jsonify(
        {
            "success": True,
            "hardwares": hardware.get_hardware_data(),
            "timestamp": datetime.now().isoformat(),
        }
    )


@bp.route("/activity/<int:hours>")
def api_activity(hours):
    """Get raw event logs."""
    hardware = get_services().get_hardware_manager()
    if not hardware:
        return jsonify({"success": False, "error": "Hardware service unavailable"}), 503

    return jsonify(
        {
            "success": True,
            "activity": hardware.get_activity_data(hours),
            "timestamp": datetime.now().isoformat(),
            "hours": hours,
        }
    )


@bp.route("/frequency/<int:hours>/<int:interval>")
def api_frequency(hours, interval):
    """Get aggregated frequency data for graphs."""
    hardware = get_services().get_hardware_manager()
    if not hardware:
        return jsonify({"success": False, "error": "Hardware service unavailable"}), 503

    data = hardware.get_frequency_data(hours, interval)

    return jsonify(
        {
            "success": True,
            "frequency": data,
            "timestamp": datetime.now().isoformat(),
            "hours": hours,
            "interval_minutes": interval,
        }
    )


@bp.route("/hardwares/<int:hardware_id>/toggle", methods=["POST"])
def toggle_hardware(hardware_id):
    """Toggle a relay or output device."""
    hardware = get_services().get_hardware_manager()
    if not hardware:
        return jsonify({"success": False, "error": "Hardware service unavailable"}), 503

    # The hardware manager handles the specifics of the toggle
    success, result = hardware.toggle_hardware(hardware_id)

    if success:
        return jsonify(
            {
                "success": True,
                "new_state": result,  # True = On, False = Off
                "message": "Device toggled successfully",
            }
        )
    else:
        return jsonify({"success": False, "error": result}), 400


# ================================
# SEQUENCE PROCESSING ROUTES
# ================================


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
    """System Health Check."""
    hardware = get_services().get_hardware_manager()
    status = "healthy"
    services = {}

    # Check Hardware Service
    if hardware:
        try:
            # Simple read to ensure lock isn't stuck
            hardware.get_hardware_data()
            services["hardware_system"] = "operational"
        except Exception as e:
            services["hardware_system"] = f"error: {str(e)}"
            status = "degraded"
    else:
        services["hardware_system"] = "not_initialized"
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
    """Register a new device for presence monitoring"""
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
    """Update device information"""
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
    """Get presence event history"""
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
    """Quick endpoint to see who is currently home."""
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
                "count": len(present_devices),
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
