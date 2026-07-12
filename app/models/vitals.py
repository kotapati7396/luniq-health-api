from pydantic import BaseModel, Field
from typing import List, Dict, Any


class VitalsInput(BaseModel):
    username: str = Field(..., description="User's full name", examples=["John Doe"])
    mobile_number: str = Field(..., description="User's mobile number (conversation key)", examples=["9876543210"])
    age: int = Field(..., description="User's age", examples=[30])
    heart_rate: int = Field(..., description="Heart rate in beats per minute (bpm)", examples=[72])
    sys_bp: int = Field(..., description="Systolic Blood Pressure (mmHg)", examples=[120])
    dia_bp: int = Field(..., description="Diastolic Blood Pressure (mmHg)", examples=[80])
    oxygen: int = Field(..., description="Blood Oxygen level (% SpO2)", examples=[98])
    temperature: float = Field(..., description="Body temperature in Celsius (°C)", examples=[37.1])
    ecg: str = Field(..., description="ECG reading status (e.g. 'Normal', 'Abnormal')", examples=["Normal"])


class AssessmentResponse(BaseModel):
    username: str
    mobile_number: str
    age: int
    status: str  # "Normal", "Warning", "Critical" - decided by the deterministic rule engine
    rule_based_flags: List[str]  # which specific readings triggered the status
    vitals_summary: Dict[str, Any]
    assessment_details: List[str]
    recommendation: str
