"""
Nutri Milk Guard - Sensor Normalization and History Service.
Parses raw Firebase JSON, maps sensor aliases, calculates deltas,
maintains historical series, and integrates quality assessment.
"""

import os
import json
import time
import logging
from datetime import datetime, timezone
from collections import deque
from typing import Dict, Any, List, Optional
from config import Config
from app.services.quality_service import QualityService, QualityStatus

logger = logging.getLogger(__name__)

# Standard sensor metadata definitions
DEFAULT_SENSOR_DEFINITIONS = {
    "temperature_C": {
        "id": "temperature_C",
        "name": "Milk Temperature",
        "unit": "°C",
        "icon": "thermometer",
        "aliases": ["temperature_C", "temperature", "temp", "temp_c", "tempC"],
        "precision": 2
    },
    "pH": {
        "id": "pH",
        "name": "Milk pH Level",
        "unit": "pH",
        "icon": "droplets",
        "aliases": ["pH", "ph", "ph_value", "phValue", "PH"],
        "precision": 2
    },
    "milk_quantity_ml": {
        "id": "milk_quantity_ml",
        "name": "Milk Volume",
        "unit": "mL",
        "icon": "scale",
        "aliases": ["milk_quantity_ml", "quantity", "volume", "milkQuantity", "level_ml"],
        "precision": 1
    }
}


