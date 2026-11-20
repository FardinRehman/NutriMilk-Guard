"""
Nutri Milk Guard - Flask Application Factory.
"""

import os
from flask import Flask, render_template
from config import config_by_name, Config


def create_app(config_name=None):
    """Factory creating and configuring the Flask application instance."""
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")

    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder="templates",
        static_folder="static"
    )

    # Load configuration
    cfg = config_by_name.get(config_name, Config)
    app.config.from_object(cfg)

    # Ensure instance folder exists
    os.makedirs(app.instance_path, exist_ok=True)

    # Register Blueprints
    from app.routes.dashboard import dashboard_bp
    from app.routes.history import history_bp
    from app.routes.alerts import alerts_bp
    from app.routes.settings import settings_bp
    from app.routes.api import api_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(api_bp)

    # Context processors for templates
    @app.context_processor
    def inject_app_metadata():
        from app.services import FirebaseService, AlertService
        try:
            fb_info = FirebaseService().get_connection_info()
            alert_count = AlertService().get_active_count()
        except Exception:
            fb_info = {"is_connected": False, "is_stale": True, "status": "UNKNOWN", "target_path": "milk_monitor/current"}
            alert_count = 0

        return {
            "APP_NAME": "Nutri Milk Guard",
            "APP_SUBTITLE": "IoT-Based Milk Quality Monitoring System",
            "PROJECT_INSTITUTION": "VTU Engineering Final Project",
            "FIREBASE_PROJECT_ID": app.config.get("FIREBASE_PROJECT_ID", "milk-monitoring-4cb97"),
            "conn_info": fb_info,
            "active_alert_count": alert_count
        }

    # Error Handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("errors/404.html", error=e), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template("errors/500.html", error=e), 500

    return app
