"""
Integration tests for Flask application routes and API endpoints.
"""

import pytest
from app import create_app


@pytest.fixture
def client():
    app = create_app("testing")
    with app.test_client() as client:
        yield client


def test_dashboard_route(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Nutri Milk Guard" in response.data
    assert b"Overall Milk Quality Assessment" in response.data


def test_history_route(client):
    response = client.get("/history/")
    assert response.status_code == 200
    assert b"Sensor Reading History" in response.data


def test_history_export_route(client):
    response = client.get("/history/export")
    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert b"Timestamp,Unix Timestamp,Temperature" in response.data


def test_alerts_route(client):
    response = client.get("/alerts/")
    assert response.status_code == 200
    assert b"Safety Threshold Alerts" in response.data


def test_settings_route(client):
    response = client.get("/settings/")
    assert response.status_code == 200
    assert b"Quality Threshold Configuration" in response.data


def test_api_status(client):
    response = client.get("/api/status")
    assert response.status_code == 200
    json_data = response.get_json()
    assert "status" in json_data
    assert "project_id" in json_data
    assert json_data["project_id"] == "milk-monitoring-4cb97"


def test_api_sensors_latest(client):
    response = client.get("/api/sensors/latest")
    assert response.status_code == 200
    json_data = response.get_json()
    assert "telemetry" in json_data
    assert "connection" in json_data


def test_api_reconnect(client):
    response = client.post("/api/reconnect")
    assert response.status_code == 200
    json_data = response.get_json()
    assert "connection" in json_data


def test_404_error_page(client):
    response = client.get("/non-existent-route-404")
    assert response.status_code == 404
    assert b"Page Not Found" in response.data
