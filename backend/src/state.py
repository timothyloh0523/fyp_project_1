from typing import TypedDict, Sequence, Annotated, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class UserStats(TypedDict):
    curr_streak: int
    best_streak: int
    total_score: int
    total_attempts: int

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    awaiting_eval: bool
    coin_result: Optional[str]
    score: Optional[int]
    user_stats: UserStats