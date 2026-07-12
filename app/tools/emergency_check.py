import re
from typing import Any, Dict, List

# Deliberately simple, transparent, and easy to extend - a keyword/phrase
# red-flag list is safer here than relying purely on model judgement, because
# it can't be "talked out of" flagging a genuine emergency.
_RED_FLAGS: List[str] = [
    r"difficulty breathing", r"can'?t breathe", r"shortness of breath", r"breathless",
    r"chest pain", r"tight(?:ness)? in (?:my|the) chest",
    r"blue lips", r"turning blue",
    r"severe allerg", r"anaphylax", r"swelling of (?:the )?(?:face|throat|tongue)",
    r"unconscious", r"fainted", r"passed out", r"unresponsive",
    r"seizure", r"convulsion",
    r"severe bleeding", r"won'?t stop bleeding", r"heavy bleeding",
    r"slurred speech", r"one[- ]sided weakness", r"face droop", r"sudden numbness",
    r"suicidal", r"want to die", r"end my life", r"self[- ]harm",
    r"very high fever", r"104\s*f", r"40(\.\d)?\s*(?:c|celsius|°c)",
    r"stiff neck", r"severe headache.*worst",
    r"poisoning", r"overdose",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in _RED_FLAGS]


TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "check_emergency_symptoms",
        "description": (
            "Check free-text symptom description against a red-flag emergency list. "
            "ALWAYS call this once per user message that mentions symptoms, before giving care advice."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "symptoms_text": {
                    "type": "string",
                    "description": "The user's message or symptom description to screen for emergency red flags.",
                }
            },
            "required": ["symptoms_text"],
        },
    },
}


def check_emergency_symptoms(symptoms_text: str) -> Dict[str, Any]:
    matched = [p.pattern for p in _COMPILED if p.search(symptoms_text)]
    return {
        "is_emergency": len(matched) > 0,
        "matched_flags_count": len(matched),
        "instruction": (
            "This message contains possible emergency red flags. You MUST clearly tell the user "
            "to seek immediate medical care / call emergency services, before anything else."
            if matched
            else "No emergency red flags detected in this message."
        ),
    }
