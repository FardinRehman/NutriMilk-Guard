"""
Nutri Milk Guard - Settings Route Blueprint.
Manages application thresholds, field aliases, update intervals,
and diagnostics without altering ESP32 hardware memory.
"""

import os
import json
from flask import Blueprint, render_template, request, flash, redirect, url_for
from config import Config
from app.services import FirebaseService, SensorService, QualityService, AlertService

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")


def load_local_settings():
    """Load customized thresholds and display preferences from instance JSON."""
    if os.path.exists(Config.SETTINGS_FILE):
        try:
            with open(Config.SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_local_settings(data):
    """Save user-configured settings safely into instance directory."""
    os.makedirs(os.path.dirname(Config.SETTINGS_FILE), exist_ok=True)
    with open(Config.SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


@settings_bp.route("/", methods=["GET", "POST"])
def index():
    """Settings view and form update handler."""
    firebase_service = FirebaseService()
    quality_service = QualityService()
    alert_service = AlertService()

    local_settings = load_local_settings()
    current_thresholds = quality_service.thresholds

    if request.method == "POST":
        action = request.form.get("action", "save_thresholds")

        if action == "save_thresholds":
            try:
                # Temperature thresholds
                temp_cfg = current_thresholds.get("temperature_C", {}).copy()
                temp_cfg["optimal_max"] = float(request.form.get("temp_optimal_max", 10.0))
                temp_cfg["warning_max"] = float(request.form.get("temp_warning_max", 25.0))
                temp_cfg["critical_max"] = float(request.form.get("temp_critical_max", 35.0))
                temp_cfg["critical_min"] = float(request.form.get("temp_critical_min", -0.5))

                # pH thresholds
                ph_cfg = current_thresholds.get("pH", {}).copy()
                ph_cfg["critical_low"] = float(request.form.get("ph_critical_low", 5.90))
                ph_cfg["warning_low"] = float(request.form.get("ph_warning_low", 6.20))
                ph_cfg["optimal_min"] = float(request.form.get("ph_optimal_min", 6.50))
                ph_cfg["optimal_max"] = float(request.form.get("ph_optimal_max", 6.80))
                ph_cfg["warning_high"] = float(request.form.get("ph_warning_high", 7.00))
                ph_cfg["critical_high"] = float(request.form.get("ph_critical_high", 7.30))

                # Update memory
                quality_service.update_thresholds({
                    "temperature_C": temp_cfg,
                    "pH": ph_cfg
                })

                # Update local file
                local_settings["thresholds"] = quality_service.thresholds
                local_settings["poll_interval"] = float(request.form.get("poll_interval", 3.0))
                local_settings["stale_timeout"] = int(request.form.get("stale_timeout", 45))
                local_settings["db_path"] = request.form.get("db_path", "milk_monitor/current").strip().strip("/")
                save_local_settings(local_settings)

                # Update live service intervals
                firebase_service.poll_interval = local_settings["poll_interval"]
                firebase_service.stale_timeout = local_settings["stale_timeout"]
                firebase_service.default_db_path = local_settings["db_path"]

                flash("Settings successfully updated and applied.", "success")
            except ValueError as e:
                flash(f"Invalid input numeric value: {e}", "danger")

        elif action == "reset_defaults":
            if os.path.exists(Config.SETTINGS_FILE):
                os.remove(Config.SETTINGS_FILE)
            flash("Settings restored to dairy science project defaults.", "info")
            return redirect(url_for("settings.index"))

    conn_info = firebase_service.get_connection_info()

    return render_template(
        "settings.html",
        conn_info=conn_info,
        thresholds=quality_service.thresholds,
        local_settings=local_settings,
        active_alert_count=alert_service.get_active_count(),
        active_page="settings"
    )
