"""Unit tests for Phase 3 Background Music & Keyframe Foley Scheduler.

Verifies:
1. Multi-Track BGM Selection across 4 functional moods:
   - theatrical_narrative
   - tense_confrontation
   - divine_cosmic
   - melancholy_tragedy
2. BGM full-length duration (>= 160 seconds) eliminating mechanical 56.03s loop.
3. 48,000Hz stereo specifications on BGM and authentic SFX audio files.
4. Foley scheduler cue generation for prologue conch blast, camera motions, and props.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.engine.config import (
    BGM_MOOD_CONFRONTATION,
    BGM_MOOD_COSMIC,
    BGM_MOOD_THEATRICAL,
    BGM_MOOD_TRAGEDY,
    PROP_FIRE_BRAZIER,
    PROP_SUBJUGATION_BOOT,
    PROP_VEDIC_KUNDALI,
)
from scripts.engine.foley_scheduler import (
    MOOD_TO_BGM_FILE,
    PROP_SFX_MAP,
    FoleyCue,
    resolve_bgm_track,
    schedule_foley_for_episode,
)
from scripts.render_and_qa import probe_media


class TestBgmResolution:
    """Tests resolution of functional moods to 48kHz BGM files."""

    def test_canonical_moods_resolution(self):
        assert resolve_bgm_track(BGM_MOOD_THEATRICAL) == "theatrical_narrative.mp3"
        assert resolve_bgm_track(BGM_MOOD_CONFRONTATION) == "tense_confrontation.mp3"
        assert resolve_bgm_track(BGM_MOOD_COSMIC) == "divine_cosmic.mp3"
        assert resolve_bgm_track(BGM_MOOD_TRAGEDY) == "melancholy_tragedy.mp3"

    def test_mood_aliases_resolution(self):
        assert resolve_bgm_track("dramatic") == "theatrical_narrative.mp3"
        assert resolve_bgm_track("wrath") == "tense_confrontation.mp3"
        assert resolve_bgm_track("cosmic") == "divine_cosmic.mp3"
        assert resolve_bgm_track("sorrow") == "melancholy_tragedy.mp3"

    def test_unknown_mood_fallback(self):
        assert resolve_bgm_track("unknown_mood") == "theatrical_narrative.mp3"


@pytest.mark.skipif(shutil.which("ffprobe") is None, reason="ffprobe not found on PATH")
class TestBgmPhysicalAudioProperties:
    """Verifies physical properties of master BGM files on disk."""

    @pytest.mark.parametrize(
        "track_name",
        [
            "theatrical_narrative.mp3",
            "tense_confrontation.mp3",
            "divine_cosmic.mp3",
            "melancholy_tragedy.mp3",
        ],
    )
    def test_bgm_tracks_48k_stereo_duration(self, track_name: str):
        bgm_path = REPO_ROOT / "assets" / "bgm" / track_name
        assert bgm_path.is_file(), f"BGM file missing: {bgm_path}"

        info = probe_media(bgm_path)
        streams = info.get("streams", [])
        a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
        assert a_stream is not None

        # Verify 48kHz and 2-channel stereo
        assert int(a_stream.get("sample_rate", 0)) == 48000
        assert int(a_stream.get("channels", 0)) == 2

        # Verify duration >= 160s (eliminates 56.03s loop problem)
        duration = float(info.get("format", {}).get("duration", 0.0))
        assert duration >= 160.0, f"BGM track {track_name} is only {duration}s (< 160s limit)"


@pytest.mark.skipif(shutil.which("ffprobe") is None, reason="ffprobe not found on PATH")
class TestSfxPhysicalAudioProperties:
    """Verifies authentic 48kHz acoustic Foley assets."""

    @pytest.mark.parametrize(
        "sfx_file",
        [
            "metal_clang.wav",
            "foot_thud.wav",
            "chain_rattle.wav",
            "fire_crackle.wav",
            "conch_blast.wav",
        ],
    )
    def test_sfx_tracks_48k(self, sfx_file: str):
        sfx_path = REPO_ROOT / "assets" / "sfx" / sfx_file
        assert sfx_path.is_file(), f"SFX file missing: {sfx_path}"

        info = probe_media(sfx_path)
        streams = info.get("streams", [])
        a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
        assert a_stream is not None

        # Verify 48kHz and 2 channels
        assert int(a_stream.get("sample_rate", 0)) == 48000
        assert int(a_stream.get("channels", 0)) == 2


class TestFoleyScheduler:
    """Verifies automated keyframe Foley scheduling."""

    def test_prologue_conch_blast_scheduled(self):
        cues = schedule_foley_for_episode([])
        assert len(cues) >= 1
        assert cues[0].sfx_name == "conch_blast.wav"
        assert cues[0].timestamp_sec == 0.1

    def test_prop_impact_scheduling(self):
        beats = [
            {"start_sec": 0.0, "duration_sec": 5.0, "camera_motion": "push_in"},
            {"start_sec": 5.0, "duration_sec": 4.0, "camera_motion": "dramatic_zoom"},
        ]
        props = [
            {"id": "p_kundali", "prop_id": PROP_VEDIC_KUNDALI, "start_sec": 1.0, "duration_sec": 4.0},
            {"id": "p_boot", "prop_id": PROP_SUBJUGATION_BOOT, "start_sec": 6.0, "duration_sec": 3.0},
        ]
        cues = schedule_foley_for_episode(beats, props_list=props)

        # Conch blast at 0.1s
        assert cues[0].sfx_name == "conch_blast.wav"

        # Kundali shatter scheduled at start_sec + (duration * 0.55) = 1.0 + 2.2 = 3.2s
        kundali_cue = next((c for c in cues if c.sfx_name == "crystal_shatter.wav"), None)
        assert kundali_cue is not None
        assert abs(kundali_cue.timestamp_sec - 3.2) < 0.05

        # Dramatic zoom tension swell at 5.0s
        zoom_cue = next((c for c in cues if c.sfx_name == "tension_swell.wav"), None)
        assert zoom_cue is not None
        assert zoom_cue.timestamp_sec == 5.0

        # Boot stomp at start_sec + (duration * 0.30) = 6.0 + 0.9 = 6.9s
        boot_cue = next((c for c in cues if c.sfx_name == "foot_thud.wav"), None)
        assert boot_cue is not None
        assert abs(boot_cue.timestamp_sec - 6.9) < 0.05

        # Cues should be strictly sorted by timestamp
        timestamps = [c.timestamp_sec for c in cues]
        assert timestamps == sorted(timestamps)
