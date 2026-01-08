import logging

from flask import Flask, jsonify, render_template, request

from app.extensions import db, migrate, socketio
from config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    # Initialize Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    socketio.init_app(app, path="/sheoak/socket.io")

    # Register Blueprints
    from app.routes.api import bp as api_bp
    from app.routes.hardwares import bp as hardwares_bp
    from app.routes.main import bp as main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(hardwares_bp, url_prefix="/hardwares")

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
