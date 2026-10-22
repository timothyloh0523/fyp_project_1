CREATE TABLE IF NOT EXISTS user_stats (
    user_id VARCHAR(100) PRIMARY KEY,
    curr_streak INT DEFAULT 0,
    best_streak INT DEFAULT 0,
    total_score INT DEFAULT 0,
    total_attempts INT DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    thread_id UUID PRIMARY KEY,
    user_id TEXT NOT NULL,
    topic TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_activity_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id BIGSERIAL PRIMARY KEY,
    thread_id UUID NOT NULL REFERENCES chat_sessions(thread_id) ON DELETE CASCADE,
    sequence_no INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('human', 'ai', 'system')),
    content TEXT NOT NULL,
    node_name TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (thread_id, sequence_no)
);

CREATE TABLE IF NOT EXISTS probes (
    id BIGSERIAL PRIMARY KEY,
    thread_id UUID NOT NULL REFERENCES chat_sessions(thread_id) ON DELETE CASCADE,
    message_id BIGINT REFERENCES chat_messages(id) ON DELETE SET NULL,
    question TEXT NOT NULL,
    options JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS probe_answers (
    id BIGSERIAL PRIMARY KEY,
    probe_id BIGINT NOT NULL REFERENCES probes(id) ON DELETE CASCADE,
    raw_answer TEXT NOT NULL,
    selected_options JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_correct BOOLEAN,
    score INTEGER,
    feedback TEXT,
    answered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS llm_events (
    id BIGSERIAL PRIMARY KEY,
    thread_id UUID NOT NULL REFERENCES chat_sessions(thread_id) ON DELETE CASCADE,
    node_name TEXT NOT NULL,
    event_name TEXT NOT NULL,
    model_name TEXT,
    input_message_count INTEGER,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_thread ON chat_messages(thread_id, sequence_no);
CREATE INDEX IF NOT EXISTS idx_llm_events_thread ON llm_events(thread_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_probes_thread ON probes(thread_id, created_at);
