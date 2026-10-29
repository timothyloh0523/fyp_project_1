import uuid
import re
import asyncio
from typing import Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage

# Local imports
from graph import app_graph
from db.database import (
    a_get_user_stats,
    a_upsert_user_stats,
    a_ensure_chat_session,
    a_record_message,
    a_ensure_user,
    a_get_user_profile,
    a_update_user_goals,
)

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
    weekly_score: int
    weekly_score_week: str | None

class UserGoalRequest(BaseModel):
    goal_type: Literal["weekly_score"]
    number: int = Field(ge=1)
    period: Literal["week"] = "week"
    enabled: bool = True

class UserProfileResponse(BaseModel):
    user_id: str
    display_name: str | None = None
    email: str | None = None
    goals: list[dict] = Field(default_factory=list)


@router.post("/chat")
async def chat(request: ChatRequest):
    # 1. Generate or re-use session ID
    session_id = request.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": session_id}}

    # 2. Check if the prompt is an explicit answer submission
    is_answer = request.prompt.strip().startswith("/a")

    # 3. Retrieve persistent user stats from DB to hydrate state
    await a_ensure_user(request.user_id)
    user_profile = await a_get_user_profile(request.user_id)
    existing_stats = await a_get_user_stats(request.user_id)
    await a_ensure_chat_session(session_id, request.user_id, "Linear Algebra")

    # 4. Construct graph inputs
    inputs = {
        "messages": [HumanMessage(content=request.prompt)],
        "awaiting_eval": is_answer,
        "user_id": request.user_id,
        "user_stats": existing_stats,
        "thread_id": session_id,
        "event_log": [],
        "user_goals": user_profile.get("goals", []),
    }

    # 5. Invoke LangGraph state graph
    result = await app_graph.ainvoke(inputs, config=config)

    # 6. Extract results & latest stats state
    latest_message = result["messages"][-1]
    tutor_message = latest_message if is_answer else result["messages"][-2]
    probe_message = None if is_answer else latest_message
    updated_stats = result.get("user_stats", existing_stats)

    # 7. Persist updated user stats to PostgreSQL
    if not is_answer:
        await a_upsert_user_stats(request.user_id, updated_stats)
    
    asyncio.create_task(a_record_message(
        session_id,
        len(result["messages"]) - 1,
        "human",
        request.prompt,
        "evaluate" if is_answer else "tutor",
    ))
    asyncio.create_task(a_record_message(
        session_id,
        len(result["messages"]),
        "ai" if latest_message.type == "ai" else "human",
        latest_message.content,
        "evaluate" if is_answer else "prober",
    ))

    return {
        "thread_id": session_id,
        "user_id": request.user_id,
        "response": latest_message.content,
        "tutor_response": tutor_message.content,
        "probe_question": probe_message.content if probe_message else None,
        "awaiting_eval": result.get("awaiting_eval", False),
        "options_list": [
            {"label": item.get("label", item["option"]), "option": item["option"]}
            for item in (result.get("options_list") or [])
        ] if not is_answer else [],
        "user_stats": updated_stats,
        "score": result.get("score"),
        "weekly_score": updated_stats.get("weekly_score", 0),
        "message_count": len(result["messages"]),
    }


@router.get("/stats/{user_id}", response_model=UserStatsResponse)
async def fetch_user_stats(user_id: str):
    """Retrieves current user streak & user stats metrics directly from DB."""
    stats = await a_get_user_stats(user_id)
    return {"user_id": user_id, **stats}

@router.get("/users/{user_id}", response_model=UserProfileResponse)
async def fetch_user_profile(user_id: str):
    await a_ensure_user(user_id)
    return await a_get_user_profile(user_id)

@router.put("/users/{user_id}/goals", response_model=UserProfileResponse)
async def update_user_goals(user_id: str, goals: list[UserGoalRequest]):
    saved_goals = [goal.model_dump() for goal in goals]
    return await a_update_user_goals(user_id, saved_goals)


@router.post("/stats/{user_id}/reset")
async def reset_user_stats(user_id: str):
    """Resets user user stats back to 0 in DB."""
    zero_stats = {
        "curr_streak": 0,
        "best_streak": 0,
        "total_score": 0,
        "total_attempts": 0,
        "weekly_score": 0,
        "weekly_score_week": None,
    }
    await a_upsert_user_stats(user_id, zero_stats)
    return {"message": f"Stats for user '{user_id}' reset successfully."}
