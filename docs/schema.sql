CREATE TABLE IF NOT EXISTS series (
    series_id INTEGER PRIMARY KEY AUTOINCREMENT,
    series_title TEXT NOT NULL,
    pillar TEXT NOT NULL,
    tts_voice TEXT NOT NULL,
    bgm_track TEXT NOT NULL,
    total_planned_episodes INTEGER NOT NULL CHECK (total_planned_episodes BETWEEN 3 AND 6),
    completed_episodes INTEGER NOT NULL DEFAULT 0
        CHECK (completed_episodes >= 0 AND completed_episodes <= total_planned_episodes),
    series_bible_json TEXT NOT NULL,
    youtube_playlist_id TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'COMPLETED')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_single_active_series
    ON series (status)
    WHERE status = 'ACTIVE';

CREATE TABLE IF NOT EXISTS episodes (
    episode_id INTEGER PRIMARY KEY AUTOINCREMENT,
    series_id INTEGER NOT NULL,
    episode_number_in_series INTEGER NOT NULL CHECK (episode_number_in_series >= 1),
    global_episode_number INTEGER NOT NULL UNIQUE CHECK (global_episode_number >= 1),
    youtube_title TEXT NOT NULL,
    summary TEXT NOT NULL,
    bespoke_asset_path TEXT NOT NULL,
    script_json TEXT NOT NULL,
    youtube_video_id TEXT UNIQUE,
    scheduled_publish_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('PUBLISHED', 'PRIVATE_REVIEW', 'FAILED')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (series_id) REFERENCES series(series_id) ON DELETE RESTRICT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_non_failed_episode_slot
    ON episodes (series_id, episode_number_in_series)
    WHERE status != 'FAILED';

CREATE INDEX IF NOT EXISTS idx_episodes_series_id
    ON episodes (series_id, episode_number_in_series);