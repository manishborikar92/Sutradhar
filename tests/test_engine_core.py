"""Unit & integration test suite for Sutradhar Video Engine Core & Puppet Rig (v4.0).

Verifies:
1. Canonical 9:16 vertical geometry and Golden Action Zone standards.
2. Standardized 480x960px puppet dimensions and transform-origin: 50% 100%.
3. Anatomical joint constraints, permanently eliminating the 105deg scarecrow pose.
4. Redesigned bound captive pose (`humbled_braced`).
5. ContinuousLifeEngine biological cycles (breathing, blinks, saccades, weight shift).
"""

from __future__ import annotations

import unittest
from pathlib import Path

from scripts.engine.config import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    FPS,
    GOLDEN_ZONE_X_MAX,
    GOLDEN_ZONE_X_MIN,
    GOLDEN_ZONE_Y_MAX,
    GOLDEN_ZONE_Y_MIN,
    JOINT_LIMITS,
    PUPPET_BASE_HEIGHT,
    PUPPET_BASE_WIDTH,
    PUPPET_TRANSFORM_ORIGIN,
    SHOT_SCALES,
    STAGE_FLOOR_BASELINE_Y,
    TWO_SHOT_GAP_PX,
    TWO_SHOT_P1_X,
    TWO_SHOT_P2_X,
    TWO_SHOT_SCALE,
)
from scripts.engine.puppet_rig import (
    STANDARD_POSES,
    ContinuousLifeEngine,
    JointConstraintError,
    get_pose,
    get_puppet_wrapper_css,
    validate_joint_value,
    validate_pose,
)


class TestEngineConfig(unittest.TestCase):
    """Verifies core geometry and architectural invariants."""

    def test_canvas_and_golden_zone_invariants(self) -> None:
        self.assertEqual(CANVAS_WIDTH, 1080)
        self.assertEqual(CANVAS_HEIGHT, 1920)
        self.assertEqual(FPS, 30)
        self.assertEqual(STAGE_FLOOR_BASELINE_Y, 1420)

        # Golden Action Zone must be fully contained within canvas
        self.assertGreaterEqual(GOLDEN_ZONE_X_MIN, 80)
        self.assertLessEqual(GOLDEN_ZONE_X_MAX, 920)
        self.assertGreaterEqual(GOLDEN_ZONE_Y_MIN, 300)
        self.assertLessEqual(GOLDEN_ZONE_Y_MAX, 1420)

    def test_puppet_standard_dimensions(self) -> None:
        self.assertEqual(PUPPET_BASE_WIDTH, 480)
        self.assertEqual(PUPPET_BASE_HEIGHT, 960)
        self.assertEqual(PUPPET_TRANSFORM_ORIGIN, "50% 100%")

    def test_two_character_staging_clearance(self) -> None:
        # P1 center at 240, scale 0.75 -> width 360px -> occupies [60, 420]
        # P2 center at 760, scale 0.75 -> width 360px -> occupies [580, 940]
        p1_right = TWO_SHOT_P1_X + (PUPPET_BASE_WIDTH * TWO_SHOT_SCALE) / 2
        p2_left = TWO_SHOT_P2_X - (PUPPET_BASE_WIDTH * TWO_SHOT_SCALE) / 2
        central_gap = p2_left - p1_right

        self.assertEqual(central_gap, TWO_SHOT_GAP_PX)
        self.assertGreaterEqual(central_gap, 160, "Central gap between confrontation puppets must be >= 160px")

    def test_shot_scales_hierarchy(self) -> None:
        self.assertIn("establishing_wide", SHOT_SCALES)
        self.assertIn("full_two_shot", SHOT_SCALES)
        self.assertIn("medium_shot", SHOT_SCALES)
        self.assertIn("medium_close_up", SHOT_SCALES)
        self.assertIn("close_up", SHOT_SCALES)
        self.assertIn("extreme_close_up", SHOT_SCALES)

        # Scale must strictly increase from establishing wide to extreme close-up
        self.assertLess(SHOT_SCALES["establishing_wide"].scale, SHOT_SCALES["full_two_shot"].scale)
        self.assertLess(SHOT_SCALES["full_two_shot"].scale, SHOT_SCALES["medium_shot"].scale)
        self.assertLess(SHOT_SCALES["medium_shot"].scale, SHOT_SCALES["medium_close_up"].scale)
        self.assertLess(SHOT_SCALES["medium_close_up"].scale, SHOT_SCALES["close_up"].scale)
        self.assertLess(SHOT_SCALES["close_up"].scale, SHOT_SCALES["extreme_close_up"].scale)


