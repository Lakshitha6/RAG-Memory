-- Supabase tables creation script. Copy this code and paste into Supabase SQL editor --

-- ============================================================
-- 0. Extensions
-- ============================================================
CREATE EXTENSION IF NOT EXISTS vector;


-- ============================================================
-- 1. Users
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    user_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    email       TEXT NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT;

-- ============================================================
-- 2. Chat sessions
-- ============================================================
CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    title       TEXT,
    started_at  TIMESTAMPTZ DEFAULT NOW(),
    ended_at    TIMESTAMPTZ,
    is_active   BOOLEAN DEFAULT true
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_user
    ON chat_sessions(user_id, is_active);


-- ============================================================
-- 3. Chat messages
-- ============================================================
CREATE TABLE IF NOT EXISTS chat_messages (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  UUID NOT NULL REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
    role        TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content     TEXT NOT NULL,
    metadata    JSONB DEFAULT '{}',   -- confidence, source docs, token counts etc.
    message_timestamp   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session
    ON chat_messages(session_id, message_timestamp);


-- ============================================================
-- 4. User preferences  (long-term memory)
-- !! Replace 768 with embedding dimension of the model
-- ============================================================
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id               UUID PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    preferred_language    TEXT DEFAULT 'en',
    response_detail_level TEXT DEFAULT 'concise'
                              CHECK (response_detail_level IN ('concise', 'detailed')),
    common_queries        JSONB DEFAULT '[]',   -- ["repeat course", "GPA calc", ...]
    summary               TEXT,                -- latest summarized history text
    preference_vec        vector(768),
    updated_at            TIMESTAMPTZ DEFAULT NOW()
);

-- HNSW index for fast cosine similarity lookups
CREATE INDEX IF NOT EXISTS idx_user_preferences_vec
    ON user_preferences
    USING hnsw (preference_vec vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);


-- ============================================================
-- 5. auto-update updated_at on user_preferences
-- ============================================================
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_preferences_updated_at ON user_preferences;
CREATE TRIGGER trg_preferences_updated_at
    BEFORE UPDATE ON user_preferences
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ============================================================
-- 6. Helper: get recent messages for a session
--    Returns last `p_limit` turns ordered oldest-first
--    so they slot directly into LangChain message history.
-- ============================================================
CREATE OR REPLACE FUNCTION get_recent_messages(
    p_session_id UUID,
    p_limit      INT DEFAULT 10
)
RETURNS TABLE (
    role      TEXT,
    content   TEXT,
    message_timestamp TIMESTAMPTZ
)
LANGUAGE sql STABLE SECURITY DEFINER AS $$
    SELECT role, content, message_timestamp
    FROM (
        SELECT role, content, message_timestamp
        FROM chat_messages
        WHERE session_id = p_session_id
        ORDER BY message_timestamp DESC
        LIMIT p_limit
    ) recent
    ORDER BY message_timestamp ASC;   -- oldest first for LangChain
$$;


-- ============================================================
-- 7. Helper: count messages since last summarization
--    Used by background summarizer to decide when to fire.
-- ============================================================
CREATE OR REPLACE FUNCTION unsummarized_message_count(
    p_user_id UUID
)
RETURNS INT
LANGUAGE sql STABLE SECURITY DEFINER AS $$
    SELECT COUNT(*)::INT
    FROM chat_messages cm
    JOIN chat_sessions cs ON cs.session_id = cm.session_id
    WHERE cs.user_id = p_user_id
      AND cm.message_timestamp > COALESCE(
            (SELECT updated_at FROM user_preferences WHERE user_id = p_user_id),
            '-infinity'::TIMESTAMPTZ
          );
$$;


-- ============================================================
-- 8. RLS — enable then add policies
-- ============================================================
ALTER TABLE users            ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_sessions    ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages    ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY;

-- users: backend service can read/write; public cannot
CREATE POLICY "Service role manages users"
    ON users FOR ALL
    USING (true)
    WITH CHECK (true);

-- chat_sessions: scoped to the authenticated user_id
CREATE POLICY "Users manage own sessions"
    ON chat_sessions FOR ALL
    USING (user_id::TEXT = current_setting('app.current_user_id', true))
    WITH CHECK (user_id::TEXT = current_setting('app.current_user_id', true));

-- chat_messages: scoped through session ownership
CREATE POLICY "Users manage own messages"
    ON chat_messages FOR ALL
    USING (
        session_id IN (
            SELECT session_id FROM chat_sessions
            WHERE user_id::TEXT = current_setting('app.current_user_id', true)
        )
    );

-- user_preferences: scoped directly to user
CREATE POLICY "Users manage own preferences"
    ON user_preferences FOR ALL
    USING (user_id::TEXT = current_setting('app.current_user_id', true))
    WITH CHECK (user_id::TEXT = current_setting('app.current_user_id', true));