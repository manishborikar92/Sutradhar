-- Sutradhar Production Database Schema
-- Version: 4.0.0 (Bilingual Series Metadata, Publishing Audit History & TTS Ledger)

PRAGMA foreign_keys = ON;
PRAGMA user_version = 4;

CREATE TABLE IF NOT EXISTS series (
    series_id INTEGER PRIMARY KEY AUTOINCREMENT,
    series_title TEXT NOT NULL,
    series_title_en TEXT,
    series_title_hi TEXT,
    pillar TEXT NOT NULL,
    tts_voice TEXT NOT NULL DEFAULT 'uuyFQegRan8rpIQCGu9K',
    bgm_track TEXT NOT NULL,
    metadata_language TEXT NOT NULL DEFAULT 'en',
    audio_language TEXT NOT NULL DEFAULT 'hi',
    total_planned_episodes INTEGER DEFAULT NULL,
    completed_episodes INTEGER NOT NULL DEFAULT 0,
    series_bible_json TEXT NOT NULL,
    youtube_playlist_id TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'COMPLETED', 'ARCHIVED')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    legacy_asset_path TEXT,
    script_json TEXT NOT NULL,
    research_sources_json TEXT,
    youtube_video_id TEXT UNIQUE,
    video_url TEXT,
    scheduled_publish_at TEXT,
    published_at TEXT,
    duration_sec REAL,
    audio_language TEXT NOT NULL DEFAULT 'hi',
    metadata_language TEXT NOT NULL DEFAULT 'en',
    thumbnail_asset_path TEXT,
    video_asset_path TEXT,
    file_bytes INTEGER,
    kinocut_score REAL,
    static_fraction REAL,
    tts_billed_chars INTEGER,
    visual_direction_version TEXT DEFAULT 'v2_storycraft',
    status TEXT NOT NULL CHECK (status IN ('PLANNED', 'PREVIEW_APPROVED', 'PUBLISHED', 'PRIVATE_REVIEW', 'FAILED', 'SUPERSEDED')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (series_id) REFERENCES series(series_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS publishing_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    youtube_video_id TEXT NOT NULL,
    previous_video_id TEXT,
    playlist_id TEXT,
    status TEXT NOT NULL,
    notes TEXT,
    cdn_thumbnail_url TEXT,
    cdn_mae REAL,
    cdn_dhash_distance INTEGER,
    checks_json TEXT,
    details_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (episode_id) REFERENCES episodes(episode_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS audio_ledger (
    ledger_id INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id INTEGER,
    scene_index INTEGER NOT NULL CHECK (scene_index >= 1),
    sha256_key TEXT NOT NULL,
    billed_chars INTEGER NOT NULL CHECK (billed_chars >= 0),
    model_id TEXT NOT NULL DEFAULT 'eleven_v4',
    voice_id TEXT NOT NULL DEFAULT 'uuyFQegRan8rpIQCGu9K',
    cache_hit INTEGER NOT NULL DEFAULT 0 CHECK (cache_hit IN (0, 1)),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (episode_id) REFERENCES episodes(episode_id) ON DELETE SET NULL
);

-- Partial Unique Index: ensures series episode slots are unique among live/planned non-failed episodes
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_non_failed_episode_slot
    ON episodes (series_id, episode_number_in_series)
    WHERE status NOT IN ('FAILED', 'SUPERSEDED') AND series_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_episodes_series_id
    ON episodes (series_id, episode_number_in_series);

CREATE INDEX IF NOT EXISTS idx_episodes_global_number
    ON episodes (global_episode_number);

CREATE INDEX IF NOT EXISTS idx_publishing_history_episode_id
    ON publishing_history (episode_id, created_at);

CREATE INDEX IF NOT EXISTS idx_publishing_history_video_id
    ON publishing_history (youtube_video_id);

CREATE INDEX IF NOT EXISTS idx_audio_ledger_sha256
    ON audio_ledger (sha256_key);

CREATE INDEX IF NOT EXISTS idx_audio_ledger_episode_id
    ON audio_ledger (episode_id, scene_index);
