from flask import Blueprint, jsonify, request, current_app
from datetime import datetime
from app.services.manager import get_services

bp = Blueprint("api", __name__)


@bp.route("/sensors")
def api_sensors():
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
        return jsonify(
            {"success": True, **result, "timestamp": datetime.now().isoformat()}
        )
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
