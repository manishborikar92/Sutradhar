"""Pydantic production contracts for Series Bibles, Episode Plans, Storyboard IR & Publishing."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any, Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

# ---------------------------------------------------------------------------
# Constants & Validation Patterns
# ---------------------------------------------------------------------------

RIG_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
AUDIO_FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.(mp3|wav|ogg|flac)$")
YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{3,128}$")
DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")

BESPOKE_ASSET_DIRS = (
    "assets/props",
    "assets/characters",
    "assets/environments",
)
CANONICAL_ASSET_PREFIXES = ("canvas_prop:", "character:", "environment:")

ENGLISH_CLIFFHANGER_TRIGGERS = (
    "to be continued",
    "part 2",
    "in part 2",
    "stay tuned for part",
    "stay tuned",
    "in the next episode",
    "in our next episode",
    "find out in the next",
    "find out in part",
    "next time on",
    "next episode",
    "continued in",
)

HINDI_CLIFFHANGER_TRIGGERS = (
    "अगले भाग में",
    "अगले एपिसोड में",
    "जारी रहेगा",
    "कहानी जारी",
    "पार्ट 2",
    "पार्ट २",
    "भाग 2",
    "भाग २",
    "देखिए अगले",
)

ALL_CLIFFHANGER_TRIGGERS = ENGLISH_CLIFFHANGER_TRIGGERS + HINDI_CLIFFHANGER_TRIGGERS


# ---------------------------------------------------------------------------
# Shared Field Validators & Text Utilities
# ---------------------------------------------------------------------------

def has_devanagari(text: str) -> bool:
    """Return True if text contains any Devanagari character."""
    return bool(DEVANAGARI_RE.search(text or ""))


def devanagari_token_ratio(text: str) -> float:
    """Compute fraction of whitespace-delimited words containing Devanagari characters."""
    cleaned = re.sub(r"\[[^\]]+\]", " ", text or "").strip()
    tokens = [tok for tok in cleaned.split() if tok]
    if not tokens:
        return 0.0
    hi_tokens = sum(1 for tok in tokens if DEVANAGARI_RE.search(tok))
    return hi_tokens / len(tokens)


def count_billed_chars(scenes: list[Any], default_tag: str = "[slowly, solemn, deep]") -> int:
    """Compute exact pre-TTS ElevenLabs billed characters across all scenes (including [tags])."""
    total = 0
    for sc in scenes:
        text = (getattr(sc, "narration_text", None) or "").strip()
        vocal_tag = getattr(sc, "vocal_tag", None)
        if text.startswith("["):
            total += len(text)
        elif vocal_tag:
            total += len(f"{vocal_tag.strip()} {text}")
        else:
            total += len(f"{default_tag} {text}")
    return total


def _blank_to_none(v: Any) -> Any:
    if isinstance(v, str) and v.strip() == "":
        return None
    return v


def _validate_tts_voice(value: str) -> str:
    voice = value.strip()
    if not voice:
        raise ValueError("tts_voice must not be empty")
    if voice in ("Viraj", "uuyFQegRan8rpIQCGu9K") or re.match(r"^[A-Za-z0-9_-]{20,24}$", voice):
        return voice
    if re.match(r"^[a-z0-9_]+$", voice):
        return voice
    raise ValueError(
        f"Invalid voice ID '{voice}' (expected Viraj, ElevenLabs voice ID, or valid voice identifier)"
    )


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
    cleaned = value.strip().replace("\\", "/")
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]

    # Canonical Schema v4 asset IDs (canvas_prop:<slug>, character:<slug>, environment:<slug>)
    for prefix in CANONICAL_ASSET_PREFIXES:
        if cleaned.startswith(prefix):
            slug = cleaned[len(prefix) :]
            if not RIG_SLUG_RE.match(slug):
                raise ValueError(
                    f"bespoke asset slug '{slug}' in '{cleaned}' must be lowercase alphanumeric/underscore/hyphen"
                )
            return cleaned

    posix = PurePosixPath(cleaned)
    if ".." in posix.parts or posix.is_absolute():
        raise ValueError(f"bespoke asset path '{value}' must be a relative path without '..'")

    parent_dir = posix.parent.as_posix()
    if parent_dir.startswith("assets/episodes/") and len(posix.parts) == 4:
        if not RIG_SLUG_RE.match(posix.stem):
            raise ValueError(
                f"bespoke asset filename stem '{posix.stem}' must be lowercase alphanumeric/underscore/hyphen"
            )
        return posix.as_posix()

    if parent_dir not in BESPOKE_ASSET_DIRS:
        raise ValueError(
            f"bespoke asset path '{cleaned}' must be a canonical ID ({CANONICAL_ASSET_PREFIXES}) "
            f"or sit inside one of {BESPOKE_ASSET_DIRS} (got '{parent_dir}')"
        )
    if posix.suffix.lower() != ".json":
        raise ValueError(f"bespoke asset path '{cleaned}' must end with '.json'")
    if not RIG_SLUG_RE.match(posix.stem):
        raise ValueError(
            f"bespoke asset filename stem '{posix.stem}' must be lowercase alphanumeric/underscore/hyphen"
        )
    return posix.as_posix()


# ---------------------------------------------------------------------------
# Narrative Templates & Story Research Models
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
            {"phase_index": 8, "phase_name": "Concluding Thought / Lesson", "structure_type": "concluding_thought", "narrative_goal": "Philosophical closure, moral resonance, or thematic reflection."},
        ],
    },
    "five_phase_compact_arc": {
        "name": "Five-Phase Compact Dramatic Arc",
        "description": "Streamlined arc optimized for 40-65s concise stories and sharp paradoxes.",
        "phases": [
            {"phase_index": 1, "phase_name": "Dramatic Hook", "structure_type": "hook", "narrative_goal": "Direct question or impossible paradox hooks the viewer instantly."},
            {"phase_index": 2, "phase_name": "Setup & Context", "structure_type": "premise", "narrative_goal": "Establish the rule, characters, or cosmic principle at play."},
            {"phase_index": 3, "phase_name": "Crisis Escalation", "structure_type": "escalation", "narrative_goal": "The tension peaks as the inevitable collision approaches."},
            {"phase_index": 4, "phase_name": "Climax / Turning Point", "structure_type": "climax", "narrative_goal": "The decisive turning point or revelation occurs."},
            {"phase_index": 5, "phase_name": "Resolution & Lesson", "structure_type": "resolution", "narrative_goal": "Conflict resolved, concluding with a memorable philosophical takeaway."},
        ],
    },
    "in_medias_res": {
        "name": "In Medias Res Dramatic Structure",
        "description": "Non-linear structure opening at the boiling point of confrontation before revealing origins and resolving.",
        "phases": [
            {"phase_index": 1, "phase_name": "Boiling Point Hook", "structure_type": "in_medias_res", "narrative_goal": "Open at the height of confrontation or disaster with zero preamble."},
            {"phase_index": 2, "phase_name": "Origin Rewind / Flashback", "structure_type": "flashback", "narrative_goal": "Rewind to the pivotal mistake or fateful vow that caused this clash."},
            {"phase_index": 3, "phase_name": "Escalation", "structure_type": "escalation", "narrative_goal": "Fast-forward through the chain of events leading back to the crisis."},
            {"phase_index": 4, "phase_name": "Climax Continuation", "structure_type": "climax", "narrative_goal": "Resume the opening confrontation and push it past the breaking point."},
            {"phase_index": 5, "phase_name": "Resolution & Closure", "structure_type": "resolution", "narrative_goal": "Decisive aftermath and philosophical meaning of the outcome."},
        ],
    },
}


class StoryResearch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_tradition: str = Field(..., min_length=3, max_length=250)
    canonical_story_summary: str = Field(..., min_length=15, max_length=2500)
    key_verified_facts: list[str] = Field(..., min_length=1)
    cross_checked_variants: Optional[str] = Field(default=None, max_length=1500)
    source_references: list[str] = Field(..., min_length=1)

    @field_validator("cross_checked_variants", mode="before")
    @classmethod
    def clean_variants(cls, v: Any) -> Any:
        return _blank_to_none(v)


class SeriesBibleEpisode(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    episode_number: int = Field(..., ge=1)
    working_title: str = Field(..., min_length=3, max_length=120)
    hook: str = Field(..., min_length=10, max_length=300)
    narrative_direction: str = Field(..., min_length=15, max_length=1000)
    planned_bespoke_asset: str = Field(..., min_length=6, max_length=255)
    satisfying_takeaway: str = Field(..., min_length=10, max_length=400)
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
    content_format: Optional[Literal["episodic_series", "serial"]] = "episodic_series"
    continuity_notes: Optional[str] = Field(default=None, max_length=1000)
    episodes: list[SeriesBibleEpisode] = Field(..., min_length=1)

    @field_validator("continuity_notes", mode="before")
    @classmethod
    def clean_continuity_notes(cls, v: Any) -> Any:
        return _blank_to_none(v)


class NewSeriesPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    content_format: Optional[Literal["episodic_series", "serial"]] = "episodic_series"
    series_title: str = Field(..., min_length=3, max_length=150)
    series_title_hi: Optional[str] = Field(default=None, min_length=2, max_length=150)
    pillar: str = Field(..., min_length=2, max_length=100)
    tts_voice: str = Field(..., min_length=4, max_length=120)
    bgm_track: str = Field(..., min_length=5, max_length=120)
    total_planned_episodes: Optional[int] = None
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
        return _validate_tts_voice(v)

    @field_validator("bgm_track")
    @classmethod
    def check_bgm_track(cls, v: str, info: ValidationInfo) -> str:
        cfg = (info.context or {}).get("config")
        return _validate_configured_bgm(v, cfg)

    @field_validator("total_planned_episodes")
    @classmethod
    def check_episode_count(cls, v: Optional[int], info: ValidationInfo) -> Optional[int]:
        if v is None:
            return None
        cfg = (info.context or {}).get("config")
        series_cfg = cfg.get("series", {}) if cfg else {}
        min_ep = series_cfg.get("min_episodes", 1)
        max_ep = series_cfg.get("max_episodes", 999999)
        if not (min_ep <= v <= max_ep):
            raise ValueError(f"total_planned_episodes must be between {min_ep} and {max_ep} (got {v})")
        return v

    @field_validator("series_bible_json", mode="before")
    @classmethod
    def decode_series_bible_str(cls, v: Any) -> Any:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError as exc:
                raise ValueError(f"series_bible_json string is not valid JSON: {exc}") from exc
        return v

    @model_validator(mode="after")
    def validate_bible_episode_alignment(self) -> "NewSeriesPlan":
        episodes = self.series_bible_json.episodes
        if self.total_planned_episodes is not None:
            if len(episodes) != self.total_planned_episodes:
                raise ValueError(
                    f"series_bible_json.episodes length ({len(episodes)}) must match "
                    f"total_planned_episodes ({self.total_planned_episodes})"
                )
            expected_nums = list(range(1, self.total_planned_episodes + 1))
        else:
            expected_nums = list(range(1, len(episodes) + 1))
        actual_nums = [ep.episode_number for ep in episodes]
        if actual_nums != expected_nums:
            raise ValueError(
                f"series_bible_json episode_number values must be strictly sequential "
                f"{expected_nums} (got {actual_nums})"
            )
        planned_assets = [ep.planned_bespoke_asset for ep in episodes]
        if len(planned_assets) != len(set(planned_assets)):
            raise ValueError("series_bible_json planned_bespoke_asset values must be unique across all episodes")
        return self

    def serialized_bible(self) -> str:
        return json.dumps(self.series_bible_json.model_dump(exclude_none=True), ensure_ascii=False)


# ---------------------------------------------------------------------------
# Redesign v2 Storyboard IR, Thumbnail & Visual Specification Models
# ---------------------------------------------------------------------------

class PropPlacement(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(..., min_length=2, max_length=80)
    kind: str = Field(..., min_length=2, max_length=80)
    mount: Literal["floor", "dais", "table", "pedestal", "terrain", "sky"] = "floor"
    x: float = Field(default=540.0, ge=-200.0, le=1280.0)
    y: Optional[float] = Field(default=None, ge=-200.0, le=2000.0)
    scale: float = Field(default=1.0, gt=0.1, le=4.0)
    cue_word: Optional[str] = Field(default=None, max_length=80)
    params: dict[str, Any] = Field(default_factory=dict)


class CharacterPlacement(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(..., min_length=2, max_length=80)
    role: str = Field(..., min_length=2, max_length=80)
    x: float = Field(default=540.0, ge=0.0, le=1080.0)
    surface_type: Literal["floor", "dais", "lotus", "terrain", "rock"] = "floor"
    pose: str = Field(default="standing_hero", min_length=2, max_length=60)
    expr: str = Field(default="calm", min_length=2, max_length=60)
    turn: float = Field(default=0.0, ge=-0.45, le=0.45)
    gaze_target: Optional[str] = Field(default=None, max_length=80)
    seated: Optional[bool] = Field(default=None)


class ContextualPill(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    enabled: bool = False
    text: Optional[str] = Field(default=None, max_length=48)
    subtext: Optional[str] = Field(default=None, max_length=80)
    y_px: int = Field(default=320, ge=295, le=1220)

    @model_validator(mode="after")
    def validate_enabled_text(self) -> "ContextualPill":
        if self.enabled and (not self.text or len(self.text.strip()) < 2):
            raise ValueError("contextual_pill requires non-empty text when enabled=True")
        return self


class SceneVisualSpec(BaseModel):
    """Declarative Canvas2D + DOM Storyboard IR descriptor for a single scene."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    atmosphere_mode: Literal["palace_court", "dawn_epic", "archival", "cosmic_explainer"]
    environment_preset: str = Field(..., min_length=2, max_length=100)
    horizon_y: int = Field(default=1142, ge=700, le=1500)
    camera_move: str = Field(..., min_length=2, max_length=60)
    transition_in: str = Field(default="fade", min_length=2, max_length=60)
    transition_sfx: Optional[str] = Field(default=None, max_length=80)
    bgm_mood: Literal["dramatic", "epic", "mystic", "cosmic", "wrath", "sorrow", "serene"] = "dramatic"
    props: list[PropPlacement] = Field(default_factory=list)
    characters: list[CharacterPlacement] = Field(default_factory=list)
    contextual_pill: ContextualPill = Field(default_factory=ContextualPill)
    environment_overrides: dict[str, Any] = Field(default_factory=dict)


