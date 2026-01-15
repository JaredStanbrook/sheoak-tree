from datetime import datetime

from flask import Blueprint, current_app, jsonify, request

from app.services.manager import get_services

bp = Blueprint("api", __name__)
logger = current_app.logger if current_app else None


@bp.route("/events", methods=["GET"])
def dev_get_all_events():
    """
    Development endpoint to load all events with hardware relationships.
    """
    # Check if we are in development mode for safety
    if current_app.config.get("ENV") != "development":
        return jsonify(
            {"success": False, "error": "Endpoint only available in development mode"}
        ), 403

    try:
        from app.models import Event

        # Query all events, joining the hardware table to ensure relationships are loaded
        all_events = Event.query.all()

        return jsonify(
            {
                "success": True,
                "count": len(all_events),
                "events": [e.to_dict() for e in all_events],
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        current_app.logger.error(f"Dev API Error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/hardwares", methods=["GET"])
def get_hardwares():
    """
    Returns the current state of all hardware devices.
    Used for the initial dashboard render.
    """
    try:
        hardware = current_app.service_manager.get_service("HardwareManager")

        if not hardware:
            return jsonify({"success": False, "error": "Hardware service not running"}), 503

        response_data = []
        for _, strategy in hardware.strategies.items():
            snapshot = strategy.get_snapshot()
            response_data.append(snapshot)

        return jsonify({"success": True, "hardwares": response_data}), 200

    except Exception as e:
        current_app.logger.error(f"API Error fetching hardwares: {e}")
        return jsonify({"success": False, "error": "Failed to fetch hardware data"}), 500


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
