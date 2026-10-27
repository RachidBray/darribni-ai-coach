-- Darribni database schema (PostgreSQL)
-- Reconstructed from the queries used in the n8n workflows.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE athletes (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT,
    telegram_id   TEXT UNIQUE,          -- Telegram user ID, used to find the athlete from a chat message
    strava_id     TEXT UNIQUE,          -- Strava athlete ID, used to match incoming activities
    metrics       JSONB DEFAULT '{}',   -- e.g. {"ftp": 230, "max_hr": 185, "weight_kg": 70}
    coach_notes   TEXT                  -- long-term constraints the coach must remember
);

CREATE TABLE goals (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    athlete_id    UUID REFERENCES athletes(id) ON DELETE CASCADE,
    description   TEXT NOT NULL,        -- e.g. "MTB XC marathon, 80 km, 12 April"
    target_date   DATE,
    status        TEXT DEFAULT 'Active' -- 'Active' | 'Completed' | 'Abandoned'
);

CREATE TABLE strategy_phases (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    goal_id       UUID REFERENCES goals(id) ON DELETE CASCADE,
    name          TEXT,                 -- e.g. "Base", "Build", "Taper"
    focus         TEXT,                 -- what this phase is about, read by the weekly planner
    start_date    DATE,
    end_date      DATE
);

CREATE TABLE activities (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strava_activity_id  TEXT UNIQUE NOT NULL,
    athlete_id          UUID REFERENCES athletes(id) ON DELETE CASCADE,
    start_date          TIMESTAMPTZ,
    sport_type          TEXT,
    summary_metrics     JSONB           -- {"distance_m": ..., "time_s": ..., "avg_hr": ...}
);

CREATE TABLE workouts (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    athlete_id            UUID REFERENCES athletes(id) ON DELETE CASCADE,
    scheduled_date        DATE NOT NULL,
    sport_type            TEXT,
    title                 TEXT,
    description           TEXT,
    target_duration_mins  INTEGER,
    status                TEXT DEFAULT 'Planned',
    gcal_event_id         TEXT          -- written back by the Google Calendar Sync workflow
);

CREATE TABLE conversations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    athlete_id  UUID REFERENCES athletes(id) ON DELETE CASCADE,
    role        TEXT NOT NULL,          -- 'user' | 'coach'
    content     TEXT,
    timestamp   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ON activities (athlete_id, start_date);
CREATE INDEX ON workouts (athlete_id, scheduled_date);
CREATE INDEX ON conversations (athlete_id, timestamp DESC);
