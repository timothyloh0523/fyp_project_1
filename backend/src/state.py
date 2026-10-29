from typing import Annotated, TypedDict, Optional, List
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class OptionItem(TypedDict):
    label: str        # e.g., "a", "b", "c", "d"
    option: str       # The actual option content shown to the student
    is_correct: bool # True if correct, False otherwise
    explanation: str  # Why this option is correct or incorrect

class UserStats(TypedDict):
    curr_streak: int
    best_streak: int
    total_score: int
    total_attempts: int
    weekly_score: int
    weekly_score_week: str | None

class UserGoal(TypedDict):
    goal_type: str       # Currently: "weekly_score"
    number: int          # Target number for the goal
    period: str          # Currently: "week"
    enabled: bool

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    awaiting_eval: bool
    options_list: Optional[List[OptionItem]]  
    user_id: Optional[str]
    user_stats: Optional[UserStats]
    score: Optional[int]
    thread_id: Optional[str]
    current_probe_id: Optional[int]
    event_log: List[dict]
    user_goals: Optional[List[UserGoal]]
