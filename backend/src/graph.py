from typing import TypedDict, Sequence, Annotated, Optional
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, SystemMessage

import re

from coinflip import flip_coin
from prompts import answer_with_follow_up_prompt, base_prompt, evaluation_prompt
from state import AgentState, UserStats

load_dotenv()

TOPIC = "Linear Algebra"

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

def tutor_node(state: AgentState) -> dict:
    # MODE 1 - Uncomment out following lines to enable randomisation of whether to ask a probing question or not
    # coin_result = flip_coin()
    # if coin_result == "heads":
    #     system_content = base_prompt(TOPIC)
    #     awaiting_eval = False
    # else:
    #     system_content = answer_with_follow_up_prompt(TOPIC)
    #     awaiting_eval = True

    # MODE 2 - Uncomment out the following lines to always ask a probing question after the answer
    system_content = answer_with_follow_up_prompt(TOPIC)
    awaiting_eval = True
        
    system_prompt = SystemMessage(content=system_content)
    full_messages = [system_prompt] + list(state["messages"])
    response = llm.invoke(full_messages)

    # Get user_stats, initialise if not present
    current_board = state.get("user_stats") or {
        "curr_streak": 0,
        "best_streak": 0,
        "total_score": 0,
        "total_attempts": 0,
    }
    
    return {
        "messages": [response],
        "awaiting_eval": awaiting_eval,
        # "coin_result": coin_result # Toggle to this line if using randomisation mode
        "coin_result": "tails",
        "user_stats": current_board
    }

def evaluate_node(state: AgentState) -> dict:
    system_prompt = SystemMessage(content=evaluation_prompt(TOPIC))
    full_messages = [system_prompt] + list(state["messages"])
    response = llm.invoke(full_messages)
    
    # Parse binary score (0 or 1) from response (e.g., "Score: 1" or "Score: 1/1")
    score_match = re.search(r"Score:\s*([01])(?:/1)?", response.content, re.IGNORECASE)
    score = int(score_match.group(1)) if score_match else 0  # Fallback to 0 if unparsed

    # Retrieve current user_stats metrics
    board = state.get("user_stats") or {
        "curr_streak": 0,
        "best_streak": 0,
        "total_score": 0,
        "total_attempts": 0,
    }

    # Update attempt & total score
    total_attempts = board["total_attempts"] + 1
    total_score = board["total_score"] + score

    # Binary logic: Score 1 increments streak, Score 0 resets streak
    if score == 1:
        curr_streak = board["curr_streak"] + 1
        best_streak = max(board["best_streak"], curr_streak)
    else:
        curr_streak = 0  # Score 0 resets streak
        best_streak = board["best_streak"]

    updated_board: user_stats = {
        "curr_streak": curr_streak,
        "best_streak": best_streak,
        "total_score": total_score,
        "total_attempts": total_attempts,
    }

    return {
        "messages": [response],
        "awaiting_eval": False,
        "score": score,
        "user_stats": updated_board,
    }

def route_tutor(state: AgentState) -> str:
    if state.get("awaiting_eval"):
        return "evaluate"
    return "tutor"

workflow = StateGraph(AgentState)
workflow.add_node("tutor", tutor_node)
workflow.add_node("evaluate", evaluate_node)

# Entry point routes directly to evaluate if waiting for user's test answer
workflow.set_conditional_entry_point(
    route_tutor,
    {
        "tutor": "tutor",
        "evaluate": "evaluate"
    }
)

workflow.add_edge("tutor", END)
workflow.add_edge("evaluate", END)

checkpointer = InMemorySaver()
app_graph = workflow.compile(checkpointer=checkpointer)