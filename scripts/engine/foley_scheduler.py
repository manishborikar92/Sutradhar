"""Sutradhar Video Engine — Keyframe Foley & Multi-Track BGM Scheduler (v4.0).

Automates:
1. Multi-Track BGM Selection mapped across 4 functional moods:
   - theatrical_narrative (epic, royal, majestic)
   - tense_confrontation (aggressive, martial, wrathful)
   - divine_cosmic (ethereal, celestial, mysterious)
   - melancholy_tragedy (sorrowful, solemn, bowed)
2. Authentic Acoustic Foley Mapping:
   - Synchronizes physical props (shattering Kundalis, stepping boots, eye beams, havan fires)
     with timestamped acoustic sound effects without volume crushing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Optional

from .config import (
    BGM_MOOD_CONFRONTATION,
    BGM_MOOD_COSMIC,
    BGM_MOOD_THEATRICAL,
    BGM_MOOD_TRAGEDY,
    PROP_COSMIC_EYE_BEAMS,
    PROP_FIRE_BRAZIER,
    PROP_PLANETARY_STAIRCASE,
    PROP_SUBJUGATION_BOOT,
    PROP_VEDIC_KUNDALI,
)

# Canonical mood-to-file mapping
MOOD_TO_BGM_FILE: Final[dict[str, str]] = {
    BGM_MOOD_THEATRICAL: "theatrical_narrative.mp3",
    BGM_MOOD_CONFRONTATION: "tense_confrontation.mp3",
    BGM_MOOD_COSMIC: "divine_cosmic.mp3",
    BGM_MOOD_TRAGEDY: "melancholy_tragedy.mp3",
    # Aliases
    "dramatic": "theatrical_narrative.mp3",
    "dramatic_mythology": "theatrical_narrative.mp3",
    "epic_history": "theatrical_narrative.mp3",
    "wrath": "tense_confrontation.mp3",
    "wrath_confrontation": "tense_confrontation.mp3",
    "confrontation": "tense_confrontation.mp3",
    "cosmic": "divine_cosmic.mp3",
    "cosmic_mystery": "divine_cosmic.mp3",
    "serene": "divine_cosmic.mp3",
    "serene_blessing": "divine_cosmic.mp3",
    "tragedy": "melancholy_tragedy.mp3",
    "sorrow": "melancholy_tragedy.mp3",
    "sorrow_tragedy": "melancholy_tragedy.mp3",
}

# Prop-to-SFX mapping
PROP_SFX_MAP: Final[dict[str, tuple[str, float]]] = {
    PROP_VEDIC_KUNDALI: ("crystal_shatter.wav", 0.55),     # Trigger at 55% of duration (shatter moment)
    PROP_PLANETARY_STAIRCASE: ("foot_thud.wav", 0.20),      # Stomp on steps
    PROP_SUBJUGATION_BOOT: ("foot_thud.wav", 0.30),         # Crushing stomp
    PROP_COSMIC_EYE_BEAMS: ("laser_strike.wav", 0.20),      # Eye beam ignition
    PROP_FIRE_BRAZIER: ("fire_crackle.wav", 0.10),          # Flame ignition
}

TRANSITION_SFX_MAP: Final[dict[str, str]] = {
    "curtain_open": "conch_blast.wav",
    "curtain_close": "curtain_whoosh.wav",
    "dramatic_zoom": "tension_swell.wav",
    "combat_strike": "sword_clash.wav",
    "sub_bass_drop": "sub_hit.wav",
}


@dataclass(frozen=True)
class FoleyCue:
    """Represents a scheduled sound effect cue."""

    sfx_name: str
    timestamp_sec: float
    volume_db: float = -10.0
    source_tag: str = "general"


def resolve_bgm_track(mood_or_name: str, bgm_dir: Optional[Path] = None) -> str:
    """Resolve a mood or filename to an authentic BGM audio file."""
    norm = mood_or_name.strip().lower()
    if norm in MOOD_TO_BGM_FILE:
        resolved = MOOD_TO_BGM_FILE[norm]
    elif norm.endswith(".mp3") or norm.endswith(".wav"):
        resolved = norm
    else:
        resolved = "theatrical_narrative.mp3"

    if bgm_dir and (bgm_dir / resolved).is_file():
        return resolved

    # Fallback to first available file in bgm_dir if specified
    if bgm_dir:
        fallback = next(bgm_dir.glob("*.mp3"), None) or next(bgm_dir.glob("*.wav"), None)
        if fallback:
            return fallback.name

    return resolved


def schedule_foley_for_episode(
    beats_or_scenes: list[dict[str, Any]],
    props_list: Optional[list[dict[str, Any]]] = None,
) -> list[FoleyCue]:
    """Analyze narrative beats and storytelling props to schedule precise Foley audio cues."""
    cues: list[FoleyCue] = []

    # 1. Opening Curtain / Prologue Conch Blast
    cues.append(FoleyCue(sfx_name="conch_blast.wav", timestamp_sec=0.1, volume_db=-8.0, source_tag="prologue"))

    # 2. Schedule SFX based on Beat Events & Camera Movements
    for idx, item in enumerate(beats_or_scenes):
        if hasattr(item, "start_sec"):
            st = float(item.start_sec)
            dur = float(item.duration_sec)
            cam = str(item.camera_motion or "static")
            explicit_sfx = getattr(item, "sfx_cue", None)
        else:
            st = float(item.get("start_sec", 0.0))
            dur = float(item.get("duration_sec", 2.5))
            cam = str(item.get("camera_motion", "static"))
            explicit_sfx = item.get("sfx_cue")

        if explicit_sfx:
            cues.append(FoleyCue(sfx_name=str(explicit_sfx), timestamp_sec=st + 0.15, source_tag="explicit_beat"))

        if cam == "dramatic_zoom":
            cues.append(FoleyCue(sfx_name="tension_swell.wav", timestamp_sec=round(st, 2), volume_db=-12.0, source_tag="camera_zoom"))
        elif cam in ("pan_left", "pan_right") and idx > 0:
            cues.append(FoleyCue(sfx_name="whoosh_soft.wav", timestamp_sec=round(st, 2), volume_db=-16.0, source_tag="camera_pan"))

    # 3. Schedule SFX based on Storytelling Props
    if props_list:
        for p in props_list:
            p_id = p.get("prop_id") or p.get("id", "")
            p_st = float(p.get("start_sec", 0.0))
            p_dur = float(p.get("duration_sec", 3.0))

            for known_prop, (sfx_file, offset_pct) in PROP_SFX_MAP.items():
                if known_prop in p_id:
                    trigger_t = round(p_st + (p_dur * offset_pct), 3)
                    cues.append(FoleyCue(sfx_name=sfx_file, timestamp_sec=trigger_t, volume_db=-8.0, source_tag=f"prop_{known_prop}"))

    # Sort strictly by timestamp
    cues.sort(key=lambda c: c.timestamp_sec)
    return cues
