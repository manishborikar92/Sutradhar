"""SQLite Schema v4 engine, idempotent migrations, pillar rotation & state commands."""

from __future__ import annotations

import contextlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Iterator, Optional

from pydantic import ValidationError

from sutradhar.config import (
    StateError,
    get_language_policy,
    load_json_file,
    resolve_paths,
)
from sutradhar.models import (
    EpisodePlan,
    NewSeriesPlan,
    PublishResult,
    count_billed_chars,
    emit_pacing_warnings,
    has_devanagari,
)

SCHEMA_VERSION = 4

SCHEMA_SQL = """
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
"""


# ---------------------------------------------------------------------------
# Low-level Connection & Transactions
# ---------------------------------------------------------------------------

def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}


def ensure_episodes_table_columns(conn: sqlite3.Connection) -> None:
    """Ensure non-destructive forward compatibility when opening an existing DB."""
    cur = conn.cursor()
    cur.execute("DROP INDEX IF EXISTS idx_single_active_series")
    tables = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "episodes" in tables:
        cols = _table_columns(conn, "episodes")
        if "content_format" not in cols:
            cur.execute("ALTER TABLE episodes ADD COLUMN content_format TEXT NOT NULL DEFAULT 'episodic_series'")
        if "research_sources_json" not in cols:
            cur.execute("ALTER TABLE episodes ADD COLUMN research_sources_json TEXT")


def connect_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    ensure_episodes_table_columns(conn)
    return conn


@contextlib.contextmanager
def immediate_transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Cursor]:
    cur = conn.cursor()
    cur.execute("BEGIN IMMEDIATE;")
    try:
        yield cur
    except Exception:
        cur.execute("ROLLBACK;")
        raise
    else:
        cur.execute("COMMIT;")


def _needs_v4_migration(conn: sqlite3.Connection) -> bool:
    user_ver = int(conn.execute("PRAGMA user_version").fetchone()[0])
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if not tables or ("series" not in tables and "episodes" not in tables):
        return False

    if user_ver < SCHEMA_VERSION:
        return True

    required_tables = {"series", "episodes", "publishing_history", "audio_ledger"}
    if not required_tables.issubset(tables):
        return True

    if not {"series_title_en", "series_title_hi", "metadata_language", "audio_language", "updated_at"}.issubset(
        _table_columns(conn, "series")
    ):
        return True

    if not {
        "legacy_asset_path",
        "video_url",
        "published_at",
        "duration_sec",
        "audio_language",
        "metadata_language",
        "thumbnail_asset_path",
        "video_asset_path",
        "file_bytes",
        "kinocut_score",
        "static_fraction",
        "tts_billed_chars",
        "visual_direction_version",
    }.issubset(_table_columns(conn, "episodes")):
        return True

    if not {
        "action",
        "previous_video_id",
        "notes",
        "cdn_thumbnail_url",
        "cdn_mae",
        "cdn_dhash_distance",
        "checks_json",
        "details_json",
        "created_at",
    }.issubset(_table_columns(conn, "publishing_history")):
        return True

    return False


def _transform_legacy_publishing_history_row(row: sqlite3.Row) -> tuple[Any, ...]:
    """Map v3 ad-hoc publishing_history rows (if present) into clean Schema v4 columns."""
    r = dict(row)
    action = r.get("action") or r.get("event_type") or "PUBLISHED"
    created_at = r.get("created_at") or r.get("recorded_at")
    previous_video_id = r.get("previous_video_id")

    raw_ver = r.get("verification_json")
    ver_obj: dict[str, Any] = {}
    if isinstance(raw_ver, str) and raw_ver.strip():
        try:
            ver_obj = json.loads(raw_ver)
        except json.JSONDecodeError:
            ver_obj = {"raw": raw_ver}

    if previous_video_id is None and action == "REPLACEMENT_PUBLISHED":
        previous_video_id = "Y63AyoTo-Jo"

    cdn_url = r.get("cdn_thumbnail_url") or ver_obj.get("cdn_url")
    cdn_mae = r.get("cdn_mae")
    cdn_dhash = r.get("cdn_dhash_distance")
    sim = ver_obj.get("similarity") or {}
    if cdn_mae is None and isinstance(sim, dict):
        cdn_mae = sim.get("mae")
    if cdn_dhash is None and isinstance(sim, dict):
        cdn_dhash = sim.get("dhash_distance")

    checks_json = r.get("checks_json")
    if checks_json is None and isinstance(ver_obj.get("checks"), dict):
        checks_json = json.dumps(ver_obj["checks"], ensure_ascii=False)

    details_json = r.get("details_json")
    if details_json is None:
        details = {
            k: v
            for k, v in {
                "global_episode_number": r.get("global_episode_number"),
                "series_id": r.get("series_id"),
                "youtube_title": r.get("youtube_title"),
                "metadata_language": r.get("metadata_language"),
                "audio_language": r.get("audio_language"),
                "tags": json.loads(r["tags_json"]) if isinstance(r.get("tags_json"), str) and r["tags_json"].startswith("[") else r.get("tags_json"),
                "video_url": r.get("video_url"),
                "video_asset_path": r.get("video_asset_path"),
                "thumbnail_asset_path": r.get("thumbnail_asset_path"),
                "deleted_at": r.get("deleted_at"),
                "replaced_by_video_id": r.get("replaced_by_video_id"),
                "verification": ver_obj if ver_obj else None,
            }.items()
            if v is not None
        }
        details_json = json.dumps(details, ensure_ascii=False) if details else None

    notes = r.get("notes")
    if notes is None and r.get("youtube_title"):
        notes = f"{action}: {r.get('youtube_title')}"

    return (
        r.get("history_id"),
        r["episode_id"],
        action,
        r["youtube_video_id"],
        previous_video_id,
        r.get("playlist_id"),
        r["status"],
        notes,
        cdn_url,
        cdn_mae,
        cdn_dhash,
        checks_json,
        details_json,
        created_at,
    )


