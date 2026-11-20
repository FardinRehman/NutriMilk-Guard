"""
Unit tests for FirebaseService mocking network requests and testing fail-safe behavior.
"""

import pytest
from unittest.mock import MagicMock, patch
from app.services.firebase_service import FirebaseService, ConnectionStatus


@pytest.fixture
def fb_service():
    service = FirebaseService()
    return service


def test_firebase_service_mock_read_success(fb_service, monkeypatch):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "milk_monitor": {
            "current": {
                "milk_quantity_ml": 0.0,
                "pH": 4.45,
                "temperature_C": 28.75
            }
        }
    }

    monkeypatch.setattr(fb_service._session, "get", lambda *args, **kwargs: mock_resp)

    data = fb_service.fetch_data("milk_monitor/current")
    assert "milk_monitor" in data
    assert fb_service.connection_status == ConnectionStatus.CONNECTED


def test_firebase_service_permission_denied(fb_service, monkeypatch):
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    monkeypatch.setattr(fb_service._session, "get", lambda *args, **kwargs: mock_resp)

    data = fb_service.fetch_data("restricted/path")
    assert data == {}
    assert fb_service.connection_status == ConnectionStatus.ERROR
    assert "Permission Denied" in fb_service.last_error_message


def test_firebase_service_subscriber(fb_service):
    received = []

    def callback(payload):
        received.append(payload)

    fb_service.subscribe(callback)
    test_payload = {"test": 123}
    fb_service._broadcast(test_payload)

    assert len(received) == 1
    assert received[0] == test_payload

    fb_service.unsubscribe(callback)
    fb_service._broadcast({"test": 456})
    assert len(received) == 1
