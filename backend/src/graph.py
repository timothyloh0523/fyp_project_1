import asyncio
import re
from typing import TypedDict, Sequence, Annotated, Optional, List
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, AIMessage
from pydantic import BaseModel, Field
from db.database import (
    a_upsert_user_stats,
    a_record_llm_event,
    a_record_probe,
    a_record_probe_answer,
)

from prompts import base_prompt, probe_prompt
from state import AgentState, UserStats, OptionItem

load_dotenv()

TOPIC = "Linear Algebra"
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

class StructuredProbeOption(BaseModel):
    label: str = Field(description="A short option label such as a, b, c, or d")
    option: str = Field(description="The complete answer choice text shown to the student")
    is_correct: bool = Field(description="Whether this option is correct")
    explanation: str = Field(description="Why this option is correct or incorrect")

class StructuredProbe(BaseModel):
    question: str = Field(description="The probing question shown to the student")
    options: list[StructuredProbeOption] = Field(min_length=2, max_length=8)

structured_prober = llm.with_structured_output(StructuredProbe)

async def _persist_event(thread_id: str, node_name: str, event_name: str, metadata: dict,
                         input_message_count: int):
    try:
        await a_record_llm_event(
            thread_id,
            node_name,
            event_name,
            model_name="gpt-4o-mini" if node_name in {"tutor", "prober"} else None,
            input_message_count=input_message_count,
            metadata=metadata,
        )
    except Exception as error:
        print(f"[db] event persist failed: {type(error).__name__}")

async def _persist_probe_answer(probe_id: int | None, raw_answer: str,
                                selected_options: list[str], score: int,
                                feedback: str):
    try:
        if probe_id:
            await a_record_probe_answer(
                probe_id, raw_answer, selected_options, score, feedback
            )
    except Exception as error:
        print(f"[db] evaluation persist failed: {type(error).__name__}")

def log_event(state: AgentState, node_name: str, event_name: str, **metadata):
    """Persist telemetry and keep a small copy in graph state for debugging."""
    thread_id = state.get("thread_id")
    print(f"[event] {node_name}:{event_name}", flush=True)
    event = {"node": node_name, "event": event_name, "metadata": metadata}
    if thread_id:
        asyncio.create_task(
            _persist_event(
                thread_id,
                node_name,
                event_name,
                metadata,
                len(state.get("messages", [])),
            )
        )
    return [*state.get("event_log", []), event]

async def tutor_node(state: AgentState) -> dict:
    event_log = log_event(state, "tutor", "llm_generation_started")
    system_prompt = SystemMessage(content=base_prompt(TOPIC))
    full_messages = [system_prompt] + list(state["messages"])
    response = await llm.ainvoke(full_messages)
    event_log = log_event(state, "tutor", "llm_generation_finished", response_length=len(response.content))
    
    return {
        "messages": [response],
        "awaiting_eval": False,
        # A tutor turn starts a new probe.  Clear the previous probe's
        # metadata explicitly; prober_node will replace it immediately.
        "options_list": None,
        "event_log": event_log,
    }

async def prober_node(state: AgentState) -> dict:
    event_log = log_event(state, "prober", "received_tutor_response")
    event_log = log_event(state, "prober", "llm_generation_started")
    system_prompt = SystemMessage(content=probe_prompt(TOPIC))
    # The tutor node has just appended the explanation.  Do not send the
    # entire accumulated conversation here: old probe metadata/questions can
    # distract the model from the current explanation and its required block.
    full_messages = [system_prompt, state["messages"][-1]]
    response = await structured_prober.ainvoke(full_messages)
    event_log = log_event(
        state,
        "prober",
        "llm_generation_finished",
        response_length=len(response.question),
    )

    clean_content = response.question.strip()
    options_list: List[OptionItem] = [
        {
            "label": item.label.strip().lower(),
            "option": item.option.strip(),
            "is_correct": item.is_correct,
            "explanation": item.explanation.strip(),
        }
        for item in response.options
    ]

    current_stats = state.get("user_stats") or {
        "curr_streak": 0,
        "best_streak": 0,
        "total_score": 0,
        "total_attempts": 0,
        "weekly_score": 0,
        "weekly_score_week": None,
    }
    
    probe_id = None
    if state.get("thread_id"):
        probe_id = await a_record_probe(state["thread_id"], clean_content, options_list)


    return {
        "messages": [AIMessage(content=clean_content)],
        "awaiting_eval": True,
        "options_list": options_list,  # Stored background list of pairs
        "user_stats": current_stats,
        "current_probe_id": probe_id,
        "event_log": event_log,
    }
async def evaluate_node(state: AgentState) -> dict:
    event_log = log_event(state, "evaluate", "answer_evaluation_started")
    last_msg = state["messages"][-1].content
    
    # Clean input if sent via CLI '/a' command (e.g. "/a a, c" -> "a, c")
    student_ans_raw = re.sub(r"^/a\s*", "", last_msg).strip().lower()
    
    # Parse user selected options (split by comma)
    student_selections = {p.strip() for p in student_ans_raw.replace(";", ",").split(",") if p.strip()}
    
    # Retrieve options list from state
    options_list: List[OptionItem] = state.get("options_list", [])
    
    # Determine correct selections based on the options_list pairs
    expected_correct = {
        item.get("label", item["option"])
        for item in options_list
        if item["is_correct"]
    }
    
    # Score is 1 if student selections match expected correct options precisely
    score = 1 if student_selections == expected_correct else 0

    stats = state.get("user_stats") or {
        "curr_streak": 0,
        "best_streak": 0,
        "total_score": 0,
        "total_attempts": 0,
        "weekly_score": 0,
        "weekly_score_week": None,
    }

    total_attempts = stats["total_attempts"] + 1
    total_score = stats["total_score"] + score
    weekly_score = stats.get("weekly_score", 0) + score

    if score == 1:
        curr_streak = stats["curr_streak"] + 1
        best_streak = max(stats["best_streak"], curr_streak)
        feedback = f"✅ **Correct!** Your selection (`{student_ans_raw}`) matches the expected options."
    else:
        correct_str = ", ".join(sorted(list(expected_correct)))
        curr_streak = 0
        best_streak = stats["best_streak"]
        feedback = f"❌ **Incorrect.** Your selection was (`{student_ans_raw}`), but the correct options were: `{correct_str}`."

    feedback += "\n\n**Option explanations:**\n" + "\n".join(
        f"- Option {item.get('label', item['option'])}: {item['explanation']}"
        for item in options_list
    )

    updated_stats: UserStats = {
        "curr_streak": curr_streak,
        "best_streak": best_streak,
        "total_score": total_score,
        "total_attempts": total_attempts,
        "weekly_score": weekly_score,
        "weekly_score_week": stats.get("weekly_score_week"),
    }

    user_id = state.get("user_id", "default_user")
    await a_upsert_user_stats(user_id, updated_stats)
    asyncio.create_task(
        _persist_probe_answer(
            state.get("current_probe_id"),
            student_ans_raw,
            sorted(student_selections),
            score,
            feedback,
        )
    )
    event_log = log_event(state, "evaluate", "answer_evaluation_finished", score=score)

    return {
        "messages": [AIMessage(content=feedback)],
        "awaiting_eval": False,
        "options_list": None,
        "score": score,
        "user_stats": updated_stats,
        "event_log": event_log,
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
