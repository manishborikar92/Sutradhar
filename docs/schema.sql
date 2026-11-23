-- Sutradhar Production Database Schema
-- Version: 3.0.0 (Unified Hindi Episodic & Standalone Architecture)

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS series (
    series_id INTEGER PRIMARY KEY AUTOINCREMENT,
    series_title TEXT NOT NULL,
    pillar TEXT NOT NULL,
    tts_voice TEXT NOT NULL DEFAULT 'uuyFQegRan8rpIQCGu9K',
    bgm_track TEXT NOT NULL,
    total_planned_episodes INTEGER DEFAULT NULL,
    completed_episodes INTEGER NOT NULL DEFAULT 0,
    series_bible_json TEXT NOT NULL,
    youtube_playlist_id TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'COMPLETED', 'ARCHIVED')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS episodes (
    episode_id INTEGER PRIMARY KEY AUTOINCREMENT,
    series_id INTEGER,
    episode_number_in_series INTEGER CHECK (episode_number_in_series IS NULL OR episode_number_in_series >= 1),
    global_episode_number INTEGER NOT NULL UNIQUE CHECK (global_episode_number >= 1),
    content_format TEXT NOT NULL DEFAULT 'episodic_series' CHECK (content_format IN ('standalone', 'episodic_series', 'serial')),
    youtube_title TEXT NOT NULL,
    summary TEXT NOT NULL,
    bespoke_asset_path TEXT NOT NULL,
    script_json TEXT NOT NULL,
    research_sources_json TEXT,
    youtube_video_id TEXT UNIQUE,
    scheduled_publish_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('PUBLISHED', 'PRIVATE_REVIEW', 'FAILED')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (series_id) REFERENCES series(series_id) ON DELETE RESTRICT
);

-- Partial Unique Index: ensures series episode numbers are unique among non-failed series episodes
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_non_failed_episode_slot
    ON episodes (series_id, episode_number_in_series)
    WHERE status != 'FAILED' AND series_id IS NOT NULL;

-- Fast lookups for series continuity
CREATE INDEX IF NOT EXISTS idx_episodes_series_id
    ON episodes (series_id, episode_number_in_series);

-- Fast lookups for global episode ordering
CREATE INDEX IF NOT EXISTS idx_episodes_global_number
    ON episodes (global_episode_number);
