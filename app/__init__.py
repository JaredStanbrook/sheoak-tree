import logging
import os

from flask import Flask, jsonify, render_template, request

from app.extensions import db, migrate, socketio
from app.services.core import ServiceManager
from app.services.hardware_manager import HardwareManager
from app.services.presence_monitor import IntelligentPresenceMonitor
from app.services.system_monitor import SystemMonitor
from config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

basedir = os.path.abspath(os.path.dirname(__file__))


def create_app(config_class=Config):
    app = Flask(
        __name__, instance_path=os.path.join(basedir, "data"), instance_relative_config=True
    )
    app.config.from_object(config_class)

    # Initialize Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    socketio.init_app(app, path="/sheoak/socket.io")

    # Initialize Service Manager
    app.service_manager = ServiceManager()

    # Initialize Services
    with app.app_context():
        # 1. System Monitor
        app.service_manager.register(SystemMonitor(app))

        # 2. Hardware Manager
        app.service_manager.register(HardwareManager(app))

        # 3. Presence Monitor (Process-based wrapper)
        # Note: Ensure IntelligentPresenceMonitor inherits BaseService
        app.service_manager.register(
            IntelligentPresenceMonitor(
                app, target_ip=app.config["SNMP_TARGET_IP"], community=app.config["SNMP_COMMUNITY"]
            )
        )

    from app.routes import api, devices, hardwares, main

    app.register_blueprint(main.bp)
    app.register_blueprint(api.bp, url_prefix="/api")
    app.register_blueprint(hardwares.bp, url_prefix="/hardwares")
    app.register_blueprint(devices.devices_bp)

    # Global Error Handlers
    register_error_handlers(app)

    return app


def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found_error(error):
        if request.path.startswith("/api/"):
            return jsonify({"success": False, "error": "Endpoint not found"}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal error: {error}")
        if request.path.startswith("/api/"):
            return jsonify({"success": False, "error": "Internal server error"}), 500
        return render_template("errors/500.html"), 500

    @app.errorhandler(503)
    def service_unavailable(error):
        if request.path.startswith("/api/"):
            return jsonify({"success": False, "error": "Service unavailable"}), 503
        return render_template("errors/503.html"), 503
