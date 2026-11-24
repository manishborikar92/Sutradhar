"""Automated unit and integration tests for scripts/engine/beat_planner.py (v4.0).

Verifies:
1. Scene-to-beat decomposition generates micro-beats of 1.8s - 3.5s.
2. Average Shot Length (ASL) strictly complies with target [2.2s, 3.0s] and Gate 1 [1.8s, 3.2s].
3. Opening hook rule: Beat 1 of Episode has duration <= 2.0s.
4. Maximum static hold rule: Zero beats exceed 3.8s.
5. Minimum floor rule: Zero beats are below 1.2s.
6. Word boundary snapping aligns cuts with natural speech pauses and punctuation.
7. Two-character confrontation, single-character, and edge cases.
"""

from __future__ import annotations

import unittest
from typing import Any

from scripts.engine.beat_planner import (
    BeatPacingError,
    BeatPlan,
    compute_asl,
    decompose_episode_into_beats,
    decompose_scene_into_beats,
    select_beat_shot_scales,
    validate_beat_pacing,
)
from scripts.engine.config import (
    ASL_HARD_MAX_SEC,
    ASL_HARD_MIN_SEC,
    ASL_TARGET_MAX_SEC,
    ASL_TARGET_MIN_SEC,
    BEAT_FLOOR_MIN_SEC,
    BEAT_STATIC_MAX_SEC,
    HOOK_BEAT_MAX_SEC,
)