class SensorService:
    """
    Normalizes readings, computes reading trends, and manages session history.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(SensorService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, quality_service: Optional[QualityService] = None):
        if getattr(self, "_initialized", False):
            return

        self.quality_service = quality_service or QualityService()
        self.sensor_definitions = DEFAULT_SENSOR_DEFINITIONS.copy()
        self.max_history = Config.MAX_HISTORY_POINTS
        self.history_cache_file = Config.HISTORY_CACHE_FILE
        
        # In-memory ring buffer for historical data points
        self.history: deque = deque(maxlen=self.max_history)
        self.previous_readings: Dict[str, float] = {}
        self.latest_normalized: Optional[Dict[str, Any]] = None

        # Load cached history if available
        self._load_cached_history()
        self._initialized = True

    def _load_cached_history(self):
        """Load session history points from instance storage if present."""
        if os.path.exists(self.history_cache_file):
            try:
                with open(self.history_cache_file, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                    if isinstance(cached, list):
                        for item in cached:
                            self.history.append(item)
                logger.info(f"Loaded {len(self.history)} historical records from cache.")
            except Exception as e:
                logger.warning(f"Could not load history cache: {e}")

    def _persist_history(self):
        """Persist session history buffer to disk asynchronously or on update."""
        try:
            os.makedirs(os.path.dirname(self.history_cache_file), exist_ok=True)
            with open(self.history_cache_file, "w", encoding="utf-8") as f:
                json.dump(list(self.history), f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to persist history cache: {e}")

    def normalize_payload(self, raw_data: Dict[str, Any], is_stale: bool = False, is_connected: bool = True) -> Dict[str, Any]:
        """
        Convert raw Firebase dictionary into normalized telemetry payload.
        Handles nested structures, missing fields, zero measurements, and timestamps.
        """
        now = time.time()
        now_dt = datetime.fromtimestamp(now, tz=timezone.utc)
        iso_timestamp = now_dt.strftime("%Y-%m-%d %H:%M:%S UTC")

        # Unwrap if raw_data is nested under 'current' or 'milk_monitor'
        flat_data = self._flatten_dict(raw_data)

        # Detect or assign timestamp
        timestamp_str = self._extract_timestamp(flat_data) or iso_timestamp

        normalized_sensors: Dict[str, Any] = {}
        sensor_evaluations: Dict[str, Any] = {}
        reporting_count = 0

        for key, defn in self.sensor_definitions.items():
            raw_val = self._resolve_field(flat_data, defn["aliases"])
            num_val = None
            is_reporting = False

            if raw_val is not None:
                try:
                    num_val = round(float(raw_val), defn["precision"])
                    is_reporting = True
                    reporting_count += 1
                except (ValueError, TypeError):
                    num_val = None

            # Calculate change delta
            delta = None
            delta_direction = "neutral"
            if num_val is not None and key in self.previous_readings:
                diff = round(num_val - self.previous_readings[key], defn["precision"])
                delta = diff
                if diff > 0:
                    delta_direction = "up"
                elif diff < 0:
                    delta_direction = "down"

            # Evaluate with quality service
            evaluation = self.quality_service.evaluate_sensor(key, num_val, is_stale=is_stale)
            sensor_evaluations[key] = evaluation

            # Sparkline trend from history
            sparkline = [
                h["sensors"][key]["value"]
                for h in self.history
                if "sensors" in h and key in h["sensors"] and h["sensors"][key]["value"] is not None
            ][-15:]

            normalized_sensors[key] = {
                "id": key,
                "name": defn["name"],
                "value": num_val,
                "formatted_value": f"{num_val:.{defn['precision']}f}" if num_val is not None else "--",
                "unit": defn["unit"],
                "icon": defn["icon"],
                "delta": delta,
                "delta_direction": delta_direction,
                "status": evaluation.get("status"),
                "badge_class": evaluation.get("badge_class"),
                "severity": evaluation.get("severity"),
                "explanation": evaluation.get("explanation"),
                "threshold_applied": evaluation.get("threshold_applied"),
                "is_reporting": is_reporting,
                "sparkline": sparkline
            }

            # Update previous reading memory if numeric
            if num_val is not None:
                self.previous_readings[key] = num_val

        # Overall milk quality synthesis
        overall_quality = self.quality_service.evaluate_overall(sensor_evaluations, is_connected=is_connected)

        result = {
            "timestamp": timestamp_str,
            "unix_timestamp": int(now),
            "is_stale": is_stale,
            "is_connected": is_connected,
            "sensors_configured": len(self.sensor_definitions),
            "sensors_reporting": reporting_count,
            "overall_status": overall_quality["status"],
            "overall_badge_class": overall_quality["badge_class"],
            "overall_color": overall_quality["color"],
            "overall_summary": overall_quality["summary"],
            "overall_disclaimer": overall_quality["disclaimer"],
            "sensors": normalized_sensors,
            "raw_payload": raw_data
        }

        self.latest_normalized = result

        # Record to history if at least one sensor is reporting valid data
        if reporting_count > 0:
            self._record_history_point(result)

        return result

    def _record_history_point(self, normalized_result: Dict[str, Any]):
        """Append point to history buffer if distinct or after interval."""
        point = {
            "timestamp": normalized_result["timestamp"],
            "unix_timestamp": normalized_result["unix_timestamp"],
            "overall_status": normalized_result["overall_status"],
            "sensors": {
                k: {
                    "value": s["value"],
                    "unit": s["unit"],
                    "status": s["status"]
                }
                for k, s in normalized_result["sensors"].items()
            }
        }
        
        # Avoid recording identical consecutive points within 3 seconds
        if self.history:
            last = self.history[-1]
            if (point["unix_timestamp"] - last["unix_timestamp"] < 3):
                # Update latest
                self.history[-1] = point
                return

        self.history.append(point)
        self._persist_history()

    def get_history(self, range_filter: str = "all", limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieve historical records filtered by time range.
        Ranges: '15m', '1h', '6h', '24h', '7d', 'all'
        """
        now = time.time()
        time_deltas = {
            "15m": 15 * 60,
            "1h": 3600,
            "6h": 6 * 3600,
            "24h": 24 * 3600,
            "7d": 7 * 86400,
            "all": None
        }

        max_age = time_deltas.get(range_filter)
        records = list(self.history)

        if max_age is not None:
            cutoff = now - max_age
            records = [r for r in records if r["unix_timestamp"] >= cutoff]

        return records[-limit:]

    def export_csv(self) -> str:
        """Generate CSV export string from recorded readings."""
        lines = ["Timestamp,Unix Timestamp,Temperature (°C),pH Level,Milk Volume (mL),Overall Status"]
        for record in self.history:
            sensors = record.get("sensors", {})
            t_val = sensors.get("temperature_C", {}).get("value", "")
            p_val = sensors.get("pH", {}).get("value", "")
            q_val = sensors.get("milk_quantity_ml", {}).get("value", "")
            status = record.get("overall_status", "")
            ts = record.get("timestamp", "")
            u_ts = record.get("unix_timestamp", "")
            lines.append(f'"{ts}",{u_ts},{t_val},{p_val},{q_val},"{status}"')
        return "\n".join(lines)

    def _flatten_dict(self, d: Any) -> Dict[str, Any]:
        """Flatten nested dictionary keys for resilient alias resolution."""
        flat = {}
        if not isinstance(d, dict):
            return flat
        
        for k, v in d.items():
            if isinstance(v, dict):
                # Include nested children directly if shallow
                flat.update(self._flatten_dict(v))
            flat[k] = v
        return flat

    def _resolve_field(self, data: Dict[str, Any], aliases: List[str]) -> Any:
        """Find value matching any alias."""
        for alias in aliases:
            if alias in data and data[alias] is not None:
                return data[alias]
        return None

    def _extract_timestamp(self, data: Dict[str, Any]) -> Optional[str]:
        """Extract and format timestamp from potential payload keys."""
        ts_keys = ["timestamp", "time", "date", "created_at", "updated_at", "ts"]
        for k in ts_keys:
            val = data.get(k)
            if val is not None:
                if isinstance(val, (int, float)):
                    # Check if milliseconds or seconds
                    if val > 1e11:
                        val = val / 1000.0
                    return datetime.fromtimestamp(val, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                elif isinstance(val, str) and len(val) >= 8:
                    return val
        return None
