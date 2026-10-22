from typing import TypedDict, Sequence, Annotated, Optional, List
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, AIMessage
from db.database import upsert_user_stats

import json
import re
import ast

from prompts import base_prompt, probe_prompt
from state import AgentState, UserStats, OptionItem

load_dotenv()

TOPIC = "Linear Algebra"
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

def tutor_node(state: AgentState) -> dict:
    system_prompt = SystemMessage(content=base_prompt(TOPIC))
    full_messages = [system_prompt] + list(state["messages"])
    response = llm.invoke(full_messages)
    
    return {
        "messages": [response],
        "awaiting_eval": False,
        # A tutor turn starts a new probe.  Clear the previous probe's
        # metadata explicitly; prober_node will replace it immediately.
        "options_list": None,
    }

def prober_node(state: AgentState) -> dict:
    system_prompt = SystemMessage(content=probe_prompt(TOPIC))
    # The tutor node has just appended the explanation.  Do not send the
    # entire accumulated conversation here: old probe metadata/questions can
    # distract the model from the current explanation and its required block.
    full_messages = [system_prompt, state["messages"][-1]]
    response = llm.invoke(full_messages)

    content = response.content
    
    # 1. Extract the options metadata block (e.g. [Options Meta: {"a": true, "b": false...}])
    # The model may vary whitespace/capitalisation and may emit a Python-style
    # dict (single quotes/True) despite the prompt asking for JSON.  Keep the
    # student-facing output independent of that formatting variation.
    meta_match = re.search(
        r"\[\s*Options\s+Meta\s*:\s*(\{.*?\})\s*\]",
        content,
        re.IGNORECASE | re.DOTALL,
    )
    
    options_list: List[OptionItem] = []
    if meta_match:
        try:
            raw_meta = meta_match.group(1)
            try:
                meta_dict = json.loads(raw_meta)
            except json.JSONDecodeError:
                # Tolerate {'a': True, 'b': False}, while still parsing only
                # the already-delimited metadata object.
                meta_dict = ast.literal_eval(raw_meta)
            if not isinstance(meta_dict, dict):
                raise ValueError("Options metadata must be an object")
            # Convert dictionary into list of (option, isCorrect) structure
            options_list = [{"option": k.strip().lower(), "is_correct": bool(v)} for k, v in meta_dict.items()]
        except (ValueError, SyntaxError, TypeError):
            # Do not invent a correct answer. An empty list makes the failure
            # visible and prevents a bogus evaluation from being recorded.
            options_list = []

    # 2. Strip the meta tag so the student only sees the question and choices
    clean_content = re.sub(
        r"\[\s*Options\s+Meta\s*:\s*(\{.*?\})\s*\]",
        "",
        content,
        flags=re.IGNORECASE | re.DOTALL,
    ).strip()

    current_stats = state.get("user_stats") or {
        "curr_streak": 0,
        "best_streak": 0,
        "total_score": 0,
        "total_attempts": 0,
    }
    
    return {
        "messages": [AIMessage(content=clean_content)],
        "awaiting_eval": True,
        "options_list": options_list,  # Stored background list of pairs
        "user_stats": current_stats
    }
def evaluate_node(state: AgentState) -> dict:
    last_msg = state["messages"][-1].content
    
    # Clean input if sent via CLI '/a' command (e.g. "/a a, c" -> "a, c")
    student_ans_raw = re.sub(r"^/a\s*", "", last_msg).strip().lower()
    
    # Parse user selected options (split by comma)
    student_selections = {p.strip() for p in student_ans_raw.replace(";", ",").split(",") if p.strip()}
    
    # Retrieve options list from state
    options_list: List[OptionItem] = state.get("options_list", [])
    
    # Determine correct selections based on the options_list pairs
    expected_correct = {item["option"] for item in options_list if item["is_correct"]}
    
    # Score is 1 if student selections match expected correct options precisely
    score = 1 if student_selections == expected_correct else 0

    stats = state.get("user_stats") or {
        "curr_streak": 0,
        "best_streak": 0,
        "total_score": 0,
        "total_attempts": 0,
    }

    total_attempts = stats["total_attempts"] + 1
    total_score = stats["total_score"] + score

    if score == 1:
        curr_streak = stats["curr_streak"] + 1
        best_streak = max(stats["best_streak"], curr_streak)
        feedback = f"✅ **Correct!** Your selection (`{student_ans_raw}`) matches the expected options."
    else:
        correct_str = ", ".join(sorted(list(expected_correct)))
        curr_streak = 0
        best_streak = stats["best_streak"]
        feedback = f"❌ **Incorrect.** Your selection was (`{student_ans_raw}`), but the correct options were: `{correct_str}`."

    updated_stats: UserStats = {
        "curr_streak": curr_streak,
        "best_streak": best_streak,
        "total_score": total_score,
        "total_attempts": total_attempts,
    }

    user_id = state.get("user_id", "default_user")
    upsert_user_stats(user_id, updated_stats)

    return {
        "messages": [AIMessage(content=feedback)],
        "awaiting_eval": False,
        "options_list": None,
        "score": score,
        "user_stats": updated_stats,
    }

def route_tutor(state: AgentState) -> str:
    if state.get("awaiting_eval"):
        return "evaluate"
    return "tutor"

workflow = StateGraph(AgentState)
workflow.add_node("tutor", tutor_node)
workflow.add_node("prober", prober_node)
workflow.add_node("evaluate", evaluate_node)

workflow.set_conditional_entry_point(
    route_tutor,
    {
        "tutor": "tutor",
        "evaluate": "evaluate"
    }
)

workflow.add_edge("tutor", "prober")
workflow.add_edge("prober", END)
workflow.add_edge("evaluate", END)

checkpointer = InMemorySaver()
app_graph = workflow.compile(checkpointer=checkpointer)
