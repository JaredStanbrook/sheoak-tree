import os
from datetime import datetime
from functools import wraps
from flask import (
    Blueprint,
    render_template,
    jsonify,
    send_file,
    current_app,
    send_from_directory,
)
from flask_socketio import emit
from app.extensions import socketio
from app.services.manager import get_services

bp = Blueprint("main", __name__)
logger = current_app.logger if current_app else None


def require_motion_app(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not get_services().get_motion_app():
            return jsonify({"error": "Motion sensor service not available"}), 503
        return f(*args, **kwargs)

    return decorated_function


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/<filename>.pdf")
def serve_pdf(filename):
    """
    Serves any PDF file located in the static folder
    via the root URL (e.g., /manual.pdf).
    """
    return send_from_directory(current_app.static_folder, f"{filename}.pdf")


@bp.route("/download/activity")
@require_motion_app
def download_activity():
    app_svc = get_services().get_motion_app()
    if os.path.exists(app_svc.log_file):
        filename = f'sensor_activity_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        return send_file(app_svc.log_file, as_attachment=True, download_name=filename)
    return jsonify({"error": "Activity log file not found"}), 404


# --- SocketIO Handlers ---


@socketio.on("connect")
def handle_connect():
    app_svc = get_services().get_motion_app()
    if not app_svc:
        emit("error", {"message": "Sensor service not available"})
        return False

    emit(
        "sensor_update",
        {
            "all_sensors": app_svc.get_sensor_data(),
            "timestamp": datetime.now().isoformat(),
        },
    )


@socketio.on("disconnect")
def handle_disconnect():
    pass


@socketio.on("request_activity_data")
def handle_activity_request(data):
    app_svc = get_services().get_motion_app()
    if app_svc:
        hours = data.get("hours", 24)
        emit(
            "activity_data",
            {
                "activity": app_svc.get_activity_data(hours),
                "hours": hours,
                "timestamp": datetime.now().isoformat(),
            },
        )


@socketio.on("request_frequency_data")
def handle_frequency_request(data):
    """
    Handle request for frequency data (for the Graph tab).
    Calculates activations per time interval using SQL queries.
    """
    app_svc = get_services().get_motion_app()

    if app_svc:
        hours = int(data.get("hours", 24))
        interval = int(data.get("interval", 30))

        result = app_svc.get_frequency_data(hours, interval)

        emit(
            "frequency_data",
            {
                "frequency": result,
                "hours": hours,
                "interval": interval,
                "timestamp": datetime.now().isoformat(),
            },
        )
    else:
        emit("error", {"message": "Sensor service not initialized"})
