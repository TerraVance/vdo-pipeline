-- ============================================================
-- Interactive AI Video Generation Pipeline — Supabase Schema
-- Run this entire file in the Supabase SQL Editor.
-- It is safe to re-run (uses IF NOT EXISTS / CREATE OR REPLACE).
-- ============================================================


-- ── Step 1: Create the pipeline_status ENUM ──────────────────────────────────
-- This mirrors the PipelineStatus enum in backend/app/models/schemas.py
-- EXACTLY. If you add a new status to Python, add it here too.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'pipeline_status') THEN
        CREATE TYPE pipeline_status AS ENUM (
            'DRAFT',
            'PROMPT_REFINED',
            'GENERATING_IMAGES',
            'IMAGES_READY',
            'FAILED'
        );
    END IF;
END$$;


-- ── Step 2: Create the projects table ────────────────────────────────────────

CREATE TABLE IF NOT EXISTS projects (
    -- Primary Key
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Step 1: User input
    raw_prompt          TEXT            NOT NULL,
    style_tags          JSONB           NOT NULL DEFAULT '[]',   -- e.g. ["Cyberpunk", "Neon"]

    -- Step 2: Gemini refined prompts
    refined_prompt      TEXT,
    image_prompt        TEXT,                                    -- focused visual description

    -- Step 3: Image generation
    image_urls          JSONB           NOT NULL DEFAULT '[]',   -- array of 4 candidate image URLs
    selected_image_url  TEXT,                                    -- single-scene: the one the user picks
    selected_image_urls JSONB           NOT NULL DEFAULT '[]',   -- multi-scene: ordered list of selected images


    -- Auth: link project to its creator (nullable for backwards compat with anonymous projects)
    user_id             UUID            REFERENCES auth.users(id),

    -- Pipeline tracking
    status              pipeline_status NOT NULL DEFAULT 'DRAFT',
    task_id             TEXT,                                    -- current Celery task ID

    -- Timestamps
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);


-- ── Step 3: Auto-update the updated_at column on every row update ─────────────

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_projects_updated_at ON projects;
CREATE TRIGGER trg_projects_updated_at
    BEFORE UPDATE ON projects
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- ── Step 4: Row Level Security ───────────────────────────────────────────────
-- We enable RLS but allow all operations for now (no user auth yet).
-- When you add Supabase Auth later, replace these policies with
-- user-scoped ones (e.g. USING (auth.uid() = user_id)).

ALTER TABLE projects ENABLE ROW LEVEL SECURITY;

-- Drop & recreate to avoid duplicates on re-run
DROP POLICY IF EXISTS "projects_select" ON projects;
DROP POLICY IF EXISTS "projects_insert" ON projects;
DROP POLICY IF EXISTS "projects_update" ON projects;
DROP POLICY IF EXISTS "projects_delete" ON projects;

-- Allow anyone to read (supports future public gallery)
CREATE POLICY "projects_select" ON projects FOR SELECT USING (true);
-- Any authenticated or anonymous user can insert (user_id may be null for anonymous)
CREATE POLICY "projects_insert" ON projects FOR INSERT WITH CHECK (true);
-- Anyone can update a project row (ownership enforced at the API layer)
CREATE POLICY "projects_update" ON projects FOR UPDATE USING (true) WITH CHECK (true);
-- Allow deletes (ownership is enforced in the FastAPI backend before this is reached)
CREATE POLICY "projects_delete" ON projects FOR DELETE USING (true);


-- ── Step 5: Helpful indexes ───────────────────────────────────────────────────
-- Speeds up the status polling query (GET /status called every 3s)
CREATE INDEX IF NOT EXISTS idx_projects_status     ON projects (status);
CREATE INDEX IF NOT EXISTS idx_projects_created_at ON projects (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_projects_user_id    ON projects (user_id);


-- ── Step 6: Verify (optional — run to confirm everything was created) ─────────
-- SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'projects';
-- SELECT * FROM pg_policies WHERE tablename = 'projects';


-- ============================================================
-- Phase 1 Studio UI: Sessions and Messages Schema
-- ============================================================

CREATE TABLE IF NOT EXISTS sessions (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID            REFERENCES auth.users(id),
    title               TEXT            NOT NULL DEFAULT 'New Conversation',
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Auto-update trigger for sessions
DROP TRIGGER IF EXISTS trg_sessions_updated_at ON sessions;
CREATE TRIGGER trg_sessions_updated_at
    BEFORE UPDATE ON sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- Message status enum
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'message_status') THEN
        CREATE TYPE message_status AS ENUM (
            'COMPLETED',
            'PENDING',
            'FAILED'
        );
    END IF;
END$$;


CREATE TABLE IF NOT EXISTS messages (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID            NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role                TEXT            NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content             TEXT            NOT NULL,
    action              TEXT,           -- e.g., 'create_image', 'create_video', 'refine_prompt'
    model               TEXT,           -- e.g., 'gemini_veo2'
    aspect_ratio        TEXT,           -- e.g., '16:9'
    image_urls          JSONB           NOT NULL DEFAULT '[]',
    status              message_status  NOT NULL DEFAULT 'COMPLETED',
    task_id             TEXT,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Auto-update trigger for messages
DROP TRIGGER IF EXISTS trg_messages_updated_at ON messages;
CREATE TRIGGER trg_messages_updated_at
    BEFORE UPDATE ON messages
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- RLS for sessions and messages
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "sessions_select" ON sessions;
DROP POLICY IF EXISTS "sessions_insert" ON sessions;
DROP POLICY IF EXISTS "sessions_update" ON sessions;
DROP POLICY IF EXISTS "sessions_delete" ON sessions;
CREATE POLICY "sessions_select" ON sessions FOR SELECT USING (true);
CREATE POLICY "sessions_insert" ON sessions FOR INSERT WITH CHECK (true);
CREATE POLICY "sessions_update" ON sessions FOR UPDATE USING (true) WITH CHECK (true);
CREATE POLICY "sessions_delete" ON sessions FOR DELETE USING (true);

DROP POLICY IF EXISTS "messages_select" ON messages;
DROP POLICY IF EXISTS "messages_insert" ON messages;
DROP POLICY IF EXISTS "messages_update" ON messages;
DROP POLICY IF EXISTS "messages_delete" ON messages;
CREATE POLICY "messages_select" ON messages FOR SELECT USING (true);
CREATE POLICY "messages_insert" ON messages FOR INSERT WITH CHECK (true);
CREATE POLICY "messages_update" ON messages FOR UPDATE USING (true) WITH CHECK (true);
CREATE POLICY "messages_delete" ON messages FOR DELETE USING (true);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);
