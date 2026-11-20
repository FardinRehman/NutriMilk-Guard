"""
Nutri Milk Guard - Dashboard Route Blueprint.
Renders the primary real-time milk quality monitoring interface.
"""

from flask import Blueprint, render_template
from app.services import FirebaseService, SensorService, AlertService

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def index():
    """Main real-time dashboard view."""
    firebase_service = FirebaseService()
    sensor_service = SensorService()
    alert_service = AlertService()

    # Get connection diagnostic info
    conn_info = firebase_service.get_connection_info()

    # Get latest data if available
    raw_data = firebase_service.last_payload or firebase_service.fetch_data()
    is_stale = firebase_service.is_stale()
    is_connected = conn_info["is_connected"]

    # Normalize readings
    telemetry = sensor_service.normalize_payload(raw_data, is_stale=is_stale, is_connected=is_connected)
    
    # Process active alerts
    alert_service.process_sensors(telemetry)
    active_alert_count = alert_service.get_active_count()

    return render_template(
        "dashboard.html",
        telemetry=telemetry,
        conn_info=conn_info,
        active_alert_count=active_alert_count,
        active_page="dashboard"
    )
