import uuid
import re
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

# Local imports
from graph import app_graph
from db.database import upsert_user_stats, get_user_stats

router = APIRouter(prefix="/api", tags=["Chat & User Stats"])


class ChatRequest(BaseModel):
    user_id: str = "default_user"
    prompt: str
    thread_id: str | None = None  # Optional thread ID for session continuity


class UserStatsResponse(BaseModel):
    user_id: str
    curr_streak: int
    best_streak: int
    total_score: int
    total_attempts: int


@router.post("/chat")
def chat(request: ChatRequest):
    # 1. Generate or re-use session ID
    session_id = request.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": session_id}}

    # 2. Check if the prompt is an explicit answer submission
    is_answer = request.prompt.strip().startswith("/a")

    # 3. Retrieve persistent user stats from DB to hydrate state
    existing_stats = get_user_stats(request.user_id)

    # 4. Construct graph inputs
    inputs = {
        "messages": [HumanMessage(content=request.prompt)],
        "awaiting_eval": is_answer,
        "user_id": request.user_id,
        "user_stats": existing_stats,
    }

    # 5. Invoke LangGraph state graph
    result = app_graph.invoke(inputs, config=config)

    # 6. Extract results & latest stats state
    latest_message = result["messages"][-1]
    updated_stats = result.get("user_stats", existing_stats)

    # 7. Persist updated user stats to PostgreSQL
    upsert_user_stats(request.user_id, updated_stats)

    return {
        "thread_id": session_id,
        "user_id": request.user_id,
        "response": latest_message.content,
        "awaiting_eval": result.get("awaiting_eval", False),
        "options_list": result.get("options_list") or [],
        "user_stats": updated_stats,
        "message_count": len(result["messages"]),
    }


@router.get("/stats/{user_id}", response_model=UserStatsResponse)
def fetch_user_stats(user_id: str):
    """Retrieves current user streak & user stats metrics directly from DB."""
    stats = get_user_stats(user_id)
    return {"user_id": user_id, **stats}


@router.post("/stats/{user_id}/reset")
def reset_user_stats(user_id: str):
    """Resets user user stats back to 0 in DB."""
    zero_stats = {
        "curr_streak": 0,
        "best_streak": 0,
        "total_score": 0,
        "total_attempts": 0,
    }
    upsert_user_stats(user_id, zero_stats)
    return {"message": f"Stats for user '{user_id}' reset successfully."}
