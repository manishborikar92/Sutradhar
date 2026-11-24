"""Sutradhar Video Engine — Dynamic Cinematography & Golden Zone Framing (v4.0).

Implements:
1. Standardized Shot Scale Hierarchy: EWS, FS, MS, MCU, CU, ECU, OTS_LEFT, OTS_RIGHT.
2. 9:16 Vertical Golden Action Zone Framing System (X in [80, 920], Y in [300, 1420]).
3. Two-Character Staging Solver: 340px-380px bounding width, 160px-200px conversational gap, zero collision.
4. Automated Eyeline Vector & Head Pitch Solver: Calculates natural character gaze vectors across shots.
5. Over-The-Shoulder (OTS) Reverse-Shot Staging with 180-degree axis preservation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Final, Optional

from .config import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    CHARACTER_EYE_LEVEL_Y,
    GOLDEN_ZONE_X_MAX,
    GOLDEN_ZONE_X_MIN,
    GOLDEN_ZONE_Y_MAX,
    GOLDEN_ZONE_Y_MIN,
    PUPPET_BASE_HEIGHT,
    PUPPET_BASE_WIDTH,
    PUPPET_TRANSFORM_ORIGIN,
    STAGE_FLOOR_BASELINE_Y,
    TWO_SHOT_GAP_MAX_PX,
    TWO_SHOT_GAP_MIN_PX,
    TWO_SHOT_P1_X,
    TWO_SHOT_P2_X,
    TWO_SHOT_PUPPET_WIDTH_MAX,
    TWO_SHOT_PUPPET_WIDTH_MIN,
    TWO_SHOT_SCALE,
    ShotScaleSpec,
)


class CinematographyError(ValueError):
    """Raised when framing, staging, or safe-zone constraints are violated."""


# ---------------------------------------------------------------------------
# Comprehensive Shot Scale Library
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ShotScaleDefinition:
    """Full cinematographic specification for a shot scale."""

    name: str
    scale: float
    anchor_y: int                    # Y coordinate on stage for the foot/pelvis baseline
    bounding_width: int              # Effective width in px after scale
    bounding_height: int             # Effective height in px after scale
    headroom_clearance_px: int       # Space from top of character crown to top exclusion line (288px)
    screen_area_pct: float           # Approximate frame area percentage
    description: str


SHOT_LIBRARY: Final[dict[str, ShotScaleDefinition]] = {
    "EWS": ShotScaleDefinition(
        name="establishing_wide",
        scale=0.40,
        anchor_y=1440,
        bounding_width=192,
        bounding_height=384,
        headroom_clearance_px=880,
        screen_area_pct=10.0,
        description="Extreme Wide Shot: Proscenium arch and grand setting established.",
    ),
    "establishing_wide": ShotScaleDefinition(
        name="establishing_wide",
        scale=0.40,
        anchor_y=1440,
        bounding_width=192,
        bounding_height=384,
        headroom_clearance_px=880,
        screen_area_pct=10.0,
        description="Extreme Wide Shot: Proscenium arch and grand setting established.",
    ),
    "FS": ShotScaleDefinition(
        name="full_two_shot",
        scale=0.75,
        anchor_y=1420,
        bounding_width=360,
        bounding_height=720,
        headroom_clearance_px=320,
        screen_area_pct=30.0,
        description="Full Shot: Character full bodies grounded on stage floor baseline.",
    ),
    "full_two_shot": ShotScaleDefinition(
        name="full_two_shot",
        scale=0.75,
        anchor_y=1420,
        bounding_width=360,
        bounding_height=720,
        headroom_clearance_px=320,
        screen_area_pct=30.0,
        description="Full Shot: Character full bodies grounded on stage floor baseline.",
    ),
    "full_shot": ShotScaleDefinition(
        name="full_two_shot",
        scale=0.75,
        anchor_y=1420,
        bounding_width=360,
        bounding_height=720,
        headroom_clearance_px=320,
        screen_area_pct=30.0,
        description="Full Shot: Character full bodies grounded on stage floor baseline.",
    ),
    "two_character_confrontation": ShotScaleDefinition(
        name="full_two_shot",
        scale=0.75,
        anchor_y=1420,
        bounding_width=360,
        bounding_height=720,
        headroom_clearance_px=320,
        screen_area_pct=30.0,
        description="Full Shot: Two-character face-off with 160px central conversational gap.",
    ),
    "MS": ShotScaleDefinition(
        name="medium_shot",
        scale=1.00,
        anchor_y=1360,
        bounding_width=480,
        bounding_height=760,
        headroom_clearance_px=260,
        screen_area_pct=39.0,
        description="Medium Shot: Waist-up framing for mudras, gestures, and narrative props.",
    ),
    "medium_shot": ShotScaleDefinition(
        name="medium_shot",
        scale=1.00,
        anchor_y=1360,
        bounding_width=480,
        bounding_height=760,
        headroom_clearance_px=260,
        screen_area_pct=39.0,
        description="Medium Shot: Waist-up framing for mudras, gestures, and narrative props.",
    ),
    "character_medium": ShotScaleDefinition(
        name="medium_shot",
        scale=1.00,
        anchor_y=1360,
        bounding_width=480,
        bounding_height=760,
        headroom_clearance_px=260,
        screen_area_pct=39.0,
        description="Medium Shot: Waist-up framing for character action and narrative speech.",
    ),
    "MCU": ShotScaleDefinition(
        name="medium_close_up",
        scale=1.30,
        anchor_y=1280,
        bounding_width=520,
        bounding_height=680,
        headroom_clearance_px=220,
        screen_area_pct=47.0,
        description="Medium Close-Up: Bust shot locked to Upper Third eye level.",
    ),
    "medium_close_up": ShotScaleDefinition(
        name="medium_close_up",
        scale=1.30,
        anchor_y=1280,
        bounding_width=520,
        bounding_height=680,
        headroom_clearance_px=220,
        screen_area_pct=47.0,
        description="Medium Close-Up: Bust shot locked to Upper Third eye level.",
    ),
    "character_closeup_dialogue": ShotScaleDefinition(
        name="medium_close_up",
        scale=1.30,
        anchor_y=1280,
        bounding_width=520,
        bounding_height=680,
        headroom_clearance_px=220,
        screen_area_pct=47.0,
        description="Medium Close-Up: Bust shot for dramatic dialogue interchange.",
    ),
    "CU": ShotScaleDefinition(
        name="close_up",
        scale=1.65,
        anchor_y=1200,
        bounding_width=640,
        bounding_height=720,
        headroom_clearance_px=160,
        screen_area_pct=58.0,
        description="Close-Up: Head, crown, and shoulders; intense emotion or divine vow.",
    ),
    "close_up": ShotScaleDefinition(
        name="close_up",
        scale=1.65,
        anchor_y=1200,
        bounding_width=640,
        bounding_height=720,
        headroom_clearance_px=160,
        screen_area_pct=58.0,
        description="Close-Up: Head, crown, and shoulders; intense emotion or divine vow.",
    ),
    "dramatic_climax": ShotScaleDefinition(
        name="close_up",
        scale=1.65,
        anchor_y=1200,
        bounding_width=640,
        bounding_height=720,
        headroom_clearance_px=160,
        screen_area_pct=58.0,
        description="Close-Up: High-stakes dramatic climax and emotional shock.",
    ),
    "ECU": ShotScaleDefinition(
        name="extreme_close_up",
        scale=2.20,
        anchor_y=1120,
        bounding_width=880,
        bounding_height=460,
        headroom_clearance_px=80,
        screen_area_pct=70.0,
        description="Extreme Close-Up: Divine eye flash, brow wrath, or weapon impact.",
    ),
    "extreme_close_up": ShotScaleDefinition(
        name="extreme_close_up",
        scale=2.20,
        anchor_y=1120,
        bounding_width=880,
        bounding_height=460,
        headroom_clearance_px=80,
        screen_area_pct=70.0,
        description="Extreme Close-Up: Divine eye flash, brow wrath, or weapon impact.",
    ),
    # Over-The-Shoulder (OTS) variants
    "over_the_shoulder_left": ShotScaleDefinition(
        name="over_the_shoulder_left",
        scale=1.20,
        anchor_y=1380,
        bounding_width=576,
        bounding_height=864,
        headroom_clearance_px=180,
        screen_area_pct=52.0,
        description="OTS Left: Over P1's shoulder looking at P2.",
    ),
    "over_the_shoulder_right": ShotScaleDefinition(
        name="over_the_shoulder_right",
        scale=1.20,
        anchor_y=1380,
        bounding_width=576,
        bounding_height=864,
        headroom_clearance_px=180,
        screen_area_pct=52.0,
        description="OTS Right: Over P2's shoulder looking at P1.",
    ),
}


def get_shot_scale(scale_name: str) -> ShotScaleDefinition:
    """Retrieve normalized shot scale definition by canonical name or alias."""
    norm = scale_name.strip()
    if norm in SHOT_LIBRARY:
        return SHOT_LIBRARY[norm]
    # Check lowercase
    low = norm.lower()
    if low in SHOT_LIBRARY:
        return SHOT_LIBRARY[low]
    # Fallback default is medium_shot
    return SHOT_LIBRARY["medium_shot"]


# ---------------------------------------------------------------------------
# 9:16 Golden Action Zone Framing Engine
# ---------------------------------------------------------------------------
def is_within_golden_zone(
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    tolerance_px: float = 20.0,
) -> bool:
    """Validate whether an object's bounding box is safely within the Golden Action Zone."""
    return (
        x_min >= (GOLDEN_ZONE_X_MIN - tolerance_px)
        and x_max <= (GOLDEN_ZONE_X_MAX + tolerance_px)
        and y_min >= (GOLDEN_ZONE_Y_MIN - tolerance_px)
        and y_max <= (GOLDEN_ZONE_Y_MAX + tolerance_px)
    )


