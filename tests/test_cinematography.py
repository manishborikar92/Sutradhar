"""Unit and integration tests for Cinematography, Golden Zone, and Staging (Phase 2)."""

import math
import pytest

from scripts.engine.cinematography import (
    CinematographyError,
    EyelineSolution,
    OTSStagingLayout,
    SHOT_LIBRARY,
    ShotScaleDefinition,
    get_shot_scale,
    is_within_golden_zone,
    solve_eyeline_vector,
    solve_ots_staging,
    solve_two_character_staging,
)
from scripts.engine.config import (
    GOLDEN_ZONE_X_MAX,
    GOLDEN_ZONE_X_MIN,
    GOLDEN_ZONE_Y_MAX,
    GOLDEN_ZONE_Y_MIN,
    PUPPET_TRANSFORM_ORIGIN,
    TWO_SHOT_GAP_MAX_PX,
    TWO_SHOT_GAP_MIN_PX,
    TWO_SHOT_PUPPET_WIDTH_MAX,
    TWO_SHOT_PUPPET_WIDTH_MIN,
    TWO_SHOT_SCALE,
)


class TestShotLibrary:
    """Verifies standard shot scale definitions, hierarchy, and retrieval."""

    def test_canonical_scales_exist(self):
        canonical_keys = ["EWS", "FS", "MS", "MCU", "CU", "ECU", "over_the_shoulder_left", "over_the_shoulder_right"]
        for key in canonical_keys:
            assert key in SHOT_LIBRARY, f"Missing shot scale: {key}"
            scale_def = SHOT_LIBRARY[key]
            assert isinstance(scale_def, ShotScaleDefinition)
            assert scale_def.scale > 0
            assert scale_def.bounding_width > 0
            assert scale_def.bounding_height > 0
            assert scale_def.headroom_clearance_px >= 0

    def test_scale_hierarchy_monotonically_increases(self):
        scales = [
            SHOT_LIBRARY["EWS"].scale,
            SHOT_LIBRARY["FS"].scale,
            SHOT_LIBRARY["MS"].scale,
            SHOT_LIBRARY["MCU"].scale,
            SHOT_LIBRARY["CU"].scale,
            SHOT_LIBRARY["ECU"].scale,
        ]
        for i in range(len(scales) - 1):
            assert scales[i] < scales[i + 1], f"Scale hierarchy not strictly monotonic: {scales[i]} >= {scales[i+1]}"

    def test_shot_scale_aliases(self):
        assert get_shot_scale("EWS") == SHOT_LIBRARY["EWS"]
        assert get_shot_scale("establishing_wide") == SHOT_LIBRARY["EWS"]
        assert get_shot_scale("two_character_confrontation").name == SHOT_LIBRARY["FS"].name
        assert get_shot_scale("two_character_confrontation").scale == SHOT_LIBRARY["FS"].scale
        assert get_shot_scale("character_closeup_dialogue").name == SHOT_LIBRARY["MCU"].name
        assert get_shot_scale("dramatic_climax").name == SHOT_LIBRARY["CU"].name
        # Fallback for unrecognized shot
        fallback = get_shot_scale("unknown_angle_xyz")
        assert fallback == SHOT_LIBRARY["medium_shot"]


