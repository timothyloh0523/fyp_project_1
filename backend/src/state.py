from typing import Annotated, TypedDict, Optional, List
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class OptionItem(TypedDict):
    option: str      # e.g., "a", "b", "c", "d" or option text
    is_correct: bool # True if correct, False otherwise

class UserStats(TypedDict):
    curr_streak: int
    best_streak: int
    total_score: int
    total_attempts: int

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
