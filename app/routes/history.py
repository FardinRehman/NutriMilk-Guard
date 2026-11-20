"""
Nutri Milk Guard - Sensor History Route Blueprint.
Displays recorded sensor data, date filters, and provides CSV export.
"""

from flask import Blueprint, render_template, request, Response
from app.services import SensorService, AlertService, FirebaseService

history_bp = Blueprint("history", __name__, url_prefix="/history")


@history_bp.route("/")
def index():
    """History table page with range filters and search."""
    sensor_service = SensorService()
    alert_service = AlertService()
    firebase_service = FirebaseService()

    range_filter = request.args.get("range", "all")
    records = sensor_service.get_history(range_filter=range_filter, limit=200)

    return render_template(
        "history.html",
        records=records,
        range_filter=range_filter,
        conn_info=firebase_service.get_connection_info(),
        active_alert_count=alert_service.get_active_count(),
        active_page="history"
    )


@history_bp.route("/export")
def export():
    """Export recorded history to CSV format."""
    sensor_service = SensorService()
    csv_data = sensor_service.export_csv()
    
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=nutri_milk_guard_history.csv"}
    )
