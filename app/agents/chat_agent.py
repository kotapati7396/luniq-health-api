import json
import logging
from typing import Dict, List, Tuple

from openai import OpenAI

from app.config import settings
from app.tools.emergency_check import TOOL_SCHEMA as EMERGENCY_TOOL, check_emergency_symptoms

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are LUNIQ Health Assistant, a friendly health-information chatbot inside a health app.

You help users with:
- General questions about common OTC (over-the-counter) medicines (e.g. paracetamol/Dolo, ORS, antacids, cough syrup)
- Simple food/diet precautions related to their symptoms
- Suggesting a sensible next step (e.g. rest and monitor, see a doctor, go to the ER)

Read the user's actual message and answer it directly and specifically - don't give a generic canned
answer. Base your answer on what they actually asked (the medicine they named, the symptom they
described, their age/context given to you).

Tools available to you:
- check_emergency_symptoms: call this for any message describing symptoms, before giving advice.
  If it reports an emergency, your reply MUST lead with telling the user to seek immediate medical
  care / call emergency services.

How to answer medicine questions:
- Give the STANDARD label/package guidance for that medicine (typical adult/child dose range, usual
  max doses per day, minimum gap between doses), clearly stated as standard/label guidance - not a
  personal prescription.
- Always tell the user to confirm the exact dose against the product label or a pharmacist/doctor,
  especially for children, elderly, pregnant/breastfeeding users, or anyone with existing conditions
  or other medications.
- Never invent a dose you're not confident about. If you're not sure of the standard dosing for a
  medicine, say so plainly and recommend asking a pharmacist instead of guessing.

Style:
- Be clear, short, and reassuring. Use simple language.
- Structure longer answers with: (1) direct answer, (2) food/care precautions if relevant,
  (3) suggested next step.
- You are not a doctor and cannot diagnose. Make that clear when the question goes beyond simple OTC
  guidance.
"""

TOOLS = [EMERGENCY_TOOL]

_TOOL_IMPL = {
    "check_emergency_symptoms": lambda args: check_emergency_symptoms(**args),
}

MAX_TOOL_ITERATIONS = 4


def _build_messages(username: str, age: int, history: List[Dict[str, str]], query: str) -> List[dict]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.append({
        "role": "system",
        "content": f"User context -> name: {username}, age: {age}. Use the age when it matters for dosing.",
    })
    messages.extend(history)
    messages.append({"role": "user", "content": query})
    return messages


def get_chat_reply(username: str, age: int, history: List[Dict[str, str]], query: str) -> Tuple[str, List[str]]:
    """Returns (reply_text, list_of_tool_names_used). The reply is generated directly
    from the user's input by the model - no hardcoded reference table is involved."""
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set. Please set it before calling the chatbot.")

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    messages = _build_messages(username, age, history, query)
    tools_used: List[str] = []

    for _ in range(MAX_TOOL_ITERATIONS):
        response = client.chat.completions.create(
            model=settings.MODEL_NAME,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )
        msg = response.choices[0].message

        if not msg.tool_calls:
            reply = (msg.content or "").strip()
            if not reply:
                reply = "Sorry, I couldn't generate a response right now. Please try again or consult a pharmacist/doctor."
            return reply, tools_used

        messages.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ],
        })

        for tc in msg.tool_calls:
            fn_name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
                result = _TOOL_IMPL[fn_name](args) if fn_name in _TOOL_IMPL else {"error": f"unknown tool {fn_name}"}
            except Exception as exc:  # noqa: BLE001
                logger.exception("Tool execution failed: %s", fn_name)
                result = {"error": str(exc)}

            tools_used.append(fn_name)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result),
            })

    logger.warning("Chat agent hit MAX_TOOL_ITERATIONS without a final answer")
    return (
        "Sorry, I'm having trouble putting together a reliable answer right now. "
        "Please try again, or consult a pharmacist/doctor for anything urgent.",
        tools_used,
    )