def migrate_database_schema(conn: sqlite3.Connection) -> bool:
    """Idempotently migrate any v0-v3 Sutradhar database cleanly to Schema v4."""
    if not _needs_v4_migration(conn):
        return False

    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    existing_history: list[sqlite3.Row] = []
    if "publishing_history" in tables:
        existing_history = conn.execute("SELECT * FROM publishing_history ORDER BY history_id ASC").fetchall()

    conn.execute("PRAGMA foreign_keys = OFF;")
    conn.execute("BEGIN IMMEDIATE TRANSACTION;")
    try:
        conn.execute(
            """
            CREATE TABLE _v4_series (
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
            """
        )
        conn.execute(
            """
            CREATE TABLE _v4_episodes (
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
            """
        )
        conn.execute(
            """
            CREATE TABLE _v4_publishing_history (
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
            """
        )

        if "series" in tables:
            s_cols = _table_columns(conn, "series")
            target_s_cols = [
                c
                for c in (
                    "series_id",
                    "series_title",
                    "series_title_en",
                    "series_title_hi",
                    "pillar",
                    "tts_voice",
                    "bgm_track",
                    "metadata_language",
                    "audio_language",
                    "total_planned_episodes",
                    "completed_episodes",
                    "series_bible_json",
                    "youtube_playlist_id",
                    "status",
                    "created_at",
                    "updated_at",
                )
                if c in s_cols
            ]
            s_list = ", ".join(target_s_cols)
            conn.execute(f"INSERT INTO _v4_series ({s_list}) SELECT {s_list} FROM series;")

        if "episodes" in tables:
            e_cols = _table_columns(conn, "episodes")
            target_e_cols = [
                c
                for c in (
                    "episode_id",
                    "series_id",
                    "episode_number_in_series",
                    "global_episode_number",
                    "content_format",
                    "youtube_title",
                    "summary",
                    "bespoke_asset_path",
                    "legacy_asset_path",
                    "script_json",
                    "research_sources_json",
                    "youtube_video_id",
                    "video_url",
                    "scheduled_publish_at",
                    "published_at",
                    "duration_sec",
                    "audio_language",
                    "metadata_language",
                    "thumbnail_asset_path",
                    "video_asset_path",
                    "file_bytes",
                    "kinocut_score",
                    "static_fraction",
                    "tts_billed_chars",
                    "visual_direction_version",
                    "status",
                    "created_at",
                )
                if c in e_cols
            ]
            e_list = ", ".join(target_e_cols)
            conn.execute(f"INSERT INTO _v4_episodes ({e_list}) SELECT {e_list} FROM episodes;")

        for hrow in existing_history:
            conn.execute(
                """
                INSERT INTO _v4_publishing_history (
                    history_id, episode_id, action, youtube_video_id, previous_video_id,
                    playlist_id, status, notes, cdn_thumbnail_url, cdn_mae,
                    cdn_dhash_distance, checks_json, details_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _transform_legacy_publishing_history_row(hrow),
            )

        conn.execute("DROP TABLE IF EXISTS publishing_history;")
        conn.execute("DROP TABLE IF EXISTS episodes;")
        conn.execute("DROP TABLE IF EXISTS series;")
        conn.execute("ALTER TABLE _v4_series RENAME TO series;")
        conn.execute("ALTER TABLE _v4_episodes RENAME TO episodes;")
        conn.execute("ALTER TABLE _v4_publishing_history RENAME TO publishing_history;")

        conn.execute(
            """
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
            """
        )

        conn.execute("DROP INDEX IF EXISTS idx_unique_non_failed_episode_slot;")
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_non_failed_episode_slot
                ON episodes (series_id, episode_number_in_series)
                WHERE status NOT IN ('FAILED', 'SUPERSEDED') AND series_id IS NOT NULL;
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_episodes_series_id ON episodes (series_id, episode_number_in_series);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_episodes_global_number ON episodes (global_episode_number);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_publishing_history_episode_id ON publishing_history (episode_id, created_at);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_publishing_history_video_id ON publishing_history (youtube_video_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audio_ledger_sha256 ON audio_ledger (sha256_key);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audio_ledger_episode_id ON audio_ledger (episode_id, scene_index);")
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION};")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON;")

    return True


def ensure_db_initialized(db_path: Path) -> None:
    if not db_path.is_file():
        raise StateError(
            f"Database file not found at {db_path}. Run 'python scripts/db_manager.py --init' first."
        )
    conn = connect_db(db_path)
    try:
        migrate_database_schema(conn)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Historical Live DB Healing & Backfill (Episodes 1-4 & Series 1-3)
# ---------------------------------------------------------------------------

def heal_and_backfill_live_db(conn: sqlite3.Connection, root: Optional[Path] = None) -> dict[str, Any]:
    """Heals Series 1 counter, preserves Ep 1-4 legacy assets, and backfills publishing_history."""
    ep4_ver: dict[str, Any] = {}
    ep4_man: dict[str, Any] = {}
    cand_b_rep: dict[str, Any] = {}
    if root is not None:
        p4_v = root / "playground/ep4_neelakantha_shiva/ep4_publish_verification.json"
        if p4_v.is_file():
            ep4_ver = json.loads(p4_v.read_text(encoding="utf-8"))
        p4_m = root / "playground/ep4_neelakantha_shiva/audio/ep4_audio_manifest.json"
        if p4_m.is_file():
            ep4_man = json.loads(p4_m.read_text(encoding="utf-8"))
        pcb = root / "playground/candidate_b_ref1_cinematic/candidate_b_publish_report.json"
        if pcb.is_file():
            cand_b_rep = json.loads(pcb.read_text(encoding="utf-8"))

    series_repaired = 0
    assets_migrated = 0
    history_backfilled: list[str] = []

    with immediate_transaction(conn) as cur:
        # 1. Recompute accurate completed_episodes across all series (fixes Series 1: 0 -> 1)
        series_rows = cur.execute("SELECT series_id, completed_episodes, total_planned_episodes, status FROM series").fetchall()
        for srow in series_rows:
            cnt = int(
                cur.execute(
                    "SELECT COUNT(*) FROM episodes WHERE series_id = ? AND status IN ('PUBLISHED', 'PRIVATE_REVIEW')",
                    (srow["series_id"],),
                ).fetchone()[0]
            )
            new_status = srow["status"]
            if srow["total_planned_episodes"] is not None and cnt >= int(srow["total_planned_episodes"]):
                new_status = "COMPLETED"
            if cnt != int(srow["completed_episodes"]) or new_status != srow["status"]:
                cur.execute(
                    "UPDATE series SET completed_episodes = ?, status = ?, updated_at = CURRENT_TIMESTAMP WHERE series_id = ?",
                    (cnt, new_status, srow["series_id"]),
                )
                series_repaired += 1

        # Preserve Hindi titles in series_title_hi cleanly when title has Devanagari
        for srow in cur.execute("SELECT series_id, series_title, series_title_en, series_title_hi FROM series").fetchall():
            title = srow["series_title"]
            hi_title = srow["series_title_hi"] or (title if has_devanagari(title) else None)
            en_title = srow["series_title_en"] or (title if not has_devanagari(title) else None)
            cur.execute(
                "UPDATE series SET series_title_hi = ?, series_title_en = ?, updated_at = CURRENT_TIMESTAMP WHERE series_id = ?",
                (hi_title, en_title, srow["series_id"]),
            )

        # 2. Enrich Ep 1-4 metadata + preserve legacy SVG paths inside legacy_asset_path
        ep_metadata_overrides: dict[str, dict[str, Any]] = {
            "cd1cc1mhfwg": {
                "canonical_asset": "canvas_prop:shani_drishti_mandala",
                "duration_sec": 71.0,
                "file_bytes": 25213651,
                "metadata_language": "hi",
                "audio_language": "hi",
                "published_at": "2026-11-24T04:33:32Z",
                "visual_direction_version": "v1_legacy_svg",
            },
            "hcKmhzjQkz4": {
                "canonical_asset": "canvas_prop:mehrauli_iron_pillar",
                "duration_sec": 55.0,
                "file_bytes": 14501227,
                "metadata_language": "hi",
                "audio_language": "hi",
                "published_at": "2026-11-25T13:43:57Z",
                "visual_direction_version": "v1_legacy_svg",
            },
            "oBcyiPy26rg": {
                "canonical_asset": "canvas_prop:brahmaloka_time_chakra",
                "duration_sec": 63.533,
                "file_bytes": 36921509,
                "metadata_language": "en",
                "audio_language": "hi",
                "published_at": cand_b_rep.get("upload_timestamp_utc") or "2026-11-26T16:46:07Z",
                "video_asset_path": "playground/candidate_b_ref1_cinematic/candidate_b_ref1_cinematic.mp4",
                "thumbnail_asset_path": "playground/candidate_b_ref1_cinematic/candidate_b_ref1_cinematic_thumbnail.jpg",
                "kinocut_score": 89.4,
                "static_fraction": 0.4724,
                "visual_direction_version": "candidate_b_ref1",
            },
            "7PWFV7lQG6U": {
                "canonical_asset": "canvas_prop:samudra_manthan_halahala",
                "duration_sec": 61.967,
                "file_bytes": 553759709,
                "metadata_language": "en",
                "audio_language": "hi",
                "published_at": "2026-11-27T07:34:17Z",
                "video_asset_path": "playground/ep4_neelakantha_shiva/ep4_neelakantha_shiva.mp4",
                "thumbnail_asset_path": "playground/ep4_neelakantha_shiva/ep4_thumbnail.jpg",
                "kinocut_score": 94.0,
                "static_fraction": 0.0054,
                "tts_billed_chars": int(ep4_man.get("billed_chars") or 776),
                "visual_direction_version": "ep4_v2_preview",
            },
        }

        for ep_row in cur.execute("SELECT * FROM episodes ORDER BY episode_id").fetchall():
            vid = ep_row["youtube_video_id"]
            if not vid:
                continue
            ov = ep_metadata_overrides.get(vid, {})
            cur_asset = ep_row["bespoke_asset_path"]
            legacy_asset = ep_row["legacy_asset_path"]
            if cur_asset and cur_asset.startswith("assets/svg/") and not legacy_asset:
                legacy_asset = cur_asset
            canonical_asset = ov.get("canonical_asset") or cur_asset
            if cur_asset != canonical_asset:
                assets_migrated += 1

            sj = {}
            try:
                sj = json.loads(ep_row["script_json"])
            except json.JSONDecodeError:
                pass
            scene_chars = sum(len(s.get("narration_text", "")) for s in sj.get("scenes", []))
            tts_chars = ov.get("tts_billed_chars") or ep_row["tts_billed_chars"] or scene_chars

            cur.execute(
                """
                UPDATE episodes
                SET bespoke_asset_path = ?,
                    legacy_asset_path = COALESCE(legacy_asset_path, ?),
                    video_url = COALESCE(video_url, ?),
                    published_at = COALESCE(published_at, ?),
                    duration_sec = COALESCE(duration_sec, ?),
                    audio_language = ?,
                    metadata_language = ?,
                    thumbnail_asset_path = COALESCE(thumbnail_asset_path, ?),
                    video_asset_path = COALESCE(video_asset_path, ?),
                    file_bytes = COALESCE(file_bytes, ?),
                    kinocut_score = COALESCE(kinocut_score, ?),
                    static_fraction = COALESCE(static_fraction, ?),
                    tts_billed_chars = COALESCE(tts_billed_chars, ?),
                    visual_direction_version = COALESCE(?, visual_direction_version)
                WHERE episode_id = ?
                """,
                (
                    canonical_asset,
                    legacy_asset,
                    f"https://youtu.be/{vid}",
                    ov.get("published_at") or ep_row["created_at"],
                    ov.get("duration_sec") or sj.get("target_duration_sec"),
                    ov.get("audio_language", "hi"),
                    ov.get("metadata_language") or ("en" if not has_devanagari(ep_row["youtube_title"]) else "hi"),
                    ov.get("thumbnail_asset_path"),
                    ov.get("video_asset_path"),
                    ov.get("file_bytes"),
                    ov.get("kinocut_score"),
                    ov.get("static_fraction"),
                    tts_chars,
                    ov.get("visual_direction_version"),
                    ep_row["episode_id"],
                ),
            )

        # 3. Backfill missing publishing_history entries for Ep 1 (cd1cc1mhfwg), Ep 2 (hcKmhzjQkz4), Ep 4 (7PWFV7lQG6U)
        for ep_row in cur.execute(
            """
            SELECT e.*, s.youtube_playlist_id
            FROM episodes e
            LEFT JOIN series s ON e.series_id = s.series_id
            WHERE e.youtube_video_id IS NOT NULL
            ORDER BY e.episode_id ASC
            """
        ).fetchall():
            vid = ep_row["youtube_video_id"]
            exists = cur.execute(
                "SELECT 1 FROM publishing_history WHERE episode_id = ? AND youtube_video_id = ?",
                (ep_row["episode_id"], vid),
            ).fetchone()
            if exists is not None:
                continue

            if vid == "7PWFV7lQG6U":
                tver = ep4_ver.get("thumbnail_verification") or {}
                sim = tver.get("similarity") or {}
                checks = ep4_ver.get("checks") or {}
                cdn_url = tver.get("cdn_url") or f"https://i.ytimg.com/vi/{vid}/sardefault.jpg"
                cdn_mae = sim.get("mae", 0.273)
                cdn_dhash = sim.get("dhash_distance", 1)
                checks_json = json.dumps(checks, ensure_ascii=False) if checks else None
                details_json = json.dumps(
                    {
                        "backfilled_in": "schema_v4_phase1",
                        "youtube_title": ep_row["youtube_title"],
                        "metadata_language": "en",
                        "audio_language": "hi",
                        "video_asset_path": ep_row["video_asset_path"],
                        "thumbnail_asset_path": ep_row["thumbnail_asset_path"],
                        "verification": tver if tver else None,
                    },
                    ensure_ascii=False,
                )
                cur.execute(
                    """
                    INSERT INTO publishing_history (
                        episode_id, action, youtube_video_id, previous_video_id,
                        playlist_id, status, notes, cdn_thumbnail_url, cdn_mae,
                        cdn_dhash_distance, checks_json, details_json, created_at
                    ) VALUES (?, 'PUBLISHED', ?, NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ep_row["episode_id"],
                        vid,
                        ep_row["status"],
                        f"Ep {ep_row['global_episode_number']} standalone upload + sardefault.jpg CDN verified",
                        cdn_url,
                        cdn_mae,
                        cdn_dhash,
                        checks_json,
                        details_json,
                        ep_row["published_at"] or ep_row["created_at"],
                    ),
                )
            else:
                details_json = json.dumps(
                    {
                        "backfilled_in": "schema_v4_phase1",
                        "youtube_title": ep_row["youtube_title"],
                        "metadata_language": ep_row["metadata_language"],
                        "audio_language": ep_row["audio_language"],
                        "legacy_baseline": True,
                    },
                    ensure_ascii=False,
                )
                cur.execute(
                    """
                    INSERT INTO publishing_history (
                        episode_id, action, youtube_video_id, previous_video_id,
                        playlist_id, status, notes, details_json, created_at
                    ) VALUES (?, 'PUBLISHED', ?, NULL, ?, ?, ?, ?, ?)
                    """,
                    (
                        ep_row["episode_id"],
                        vid,
                        ep_row["youtube_playlist_id"],
                        ep_row["status"],
                        f"Backfilled historical Ep {ep_row['global_episode_number']} upload (legacy baseline)",
                        details_json,
                        ep_row["published_at"] or ep_row["created_at"],
                    ),
                )
            history_backfilled.append(vid)

    return {
        "series_repaired": series_repaired,
        "assets_migrated": assets_migrated,
        "history_backfilled": history_backfilled,
    }


