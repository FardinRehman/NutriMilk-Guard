"""
Nutri Milk Guard - Alert Management Service.
Generates alerts based on sensor thresholds, performs stateful deduplication
to prevent alert flooding, and tracks alert lifecycle (active vs resolved).
"""

import os
import json
import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from app.services.quality_service import QualityStatus

logger = logging.getLogger(__name__)


class AlertService:
    """
    Manages generation, deduplication, and resolution of sensor alerts.
    Does NOT write alerts to ESP32 Firebase nodes to protect hardware state.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(AlertService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, storage_path: Optional[str] = None):
        if getattr(self, "_initialized", False):
            return

        self.storage_path = storage_path or os.path.join(
            os.path.abspath(os.path.dirname(__file__)), "..", "..", "instance", "alerts.json"
        )
        self.alerts: List[Dict[str, Any]] = []
        self.active_alert_keys: Dict[str, str] = {}  # sensor_id -> alert_id
        
        self._load_alerts()
        self._initialized = True

    def _load_alerts(self):
        """Load persisted alerts from instance directory."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.alerts = data
                        for alert in self.alerts:
                            if alert.get("status") == "active":
                                self.active_alert_keys[alert["sensor_id"]] = alert["id"]
            except Exception as e:
                logger.warning(f"Could not load alerts storage: {e}")

    def _persist_alerts(self):
        """Persist alerts to file storage."""
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self.alerts[-150:], f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to persist alerts: {e}")

    def process_sensors(self, normalized_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Evaluate normalized sensor readings, create new alerts if condition tripped,
        or auto-resolve if reading returned to normal. Deduplicates ongoing alerts.
        """
        now = time.time()
        iso_now = datetime.fromtimestamp(now, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        sensors = normalized_payload.get("sensors", {})
        newly_triggered = []

        for sensor_id, sensor_data in sensors.items():
            status = sensor_data.get("status")
            val = sensor_data.get("value")
            unit = sensor_data.get("unit", "")
            sensor_name = sensor_data.get("name", sensor_id)
            threshold_desc = sensor_data.get("threshold_applied", "Configured Limit")
            explanation = sensor_data.get("explanation", "")

            # If condition is Critical or Warning
            if status in (QualityStatus.CRITICAL, QualityStatus.WARNING):
                severity = "critical" if status == QualityStatus.CRITICAL else "warning"
                
                # Check if an active alert already exists for this sensor
                if sensor_id in self.active_alert_keys:
                    # Update reading and last-seen timestamp on existing alert (DEDUPLICATION)
                    alert_id = self.active_alert_keys[sensor_id]
                    for a in self.alerts:
                        if a["id"] == alert_id:
                            a["latest_reading"] = f"{val} {unit}"
                            a["last_evaluated"] = iso_now
                            a["occurrence_count"] = a.get("occurrence_count", 1) + 1
                            break
                else:
                    # Trigger a new alert
                    alert_id = f"ALT-{int(now * 1000)}"
                    new_alert = {
                        "id": alert_id,
                        "sensor_id": sensor_id,
                        "sensor_name": sensor_name,
                        "severity": severity,
                        "status": "active",
                        "initial_reading": f"{val} {unit}",
                        "latest_reading": f"{val} {unit}",
                        "threshold": threshold_desc,
                        "message": explanation,
                        "timestamp": iso_now,
                        "unix_timestamp": int(now),
                        "resolved_at": None,
                        "occurrence_count": 1,
                        "source": "Application Quality Rule"
                    }
                    self.alerts.append(new_alert)
                    self.active_alert_keys[sensor_id] = alert_id
                    newly_triggered.append(new_alert)
                    logger.warning(f"New alert triggered: [{severity.upper()}] {sensor_name}: {explanation}")

            elif status == QualityStatus.NORMAL and sensor_id in self.active_alert_keys:
                # Sensor recovered to normal! Auto-resolve active alert
                alert_id = self.active_alert_keys.pop(sensor_id)
                for a in self.alerts:
                    if a["id"] == alert_id:
                        a["status"] = "resolved"
                        a["resolved_at"] = iso_now
                        a["recovery_reading"] = f"{val} {unit}"
                        logger.info(f"Alert resolved: {sensor_name} returned to normal ({val} {unit})")
                        break

        if newly_triggered or not self.active_alert_keys:
            self._persist_alerts()

        return newly_triggered

    def get_alerts(self, status_filter: str = "all", severity_filter: str = "all") -> List[Dict[str, Any]]:
        """Return alerts list with optional filtering."""
        filtered = self.alerts

        if status_filter != "all":
            filtered = [a for a in filtered if a.get("status") == status_filter]

        if severity_filter != "all":
            filtered = [a for a in filtered if a.get("severity") == severity_filter]

        # Return reverse chronological (newest first)
        return list(reversed(filtered))

    def get_active_count(self) -> int:
        """Return count of currently active alerts."""
        return len(self.active_alert_keys)

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Mark an alert as acknowledged."""
        for a in self.alerts:
            if a["id"] == alert_id:
                a["acknowledged"] = True
                self._persist_alerts()
                return True
        return False

    def clear_resolved_alerts(self):
        """Clear resolved alerts from memory."""
        self.alerts = [a for a in self.alerts if a.get("status") == "active"]
        self._persist_alerts()
