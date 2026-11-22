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
from pathlib import Path, PurePosixPath
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
YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{3,128}$")

BESPOKE_ASSET_DIRS = (
    "assets/svg/diagrams",
    "assets/svg/backdrops",
    "assets/svg/characters",
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
    series_id INTEGER,
    episode_number_in_series INTEGER CHECK (episode_number_in_series IS NULL OR episode_number_in_series >= 1),
    global_episode_number INTEGER NOT NULL UNIQUE CHECK (global_episode_number >= 1),
    content_format TEXT NOT NULL DEFAULT 'serial' CHECK (content_format IN ('standalone', 'episodic_series', 'serial')),
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
    WHERE status != 'FAILED' AND series_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_episodes_series_id
    ON episodes (series_id, episode_number_in_series);
"""


class StateError(RuntimeError):
    """Raised when a database invariant, config check, or state transition fails."""


# ---------------------------------------------------------------------------
# Workspace & Configuration Helpers
# ---------------------------------------------------------------------------

def get_project_root() -> Path:
    """Resolve repository root (supports SUTRADHAR_ROOT override for isolated tests)."""
    env_root = os.environ.get("SUTRADHAR_ROOT")
    if env_root:
        return Path(env_root).resolve()
    return Path(__file__).resolve().parent.parent


def validate_config(cfg: Any, config_path: Path) -> dict[str, Any]:
    """Validate config.yaml structure and critical safety invariants."""
    if not isinstance(cfg, dict):
        raise StateError(f"Invalid YAML structure in {config_path}")

    required_sections = (
        "channel",
        "series",
        "episode_pacing",
        "tts",
        "assets",
        "publishing",
        "paths",
    )
    missing = [sec for sec in required_sections if not isinstance(cfg.get(sec), dict)]
    if missing:
        raise StateError(f"config.yaml missing or invalid sections: {', '.join(missing)}")

    channel = cfg["channel"]
    primary_lang = channel.get("primary_language")
    lang_mode = channel.get("language_mode")
    if lang_mode not in ("global_english", "per_channel") or primary_lang not in ("en", "hi"):
        raise StateError(
            "config.yaml language lock violated: Sutradhar requires "
            f"channel.primary_language in ('en', 'hi') and language_mode in ('global_english', 'per_channel') "
            f"(got primary_language={primary_lang!r}, language_mode={lang_mode!r})."
        )

    # Validate languages profile when configured
    if "languages" in cfg:
        langs = cfg["languages"]
        if not isinstance(langs, dict) or "en" not in langs or "hi" not in langs:
            raise StateError("config.yaml languages must define profiles for both 'en' and 'hi'.")
        for lcode in ("en", "hi"):
            lprof = langs[lcode]
            if not isinstance(lprof, dict):
                raise StateError(f"config.yaml languages.{lcode} profile must be a mapping.")
            for req_key in ("narrator_voice", "character_dialogue_voice", "narrator_speed", "character_dialogue_speed", "pronunciations_file"):
                if req_key not in lprof:
                    raise StateError(f"config.yaml languages.{lcode} missing required key: '{req_key}'.")
    pillars = channel.get("pillars")
    if not isinstance(pillars, list) or not pillars or not all(isinstance(p, str) and p.strip() for p in pillars):
        raise StateError("config.yaml channel.pillars must be a non-empty list of strings.")

    series_cfg = cfg["series"]
    min_ep = series_cfg.get("min_episodes")
    max_ep = series_cfg.get("max_episodes")
    if not isinstance(min_ep, int) or not isinstance(max_ep, int) or not (1 <= min_ep <= max_ep):
        raise StateError("config.yaml series.min_episodes/max_episodes must be valid integers with min <= max.")

    pacing = cfg["episode_pacing"]
    for key in ("min_scenes", "max_scenes", "min_words_per_scene", "max_words_per_scene"):
        if not isinstance(pacing.get(key), int) or pacing[key] < 1:
            raise StateError(f"config.yaml episode_pacing.{key} must be a positive integer.")
    if pacing["min_scenes"] > pacing["max_scenes"]:
        raise StateError("config.yaml episode_pacing.min_scenes cannot exceed max_scenes.")

    tts = cfg["tts"]
    if not isinstance(tts.get("engine"), str):
        raise StateError("config.yaml tts.engine must be a string.")
    if "default_voice" not in tts and "languages" in cfg:
        active_lprof = cfg["languages"].get(primary_lang, {})
        narr_v = active_lprof.get("narrator_voice")
        if isinstance(narr_v, dict):
            tts["default_voice"] = "+".join(f"{k}:{v}" for k, v in narr_v.items())
        elif isinstance(narr_v, str):
            tts["default_voice"] = narr_v
    if not isinstance(tts.get("default_voice"), str):
        raise StateError("config.yaml tts.default_voice must be a string or resolvable from languages profile.")

    assets = cfg["assets"]
    bgm_map = assets.get("bgm_by_pillar")
    if not isinstance(bgm_map, dict) or not bgm_map:
        raise StateError("config.yaml assets.bgm_by_pillar must be a non-empty mapping.")
    for key in ("sfx_tracks", "mood_palettes", "particle_themes"):
        if not isinstance(assets.get(key), list) or not assets[key]:
            raise StateError(f"config.yaml assets.{key} must be a non-empty list.")

    pub = cfg["publishing"]
    upload_mode = pub.get("upload_mode")
    if upload_mode not in ("public", "private_review", "scheduled"):
        raise StateError(
            f"config.yaml publishing.upload_mode must be 'public', 'private_review', or 'scheduled' (got {upload_mode!r})."
        )
    if not isinstance(pub.get("allow_public_or_scheduled"), bool):
        raise StateError("config.yaml publishing.allow_public_or_scheduled must be a boolean.")

    paths = cfg["paths"]
    for key in ("db_file", "build_dir", "assets_dir"):
        if not isinstance(paths.get(key), str) or not paths[key].strip():
            raise StateError(f"config.yaml paths.{key} must be a non-empty string.")

    # Validate optional content_format and duration range
    content_format = cfg.get("content_format") or cfg.get("content", {}).get("format")
    if content_format is not None and content_format not in ("standalone", "episodic_series", "serial"):
        raise StateError(
            f"config.yaml content_format must be 'standalone', 'episodic_series', or 'serial' (got {content_format!r})."
        )

    dur_range = cfg.get("target_duration_range") or cfg.get("content", {}).get("target_duration_range")
    if dur_range is not None:
        if not isinstance(dur_range, dict):
            raise StateError("config.yaml target_duration_range must be a mapping with min_seconds and max_seconds.")
        min_s = dur_range.get("min_seconds")
        max_s = dur_range.get("max_seconds")
        if (
            not isinstance(min_s, (int, float))
            or not isinstance(max_s, (int, float))
            or min_s <= 0
            or min_s > max_s
        ):
            raise StateError(
                f"config.yaml target_duration_range min_seconds/max_seconds must be positive numbers with min <= max (got {dur_range})."
            )

    return cfg


def load_config(root: Path) -> dict[str, Any]:
    config_path = root / "config.yaml"
    if not config_path.is_file():
        raise StateError(f"Missing configuration file: {config_path}")
    try:
        with config_path.open("r", encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise StateError(f"Malformed YAML in {config_path}: {exc}") from exc
    return validate_config(cfg, config_path)


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
        seen_voices: set[str] = set()
        for part in parts:
            if ":" not in part:
                raise ValueError(
                    f"Voice blend component '{part}' must use 'voice_id:weight' format"
                )
            vid, raw_weight = part.split(":", 1)
            if not VOICE_ID_RE.match(vid):
                raise ValueError(f"Invalid Kokoro voice ID '{vid}' in blend '{voice}'")
            if vid in seen_voices:
                raise ValueError(f"Duplicate voice ID '{vid}' in blend '{voice}'")
            seen_voices.add(vid)
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


def _validate_configured_bgm(value: str, cfg: Optional[dict[str, Any]]) -> str:
    cleaned = _validate_audio_filename(value, "bgm_track")
    if cfg and "assets" in cfg:
        allowed_bgms = set(cfg["assets"].get("bgm_tracks", []))
        if "bgm_by_pillar" in cfg["assets"]:
            allowed_bgms.update(cfg["assets"]["bgm_by_pillar"].values())
        if "bgm_by_mood" in cfg["assets"]:
            allowed_bgms.update(cfg["assets"]["bgm_by_mood"].values())
        allowed_bgms_list = sorted(allowed_bgms)
        if allowed_bgms_list and cleaned not in allowed_bgms:
            raise ValueError(
                f"bgm_track '{cleaned}' is not in configured BGM tracks: {allowed_bgms_list}"
            )
    return cleaned


def _validate_rig_slug(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not RIG_SLUG_RE.match(cleaned):
        raise ValueError(
            f"{field_name} '{cleaned}' must be a lowercase slug without '.svg' or path separators"
        )
    return cleaned


def _validate_bespoke_asset_path(value: str) -> str:
    normalized = value.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    posix = PurePosixPath(normalized)
    if ".." in posix.parts or posix.is_absolute():
        raise ValueError(f"bespoke asset path '{value}' must be a relative path without '..'")
    parent_dir = posix.parent.as_posix()
    if parent_dir not in BESPOKE_ASSET_DIRS:
        raise ValueError(
            f"bespoke asset path '{normalized}' must sit directly inside one of "
            f"{BESPOKE_ASSET_DIRS} (got '{parent_dir}')"
        )
    if posix.suffix.lower() != ".svg":
        raise ValueError(f"bespoke asset path '{normalized}' must end with '.svg'")
    if not RIG_SLUG_RE.match(posix.stem):
        raise ValueError(
            f"bespoke asset filename stem '{posix.stem}' must be lowercase alphanumeric/underscore/hyphen"
        )
    return posix.as_posix()


def _blank_to_none(v: Any) -> Any:
    if isinstance(v, str) and v.strip() == "":
        return None
    return v


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class SeriesBibleEpisode(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    episode_number: int = Field(..., ge=1)
    working_title: str = Field(..., min_length=3, max_length=120)
    hook: str = Field(..., min_length=10, max_length=300)
    narrative_direction: str = Field(..., min_length=15, max_length=1000)
    planned_bespoke_asset: str = Field(..., min_length=10, max_length=255)
    cliffhanger_or_payoff: str = Field(..., min_length=10, max_length=400)
    # Episodic series extensions (optional for backwards compatibility)
    standalone_story_synopsis: Optional[str] = Field(default=None, min_length=15, max_length=1000)
    central_conflict: Optional[str] = Field(default=None, min_length=10, max_length=500)
    resolution: Optional[str] = Field(default=None, min_length=10, max_length=500)
    series_connection: Optional[str] = Field(default=None, max_length=500)

    @field_validator(
        "standalone_story_synopsis",
        "central_conflict",
        "resolution",
        "series_connection",
        mode="before",
    )
    @classmethod
    def clean_optional_bible_strings(cls, v: Any) -> Any:
        return _blank_to_none(v)

    @field_validator("planned_bespoke_asset")
    @classmethod
    def check_planned_asset(cls, v: str) -> str:
        return _validate_bespoke_asset_path(v)


class SeriesBible(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    arc_summary: str = Field(..., min_length=15, max_length=1500)
    content_format: Optional[Literal["episodic_series", "serial"]] = "serial"
    continuity_notes: Optional[str] = Field(default=None, max_length=1000)
    episodes: list[SeriesBibleEpisode] = Field(..., min_length=1)

    @field_validator("continuity_notes", mode="before")
    @classmethod
    def clean_continuity_notes(cls, v: Any) -> Any:
        return _blank_to_none(v)


class NewSeriesPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    content_format: Optional[Literal["episodic_series", "serial"]] = "serial"
    series_title: str = Field(..., min_length=3, max_length=150)
    pillar: str = Field(..., min_length=2, max_length=100)
    tts_voice: str = Field(..., min_length=4, max_length=120)
    bgm_track: str = Field(..., min_length=5, max_length=120)
    total_planned_episodes: int
    series_bible_json: SeriesBible

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
    def check_bgm_track(cls, v: str, info: ValidationInfo) -> str:
        cfg = (info.context or {}).get("config")
        return _validate_configured_bgm(v, cfg)

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

    @field_validator("series_bible_json", mode="before")
    @classmethod
    def decode_series_bible_str(cls, v: Any) -> Any:
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
            except json.JSONDecodeError as exc:
                raise ValueError(f"series_bible_json string is not valid JSON: {exc}") from exc
            return parsed
        return v

    @model_validator(mode="after")
    def validate_bible_episode_alignment(self) -> "NewSeriesPlan":
        episodes = self.series_bible_json.episodes
        if len(episodes) != self.total_planned_episodes:
            raise ValueError(
                f"series_bible_json.episodes length ({len(episodes)}) must match "
                f"total_planned_episodes ({self.total_planned_episodes})"
            )
        expected_nums = list(range(1, self.total_planned_episodes + 1))
        actual_nums = [ep.episode_number for ep in episodes]
        if actual_nums != expected_nums:
            raise ValueError(
                f"series_bible_json episode_number values must be strictly sequential "
                f"{expected_nums} (got {actual_nums})"
            )
        planned_assets = [ep.planned_bespoke_asset for ep in episodes]
        if len(planned_assets) != len(set(planned_assets)):
            raise ValueError(
                "series_bible_json planned_bespoke_asset values must be unique across all episodes"
            )
        return self

    def serialized_bible(self) -> str:
        return json.dumps(self.series_bible_json.model_dump(exclude_none=True), ensure_ascii=False)


class ScenePlan(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    scene_index: int = Field(..., ge=1)
    narration_text: str = Field(..., min_length=5)
    visual_mode: Literal["character_drama", "explainer_diagram", "kinetic_callout"]
    backdrop_rig: str = Field(..., min_length=2, max_length=100)
    diagram_rig: Optional[str] = None
    active_diagram_stage: Optional[int] = Field(default=None, ge=1, le=4)
    primary_character: Optional[str] = None
    secondary_character: Optional[str] = None
    tertiary_character: Optional[str] = None
    callout_headline: Optional[str] = None
    callout_subtext: Optional[str] = None
    emotion: Literal[
        "calm", "wrath", "rage", "fear", "joy", "shock", "smirk", "meditating"
    ] = "calm"
    action_gesture: Literal[
        "idle_breathe", "raise_weapon", "point_accuse", "bless_hand", "tremble"
    ] = "idle_breathe"
    mood_palette: str = Field(..., min_length=2, max_length=60)
    particle_theme: str = Field(..., min_length=2, max_length=60)
    camera_motion: str = Field(..., min_length=2, max_length=60)
    transition_sfx: Optional[str] = None
    pause_after_ms: Optional[int] = Field(default=None, ge=50, le=1200)
    emphasis_word: Optional[str] = None
    # V2 Multi-Shot / Beat-Level Storytelling Attributes
    speaker_role: Literal["narrator", "character_dialogue"] = "narrator"
    voice_override: Optional[str] = None
    speed: Optional[float] = Field(default=None, ge=0.5, le=2.0)
    shot_type: Optional[str] = None
    transition_type: Optional[str] = None
    sfx_cue: Optional[str] = None
    fx_theme: Optional[str] = None
    vfx_elements: Optional[list[str]] = None
    characters: Optional[list[str]] = None
    pose_preset: Optional[str] = None
    expression_preset: Optional[str] = None
    infographic_type: Optional[str] = None
    infographic_text: Optional[str] = None
    expression_change: Optional[dict[str, Any]] = None

    @field_validator(
        "diagram_rig",
        "primary_character",
        "secondary_character",
        "tertiary_character",
        "callout_headline",
        "callout_subtext",
        "transition_sfx",
        "emphasis_word",
        "voice_override",
        "shot_type",
        "transition_type",
        "sfx_cue",
        "fx_theme",
        "pose_preset",
        "expression_preset",
        "infographic_type",
        "infographic_text",
        mode="before",
    )
    @classmethod
    def clean_optional_strings(cls, v: Any) -> Any:
        return _blank_to_none(v)

    @field_validator("infographic_type")
    @classmethod
    def check_infographic_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip().lower()
        if not SNAKE_CASE_RE.match(cleaned):
            raise ValueError(f"infographic_type '{v}' must be lowercase snake_case")
        return cleaned

    @field_validator("vfx_elements")
    @classmethod
    def check_vfx_elements(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is None:
            return None
        valid_items: list[str] = []
        for item in v:
            if not isinstance(item, str):
                continue
            cleaned = item.strip().lower()
            if not SNAKE_CASE_RE.match(cleaned):
                raise ValueError(f"vfx_element '{item}' must be lowercase snake_case")
            valid_items.append(cleaned)
        return valid_items

    @field_validator("backdrop_rig")
    @classmethod
    def check_backdrop_rig(cls, v: str) -> str:
        return _validate_rig_slug(v, "backdrop_rig")

    @field_validator("diagram_rig", "primary_character", "secondary_character", "tertiary_character")
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
            allowed = cfg["assets"]["sfx_tracks"]
            if cleaned not in allowed:
                raise ValueError(
                    f"transition_sfx '{cleaned}' not in configured sfx_tracks: {allowed}"
                )
        return cleaned

    @model_validator(mode="after")
    def validate_mode_and_text_requirements(self) -> "ScenePlan":
        if len(self.narration_text.split()) < 3:
            raise ValueError(
                f"Scene {self.scene_index}: narration_text must contain at least 3 words"
            )

        if self.visual_mode == "character_drama":
            if not self.primary_character:
                raise ValueError(
                    f"Scene {self.scene_index}: primary_character is required for character_drama"
                )
            if self.secondary_character and self.secondary_character == self.primary_character:
                raise ValueError(
                    f"Scene {self.scene_index}: secondary_character cannot duplicate primary_character"
                )
            if self.tertiary_character and (
                self.tertiary_character == self.primary_character
                or self.tertiary_character == self.secondary_character
            ):
                raise ValueError(
                    f"Scene {self.scene_index}: tertiary_character cannot duplicate primary or secondary character"
                )
            if self.active_diagram_stage is not None:
                raise ValueError(
                    f"Scene {self.scene_index}: active_diagram_stage must be null for character_drama"
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
            if not self.callout_headline or len(self.callout_headline) < 2:
                raise ValueError(
                    f"Scene {self.scene_index}: callout_headline is required for kinetic_callout"
                )
            if self.active_diagram_stage is not None:
                raise ValueError(
                    f"Scene {self.scene_index}: active_diagram_stage must be null for kinetic_callout"
                )
        return self


# ---------------------------------------------------------------------------
# Narrative Arc Templates & Constants
# ---------------------------------------------------------------------------

NARRATIVE_TEMPLATES: dict[str, dict[str, Any]] = {
    "eight_phase_complete_arc": {
        "name": "Eight-Phase Complete Dramatic Arc",
        "description": "Reference-quality narrative arc for 70-180s videos with complete story development and resolution.",
        "phases": [
            {"phase_index": 1, "phase_name": "Hook / Opening Mystery", "structure_type": "hook", "narrative_goal": "Establish intense stakes, visual intrigue, or central dramatic question immediately."},
            {"phase_index": 2, "phase_name": "Premise & Backstory", "structure_type": "premise", "narrative_goal": "Introduce core characters, context, motivation, and the underlying condition."},
            {"phase_index": 3, "phase_name": "Rising Action / First Move", "structure_type": "rising_action", "narrative_goal": "Initial action or hubris initiates the conflict; stakes begin to mount."},
            {"phase_index": 4, "phase_name": "Complication / Escalation", "structure_type": "escalation", "narrative_goal": "Counter-action or unexpected twist raises the difficulty and tension."},
            {"phase_index": 5, "phase_name": "Direct Confrontation", "structure_type": "confrontation", "narrative_goal": "The two opposing forces or moral principles collide directly."},
            {"phase_index": 6, "phase_name": "Dramatic Climax", "structure_type": "climax", "narrative_goal": "The peak moment of reckoning, turning point, or fateful choice."},
            {"phase_index": 7, "phase_name": "Conflict Resolution", "structure_type": "resolution", "narrative_goal": "The primary conflict is settled with clear, decisive consequence."},
            {"phase_index": 8, "phase_name": "Concluding Thought / Lesson", "structure_type": "concluding_thought", "narrative_goal": "Philosophical closure, moral resonance, or teaser connection for series."}
        ]
    },
    "five_phase_compact_arc": {
        "name": "Five-Phase Compact Dramatic Arc",
        "description": "Streamlined arc optimized for 40-60s concise stories and sharp paradoxes.",
        "phases": [
            {"phase_index": 1, "phase_name": "Dramatic Hook", "structure_type": "hook", "narrative_goal": "Direct question or impossible paradox hooks the viewer instantly."},
            {"phase_index": 2, "phase_name": "Setup & Context", "structure_type": "premise", "narrative_goal": "Establish the rule, characters, or cosmic principle at play."},
            {"phase_index": 3, "phase_name": "Crisis Escalation", "structure_type": "escalation", "narrative_goal": "The tension peaks as the inevitable collision approaches."},
            {"phase_index": 4, "phase_name": "Climax / Turning Point", "structure_type": "climax", "narrative_goal": "The decisive turning point or revelation occurs."},
            {"phase_index": 5, "phase_name": "Resolution & Lesson", "structure_type": "resolution", "narrative_goal": "Conflict resolved, concluding with a memorable philosophical takeaway."}
        ]
    },
    "in_medias_res": {
        "name": "In Medias Res Dramatic Structure",
        "description": "Non-linear structure opening at the boiling point of confrontation, then rewinding to reveal origins before concluding.",
        "phases": [
            {"phase_index": 1, "phase_name": "Boiling Point Hook", "structure_type": "in_medias_res", "narrative_goal": "Open at the height of confrontation or disaster with zero preamble."},
            {"phase_index": 2, "phase_name": "Origin Rewind / Flashback", "structure_type": "flashback", "narrative_goal": "Rewind to the pivotal mistake or fateful vow that caused this clash."},
            {"phase_index": 3, "phase_name": "Escalation", "structure_type": "escalation", "narrative_goal": "Fast-forward through the chain of events leading right back to the crisis."},
            {"phase_index": 4, "phase_name": "Climax Continuation", "structure_type": "climax", "narrative_goal": "Resume the opening confrontation and push it past the breaking point."},
            {"phase_index": 5, "phase_name": "Resolution & Closure", "structure_type": "resolution", "narrative_goal": "Decisive aftermath and philosophical meaning of the outcome."}
        ]
    }
}


class StoryPhase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    phase_index: int = Field(..., ge=1)
    phase_name: str = Field(..., min_length=2, max_length=100)
    narrative_goal: str = Field(..., min_length=5, max_length=500)
    target_duration_sec: Optional[float] = Field(default=None, ge=1.0, le=180.0)
    scenes: Optional[list[int]] = None
    structure_type: Optional[str] = None

    @field_validator("structure_type", mode="before")
    @classmethod
    def clean_structure_type(cls, v: Any) -> Any:
        return _blank_to_none(v)


class StoryArc(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    arc_title: str = Field(..., min_length=3, max_length=150)
    premise: str = Field(..., min_length=10, max_length=1000)
    central_conflict: str = Field(..., min_length=10, max_length=1000)
    resolution: str = Field(..., min_length=10, max_length=1000)
    phases: list[StoryPhase] = Field(..., min_length=1)
    narrative_structure: Optional[
        Literal[
            "eight_phase_complete_arc",
            "in_medias_res",
            "linear_escalation",
            "five_phase_compact_arc",
        ]
    ] = None
    climax_scene_index: Optional[int] = Field(default=None, ge=1)
    resolution_scene_index: Optional[int] = Field(default=None, ge=1)
    character_arcs: Optional[dict[str, str]] = None
    thematic_lesson: Optional[str] = None

    @field_validator("narrative_structure", "thematic_lesson", mode="before")
    @classmethod
    def clean_arc_optional_strings(cls, v: Any) -> Any:
        return _blank_to_none(v)


class EpisodePlan(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    content_format: Optional[Literal["standalone", "episodic_series", "serial"]] = "serial"
    story_arc: Optional[StoryArc] = None
    target_duration_sec: Optional[float] = Field(default=None, ge=30.0, le=180.0)
    target_duration_range: Optional[dict[str, float]] = None
    narrative_structure: Optional[str] = None

    series_id: Optional[int] = Field(default=None, ge=1)
    series_title: Optional[str] = Field(default=None, min_length=3, max_length=150)
    pillar: str = Field(..., min_length=2, max_length=100)
    episode_number_in_series: Optional[int] = Field(default=None, ge=1)
    total_planned_episodes: Optional[int] = Field(default=None, ge=1)
    global_episode_number: int = Field(..., ge=1)
    tts_voice: str = Field(..., min_length=4, max_length=120)
    bgm_track: str = Field(..., min_length=5, max_length=120)
    bespoke_asset_path: str = Field(..., min_length=10, max_length=255)
    youtube_title: str = Field(..., min_length=5, max_length=100)
    youtube_description: str = Field(..., min_length=10, max_length=5000)
    summary: str = Field(..., min_length=10, max_length=1000)
    language: Literal["en", "hi"] = "en"
    scenes: list[ScenePlan]

    @model_validator(mode="before")
    @classmethod
    def remap_shots_to_scenes(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "scenes" not in data and "shots" in data:
                data["scenes"] = data["shots"]
        return data

    @field_validator("language")
    @classmethod
    def check_language(cls, v: str, info: ValidationInfo) -> str:
        cfg = (info.context or {}).get("config")
        if cfg:
            expected = cfg["channel"].get("primary_language", "en")
            if v != expected:
                raise ValueError(
                    f"episode_plan language '{v}' must match channel.primary_language '{expected}'"
                )
        return v

    @field_validator("pillar")
    @classmethod
    def check_pillar(cls, v: str, info: ValidationInfo) -> str:
        cfg = (info.context or {}).get("config")
        if cfg:
            allowed = cfg["channel"]["pillars"]
            if v not in allowed:
                raise ValueError(f"pillar '{v}' is not in configured pillars: {allowed}")
        return v

    @field_validator("total_planned_episodes")
    @classmethod
    def check_total_planned(cls, v: Optional[int], info: ValidationInfo) -> Optional[int]:
        if v is None:
            return None
        cfg = (info.context or {}).get("config")
        min_ep = cfg["series"]["min_episodes"] if cfg else 3
        max_ep = cfg["series"]["max_episodes"] if cfg else 6
        if not (min_ep <= v <= max_ep):
            raise ValueError(
                f"total_planned_episodes must be between {min_ep} and {max_ep} (got {v})"
            )
        return v

    @field_validator("tts_voice")
    @classmethod
    def check_tts_voice(cls, v: str) -> str:
        return _validate_kokoro_voice(v)

    @field_validator("bgm_track")
    @classmethod
    def check_bgm_track(cls, v: str, info: ValidationInfo) -> str:
        cfg = (info.context or {}).get("config")
        return _validate_configured_bgm(v, cfg)

    @field_validator("bespoke_asset_path")
    @classmethod
    def check_bespoke_asset_path(cls, v: str) -> str:
        return _validate_bespoke_asset_path(v)

    @field_validator("youtube_title")
    @classmethod
    def check_youtube_title_chars(cls, v: str) -> str:
        if "<" in v or ">" in v:
            raise ValueError("youtube_title must not contain '<' or '>' characters")
        return v

    @model_validator(mode="after")
    def validate_scenes_and_originality(self, info: ValidationInfo) -> "EpisodePlan":
        cfg = (info.context or {}).get("config")
        fmt = self.content_format or "serial"
        if cfg:
            format_pacing = cfg.get("format_pacing", {}).get(fmt, {})
            default_pacing = cfg.get("episode_pacing", {})
            min_scenes = format_pacing.get("min_scenes", default_pacing.get("min_scenes", 5))
            max_scenes = format_pacing.get("max_scenes", default_pacing.get("max_scenes", 15))
        else:
            min_scenes = 5
            max_scenes = 15
        require_bespoke = (
            cfg["series"].get("require_bespoke_asset_per_episode", True) if cfg else True
        )
        if fmt != "standalone":
            if self.series_id is None:
                raise ValueError(f"series_id is required when content_format is '{fmt}'")
            if self.series_title is None:
                raise ValueError(f"series_title is required when content_format is '{fmt}'")
            if self.episode_number_in_series is None:
                raise ValueError(f"episode_number_in_series is required when content_format is '{fmt}'")
            if self.total_planned_episodes is None:
                raise ValueError(f"total_planned_episodes is required when content_format is '{fmt}'")

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
            bespoke_posix = PurePosixPath(self.bespoke_asset_path)
            bespoke_dir = bespoke_posix.parent.as_posix()
            bespoke_stem = bespoke_posix.stem

            if bespoke_dir == "assets/svg/diagrams":
                featured = any(s.diagram_rig == bespoke_stem for s in self.scenes)
                expected_field = "diagram_rig"
            elif bespoke_dir == "assets/svg/backdrops":
                featured = any(s.backdrop_rig == bespoke_stem for s in self.scenes)
                expected_field = "backdrop_rig"
            else:
                featured = any(
                    s.primary_character == bespoke_stem
                    or s.secondary_character == bespoke_stem
                    or s.tertiary_character == bespoke_stem
                    or (s.characters and bespoke_stem in s.characters)
                    for s in self.scenes
                )
                expected_field = "primary_character/secondary_character/tertiary_character"

            if not featured:
                raise ValueError(
                    f"bespoke_asset_path '{self.bespoke_asset_path}' (stem '{bespoke_stem}') "
                    f"must be actively featured in at least one scene's {expected_field}"
                )
        return self

    @model_validator(mode="after")
    def validate_story_completeness(self) -> "EpisodePlan":
        fmt = self.content_format or "serial"
        total_scenes = len(self.scenes)

        if self.story_arc is not None:
            arc = self.story_arc
            if len(arc.central_conflict.strip()) < 10:
                raise ValueError("story_arc.central_conflict must contain at least 10 characters")
            if len(arc.resolution.strip()) < 10:
                raise ValueError("story_arc.resolution must contain at least 10 characters")

            if arc.climax_scene_index is not None:
                if not (1 <= arc.climax_scene_index <= total_scenes):
                    raise ValueError(
                        f"story_arc.climax_scene_index ({arc.climax_scene_index}) must be within 1..{total_scenes}"
                    )
            if arc.resolution_scene_index is not None:
                if not (1 <= arc.resolution_scene_index <= total_scenes):
                    raise ValueError(
                        f"story_arc.resolution_scene_index ({arc.resolution_scene_index}) must be within 1..{total_scenes}"
                    )
            if arc.climax_scene_index is not None and arc.resolution_scene_index is not None:
                if arc.climax_scene_index > arc.resolution_scene_index:
                    raise ValueError(
                        f"story_arc.climax_scene_index ({arc.climax_scene_index}) cannot come after "
                        f"story_arc.resolution_scene_index ({arc.resolution_scene_index})"
                    )

            # Check that scene indices in phases are valid
            for phase in arc.phases:
                if phase.scenes:
                    for s_idx in phase.scenes:
                        if not (1 <= s_idx <= total_scenes):
                            raise ValueError(
                                f"StoryPhase {phase.phase_index} ('{phase.phase_name}') references "
                                f"invalid scene_index {s_idx} (total scenes: {total_scenes})"
                            )

            # Story completeness for standalone videos: NO dangling cliffhangers!
            if fmt == "standalone":
                cliffhanger_triggers = (
                    "to be continued",
                    "part 2",
                    "in part 2",
                    "stay tuned for part",
                    "in the next episode",
                    "in our next episode",
                    "find out in the next",
                    "find out in part",
                )
                last_scene_text = self.scenes[-1].narration_text.lower()
                res_text = arc.resolution.lower()
                summary_text = self.summary.lower()

                for trigger in cliffhanger_triggers:
                    if trigger in last_scene_text or trigger in res_text or trigger in summary_text:
                        raise ValueError(
                            f"Standalone story completeness violation: found cliffhanger phrase '{trigger}'. "
                            "Standalone videos must fully resolve their central conflict without unresolved serial hooks."
                        )
        return self


class PublishResult(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    video_id: Optional[str] = None
    playlist_id: Optional[str] = None
    upload_status: Literal["PUBLISHED", "PRIVATE_REVIEW", "FAILED"]
    scheduled_publish_at: Optional[str] = None
    upload_mode: Optional[Literal["public", "private_review", "scheduled"]] = None
    privacy_status: Optional[Literal["private", "unlisted", "public"]] = None
    video_url: Optional[str] = None
    error_message: Optional[str] = None

    @field_validator(
        "video_id",
        "playlist_id",
        "scheduled_publish_at",
        "upload_mode",
        "privacy_status",
        "video_url",
        "error_message",
        mode="before",
    )
    @classmethod
    def normalize_blanks(cls, v: Any) -> Any:
        return _blank_to_none(v)

    @field_validator("upload_status", mode="before")
    @classmethod
    def normalize_status(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip().upper()
        return v

    @field_validator("upload_mode", "privacy_status", mode="before")
    @classmethod
    def normalize_lower(cls, v: Any) -> Any:
        if isinstance(v, str):
            cleaned = v.strip().lower()
            return cleaned if cleaned else None
        return v

    @field_validator("video_id", "playlist_id")
    @classmethod
    def check_youtube_id(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        if v is None:
            return None
        if not YOUTUBE_ID_RE.match(v):
            raise ValueError(f"{info.field_name} '{v}' contains invalid characters")
        return v

    @field_validator("scheduled_publish_at")
    @classmethod
    def validate_iso_timestamp(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if "T" not in v and "t" not in v:
            raise ValueError(
                f"scheduled_publish_at '{v}' must include a time component (ISO-8601 RFC 3339)"
            )
        try:
            dt = datetime.fromisoformat(v.replace("Z", "+00:00").replace("z", "+00:00"))
        except ValueError as exc:
            raise ValueError(
                f"scheduled_publish_at '{v}' is not a valid ISO-8601 timestamp"
            ) from exc
        if dt.tzinfo is None:
            raise ValueError(
                f"scheduled_publish_at '{v}' must include an explicit timezone ('Z' or '±HH:MM')"
            )
        return v

    @model_validator(mode="after")
    def validate_status_and_publishing_policy(self, info: ValidationInfo) -> "PublishResult":
        if self.upload_status in ("PUBLISHED", "PRIVATE_REVIEW") and not self.video_id:
            raise ValueError(f"video_id is required when upload_status is '{self.upload_status}'")

        cfg = (info.context or {}).get("config")
        if cfg:
            pub_cfg = cfg["publishing"]
            cfg_mode = pub_cfg["upload_mode"]
            allow_pub = bool(pub_cfg["allow_public_or_scheduled"])
            private_lock_active = (cfg_mode == "private_review") or (not allow_pub)

            if private_lock_active:
                if self.upload_status == "PUBLISHED":
                    raise ValueError(
                        "Publishing safety lock active (upload_mode='private_review' or "
                        "allow_public_or_scheduled=false): PUBLISHED status is forbidden."
                    )
                if self.scheduled_publish_at is not None:
                    raise ValueError(
                        "Publishing safety lock active: scheduled_publish_at is forbidden "
                        "while private_review lock is active or allow_public_or_scheduled is false."
                    )
                if self.upload_mode is not None and self.upload_mode != "private_review":
                    raise ValueError(
                        f"Publishing safety lock active: upload_mode '{self.upload_mode}' "
                        "is forbidden (only 'private_review' is permitted)."
                    )
                if self.privacy_status is not None and self.privacy_status != "private":
                    raise ValueError(
                        f"Publishing safety lock active: privacy_status '{self.privacy_status}' "
                        "is forbidden (only 'private' is permitted)."
                    )
            else:
                if cfg_mode == "scheduled" and self.upload_status == "PUBLISHED" and not self.scheduled_publish_at:
                    raise ValueError(
                        "When upload_mode='scheduled', scheduled_publish_at timestamp is required for PUBLISHED status."
                    )
                if cfg_mode == "public" and self.scheduled_publish_at is not None:
                    raise ValueError(
                        "When upload_mode='public', scheduled_publish_at must be null (use 'scheduled' mode for delayed release)."
                    )
        return self


SeriesBibleEpisode.model_rebuild()
SeriesBible.model_rebuild()
NewSeriesPlan.model_rebuild()
StoryPhase.model_rebuild()
StoryArc.model_rebuild()
ScenePlan.model_rebuild()
EpisodePlan.model_rebuild()
PublishResult.model_rebuild()


def emit_pacing_warnings(plan: EpisodePlan, cfg: dict[str, Any]) -> None:
    """Log non-fatal Kokoro prosody word-count warnings to stderr."""
    fmt = getattr(plan, "content_format", None) or cfg.get("content_format", "serial")
    format_pacing = cfg.get("format_pacing", {}).get(fmt, {})
    default_pacing = cfg.get("episode_pacing", {})
    min_words = format_pacing.get("min_words_per_scene", default_pacing.get("min_words_per_scene", 10))
    max_words = format_pacing.get("max_words_per_scene", default_pacing.get("max_words_per_scene", 25))
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

def ensure_episodes_table_columns(conn: sqlite3.Connection) -> None:
    """Ensure backward-compatible schema migration for episodes table."""
    cur = conn.cursor()
    table_exists = cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='episodes'"
    ).fetchone()
    if table_exists:
        cols = [r[1] for r in cur.execute("PRAGMA table_info(episodes)").fetchall()]
        if "content_format" not in cols:
            cur.execute("ALTER TABLE episodes ADD COLUMN content_format TEXT NOT NULL DEFAULT 'serial'")


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

        private_review_count_row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM episodes WHERE status = 'PRIVATE_REVIEW'"
        ).fetchone()
        private_review_count = int(private_review_count_row["cnt"])
    finally:
        conn.close()

    content_format = cfg.get("content_format") or cfg.get("content", {}).get("format", "episodic_series")
    target_duration_range = cfg.get("target_duration_range") or cfg.get("content", {}).get("target_duration_range")

    return {
        "channel_config": {
            "language_mode": cfg["channel"]["language_mode"],
            "primary_language": cfg["channel"]["primary_language"],
            "locked_voice_profile": cfg["languages"].get(cfg["channel"]["primary_language"]) if "languages" in cfg else None,
            "pillars": cfg["channel"]["pillars"],
            "tts_engine": cfg["tts"]["engine"],
            "tts_voice": cfg["tts"]["default_voice"],
            "voice_provisional": cfg["languages"][cfg["channel"]["primary_language"]].get("voice_provisional", False) if "languages" in cfg else cfg["tts"].get("voice_provisional", True),
            "upload_mode": cfg["publishing"]["upload_mode"],
            "allow_public_or_scheduled": cfg["publishing"]["allow_public_or_scheduled"],
            "calibration_episodes_required": cfg["publishing"].get("calibration_episodes_required", 3),
            "completed_private_review_episodes": private_review_count,
            "min_episodes": cfg["series"]["min_episodes"],
            "max_episodes": cfg["series"]["max_episodes"],
            "bgm_by_pillar": cfg["assets"]["bgm_by_pillar"],
            "mood_palettes": cfg["assets"]["mood_palettes"],
            "particle_themes": cfg["assets"]["particle_themes"],
            "content_format": content_format,
            "target_duration_range": target_duration_range,
        },
        "content_format": content_format,
        "target_duration_range": target_duration_range,
        "can_plan_standalone": True,
        "autonomous_planning_guidelines": {
            "workflow": "Fully automated end-to-end; zero manual topic, duration, or format input needed from the user.",
            "topic_selection": "Autonomously select topic from channel_config.pillars rotating away from last_completed_pillar and completed_series_history.",
            "format_decision": "If active_series is null, autonomously decide between 'standalone' (single complete story) or 'episodic_series' (3-6 episode connected arc). If active_series is active, continue it.",
            "duration_rule": {
                "min_seconds": 30.0,
                "max_seconds": 180.0,
                "preferred_range": [40.0, 120.0],
                "guidance": "Autonomously set duration based on story complexity: concise ~40-60s (5-7 scenes), standard ~70-110s (8-11 scenes), epic ~120-180s (11-15 scenes)."
            },
            "storytelling_rule": "Every episode (standalone or series) must have a complete, satisfying story with proper beginning, middle, climax, and resolution.",
            "narrative_templates": {
                "eight_phase_complete_arc": "Reference dramatic structure (70-180s): 1. Hook/In Medias Res -> 2. Premise/Backstory -> 3. Rising Action -> 4. Escalation -> 5. Confrontation -> 6. Climax -> 7. Resolution -> 8. Concluding Thought.",
                "five_phase_compact_arc": "Compact structure for 40-60s stories: 1. Hook -> 2. Setup & Premise -> 3. Crisis Escalation -> 4. Climax -> 5. Resolution & Lesson.",
                "in_medias_res": "Non-linear structure: Open at the height of confrontation/disaster, flashback to origin, build back to climax, and resolve."
            },
            "story_completeness_rules": {
                "rule": "Every episode (standalone or series) must resolve its primary conflict within the episode.",
                "standalone_mandate": "Standalone videos must be 100% self-contained with no cliffhangers ('to be continued', 'part 2', etc.).",
                "episodic_series_mandate": "Each episode tells a complete story with beginning, middle, climax, and resolution, while sharing characters, world-building, and thematic continuity."
            },
            "pacing_rules": {
                "emotion_speed_guidance": "Calm/meditative/solemn: ~0.88-0.92; Urgent/wrath/climax: ~0.94-0.96; Dialogue: 0.88-0.92.",
                "pause_guidance": "Dramatic pause after climax/revelation: 350-500ms; rapid dialogue: 150-200ms; final scene: 850ms."
            },
            "visual_effects_and_transitions": {
                "available_vfx": ["laser_beam", "sunburst", "screen_shatter", "fracture_cracks", "sound_ripple"],
                "available_transitions": ["fade", "curtain_open", "blind_wipe", "border_wipe", "shatter_transition", "radial_wipe", "cut"],
                "guidance": "Every episode must feature at least 3 distinct transitions across scenes (e.g. curtain_open -> border_wipe -> shatter_transition) and at least 2 narrative-synchronized VFX elements (e.g. laser_beam + sunburst)."
            },
            "character_expressions_and_choreography": {
                "standard_emotions": ["calm", "wrath", "rage", "fear", "joy"],
                "choreography_modes": [
                    "dialogue_duel (two puppets facing each other with turn-taking talking gestures)",
                    "scale_swap (speaker scale 1.25, listener scale 1.05)",
                    "triad_council (three characters across stage: left, center, right)",
                    "humbled_confrontation (one puppet braced/kneeling in fear while the other towers)"
                ],
                "infographics": ["thought_bubble", "comparison_card", "symbol_infinity", "symbol_scales"],
                "outro_curtain_call": "Automated theatrical outro marquee and cast lineup at episode conclusion before curtains close."
            },
            "canvas_rule": "Strict clean canvas: zero burned-in subtitles by default (YouTube generates closed captions automatically)."
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
            "vfx": _list_svg_stems(assets_dir / "svg" / "vfx"),
            "infographics": _list_svg_stems(assets_dir / "svg" / "infographics"),
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

            for ep in plan.series_bible_json.episodes:
                used = cur.execute(
                    "SELECT episode_id FROM episodes WHERE bespoke_asset_path = ? AND status != 'FAILED'",
                    (ep.planned_bespoke_asset,),
                ).fetchone()
                if used is not None:
                    raise StateError(
                        f"Series bible episode {ep.episode_number} planned_bespoke_asset "
                        f"'{ep.planned_bespoke_asset}' was already used by episode_id={used['episode_id']}."
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

    conn = connect_db(db_path)
    try:
        with immediate_transaction(conn) as cur:
            fmt = ep_plan.content_format or "serial"

            if fmt == "standalone":
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
                    WHERE bespoke_asset_path = ? AND status != 'FAILED'
                    """,
                    (ep_plan.bespoke_asset_path,),
                ).fetchone()
                if dup_bespoke is not None:
                    raise StateError(
                        f"bespoke_asset_path '{ep_plan.bespoke_asset_path}' was already used "
                        f"by episode_id={dup_bespoke['episode_id']} (each episode requires a unique SVG)."
                    )

                script_json_str = json.dumps(ep_plan.model_dump(), ensure_ascii=False)
                cur.execute(
                    """
                    INSERT INTO episodes (
                        series_id, episode_number_in_series, global_episode_number,
                        content_format, youtube_title, summary, bespoke_asset_path, script_json,
                        youtube_video_id, scheduled_publish_at, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        pub_res.video_id,
                        pub_res.scheduled_publish_at,
                        pub_res.upload_status,
                    ),
                )
                episode_id = int(cur.lastrowid)

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

            # Serial or Episodic Series path: requires active series
            active = cur.execute(
                "SELECT * FROM series WHERE status = 'ACTIVE'"
            ).fetchone()
            if active is None:
                raise StateError("No ACTIVE series exists; cannot record episode.")

            if ep_plan.series_id is None or int(active["series_id"]) != ep_plan.series_id:
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
            if ep_plan.total_planned_episodes is None or int(active["total_planned_episodes"]) != ep_plan.total_planned_episodes:
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
                    content_format, youtube_title, summary, bespoke_asset_path, script_json,
                    youtube_video_id, scheduled_publish_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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