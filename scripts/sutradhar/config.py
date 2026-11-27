"""Configuration loading, workspace path resolution, and strict language policy."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class StateError(RuntimeError):
    """Raised when a database invariant, config check, or state transition fails."""


class LanguagePolicy(BaseModel):
    """Strict Sutradhar language separation policy."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    audio_language: Literal["hi"] = "hi"
    caption_language: Literal["hi"] = "hi"
    metadata_language: Literal["en"] = "en"
    thumbnail_language: Literal["en"] = "en"


class PacingSpec(BaseModel):
    """Canonical duration, scene, and narration pacing constraints."""

    model_config = ConfigDict(extra="allow")

    target_duration_min_sec: float = Field(default=40.0, gt=0)
    target_duration_max_sec: float = Field(default=120.0, gt=0)
    hard_duration_min_sec: float = Field(default=30.0, gt=0)
    hard_duration_max_sec: float = Field(default=180.0, gt=0)
    min_scenes: int = Field(default=5, ge=1)
    max_scenes: int = Field(default=15, ge=1)
    min_words_per_scene: int = Field(default=8, ge=1)
    max_words_per_scene: int = Field(default=35, ge=1)


def get_project_root() -> Path:
    """Resolve repository root (supports SUTRADHAR_ROOT override for isolated tests)."""
    env_root = os.environ.get("SUTRADHAR_ROOT")
    if env_root:
        return Path(env_root).resolve()
    return Path(__file__).resolve().parents[2]


def get_language_policy(cfg: dict[str, Any]) -> LanguagePolicy:
    """Validate and return the channel's LanguagePolicy from loaded config."""
    channel = cfg.get("channel") or {}
    payload = {
        "audio_language": channel.get("audio_language")
        or channel.get("default_audio_language")
        or channel.get("primary_language", "hi"),
        "caption_language": channel.get("caption_language", "hi"),
        "metadata_language": channel.get("metadata_language", "en"),
        "thumbnail_language": channel.get("thumbnail_language", "en"),
    }
    try:
        return LanguagePolicy.model_validate(payload)
    except ValidationError as exc:
        raise StateError(
            "config.yaml language lock violated: expected Hindi audio/captions "
            f"and English metadata/thumbnails ({exc})"
        ) from exc