# ---------------------------------------------------------------------------
# Context, Pillar Rotation & CLI Command Functions
# ---------------------------------------------------------------------------

def _list_svg_stems(directory: Path) -> list[str]:
    if not directory.is_dir():
        return []
    return sorted(p.stem for p in directory.iterdir() if p.is_file() and p.suffix.lower() == ".svg")


def _list_audio_files(directory: Path) -> list[str]:
    if not directory.is_dir():
        return []
    valid_ext = {".mp3", ".wav", ".ogg", ".flac"}
    return sorted(p.name for p in directory.iterdir() if p.is_file() and p.suffix.lower() in valid_ext)


def _row_to_active_series(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    try:
        bible_parsed: Any = json.loads(row["series_bible_json"])
    except json.JSONDecodeError:
        bible_parsed = row["series_bible_json"]

    ep_rows = conn.execute(
        """
        SELECT episode_number_in_series, global_episode_number, youtube_title,
               summary, bespoke_asset_path, legacy_asset_path, youtube_video_id, status
        FROM episodes
        WHERE series_id = ? AND status NOT IN ('FAILED', 'SUPERSEDED')
        ORDER BY episode_number_in_series ASC
        """,
        (row["series_id"],),
    ).fetchall()

    rdict = dict(row)
    return {
        "series_id": rdict["series_id"],
        "series_title": rdict["series_title"],
        "series_title_en": rdict.get("series_title_en"),
        "series_title_hi": rdict.get("series_title_hi"),
        "pillar": rdict["pillar"],
        "tts_voice": rdict["tts_voice"],
        "bgm_track": rdict["bgm_track"],
        "total_planned_episodes": rdict["total_planned_episodes"],
        "completed_episodes": rdict["completed_episodes"],
        "series_bible_json": bible_parsed,
        "youtube_playlist_id": rdict["youtube_playlist_id"],
        "status": rdict["status"],
        "created_at": rdict["created_at"],
        "completed_episode_summaries": [dict(ep) for ep in ep_rows],
    }


def compute_pillar_rotation(conn: sqlite3.Connection, pillars: list[str]) -> tuple[Optional[str], Optional[str]]:
    """Compute (last_completed_pillar, next_pillar) across both finite and open-ended series."""
    latest_ep = conn.execute(
        """
        SELECT e.episode_id, e.series_id, s.pillar AS series_pillar,
               json_extract(e.script_json, '$.pillar') AS script_pillar
        FROM episodes e
        LEFT JOIN series s ON e.series_id = s.series_id
        WHERE e.status IN ('PUBLISHED', 'PRIVATE_REVIEW')
        ORDER BY e.global_episode_number DESC, e.episode_id DESC
        LIMIT 1
        """
    ).fetchone()

    last_pillar: Optional[str] = None
    if latest_ep is not None:
        last_pillar = latest_ep["series_pillar"] or latest_ep["script_pillar"]

    if last_pillar is None:
        completed_row = conn.execute(
            "SELECT pillar FROM series WHERE status = 'COMPLETED' ORDER BY series_id DESC LIMIT 1"
        ).fetchone()
        if completed_row is not None:
            last_pillar = completed_row["pillar"]

    if not pillars:
        return last_pillar, None
    if last_pillar in pillars:
        idx = pillars.index(last_pillar)
        return last_pillar, pillars[(idx + 1) % len(pillars)]
    return last_pillar, pillars[0]


def cmd_init(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    paths = resolve_paths(root, cfg)
    db_path = paths["db_file"]
    db_path.parent.mkdir(parents=True, exist_ok=True)
    paths["build_dir"].mkdir(parents=True, exist_ok=True)

    conn = connect_db(db_path)
    try:
        migrated = migrate_database_schema(conn)
        with immediate_transaction(conn) as cur:
            for statement in SCHEMA_SQL.strip().split(";"):
                stmt = statement.strip()
                if stmt:
                    cur.execute(stmt)
        user_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
    finally:
        conn.close()

    return {
        "status": "ok",
        "action": "init",
        "db_file": str(db_path),
        "schema_version": user_version,
        "migrated": migrated,
        "tables": ["series", "episodes", "publishing_history", "audio_ledger"],
    }


def cmd_context(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    paths = resolve_paths(root, cfg)
    db_path = paths["db_file"]
    ensure_db_initialized(db_path)

    history_limit = int(cfg["series"].get("completed_history_window", 20))
    assets_dir = paths["assets_dir"]
    pillars = cfg["channel"]["pillars"]
    policy = get_language_policy(cfg)

    conn = connect_db(db_path)
    try:
        active_rows = conn.execute(
            "SELECT * FROM series WHERE status = 'ACTIVE' ORDER BY series_id ASC"
        ).fetchall()

        active_series_list = [_row_to_active_series(conn, r) for r in active_rows]
        active_series = active_series_list[-1] if active_series_list else None

        next_global_row = conn.execute(
            "SELECT COALESCE(MAX(global_episode_number), 0) + 1 AS next_global "
            "FROM episodes WHERE status NOT IN ('FAILED', 'SUPERSEDED')"
        ).fetchone()
        next_global = int(next_global_row["next_global"])

        if active_series is not None:
            next_in_series = int(active_series["completed_episodes"]) + 1
            if (
                active_series["total_planned_episodes"] is not None
                and next_in_series > int(active_series["total_planned_episodes"])
            ):
                raise StateError(
                    f"Active series {active_series['series_id']} has completed_episodes "
                    f"({active_series['completed_episodes']}) >= total_planned_episodes "
                    f"({active_series['total_planned_episodes']}) but is still ACTIVE."
                )
        else:
            next_in_series = 1

        completed_rows = conn.execute(
            """
            SELECT series_id, series_title, series_title_en, series_title_hi, pillar,
                   total_planned_episodes, completed_episodes, youtube_playlist_id, created_at
            FROM series
            WHERE status = 'COMPLETED'
            ORDER BY series_id DESC
            LIMIT ?
            """,
            (history_limit,),
        ).fetchall()
        completed_history = [dict(r) for r in completed_rows]

        last_completed_pillar, next_pillar = compute_pillar_rotation(conn, pillars)

        bespoke_rows = conn.execute(
            "SELECT bespoke_asset_path FROM episodes WHERE status NOT IN ('FAILED', 'SUPERSEDED') ORDER BY episode_id ASC"
        ).fetchall()
        previous_bespoke_assets = [r["bespoke_asset_path"] for r in bespoke_rows]

        topic_rows = conn.execute(
            """
            SELECT episode_id, series_id, global_episode_number, youtube_title, summary,
                   content_format, youtube_video_id, scheduled_publish_at
            FROM episodes
            WHERE status NOT IN ('FAILED', 'SUPERSEDED')
            ORDER BY episode_id DESC
            LIMIT 30
            """
        ).fetchall()
        previously_covered_topics = [dict(r) for r in topic_rows]

        private_review_count = int(
            conn.execute("SELECT COUNT(*) FROM episodes WHERE status = 'PRIVATE_REVIEW'").fetchone()[0]
        )

        # Monthly TTS credit accounting from audio_ledger
        tts_row = conn.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN cache_hit = 0 THEN billed_chars ELSE 0 END), 0) AS spent_chars,
                COALESCE(SUM(CASE WHEN cache_hit = 1 THEN 1 ELSE 0 END), 0) AS cache_hits,
                COUNT(*) AS total_rows
            FROM audio_ledger
            WHERE strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')
            """
        ).fetchone()
        monthly_limit = int(cfg.get("tts", {}).get("monthly_credit_budget", 30000))
        spent_chars = int(tts_row["spent_chars"]) if tts_row else 0
        monthly_tts_budget = {
            "monthly_limit": monthly_limit,
            "spent_this_month_billed_chars": spent_chars,
            "remaining_credits": max(0, monthly_limit - spent_chars),
            "cache_hits_this_month": int(tts_row["cache_hits"]) if tts_row else 0,
            "max_billed_chars_per_episode": int(cfg.get("tts", {}).get("max_billed_chars_per_episode", 900)),
            "target_billed_chars_range": [
                int(cfg.get("tts", {}).get("target_billed_chars_min", 760)),
                int(cfg.get("tts", {}).get("target_billed_chars_max", 840)),
            ],
        }
    finally:
        conn.close()

    content_format = cfg.get("content_format") or cfg.get("content", {}).get("format", "episodic_series")
    pacing = cfg["episode_pacing"]

    return {
        "schema_version": SCHEMA_VERSION,
        "language_policy": policy.model_dump(),
        "next_pillar": next_pillar,
        "last_completed_pillar": last_completed_pillar,
        "monthly_tts_budget": monthly_tts_budget,
        "channel_config": {
            "language_mode": cfg["channel"]["language_mode"],
            "primary_language": cfg["channel"]["primary_language"],
            "audio_language": policy.audio_language,
            "caption_language": policy.caption_language,
            "metadata_language": policy.metadata_language,
            "thumbnail_language": policy.thumbnail_language,
            "locked_voice_profile": cfg["languages"].get(cfg["channel"]["primary_language"]) if "languages" in cfg else None,
            "pillars": pillars,
            "tts_engine": cfg["tts"]["engine"],
            "tts_voice": cfg["tts"]["default_voice"],
            "upload_mode": cfg["publishing"]["upload_mode"],
            "allow_public_or_scheduled": cfg["publishing"]["allow_public_or_scheduled"],
            "calibration_episodes_required": cfg["publishing"].get("calibration_episodes_required", 0),
            "completed_private_review_episodes": private_review_count,
            "min_episodes": cfg.get("series", {}).get("min_episodes"),
            "max_episodes": cfg.get("series", {}).get("max_episodes"),
            "bgm_by_pillar": cfg["assets"]["bgm_by_pillar"],
            "mood_palettes": cfg["assets"]["mood_palettes"],
            "particle_themes": cfg["assets"]["particle_themes"],
            "content_format": content_format,
            "episode_pacing": pacing,
        },
        "content_format": content_format,
        "can_plan_standalone": True,
        "active_series": active_series,
        "active_series_list": active_series_list,
        "previously_covered_topics": previously_covered_topics,
        "next_episode_number_in_series": next_in_series,
        "next_global_episode_number": next_global,
        "completed_series_history": completed_history,
        "previous_bespoke_assets": previous_bespoke_assets,
        "available_rigs": {
            "characters": _list_svg_stems(assets_dir / "svg" / "characters"),
            "backdrops": _list_svg_stems(assets_dir / "svg" / "backdrops"),
            "bgm": _list_audio_files(assets_dir / "audio" / "bgm") or _list_audio_files(assets_dir / "bgm"),
            "sfx": _list_audio_files(assets_dir / "audio" / "sfx") or _list_audio_files(assets_dir / "sfx"),
        },
    }


def cmd_create_series(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    paths = resolve_paths(root, cfg)
    db_path = paths["db_file"]
    ensure_db_initialized(db_path)

    plan_path = paths["build_dir"] / "new_series_plan.json"
    raw_plan = load_json_file(plan_path, "new_series_plan.json")
    try:
        plan = NewSeriesPlan.model_validate(raw_plan, context={"config": cfg})
    except ValidationError as exc:
        raise StateError(f"new_series_plan.json validation failed:\n{exc}") from exc

    policy = get_language_policy(cfg)
    conn = connect_db(db_path)
    try:
        with immediate_transaction(conn) as cur:
            dup = cur.execute(
                "SELECT series_id FROM series WHERE LOWER(series_title) = LOWER(?)",
                (plan.series_title,),
            ).fetchone()
            if dup is not None:
                raise StateError(
                    f"A series titled '{plan.series_title}' already exists (series_id={dup['series_id']})."
                )

            pillars = cfg["channel"]["pillars"]
            if len(pillars) > 1:
                last_pillar, _ = compute_pillar_rotation(conn, pillars)
                if last_pillar is not None and last_pillar == plan.pillar:
                    raise StateError(
                        f"Pillar rotation violation: cannot repeat immediately preceding pillar '{plan.pillar}'."
                    )

            for ep in plan.series_bible_json.episodes:
                used = cur.execute(
                    "SELECT episode_id FROM episodes WHERE bespoke_asset_path = ? AND status NOT IN ('FAILED', 'SUPERSEDED')",
                    (ep.planned_bespoke_asset,),
                ).fetchone()
                if used is not None:
                    raise StateError(
                        f"Series bible episode {ep.episode_number} planned_bespoke_asset "
                        f"'{ep.planned_bespoke_asset}' was already used by episode_id={used['episode_id']}."
                    )

            en_title = plan.series_title if not has_devanagari(plan.series_title) else None
            hi_title = plan.series_title_hi or (plan.series_title if has_devanagari(plan.series_title) else None)
            cur.execute(
                """
                INSERT INTO series (
                    series_title, series_title_en, series_title_hi, pillar, tts_voice, bgm_track,
                    metadata_language, audio_language, total_planned_episodes, completed_episodes,
                    series_bible_json, youtube_playlist_id, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, NULL, 'ACTIVE')
                """,
                (
                    plan.series_title,
                    en_title,
                    hi_title,
                    plan.pillar,
                    plan.tts_voice,
                    plan.bgm_track,
                    policy.metadata_language,
                    policy.audio_language,
                    plan.total_planned_episodes,
                    plan.serialized_bible(),
                ),
            )
            new_series_id = int(cur.lastrowid)
    except sqlite3.IntegrityError as exc:
        raise StateError(f"SQLite integrity error while creating series: {exc}") from exc
    finally:
        conn.close()

    return {
        "status": "ok",
        "action": "create_series",
        "series_id": new_series_id,
        "series_title": plan.series_title,
        "pillar": plan.pillar,
        "total_planned_episodes": plan.total_planned_episodes,
        "series_status": "ACTIVE",
    }


def cmd_record_published(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    paths = resolve_paths(root, cfg)
    db_path = paths["db_file"]
    ensure_db_initialized(db_path)

    ep_path = paths["build_dir"] / "episode_plan.json"
    pub_path = paths["build_dir"] / "publish_result.json"

    raw_ep = load_json_file(ep_path, "episode_plan.json")
    raw_pub = load_json_file(pub_path, "publish_result.json")

    try:
        ep_plan = EpisodePlan.model_validate(raw_ep, context={"config": cfg})
    except ValidationError as exc:
        raise StateError(f"episode_plan.json validation failed:\n{exc}") from exc

    try:
        pub_res = PublishResult.model_validate(raw_pub, context={"config": cfg})
    except ValidationError as exc:
        raise StateError(f"publish_result.json validation failed:\n{exc}") from exc

    emit_pacing_warnings(ep_plan, cfg)
    billed_chars = count_billed_chars(ep_plan.scenes)
    meta_lang = ep_plan.metadata_language or ("en" if not has_devanagari(ep_plan.youtube_title) else "hi")
    aud_lang = ep_plan.audio_language or ep_plan.language or "hi"

    conn = connect_db(db_path)
    try:
        with immediate_transaction(conn) as cur:
            fmt = ep_plan.content_format or "serial"

            if fmt == "standalone":
                next_global_row = cur.execute(
                    "SELECT COALESCE(MAX(global_episode_number), 0) + 1 AS next_global "
                    "FROM episodes WHERE status NOT IN ('FAILED', 'SUPERSEDED')"
                ).fetchone()
                expected_global = int(next_global_row["next_global"])
                if ep_plan.global_episode_number != expected_global:
                    raise StateError(
                        f"Expected global_episode_number={expected_global}, got {ep_plan.global_episode_number}."
                    )

                dup_bespoke = cur.execute(
                    "SELECT episode_id FROM episodes WHERE bespoke_asset_path = ? AND status NOT IN ('FAILED', 'SUPERSEDED')",
                    (ep_plan.bespoke_asset_path,),
                ).fetchone()
                if dup_bespoke is not None:
                    raise StateError(
                        f"bespoke_asset_path '{ep_plan.bespoke_asset_path}' was already used "
                        f"by episode_id={dup_bespoke['episode_id']}."
                    )

                script_json_str = json.dumps(ep_plan.model_dump(), ensure_ascii=False)
                research_json_str = (
                    json.dumps(ep_plan.story_research.model_dump(exclude_none=True), ensure_ascii=False)
                    if ep_plan.story_research
                    else None
                )
                cur.execute(
                    """
                    INSERT INTO episodes (
                        series_id, episode_number_in_series, global_episode_number,
                        content_format, youtube_title, summary, bespoke_asset_path, script_json,
                        research_sources_json, youtube_video_id, video_url, scheduled_publish_at,
                        duration_sec, audio_language, metadata_language, tts_billed_chars, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        None,
                        None,
                        ep_plan.global_episode_number,
                        "standalone",
                        ep_plan.youtube_title,
                        ep_plan.summary,
                        ep_plan.bespoke_asset_path,
                        script_json_str,
                        research_json_str,
                        pub_res.video_id,
                        pub_res.video_url,
                        pub_res.scheduled_publish_at,
                        ep_plan.target_duration_sec,
                        aud_lang,
                        meta_lang,
                        billed_chars,
                        pub_res.upload_status,
                    ),
                )
                episode_id = int(cur.lastrowid)
                if pub_res.video_id:
                    cur.execute(
                        """
                        INSERT INTO publishing_history (
                            episode_id, action, youtube_video_id, playlist_id, status, notes
                        ) VALUES (?, ?, ?, NULL, ?, ?)
                        """,
                        (
                            episode_id,
                            pub_res.upload_status,
                            pub_res.video_id,
                            pub_res.upload_status,
                            ep_plan.youtube_title,
                        ),
                    )

                return {
                    "status": "ok",
                    "action": "record_published",
                    "episode_id": episode_id,
                    "series_id": None,
                    "content_format": "standalone",
                    "episode_number_in_series": None,
                    "global_episode_number": ep_plan.global_episode_number,
                    "episode_status": pub_res.upload_status,
                    "youtube_video_id": pub_res.video_id,
                    "youtube_playlist_id": None,
                    "completed_episodes": None,
                    "total_planned_episodes": None,
                    "series_status": None,
                }

            if ep_plan.series_id is None:
                raise StateError("episode_plan.series_id is required for episodic series.")

            active = cur.execute(
                "SELECT * FROM series WHERE series_id = ? AND status = 'ACTIVE'",
                (ep_plan.series_id,),
            ).fetchone()
            if active is None:
                raise StateError(f"No ACTIVE series exists with series_id={ep_plan.series_id}; cannot record episode.")

            if active["series_title"] != ep_plan.series_title:
                raise StateError(
                    f"episode_plan.series_title ('{ep_plan.series_title}') does not match "
                    f"ACTIVE series_title ('{active['series_title']}')."
                )
            if active["pillar"] != ep_plan.pillar:
                raise StateError(
                    f"episode_plan.pillar ('{ep_plan.pillar}') does not match "
                    f"ACTIVE series pillar ('{active['pillar']}')."
                )
            if ep_plan.total_planned_episodes is not None and active["total_planned_episodes"] is not None:
                if int(active["total_planned_episodes"]) != ep_plan.total_planned_episodes:
                    raise StateError(
                        f"episode_plan.total_planned_episodes ({ep_plan.total_planned_episodes}) "
                        f"does not match ACTIVE series ({active['total_planned_episodes']})."
                    )
            if active["tts_voice"] != ep_plan.tts_voice:
                raise StateError(
                    f"episode_plan.tts_voice ('{ep_plan.tts_voice}') does not match "
                    f"ACTIVE series tts_voice ('{active['tts_voice']}')."
                )
            if active["bgm_track"] != ep_plan.bgm_track:
                raise StateError(
                    f"episode_plan.bgm_track ('{ep_plan.bgm_track}') does not match "
                    f"ACTIVE series bgm_track ('{active['bgm_track']}')."
                )

            expected_in_series = int(active["completed_episodes"]) + 1
            if ep_plan.episode_number_in_series != expected_in_series:
                raise StateError(
                    f"Expected episode_number_in_series={expected_in_series}, got {ep_plan.episode_number_in_series}."
                )

            next_global_row = cur.execute(
                "SELECT COALESCE(MAX(global_episode_number), 0) + 1 AS next_global "
                "FROM episodes WHERE status NOT IN ('FAILED', 'SUPERSEDED')"
            ).fetchone()
            expected_global = int(next_global_row["next_global"])
            if ep_plan.global_episode_number != expected_global:
                raise StateError(
                    f"Expected global_episode_number={expected_global}, got {ep_plan.global_episode_number}."
                )

            dup_bespoke = cur.execute(
                """
                SELECT episode_id FROM episodes
                WHERE bespoke_asset_path = ?
                  AND NOT (series_id = ? AND episode_number_in_series = ? AND status = 'FAILED')
                  AND status != 'SUPERSEDED'
                """,
                (ep_plan.bespoke_asset_path, ep_plan.series_id, ep_plan.episode_number_in_series),
            ).fetchone()
            if dup_bespoke is not None:
                raise StateError(
                    f"bespoke_asset_path '{ep_plan.bespoke_asset_path}' was already used "
                    f"by episode_id={dup_bespoke['episode_id']}."
                )

            existing_playlist_id = active["youtube_playlist_id"]
            final_playlist_id = existing_playlist_id
            if pub_res.playlist_id:
                if existing_playlist_id is None:
                    cur.execute(
                        "UPDATE series SET youtube_playlist_id = ?, updated_at = CURRENT_TIMESTAMP WHERE series_id = ?",
                        (pub_res.playlist_id, ep_plan.series_id),
                    )
                    final_playlist_id = pub_res.playlist_id
                elif existing_playlist_id != pub_res.playlist_id:
                    raise StateError(
                        f"Playlist mismatch for series #{ep_plan.series_id}: "
                        f"stored='{existing_playlist_id}', publish_result='{pub_res.playlist_id}'."
                    )

            cur.execute(
                "DELETE FROM episodes WHERE series_id = ? AND episode_number_in_series = ? AND status = 'FAILED'",
                (ep_plan.series_id, ep_plan.episode_number_in_series),
            )

            script_json_str = json.dumps(ep_plan.model_dump(), ensure_ascii=False)
            research_json_str = (
                json.dumps(ep_plan.story_research.model_dump(exclude_none=True), ensure_ascii=False)
                if ep_plan.story_research
                else None
            )
            cur.execute(
                """
                INSERT INTO episodes (
                    series_id, episode_number_in_series, global_episode_number,
                    content_format, youtube_title, summary, bespoke_asset_path, script_json,
                    research_sources_json, youtube_video_id, video_url, scheduled_publish_at,
                    duration_sec, audio_language, metadata_language, tts_billed_chars, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ep_plan.series_id,
                    ep_plan.episode_number_in_series,
                    ep_plan.global_episode_number,
                    fmt,
                    ep_plan.youtube_title,
                    ep_plan.summary,
                    ep_plan.bespoke_asset_path,
                    script_json_str,
                    research_json_str,
                    pub_res.video_id,
                    pub_res.video_url,
                    pub_res.scheduled_publish_at,
                    ep_plan.target_duration_sec,
                    aud_lang,
                    meta_lang,
                    billed_chars,
                    pub_res.upload_status,
                ),
            )
            episode_id = int(cur.lastrowid)

            if pub_res.video_id:
                cur.execute(
                    """
                    INSERT INTO publishing_history (
                        episode_id, action, youtube_video_id, playlist_id, status, notes
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        episode_id,
                        pub_res.upload_status,
                        pub_res.video_id,
                        final_playlist_id,
                        pub_res.upload_status,
                        ep_plan.youtube_title,
                    ),
                )

            new_completed = int(active["completed_episodes"])
            new_series_status = str(active["status"])
            if pub_res.upload_status in ("PUBLISHED", "PRIVATE_REVIEW"):
                new_completed += 1
                if active["total_planned_episodes"] is not None and new_completed == int(active["total_planned_episodes"]):
                    new_series_status = "COMPLETED"
                cur.execute(
                    "UPDATE series SET completed_episodes = ?, status = ?, updated_at = CURRENT_TIMESTAMP WHERE series_id = ?",
                    (new_completed, new_series_status, ep_plan.series_id),
                )
    except sqlite3.IntegrityError as exc:
        raise StateError(f"SQLite integrity error while recording episode: {exc}") from exc
    finally:
        conn.close()

    return {
        "status": "ok",
        "action": "record_published",
        "episode_id": episode_id,
        "series_id": ep_plan.series_id,
        "content_format": fmt,
        "episode_number_in_series": ep_plan.episode_number_in_series,
        "global_episode_number": ep_plan.global_episode_number,
        "episode_status": pub_res.upload_status,
        "youtube_video_id": pub_res.video_id,
        "youtube_playlist_id": final_playlist_id,
        "completed_episodes": new_completed,
        "total_planned_episodes": ep_plan.total_planned_episodes,
        "series_status": new_series_status,
    }


def cmd_repair(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    """Repair derived DB counters, run Schema v4 healing/backfill, and verify FK integrity."""
    paths = resolve_paths(root, cfg)
    db_path = paths["db_file"]
    ensure_db_initialized(db_path)

    conn = connect_db(db_path)
    try:
        migrated = migrate_database_schema(conn)
        heal_stats = heal_and_backfill_live_db(conn, root=root)
        fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        conn.close()

    if integrity != "ok" or fk_violations:
        raise StateError(f"Database integrity check failed after repair: integrity={integrity}, fk={len(fk_violations)}")

    return {
        "status": "ok",
        "action": "repair",
        "schema_version": SCHEMA_VERSION,
        "migrated": migrated,
        "integrity": integrity,
        **heal_stats,
    }
