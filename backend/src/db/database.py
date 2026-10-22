import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# Match the credentials set in docker-compose.yml
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "fyp_postgres")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "password")

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        cursor_factory=RealDictCursor
    )

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
        conn.close()

def get_user_stats(user_id: str):
    """
    Retrieves user stats from Postgres. Returns defaults if non-existent.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM user_stats WHERE user_id = %s;", (user_id,))
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
        conn.close()