class TestPuppetRigAndKinematics(unittest.TestCase):
    """Verifies puppet forward kinematics, joint limits, and life engine."""

    def test_elimination_of_105_deg_scarecrow_pose(self) -> None:
        # A 105deg shoulder angle violates anatomical limits [-40, 65]
        with self.assertRaises(JointConstraintError):
            validate_joint_value("--rot-shoulder-l", "105deg")

        with self.assertRaises(JointConstraintError):
            validate_joint_value("--rot-shoulder-r", "-105deg")

        with self.assertRaises(JointConstraintError):
            validate_pose({"--rot-shoulder-l": "105deg", "--rot-elbow-l": "55deg"})

    def test_joint_clamping_behavior(self) -> None:
        clamped_l = validate_joint_value("--rot-shoulder-l", "105deg", clamp=True)
        self.assertEqual(clamped_l, "65deg")

        clamped_r = validate_joint_value("--rot-shoulder-r", "-105deg", clamp=True)
        self.assertEqual(clamped_r, "-65deg")

        clamped_torso = validate_joint_value("--rot-torso", "25deg", clamp=True)
        self.assertEqual(clamped_torso, "6deg")

    def test_redesigned_humbled_braced_pose(self) -> None:
        pose = get_pose("humbled_braced")
        validated = validate_pose(pose)

        # Upper arms angled downward naturally (35deg / -35deg)
        self.assertEqual(validated["--rot-shoulder-l"], "35deg")
        self.assertEqual(validated["--rot-shoulder-r"], "-35deg")

        # Forearms crossed inward over chest (75deg / -75deg)
        self.assertEqual(validated["--rot-elbow-l"], "75deg")
        self.assertEqual(validated["--rot-elbow-r"], "-75deg")

        # Wrists clasped (15deg / -15deg)
        self.assertEqual(validated["--rot-wrist-l"], "15deg")
        self.assertEqual(validated["--rot-wrist-r"], "-15deg")

        # Torso pitched forward by 15px with 4deg incline
        self.assertEqual(validated["--trans-torso-y"], "15px")
        self.assertEqual(validated["--rot-torso"], "4deg")

        # Head bowed downward (-10deg)
        self.assertEqual(validated["--rot-head"], "-10deg")

    def test_all_standard_poses_satisfy_anatomical_limits(self) -> None:
        for pose_name, pose_vars in STANDARD_POSES.items():
            # validate_pose must not raise any JointConstraintError
            validated = validate_pose(pose_vars, clamp=False)
            self.assertIsInstance(validated, dict)
            self.assertGreater(len(validated), 0, f"Pose '{pose_name}' is empty")

    def test_puppet_wrapper_css_conforms_to_specs(self) -> None:
        css = get_puppet_wrapper_css()
        self.assertIn(f"width: {PUPPET_BASE_WIDTH}px;", css)
        self.assertIn(f"height: {PUPPET_BASE_HEIGHT}px;", css)
        self.assertIn(f"transform-origin: {PUPPET_TRANSFORM_ORIGIN};", css)


class TestContinuousLifeEngine(unittest.TestCase):
    """Verifies the ContinuousLifeEngine generates natural biological cycles."""

    def test_life_engine_parameters(self) -> None:
        engine = ContinuousLifeEngine()
        self.assertEqual(engine.breathing_cycle_sec, 2.2)
        self.assertEqual(engine.breathing_scale_y, 1.025)
        self.assertEqual(engine.shoulder_float_px, 2.0)
        self.assertEqual(engine.blink_interval_min, 2.8)
        self.assertEqual(engine.blink_interval_max, 4.2)
        self.assertEqual(engine.blink_closed_sec, 0.070)
        self.assertEqual(engine.saccade_interval_sec, 1.2)
        self.assertEqual(engine.saccade_offset_px, 2.5)
        self.assertEqual(engine.weight_shift_sec, 3.8)
        self.assertEqual(engine.weight_shift_angle_deg, 1.2)
        self.assertEqual(engine.follow_through_lag_ms, 120)

    def test_life_engine_gsap_code_generation(self) -> None:
        engine = ContinuousLifeEngine()
        code = engine.generate_gsap_code("puppet_shani_dev", duration_sec=40.0)

        # Diaphragmatic breathing
        self.assertIn("Diaphragmatic Breathing", code)
        self.assertIn("scaleY: 1.025", code)
        self.assertIn("duration: 1.1", code)  # Half of 2.2s cycle
        self.assertIn('ease: "sine.inOut"', code)

        # Autonomous blinking
        self.assertIn("Autonomous Blinking", code)
        self.assertIn("seededRandom(2.8, 4.2)", code)
        self.assertIn("0.07", code)  # Closed duration

        # Micro-saccades
        self.assertIn("Eye Micro-Saccades", code)
        self.assertIn("seededRandom(-2.5, 2.5)", code)

        # Weight shift
        self.assertIn("Idle Weight Shift", code)
        self.assertIn('rotation: "+=1.2"', code)
        self.assertIn("duration: 1.9", code)  # Half of 3.8s cycle

        # Passive follow-through
        self.assertIn("Passive Follow-Through", code)
        self.assertIn("delay: 0.12", code)  # 120ms lag


if __name__ == "__main__":
    unittest.main()
