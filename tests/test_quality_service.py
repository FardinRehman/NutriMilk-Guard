"""
Unit tests for QualityService milk assessment logic.
"""

import pytest
from app.services.quality_service import QualityService, QualityStatus


@pytest.fixture
def service():
    return QualityService()


def test_ph_evaluation_normal(service):
    res = service.evaluate_sensor("pH", 6.65)
    assert res["status"] == QualityStatus.NORMAL
    assert "6.65" in res["explanation"]


def test_ph_evaluation_acidic_warning(service):
    res = service.evaluate_sensor("pH", 6.10)
    assert res["status"] == QualityStatus.WARNING
    assert "acidic" in res["explanation"].lower()


def test_ph_evaluation_acidic_critical(service):
    res = service.evaluate_sensor("pH", 4.45)
    assert res["status"] == QualityStatus.CRITICAL
    assert "curdling" in res["explanation"].lower()


def test_ph_evaluation_alkaline_critical(service):
    res = service.evaluate_sensor("pH", 7.45)
    assert res["status"] == QualityStatus.CRITICAL
    assert "alkaline" in res["explanation"].lower()


def test_temperature_evaluation_normal_chilled(service):
    res = service.evaluate_sensor("temperature_C", 4.0)
    assert res["status"] == QualityStatus.NORMAL
    assert "chilled" in res["explanation"].lower()


def test_temperature_evaluation_warning_ambient(service):
    res = service.evaluate_sensor("temperature_C", 26.5)
    assert res["status"] == QualityStatus.WARNING
    assert "refrigeration" in res["explanation"].lower()


def test_temperature_evaluation_critical_high(service):
    res = service.evaluate_sensor("temperature_C", 38.0)
    assert res["status"] == QualityStatus.CRITICAL
    assert "spoilage" in res["explanation"].lower()


def test_temperature_evaluation_freezing(service):
    res = service.evaluate_sensor("temperature_C", -1.2)
    assert res["status"] == QualityStatus.CRITICAL
    assert "freezing" in res["explanation"].lower()


def test_stale_data_evaluation(service):
    res = service.evaluate_sensor("pH", 6.65, is_stale=True)
    assert res["status"] == QualityStatus.OFFLINE
    assert "timeout" in res["explanation"].lower()


def test_missing_or_invalid_values(service):
    res_none = service.evaluate_sensor("pH", None)
    assert res_none["status"] == QualityStatus.INSUFFICIENT_DATA

    res_invalid = service.evaluate_sensor("pH", "not-a-number")
    assert res_invalid["status"] == QualityStatus.INSUFFICIENT_DATA


def test_overall_synthesis_critical(service):
    evals = {
        "pH": service.evaluate_sensor("pH", 4.45),
        "temperature_C": service.evaluate_sensor("temperature_C", 28.75)
    }
    overall = service.evaluate_overall(evals, is_connected=True)
    assert overall["status"] == QualityStatus.CRITICAL
    assert "pH" in overall["summary"]


def test_overall_synthesis_disconnected(service):
    overall = service.evaluate_overall({}, is_connected=False)
    assert overall["status"] == QualityStatus.OFFLINE