def validate_config(cfg: Any, config_path: Path) -> dict[str, Any]:
    """Validate config.yaml structure, language locks, pacing, and path settings."""
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
            "channel.primary_language in ('en', 'hi') and language_mode in "
            f"('global_english', 'per_channel') (got primary_language={primary_lang!r}, "
            f"language_mode={lang_mode!r})."
        )

    # Validate explicit strict v4 language split when declared or audio/metadata keys present
    if any(
        k in channel
        for k in ("audio_language", "caption_language", "metadata_language", "thumbnail_language")
    ):
        get_language_policy(cfg)

    if "languages" in cfg:
        langs = cfg["languages"]
        if not isinstance(langs, dict) or primary_lang not in langs:
            raise StateError(
                f"config.yaml languages must define a profile for primary_language '{primary_lang}'."
            )
        for lcode, lprof in langs.items():
            if not isinstance(lprof, dict):
                raise StateError(f"config.yaml languages.{lcode} profile must be a mapping.")
            if "narrator_voice" not in lprof and "narrator_voice_id" not in lprof:
                raise StateError(
                    f"config.yaml languages.{lcode} missing required voice key: 'narrator_voice'."
                )
            if "pronunciations_file" not in lprof:
                raise StateError(
                    f"config.yaml languages.{lcode} missing required key: 'pronunciations_file'."
                )

    pillars = channel.get("pillars")
    if not isinstance(pillars, list) or not pillars or not all(isinstance(p, str) and p.strip() for p in pillars):
        raise StateError("config.yaml channel.pillars must be a non-empty list of strings.")

    series_cfg = cfg.get("series", {})
    min_ep = series_cfg.get("min_episodes")
    max_ep = series_cfg.get("max_episodes")
    if min_ep is not None or max_ep is not None:
        if not isinstance(min_ep, int) or not isinstance(max_ep, int) or not (1 <= min_ep <= max_ep):
            raise StateError("config.yaml series.min_episodes/max_episodes must be valid integers with min <= max.")

    pacing = cfg["episode_pacing"]
    for key in ("min_scenes", "max_scenes", "min_words_per_scene", "max_words_per_scene"):
        if not isinstance(pacing.get(key), int) or pacing[key] < 1:
            raise StateError(f"config.yaml episode_pacing.{key} must be a positive integer.")
    if pacing["min_scenes"] > pacing["max_scenes"]:
        raise StateError("config.yaml episode_pacing.min_scenes cannot exceed max_scenes.")
    if pacing["min_words_per_scene"] > pacing["max_words_per_scene"]:
        raise StateError("config.yaml episode_pacing.min_words_per_scene cannot exceed max_words_per_scene.")
    try:
        PacingSpec.model_validate(pacing)
    except ValidationError as exc:
        raise StateError(f"config.yaml episode_pacing invalid: {exc}") from exc

    tts = cfg["tts"]
    if not isinstance(tts.get("engine"), str):
        raise StateError("config.yaml tts.engine must be a string.")
    max_chars = tts.get("max_billed_chars_per_episode")
    if max_chars is not None:
        if not isinstance(max_chars, int) or not (100 <= max_chars <= 900):
            raise StateError(
                f"config.yaml tts.max_billed_chars_per_episode must be between 100 and 900 (got {max_chars!r})."
            )
    if "default_voice" not in tts and "languages" in cfg:
        active_lprof = cfg["languages"].get(primary_lang, {})
        narr_v = active_lprof.get("narrator_voice") or active_lprof.get("narrator_voice_id")
        if isinstance(narr_v, dict):
            tts["default_voice"] = "+".join(f"{k}:{v}" for k, v in narr_v.items())
        elif isinstance(narr_v, str):
            tts["default_voice"] = narr_v
    if "default_voice" not in tts and "voice_id" in tts:
        tts["default_voice"] = tts["voice_id"]
    if not isinstance(tts.get("default_voice"), str):
        raise StateError("config.yaml tts.default_voice or tts.voice_id must be resolved to a string.")

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
            f"config.yaml publishing.upload_mode must be 'public', 'private_review', or 'scheduled' "
            f"(got {upload_mode!r})."
        )
    if not isinstance(pub.get("allow_public_or_scheduled"), bool):
        raise StateError("config.yaml publishing.allow_public_or_scheduled must be a boolean.")

    paths = cfg["paths"]
    for key in ("db_file", "build_dir", "assets_dir"):
        if not isinstance(paths.get(key), str) or not paths[key].strip():
            raise StateError(f"config.yaml paths.{key} must be a non-empty string.")

    content_format = cfg.get("content_format") or cfg.get("content", {}).get("format")
    if content_format is not None and content_format not in ("standalone", "episodic_series", "serial"):
        raise StateError(
            f"config.yaml content_format must be 'standalone', 'episodic_series', or 'serial' (got {content_format!r})."
        )

    dur_range = cfg.get("target_duration_range") or cfg.get("content", {}).get("target_duration_range")
    if dur_range is not None:
        if not isinstance(dur_range, dict):
            raise StateError("config.yaml target_duration_range must be a mapping.")
        min_s = dur_range.get("min_seconds")
        max_s = dur_range.get("max_seconds")
        if (
            not isinstance(min_s, (int, float))
            or not isinstance(max_s, (int, float))
            or min_s <= 0
            or min_s > max_s
        ):
            raise StateError(
                f"config.yaml target_duration_range min_seconds/max_seconds invalid (got {dur_range})."
            )

    return cfg


def load_config(root: Path) -> dict[str, Any]:
    """Read and validate config.yaml from the project root."""
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
    """Resolve configured project data, build, assets, and auditions directories."""
    paths_cfg = cfg["paths"]
    return {
        "db_file": (root / paths_cfg["db_file"]).resolve(),
        "build_dir": (root / paths_cfg["build_dir"]).resolve(),
        "assets_dir": (root / paths_cfg["assets_dir"]).resolve(),
        "auditions_dir": (root / paths_cfg.get("auditions_dir", "build/auditions")).resolve(),
    }


def load_json_file(path: Path, label: str) -> Any:
    """Load UTF-8 JSON file or raise StateError."""
    if not path.is_file():
        raise StateError(f"Required input file not found ({label}): {path}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        raise StateError(f"Malformed JSON in {path}: {exc}") from exc
