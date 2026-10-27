from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Local imports
from api.routes import router as api_router

# Load environment variables (.env)
load_dotenv()

app = FastAPI(
    title="LearnLoop Guiding Tutor API",
    description="FastAPI + LangGraph backend with persistent PostgreSQL user stats",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API endpoints from routes.py
app.include_router(api_router)


@app.get("/")
def health_check():
    return {"status": "ok", "service": "LearnLoop API"}
