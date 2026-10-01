from typing import TypedDict, Sequence, Annotated, Optional
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, SystemMessage

from coinflip import flip_coin
from prompts import answer_with_follow_up_prompt, base_prompt, evaluation_prompt

load_dotenv()

TOPIC = "Linear Algebra"

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    # Flag to indicate if the system is awaiting a follow-up answer from the user
    # If true, expect next user input to be answer to probing question
    awaiting_eval: bool
    coin_result: Optional[str]
    score: Optional[int]

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
    
    return {
        "messages": [response],
        "awaiting_eval": awaiting_eval,
        # "coin_result": coin_result # Toggle to this line if using randomisation mode
        "coin_result": "tails"
    }

def evaluate_node(state: AgentState) -> dict:
    system_prompt = SystemMessage(content=evaluation_prompt(TOPIC))
    full_messages = [system_prompt] + list(state["messages"])
    response = llm.invoke(full_messages)
    
    # Reset evaluation flag after processing
    return {
        "messages": [response],
        "awaiting_eval": False
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