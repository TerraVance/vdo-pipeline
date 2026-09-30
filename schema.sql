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
            'GENERATING_VIDEO',
            'VIDEO_READY',
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

    -- Step 2: Gemini refined prompt
    refined_prompt      TEXT,

    -- Step 3: Image generation
    image_urls          JSONB           NOT NULL DEFAULT '[]',   -- array of 4 candidate image URLs
    selected_image_url  TEXT,                                    -- the one the user picks

    -- Step 4: Video generation
    final_video_url     TEXT,                                    -- final MP4 URL in Supabase Storage

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

CREATE POLICY "projects_select" ON projects FOR SELECT USING (true);
CREATE POLICY "projects_insert" ON projects FOR INSERT WITH CHECK (true);
CREATE POLICY "projects_update" ON projects FOR UPDATE USING (true) WITH CHECK (true);


-- ── Step 5: Helpful indexes ───────────────────────────────────────────────────
-- Speeds up the status polling query (GET /status called every 3s)
CREATE INDEX IF NOT EXISTS idx_projects_status     ON projects (status);
CREATE INDEX IF NOT EXISTS idx_projects_created_at ON projects (created_at DESC);


-- ── Step 6: Verify (optional — run to confirm everything was created) ─────────
-- SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'projects';
-- SELECT * FROM pg_policies WHERE tablename = 'projects';
