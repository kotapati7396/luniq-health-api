"""
Deterministic, rule-based status engine for vitals.

Why: an LLM can be inconsistent or persuadable about how serious a reading is.
For a health app, the actual Normal/Warning/Critical decision should come from
fixed, auditable clinical thresholds. The LLM's job is only to explain the
result in plain language and suggest next steps - it is explicitly instructed
(in the agent prompt) never to downgrade this status.

These are general population thresholds for a POC and are NOT a substitute
for clinician-defined ranges (e.g. athletes, known chronic conditions, etc.
have different normals) - that caveat is included in the response.
"""
from typing import Any, Dict, List, Tuple

STATUS_ORDER = {"Normal": 0, "Warning": 1, "Critical": 2}


def _worse(a: str, b: str) -> str:
    return a if STATUS_ORDER[a] >= STATUS_ORDER[b] else b


def _heart_rate_status(hr: int) -> Tuple[str, str]:
    if hr < 40 or hr > 150:
        return "Critical", f"Heart rate {hr} bpm is far outside the safe range."
    if hr < 50 or hr > 120:
        return "Warning", f"Heart rate {hr} bpm is outside the typical resting range."
    return "Normal", f"Heart rate {hr} bpm is within a typical resting range."


def _oxygen_status(spo2: int) -> Tuple[str, str]:
    if spo2 < 90:
        return "Critical", f"Oxygen saturation {spo2}% is dangerously low."
    if spo2 < 95:
        return "Warning", f"Oxygen saturation {spo2}% is below the typical healthy range."
    return "Normal", f"Oxygen saturation {spo2}% is within a healthy range."


def _bp_status(sys_bp: int, dia_bp: int) -> Tuple[str, str]:
    if sys_bp < 90 or sys_bp > 180 or dia_bp < 60 or dia_bp > 120:
        return "Critical", f"Blood pressure {sys_bp}/{dia_bp} mmHg is at a critical level."
    if sys_bp < 100 or sys_bp >= 140 or dia_bp < 65 or dia_bp >= 90:
        return "Warning", f"Blood pressure {sys_bp}/{dia_bp} mmHg is outside the typical healthy range."
    return "Normal", f"Blood pressure {sys_bp}/{dia_bp} mmHg is within a typical healthy range."


def _temperature_status(temp_c: float) -> Tuple[str, str]:
    if temp_c < 35.0 or temp_c >= 39.5:
        return "Critical", f"Temperature {temp_c}°C indicates possible hypothermia or a very high fever."
    if temp_c >= 38.0:
        return "Warning", f"Temperature {temp_c}°C indicates a fever."
    return "Normal", f"Temperature {temp_c}°C is within a typical range."


def _ecg_status(ecg: str) -> Tuple[str, str]:
    if "abnormal" in ecg.strip().lower():
        return "Warning", "ECG reading is flagged as abnormal."
    return "Normal", "ECG reading is normal."


def evaluate_vitals(
    heart_rate: int, sys_bp: int, dia_bp: int, oxygen: int, temperature: float, ecg: str
) -> Dict[str, Any]:
    checks = [
        _heart_rate_status(heart_rate),
        _oxygen_status(oxygen),
        _bp_status(sys_bp, dia_bp),
        _temperature_status(temperature),
        _ecg_status(ecg),
    ]

    overall = "Normal"
    flags: List[str] = []
    for status, explanation in checks:
        overall = _worse(overall, status)
        if status != "Normal":
            flags.append(explanation)

    return {
        "status": overall,
        "flags": flags,
        "note": (
            "These are general-population thresholds for a proof-of-concept and do not "
            "replace clinician-defined normal ranges for a specific individual."
        ),
    }
