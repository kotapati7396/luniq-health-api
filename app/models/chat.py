from pydantic import BaseModel, Field
from typing import List, Dict


class ChatInput(BaseModel):
    username: str = Field(..., description="User's full name", examples=["John Doe"])
    mobile_number: str = Field(..., description="User's mobile number (used as the conversation key)", examples=["9876543210"])
    age: int = Field(..., description="User's age", examples=[30])
    query: str = Field(..., min_length=1, description="The user's question for the chatbot", examples=["Can I take Dolo 650 for fever?"])


class ChatResponse(BaseModel):
    mobile_number: str
    reply: str
    tools_used: List[str]  # which agent tools were invoked to build this reply (transparency/debugging)
    history: List[Dict[str, str]]  # last up-to-N turns returned for transparency/debugging


class HistoryResponse(BaseModel):
    mobile_number: str
    history: List[Dict[str, str]]
