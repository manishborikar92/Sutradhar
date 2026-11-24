"""Sutradhar Video Engine — Central Architectural & Geometric Invariants (v4.0).

Defines standard 9:16 vertical canvas boundaries, Golden Action Zone,
puppet proportions, joint kinematic limits, and life engine invariants.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# ---------------------------------------------------------------------------
# Canvas & Render Standards
# ---------------------------------------------------------------------------
CANVAS_WIDTH: Final[int] = 1080
CANVAS_HEIGHT: Final[int] = 1920
FPS: Final[int] = 30
AUDIO_SAMPLE_RATE: Final[int] = 48000
AUDIO_CHANNELS: Final[int] = 2  # Broadcast Stereo

# ---------------------------------------------------------------------------
# 9:16 Vertical Safe Zones & Golden Zone
# ---------------------------------------------------------------------------
# Top exclusion zone (Search, UI, Audio Bar, Status Icons)
TOP_EXCLUSION_PX: Final[int] = 288

# Bottom exclusion zone (Captions, Video Title, Channel Badge, Subscribe CTA)
BOTTOM_EXCLUSION_PX: Final[int] = 500  # Y in [1420, 1920]

# Horizontal margins (Right rail reserved for Like/Comment/Share buttons)
LEFT_MARGIN_PX: Final[int] = 80
RIGHT_MARGIN_PX: Final[int] = 160  # Safe from right-side engagement overlay (920px - 1080px)

# Golden Action Zone (All critical narrative staging must fit inside)
GOLDEN_ZONE_X_MIN: Final[int] = 80
GOLDEN_ZONE_X_MAX: Final[int] = 920
GOLDEN_ZONE_Y_MIN: Final[int] = 300
GOLDEN_ZONE_Y_MAX: Final[int] = 1420

# Canonical Theatrical Stage Anchors
CHARACTER_EYE_LEVEL_Y: Final[int] = 700   # Upper Third Rule
STAGE_CENTER_ACTION_X: Final[int] = 500
STAGE_CENTER_ACTION_Y: Final[int] = 900
STAGE_FLOOR_BASELINE_Y: Final[int] = 1420  # Stage floor ellipse contact plane

# ---------------------------------------------------------------------------
# Standardized Puppet Dimensions & Staging Math
# ---------------------------------------------------------------------------
PUPPET_BASE_WIDTH: Final[int] = 480
PUPPET_BASE_HEIGHT: Final[int] = 960
PUPPET_TRANSFORM_ORIGIN: Final[str] = "50% 100%"

# Two-Character Confrontation Staging (Full Shot)
TWO_SHOT_SCALE: Final[float] = 0.75  # 360px bounding width, 720px height (37.5% screen height)
TWO_SHOT_P1_X: Final[int] = 240      # Center X for left puppet (occupies [60, 420])
TWO_SHOT_P2_X: Final[int] = 760      # Center X for right puppet (flipped, occupies [580, 940])
TWO_SHOT_GAP_PX: Final[int] = 160    # Central negative space gap [420, 580] = 160px clearance
TWO_SHOT_MAX_PUPPET_WIDTH: Final[int] = 400

# ---------------------------------------------------------------------------
# Standardized Shot Scale Hierarchy
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ShotScaleSpec:
    name: str
    scale: float
    anchor_y: int
    bounding_width: int
    bounding_height: int
    screen_height_pct: float
    description: str


SHOT_SCALES: Final[dict[str, ShotScaleSpec]] = {
    "establishing_wide": ShotScaleSpec(
        name="establishing_wide",
        scale=0.40,
        anchor_y=1440,
        bounding_width=192,
        bounding_height=384,
        screen_height_pct=20.0,
        description="Establishing wide shot showing proscenium arch and stage floor",
    ),
    "full_two_shot": ShotScaleSpec(
        name="full_two_shot",
        scale=0.75,
        anchor_y=1420,
        bounding_width=360,
        bounding_height=720,
        screen_height_pct=37.5,
        description="Full two-shot face-off grounded on stage floor baseline",
    ),
    "medium_shot": ShotScaleSpec(
        name="medium_shot",
        scale=1.00,
        anchor_y=1360,
        bounding_width=480,
        bounding_height=760,
        screen_height_pct=39.6,
        description="Medium shot, waist-up for storytelling mudras and props",
    ),
    "medium_close_up": ShotScaleSpec(
        name="medium_close_up",
        scale=1.30,
        anchor_y=1280,
        bounding_width=520,
        bounding_height=680,
        screen_height_pct=50.0,
        description="Medium close-up bust shot locked to Upper Third eye level",
    ),
    "close_up": ShotScaleSpec(
        name="close_up",
        scale=1.65,
        anchor_y=1200,
        bounding_width=640,
        bounding_height=720,
        screen_height_pct=60.0,
        description="Dramatic close-up, crown crest contained below top exclusion zone",
    ),
    "extreme_close_up": ShotScaleSpec(
        name="extreme_close_up",
        scale=2.20,
        anchor_y=1120,
        bounding_width=880,
        bounding_height=460,
        screen_height_pct=70.0,
        description="Extreme close-up on divine gaze, brows, or third eye",
    ),
}

# ---------------------------------------------------------------------------
# Anatomical Joint Limits (Forward Kinematics)
# ---------------------------------------------------------------------------
# Natural joint limits to permanently prevent broken poses (e.g. 105deg scarecrow)
@dataclass(frozen=True)
class JointLimit:
    min_deg: float
    max_deg: float


JOINT_LIMITS: Final[dict[str, JointLimit]] = {
    "shoulder_l": JointLimit(min_deg=-40.0, max_deg=65.0),
    "shoulder_r": JointLimit(min_deg=-65.0, max_deg=40.0),
    "elbow_l": JointLimit(min_deg=0.0, max_deg=135.0),
    "elbow_r": JointLimit(min_deg=-135.0, max_deg=0.0),
    "wrist_l": JointLimit(min_deg=-30.0, max_deg=30.0),
    "wrist_r": JointLimit(min_deg=-30.0, max_deg=30.0),
    "torso_rot": JointLimit(min_deg=-6.0, max_deg=6.0),
    "torso_lean_y_px": JointLimit(min_deg=-20.0, max_deg=40.0),
    "head_rot": JointLimit(min_deg=-12.0, max_deg=12.0),
    "thigh_l": JointLimit(min_deg=-45.0, max_deg=45.0),
    "thigh_r": JointLimit(min_deg=-45.0, max_deg=45.0),
    "calf_l": JointLimit(min_deg=-60.0, max_deg=60.0),
    "calf_r": JointLimit(min_deg=-60.0, max_deg=60.0),
}

# ---------------------------------------------------------------------------
# Continuous Life Engine Invariants
# ---------------------------------------------------------------------------
# 1. Diaphragmatic Breathing
BREATHING_CYCLE_SEC: Final[float] = 2.2
BREATHING_SCALE_Y_MAX: Final[float] = 1.025
BREATHING_SHOULDER_FLOAT_PX: Final[float] = 2.0

# 2. Autonomous Blinking & Eye Saccades
BLINK_INTERVAL_MIN_SEC: Final[float] = 2.8
BLINK_INTERVAL_MAX_SEC: Final[float] = 4.2
BLINK_CLOSED_SEC: Final[float] = 0.070
BLINK_OPEN_SEC: Final[float] = 0.110
SACCADE_INTERVAL_SEC: Final[float] = 1.2
SACCADE_OFFSET_PX: Final[float] = 2.5

# 3. Idle Weight Shift
WEIGHT_SHIFT_CYCLE_SEC: Final[float] = 3.8
WEIGHT_SHIFT_ANGLE_DEG: Final[float] = 1.2

# 4. Passive Follow-Through Lag
FOLLOW_THROUGH_LAG_MS: Final[int] = 120

# ---------------------------------------------------------------------------
# 5 SVG Mouth Viseme States
# ---------------------------------------------------------------------------
MOUTH_CALM: Final[str] = "mouth_calm"
MOUTH_TALK: Final[str] = "mouth_talk"
MOUTH_SHOUT: Final[str] = "mouth_shout"
MOUTH_FEAR: Final[str] = "mouth_fear"
MOUTH_JOY: Final[str] = "mouth_joy"

ALL_MOUTH_STATES: Final[tuple[str, ...]] = (
    MOUTH_CALM,
    MOUTH_TALK,
    MOUTH_SHOUT,
    MOUTH_FEAR,
    MOUTH_JOY,
)
