"""
Nutri Milk Guard - Alerts Route Blueprint.
Displays threshold violation events, recovery timestamps, and allows acknowledgement.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.services import AlertService, FirebaseService

alerts_bp = Blueprint("alerts", __name__, url_prefix="/alerts")


@alerts_bp.route("/")
def index():
    """Alerts log page with severity and status filters."""
    alert_service = AlertService()
    firebase_service = FirebaseService()

    status_filter = request.args.get("status", "all")
    severity_filter = request.args.get("severity", "all")
    
    alerts_list = alert_service.get_alerts(
        status_filter=status_filter,
        severity_filter=severity_filter
    )

    return render_template(
        "alerts.html",
        alerts=alerts_list,
        status_filter=status_filter,
        severity_filter=severity_filter,
        active_alert_count=alert_service.get_active_count(),
        conn_info=firebase_service.get_connection_info(),
        active_page="alerts"
    )


@alerts_bp.route("/acknowledge/<alert_id>", methods=["POST"])
def acknowledge(alert_id):
    """Acknowledge an alert."""
    alert_service = AlertService()
    alert_service.acknowledge_alert(alert_id)
    flash(f"Alert {alert_id} acknowledged.", "success")
    return redirect(url_for("alerts.index"))


@alerts_bp.route("/clear-resolved", methods=["POST"])
def clear_resolved():
    """Clear inactive/resolved alerts."""
    alert_service = AlertService()
    alert_service.clear_resolved_alerts()
    flash("Resolved alerts cleared from view.", "info")
    return redirect(url_for("alerts.index"))