class TestGoldenActionZone:
    """Verifies 9:16 Golden Action Zone boundary enforcement."""

    def test_safely_inside_golden_zone(self):
        assert is_within_golden_zone(
            x_min=GOLDEN_ZONE_X_MIN + 20,
            x_max=GOLDEN_ZONE_X_MAX - 20,
            y_min=GOLDEN_ZONE_Y_MIN + 50,
            y_max=GOLDEN_ZONE_Y_MAX - 50,
        )

    def test_outside_horizontal_bounds(self):
        # Exceeds left bound
        assert not is_within_golden_zone(
            x_min=20,  # Below 80px minus tolerance
            x_max=500,
            y_min=400,
            y_max=1200,
            tolerance_px=10.0,
        )
        # Exceeds right bound
        assert not is_within_golden_zone(
            x_min=500,
            x_max=980,  # Above 920px plus tolerance
            y_min=400,
            y_max=1200,
            tolerance_px=10.0,
        )

    def test_outside_vertical_bounds(self):
        # Enters top exclusion zone (status bar / channel header)
        assert not is_within_golden_zone(
            x_min=100,
            x_max=800,
            y_min=150,  # Above Y=300px safe line
            y_max=1200,
            tolerance_px=10.0,
        )
        # Enters bottom exclusion zone (subtitles / UI)
        assert not is_within_golden_zone(
            x_min=100,
            x_max=800,
            y_min=500,
            y_max=1550,  # Below Y=1420px safe line
            tolerance_px=10.0,
        )