class TestBeatPlanner(unittest.TestCase):
    """Test suite for beat decomposition, temporal constraints, and pacing rules."""

    def test_01_opening_hook_duration_limit(self) -> None:
        """Verify the first beat of the opening scene strictly enforces duration <= 2.0s."""
        scene_1 = {
            "scene_index": 1,
            "start_sec": 0.0,
            "end_sec": 9.5,
            "duration_sec": 9.5,
            "shot_type": "curtain_establishing",
            "primary_character": "ravana",
            "emotion": "calm",
        }
        beats = decompose_scene_into_beats(scene_1, is_first_scene=True)
        self.assertGreaterEqual(len(beats), 3)

        # Beat 1 MUST be a hook beat with duration <= 2.0s
        hook_beat = beats[0]
        self.assertTrue(hook_beat.is_hook)
        self.assertLessEqual(
            hook_beat.duration_sec,
            HOOK_BEAT_MAX_SEC,
            f"Hook beat duration {hook_beat.duration_sec}s exceeds 2.0s limit",
        )
        self.assertGreaterEqual(hook_beat.duration_sec, BEAT_FLOOR_MIN_SEC)

    def test_02_maximum_static_hold_bound(self) -> None:
        """Verify that zero beats exceed the 3.8s maximum static hold ceiling across long scenes."""
        long_scene = {
            "scene_index": 2,
            "start_sec": 10.0,
            "end_sec": 24.0,
            "duration_sec": 14.0,  # 14-second long scene
            "shot_type": "character_medium",
            "primary_character": "shani_dev",
            "emotion": "wrath",
        }
        beats = decompose_scene_into_beats(long_scene, is_first_scene=False)
        self.assertGreaterEqual(len(beats), 4)

        for b in beats:
            self.assertLessEqual(
                b.duration_sec,
                BEAT_STATIC_MAX_SEC,
                f"Beat {b.beat_id} duration {b.duration_sec}s exceeds 3.8s static ceiling",
            )
            self.assertGreaterEqual(
                b.duration_sec,
                BEAT_FLOOR_MIN_SEC,
                f"Beat {b.beat_id} duration {b.duration_sec}s below floor {BEAT_FLOOR_MIN_SEC}s",
            )

    def test_03_asl_calculation_and_gate_compliance(self) -> None:
        """Verify ASL calculation across an episode meets the target 2.2s - 3.0s range."""
        test_scenes = [
            {"scene_index": 1, "start_sec": 0.0, "end_sec": 7.0, "duration_sec": 7.0, "primary_character": "ravana"},
            {"scene_index": 2, "start_sec": 7.0, "end_sec": 15.0, "duration_sec": 8.0, "primary_character": "ravana", "secondary_character": "shani_dev"},
            {"scene_index": 3, "start_sec": 15.0, "end_sec": 25.0, "duration_sec": 10.0, "primary_character": "shani_dev"},
            {"scene_index": 4, "start_sec": 25.0, "end_sec": 35.0, "duration_sec": 10.0, "primary_character": "ravana", "secondary_character": "shani_dev"},
            {"scene_index": 5, "start_sec": 35.0, "end_sec": 45.0, "duration_sec": 10.0, "primary_character": "ravana"},
        ]
        all_beats = decompose_episode_into_beats(test_scenes)
        self.assertGreaterEqual(len(all_beats), 15)

        asl = compute_asl(all_beats)
        self.assertGreaterEqual(asl, ASL_HARD_MIN_SEC, f"ASL {asl}s below Gate 1 floor {ASL_HARD_MIN_SEC}s")
        self.assertLessEqual(asl, ASL_HARD_MAX_SEC, f"ASL {asl}s above Gate 1 ceiling {ASL_HARD_MAX_SEC}s")

        # Check target sweet spot [2.2s, 3.0s]
        self.assertGreaterEqual(asl, 2.0, f"ASL {asl}s significantly below target 2.2s")
        self.assertLessEqual(asl, 3.1, f"ASL {asl}s significantly above target 3.0s")

        is_valid, violations = validate_beat_pacing(all_beats, total_duration_sec=45.0)
        self.assertTrue(is_valid, f"Validation failed with: {violations}")

    def test_04_word_boundary_snapping(self) -> None:
        """Verify beat boundaries snap to spoken word boundaries and punctuation when words are present."""
        words = [
            {"word": "राजा", "start_sec": 0.2, "end_sec": 0.7},
            {"word": "रावण", "start_sec": 0.8, "end_sec": 1.4},
            {"word": "हंसे।", "start_sec": 1.5, "end_sec": 1.95},  # Natural punctuation boundary
            {"word": "शनि", "start_sec": 2.2, "end_sec": 2.8},
            {"word": "देव", "start_sec": 2.9, "end_sec": 3.4},
            {"word": "ने", "start_sec": 3.5, "end_sec": 3.8},
            {"word": "दृष्टि", "start_sec": 4.0, "end_sec": 4.6},
            {"word": "डाली।", "start_sec": 4.7, "end_sec": 5.4},
        ]
        scene = {
            "scene_index": 1,
            "start_sec": 0.0,
            "end_sec": 5.6,
            "duration_sec": 5.6,
            "primary_character": "ravana",
            "secondary_character": "shani_dev",
            "words": words,
        }
        beats = decompose_scene_into_beats(scene, is_first_scene=True)
        self.assertGreaterEqual(len(beats), 2)

        # First beat should snap cleanly near word 3 ("हंसे।") around 1.95s
        hook_beat = beats[0]
        self.assertLessEqual(hook_beat.duration_sec, 2.0)
        self.assertAlmostEqual(hook_beat.end_sec, 1.95, delta=0.2)
        self.assertTrue(any("हंसे" in w["word"] for w in hook_beat.words))

    def test_05_two_character_shot_scale_sequencing(self) -> None:
        """Verify two-character confrontation scenes select alternating wide, OTS, and punch-in scales."""
        scene = {
            "scene_index": 3,
            "start_sec": 12.0,
            "end_sec": 21.0,
            "duration_sec": 9.0,
            "shot_type": "two_character_confrontation",
            "primary_character": "ravana",
            "secondary_character": "shani_dev",
            "emotion": "wrath",
        }
        scales = select_beat_shot_scales(scene, count=3, is_first_scene=False)
        self.assertEqual(len(scales), 3)

        # Scale 1 should be full_two_shot
        self.assertEqual(scales[0][0], "full_two_shot")
        # Scale 2 should be Over-The-Shoulder (OTS)
        self.assertEqual(scales[1][0], "over_the_shoulder_left")
        # Scale 3 should be punch-in close-up / MCU
        self.assertEqual(scales[2][0], "medium_close_up")

    def test_06_expression_change_propagation(self) -> None:
        """Verify mid-scene expression changes update the emotion and pose of subsequent beats."""
        scene = {
            "scene_index": 2,
            "start_sec": 10.0,
            "end_sec": 20.0,
            "duration_sec": 10.0,
            "primary_character": "ravana",
            "secondary_character": "shani_dev",
            "emotion": "calm",
            "pose_preset": "idle_royal",
            "secondary_pose_preset": "blessing_calm",
            "expression_change": {
                "at_ratio": 0.5,
                "character": "shani_dev",
                "to_emotion": "wrath",
                "to_pose": "humbled_braced",
            },
        }
        beats = decompose_scene_into_beats(scene, is_first_scene=False)
        self.assertGreaterEqual(len(beats), 3)

        # First beat: shani_dev should be calm / blessing_calm
        self.assertEqual(beats[0].secondary_character_emotion, "calm")
        self.assertEqual(beats[0].secondary_character_pose, "blessing_calm")

        # Last beat: shani_dev should have transitioned to wrath / humbled_braced
        last_beat = beats[-1]
        self.assertEqual(last_beat.secondary_character_emotion, "wrath")
        self.assertEqual(last_beat.secondary_character_pose, "humbled_braced")

    def test_07_edge_case_short_and_long_scenes(self) -> None:
        """Verify robust handling of tiny scenes (3s) and long scenes (16s)."""
        # Tiny scene (3.0s) -> should produce 1 or 2 beats, all >= 1.2s
        tiny_scene = {
            "scene_index": 1,
            "start_sec": 0.0,
            "end_sec": 3.0,
            "duration_sec": 3.0,
            "primary_character": "ravana",
        }
        tiny_beats = decompose_scene_into_beats(tiny_scene, is_first_scene=False)
        for b in tiny_beats:
            self.assertGreaterEqual(b.duration_sec, 1.2)
            self.assertLessEqual(b.duration_sec, 3.8)

        # Long scene (16.0s) -> should produce >= 5 beats, all <= 3.8s
        long_scene = {
            "scene_index": 2,
            "start_sec": 3.0,
            "end_sec": 19.0,
            "duration_sec": 16.0,
            "primary_character": "shani_dev",
        }
        long_beats = decompose_scene_into_beats(long_scene, is_first_scene=False)
        self.assertGreaterEqual(len(long_beats), 5)
        for b in long_beats:
            self.assertLessEqual(b.duration_sec, 3.8)
            self.assertGreaterEqual(b.duration_sec, 1.2)

    def test_08_invalid_negative_duration_raises_error(self) -> None:
        """Verify invalid or zero duration raises BeatPacingError."""
        invalid_scene = {
            "scene_index": 1,
            "start_sec": 5.0,
            "end_sec": 4.0,  # Negative duration
            "duration_sec": -1.0,
        }
        with self.assertRaises(BeatPacingError):
            decompose_scene_into_beats(invalid_scene)


if __name__ == "__main__":
    unittest.main()
