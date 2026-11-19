#!/usr/bin/env python3
"""Sutradhar SQLite state machine and Pydantic schema validator.

Fixed zero-argument CLI commands (for Antigravity /automation whitelist):
    python scripts/db_manager.py --init
    python scripts/db_manager.py --context
    python scripts/db_manager.py --create-series
    python scripts/db_manager.py --record-published
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Literal, Optional

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)

# ---------------------------------------------------------------------------
# Constants & Validation Patterns
# ---------------------------------------------------------------------------

VOICE_ID_RE = re.compile(r"^[a-z]{2}_[a-z0-9_]+$")
RIG_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
AUDIO_FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.(mp3|wav|ogg|flac)$")
BESPOKE_ASSET_PREFIXES = (
    "assets/svg/diagrams/",
    "assets/svg/backdrops/",
    "assets/svg/characters/",
)

ALLOWED_EMOTIONS = ("calm", "wrath", "shock", "smirk", "meditating")
ALLOWED_GESTURES = (
    "idle_breathe",
    "raise_weapon",
    "point_accuse",
    "bless_hand",
    "tremble",
)

SCHEMA_SQL = """
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
"""


class StateError(RuntimeError):
    """Raised when a database invariant or state-machine transition is violated."""


# ---------------------------------------------------------------------------
# Workspace & Configuration Helpers
# ---------------------------------------------------------------------------

def get_project_root() -> Path:
    """Resolve repository root (supports SUTRADHAR_ROOT override for isolated tests)."""
    env_root = os.environ.get("SUTRADHAR_ROOT")
    if env_root:
        return Path(env_root).resolve()
    return Path(__file__).resolve().parent.parent


def load_config(root: Path) -> dict[str, Any]:
    config_path = root / "config.yaml"
    if not config_path.is_file():
        raise StateError(f"Missing configuration file: {config_path}")
    with config_path.open("r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    if not isinstance(cfg, dict):
        raise StateError(f"Invalid YAML structure in {config_path}")
    required_sections = ("channel", "series", "episode_pacing", "tts", "assets", "publishing", "paths")
    missing = [sec for sec in required_sections if sec not in cfg]
    if missing:
        raise StateError(f"config.yaml missing required sections: {', '.join(missing)}")
    return cfg


def resolve_paths(root: Path, cfg: dict[str, Any]) -> dict[str, Path]:
    paths_cfg = cfg["paths"]
    return {
        "db_file": (root / paths_cfg["db_file"]).resolve(),
        "build_dir": (root / paths_cfg["build_dir"]).resolve(),
        "assets_dir": (root / paths_cfg["assets_dir"]).resolve(),
    }


def load_json_file(path: Path, label: str) -> Any:
    if not path.is_file():
        raise StateError(f"Required input file not found ({label}): {path}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        raise StateError(f"Malformed JSON in {path}: {exc}") from exc


# ---------------------------------------------------------------------------
# Shared Field Validators
# ---------------------------------------------------------------------------

def _validate_kokoro_voice(value: str) -> str:
    voice = value.strip()
    if not voice:
        raise ValueError("tts_voice must not be empty")
    if "+" in voice:
        parts = voice.split("+")
        if len(parts) < 2:
            raise ValueError(f"Invalid voice blend syntax: '{voice}'")
        total_weight = 0.0
        for part in parts:
            if ":" not in part:
                raise ValueError(
                    f"Voice blend component '{part}' must use 'voice_id:weight' format"
                )
            vid, raw_weight = part.split(":", 1)
            if not VOICE_ID_RE.match(vid):
                raise ValueError(f"Invalid Kokoro voice ID '{vid}' in blend '{voice}'")
            try:
                weight = float(raw_weight)
            except ValueError as exc:
                raise ValueError(f"Invalid blend weight '{raw_weight}' in '{voice}'") from exc
            if weight <= 0:
                raise ValueError(f"Blend weight must be > 0 in '{voice}'")
            total_weight += weight
        if not (0.95 <= total_weight <= 1.05):
            raise ValueError(
                f"Voice blend weights must sum to ~1.0 (got {total_weight:.3f}) in '{voice}'"
            )
        return voice

    if not VOICE_ID_RE.match(voice):
        raise ValueError(
            f"Invalid Kokoro voice ID '{voice}' (expected format like 'am_fenrir' "
            "or blend 'am_fenrir:0.65+bm_george:0.35')"
        )
    return voice


def _validate_audio_filename(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if "/" in cleaned or "\\" in cleaned or ".." in cleaned:
        raise ValueError(f"{field_name} must be a plain filename without path separators")
    if not AUDIO_FILENAME_RE.match(cleaned):
        raise ValueError(
            f"{field_name} '{cleaned}' must be a valid audio filename (.mp3/.wav/.ogg/.flac)"
        )
    return cleaned


def _validate_rig_slug(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not RIG_SLUG_RE.match(cleaned):
        raise ValueError(
            f"{field_name} '{cleaned}' must be a lowercase slug without '.svg' or path separators"
        )
    return cleaned


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class NewSeriesPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    series_title: str = Field(..., min_length=3, max_length=150)
    pillar: str = Field(..., min_length=2, max_length=100)
    tts_voice: str = Field(..., min_length=4, max_length=120)
    bgm_track: str = Field(..., min_length=5, max_length=120)
    total_planned_episodes: int
    series_bible_json: dict[str, Any] | list[Any] | str

    @field_validator("pillar")
    @classmethod
    def check_pillar(cls, v: str, info: ValidationInfo) -> str:
        cfg = (info.context or {}).get("config")
        if cfg:
            allowed = cfg["channel"]["pillars"]
            if v not in allowed:
                raise ValueError(f"pillar '{v}' is not in configured pillars: {allowed}")
        return v

    @field_validator("tts_voice")
    @classmethod
    def check_tts_voice(cls, v: str) -> str:
        return _validate_kokoro_voice(v)

    @field_validator("bgm_track")
    @classmethod
    def check_bgm_track(cls, v: str) -> str:
        return _validate_audio_filename(v, "bgm_track")

    @field_validator("total_planned_episodes")
    @classmethod
    def check_episode_count(cls, v: int, info: ValidationInfo) -> int:
        cfg = (info.context or {}).get("config")
        min_ep = cfg["series"]["min_episodes"] if cfg else 3
        max_ep = cfg["series"]["max_episodes"] if cfg else 6
        if not (min_ep <= v <= max_ep):
            raise ValueError(
                f"total_planned_episodes must be between {min_ep} and {max_ep} (got {v})"
            )
        return v

    @field_validator("series_bible_json")
    @classmethod
    def parse_series_bible(cls, v: dict[str, Any] | list[Any] | str) -> dict[str, Any] | list[Any]:
        parsed: Any = v
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
            except json.JSONDecodeError as exc:
                raise ValueError(f"series_bible_json string is not valid JSON: {exc}") from exc
        if not isinstance(parsed, (dict, list)) or len(parsed) == 0:
            raise ValueError("series_bible_json must be a non-empty JSON object or array")
        return parsed

    @model_validator(mode="after")
    def validate_bible_episode_alignment(self) -> "NewSeriesPlan":
        bible = self.series_bible_json
        if isinstance(bible, list):
            if len(bible) != self.total_planned_episodes:
                raise ValueError(
                    f"series_bible_json array length ({len(bible)}) must match "
                    f"total_planned_episodes ({self.total_planned_episodes})"
                )
        elif isinstance(bible, dict) and "episodes" in bible:
            episodes_list = bible["episodes"]
            if not isinstance(episodes_list, list) or len(episodes_list) != self.total_planned_episodes:
                raise ValueError(
                    "series_bible_json['episodes'] must be a list matching "
                    f"total_planned_episodes ({self.total_planned_episodes})"
                )
        return self

    def serialized_bible(self) -> str:
        return json.dumps(self.series_bible_json, ensure_ascii=False)


class ScenePlan(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    scene_index: int = Field(..., ge=1)
    narration_text: str = Field(..., min_length=5)
    caption_text: str = Field(..., min_length=5)
    visual_mode: Literal["character_drama", "explainer_diagram", "kinetic_callout"]
    backdrop_rig: str = Field(..., min_length=2, max_length=100)
    diagram_rig: Optional[str] = None
    active_diagram_stage: Optional[int] = Field(default=None, ge=1, le=4)
    primary_character: Optional[str] = None
    secondary_character: Optional[str] = None
    callout_headline: Optional[str] = None
    callout_subtext: Optional[str] = None
    emotion: Literal["calm", "wrath", "shock", "smirk", "meditating"] = "calm"
    action_gesture: Literal[
        "idle_breathe", "raise_weapon", "point_accuse", "bless_hand", "tremble"
    ] = "idle_breathe"
    mood_palette: str = Field(..., min_length=2, max_length=60)
    particle_theme: str = Field(..., min_length=2, max_length=60)
    camera_motion: str = Field(..., min_length=2, max_length=60)
    transition_sfx: Optional[str] = None

    @field_validator("backdrop_rig")
    @classmethod
    def check_backdrop_rig(cls, v: str) -> str:
        return _validate_rig_slug(v, "backdrop_rig")

    @field_validator("diagram_rig", "primary_character", "secondary_character")
    @classmethod
    def check_optional_rig(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        if v is None:
            return None
        return _validate_rig_slug(v, info.field_name or "rig")

    @field_validator("mood_palette")
    @classmethod
    def check_mood_palette(cls, v: str, info: ValidationInfo) -> str:
        cfg = (info.context or {}).get("config")
        if cfg:
            allowed = cfg["assets"]["mood_palettes"]
            if v not in allowed:
                raise ValueError(f"mood_palette '{v}' not in allowed palettes: {allowed}")
        return v

    @field_validator("particle_theme")
    @classmethod
    def check_particle_theme(cls, v: str, info: ValidationInfo) -> str:
        cfg = (info.context or {}).get("config")
        if cfg:
            allowed = cfg["assets"]["particle_themes"]
            if v not in allowed:
                raise ValueError(f"particle_theme '{v}' not in allowed themes: {allowed}")
        return v

    @field_validator("camera_motion")
    @classmethod
    def check_camera_motion(cls, v: str) -> str:
        if not SNAKE_CASE_RE.match(v):
            raise ValueError(f"camera_motion '{v}' must be lowercase snake_case")
        return v

    @field_validator("transition_sfx")
    @classmethod
    def check_transition_sfx(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        if v is None:
            return None
        cleaned = _validate_audio_filename(v, "transition_sfx")
        cfg = (info.context or {}).get("config")
        if cfg:
            allowed = cfg["assets"].get("sfx_tracks", [])
            if allowed and cleaned not in allowed:
                raise ValueError(f"transition_sfx '{cleaned}' not in configured sfx_tracks: {allowed}")
        return cleaned

    @model_validator(mode="after")
    def validate_mode_requirements(self) -> "ScenePlan":
        if len(self.narration_text.split()) < 3:
            raise ValueError(
                f"Scene {self.scene_index}: narration_text must contain at least 3 words"
            )
        if self.visual_mode == "character_drama":
            if not self.primary_character:
                raise ValueError(
                    f"Scene {self.scene_index}: primary_character is required for character_drama"
                )
        elif self.visual_mode == "explainer_diagram":
            if not self.diagram_rig:
                raise ValueError(
                    f"Scene {self.scene_index}: diagram_rig is required for explainer_diagram"
                )
            if self.active_diagram_stage is None:
                raise ValueError(
                    f"Scene {self.scene_index}: active_diagram_stage (1..4) is required "
                    "for explainer_diagram"
                )
        elif self.visual_mode == "kinetic_callout":
            if not self.callout_headline:
                raise ValueError(
                    f"Scene {self.scene_index}: callout_headline is required for kinetic_callout"
                )
        return self


class EpisodePlan(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    series_id: int = Field(..., ge=1)
    series_title: str = Field(..., min_length=3, max_length=150)
    pillar: str = Field(..., min_length=2, max_length=100)
    episode_number_in_series: int = Field(..., ge=1)
    total_planned_episodes: int = Field(..., ge=1)
    global_episode_number: int = Field(..., ge=1)
    tts_voice: str = Field(..., min_length=4, max_length=120)
    bgm_track: str = Field(..., min_length=5, max_length=120)
    bespoke_asset_path: str = Field(..., min_length=10, max_length=255)
    youtube_title: str = Field(..., min_length=5, max_length=100)
    youtube_description: str = Field(..., min_length=10, max_length=5000)
    summary: str = Field(..., min_length=10, max_length=1000)
    scenes: list[ScenePlan]

    @field_validator("pillar")
    @classmethod
    def check_pillar(cls, v: str, info: ValidationInfo) -> str:
        cfg = (info.context or {}).get("config")
        if cfg:
            allowed = cfg["channel"]["pillars"]
            if v not in allowed:
                raise ValueError(f"pillar '{v}' is not in configured pillars: {allowed}")
        return v

    @field_validator("tts_voice")
    @classmethod
    def check_tts_voice(cls, v: str) -> str:
        return _validate_kokoro_voice(v)

    @field_validator("bgm_track")
    @classmethod
    def check_bgm_track(cls, v: str) -> str:
        return _validate_audio_filename(v, "bgm_track")

    @field_validator("bespoke_asset_path")
    @classmethod
    def check_bespoke_asset_path(cls, v: str) -> str:
        normalized = v.replace("\\", "/").lstrip("./")
        if ".." in normalized.split("/"):
            raise ValueError("bespoke_asset_path must not contain '..'")
        if not normalized.startswith(BESPOKE_ASSET_PREFIXES):
            raise ValueError(
                f"bespoke_asset_path must start with one of {BESPOKE_ASSET_PREFIXES} "
                f"(got '{normalized}')"
            )
        if not normalized.endswith(".svg"):
            raise ValueError("bespoke_asset_path must end with '.svg'")
        stem = Path(normalized).stem
        if not RIG_SLUG_RE.match(stem):
            raise ValueError(
                f"bespoke_asset_path filename stem '{stem}' must be lowercase alphanumeric/underscore/hyphen"
            )
        return normalized

    @model_validator(mode="after")
    def validate_scenes_and_originality(self, info: ValidationInfo) -> "EpisodePlan":
        cfg = (info.context or {}).get("config")
        min_scenes = cfg["episode_pacing"]["min_scenes"] if cfg else 7
        max_scenes = cfg["episode_pacing"]["max_scenes"] if cfg else 8
        require_bespoke = (
            cfg["series"].get("require_bespoke_asset_per_episode", True) if cfg else True
        )

        if self.episode_number_in_series > self.total_planned_episodes:
            raise ValueError(
                f"episode_number_in_series ({self.episode_number_in_series}) exceeds "
                f"total_planned_episodes ({self.total_planned_episodes})"
            )

        if not (min_scenes <= len(self.scenes) <= max_scenes):
            raise ValueError(
                f"scenes count must be between {min_scenes} and {max_scenes} "
                f"(got {len(self.scenes)})"
            )

        expected_indices = list(range(1, len(self.scenes) + 1))
        actual_indices = [scene.scene_index for scene in self.scenes]
        if actual_indices != expected_indices:
            raise ValueError(
                f"scene_index values must be strictly sequential {expected_indices} "
                f"(got {actual_indices})"
            )

        if require_bespoke:
            bespoke_stem = Path(self.bespoke_asset_path).stem
            referenced_stems: set[str] = set()
            for scene in self.scenes:
                for rig in (
                    scene.diagram_rig,
                    scene.backdrop_rig,
                    scene.primary_character,
                    scene.secondary_character,
                ):
                    if rig:
                        referenced_stems.add(rig)
            if bespoke_stem not in referenced_stems:
                raise ValueError(
                    f"bespoke_asset_path '{self.bespoke_asset_path}' (stem '{bespoke_stem}') "
                    "must be actively featured in at least one scene"
                )
        return self


class PublishResult(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    video_id: Optional[str] = None
    playlist_id: Optional[str] = None
    upload_status: Literal["PUBLISHED", "PRIVATE_REVIEW", "FAILED"]
    scheduled_publish_at: Optional[str] = None
    upload_mode: Optional[str] = None
    video_url: Optional[str] = None
    error_message: Optional[str] = None

    @field_validator("upload_status", mode="before")
    @classmethod
    def normalize_status(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip().upper()
        return v

    @field_validator("scheduled_publish_at")
    @classmethod
    def validate_iso_timestamp(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(
                f"scheduled_publish_at '{v}' is not a valid ISO-8601 timestamp"
            ) from exc
        return v

    @model_validator(mode="after")
    def validate_status_fields(self) -> "PublishResult":
        if self.upload_status in ("PUBLISHED", "PRIVATE_REVIEW") and not self.video_id:
            raise ValueError(f"video_id is required when upload_status is '{self.upload_status}'")
        return self


def emit_pacing_warnings(plan: EpisodePlan, cfg: dict[str, Any]) -> None:
    """Log non-fatal Kokoro prosody word-count warnings to stderr."""
    min_words = cfg["episode_pacing"]["min_words_per_scene"]
    max_words = cfg["episode_pacing"]["max_words_per_scene"]
    for scene in plan.scenes:
        wc = len(scene.narration_text.split())
        if wc < min_words or wc > max_words:
            print(
                f"[WARN] Scene {scene.scene_index} has {wc} words "
                f"(target Kokoro sweet spot: {min_words}-{max_words}).",
                file=sys.stderr,
            )


# ---------------------------------------------------------------------------
# Database Connection & Transactions
# ---------------------------------------------------------------------------

def connect_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
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


def ensure_db_initialized(db_path: Path) -> None:
    if not db_path.is_file():
        raise StateError(
            f"Database file not found at {db_path}. Run 'python scripts/db_manager.py --init' first."
        )


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
    bible_parsed: Any
    try:
        bible_parsed = json.loads(row["series_bible_json"])
    except json.JSONDecodeError:
        bible_parsed = row["series_bible_json"]

    ep_rows = conn.execute(
        """
        SELECT episode_number_in_series, global_episode_number, youtube_title,
               summary, bespoke_asset_path, youtube_video_id, status
        FROM episodes
        WHERE series_id = ? AND status != 'FAILED'
        ORDER BY episode_number_in_series ASC
        """,
        (row["series_id"],),
    ).fetchall()

    return {
        "series_id": row["series_id"],
        "series_title": row["series_title"],
        "pillar": row["pillar"],
        "tts_voice": row["tts_voice"],
        "bgm_track": row["bgm_track"],
        "total_planned_episodes": row["total_planned_episodes"],
        "completed_episodes": row["completed_episodes"],
        "series_bible_json": bible_parsed,
        "youtube_playlist_id": row["youtube_playlist_id"],
        "status": row["status"],
        "created_at": row["created_at"],
        "completed_episode_summaries": [dict(ep) for ep in ep_rows],
    }


# ---------------------------------------------------------------------------
# CLI Command Implementations
# ---------------------------------------------------------------------------

def cmd_init(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    paths = resolve_paths(root, cfg)
    db_path = paths["db_file"]
    db_path.parent.mkdir(parents=True, exist_ok=True)
    paths["build_dir"].mkdir(parents=True, exist_ok=True)

    conn = connect_db(db_path)
    try:
        with immediate_transaction(conn) as cur:
            for statement in SCHEMA_SQL.strip().split(";"):
                stmt = statement.strip()
                if stmt:
                    cur.execute(stmt)
    finally:
        conn.close()

    return {
        "status": "ok",
        "action": "init",
        "db_file": str(db_path),
        "tables": ["series", "episodes"],
    }


def cmd_context(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    paths = resolve_paths(root, cfg)
    db_path = paths["db_file"]
    ensure_db_initialized(db_path)

    history_limit = int(cfg["series"].get("completed_history_window", 20))
    assets_dir = paths["assets_dir"]

    conn = connect_db(db_path)
    try:
        active_rows = conn.execute(
            "SELECT * FROM series WHERE status = 'ACTIVE' ORDER BY series_id ASC"
        ).fetchall()
        if len(active_rows) > 1:
            raise StateError(
                f"Database invariant violated: found {len(active_rows)} ACTIVE series simultaneously."
            )

        active_series = _row_to_active_series(conn, active_rows[0]) if active_rows else None

        next_global_row = conn.execute(
            "SELECT COALESCE(MAX(global_episode_number), 0) + 1 AS next_global "
            "FROM episodes WHERE status != 'FAILED'"
        ).fetchone()
        next_global = int(next_global_row["next_global"])

        if active_series is not None:
            next_in_series = int(active_series["completed_episodes"]) + 1
            if next_in_series > int(active_series["total_planned_episodes"]):
                raise StateError(
                    f"Active series {active_series['series_id']} has completed_episodes "
                    f"({active_series['completed_episodes']}) >= total_planned_episodes "
                    f"({active_series['total_planned_episodes']}) but is still ACTIVE."
                )
        else:
            next_in_series = 1

        completed_rows = conn.execute(
            """
            SELECT series_id, series_title, pillar, total_planned_episodes,
                   completed_episodes, youtube_playlist_id, created_at
            FROM series
            WHERE status = 'COMPLETED'
            ORDER BY series_id DESC
            LIMIT ?
            """,
            (history_limit,),
        ).fetchall()
        completed_history = [dict(r) for r in completed_rows]
        last_completed_pillar = completed_history[0]["pillar"] if completed_history else None

        bespoke_rows = conn.execute(
            "SELECT bespoke_asset_path FROM episodes WHERE status != 'FAILED' ORDER BY episode_id ASC"
        ).fetchall()
        previous_bespoke_assets = [r["bespoke_asset_path"] for r in bespoke_rows]
    finally:
        conn.close()

    return {
        "channel_config": {
            "language_mode": cfg["channel"]["language_mode"],
            "primary_language": cfg["channel"]["primary_language"],
            "pillars": cfg["channel"]["pillars"],
            "tts_engine": cfg["tts"]["engine"],
            "tts_voice": cfg["tts"]["default_voice"],
            "voice_provisional": cfg["tts"].get("voice_provisional", True),
            "upload_mode": cfg["publishing"]["upload_mode"],
            "allow_public_or_scheduled": cfg["publishing"].get("allow_public_or_scheduled", False),
            "min_episodes": cfg["series"]["min_episodes"],
            "max_episodes": cfg["series"]["max_episodes"],
            "bgm_by_pillar": cfg["assets"]["bgm_by_pillar"],
            "mood_palettes": cfg["assets"]["mood_palettes"],
            "particle_themes": cfg["assets"]["particle_themes"],
        },
        "active_series": active_series,
        "next_episode_number_in_series": next_in_series,
        "next_global_episode_number": next_global,
        "completed_series_history": completed_history,
        "last_completed_pillar": last_completed_pillar,
        "previous_bespoke_assets": previous_bespoke_assets,
        "available_rigs": {
            "characters": _list_svg_stems(assets_dir / "svg" / "characters"),
            "backdrops": _list_svg_stems(assets_dir / "svg" / "backdrops"),
            "diagrams": _list_svg_stems(assets_dir / "svg" / "diagrams"),
            "bgm": _list_audio_files(assets_dir / "bgm"),
            "sfx": _list_audio_files(assets_dir / "sfx"),
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

    conn = connect_db(db_path)
    try:
        with immediate_transaction(conn) as cur:
            active = cur.execute(
                "SELECT series_id, series_title, completed_episodes, total_planned_episodes "
                "FROM series WHERE status = 'ACTIVE'"
            ).fetchone()
            if active is not None:
                raise StateError(
                    f"Cannot create new series while series #{active['series_id']} "
                    f"('{active['series_title']}', {active['completed_episodes']}/"
                    f"{active['total_planned_episodes']}) is still ACTIVE."
                )

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
                last_completed = cur.execute(
                    "SELECT series_id, pillar FROM series WHERE status = 'COMPLETED' "
                    "ORDER BY series_id DESC LIMIT 1"
                ).fetchone()
                if last_completed is not None and last_completed["pillar"] == plan.pillar:
                    raise StateError(
                        f"Pillar rotation violation: cannot repeat immediately preceding "
                        f"completed series pillar '{plan.pillar}' (series_id={last_completed['series_id']})."
                    )

            cur.execute(
                """
                INSERT INTO series (
                    series_title, pillar, tts_voice, bgm_track,
                    total_planned_episodes, completed_episodes,
                    series_bible_json, youtube_playlist_id, status
                ) VALUES (?, ?, ?, ?, ?, 0, ?, NULL, 'ACTIVE')
                """,
                (
                    plan.series_title,
                    plan.pillar,
                    plan.tts_voice,
                    plan.bgm_track,
                    plan.total_planned_episodes,
                    plan.serialized_bible(),
                ),
            )
            new_series_id = int(cur.lastrowid)
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
        pub_res = PublishResult.model_validate(raw_pub)
    except ValidationError as exc:
        raise StateError(f"publish_result.json validation failed:\n{exc}") from exc

    emit_pacing_warnings(ep_plan, cfg)

    conn = connect_db(db_path)
    try:
        with immediate_transaction(conn) as cur:
            active = cur.execute(
                "SELECT * FROM series WHERE status = 'ACTIVE'"
            ).fetchone()
            if active is None:
                raise StateError("No ACTIVE series exists; cannot record episode.")

            if int(active["series_id"]) != ep_plan.series_id:
                raise StateError(
                    f"episode_plan.series_id ({ep_plan.series_id}) does not match "
                    f"ACTIVE series_id ({active['series_id']})."
                )
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
                    f"Expected episode_number_in_series={expected_in_series}, "
                    f"got {ep_plan.episode_number_in_series}."
                )

            next_global_row = cur.execute(
                "SELECT COALESCE(MAX(global_episode_number), 0) + 1 AS next_global "
                "FROM episodes WHERE status != 'FAILED'"
            ).fetchone()
            expected_global = int(next_global_row["next_global"])
            if ep_plan.global_episode_number != expected_global:
                raise StateError(
                    f"Expected global_episode_number={expected_global}, "
                    f"got {ep_plan.global_episode_number}."
                )

            dup_bespoke = cur.execute(
                """
                SELECT episode_id FROM episodes
                WHERE bespoke_asset_path = ?
                  AND NOT (series_id = ? AND episode_number_in_series = ? AND status = 'FAILED')
                """,
                (
                    ep_plan.bespoke_asset_path,
                    ep_plan.series_id,
                    ep_plan.episode_number_in_series,
                ),
            ).fetchone()
            if dup_bespoke is not None:
                raise StateError(
                    f"bespoke_asset_path '{ep_plan.bespoke_asset_path}' was already used "
                    f"by episode_id={dup_bespoke['episode_id']} (each episode requires a unique SVG)."
                )

            existing_playlist_id = active["youtube_playlist_id"]
            final_playlist_id = existing_playlist_id
            if pub_res.playlist_id:
                if existing_playlist_id is None:
                    cur.execute(
                        "UPDATE series SET youtube_playlist_id = ? WHERE series_id = ?",
                        (pub_res.playlist_id, ep_plan.series_id),
                    )
                    final_playlist_id = pub_res.playlist_id
                elif existing_playlist_id != pub_res.playlist_id:
                    raise StateError(
                        f"Playlist mismatch for series #{ep_plan.series_id}: "
                        f"stored='{existing_playlist_id}', publish_result='{pub_res.playlist_id}'."
                    )

            # Clear any prior FAILED attempt for this exact slot so retry is gapless & atomic.
            cur.execute(
                """
                DELETE FROM episodes
                WHERE series_id = ? AND episode_number_in_series = ? AND status = 'FAILED'
                """,
                (ep_plan.series_id, ep_plan.episode_number_in_series),
            )

            script_json_str = json.dumps(ep_plan.model_dump(), ensure_ascii=False)
            cur.execute(
                """
                INSERT INTO episodes (
                    series_id, episode_number_in_series, global_episode_number,
                    youtube_title, summary, bespoke_asset_path, script_json,
                    youtube_video_id, scheduled_publish_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ep_plan.series_id,
                    ep_plan.episode_number_in_series,
                    ep_plan.global_episode_number,
                    ep_plan.youtube_title,
                    ep_plan.summary,
                    ep_plan.bespoke_asset_path,
                    script_json_str,
                    pub_res.video_id,
                    pub_res.scheduled_publish_at,
                    pub_res.upload_status,
                ),
            )
            episode_id = int(cur.lastrowid)

            new_completed = int(active["completed_episodes"])
            new_series_status = str(active["status"])

            if pub_res.upload_status in ("PUBLISHED", "PRIVATE_REVIEW"):
                new_completed += 1
                if new_completed == int(active["total_planned_episodes"]):
                    new_series_status = "COMPLETED"
                cur.execute(
                    """
                    UPDATE series
                    SET completed_episodes = ?, status = ?
                    WHERE series_id = ?
                    """,
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
        "episode_number_in_series": ep_plan.episode_number_in_series,
        "global_episode_number": ep_plan.global_episode_number,
        "episode_status": pub_res.upload_status,
        "youtube_video_id": pub_res.video_id,
        "youtube_playlist_id": final_playlist_id,
        "completed_episodes": new_completed,
        "total_planned_episodes": ep_plan.total_planned_episodes,
        "series_status": new_series_status,
    }


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="db_manager.py",
        description="Sutradhar SQLite series & episode state manager.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--init", action="store_true", help="Initialize episodes.db schema")
    group.add_argument("--context", action="store_true", help="Print current series & rig context JSON")
    group.add_argument("--create-series", action="store_true", help="Insert ACTIVE series from build/new_series_plan.json")
    group.add_argument("--record-published", action="store_true", help="Record episode from build/episode_plan.json & build/publish_result.json")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        root = get_project_root()
        cfg = load_config(root)

        if args.init:
            result = cmd_init(root, cfg)
        elif args.context:
            result = cmd_context(root, cfg)
        elif args.create_series:
            result = cmd_create_series(root, cfg)
        elif args.record_published:
            result = cmd_record_published(root, cfg)
        else:
            raise StateError("No valid command flag provided.")

        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except StateError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - defensive catch-all
        print(f"[FATAL] Unexpected error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())