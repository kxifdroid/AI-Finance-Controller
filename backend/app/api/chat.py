"""
Finance Q&A Chat API Routes.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.chat import ChatRequest, ChatResponse
from app.agents.finance_qa_agent import FinanceQAAgent

router = APIRouter(prefix="/finance", tags=["Finance Q&A"])


@router.post("/chat", response_model=ChatResponse)
async def chat_with_finance_agent(
    payload: ChatRequest,
    db: Session = Depends(get_db),
):
    """
    Submits a natural language query to the Finance Q&A Agent.
    The agent executes structured database tools to ground its response without hallucinations.
    """
    agent = FinanceQAAgent()
    try:
        response = await agent.answer_query(db=db, user_message=payload.message)
        return ChatResponse(
            answer=response.get("answer", ""),
            thought_process=response.get("thought_process", []),
            tools_used=response.get("tools_used", []),
            referenced_exceptions=response.get("referenced_exceptions", []),
            referenced_transactions=response.get("referenced_transactions", []),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Finance Q&A query failed: {str(e)}")
