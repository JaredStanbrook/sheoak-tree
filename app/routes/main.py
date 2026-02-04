import os
from datetime import datetime
from functools import wraps

from flask import (
    Blueprint,
    Response,
    current_app,
    jsonify,
    render_template,
    send_file,
    send_from_directory,
    stream_with_context,
)

from app.services.event_service import bus

bp = Blueprint("main", __name__)
logger = current_app.logger if current_app else None


def require_hardware_manager(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_app.service_manager.get_service("HardwareManager"):
            return jsonify({"error": "Motion hardware service not available"}), 503
        return f(*args, **kwargs)

    return decorated_function


# app/routes/main.py


@bp.route("/")
def index():
    """Live Dashboard"""
    return render_template("dashboard.html", active_page="live")


@bp.route("/presence")
def presence():
    """Device Management"""
    return render_template("presence.html", active_page="presence")


@bp.route("/analysis")
def analysis():
    """Graphs and Logs"""
    # Note: You can split Logs to their own page if desired,
    # but combining Analysis + Logs often makes sense.
    return render_template("analysis.html", active_page="analysis")


@bp.route("/ai")
def ai_training():
    """AI roadmap / workbench."""
    template = (
        "ai_workbench.html" if current_app.config.get("AI_WORKBENCH_ENABLED", False) else "ai.html"
    )
    return render_template(template, active_page="ai")


@bp.route("/<filename>.pdf")
def serve_pdf(filename):
    """
    Serves any PDF file located in the static folder
    via the root URL (e.g., /manual.pdf).
    """
    return send_from_directory(current_app.static_folder, f"{filename}.pdf")


@bp.route("/download/activity")
@require_hardware_manager
def download_activity():
    hardware = current_app.service_manager.get_service("HardwareManager")
    if os.path.exists(hardware.log_file):
        filename = f"hardware_activity_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        return send_file(hardware.log_file, as_attachment=True, download_name=filename)
    return jsonify({"error": "Activity log file not found"}), 404


@bp.route("/stream")
def stream():
    """Server-Sent Events Endpoint"""

    def gen():
        q = bus.subscribe()
        try:
            while True:
                msg = q.get()
                yield msg
        except GeneratorExit:
            bus.unsubscribe(q)

    return Response(stream_with_context(gen()), mimetype="text/event-stream")
