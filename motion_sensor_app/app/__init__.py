import logging
from flask import Flask
from config import Config
from flask_socketio import SocketIO, emit

"""
Flask Application Factory

This module creates and configures the Flask application for the
Motion Sensor application.
"""
socketio = SocketIO()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_app(config_class=Config):
    """Application factory pattern for Flask app creation"""
    app = Flask(__name__)
    app.config.from_object(config_class)

    socketio.init_app(
        app,
        cors_allowed_origins="*",
        path="/sheoak/socket.io",
        async_mode="gevent",
    )

    from app.routes.main import bp as main_bp
    from app.routes.api import bp as api_bp

    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    # Register error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        from flask import render_template
        if request.path.startswith("/api/"):
            return jsonify({"error": "Endpoint not found"}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal error: {error}")
        if request.path.startswith("/api/"):
            return jsonify({"error": "Internal server error"}), 500
        return render_template("errors/500.html"), 500

    @app.errorhandler(503)
    def service_unavailable(error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Service temporarily unavailable"}), 503
        return render_template("errors/503.html"), 503

    return app