class TestTwoCharacterStaging:
    """Verifies mathematical guarantees of two-character confrontational staging."""

    def test_standard_two_shot_geometry(self):
        layout = solve_two_character_staging(
            p1_scale=TWO_SHOT_SCALE,
            p2_scale=TWO_SHOT_SCALE,
            target_gap_px=180,
            anchor_y=1420,
        )

        # 1. Puppet bounding width strictly in [340px, 380px]
        assert TWO_SHOT_PUPPET_WIDTH_MIN <= layout.p1_bounding_width <= TWO_SHOT_PUPPET_WIDTH_MAX
        assert TWO_SHOT_PUPPET_WIDTH_MIN <= layout.p2_bounding_width <= TWO_SHOT_PUPPET_WIDTH_MAX

        # 2. Central conversational spacing strictly in [160px, 200px]
        assert TWO_SHOT_GAP_MIN_PX <= layout.central_gap_px <= TWO_SHOT_GAP_MAX_PX

        # 3. Overlap strictly equal to 0px
        assert layout.overlap_px == 0

        # 4. Both puppets balanced around Golden Zone [80px, 920px]
        p1_left = layout.p1_center_x - (layout.p1_bounding_width // 2)
        p1_right = layout.p1_center_x + (layout.p1_bounding_width // 2)
        p2_left = layout.p2_center_x - (layout.p2_bounding_width // 2)
        p2_right = layout.p2_center_x + (layout.p2_bounding_width // 2)

        # Centered with minimal edge excursion (< 35px)
        assert p1_left >= GOLDEN_ZONE_X_MIN - 35
        assert p2_right <= GOLDEN_ZONE_X_MAX + 35
        assert p1_right <= p2_left  # Zero collision guarantee

        # 5. Transform origin and facing
        assert PUPPET_TRANSFORM_ORIGIN in layout.p1_inline_style
        assert PUPPET_TRANSFORM_ORIGIN in layout.p2_inline_style
        assert layout.p1_facing == "right"
        assert layout.p2_facing == "left"
        assert "scale(0.75)" in layout.p1_transform
        assert "scale(-0.75, 0.75)" in layout.p2_transform  # Flipped facing left

    def test_compact_two_shot_strictly_inside_golden_zone(self):
        # With scale 0.70 (336px width, clamped to 340px) and 160px gap: total span 840px
        layout = solve_two_character_staging(
            p1_scale=0.70,
            p2_scale=0.70,
            target_gap_px=160,
            anchor_y=1420,
        )
        p1_left = layout.p1_center_x - (layout.p1_bounding_width // 2)
        p2_right = layout.p2_center_x + (layout.p2_bounding_width // 2)
        assert p1_left >= GOLDEN_ZONE_X_MIN
        assert p2_right <= GOLDEN_ZONE_X_MAX
        assert layout.overlap_px == 0

    def test_target_gap_clamping(self):
        # Requested gap 100px should clamp up to 160px minimum
        layout_small = solve_two_character_staging(target_gap_px=100)
        assert layout_small.central_gap_px >= TWO_SHOT_GAP_MIN_PX

        # Requested gap 300px should clamp down to 200px maximum
        layout_large = solve_two_character_staging(target_gap_px=300)
        assert layout_large.central_gap_px <= TWO_SHOT_GAP_MAX_PX


class TestOTSStaging:
    """Verifies Over-The-Shoulder reverse-shot staging and 180-degree axis preservation."""

    def test_ots_left_staging(self):
        ots = solve_ots_staging(
            shot_type="over_the_shoulder_left",
            p1_name="ravana",
            p2_name="shani_dev",
            anchor_y=1380,
        )

        assert ots.shot_type == "over_the_shoulder_left"
        assert ots.foreground_character == "ravana"
        assert ots.target_character == "shani_dev"
        assert ots.fg_scale == 1.35
        assert ots.target_scale == 1.20
        assert ots.target_facing == "left"  # Target faces back toward foreground character
        assert "filter: brightness(0.45) blur(1.5px)" in ots.fg_style
        assert "filter: brightness(1.05)" in ots.target_style
        assert ots.fg_center_x < ots.target_center_x  # FG on left, target on right

    def test_ots_right_staging(self):
        ots = solve_ots_staging(
            shot_type="over_the_shoulder_right",
            p1_name="ravana",
            p2_name="shani_dev",
            anchor_y=1380,
        )

        assert ots.shot_type == "over_the_shoulder_right"
        assert ots.foreground_character == "shani_dev"
        assert ots.target_character == "ravana"
        assert ots.fg_scale == 1.35
        assert ots.target_scale == 1.20
        assert ots.target_facing == "right"  # Target faces back toward foreground character
        assert "filter: brightness(0.45) blur(1.5px)" in ots.fg_style
        assert "filter: brightness(1.05)" in ots.target_style
        assert ots.target_center_x < ots.fg_center_x  # Target on left, FG on right


class TestEyelineVectorSolver:
    """Verifies anatomical head pitch and gaze angle calculations."""

    def test_level_eyeline(self):
        # Both puppets at the exact same anchor Y and scale
        solution = solve_eyeline_vector(
            p1_center_x=300,
            p1_anchor_y=1420,
            p1_scale=0.75,
            p2_center_x=700,
            p2_anchor_y=1420,
            p2_scale=0.75,
            p1_facing="right",
            p2_facing="left",
        )

        assert isinstance(solution, EyelineSolution)
        assert math.isclose(solution.p1_eye_stage_y, solution.p2_eye_stage_y, abs_tol=1.0)
        assert math.isclose(solution.p1_head_pitch_deg, 0.0, abs_tol=0.1)
        assert math.isclose(solution.p2_head_pitch_deg, 0.0, abs_tol=0.1)
        assert solution.eyeline_aligned is True

    def test_unequal_height_eyeline_pitch(self):
        # P1 is lower than P2 (P2 is elevated on throne or larger scale)
        solution = solve_eyeline_vector(
            p1_center_x=300,
            p1_anchor_y=1420,
            p1_scale=0.70,
            p2_center_x=700,
            p2_anchor_y=1200,  # P2 higher up on stage
            p2_scale=0.85,
            p1_facing="right",
            p2_facing="left",
        )

        # P1 must tilt head UP (positive pitch), P2 must tilt head DOWN (negative pitch)
        assert solution.p1_head_pitch_deg > 0.0
        assert solution.p2_head_pitch_deg < 0.0

        # Must be strictly clamped to natural anatomical limits [-12.0 deg, +12.0 deg]
        assert -12.0 <= solution.p1_head_pitch_deg <= 12.0
        assert -12.0 <= solution.p2_head_pitch_deg <= 12.0
        assert solution.eyeline_aligned is True

    def test_misaligned_facing(self):
        # Both characters facing away from each other
        solution = solve_eyeline_vector(
            p1_center_x=300,
            p1_anchor_y=1420,
            p1_scale=0.75,
            p2_center_x=700,
            p2_anchor_y=1420,
            p2_scale=0.75,
            p1_facing="left",  # Facing away
            p2_facing="right",  # Facing away
        )
        assert solution.eyeline_aligned is False
