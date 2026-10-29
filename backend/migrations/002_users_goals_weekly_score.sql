CREATE TABLE IF NOT EXISTS users (
    user_id VARCHAR(100) PRIMARY KEY,
    display_name TEXT,
    email TEXT,
    goals JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE user_stats
    ADD COLUMN IF NOT EXISTS weekly_score INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS weekly_score_week DATE NOT NULL DEFAULT date_trunc('week', CURRENT_DATE)::date;

CREATE INDEX IF NOT EXISTS idx_users_goals ON users USING GIN (goals);
