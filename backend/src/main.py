import os
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI

# Import prompts from prompts.py
from prompts import build_direct_answer_prompt, build_probing_question_prompt
from coinflip import flip_coin

# Load environment variables from .env
load_dotenv()

app = FastAPI()
client = OpenAI() # Automatically reads OPENAI_API_KEY from environment

TOPIC = "Linear Algebra"  # Example topic

class ChatRequest(BaseModel):
    prompt: str

@app.post("/api/chat")
def chat(request: ChatRequest):
    # Option 1: Determine mode via coinflip
    # coin_result = flip_coin()
    # Option 2: Hardcoded mode
    coin_result = "tails"  # or "heads"

    if coin_result == "heads":  # HEADS: Direct answer
        system_instructions = build_direct_answer_prompt(TOPIC)
    else:                       # TAILS: Probing question
        system_instructions = build_probing_question_prompt(TOPIC)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "developer", "content": system_instructions},
            {"role": "user", "content": request.prompt}
        ]
    )
    
    return {
        "coin_result": coin_result,
        "response": response.choices[0].message.content
    }