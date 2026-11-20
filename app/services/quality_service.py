"""
Nutri Milk Guard - Quality Assessment Service.
Evaluates sensor readings against scientific dairy quality thresholds.
Does not make unverified claims; provides transparent, rule-based classifications
referencing configured standards and sensor calibration notes.
"""

from typing import Dict, Any, Optional, Tuple


class QualityStatus:
    NORMAL = "Normal"
    WARNING = "Warning"
    CRITICAL = "Critical"
    OFFLINE = "Sensor offline"
    INSUFFICIENT_DATA = "Insufficient data"
    NOT_CONFIGURED = "Thresholds not configured"


# Default reference thresholds based on standard bovine milk science (e.g., FSSAI / FAO guidelines)
# These defaults can be customized via the settings page without modifying the ESP32.
DEFAULT_THRESHOLDS = {
    "temperature_C": {
        "unit": "°C",
        "description": "Milk Temperature (°C)",
        "optimal_min": 0.0,
        "optimal_max": 10.0,      # Chilled bulk milk optimal storage (ideally <= 4°C, collection <= 10°C)
        "warning_max": 25.0,      # Ambient collection/testing temperature
        "critical_max": 35.0,     # High-risk microbial multiplication zone (> 35°C accelerates spoiling)
        "critical_min": -0.5,     # Freezing point of milk (~ -0.52°C); freezing breaks the milk fat emulsion
        "standards_ref": "FAO / FSSAI Cold Chain Standards: Raw milk chilled <= 4°C, collection max 10°C"
    },
    "pH": {
        "unit": "pH",
        "description": "Milk pH Scale",
        "optimal_min": 6.50,      # Fresh cow milk typical pH: 6.5 - 6.7 at 20-25°C
        "optimal_max": 6.80,
        "warning_low": 6.20,      # Souring begins (lactic acid fermentation)
        "critical_low": 5.90,     # High acidity / Curdling / Protein coagulation
        "warning_high": 7.00,     # Slight alkalinity (mastitis or dilution)
        "critical_high": 7.30,    # High alkalinity (subclinical mastitis, detergent residue, or neutralization)
        "standards_ref": "Standard Bovine Dairy Science: Fresh milk pH 6.50-6.80 at 25°C; pH < 6.2 indicates souring"
    },
    "milk_quantity_ml": {
        "unit": "mL",
        "description": "Milk Volume (mL)",
        "optimal_min": 50.0,
        "optimal_max": 5000.0,
        "warning_low": 20.0,
        "critical_low": 0.0,
        "standards_ref": "Container volume sensor"
    }
}