class StoryboardIR(BaseModel):
    """Episode-level deterministic visual runtime contract."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    visual_direction_version: str = Field(default="v2_storycraft", min_length=2, max_length=40)
    width: int = Field(default=1080, ge=480, le=2160)
    height: int = Field(default=1920, ge=854, le=3840)
    fps: int = Field(default=30, ge=24, le=60)
    horizon_y: int = Field(default=1142, ge=700, le=1500)
    scenes: list[SceneVisualSpec] = Field(default_factory=list)


class ThumbnailSpec(BaseModel):
    """1080x1920 English Shorts thumbnail copy contract (strictly zero Devanagari)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    pill: str = Field(..., min_length=2, max_length=40)
    headline_line1: str = Field(..., min_length=2, max_length=32)
    headline_line2: str = Field(..., min_length=2, max_length=32)
    sub_pill: Optional[str] = Field(default=None, max_length=48)
    font_weight: Literal[500, 700, 800] = 800
    theme: str = Field(default="dawn_epic", min_length=2, max_length=60)

    @field_validator("pill", "headline_line1", "headline_line2", "sub_pill")
    @classmethod
    def enforce_english_only(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        if v is not None and has_devanagari(v):
            raise ValueError(f"thumbnail_spec.{info.field_name} must be English-only (found Devanagari)")
        return v


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
    speaker_role: Literal["narrator", "character_dialogue"] = "narrator"
    voice_override: Optional[str] = None
    vocal_tag: Optional[str] = None
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
    visual_spec: Optional[SceneVisualSpec] = None

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
        "vocal_tag",
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
                raise ValueError(f"transition_sfx '{cleaned}' not in configured sfx_tracks: {allowed}")
        return cleaned

    @model_validator(mode="after")
    def validate_mode_and_text_requirements(self) -> "ScenePlan":
        if len(self.narration_text.split()) < 3:
            raise ValueError(f"Scene {self.scene_index}: narration_text must contain at least 3 words")

        if self.visual_mode == "character_drama":
            if not self.primary_character:
                raise ValueError(f"Scene {self.scene_index}: primary_character is required for character_drama")
            if self.secondary_character and self.secondary_character == self.primary_character:
                raise ValueError(f"Scene {self.scene_index}: secondary_character cannot duplicate primary_character")
            if self.tertiary_character and (
                self.tertiary_character == self.primary_character
                or self.tertiary_character == self.secondary_character
            ):
                raise ValueError(
                    f"Scene {self.scene_index}: tertiary_character cannot duplicate primary or secondary character"
                )
            if self.active_diagram_stage is not None:
                raise ValueError(f"Scene {self.scene_index}: active_diagram_stage must be null for character_drama")
        elif self.visual_mode == "explainer_diagram":
            if not self.diagram_rig:
                raise ValueError(f"Scene {self.scene_index}: diagram_rig is required for explainer_diagram")
            if self.active_diagram_stage is None:
                raise ValueError(f"Scene {self.scene_index}: active_diagram_stage (1..4) is required for explainer_diagram")
        elif self.visual_mode == "kinetic_callout":
            if not self.callout_headline or len(self.callout_headline) < 2:
                raise ValueError(f"Scene {self.scene_index}: callout_headline is required for kinetic_callout")
            if self.active_diagram_stage is not None:
                raise ValueError(f"Scene {self.scene_index}: active_diagram_stage must be null for kinetic_callout")
        return self


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

    content_format: Optional[Literal["standalone", "episodic_series", "serial"]] = "episodic_series"
    story_arc: Optional[StoryArc] = None
    story_research: Optional[StoryResearch] = None
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
    bespoke_asset_path: str = Field(..., min_length=6, max_length=255)
    youtube_title: str = Field(..., min_length=5, max_length=100)
    youtube_description: str = Field(..., min_length=10, max_length=5000)
    youtube_tags: Optional[list[str]] = None
    summary: str = Field(..., min_length=10, max_length=1000)
    language: Literal["en", "hi"] = "en"
    audio_language: Optional[Literal["hi"]] = None
    caption_language: Optional[Literal["hi"]] = None
    metadata_language: Optional[Literal["en"]] = None
    thumbnail_language: Optional[Literal["en"]] = None
    thumbnail_spec: Optional[ThumbnailSpec] = None
    storyboard_ir: Optional[StoryboardIR] = None
    scenes: list[ScenePlan]

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
        series_cfg = cfg.get("series", {}) if cfg else {}
        min_ep = series_cfg.get("min_episodes", 1)
        max_ep = series_cfg.get("max_episodes", 999999)
        if not (min_ep <= v <= max_ep):
            raise ValueError(f"total_planned_episodes must be between {min_ep} and {max_ep} (got {v})")
        return v

    @field_validator("tts_voice")
    @classmethod
    def check_tts_voice(cls, v: str) -> str:
        return _validate_tts_voice(v)

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

    def total_billed_chars(self) -> int:
        return count_billed_chars(self.scenes)

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
        require_bespoke = cfg["series"].get("require_bespoke_asset_per_episode", True) if cfg else True

        if fmt != "standalone":
            if self.series_id is None:
                raise ValueError(f"series_id is required when content_format is '{fmt}'")
            if self.series_title is None:
                raise ValueError(f"series_title is required when content_format is '{fmt}'")
            if self.episode_number_in_series is None:
                raise ValueError(f"episode_number_in_series is required when content_format is '{fmt}'")
            if self.total_planned_episodes is not None and self.episode_number_in_series > self.total_planned_episodes:
                raise ValueError(
                    f"episode_number_in_series ({self.episode_number_in_series}) exceeds "
                    f"total_planned_episodes ({self.total_planned_episodes})"
                )

        if not (min_scenes <= len(self.scenes) <= max_scenes):
            raise ValueError(f"scenes count must be between {min_scenes} and {max_scenes} (got {len(self.scenes)})")

        expected_indices = list(range(1, len(self.scenes) + 1))
        actual_indices = [scene.scene_index for scene in self.scenes]
        if actual_indices != expected_indices:
            raise ValueError(f"scene_index values must be strictly sequential {expected_indices} (got {actual_indices})")

        if require_bespoke:
            asset = self.bespoke_asset_path
            if asset.startswith("canvas_prop:") or asset.startswith("assets/props/"):
                slug = asset.split(":", 1)[-1] if ":" in asset else PurePosixPath(asset).stem
                featured = any(
                    s.diagram_rig == slug
                    or s.backdrop_rig == slug
                    or (s.visual_spec is not None and any(p.id == slug or p.kind == slug for p in s.visual_spec.props))
                    for s in self.scenes
                )
                expected_field = "diagram_rig/backdrop_rig/visual_spec.props"
            elif asset.startswith("environment:") or asset.startswith("assets/environments/"):
                slug = asset.split(":", 1)[-1] if ":" in asset else PurePosixPath(asset).stem
                featured = any(
                    s.backdrop_rig == slug
                    or (s.visual_spec is not None and s.visual_spec.environment_preset == slug)
                    for s in self.scenes
                )
                expected_field = "backdrop_rig/visual_spec.environment_preset"
            elif asset.startswith("character:") or asset.startswith("assets/characters/"):
                slug = asset.split(":", 1)[-1] if ":" in asset else PurePosixPath(asset).stem
                featured = any(
                    s.primary_character == slug
                    or s.secondary_character == slug
                    or s.tertiary_character == slug
                    or (s.characters and slug in s.characters)
                    or (s.visual_spec is not None and any(c.id == slug for c in s.visual_spec.characters))
                    for s in self.scenes
                )
                expected_field = "characters/visual_spec.characters"
            elif asset.startswith("assets/episodes/"):
                featured = True
                expected_field = "episode_bespoke_asset"
            else:
                featured = False
                expected_field = "canonical_asset"

            if not featured:
                raise ValueError(
                    f"bespoke_asset_path '{self.bespoke_asset_path}' must be actively featured in at least one scene's {expected_field}"
                )

        if self.storyboard_ir is not None and self.storyboard_ir.scenes:
            if len(self.storyboard_ir.scenes) != len(self.scenes):
                raise ValueError(
                    f"storyboard_ir.scenes length ({len(self.storyboard_ir.scenes)}) must match scenes ({len(self.scenes)})"
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

            if arc.climax_scene_index is not None and not (1 <= arc.climax_scene_index <= total_scenes):
                raise ValueError(
                    f"story_arc.climax_scene_index ({arc.climax_scene_index}) must be within 1..{total_scenes}"
                )
            if arc.resolution_scene_index is not None and not (1 <= arc.resolution_scene_index <= total_scenes):
                raise ValueError(
                    f"story_arc.resolution_scene_index ({arc.resolution_scene_index}) must be within 1..{total_scenes}"
                )
            if (
                arc.climax_scene_index is not None
                and arc.resolution_scene_index is not None
                and arc.climax_scene_index > arc.resolution_scene_index
            ):
                raise ValueError(
                    f"story_arc.climax_scene_index ({arc.climax_scene_index}) cannot come after "
                    f"story_arc.resolution_scene_index ({arc.resolution_scene_index})"
                )
            for phase in arc.phases:
                if phase.scenes:
                    for s_idx in phase.scenes:
                        if not (1 <= s_idx <= total_scenes):
                            raise ValueError(
                                f"StoryPhase {phase.phase_index} ('{phase.phase_name}') references "
                                f"invalid scene_index {s_idx} (total scenes: {total_scenes})"
                            )

        if fmt in ("standalone", "episodic_series", "serial"):
            last_scene_text = self.scenes[-1].narration_text.lower()
            res_text = self.story_arc.resolution.lower() if self.story_arc and self.story_arc.resolution else ""
            summary_text = self.summary.lower()

            for trigger in ALL_CLIFFHANGER_TRIGGERS:
                if trigger in last_scene_text or trigger in res_text or trigger in summary_text:
                    prefix = (
                        "Standalone story completeness violation"
                        if fmt == "standalone"
                        else f"Episodic series story completeness violation ({fmt})"
                    )
                    raise ValueError(
                        f"{prefix}: found cliffhanger phrase '{trigger}'. "
                        "Every episode (standalone and episodic series) must fully resolve its central conflict "
                        "without unresolved forward cliffhangers."
                    )
        return self


class EpisodePlanV2(EpisodePlan):
    """Strict pre-TTS & pre-render EpisodePlan v2 enforcing bilingual policy & 900-char TTS ceiling."""

    language: Literal["hi"] = "hi"
    audio_language: Literal["hi"] = "hi"
    caption_language: Literal["hi"] = "hi"
    metadata_language: Literal["en"] = "en"
    thumbnail_language: Literal["en"] = "en"
    thumbnail_spec: ThumbnailSpec

    @model_validator(mode="after")
    def validate_v2_pre_tts_policy(self, info: ValidationInfo) -> "EpisodePlanV2":
        # 1. Pure English metadata guard (0 Devanagari allowed on YouTube metadata)
        if has_devanagari(self.youtube_title):
            raise ValueError("youtube_title must be pure English (found Devanagari)")
        if has_devanagari(self.youtube_description):
            raise ValueError("youtube_description must be pure English (found Devanagari)")
        if self.youtube_tags:
            for tag in self.youtube_tags:
                if has_devanagari(tag):
                    raise ValueError(f"youtube_tags entry '{tag}' must be pure English (found Devanagari)")

        # 2. Pure Hindi spoken narration guard (>= 70% Devanagari tokens)
        combined_narration = " ".join(s.narration_text for s in self.scenes)
        hi_ratio = devanagari_token_ratio(combined_narration)
        if hi_ratio < 0.70:
            raise ValueError(
                f"narration_text must contain >= 70% Devanagari tokens for audio_language='hi' "
                f"(got {hi_ratio:.2%})"
            )

        # 3. Pre-TTS ElevenLabs hard char cap (<= 900 billed chars, 760-840 target)
        cfg = (info.context or {}).get("config") or {}
        max_chars = int(cfg.get("tts", {}).get("max_billed_chars_per_episode", 900))
        billed = self.total_billed_chars()
        if billed > max_chars:
            raise ValueError(
                f"Pre-TTS character budget exceeded: {billed} billed chars > {max_chars} cap "
                "(target sweet spot: 760-840 billed chars including [vocal tags])."
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
        return v.strip().upper() if isinstance(v, str) else v

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
        if v is not None and not YOUTUBE_ID_RE.match(v):
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
            raise ValueError(f"scheduled_publish_at '{v}' is not a valid ISO-8601 timestamp") from exc
        if dt.tzinfo is None:
            raise ValueError(f"scheduled_publish_at '{v}' must include an explicit timezone ('Z' or '±HH:MM')")
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


StoryResearch.model_rebuild()
SeriesBibleEpisode.model_rebuild()
SeriesBible.model_rebuild()
NewSeriesPlan.model_rebuild()
StoryPhase.model_rebuild()
StoryArc.model_rebuild()
PropPlacement.model_rebuild()
CharacterPlacement.model_rebuild()
ContextualPill.model_rebuild()
SceneVisualSpec.model_rebuild()
StoryboardIR.model_rebuild()
ThumbnailSpec.model_rebuild()
ScenePlan.model_rebuild()
EpisodePlan.model_rebuild()
EpisodePlanV2.model_rebuild()
PublishResult.model_rebuild()


def emit_pacing_warnings(plan: EpisodePlan, cfg: dict[str, Any]) -> None:
    """Log non-fatal narration prosody word-count and TTS budget warnings to stderr."""
    fmt = getattr(plan, "content_format", None) or cfg.get("content_format", "episodic_series")
    format_pacing = cfg.get("format_pacing", {}).get(fmt, {})
    default_pacing = cfg.get("episode_pacing", {})
    min_words = format_pacing.get("min_words_per_scene", default_pacing.get("min_words_per_scene", 8))
    max_words = format_pacing.get("max_words_per_scene", default_pacing.get("max_words_per_scene", 35))
    for scene in plan.scenes:
        wc = len(scene.narration_text.split())
        if wc < min_words or wc > max_words:
            print(
                f"[WARN] Scene {scene.scene_index} has {wc} words "
                f"(target narration sweet spot: {min_words}-{max_words}).",
                file=sys.stderr,
            )
    billed = plan.total_billed_chars()
    soft_warn = int(cfg.get("tts", {}).get("target_billed_chars_max", 850))
    if billed > soft_warn:
        print(
            f"[WARN] Pre-TTS billed character estimate {billed} exceeds {soft_warn} soft target.",
            file=sys.stderr,
        )
