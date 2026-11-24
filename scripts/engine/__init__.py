"""Sutradhar Video Engine — Core Package (v4.0).

Autonomous cultural storytelling and 2.5D puppet animation engine.
"""

from __future__ import annotations

from .config import (
    ALL_MOUTH_STATES,
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    FPS,
    GOLDEN_ZONE_X_MAX,
    GOLDEN_ZONE_X_MIN,
    GOLDEN_ZONE_Y_MAX,
    GOLDEN_ZONE_Y_MIN,
    JOINT_LIMITS,
    MOUTH_CALM,
    MOUTH_FEAR,
    MOUTH_JOY,
    MOUTH_SHOUT,
    MOUTH_TALK,
    PUPPET_BASE_HEIGHT,
    PUPPET_BASE_WIDTH,
    PUPPET_TRANSFORM_ORIGIN,
    SHOT_SCALES,
)

__all__ = [
    "CANVAS_WIDTH",
    "CANVAS_HEIGHT",
    "FPS",
    "GOLDEN_ZONE_X_MIN",
    "GOLDEN_ZONE_X_MAX",
    "GOLDEN_ZONE_Y_MIN",
    "GOLDEN_ZONE_Y_MAX",
    "PUPPET_BASE_WIDTH",
    "PUPPET_BASE_HEIGHT",
    "PUPPET_TRANSFORM_ORIGIN",
    "SHOT_SCALES",
    "JOINT_LIMITS",
    "MOUTH_CALM",
    "MOUTH_TALK",
    "MOUTH_SHOUT",
    "MOUTH_FEAR",
    "MOUTH_JOY",
    "ALL_MOUTH_STATES",
]
