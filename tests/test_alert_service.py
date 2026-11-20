"""
Unit tests for AlertService deduplication, threshold monitoring, and auto-recovery.
"""

import pytest
from app.services.alert_service import AlertService
from app.services.sensor_service import SensorService


@pytest.fixture
def alert_svc(tmp_path):
    storage = str(tmp_path / "test_alerts.json")
    svc = AlertService(storage_path=storage)
    svc.alerts.clear()
    svc.active_alert_keys.clear()
    return svc


def test_alert_generation_and_deduplication(alert_svc):
    sensor_svc = SensorService()

    # Reading with critical low pH (4.45)
    payload_1 = {"temperature_C": 20.0, "pH": 4.45}
    telemetry_1 = sensor_svc.normalize_payload(payload_1)

    triggered_1 = alert_svc.process_sensors(telemetry_1)
    assert len(triggered_1) == 1
    assert alert_svc.get_active_count() == 1
    assert triggered_1[0]["severity"] == "critical"

    # Second reading with same condition - verify it is DEDUPLICATED (no new alert created)
    payload_2 = {"temperature_C": 20.0, "pH": 4.42}
    telemetry_2 = sensor_svc.normalize_payload(payload_2)

    triggered_2 = alert_svc.process_sensors(telemetry_2)
    assert len(triggered_2) == 0  # Deduplicated!
    assert alert_svc.get_active_count() == 1

    alert = alert_svc.alerts[0]
    assert alert["occurrence_count"] == 2
    assert "4.42" in alert["latest_reading"]


def test_alert_auto_resolution(alert_svc):
    sensor_svc = SensorService()

    # Critical reading
    telemetry_crit = sensor_svc.normalize_payload({"temperature_C": 20.0, "pH": 4.45})
    alert_svc.process_sensors(telemetry_crit)
    assert alert_svc.get_active_count() == 1

    # Recovery reading back to fresh normal range
    telemetry_norm = sensor_svc.normalize_payload({"temperature_C": 20.0, "pH": 6.65})
    alert_svc.process_sensors(telemetry_norm)

    assert alert_svc.get_active_count() == 0
    resolved_alert = alert_svc.alerts[0]
    assert resolved_alert["status"] == "resolved"
    assert resolved_alert["resolved_at"] is not None