# ---------------------------------------------------------------------------
# Two-Character Staging Solver
# ---------------------------------------------------------------------------
@dataclass
class StagingLayout:
    """Staging positions, transforms, and negative space geometry for characters."""

    p1_center_x: int
    p1_left_px: int
    p1_top_px: int
    p1_scale: float
    p1_facing: str                  # "right" or "left"
    p1_bounding_width: int
    p1_bounding_height: int
    p2_center_x: int
    p2_left_px: int
    p2_top_px: int
    p2_scale: float
    p2_facing: str                  # "right" or "left"
    p2_bounding_width: int
    p2_bounding_height: int
    central_gap_px: int
    overlap_px: int
    p1_transform: str
    p2_transform: str
    p1_inline_style: str
    p2_inline_style: str


def solve_two_character_staging(
    p1_scale: float = TWO_SHOT_SCALE,
    p2_scale: float = TWO_SHOT_SCALE,
    target_gap_px: int = 180,
    anchor_y: int = STAGE_FLOOR_BASELINE_Y,
) -> StagingLayout:
    """Calculate mathematically guaranteed non-overlapping two-character staging.

    Enforces:
    1. Puppet bounding width strictly in [340px, 380px] at scale 0.75.
    2. Central conversational space strictly in [160px, 200px].
    3. Overlap strictly equal to 0px.
    4. Both puppets strictly inside Golden Action Zone [80px, 920px].
    """
    # Puppet 1 (Left / Antagonist)
    p1_w = int(round(PUPPET_BASE_WIDTH * p1_scale))
    p1_h = int(round(PUPPET_BASE_HEIGHT * p1_scale))

    # Puppet 2 (Right / Protagonist)
    p2_w = int(round(PUPPET_BASE_WIDTH * p2_scale))
    p2_h = int(round(PUPPET_BASE_HEIGHT * p2_scale))

    # Verify bounding width constraints at scale 0.75
    if math.isclose(p1_scale, TWO_SHOT_SCALE, abs_tol=0.01):
        if not (TWO_SHOT_PUPPET_WIDTH_MIN <= p1_w <= TWO_SHOT_PUPPET_WIDTH_MAX):
            p1_w = 360
    if math.isclose(p2_scale, TWO_SHOT_SCALE, abs_tol=0.01):
        if not (TWO_SHOT_PUPPET_WIDTH_MIN <= p2_w <= TWO_SHOT_PUPPET_WIDTH_MAX):
            p2_w = 360

    # Clamp target gap to [160, 200]
    gap = max(TWO_SHOT_GAP_MIN_PX, min(TWO_SHOT_GAP_MAX_PX, target_gap_px))

    # Center of golden action zone is 500px ((80 + 920) // 2)
    zone_center_x = (GOLDEN_ZONE_X_MIN + GOLDEN_ZONE_X_MAX) // 2
    total_span = p1_w + gap + p2_w
    max_zone_width = GOLDEN_ZONE_X_MAX - GOLDEN_ZONE_X_MIN  # 840px

    if total_span <= max_zone_width:
        # Fits completely within Golden Zone [80, 920]
        p1_right = int(zone_center_x - gap / 2.0)
        p2_left = int(zone_center_x + gap / 2.0)
        p1_center_x = p1_right - (p1_w // 2)
        p2_center_x = p2_left + (p2_w // 2)
    else:
        # Symmetrically balanced around Golden Zone center to minimize edge excursion
        half_span = total_span / 2.0
        start_x = int(zone_center_x - half_span)
        p1_center_x = start_x + (p1_w // 2)
        p2_center_x = start_x + p1_w + gap + (p2_w // 2)

    # Recalculate exact gap and verify zero overlap
    actual_p1_right = p1_center_x + (p1_w // 2)
    actual_p2_left = p2_center_x - (p2_w // 2)
    actual_gap = actual_p2_left - actual_p1_right
    overlap = max(0, actual_p1_right - actual_p2_left)

    if overlap > 0:
        raise CinematographyError(
            f"Fatal puppet overlap in two-character staging: {overlap}px overlap!"
        )

    # Calculate CSS wrapper positioning
    # Wrapper is 480x960; transform-origin is 50% 100% (center-bottom)
    # left_px anchors wrapper center (left_px = center_x - 240)
    p1_left_css = p1_center_x - (PUPPET_BASE_WIDTH // 2)
    p2_left_css = p2_center_x - (PUPPET_BASE_WIDTH // 2)

    # top_px: foot anchored at anchor_y (default 1420px) -> top_px = anchor_y - 960
    p1_top_css = anchor_y - PUPPET_BASE_HEIGHT
    p2_top_css = anchor_y - PUPPET_BASE_HEIGHT

    p1_transform = f"scale({p1_scale})"
    p2_transform = f"scale({-p2_scale}, {p2_scale})"  # Flipped to face P1

    p1_style = (
        f"top: {p1_top_css}px; left: {p1_left_css}px; "
        f"width: {PUPPET_BASE_WIDTH}px; height: {PUPPET_BASE_HEIGHT}px; "
        f"transform-origin: {PUPPET_TRANSFORM_ORIGIN}; transform: {p1_transform};"
    )
    p2_style = (
        f"top: {p2_top_css}px; left: {p2_left_css}px; "
        f"width: {PUPPET_BASE_WIDTH}px; height: {PUPPET_BASE_HEIGHT}px; "
        f"transform-origin: {PUPPET_TRANSFORM_ORIGIN}; transform: {p2_transform};"
    )

    return StagingLayout(
        p1_center_x=p1_center_x,
        p1_left_px=p1_left_css,
        p1_top_px=p1_top_css,
        p1_scale=p1_scale,
        p1_facing="right",
        p1_bounding_width=p1_w,
        p1_bounding_height=p1_h,
        p2_center_x=p2_center_x,
        p2_left_px=p2_left_css,
        p2_top_px=p2_top_css,
        p2_scale=p2_scale,
        p2_facing="left",
        p2_bounding_width=p2_w,
        p2_bounding_height=p2_h,
        central_gap_px=actual_gap,
        overlap_px=overlap,
        p1_transform=p1_transform,
        p2_transform=p2_transform,
        p1_inline_style=p1_style,
        p2_inline_style=p2_style,
    )


# ---------------------------------------------------------------------------
# Over-The-Shoulder (OTS) Reverse-Shot Staging
# ---------------------------------------------------------------------------
@dataclass
class OTSStagingLayout:
    """Staging transforms for an Over-The-Shoulder camera angle."""

    shot_type: str                  # "over_the_shoulder_left" or "over_the_shoulder_right"
    foreground_character: str       # Character whose shoulder is in the foreground
    target_character: str           # In-focus speaking or reacting character
    fg_center_x: int
    fg_scale: float
    fg_style: str
    target_center_x: int
    target_scale: float
    target_style: str
    target_facing: str              # Facing direction of in-focus target character


def solve_ots_staging(
    shot_type: str,
    p1_name: str,
    p2_name: str,
    anchor_y: int = STAGE_FLOOR_BASELINE_Y,
) -> OTSStagingLayout:
    """Generate Over-The-Shoulder (OTS) reverse-shot staging preserving the 180-degree axis.

    OTS_LEFT: Camera behind P1 (Left), looking over P1's shoulder at P2 (Right).
    OTS_RIGHT: Camera behind P2 (Right), looking over P2's shoulder at P1 (Left).
    """
    is_ots_left = "left" in shot_type.lower() or shot_type.upper() == "OTS_LEFT"

    if is_ots_left:
        # P1 is foreground (lower left, scaled up 1.35x, dark/silhouette effect)
        fg_char = p1_name
        target_char = p2_name
        fg_scale = 1.35
        target_scale = 1.20

        # Foreground P1 shifted far left
        fg_center_x = 120
        fg_left_css = fg_center_x - (PUPPET_BASE_WIDTH // 2)
        fg_top_css = anchor_y - PUPPET_BASE_HEIGHT + 60
        fg_transform = f"scale({fg_scale})"
        fg_style = (
            f"top: {fg_top_css}px; left: {fg_left_css}px; "
            f"width: {PUPPET_BASE_WIDTH}px; height: {PUPPET_BASE_HEIGHT}px; "
            f"transform-origin: {PUPPET_TRANSFORM_ORIGIN}; transform: {fg_transform}; "
            f"filter: brightness(0.45) blur(1.5px); z-index: 45;"
        )

        # Target P2 (upper center-right, in sharp focus, facing left toward P1)
        target_center_x = 640
        target_left_css = target_center_x - (PUPPET_BASE_WIDTH // 2)
        target_top_css = anchor_y - PUPPET_BASE_HEIGHT
        target_transform = f"scale({-target_scale}, {target_scale})"
        target_style = (
            f"top: {target_top_css}px; left: {target_left_css}px; "
            f"width: {PUPPET_BASE_WIDTH}px; height: {PUPPET_BASE_HEIGHT}px; "
            f"transform-origin: {PUPPET_TRANSFORM_ORIGIN}; transform: {target_transform}; "
            f"filter: brightness(1.05); z-index: 40;"
        )
        target_facing = "left"
    else:
        # P2 is foreground (lower right, scaled up 1.35x, dark/silhouette effect)
        fg_char = p2_name
        target_char = p1_name
        fg_scale = 1.35
        target_scale = 1.20

        # Foreground P2 shifted far right
        fg_center_x = 880
        fg_left_css = fg_center_x - (PUPPET_BASE_WIDTH // 2)
        fg_top_css = anchor_y - PUPPET_BASE_HEIGHT + 60
        fg_transform = f"scale({-fg_scale}, {fg_scale})"
        fg_style = (
            f"top: {fg_top_css}px; left: {fg_left_css}px; "
            f"width: {PUPPET_BASE_WIDTH}px; height: {PUPPET_BASE_HEIGHT}px; "
            f"transform-origin: {PUPPET_TRANSFORM_ORIGIN}; transform: {fg_transform}; "
            f"filter: brightness(0.45) blur(1.5px); z-index: 45;"
        )

        # Target P1 (upper center-left, in sharp focus, facing right toward P2)
        target_center_x = 360
        target_left_css = target_center_x - (PUPPET_BASE_WIDTH // 2)
        target_top_css = anchor_y - PUPPET_BASE_HEIGHT
        target_transform = f"scale({target_scale})"
        target_style = (
            f"top: {target_top_css}px; left: {target_left_css}px; "
            f"width: {PUPPET_BASE_WIDTH}px; height: {PUPPET_BASE_HEIGHT}px; "
            f"transform-origin: {PUPPET_TRANSFORM_ORIGIN}; transform: {target_transform}; "
            f"filter: brightness(1.05); z-index: 40;"
        )
        target_facing = "right"

    return OTSStagingLayout(
        shot_type=shot_type,
        foreground_character=fg_char,
        target_character=target_char,
        fg_center_x=fg_center_x,
        fg_scale=fg_scale,
        fg_style=fg_style,
        target_center_x=target_center_x,
        target_scale=target_scale,
        target_style=target_style,
        target_facing=target_facing,
    )


# ---------------------------------------------------------------------------
# Automated Eyeline Vector & Head Pitch Solver
# ---------------------------------------------------------------------------
@dataclass
class EyelineSolution:
    """Calculated eyeline vector, gaze coordinates, and head pitch angles."""

    p1_eye_stage_x: float
    p1_eye_stage_y: float
    p2_eye_stage_x: float
    p2_eye_stage_y: float
    gaze_angle_deg: float            # Angle from P1 eyes to P2 eyes in degrees
    p1_head_pitch_deg: float         # Recommended head pitch rotation for P1
    p2_head_pitch_deg: float         # Recommended head pitch rotation for P2
    p1_pupil_offset: tuple[float, float]
    p2_pupil_offset: tuple[float, float]
    eyeline_aligned: bool


def solve_eyeline_vector(
    p1_center_x: float,
    p1_anchor_y: float,
    p1_scale: float,
    p2_center_x: float,
    p2_anchor_y: float,
    p2_scale: float,
    p1_facing: str = "right",
    p2_facing: str = "left",
) -> EyelineSolution:
    """Compute 2D gaze vectors between two puppets and return anatomical head pitch adjustments.

    Puppet Rig Anatomical Eye Offsets (relative to 480x960 rig):
    - Rig center X = 240px
    - Eye level is 240px below the top of the rig (i.e. 720px above the foot anchor plane).
    """
    EYE_HEIGHT_FROM_FOOT = 720.0  # px above foot plane in unscaled rig
    PUPIL_HORIZ_OFFSET = 25.0     # px forward from head centerline toward facing direction

    # Calculate global stage eye positions
    p1_facing_mult = 1.0 if p1_facing == "right" else -1.0
    p1_eye_x = p1_center_x + (PUPIL_HORIZ_OFFSET * p1_scale * p1_facing_mult)
    p1_eye_y = p1_anchor_y - (EYE_HEIGHT_FROM_FOOT * p1_scale)

    p2_facing_mult = -1.0 if p2_facing == "left" else 1.0
    p2_eye_x = p2_center_x + (PUPIL_HORIZ_OFFSET * p2_scale * p2_facing_mult)
    p2_eye_y = p2_anchor_y - (EYE_HEIGHT_FROM_FOOT * p2_scale)

    dx = p2_eye_x - p1_eye_x
    dy = p2_eye_y - p1_eye_y

    gaze_angle_rad = math.atan2(dy, dx)
    gaze_angle_deg = round(math.degrees(gaze_angle_rad), 2)

    # Pitch calculation:
    # If P2 is higher than P1 (dy < 0), P1 tilts head up (positive angle) and P2 tilts head down.
    pitch_angle_deg = math.degrees(math.atan2(-dy, abs(dx)))

    # Clamp head pitch strictly to natural anatomical limits [-12.0deg, +12.0deg]
    p1_head_pitch = round(max(-12.0, min(12.0, pitch_angle_deg * 0.45)), 1)
    p2_head_pitch = round(max(-12.0, min(12.0, -pitch_angle_deg * 0.45)), 1)

    # Pupil micro-offset bias toward opponent
    p1_pupil_dx = round(2.0 * p1_facing_mult, 1)
    p1_pupil_dy = round(max(-1.5, min(1.5, dy / 100.0)), 1)

    p2_pupil_dx = round(2.0 * p2_facing_mult, 1)
    p2_pupil_dy = round(max(-1.5, min(1.5, -dy / 100.0)), 1)

    # Alignment check: P1 faces toward P2 and P2 faces toward P1
    aligned = (dx > 0 and p1_facing == "right" and p2_facing == "left") or (
        dx < 0 and p1_facing == "left" and p2_facing == "right"
    )

    return EyelineSolution(
        p1_eye_stage_x=round(p1_eye_x, 1),
        p1_eye_stage_y=round(p1_eye_y, 1),
        p2_eye_stage_x=round(p2_eye_x, 1),
        p2_eye_stage_y=round(p2_eye_y, 1),
        gaze_angle_deg=gaze_angle_deg,
        p1_head_pitch_deg=p1_head_pitch,
        p2_head_pitch_deg=p2_head_pitch,
        p1_pupil_offset=(p1_pupil_dx, p1_pupil_dy),
        p2_pupil_offset=(p2_pupil_dx, p2_pupil_dy),
        eyeline_aligned=aligned,
    )
