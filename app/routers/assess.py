import logging

from fastapi import APIRouter, Depends, HTTPException

from app.agents.vitals_agent import get_vitals_assessment
from app.core.rate_limit import check_rate_limit
from app.core.security import verify_api_key
from app.models.vitals import AssessmentResponse, VitalsInput

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assess", tags=["Health Assessment"])


@router.post("", response_model=AssessmentResponse)
def assess_vitals(vitals: VitalsInput, _auth: None = Depends(verify_api_key)):
    check_rate_limit(vitals.mobile_number)

    try:
        result = get_vitals_assessment(vitals)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Vitals assessment failed")
        raise HTTPException(status_code=500, detail=f"AI assessment failed: {exc}")

    return AssessmentResponse(
        username=vitals.username,
        mobile_number=vitals.mobile_number,
        age=vitals.age,
        status=result["status"],
        rule_based_flags=result["rule_based_flags"],
        vitals_summary={
            "heart_rate_bpm": vitals.heart_rate,
            "blood_pressure": f"{vitals.sys_bp}/{vitals.dia_bp}",
            "oxygen_saturation_pct": vitals.oxygen,
            "temperature_c": vitals.temperature,
            "ecg_status": vitals.ecg,
        },
        assessment_details=result["assessment_details"],
        recommendation=result["recommendation"],
    )
