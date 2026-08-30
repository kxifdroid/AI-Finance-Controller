"""
Pydantic schemas for the Finance Q&A Agent.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str # user, assistant, system
    content: str


class ChatRequest(BaseModel):
    message: str
    conversation_history: Optional[List[ChatMessage]] = Field(default_factory=list)


class ToolCallRecord(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]
    result_summary: str


class ChatResponse(BaseModel):
    answer: str
    tools_used: List[ToolCallRecord] = Field(default_factory=list)
    referenced_exceptions: List[str] = Field(default_factory=list)
    referenced_transactions: List[str] = Field(default_factory=list)
