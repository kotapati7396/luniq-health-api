import logging

from fastapi import APIRouter, Depends, HTTPException

from app.agents.chat_agent import get_chat_reply
from app.core.rate_limit import check_rate_limit
from app.core.security import verify_api_key
from app.db import memory_store
from app.models.chat import ChatInput, ChatResponse, HistoryResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chatbot"])


@router.post("", response_model=ChatResponse)
def chat(payload: ChatInput, _auth: None = Depends(verify_api_key)):
    check_rate_limit(payload.mobile_number)

    try:
        history = memory_store.get_history(payload.mobile_number)
        reply, tools_used = get_chat_reply(
            username=payload.username,
            age=payload.age,
            history=history,
            query=payload.query,
        )
        memory_store.add_turn(payload.mobile_number, payload.query, reply)
        updated_history = memory_store.get_history(payload.mobile_number)
    except RuntimeError as exc:
        # e.g. missing OPENAI_API_KEY - a config problem, not a user error
        logger.error("Chat config error: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.exception("Chatbot failed")
        raise HTTPException(
            status_code=500,
            detail=(
                "We're currently experiencing a temporary issue with our AI service. "
                "Please try again later. If the issue continues, contact our support "
                "team for assistance. We apologize for the inconvenience."
            ),
        )

    return ChatResponse(
        mobile_number=payload.mobile_number,
        reply=reply,
        tools_used=tools_used,
        history=updated_history,
    )


@router.get("/history/{mobile_number}", response_model=HistoryResponse)
def get_chat_history(mobile_number: str, _auth: None = Depends(verify_api_key)):
    return HistoryResponse(mobile_number=mobile_number, history=memory_store.get_history(mobile_number))


@router.delete("/history/{mobile_number}")
def delete_chat_history(mobile_number: str, _auth: None = Depends(verify_api_key)):
    memory_store.clear_history(mobile_number)
    return {"mobile_number": mobile_number, "cleared": True}
