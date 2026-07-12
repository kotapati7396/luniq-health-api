import json
import logging
from typing import Dict

from openai import OpenAI

from app.config import settings
from app.models.vitals import VitalsInput
from app.tools.vitals_rules import evaluate_vitals

logger = logging.getLogger(__name__)


def get_vitals_assessment(vitals: VitalsInput) -> Dict:
    # 1. Deterministic status - not decided by the LLM, so it can't be talked down.
    rule_result = evaluate_vitals(
        heart_rate=vitals.heart_rate,
        sys_bp=vitals.sys_bp,
        dia_bp=vitals.dia_bp,
        oxygen=vitals.oxygen,
        temperature=vitals.temperature,
        ecg=vitals.ecg,
    )

    fallback = {
        "status": rule_result["status"],
        "rule_based_flags": rule_result["flags"],
        "assessment_details": rule_result["flags"] or ["All readings are within a typical healthy range."],
        "recommendation": (
            "Please consult a doctor as soon as possible." if rule_result["status"] == "Critical"
            else "Please consider consulting a doctor if this continues." if rule_result["status"] == "Warning"
            else "No action needed - continue routine monitoring."
        ),
    }

    if not settings.OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set - returning rule-based assessment only")
        return fallback

    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        prompt = f"""
You are a medical assessment assistant for a health app. A deterministic rule engine has ALREADY decided
the status below from standard clinical thresholds. Do not change, soften, or downgrade this status -
you may only add context, or note if you see an additional concerning combination (in which case say so
in assessment_details, but still return the same status value given to you).

Rule-engine status: {rule_result['status']}
Rule-engine flags: {rule_result['flags']}

User details:
Name: {vitals.username}
Age: {vitals.age}
Heart rate: {vitals.heart_rate} bpm
Blood pressure: {vitals.sys_bp}/{vitals.dia_bp} mmHg
Oxygen: {vitals.oxygen}%
Temperature: {vitals.temperature}°C
ECG: {vitals.ecg}

Return ONLY valid JSON with this exact structure, nothing else:
{{
  "status": "{rule_result['status']}",
  "assessment_details": ["short explanation 1", "short explanation 2"],
  "recommendation": "short recommendation"
}}

Tone rules for "recommendation" and "assessment_details":
- Keep it calm and reassuring, never dramatic or frightening.
- Do NOT give step-by-step clinical instructions (e.g. "recheck with a validated cuff", "proceed to the
  nearest emergency department if the reading remains around X/Y"). That level of detail reads as alarming
  and is not this app's job.
- If status is "Critical", the recommendation should simply be a calm, clear version of: "Please consult
  a doctor as soon as possible." If status is "Warning", something like: "Please consider consulting a
  doctor if this continues."
- If any reading looks like it could be a typo or device error (implausible value), mention that plainly
  and calmly in assessment_details, without alarming language.
"""
        response = client.chat.completions.create(
            model=settings.MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
        )
        text = (response.choices[0].message.content or "").strip()
        parsed = json.loads(text)

        # Hard safety net: never allow the LLM to downgrade the rule-based status.
        status = str(parsed.get("status", rule_result["status"]))
        order = {"Normal": 0, "Warning": 1, "Critical": 2}
        if order.get(status, 0) < order[rule_result["status"]]:
            logger.warning("LLM tried to downgrade status from %s to %s - overriding", rule_result["status"], status)
            status = rule_result["status"]

        return {
            "status": status,
            "rule_based_flags": rule_result["flags"],
            "assessment_details": parsed.get("assessment_details", fallback["assessment_details"]),
            "recommendation": str(parsed.get("recommendation", fallback["recommendation"])),
        }
    except Exception:
        logger.exception("LLM narrative generation failed - falling back to rule-based assessment")
        return fallback
