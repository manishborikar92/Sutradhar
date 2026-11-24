"""Sutradhar Video Engine — Puppet Rig & Forward Kinematics (v4.0).

Enforces standardized 480x960px puppet dimensions, foot transform-origin (50% 100%),
strict anatomical joint constraints (eliminating scarecrow 105deg poses),
and natural biological motion via ContinuousLifeEngine.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Final, Optional

from .config import (
    ALL_MOUTH_STATES,
    BLINK_CLOSED_SEC,
    BLINK_INTERVAL_MAX_SEC,
    BLINK_INTERVAL_MIN_SEC,
    BLINK_OPEN_SEC,
    BREATHING_CYCLE_SEC,
    BREATHING_SCALE_Y_MAX,
    BREATHING_SHOULDER_FLOAT_PX,
    FOLLOW_THROUGH_LAG_MS,
    JOINT_LIMITS,
    PUPPET_BASE_HEIGHT,
    PUPPET_BASE_WIDTH,
    PUPPET_TRANSFORM_ORIGIN,
    SACCADE_INTERVAL_SEC,
    SACCADE_OFFSET_PX,
    TWO_SHOT_GAP_PX,
    TWO_SHOT_MAX_PUPPET_WIDTH,
    TWO_SHOT_P1_X,
    TWO_SHOT_P2_X,
    TWO_SHOT_SCALE,
    WEIGHT_SHIFT_ANGLE_DEG,
    WEIGHT_SHIFT_CYCLE_SEC,
    JointLimit,
)


class PuppetRigError(ValueError):
    """Base exception for puppet rigging defects."""


class JointConstraintError(PuppetRigError):
    """Raised when joint angle or bone rotation violates anatomical limits."""


def _parse_numeric(val: Any) -> float:
    """Extract float number from degree or pixel string (e.g. '35deg' -> 35.0, '-10px' -> -10.0)."""
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    match = re.match(r"^([+-]?[0-9]+(?:\.[0-9]+)?)(?:deg|px|%)?$", s)
    if not match:
        raise ValueError(f"Cannot parse numeric value from '{val}'")
    return float(match.group(1))


# Canonical Joint Variable Mapping -> Limit Key
JOINT_VAR_MAP: Final[dict[str, str]] = {
    "--rot-shoulder-l": "shoulder_l",
    "--rot-shoulder-front-left": "shoulder_l",
    "--rot-shoulder-rear-left": "shoulder_l",
    "--rot-shoulder-r": "shoulder_r",
    "--rot-shoulder-front-right": "shoulder_r",
    "--rot-shoulder-rear-right": "shoulder_r",
    "--rot-elbow-l": "elbow_l",
    "--rot-elbow-front-left": "elbow_l",
    "--rot-elbow-rear-left": "elbow_l",
    "--rot-elbow-r": "elbow_r",
    "--rot-elbow-front-right": "elbow_r",
    "--rot-elbow-rear-right": "elbow_r",
    "--rot-wrist-l": "wrist_l",
    "--rot-wrist-front-left": "wrist_l",
    "--rot-wrist-r": "wrist_r",
    "--rot-wrist-front-right": "wrist_r",
    "--rot-torso": "torso_rot",
    "--trans-torso-y": "torso_lean_y_px",
    "--rot-head": "head_rot",
    "--rot-thigh-l": "thigh_l",
    "--rot-thigh-left": "thigh_l",
    "--rot-thigh-r": "thigh_r",
    "--rot-thigh-right": "thigh_r",
    "--rot-calf-l": "calf_l",
    "--rot-shin-left": "calf_l",
    "--rot-calf-r": "calf_r",
    "--rot-shin-right": "calf_r",
}


# ---------------------------------------------------------------------------
# Standard Anatomical Poses (Strictly compliant with JOINT_LIMITS)
# ---------------------------------------------------------------------------
STANDARD_POSES: Final[dict[str, dict[str, str]]] = {
    "idle_royal": {
        "--trans-torso-x": "0px",
        "--trans-torso-y": "0px",
        "--rot-torso": "0deg",
        "--rot-shoulder-l": "-10deg",
        "--rot-elbow-l": "15deg",
        "--rot-wrist-l": "0deg",
        "--rot-shoulder-r": "10deg",
        "--rot-elbow-r": "-15deg",
        "--rot-wrist-r": "0deg",
        "--rot-shoulder-front-left": "-10deg",
        "--rot-elbow-front-left": "15deg",
        "--rot-shoulder-front-right": "10deg",
        "--rot-elbow-front-right": "-15deg",
        "--rot-thigh-l": "0deg",
        "--rot-calf-l": "0deg",
        "--rot-thigh-r": "0deg",
        "--rot-calf-r": "0deg",
        "--rot-head": "0deg",
    },
    "blessing_calm": {
        "--trans-torso-x": "0px",
        "--trans-torso-y": "0px",
        "--rot-torso": "0deg",
        "--rot-shoulder-l": "15deg",
        "--rot-elbow-l": "30deg",
        "--rot-wrist-l": "0deg",
        "--rot-shoulder-r": "-35deg",  # Raised blessing hand within [-65, 40]
        "--rot-elbow-r": "-65deg",     # Bent elbow within [-135, 0]
        "--rot-wrist-r": "10deg",
        "--rot-shoulder-front-left": "15deg",
        "--rot-elbow-front-left": "30deg",
        "--rot-shoulder-front-right": "-35deg",
        "--rot-elbow-front-right": "-65deg",
        "--rot-thigh-l": "0deg",
        "--rot-calf-l": "0deg",
        "--rot-thigh-r": "0deg",
        "--rot-calf-r": "0deg",
        "--rot-head": "2deg",
    },
    # Redesigned bound captive pose: completely replaces broken 105deg scarecrow!
    "humbled_braced": {
        "--trans-torso-x": "0px",
        "--trans-torso-y": "15px",      # Torso pitched forward
        "--rot-torso": "4deg",          # Torso forward incline
        "--rot-shoulder-l": "35deg",     # Upper arms angled downward naturally
        "--rot-elbow-l": "75deg",       # Forearms crossed inward over chest
        "--rot-wrist-l": "15deg",       # Wrists clasped
        "--rot-shoulder-r": "-35deg",    # Upper arms angled downward naturally
        "--rot-elbow-r": "-75deg",      # Forearms crossed inward over chest
        "--rot-wrist-r": "-15deg",      # Wrists clasped
        "--rot-shoulder-front-left": "35deg",
        "--rot-elbow-front-left": "75deg",
        "--rot-shoulder-front-right": "-35deg",
        "--rot-elbow-front-right": "-75deg",
        "--rot-thigh-l": "20deg",
        "--rot-calf-l": "-25deg",
        "--rot-thigh-r": "-20deg",
        "--rot-calf-r": "25deg",
        "--rot-thigh-left": "20deg",
        "--rot-shin-left": "-25deg",
        "--rot-thigh-right": "-20deg",
        "--rot-shin-right": "25deg",
        "--rot-head": "-10deg",         # Head bowed downward with eyes turned upward
    },
    "combat_stance": {
        "--trans-torso-x": "0px",
        "--trans-torso-y": "10px",
        "--rot-torso": "-3deg",
        "--rot-shoulder-l": "-30deg",
        "--rot-elbow-l": "60deg",
        "--rot-wrist-l": "15deg",
        "--rot-shoulder-r": "25deg",
        "--rot-elbow-r": "-45deg",
        "--rot-wrist-r": "-10deg",
        "--rot-shoulder-front-left": "-30deg",
        "--rot-elbow-front-left": "60deg",
        "--rot-shoulder-front-right": "25deg",
        "--rot-elbow-front-right": "-45deg",
        "--rot-thigh-l": "22deg",
        "--rot-calf-l": "-25deg",
        "--rot-thigh-r": "-20deg",
        "--rot-calf-r": "22deg",
        "--rot-head": "4deg",
    },
    "wrath_rearing": {
        "--trans-torso-x": "0px",
        "--trans-torso-y": "-5px",
        "--rot-torso": "-5deg",
        "--rot-shoulder-l": "-35deg",
        "--rot-elbow-l": "45deg",
        "--rot-wrist-l": "10deg",
        "--rot-shoulder-r": "35deg",
        "--rot-elbow-r": "-45deg",
        "--rot-wrist-r": "-10deg",
        "--rot-shoulder-front-left": "-35deg",
        "--rot-elbow-front-left": "45deg",
        "--rot-shoulder-front-right": "35deg",
        "--rot-elbow-front-right": "-45deg",
        "--rot-thigh-l": "12deg",
        "--rot-calf-l": "-12deg",
        "--rot-thigh-r": "-12deg",
        "--rot-calf-r": "12deg",
        "--rot-head": "8deg",
    },
    "devotional_anjali": {
        "--trans-torso-x": "0px",
        "--trans-torso-y": "5px",
        "--rot-torso": "2deg",
        "--rot-shoulder-l": "20deg",
        "--rot-elbow-l": "70deg",
        "--rot-wrist-l": "15deg",
        "--rot-shoulder-r": "-20deg",
        "--rot-elbow-r": "-70deg",
        "--rot-wrist-r": "-15deg",
        "--rot-shoulder-front-left": "20deg",
        "--rot-elbow-front-left": "70deg",
        "--rot-shoulder-front-right": "-20deg",
        "--rot-elbow-front-right": "-70deg",
        "--rot-thigh-l": "0deg",
        "--rot-calf-l": "0deg",
        "--rot-thigh-r": "0deg",
        "--rot-calf-r": "0deg",
        "--rot-head": "-5deg",
    },
    "meditation_padmasana": {
        "--trans-torso-x": "0px",
        "--trans-torso-y": "30px",
        "--rot-torso": "0deg",
        "--rot-shoulder-l": "15deg",
        "--rot-elbow-l": "50deg",
        "--rot-wrist-l": "10deg",
        "--rot-shoulder-r": "-15deg",
        "--rot-elbow-r": "-50deg",
        "--rot-wrist-r": "-10deg",
        "--rot-shoulder-front-left": "15deg",
        "--rot-elbow-front-left": "50deg",
        "--rot-shoulder-front-right": "-15deg",
        "--rot-elbow-front-right": "-50deg",
        "--rot-thigh-l": "40deg",
        "--rot-calf-l": "-45deg",
        "--rot-thigh-r": "-40deg",
        "--rot-calf-r": "45deg",
        "--rot-head": "-2deg",
    },
}


def validate_joint_value(var_name: str, value: Any, clamp: bool = False) -> str:
    """Validates an individual joint rotation or translation against JOINT_LIMITS.

    Args:
        var_name: CSS variable name (e.g. '--rot-shoulder-l').
        value: Angle or offset value ('35deg', 35, '15px').
        clamp: If True, clamp out-of-bounds values rather than raising.

    Returns:
        Formatted CSS variable value string ('35deg', '15px').

    Raises:
        JointConstraintError: If value is out of bounds and clamp is False.
    """
    limit_key = JOINT_VAR_MAP.get(var_name)
    if not limit_key or limit_key not in JOINT_LIMITS:
        # Not a constrained joint variable (e.g. custom translation)
        return str(value)

    limit = JOINT_LIMITS[limit_key]
    numeric = _parse_numeric(value)
    unit = "px" if "px" in str(value) else "deg"

    if numeric < limit.min_deg or numeric > limit.max_deg:
        if clamp:
            clamped = max(limit.min_deg, min(limit.max_deg, numeric))
            return f"{clamped:g}{unit}"
        raise JointConstraintError(
            f"Joint '{var_name}' value {numeric}{unit} violates anatomical limits "
            f"[{limit.min_deg}{unit}, {limit.max_deg}{unit}]"
        )
    return f"{numeric:g}{unit}"


def validate_pose(pose_vars: dict[str, Any], clamp: bool = False) -> dict[str, str]:
    """Validates an entire pose dictionary against anatomical joint limits.

    Ensures no 105deg scarecrow poses or hyper-extended limbs can pass into production.
    """
    validated: dict[str, str] = {}
    for k, v in pose_vars.items():
        validated[k] = validate_joint_value(k, v, clamp=clamp)
    return validated


def get_pose(pose_name: str) -> dict[str, str]:
    """Retrieve a validated standard pose by name."""
    if pose_name in STANDARD_POSES:
        return dict(STANDARD_POSES[pose_name])
    return dict(STANDARD_POSES["idle_royal"])


# ---------------------------------------------------------------------------
# ContinuousLifeEngine: Biological Motion Generator
# ---------------------------------------------------------------------------
class ContinuousLifeEngine:
    """Generates deterministic secondary and idle animation cycles for vector puppets.

    Implements:
    1. Diaphragmatic breathing (2.2s sine cycle, 1.00 <-> 1.025 scaleY, 2px shoulder float)
    2. Autonomous blinking & eye saccades (2.8s-4.2s intervals, 70ms closed, micro-saccades ±2.5px)
    3. Idle weight shift (3.8s cycle, pelvis/hips oscillate ±1.2deg)
    4. Passive follow-through (sash, crown ribbons lag torso by ~120ms)
    """

    def __init__(
        self,
        breathing_cycle_sec: float = BREATHING_CYCLE_SEC,
        breathing_scale_y: float = BREATHING_SCALE_Y_MAX,
        shoulder_float_px: float = BREATHING_SHOULDER_FLOAT_PX,
        blink_interval_min: float = BLINK_INTERVAL_MIN_SEC,
        blink_interval_max: float = BLINK_INTERVAL_MAX_SEC,
        blink_closed_sec: float = BLINK_CLOSED_SEC,
        saccade_interval_sec: float = SACCADE_INTERVAL_SEC,
        saccade_offset_px: float = SACCADE_OFFSET_PX,
        weight_shift_sec: float = WEIGHT_SHIFT_CYCLE_SEC,
        weight_shift_angle_deg: float = WEIGHT_SHIFT_ANGLE_DEG,
        follow_through_lag_ms: int = FOLLOW_THROUGH_LAG_MS,
    ) -> None:
        self.breathing_cycle_sec = breathing_cycle_sec
        self.breathing_scale_y = breathing_scale_y
        self.shoulder_float_px = shoulder_float_px
        self.blink_interval_min = blink_interval_min
        self.blink_interval_max = blink_interval_max
        self.blink_closed_sec = blink_closed_sec
        self.saccade_interval_sec = saccade_interval_sec
        self.saccade_offset_px = saccade_offset_px
        self.weight_shift_sec = weight_shift_sec
        self.weight_shift_angle_deg = weight_shift_angle_deg
        self.follow_through_lag_ms = follow_through_lag_ms

    def generate_gsap_code(self, wrapper_id: str, duration_sec: float) -> str:
        """Generates modular GSAP 3 JavaScript animation snippet for a puppet wrapper."""
        half_breath = round(self.breathing_cycle_sec / 2.0, 3)
        weight_half = round(self.weight_shift_sec / 2.0, 3)
        
        return f"""
  // ContinuousLifeEngine for #{wrapper_id}
  (function initContinuousLife() {{
    const wrap = document.getElementById("{wrapper_id}");
    if (!wrap) return;

    const torso = wrap.querySelector("#torso_group, #shani_torso_group");
    const shoulders = wrap.querySelectorAll("#shoulder_front_left_joint, #shoulder_front_right_joint");
    const eyesNormal = wrap.querySelector("#eyes_normal");
    const pupils = wrap.querySelectorAll("#eyes_normal circle");
    const sash = wrap.querySelectorAll("#shani_dhoti_fold, .cloth-sash, .crown-ribbon");

    // 1. Diaphragmatic Breathing (2.2s sine cycle)
    if (torso) {{
      gsap.to(torso, {{
        scaleY: {self.breathing_scale_y},
        duration: {half_breath},
        yoyo: true,
        repeat: -1,
        ease: "sine.inOut",
        transformOrigin: "400px 700px"
      }});
    }}
    if (shoulders.length > 0) {{
      gsap.to(shoulders, {{
        y: -{self.shoulder_float_px},
        duration: {half_breath},
        yoyo: true,
        repeat: -1,
        ease: "sine.inOut"
      }});
    }}

    // 2. Autonomous Blinking (every 2.8s - 4.2s, closed for 70ms)
    if (eyesNormal) {{
      const scheduleBlink = () => {{
        const delay = gsap.utils.random({self.blink_interval_min}, {self.blink_interval_max});
        gsap.delayedCall(delay, () => {{
          gsap.set(eyesNormal, {{ opacity: 0 }});
          gsap.delayedCall({self.blink_closed_sec}, () => {{
            gsap.set(eyesNormal, {{ opacity: 1 }});
            scheduleBlink();
          }});
        }});
      }};
      scheduleBlink();
    }}

    // 3. Eye Micro-Saccades (every 1.2s shift pupils ±2.5px)
    if (pupils.length > 0) {{
      const scheduleSaccade = () => {{
        gsap.delayedCall({self.saccade_interval_sec}, () => {{
          const dx = gsap.utils.random(-{self.saccade_offset_px}, {self.saccade_offset_px});
          const dy = gsap.utils.random(-1.0, 1.0);
          gsap.to(pupils, {{ x: dx, y: dy, duration: 0.08, ease: "power1.out" }});
          scheduleSaccade();
        }});
      }};
      scheduleSaccade();
    }}

    // 4. Idle Weight Shift (3.8s cycle, pelvis oscillation ±1.2deg)
    if (torso) {{
      gsap.to(torso, {{
        rotation: "+={self.weight_shift_angle_deg}",
        duration: {weight_half},
        yoyo: true,
        repeat: -1,
        ease: "sine.inOut"
      }});
    }}

    // 5. Passive Follow-Through (cloth/ribbons lagging torso)
    if (sash.length > 0) {{
      gsap.to(sash, {{
        rotation: "-={self.weight_shift_angle_deg * 0.8}",
        duration: {weight_half},
        delay: {self.follow_through_lag_ms / 1000.0},
        yoyo: true,
        repeat: -1,
        ease: "sine.inOut"
      }});
    }}
  }})();
"""


# ---------------------------------------------------------------------------
# Puppet Wrapper Staging & CSS
# ---------------------------------------------------------------------------
def get_puppet_wrapper_css() -> str:
    """Returns standardized CSS rules for .puppet-wrapper conforming to 480x960px dimensions."""
    return f""".puppet-wrapper {{
  position: absolute;
  top: 460px;
  left: 300px;
  width: {PUPPET_BASE_WIDTH}px;
  height: {PUPPET_BASE_HEIGHT}px;
  z-index: 40;
  transform-origin: {PUPPET_TRANSFORM_ORIGIN};
  display: block;
  opacity: 1;
}}

.puppet-wrapper svg {{
  width: 100%;
  height: 100%;
  display: block;
}}
"""
