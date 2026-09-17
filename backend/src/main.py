import os, uuid
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI
from langchain_core.messages import HumanMessage

# Local imports
from graph import app_graph

# Load environment variables from .env
load_dotenv()

app = FastAPI()
client = OpenAI() # Automatically reads OPENAI_API_KEY from environment

class ChatRequest(BaseModel):
    prompt: str
    thread_id: str | None = None  # Optional thread ID for session continuity

@app.post("/api/chat")
def chat(request: ChatRequest):
    # Generate a new session ID if one is not provided by the client
    session_id = request.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": session_id}}

    # Invoke graph with user's new message
    inputs = {"messages": [HumanMessage(content=request.prompt)]}
    result = app_graph.invoke(inputs, config=config)
    
    # Extract latest AI response from state
    latest_message = result["messages"][-1]
    
    return {
        "thread_id": session_id,
        "response": latest_message.content,
        "message_count": len(result["messages"])
    }