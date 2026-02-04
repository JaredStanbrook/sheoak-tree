import os

from flask import Flask, jsonify, render_template, request

from app.cli import register_commands
from app.config import Config
from app.extensions import db, migrate
from app.logging_config import setup_logging
from app.services.core import ServiceManager
from app.services.hardware_manager import HardwareManager
from app.services.presence_monitor import IntelligentPresenceMonitor
from app.services.snmp_presence_scanner import SnmpPresenceScanner
from app.services.system_monitor import SystemMonitor

__version__ = "1.0.0"

basedir = os.path.abspath(os.path.dirname(__file__))
project_root = os.path.abspath(os.path.join(basedir, os.pardir))
logger = None


def create_app(config_class=Config):
    app = Flask(
        __name__, instance_path=os.path.join(basedir, "data"), instance_relative_config=True
    )
    app.config.from_object(config_class)

    with app.app_context():
        setup_logging(
            app=app,
            log_level=app.config.get("LOG_LEVEL", "INFO"),
            log_dir=app.config.get("LOG_DIR", os.path.join(project_root, "logs")),
        )

    global logger
    logger = app.logger

    # Initialize Extensions
    db.init_app(app)
    migrate.init_app(app, db)
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
        if not app.config.get("DISABLE_PRESENCE_MONITOR", False):
            app.service_manager.register(
                IntelligentPresenceMonitor(
                    app,
                    target_ip=app.config["SNMP_TARGET_IP"],
                    community=app.config["SNMP_COMMUNITY"],
                    scan_interval=app.config.get("PRESENCE_SCAN_INTERVAL", 60),
                )
            )

        if app.config.get("ENABLE_SNMP_PRESENCE", False):
            app.service_manager.register(
                SnmpPresenceScanner(
                    app,
                    target_ip=app.config["SNMP_TARGET_IP"],
                    community=app.config["SNMP_COMMUNITY"],
                    interval=app.config.get("SNMP_POLL_INTERVAL", 60),
                )
            )

    from app.routes import api, devices, hardwares, main

    app.register_blueprint(main.bp)
    app.register_blueprint(api.bp, url_prefix="/api")
    app.register_blueprint(hardwares.bp, url_prefix="/hardwares")
    app.register_blueprint(devices.devices_bp)

    @app.context_processor
    def inject_sheoak_config():
        return {
            "sheoak_config": {
                "timezone": app.config.get("TIMEZONE", "Australia/Perth"),
                "locale": app.config.get("LOCALE", "en-AU"),
            },
            "ai_workbench_enabled": app.config.get("AI_WORKBENCH_ENABLED", False),
        }

    def start_services():
        if app.config.get("TESTING"):
            return
        if not getattr(app, "_services_started", False):
            app.service_manager.start_all()
            app._services_started = True

    def stop_services():
        if getattr(app, "_services_started", False):
            app.service_manager.stop_all()
            app._services_started = False

    app.start_services = start_services
    app.stop_services = stop_services

    # Register CLI commands
    register_commands(app)

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
