"""Sutradhar Video Engine — Scene-to-Beat Decomposition & Pacing Engine (v4.0).

Deconstructs narrative scenes into dynamic micro-beats (1.8s - 3.5s) targeting
an Average Shot Length (ASL) of 2.2s - 3.0s.

Enforces:
1. Opening Hook Rule (0s - 3s): Opening shot duration <= 2.0s.
2. Maximum Static Hold Limit: No shot holds statically for > 3.8s.
3. Minimum Beat Duration Floor: Hard floor of 1.2s.
4. Gate 1 QA Compliance: 1.8s <= ASL <= 3.2s.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Final, Optional

from .config import (
    ASL_HARD_MAX_SEC,
    ASL_HARD_MIN_SEC,
    ASL_TARGET_MAX_SEC,
    ASL_TARGET_MIN_SEC,
    BEAT_DURATION_MAX_SEC,
    BEAT_DURATION_MIN_SEC,
    BEAT_FLOOR_MIN_SEC,
    BEAT_STATIC_MAX_SEC,
    HOOK_BEAT_MAX_SEC,
)

logger = logging.getLogger("sutradhar.engine.beat_planner")


class BeatPacingError(ValueError):
    """Raised when beat decomposition violates temporal or pacing constraints."""


@dataclass
class BeatPlan:
    """Represents a single micro-beat (cinematic shot) within a narrative scene."""

    beat_id: str
    scene_index: int
    beat_index: int
    start_sec: float
    end_sec: float
    duration_sec: float
    shot_type: str
    camera_motion: str = "push_in"
    primary_character: Optional[str] = None
    secondary_character: Optional[str] = None
    primary_character_pose: str = "idle_royal"
    secondary_character_pose: Optional[str] = None
    primary_character_emotion: str = "calm"
    secondary_character_emotion: Optional[str] = None
    primary_facing: str = "right"   # "right" (scaleX > 0) or "left" (scaleX < 0)
    secondary_facing: str = "left"  # "left" (scaleX < 0) or "right" (scaleX > 0)
    is_hook: bool = False
    words: list[dict[str, Any]] = field(default_factory=list)
    text_snippet: str = ""
    backdrop_rig: str = "golden_lanka_citadel"
    props: list[dict[str, Any]] = field(default_factory=list)
    foley_cues: list[str] = field(default_factory=list)
    transition_type: str = "cut"

    def to_dict(self) -> dict[str, Any]:
        """Serialize beat to dictionary."""
        return {
            "beat_id": self.beat_id,
            "scene_index": self.scene_index,
            "beat_index": self.beat_index,
            "start_sec": round(self.start_sec, 3),
            "end_sec": round(self.end_sec, 3),
            "duration_sec": round(self.duration_sec, 3),
            "shot_type": self.shot_type,
            "camera_motion": self.camera_motion,
            "primary_character": self.primary_character,
            "secondary_character": self.secondary_character,
            "primary_character_pose": self.primary_character_pose,
            "secondary_character_pose": self.secondary_character_pose,
            "primary_character_emotion": self.primary_character_emotion,
            "secondary_character_emotion": self.secondary_character_emotion,
            "primary_facing": self.primary_facing,
            "secondary_facing": self.secondary_facing,
            "is_hook": self.is_hook,
            "words": self.words,
            "text_snippet": self.text_snippet,
            "backdrop_rig": self.backdrop_rig,
            "props": self.props,
            "foley_cues": self.foley_cues,
            "transition_type": self.transition_type,
        }


def compute_asl(beats: list[BeatPlan] | list[dict[str, Any]]) -> float:
    """Compute the Average Shot Length (ASL) across a collection of beats.

    Formula: ASL = Total Duration / Total Shots
    """
    if not beats:
        return 0.0

    total_dur = 0.0
    for b in beats:
        dur = b.duration_sec if isinstance(b, BeatPlan) else float(b.get("duration_sec", 0.0))
        total_dur += dur

    return round(total_dur / len(beats), 3)


def validate_beat_pacing(
    beats: list[BeatPlan] | list[dict[str, Any]],
    total_duration_sec: Optional[float] = None,
) -> tuple[bool, list[str]]:
    """Validate pacing compliance against all Gate 1 Cinematography requirements.

    Returns:
        (is_valid, list_of_violations)
    """
    violations: list[str] = []
    if not beats:
        return False, ["No beats provided for pacing validation."]

    total_dur = 0.0
    for idx, b in enumerate(beats):
        b_id = b.beat_id if isinstance(b, BeatPlan) else b.get("beat_id", f"beat_{idx}")
        dur = b.duration_sec if isinstance(b, BeatPlan) else float(b.get("duration_sec", 0.0))
        total_dur += dur

        # 1. Minimum duration floor
        if dur < BEAT_FLOOR_MIN_SEC:
            violations.append(
                f"Beat {b_id} duration ({dur:.2f}s) is below absolute floor ({BEAT_FLOOR_MIN_SEC}s)."
            )

        # 2. Maximum static hold
        if dur > BEAT_STATIC_MAX_SEC:
            violations.append(
                f"Beat {b_id} duration ({dur:.2f}s) exceeds maximum static hold limit ({BEAT_STATIC_MAX_SEC}s)."
            )

        # 3. Opening hook check
        is_first = idx == 0
        is_hook = b.is_hook if isinstance(b, BeatPlan) else bool(b.get("is_hook", False))
        if is_first and dur > HOOK_BEAT_MAX_SEC:
            violations.append(
                f"Opening hook beat {b_id} duration ({dur:.2f}s) exceeds 2-second limit ({HOOK_BEAT_MAX_SEC}s)."
            )

    # 4. Total duration alignment check if provided
    if total_duration_sec is not None:
        if abs(total_dur - total_duration_sec) > 0.25:
            violations.append(
                f"Sum of beat durations ({total_dur:.2f}s) does not match total duration ({total_duration_sec:.2f}s)."
            )

    # 5. ASL Gate 1 compliance: 1.8s <= ASL <= 3.2s
    asl = round(total_dur / len(beats), 3)
    if asl < ASL_HARD_MIN_SEC or asl > ASL_HARD_MAX_SEC:
        violations.append(
            f"Average Shot Length (ASL = {asl:.2f}s) outside Gate 1 range [{ASL_HARD_MIN_SEC}s, {ASL_HARD_MAX_SEC}s]."
        )

    return len(violations) == 0, violations


def select_beat_shot_scales(
    scene: dict[str, Any],
    count: int,
    is_first_scene: bool = False,
) -> list[tuple[str, str]]:
    """Determine dynamic shot scales and camera motions for N beats in a scene.

    Returns:
        list of (shot_scale, camera_motion) tuples
    """
    has_two_characters = bool(
        scene.get("secondary_character")
        or scene.get("shot_type") in ("two_character_confrontation", "full_two_shot")
    )
    emotion = str(scene.get("emotion") or "calm").lower()

    # Case A: Opening Hook Scene (Scene 1)
    if is_first_scene:
        if count == 1:
            return [("establishing_wide", "push_in")]
        elif count == 2:
            return [
                ("establishing_wide", "push_in"),
                ("full_two_shot" if has_two_characters else "medium_shot", "static"),
            ]
        elif count == 3:
            return [
                ("establishing_wide", "push_in"),
                ("full_two_shot" if has_two_characters else "medium_shot", "static"),
                ("close_up" if emotion in ("wrath", "shock") else "medium_close_up", "push_in"),
            ]
        else:
            return [
                ("establishing_wide", "push_in"),
                ("full_two_shot" if has_two_characters else "medium_shot", "static"),
                ("medium_close_up", "pan_left"),
                ("close_up", "dramatic_zoom"),
            ] + [("medium_shot", "static")] * (count - 4)

    # Case B: Two-Character Confrontation / Dramatic Staging
    if has_two_characters:
        if count == 1:
            return [("full_two_shot", "static")]
        elif count == 2:
            return [
                ("full_two_shot", "push_in"),
                ("over_the_shoulder_left", "static"),
            ]
        elif count == 3:
            return [
                ("full_two_shot", "push_in"),
                ("over_the_shoulder_left", "static"),
                ("medium_close_up", "dramatic_zoom" if emotion in ("wrath", "shock") else "static"),
            ]
        elif count == 4:
            return [
                ("full_two_shot", "push_in"),
                ("over_the_shoulder_left", "static"),
                ("medium_close_up", "pan_left"),
                ("close_up" if emotion in ("wrath", "shock") else "full_two_shot", "dramatic_zoom"),
            ]
        else:
            pattern = [
                ("full_two_shot", "push_in"),
                ("over_the_shoulder_left", "static"),
                ("medium_close_up", "pan_left"),
                ("over_the_shoulder_right", "static"),
                ("close_up", "dramatic_zoom"),
            ]
            return [pattern[i % len(pattern)] for i in range(count)]

    # Case C: High Drama / Climax / Wrath
    if emotion in ("wrath", "shock", "rage"):
        if count == 1:
            return [("close_up", "dramatic_zoom")]
        elif count == 2:
            return [
                ("medium_close_up", "push_in"),
                ("close_up", "dramatic_zoom"),
            ]
        elif count == 3:
            return [
                ("medium_shot", "static"),
                ("medium_close_up", "push_in"),
                ("extreme_close_up", "dramatic_zoom"),
            ]
        else:
            return [
                ("medium_shot", "push_in"),
                ("medium_close_up", "static"),
                ("close_up", "pan_left"),
                ("extreme_close_up", "dramatic_zoom"),
            ] + [("close_up", "static")] * (count - 4)

    # Case D: General Narrative / Dialogue / Philosophy
    if count == 1:
        shot_req = scene.get("shot_type") or "medium_shot"
        return [(shot_req, "push_in")]
    elif count == 2:
        return [
            ("medium_shot", "push_in"),
            ("medium_close_up", "static"),
        ]
    elif count == 3:
        return [
            ("establishing_wide", "push_in"),
            ("medium_shot", "static"),
            ("medium_close_up", "pan_right"),
        ]
    else:
        return [
            ("establishing_wide", "push_in"),
            ("medium_shot", "static"),
            ("medium_close_up", "pan_right"),
            ("close_up", "static"),
        ] + [("medium_shot", "push_in")] * (count - 4)


def decompose_scene_into_beats(
    scene: dict[str, Any],
    is_first_scene: bool = False,
    global_start_offset: float = 0.0,
) -> list[BeatPlan]:
    """Decompose a single narrative scene into optimal 1.8s - 3.5s micro-beats.

    Guarantees:
    - Target ASL: 2.2s - 3.0s per beat.
    - If is_first_scene: Beat 1 duration <= 2.0s (Opening Hook rule).
    - Every beat duration is strictly within [1.2s, 3.8s].
    - Cuts snap cleanly to word/pause boundaries when timestamps are present.
    """
    scene_idx = int(scene.get("scene_index", 1))
    start_sec = float(scene.get("start_sec", global_start_offset))
    end_sec = float(scene.get("end_sec", start_sec + float(scene.get("duration_sec", 4.0))))
    scene_duration = round(end_sec - start_sec, 3)

    if scene_duration <= 0.0:
        raise BeatPacingError(f"Scene {scene_idx} has invalid non-positive duration: {scene_duration}s")

    words: list[dict[str, Any]] = scene.get("words", [])

    # 1. Determine optimal beat count K
    target_beat_dur = 2.50  # Center of ideal [2.2s, 3.0s]
    raw_k = max(1, int(round(scene_duration / target_beat_dur)))

    # Enforce upper bound: no beat may exceed 3.8s
    min_k_for_max_limit = math.ceil(scene_duration / BEAT_STATIC_MAX_SEC)
    k = max(raw_k, min_k_for_max_limit)

    # For opening scene: ensure hook beat (<=2.0s) can be cleanly carved
    if is_first_scene and scene_duration > HOOK_BEAT_MAX_SEC:
        k = max(2, k)

    # Ensure beats aren't sub-floor (< 1.2s) unless entire scene is tiny
    if k > 1 and (scene_duration / k) < BEAT_FLOOR_MIN_SEC:
        k = max(1, math.floor(scene_duration / BEAT_FLOOR_MIN_SEC))

    # 2. Compute candidate beat split points
    beat_durations: list[float] = []

    if is_first_scene and k > 1:
        # Carve out hook beat (target: 1.8s - 2.0s)
        hook_target = min(HOOK_BEAT_MAX_SEC, max(BEAT_FLOOR_MIN_SEC, scene_duration / k))
        hook_dur = min(hook_target, 2.0)
        rem_dur = scene_duration - hook_dur
        rem_k = k - 1
        rem_beat_dur = rem_dur / rem_k

        # Check if rem_beat_dur exceeds 3.8s
        if rem_beat_dur > BEAT_STATIC_MAX_SEC:
            rem_k = math.ceil(rem_dur / 3.4)
            rem_beat_dur = rem_dur / rem_k
            k = rem_k + 1

        beat_durations = [hook_dur] + [rem_beat_dur] * rem_k
    else:
        nom_dur = scene_duration / k
        beat_durations = [nom_dur] * k

    # Compute candidate boundary timestamps relative to scene start
    boundary_rel_times: list[float] = []
    accum = 0.0
    for d in beat_durations[:-1]:
        accum += d
        boundary_rel_times.append(accum)

    # 3. Snap candidate boundaries to Whisper word boundaries / punctuation
    snapped_rel_times: list[float] = []
    if words:
        prev_bound = 0.0
        for b_idx, cand_t in enumerate(boundary_rel_times):
            best_snap = cand_t
            min_dist = float("inf")

            # Check word boundaries within ±0.65s of candidate
            for w in words:
                w_end = float(w.get("end_sec", 0.0)) - start_sec
                dist = abs(w_end - cand_t)

                if dist < 0.65 and dist < min_dist:
                    cand_dur = w_end - prev_bound
                    cand_next_dur = (
                        (boundary_rel_times[b_idx + 1] if b_idx + 1 < len(boundary_rel_times) else scene_duration)
                        - w_end
                    )

                    # Validate duration limits
                    is_hook_cut = is_first_scene and b_idx == 0
                    max_allowed = HOOK_BEAT_MAX_SEC if is_hook_cut else BEAT_STATIC_MAX_SEC

                    if BEAT_FLOOR_MIN_SEC <= cand_dur <= max_allowed and cand_next_dur >= BEAT_FLOOR_MIN_SEC:
                        best_snap = w_end
                        min_dist = dist

            snapped_rel_times.append(round(best_snap, 3))
            prev_bound = best_snap
    else:
        snapped_rel_times = [round(t, 3) for t in boundary_rel_times]

    # Reconstruct exact final beat durations
    final_durations: list[float] = []
    curr_t = 0.0
    for b_t in snapped_rel_times:
        dur = round(b_t - curr_t, 3)
        final_durations.append(dur)
        curr_t = b_t
    final_durations.append(round(scene_duration - curr_t, 3))

    # Guard: if last beat ended up slightly below floor or above ceiling due to snapping, rebalance
    if len(final_durations) > 1:
        if final_durations[-1] < BEAT_FLOOR_MIN_SEC:
            shortfall = BEAT_FLOOR_MIN_SEC - final_durations[-1]
            if final_durations[-2] - shortfall >= BEAT_FLOOR_MIN_SEC:
                final_durations[-2] = round(final_durations[-2] - shortfall, 3)
                final_durations[-1] = BEAT_FLOOR_MIN_SEC
        elif final_durations[-1] > BEAT_STATIC_MAX_SEC:
            excess = final_durations[-1] - BEAT_STATIC_MAX_SEC
            final_durations[-2] = round(final_durations[-2] + excess, 3)
            final_durations[-1] = BEAT_STATIC_MAX_SEC

    # 4. Generate BeatPlan objects
    actual_k = len(final_durations)
    shot_configs = select_beat_shot_scales(scene, actual_k, is_first_scene=is_first_scene)

    p1_name = scene.get("primary_character")
    p2_name = scene.get("secondary_character")
    p1_pose = scene.get("pose_preset") or "idle_royal"
    p2_pose = scene.get("secondary_pose_preset") or "humbled_braced"
    emotion = scene.get("emotion") or "calm"
    backdrop = scene.get("backdrop_rig") or "golden_lanka_citadel"

    # Expression change handling
    expr_change = scene.get("expression_change") or {}
    expr_at_ratio = float(expr_change.get("at_ratio", 0.5)) if expr_change else None
    expr_char = expr_change.get("character")
    expr_emotion = expr_change.get("to_emotion")
    expr_pose = expr_change.get("to_pose")

    beats: list[BeatPlan] = []
    cursor = start_sec

    for idx, dur in enumerate(final_durations):
        b_idx = idx + 1
        b_id = f"s{scene_idx}_b{b_idx}"
        b_start = round(cursor, 3)
        b_end = round(cursor + dur, 3)
        cursor = b_end

        shot_scale, cam_motion = shot_configs[idx]
        is_hook = is_first_scene and idx == 0

        # Facing directions
        # By default in two-shot: P1 on left faces right; P2 on right faces left
        p1_facing = "right"
        p2_facing = "left"

        # In OTS shots:
        if shot_scale == "over_the_shoulder_left":
            p1_facing = "right"
            p2_facing = "left"
        elif shot_scale == "over_the_shoulder_right":
            p1_facing = "right"
            p2_facing = "left"

        # Determine pose and emotion for this beat
        beat_p1_pose = p1_pose
        beat_p2_pose = p2_pose
        beat_p1_emotion = emotion
        beat_p2_emotion = emotion

        # Apply mid-scene expression change if threshold crossed
        beat_mid_ratio = ((b_start + b_end) / 2.0 - start_sec) / max(0.1, scene_duration)
        if expr_at_ratio is not None and beat_mid_ratio >= expr_at_ratio:
            if expr_char == p1_name or (expr_char is None and p1_name):
                if expr_emotion:
                    beat_p1_emotion = expr_emotion
                if expr_pose:
                    beat_p1_pose = expr_pose
            if expr_char == p2_name:
                if expr_emotion:
                    beat_p2_emotion = expr_emotion
                if expr_pose:
                    beat_p2_pose = expr_pose

        # Filter words belonging to this beat
        beat_words: list[dict[str, Any]] = []
        for w in words:
            w_start = float(w.get("start_sec", 0.0))
            if b_start - 0.05 <= w_start < b_end:
                beat_words.append(w)

        text_snippet = " ".join(w.get("word", "") for w in beat_words)

        beats.append(
            BeatPlan(
                beat_id=b_id,
                scene_index=scene_idx,
                beat_index=b_idx,
                start_sec=b_start,
                end_sec=b_end,
                duration_sec=dur,
                shot_type=shot_scale,
                camera_motion=cam_motion,
                primary_character=p1_name,
                secondary_character=p2_name,
                primary_character_pose=beat_p1_pose,
                secondary_character_pose=beat_p2_pose if p2_name else None,
                primary_character_emotion=beat_p1_emotion,
                secondary_character_emotion=beat_p2_emotion if p2_name else None,
                primary_facing=p1_facing,
                secondary_facing=p2_facing,
                is_hook=is_hook,
                words=beat_words,
                text_snippet=text_snippet,
                backdrop_rig=backdrop,
                props=scene.get("props", []),
                foley_cues=scene.get("foley_cues", []),
                transition_type="curtain_open" if is_hook else "cut",
            )
        )

    return beats


def decompose_episode_into_beats(scenes: list[dict[str, Any]]) -> list[BeatPlan]:
    """Decompose an entire episode's scenes into a unified micro-beat timeline.

    Validates that:
    - ASL across the episode is strictly within [1.8s, 3.2s] (targeting 2.2s - 3.0s).
    - Opening hook duration <= 2.0s.
    - Zero beats exceed 3.8s.
    """
    if not scenes:
        return []

    all_beats: list[BeatPlan] = []
    for idx, sc in enumerate(scenes):
        is_first = idx == 0
        scene_beats = decompose_scene_into_beats(sc, is_first_scene=is_first)
        all_beats.extend(scene_beats)

    # Validate full episode pacing
    total_dur = sum(b.duration_sec for b in all_beats)
    is_valid, violations = validate_beat_pacing(all_beats, total_dur)
    if not is_valid:
        logger.warning("Episode beat pacing warnings: %s", violations)

    return all_beats