class QualityService:
    """
    Evaluates individual sensor values and overall milk quality condition.
    """

    def __init__(self, thresholds: Optional[Dict[str, Any]] = None):
        self.thresholds = thresholds or DEFAULT_THRESHOLDS

    def update_thresholds(self, new_thresholds: Dict[str, Any]):
        """Update active thresholds dynamically."""
        self.thresholds.update(new_thresholds)

    def evaluate_sensor(self, sensor_key: str, value: Any, is_stale: bool = False) -> Dict[str, Any]:
        """
        Evaluate an individual sensor reading.
        Returns a structured dictionary with status, explanation, and thresholds applied.
        """
        config = self.thresholds.get(sensor_key)
        
        # If no thresholds configured for this key
        if not config:
            return {
                "status": QualityStatus.NOT_CONFIGURED,
                "badge_class": "badge-secondary",
                "explanation": f"No evaluation thresholds defined for '{sensor_key}'.",
                "threshold_applied": "None",
                "severity": "info"
            }

        # If data is stale or connection lost
        if is_stale:
            return {
                "status": QualityStatus.OFFLINE,
                "badge_class": "badge-offline",
                "explanation": "No recent reading received from ESP32 within configured timeout.",
                "threshold_applied": f"Stale timeout exceeded",
                "severity": "warning"
            }

        # Handle null, invalid, or non-numeric readings
        if value is None:
            return {
                "status": QualityStatus.INSUFFICIENT_DATA,
                "badge_class": "badge-insufficient",
                "explanation": f"Sensor '{sensor_key}' is reporting null/empty value.",
                "threshold_applied": "N/A",
                "severity": "warning"
            }

        try:
            num_val = float(value)
        except (ValueError, TypeError):
            return {
                "status": QualityStatus.INSUFFICIENT_DATA,
                "badge_class": "badge-insufficient",
                "explanation": f"Non-numeric value '{value}' received for '{sensor_key}'.",
                "threshold_applied": "Numeric type required",
                "severity": "warning"
            }

        # Specific evaluation for pH
        if sensor_key == "pH":
            return self._evaluate_ph(num_val, config)

        # Specific evaluation for Temperature
        if sensor_key in ("temperature_C", "temperature", "temp"):
            return self._evaluate_temperature(num_val, config)

        # Generic numeric sensor evaluation
        return self._evaluate_generic(sensor_key, num_val, config)

    def _evaluate_ph(self, val: float, cfg: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate milk pH against dairy standards."""
        crit_low = cfg.get("critical_low", 5.90)
        warn_low = cfg.get("warning_low", 6.20)
        opt_min = cfg.get("optimal_min", 6.50)
        opt_max = cfg.get("optimal_max", 6.80)
        warn_high = cfg.get("warning_high", 7.00)
        crit_high = cfg.get("critical_high", 7.30)
        ref = cfg.get("standards_ref", "Bovine milk pH standards")

        if val < crit_low:
            return {
                "status": QualityStatus.CRITICAL,
                "badge_class": "badge-critical",
                "explanation": (
                    f"pH {val:.2f} is severely acidic (< {crit_low:.2f}). "
                    f"Indicates active bacterial acidification and curdling."
                ),
                "threshold_applied": f"Critical Low: < {crit_low:.2f} pH (Normal: {opt_min:.2f}-{opt_max:.2f})",
                "severity": "critical",
                "reference": ref
            }
        elif val < warn_low:
            return {
                "status": QualityStatus.WARNING,
                "badge_class": "badge-warning",
                "explanation": (
                    f"pH {val:.2f} is mildly acidic (< {warn_low:.2f}). "
                    f"Lactic acid development detected; milk freshness declining."
                ),
                "threshold_applied": f"Warning Low: < {warn_low:.2f} pH (Normal: {opt_min:.2f}-{opt_max:.2f})",
                "severity": "warning",
                "reference": ref
            }
        elif val > crit_high:
            return {
                "status": QualityStatus.CRITICAL,
                "badge_class": "badge-critical",
                "explanation": (
                    f"pH {val:.2f} is abnormally alkaline (> {crit_high:.2f}). "
                    f"Potential mastitic milk, alkaline adulteration, or sensor offset."
                ),
                "threshold_applied": f"Critical High: > {crit_high:.2f} pH",
                "severity": "critical",
                "reference": ref
            }
        elif val > warn_high:
            return {
                "status": QualityStatus.WARNING,
                "badge_class": "badge-warning",
                "explanation": (
                    f"pH {val:.2f} is above standard range (> {warn_high:.2f}). "
                    f"Monitor for udder health or chemical contamination."
                ),
                "threshold_applied": f"Warning High: > {warn_high:.2f} pH",
                "severity": "warning",
                "reference": ref
            }
        elif opt_min <= val <= opt_max:
            return {
                "status": QualityStatus.NORMAL,
                "badge_class": "badge-normal",
                "explanation": (
                    f"pH {val:.2f} is within standard bovine fresh milk range ({opt_min:.2f} - {opt_max:.2f})."
                ),
                "threshold_applied": f"Normal: {opt_min:.2f} - {opt_max:.2f} pH",
                "severity": "normal",
                "reference": ref
            }
        else:
            # Slight drift between warn_low and opt_min or opt_max and warn_high
            return {
                "status": QualityStatus.WARNING,
                "badge_class": "badge-warning",
                "explanation": f"pH {val:.2f} is slightly outside optimal range ({opt_min:.2f}-{opt_max:.2f}).",
                "threshold_applied": f"Acceptable boundary drift: {opt_min:.2f} - {opt_max:.2f}",
                "severity": "warning",
                "reference": ref
            }

    def _evaluate_temperature(self, val: float, cfg: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate milk temperature against cold-chain and storage standards."""
        crit_max = cfg.get("critical_max", 35.0)
        warn_max = cfg.get("warning_max", 25.0)
        opt_max = cfg.get("optimal_max", 10.0)
        crit_min = cfg.get("critical_min", -0.5)
        ref = cfg.get("standards_ref", "Dairy cold-chain standards")

        if val < crit_min:
            return {
                "status": QualityStatus.CRITICAL,
                "badge_class": "badge-critical",
                "explanation": f"Temperature {val:.1f}°C is below freezing point (< {crit_min:.1f}°C). Emulsion breakdown risk.",
                "threshold_applied": f"Critical Min: < {crit_min:.1f}°C",
                "severity": "critical",
                "reference": ref
            }
        elif val > crit_max:
            return {
                "status": QualityStatus.CRITICAL,
                "badge_class": "badge-critical",
                "explanation": (
                    f"Temperature {val:.1f}°C is dangerously high (> {crit_max:.1f}°C). "
                    f"Accelerates rapid bacterial multiplication and spoilage."
                ),
                "threshold_applied": f"Critical Max: > {crit_max:.1f}°C (Safe target: <= {opt_max:.1f}°C)",
                "severity": "critical",
                "reference": ref
            }
        elif val > warn_max:
            return {
                "status": QualityStatus.WARNING,
                "badge_class": "badge-warning",
                "explanation": (
                    f"Temperature {val:.1f}°C exceeds ambient room threshold (> {warn_max:.1f}°C). "
                    f"Milk requires prompt refrigeration to prevent quality degradation."
                ),
                "threshold_applied": f"Warning Max: > {warn_max:.1f}°C (Ideal: <= {opt_max:.1f}°C)",
                "severity": "warning",
                "reference": ref
            }
        elif val > opt_max:
            return {
                "status": QualityStatus.NORMAL,
                "badge_class": "badge-normal",
                "explanation": (
                    f"Temperature {val:.1f}°C is acceptable for immediate fresh farm collection/intake. "
                    f"Cooling to <= {opt_max:.1f}°C recommended for storage."
                ),
                "threshold_applied": f"Ambient Collection Target: <= {warn_max:.1f}°C",
                "severity": "normal",
                "reference": ref
            }
        else:
            return {
                "status": QualityStatus.NORMAL,
                "badge_class": "badge-normal",
                "explanation": f"Temperature {val:.1f}°C meets chilled storage standards (<= {opt_max:.1f}°C).",
                "threshold_applied": f"Optimal Chilled: <= {opt_max:.1f}°C",
                "severity": "normal",
                "reference": ref
            }

    def _evaluate_generic(self, key: str, val: float, cfg: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate non-standard sensor values."""
        crit_max = cfg.get("critical_max")
        crit_min = cfg.get("critical_min")
        warn_max = cfg.get("warning_max")
        warn_min = cfg.get("warning_min")
        unit = cfg.get("unit", "")

        if crit_max is not None and val > crit_max:
            return {
                "status": QualityStatus.CRITICAL,
                "badge_class": "badge-critical",
                "explanation": f"Value {val} {unit} exceeds critical maximum ({crit_max} {unit}).",
                "threshold_applied": f"> {crit_max} {unit}",
                "severity": "critical"
            }
        if crit_min is not None and val < crit_min:
            return {
                "status": QualityStatus.CRITICAL,
                "badge_class": "badge-critical",
                "explanation": f"Value {val} {unit} is below critical minimum ({crit_min} {unit}).",
                "threshold_applied": f"< {crit_min} {unit}",
                "severity": "critical"
            }
        if warn_max is not None and val > warn_max:
            return {
                "status": QualityStatus.WARNING,
                "badge_class": "badge-warning",
                "explanation": f"Value {val} {unit} exceeds warning threshold ({warn_max} {unit}).",
                "threshold_applied": f"> {warn_max} {unit}",
                "severity": "warning"
            }
        if warn_min is not None and val < warn_min:
            return {
                "status": QualityStatus.WARNING,
                "badge_class": "badge-warning",
                "explanation": f"Value {val} {unit} is below warning threshold ({warn_min} {unit}).",
                "threshold_applied": f"< {warn_min} {unit}",
                "severity": "warning"
            }

        return {
            "status": QualityStatus.NORMAL,
            "badge_class": "badge-normal",
            "explanation": f"Reading {val} {unit} is within normal parameters.",
            "threshold_applied": "Within configured operational range",
            "severity": "normal"
        }

    def evaluate_overall(self, sensor_evaluations: Dict[str, Dict[str, Any]], is_connected: bool) -> Dict[str, Any]:
        """
        Synthesize overall milk quality status from all reporting sensors.
        Transparently informs that quality status relies on sensor calibration.
        """
        if not is_connected:
            return {
                "status": QualityStatus.OFFLINE,
                "badge_class": "badge-offline",
                "color": "#64748B",
                "summary": "Monitoring system disconnected from Firebase.",
                "disclaimer": "Live data stream interrupted. Check ESP32 power and WiFi connection."
            }

        if not sensor_evaluations:
            return {
                "status": QualityStatus.INSUFFICIENT_DATA,
                "badge_class": "badge-insufficient",
                "color": "#94A3B8",
                "summary": "No sensor readings available for evaluation.",
                "disclaimer": "Waiting for ESP32 payload."
            }

        statuses = [ev.get("status") for ev in sensor_evaluations.values()]

        if QualityStatus.CRITICAL in statuses:
            critical_sensors = [k for k, ev in sensor_evaluations.items() if ev.get("status") == QualityStatus.CRITICAL]
            return {
                "status": QualityStatus.CRITICAL,
                "badge_class": "badge-critical",
                "color": "#DC2626",
                "summary": f"Critical alert on {', '.join(critical_sensors)}. Immediate inspection required.",
                "disclaimer": "Note: Milk classification is rule-based according to configured dairy thresholds. Consult laboratory testing for final food safety verification."
            }
        elif QualityStatus.WARNING in statuses:
            warning_sensors = [k for k, ev in sensor_evaluations.items() if ev.get("status") == QualityStatus.WARNING]
            return {
                "status": QualityStatus.WARNING,
                "badge_class": "badge-warning",
                "color": "#D97706",
                "summary": f"Warning condition detected on {', '.join(warning_sensors)}.",
                "disclaimer": "Note: Milk quality classification is based on configured thresholds. Ensure sensors are properly calibrated."
            }
        elif all(s == QualityStatus.NORMAL for s in statuses):
            return {
                "status": QualityStatus.NORMAL,
                "badge_class": "badge-normal",
                "color": "#16A34A",
                "summary": "All active sensors within configured normal parameters.",
                "disclaimer": "Normal readings indicate compliance with configured sensor thresholds. Regular physical testing is advised."
            }
        else:
            return {
                "status": QualityStatus.INSUFFICIENT_DATA,
                "badge_class": "badge-insufficient",
                "color": "#64748B",
                "summary": "Partial or unclassified sensor readings.",
                "disclaimer": "Verify sensor connections and threshold settings."
            }
