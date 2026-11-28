"""Unit & integration test suite for ElevenLabs audio pacing speed injection (v4.0).

Verifies:
1. Emotion and shot-type multipliers dynamically compute pacing speed.
2. Clamping ensures speed remains strictly within [0.80, 1.15].
3. The calculated speed is injected into `voice_settings["speed"]` during synthesis.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any, Optional

import numpy as np
import yaml

import scripts.build_audio as build_audio
from scripts.db_manager import cmd_init, connect_db

REPO_ROOT = Path(__file__).resolve().parent.parent


class CaptureElevenLabs:
    """Mock ElevenLabs TTS engine that captures calls and voice_settings."""

    def __init__(self, sample_rate: int = 48000) -> None:
        self.sample_rate = sample_rate
        self.calls: list[dict[str, Any]] = []

    def synthesize_scene(
        self,
        text: str,
        voice_id: Optional[str] = None,
        model_id: Optional[str] = None,
        voice_settings: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> tuple[np.ndarray, int]:
        self.calls.append({
            "text": text,
            "voice_id": voice_id,
            "model_id": model_id,
            "voice_settings": dict(voice_settings) if voice_settings else {},
        })
        n_samples = int(round(7.5 * self.sample_rate))
        t = np.linspace(0.0, 7.5, n_samples, endpoint=False, dtype=np.float32)
        samples = (0.3 * np.sin(2.0 * np.pi * 220.0 * t)).astype(np.float32)
        return samples, self.sample_rate

    def synthesize(
        self,
        text: str,
        voice_settings: Optional[dict[str, Any]] = None,
    ) -> tuple[np.ndarray, int]:
        return self.synthesize_scene(text, voice_settings=voice_settings)


class FakeWord:
    def __init__(self, word: str, start: float, end: float) -> None:
        self.word = word
        self.start = start
        self.end = end


class FakeSegment:
    def __init__(self, words: list[FakeWord]) -> None:
        self.words = words


class DummyWhisper:
    def transcribe(
        self,
        audio_path: str,
        language: str = "hi",
        word_timestamps: bool = True,
        initial_prompt: str = "",
        **kwargs: Any,
    ) -> tuple[list[FakeSegment], dict[str, Any]]:
        tokens = initial_prompt.split() if initial_prompt else ["dummy"]
        step = 3.5 / max(1, len(tokens))
        words = [FakeWord(tok, idx * step, (idx + 0.8) * step) for idx, tok in enumerate(tokens)]
        return [FakeSegment(words)], {"language": language}


class TestAudioPacingSpeedInjection(unittest.TestCase):
    """Verifies speed calculation and injection into voice_settings."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

        # Initialize test project structure
        cfg_source = (REPO_ROOT / "config.yaml").read_text(encoding="utf-8")
        (self.root / "config.yaml").write_text(cfg_source, encoding="utf-8")
        shutil.copytree(REPO_ROOT / "assets", self.root / "assets")

        cfg = yaml.safe_load(cfg_source)
        cmd_init(self.root, cfg)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_voice_settings_speed_injection_and_clamping(self) -> None:
        build_dir = self.root / "build"
        build_dir.mkdir(parents=True, exist_ok=True)

        plan = {
            "content_format": "standalone",
            "series_id": None,
            "series_title": None,
            "episode_number_in_series": None,
            "total_planned_episodes": None,
            "global_episode_number": 1,
            "target_duration_sec": 45.0,
            "target_duration_range": {"min_seconds": 40.0, "max_seconds": 60.0},
            "pillar": "Ancient Epics & Lore",
            "youtube_title": "Audio Speed Test",
            "youtube_description": "Test description",
            "summary": "Speed injection test",
            "bespoke_asset_path": "character:ravana",
            "tts_voice": "uuyFQegRan8rpIQCGu9K",
            "bgm_track": "dramatic_mythology.mp3",
            "narrative_structure": "five_phase_compact_arc",
            "story_arc": {
                "arc_title": "Audio Speed Arc",
                "premise": "Test premise",
                "central_conflict": "Test conflict",
                "resolution": "Test resolution",
                "narrative_structure": "five_phase_compact_arc",
                "climax_scene_index": 3,
                "resolution_scene_index": 4,
                "phases": [
                    {"phase_index": 1, "phase_name": "Hook", "narrative_goal": "Opening paradox."},
                    {"phase_index": 2, "phase_name": "Climax", "narrative_goal": "Cosmic reckoning."},
                ],
                "thematic_lesson": "Dharma always prevails.",
            },
            "scenes": [
                {
                    "scene_index": 1,
                    "narration_text": "शांत और गंभीर शुरुआत।",
                    "shot_type": "curtain_establishing",
                    "emotion": "calm",
                    "visual_mode": "character_drama",
                    "primary_character": "ravana",
                    "backdrop_rig": "golden_lanka_citadel",
                    "mood_palette": "golden_imperial",
                    "particle_theme": "golden_embers",
                    "camera_motion": "static",
                },
                {
                    "scene_index": 2,
                    "narration_text": "राजा रावण का प्रचंड क्रोध!",
                    "shot_type": "confrontation",
                    "emotion": "wrath",
                    "visual_mode": "character_drama",
                    "primary_character": "ravana",
                    "backdrop_rig": "golden_lanka_citadel",
                    "mood_palette": "crimson_wrath",
                    "particle_theme": "crimson_embers",
                    "camera_motion": "static",
                },
                {
                    "scene_index": 3,
                    "narration_text": "चरम सीमा पर महायुद्ध।",
                    "shot_type": "dramatic_climax",
                    "emotion": "shock",
                    "visual_mode": "character_drama",
                    "primary_character": "ravana",
                    "backdrop_rig": "golden_lanka_citadel",
                    "mood_palette": "cosmic_indigo",
                    "particle_theme": "starfield_warp",
                    "camera_motion": "static",
                },
                {
                    "scene_index": 4,
                    "narration_text": "स्पष्ट गति निर्देश का पालन।",
                    "shot_type": "character_medium",
                    "speed": 1.10,
                    "emotion": "calm",
                    "visual_mode": "character_drama",
                    "primary_character": "ravana",
                    "backdrop_rig": "golden_lanka_citadel",
                    "mood_palette": "golden_imperial",
                    "particle_theme": "golden_embers",
                    "camera_motion": "static",
                },
                {
                    "scene_index": 5,
                    "narration_text": "न्याय और धर्म की विजय।",
                    "shot_type": "philosophical_outro",
                    "emotion": "calm",
                    "visual_mode": "character_drama",
                    "primary_character": "ravana",
                    "backdrop_rig": "golden_lanka_citadel",
                    "mood_palette": "theatrical_folk_art",
                    "particle_theme": "golden_embers",
                    "camera_motion": "static",
                },
            ],
        }

        (build_dir / "episode_plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")

        mock_tts = CaptureElevenLabs(sample_rate=48000)

        res = build_audio.build_episode_audio(
            root=self.root,
            tts_factory=lambda c, r: mock_tts,
            whisper_factory=lambda c: DummyWhisper(),
        )

        self.assertEqual(res["status"], "ok")
        self.assertEqual(len(mock_tts.calls), 5)

        # 1. Scene 1 (calm / curtain_establishing) -> speed = 0.92 * 0.96 = 0.883
        call_1_settings = mock_tts.calls[0]["voice_settings"]
        self.assertIn("speed", call_1_settings)
        self.assertAlmostEqual(call_1_settings["speed"], 0.883, places=2)

        # 2. Scene 2 (wrath / confrontation) -> speed = 0.92 * 1.04 = 0.957
        call_2_settings = mock_tts.calls[1]["voice_settings"]
        self.assertIn("speed", call_2_settings)
        self.assertAlmostEqual(call_2_settings["speed"], 0.957, places=2)

        # 3. Scene 4 (explicit speed override = 1.10) -> speed = 1.10
        call_4_settings = mock_tts.calls[3]["voice_settings"]
        self.assertIn("speed", call_4_settings)
        self.assertEqual(call_4_settings["speed"], 1.10)

        # 4. Verify all injected speeds are clamped within valid ElevenLabs boundaries [0.80, 1.15]
        for idx, call in enumerate(mock_tts.calls):
            spd = call["voice_settings"]["speed"]
            self.assertGreaterEqual(spd, 0.80, f"Scene {idx + 1} speed {spd} below lower bound 0.80")
            self.assertLessEqual(spd, 1.15, f"Scene {idx + 1} speed {spd} above upper bound 1.15")


if __name__ == "__main__":
    unittest.main()
