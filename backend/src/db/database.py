import os
import json
import asyncio
import threading
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# Match the credentials set in docker-compose.yml
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "fyp_postgres")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "password")
DB_CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", "5"))

_pool = None
_pool_lock = threading.Lock()

def get_db_connection():
    """Borrow a reusable connection from the thread-safe pool."""
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = ThreadedConnectionPool(
                    minconn=1,
                    maxconn=int(os.getenv("DB_POOL_MAX", "10")),
                    host=DB_HOST,
                    port=DB_PORT,
                    dbname=DB_NAME,
                    user=DB_USER,
                    password=DB_PASS,
                    connect_timeout=DB_CONNECT_TIMEOUT,
                    keepalives=1,
                    keepalives_idle=10,
                    keepalives_interval=5,
                    keepalives_count=3,
                    cursor_factory=RealDictCursor,
                )
    return _pool.getconn()

def release_db_connection(conn):
    """Return a connection to the pool instead of closing the socket."""
    if _pool is not None and conn is not None:
        try:
            conn.rollback()
            _pool.putconn(conn)
        except Exception:
            _pool.putconn(conn, close=True)

def upsert_user_stats(user_id: str, user_stats: dict):
    """
    Inserts or updates the user stats for a specific user.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            query = """
            INSERT INTO user_stats (user_id, curr_streak, best_streak, total_score, total_attempts, updated_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            ON CONFLICT (user_id) 
            DO UPDATE SET
                curr_streak = EXCLUDED.curr_streak,
                best_streak = GREATEST(user_stats.best_streak, EXCLUDED.best_streak),
                total_score = EXCLUDED.total_score,
                total_attempts = EXCLUDED.total_attempts,
                updated_at = NOW();
            """
            cursor.execute(query, (
                user_id,
                user_stats["curr_streak"],
                user_stats["best_streak"],
                user_stats["total_score"],
                user_stats["total_attempts"]
            ))
            conn.commit()
    finally:
        release_db_connection(conn)

def get_user_stats(user_id: str):
    """
    Retrieves user stats from Postgres. Returns defaults if non-existent.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM user_stats WHERE user_id = %s;",
                (user_id,),
            )
            record = cursor.fetchone()
            if record:
                return {
                    "curr_streak": record["curr_streak"],
                    "best_streak": record["best_streak"],
                    "total_score": record["total_score"],
                    "total_attempts": record["total_attempts"]
                }
            return {"curr_streak": 0, "best_streak": 0, "total_score": 0, "total_attempts": 0}
    finally:
        release_db_connection(conn)

def record_llm_event(thread_id: str, node_name: str, event_name: str, *, model_name: str | None = None,
                     input_message_count: int | None = None, metadata: dict | None = None):
    """Append one durable graph/LLM lifecycle event."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """INSERT INTO llm_events
                (thread_id, node_name, event_name, model_name, input_message_count, metadata)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)""",
                (thread_id, node_name, event_name, model_name, input_message_count,
                 json.dumps(metadata or {})),
            )
            conn.commit()
    finally:
        release_db_connection(conn)

def ensure_chat_session(thread_id: str, user_id: str, topic: str | None = None):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """INSERT INTO chat_sessions (thread_id, user_id, topic)
                VALUES (%s, %s, %s)
                ON CONFLICT (thread_id) DO UPDATE SET last_activity_at = NOW()""",
                (thread_id, user_id, topic),
            )
            conn.commit()
    finally:
        release_db_connection(conn)

def record_message(thread_id: str, sequence_no: int, role: str, content: str, node_name: str | None = None):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """INSERT INTO chat_messages (thread_id, sequence_no, role, content, node_name)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (thread_id, sequence_no) DO NOTHING
                RETURNING id""",
                (thread_id, sequence_no, role, content, node_name),
            )
            row = cursor.fetchone()
            conn.commit()
            return row["id"] if row else None
    finally:
        release_db_connection(conn)

def record_probe(thread_id: str, question: str, options: list[dict], message_id: int | None = None):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """INSERT INTO probes (thread_id, message_id, question, options)
                VALUES (%s, %s, %s, %s::jsonb) RETURNING id""",
                (thread_id, message_id, question, json.dumps(options)),
            )
            probe_id = cursor.fetchone()["id"]
            conn.commit()
            return probe_id
    finally:
        release_db_connection(conn)

def record_probe_answer(probe_id: int, raw_answer: str, selected_options: list[str], score: int,
                        feedback: str):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """INSERT INTO probe_answers
                (probe_id, raw_answer, selected_options, is_correct, score, feedback)
                VALUES (%s, %s, %s::jsonb, %s, %s, %s)""",
                (probe_id, raw_answer, json.dumps(selected_options), score == 1, score, feedback),
            )
            conn.commit()
    finally:
        release_db_connection(conn)

# Async adapters keep the synchronous psycopg2 implementation off FastAPI's
# event loop.
async def a_get_user_stats(user_id: str):
    return await asyncio.to_thread(get_user_stats, user_id)

async def a_upsert_user_stats(user_id: str, user_stats: dict):
    return await asyncio.to_thread(upsert_user_stats, user_id, user_stats)

async def a_ensure_chat_session(thread_id: str, user_id: str, topic: str | None = None):
    return await asyncio.to_thread(ensure_chat_session, thread_id, user_id, topic)

async def a_record_message(thread_id: str, sequence_no: int, role: str, content: str,
                           node_name: str | None = None):
    return await asyncio.to_thread(record_message, thread_id, sequence_no, role, content, node_name)

async def a_record_llm_event(thread_id: str, node_name: str, event_name: str, **kwargs):
    return await asyncio.to_thread(record_llm_event, thread_id, node_name, event_name, **kwargs)

async def a_record_probe(thread_id: str, question: str, options: list[dict], message_id: int | None = None):
    return await asyncio.to_thread(record_probe, thread_id, question, options, message_id)

async def a_record_probe_answer(probe_id: int, raw_answer: str, selected_options: list[str], score: int,
                                feedback: str):
    return await asyncio.to_thread(
        record_probe_answer, probe_id, raw_answer, selected_options, score, feedback
    )
