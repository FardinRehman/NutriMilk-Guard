"""
Unit tests for SensorService normalization, delta calculations, and CSV export.
"""

import pytest
from app.services.sensor_service import SensorService
from app.services.quality_service import QualityService


@pytest.fixture
def sensor_svc(tmp_path):
    svc = SensorService()
    svc.history.clear()
    svc.previous_readings.clear()
    svc.history_cache_file = str(tmp_path / "test_history.json")
    return svc


def test_normalization_with_real_firebase_payload(sensor_svc):
    raw = {
        "milk_monitor": {
            "current": {
                "milk_quantity_ml": 0.0,
                "pH": 4.45,
                "temperature_C": 28.75
            }
        }
    }

    telemetry = sensor_svc.normalize_payload(raw, is_stale=False, is_connected=True)
    assert telemetry["is_connected"] is True
    assert telemetry["sensors_reporting"] == 3

    sensors = telemetry["sensors"]
    assert sensors["pH"]["value"] == 4.45
    assert sensors["temperature_C"]["value"] == 28.75
    # Verify zero-valued measurement is preserved as 0.0, not None
    assert sensors["milk_quantity_ml"]["value"] == 0.0
    assert sensors["milk_quantity_ml"]["is_reporting"] is True


def test_delta_calculation(sensor_svc):
    payload_1 = {"temperature_C": 25.0, "pH": 6.60}
    sensor_svc.normalize_payload(payload_1)

    payload_2 = {"temperature_C": 25.5, "pH": 6.55}
    telemetry_2 = sensor_svc.normalize_payload(payload_2)

    temp_sensor = telemetry_2["sensors"]["temperature_C"]
    ph_sensor = telemetry_2["sensors"]["pH"]

    assert temp_sensor["delta"] == 0.5
    assert temp_sensor["delta_direction"] == "up"

    assert ph_sensor["delta"] == -0.05
    assert ph_sensor["delta_direction"] == "down"


def test_alias_resolution(sensor_svc):
    # Test with alternative field names from different firmware revisions
    raw = {
        "temp": 22.4,
        "ph_value": 6.72,
        "volume": 250.0
    }
    telemetry = sensor_svc.normalize_payload(raw)
    sensors = telemetry["sensors"]

    assert sensors["temperature_C"]["value"] == 22.4
    assert sensors["pH"]["value"] == 6.72
    assert sensors["milk_quantity_ml"]["value"] == 250.0


def test_timestamp_parsing_unix_ms(sensor_svc):
    raw = {
        "timestamp": 1700000000000,
        "temperature_C": 20.0,
        "pH": 6.6
    }
    telemetry = sensor_svc.normalize_payload(raw)
    assert "2023-" in telemetry["timestamp"] or "UTC" in telemetry["timestamp"]


def test_history_and_csv_export(sensor_svc):
    payload = {"temperature_C": 24.1, "pH": 6.65, "milk_quantity_ml": 500.0}
    sensor_svc.normalize_payload(payload)

    history = sensor_svc.get_history(range_filter="all")
    assert len(history) == 1

    csv_data = sensor_svc.export_csv()
    assert "Timestamp,Unix Timestamp,Temperature (°C),pH Level,Milk Volume (mL),Overall Status" in csv_data
    assert "24.1" in csv_data
    assert "6.65" in csv_data
