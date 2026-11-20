"""
Nutri Milk Guard - REST & Server-Sent Events (SSE) API Blueprint.
Provides streaming live updates to the browser dashboard and JSON endpoints.
"""

import time
import json
import queue
import logging
from flask import Blueprint, Response, jsonify, request
from app.services import FirebaseService, SensorService, AlertService

logger = logging.getLogger(__name__)
api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/status")
def status():
    """Connection diagnostics and system status."""
    firebase_service = FirebaseService()
    return jsonify(firebase_service.get_connection_info())


@api_bp.route("/sensors/latest")
def latest():
    """Latest normalized sensor readings."""
    firebase_service = FirebaseService()
    sensor_service = SensorService()
    alert_service = AlertService()

    raw_data = firebase_service.last_payload or firebase_service.fetch_data()
    is_stale = firebase_service.is_stale()
    conn_info = firebase_service.get_connection_info()

    telemetry = sensor_service.normalize_payload(
        raw_data,
        is_stale=is_stale,
        is_connected=conn_info["is_connected"]
    )
    alert_service.process_sensors(telemetry)

    return jsonify({
        "telemetry": telemetry,
        "connection": conn_info,
        "active_alerts": alert_service.get_active_count()
    })


@api_bp.route("/sensors/history")
def history():
    """Historical sensor readings for charts."""
    sensor_service = SensorService()
    range_filter = request.args.get("range", "1h")
    records = sensor_service.get_history(range_filter=range_filter, limit=100)
    return jsonify({
        "range": range_filter,
        "count": len(records),
        "records": records
    })


@api_bp.route("/alerts")
def alerts():
    """Active and logged alerts."""
    alert_service = AlertService()
    status_filter = request.args.get("status", "all")
    severity_filter = request.args.get("severity", "all")
    return jsonify({
        "alerts": alert_service.get_alerts(status_filter, severity_filter),
        "active_count": alert_service.get_active_count()
    })


@api_bp.route("/reconnect", methods=["POST"])
def reconnect():
    """Force an immediate re-fetch and connection health check."""
    firebase_service = FirebaseService()
    data = firebase_service.fetch_data()
    conn_info = firebase_service.get_connection_info()
    return jsonify({
        "success": conn_info["is_connected"],
        "connection": conn_info
    })


@api_bp.route("/stream")
def stream():
    """
    Server-Sent Events (SSE) live data stream.
    Streams new readings to the browser automatically when ESP32 updates Firebase.
    Includes periodic heartbeats to maintain persistent connection.
    """
    firebase_service = FirebaseService()
    sensor_service = SensorService()
    alert_service = AlertService()

    client_queue = queue.Queue(maxsize=20)

    def on_new_data(raw_payload):
        """Subscriber callback pushing data into client SSE queue."""
        try:
            client_queue.put_nowait(raw_payload)
        except queue.Full:
            pass

    firebase_service.subscribe(on_new_data)

    def event_stream():
        try:
            # Send initial state immediately on connect
            conn_info = firebase_service.get_connection_info()
            raw_data = firebase_service.last_payload or firebase_service.fetch_data()
            is_stale = firebase_service.is_stale()

            initial_telemetry = sensor_service.normalize_payload(
                raw_data,
                is_stale=is_stale,
                is_connected=conn_info["is_connected"]
            )
            alert_service.process_sensors(initial_telemetry)

            initial_event = {
                "telemetry": initial_telemetry,
                "connection": conn_info,
                "active_alerts": alert_service.get_active_count()
            }
            yield f"event: telemetry\ndata: {json.dumps(initial_event)}\n\n"

            last_ping = time.time()

            while True:
                try:
                    # Wait up to 5 seconds for incoming data update
                    raw = client_queue.get(timeout=5.0)
                    is_stale = firebase_service.is_stale()
                    conn = firebase_service.get_connection_info()
                    
                    telemetry = sensor_service.normalize_payload(
                        raw,
                        is_stale=is_stale,
                        is_connected=conn["is_connected"]
                    )
                    alert_service.process_sensors(telemetry)

                    event_payload = {
                        "telemetry": telemetry,
                        "connection": conn,
                        "active_alerts": alert_service.get_active_count()
                    }
                    yield f"event: telemetry\ndata: {json.dumps(event_payload)}\n\n"

                except queue.Empty:
                    # Send periodic SSE keepalive heartbeat
                    now = time.time()
                    if now - last_ping >= 15.0:
                        last_ping = now
                        conn = firebase_service.get_connection_info()
                        yield f"event: ping\ndata: {json.dumps({'time': int(now), 'connected': conn['is_connected']})}\n\n"

        except GeneratorExit:
            # Client disconnected
            logger.debug("SSE client disconnected cleanly.")
        finally:
            firebase_service.unsubscribe(on_new_data)

    return Response(
        event_stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )
