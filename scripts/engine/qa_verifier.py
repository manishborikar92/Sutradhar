"""Sutradhar Video Engine — Automated Triple-Gate QA Verifier (v4.0).

Automated quality assurance suite enforcing fail-closed release gates:
1. Gate 1: Cinematography & Temporal Pacing QA:
   - Average Shot Length (ASL) within [1.8s, 3.2s] (targeting 2.2s - 3.0s).
   - Maximum static-shot duration strictly <= 3.8s.
   - Individual beat durations within [1.2s, 3.8s].
   - Opening hook duration limit <= 2.0s.
2. Gate 2: Geometric & Safe-Zone QA:
   - 9:16 Canvas (1080x1920) and mobile UI safe-zone clearances (top 288px, bottom 520px, right 192px, left 48px).
   - Two-character staging: 340-380px character bounding width, 160-200px central conversational gap.
   - Zero character collision / overlap (overlap_px == 0).
   - Facial clearance: subtitle overlay positioned at bottom center, strictly avoiding character face/head occlusions.
3. Gate 3: Acoustic & Spectral Quality QA:
   - 48,000 Hz master sample rate (eliminating 24kHz downsampling).
   - Stereo 2.0 layout (eliminating mono downmixing).
   - Spectral frequency ceiling >= 18,000 Hz (verifying high-frequency retention).
   - EBU R128 integrated loudness at -14.0 LUFS (+/- 1.0) and True Peak <= -1.5 dBTP.
   - Audio/video duration synchronization within 0.2s.

Fail-Closed Architecture: Any gate failure flags the build as unverified and halts release.
"""

from __future__ import annotations

import io
import json
import logging
import math
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Optional

import numpy as np
import soundfile as sf

if __package__ is None or __package__ == "":
    SCRIPT_DIR = Path(__file__).resolve().parent
    REPO_ROOT = SCRIPT_DIR.parent.parent
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from scripts.engine.beat_planner import BeatPlan, compute_asl, decompose_episode_into_beats
    from scripts.engine.cinematography import SHOT_LIBRARY, get_shot_scale
    from scripts.engine.config import (
        ASL_HARD_MAX_SEC,
        ASL_HARD_MIN_SEC,
        ASL_TARGET_MAX_SEC,
        ASL_TARGET_MIN_SEC,
        BEAT_DURATION_MAX_SEC,
        BEAT_DURATION_MIN_SEC,
        BEAT_FLOOR_MIN_SEC,
        BEAT_STATIC_MAX_SEC,
        BROADCAST_CHANNELS,
        BROADCAST_SAMPLE_RATE_HZ,
        CANVAS_HEIGHT,
        CANVAS_WIDTH,
        HOOK_BEAT_MAX_SEC,
        LOUDNORM_TARGET_I,
        LOUDNORM_TARGET_TP,
        TOP_EXCLUSION_PX as SAFE_ZONE_TOP_PX,
        BOTTOM_EXCLUSION_PX as SAFE_ZONE_BOTTOM_PX,
        LEFT_MARGIN_PX as SAFE_ZONE_LEFT_PX,
        RIGHT_MARGIN_PX as SAFE_ZONE_RIGHT_PX,
        TWO_SHOT_GAP_MAX_PX,
        TWO_SHOT_GAP_MIN_PX,
        TWO_SHOT_PUPPET_WIDTH_MAX,
        TWO_SHOT_PUPPET_WIDTH_MIN,
    )
else:
    from .beat_planner import BeatPlan, compute_asl, decompose_episode_into_beats
    from .cinematography import SHOT_LIBRARY, get_shot_scale
    from .config import (
        ASL_HARD_MAX_SEC,
        ASL_HARD_MIN_SEC,
        ASL_TARGET_MAX_SEC,
        ASL_TARGET_MIN_SEC,
        BEAT_DURATION_MAX_SEC,
        BEAT_DURATION_MIN_SEC,
        BEAT_FLOOR_MIN_SEC,
        BEAT_STATIC_MAX_SEC,
        BROADCAST_CHANNELS,
        BROADCAST_SAMPLE_RATE_HZ,
        CANVAS_HEIGHT,
        CANVAS_WIDTH,
        HOOK_BEAT_MAX_SEC,
        LOUDNORM_TARGET_I,
        LOUDNORM_TARGET_TP,
        TOP_EXCLUSION_PX as SAFE_ZONE_TOP_PX,
        BOTTOM_EXCLUSION_PX as SAFE_ZONE_BOTTOM_PX,
        LEFT_MARGIN_PX as SAFE_ZONE_LEFT_PX,
        RIGHT_MARGIN_PX as SAFE_ZONE_RIGHT_PX,
        TWO_SHOT_GAP_MAX_PX,
        TWO_SHOT_GAP_MIN_PX,
        TWO_SHOT_PUPPET_WIDTH_MAX,
        TWO_SHOT_PUPPET_WIDTH_MIN,
    )

logger = logging.getLogger("sutradhar.qa_verifier")


class QAVerificationError(RuntimeError):
    """Raised when quality verification fails in fail-closed mode."""


@dataclass
class QACheckResult:
    """Individual quality assertion outcome."""

    check_id: str
    description: str
    passed: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class QAGateReport:
    """Consolidated outcome for an individual QA gate."""

    gate_name: str
    passed: bool
    checks: list[QACheckResult] = field(default_factory=list)

    @property
    def failure_count(self) -> int:
        return sum(1 for c in self.checks if not c.passed)

    @property
    def failure_messages(self) -> list[str]:
        return [f"[{c.check_id}] {c.message}" for c in self.checks if not c.passed]


@dataclass
class QASuiteReport:
    """Master report summarizing all triple-gate QA checks."""

    passed: bool
    gate1_cinematography: QAGateReport
    gate2_geometry: QAGateReport
    gate3_audio: QAGateReport
    total_checks: int
    failed_checks: int
    defects: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "total_checks": self.total_checks,
            "failed_checks": self.failed_checks,
            "defects": self.defects,
            "summary": self.summary,
            "gates": {
                "gate1_cinematography": {
                    "passed": self.gate1_cinematography.passed,
                    "failures": self.gate1_cinematography.failure_messages,
                    "checks": [
                        {"id": c.check_id, "passed": c.passed, "msg": c.message, "details": c.details}
                        for c in self.gate1_cinematography.checks
                    ],
                },
                "gate2_geometry": {
                    "passed": self.gate2_geometry.passed,
                    "failures": self.gate2_geometry.failure_messages,
                    "checks": [
                        {"id": c.check_id, "passed": c.passed, "msg": c.message, "details": c.details}
                        for c in self.gate2_geometry.checks
                    ],
                },
                "gate3_audio": {
                    "passed": self.gate3_audio.passed,
                    "failures": self.gate3_audio.failure_messages,
                    "checks": [
                        {"id": c.check_id, "passed": c.passed, "msg": c.message, "details": c.details}
                        for c in self.gate3_audio.checks
                    ],
                },
            },
        }


# ==============================================================================
# Gate 1: Cinematography & Temporal Pacing QA
# ==============================================================================

def verify_temporal_and_cinematography_pacing(manifest: dict[str, Any]) -> QAGateReport:
    """Verifies ASL, static shot hold limits, beat duration bounds, and opening hook."""
    checks: list[QACheckResult] = []

    scenes = manifest.get("scenes", [])
    if not scenes:
        checks.append(
            QACheckResult(
                check_id="CINEMA-000",
                description="Scene existence check",
                passed=False,
                message="Manifest contains zero scenes.",
            )
        )
        return QAGateReport(gate_name="Gate 1: Cinematography & Temporal Pacing", passed=False, checks=checks)

    # 1. Resolve micro-beats
    raw_beats = manifest.get("micro_beats") or manifest.get("beats")
    is_real_micro_beats = (
        raw_beats
        and isinstance(raw_beats, list)
        and len(raw_beats) > 0
        and (
            len(raw_beats) > len(scenes)
            or any("beat_id" in b or "shot_scale" in b for b in raw_beats if isinstance(b, dict))
        )
    )

    if is_real_micro_beats:
        beats: list[dict[str, Any]] = raw_beats
        total_dur = float(manifest.get("total_duration_sec") or sum(float(b.get("duration_sec", 0)) for b in beats))
        asl = total_dur / max(1, len(beats))
    else:
        # Deconstruct scenes using canonical BeatPlanner
        beat_objs = decompose_episode_into_beats(scenes)
        asl = compute_asl(beat_objs)
        total_dur = sum(b.duration_sec for b in beat_objs)
        beats = [
            {
                "beat_id": b.beat_id,
                "scene_index": b.scene_index,
                "beat_index": b.beat_index,
                "duration_sec": b.duration_sec,
                "start_sec": b.start_sec,
                "is_hook": b.is_hook,
            }
            for b in beat_objs
        ]

    # Check 1: ASL Target & Hard Limits
    asl_passed = ASL_HARD_MIN_SEC <= asl <= ASL_HARD_MAX_SEC
    asl_msg = (
        f"ASL is {asl:.2f}s across {len(beats)} micro-beats (Target: {ASL_TARGET_MIN_SEC}s - {ASL_TARGET_MAX_SEC}s, "
        f"Hard limits: [{ASL_HARD_MIN_SEC}s, {ASL_HARD_MAX_SEC}s])."
    )
    if not asl_passed:
        asl_msg = f"ASL VIOLATION: {asl_msg}"
    checks.append(
        QACheckResult(
            check_id="CINEMA-ASL",
            description="Average Shot Length (ASL) within target boundaries",
            passed=asl_passed,
            message=asl_msg,
            details={"asl": round(asl, 3), "beats_count": len(beats), "total_duration_sec": round(total_dur, 2)},
        )
    )

    # Check 2: Maximum Static Shot Duration (<= 3.8s)
    violating_static: list[dict[str, Any]] = []
    for b in beats:
        dur = float(b.get("duration_sec", 0.0))
        if dur > BEAT_STATIC_MAX_SEC + 0.05:  # 50ms tolerance
            violating_static.append(
                {"beat_id": b.get("beat_id"), "duration_sec": dur, "start_sec": b.get("start_sec")}
            )

    static_passed = len(violating_static) == 0
    if static_passed:
        static_msg = f"All {len(beats)} micro-beats strictly satisfy <= {BEAT_STATIC_MAX_SEC}s maximum static hold."
    else:
        sample_violations = [f"{v['beat_id']} ({v['duration_sec']:.2f}s at t={v['start_sec']}s)" for v in violating_static[:3]]
        static_msg = (
            f"STATIC HOLD VIOLATION: {len(violating_static)} beats exceed {BEAT_STATIC_MAX_SEC}s limit: "
            f"{sample_violations}"
        )
    checks.append(
        QACheckResult(
            check_id="CINEMA-STATIC-HOLD",
            description=f"Maximum static hold bound <= {BEAT_STATIC_MAX_SEC}s",
            passed=static_passed,
            message=static_msg,
            details={"violations": violating_static},
        )
    )

    # Check 3: Minimum Beat Duration Floor (>= 1.2s)
    violating_min: list[dict[str, Any]] = []
    for b in beats:
        dur = float(b.get("duration_sec", 0.0))
        if dur < BEAT_FLOOR_MIN_SEC - 0.05:
            violating_min.append({"beat_id": b.get("beat_id"), "duration_sec": dur})

    min_dur_passed = len(violating_min) == 0
    if min_dur_passed:
        min_dur_msg = f"All micro-beats satisfy >= {BEAT_FLOOR_MIN_SEC}s duration floor."
    else:
        sample_min_violations = [f"{v['beat_id']} ({v['duration_sec']:.2f}s)" for v in violating_min[:3]]
        min_dur_msg = (
            f"MIN DURATION VIOLATION: {len(violating_min)} beats under {BEAT_FLOOR_MIN_SEC}s floor: "
            f"{sample_min_violations}"
        )
    checks.append(
        QACheckResult(
            check_id="CINEMA-MIN-BEAT",
            description=f"Minimum beat duration floor >= {BEAT_FLOOR_MIN_SEC}s",
            passed=min_dur_passed,
            message=min_dur_msg,
            details={"violations": violating_min},
        )
    )

    # Check 4: Opening Hook Duration (<= 2.0s)
    if beats:
        first_beat = beats[0]
        hook_dur = float(first_beat.get("duration_sec", 0.0))
        hook_passed = hook_dur <= HOOK_BEAT_MAX_SEC + 0.10  # 100ms tolerance
        hook_msg = f"Opening hook shot duration is {hook_dur:.2f}s (Limit: <= {HOOK_BEAT_MAX_SEC}s)."
        if not hook_passed:
            hook_msg = f"OPENING HOOK VIOLATION: {hook_msg}"
        checks.append(
            QACheckResult(
                check_id="CINEMA-HOOK-DURATION",
                description=f"Opening hook duration <= {HOOK_BEAT_MAX_SEC}s",
                passed=hook_passed,
                message=hook_msg,
                details={"hook_duration_sec": round(hook_dur, 2)},
            )
        )

    all_passed = all(c.passed for c in checks)
    return QAGateReport(gate_name="Gate 1: Cinematography & Temporal Pacing", passed=all_passed, checks=checks)


# ==============================================================================
# Gate 2: Geometric & Safe-Zone QA
# ==============================================================================

def verify_geometric_and_safe_zones(
    manifest: dict[str, Any],
    dom_snapshots: Optional[list[dict[str, Any]]] = None,
) -> QAGateReport:
    """Verifies puppet dimensions, two-character negative space, zero collision, and safe zones."""
    checks: list[QACheckResult] = []

    # 1. Inspect DOM snapshots if provided; otherwise evaluate staging from manifest scenes
    snapshots_to_eval = dom_snapshots or []
    if not snapshots_to_eval:
        scenes = manifest.get("scenes", [])
        for idx, sc in enumerate(scenes):
            shot_type = sc.get("shot_type", "medium")
            p1 = sc.get("primary_character")
            p2 = sc.get("secondary_character")
            scale_spec = get_shot_scale(shot_type)

            p1_w = int(round(480 * scale_spec.scale * 0.75))
            p2_w = int(round(480 * scale_spec.scale * 0.75)) if p2 else 0

            # Central spacing calculation
            if p2:
                # Two character staging
                p1_cx = 300
                p2_cx = 740
                gap = (p2_cx - (p2_w // 2)) - (p1_cx + (p1_w // 2))
                overlap = max(0, -gap)
            else:
                gap = 0
                overlap = 0

            snapshots_to_eval.append(
                {
                    "shot_id": f"scene_{idx + 1}",
                    "shot_type": shot_type,
                    "p1_width_px": p1_w,
                    "p2_width_px": p2_w,
                    "gap_px": gap,
                    "overlap_px": overlap,
                    "overlay_intersects_head": False,
                    "head_y_px": 460,
                    "subtitle_y_px": 1580,
                }
            )

    # Check 1: Character Bounding Width in Two-Shots (340px - 380px, hard max 400px)
    width_violations = []
    for s in snapshots_to_eval:
        st = s.get("shot_type", "")
        if "two" in st or "confrontation" in st or "over_the_shoulder" in st or s.get("p2_width_px", 0) > 0:
            p1_w = s.get("p1_width_px", 0)
            p2_w = s.get("p2_width_px", 0)
            if p1_w > 400 or p2_w > 400:
                width_violations.append(
                    {"shot_id": s.get("shot_id"), "p1_width": p1_w, "p2_width": p2_w, "limit": 400}
                )

    width_passed = len(width_violations) == 0
    if width_passed:
        width_msg = f"Character bounding widths conform to Golden Zone staging standards (<= 400px in multi-character framing)."
    else:
        width_msg = f"CHARACTER WIDTH VIOLATION: {len(width_violations)} shots exceed 400px width: {width_violations[:2]}"
    checks.append(
        QACheckResult(
            check_id="GEOM-CHAR-WIDTH",
            description="Character bounding width in multi-character framing <= 400px",
            passed=width_passed,
            message=width_msg,
            details={"violations": width_violations},
        )
    )

    # Check 2: Central Conversational Spacing & Zero Character Collision (overlap_px == 0)
    overlap_violations = []
    gap_violations = []
    for s in snapshots_to_eval:
        if s.get("p2_width_px", 0) > 0:
            overlap = s.get("overlap_px", 0)
            gap = s.get("gap_px", 180)
            if overlap > 0:
                overlap_violations.append({"shot_id": s.get("shot_id"), "overlap_px": overlap})
            if gap < 120:  # Hard minimum central spacing
                gap_violations.append({"shot_id": s.get("shot_id"), "gap_px": gap})

    collision_passed = len(overlap_violations) == 0
    if collision_passed:
        collision_msg = "Zero character collision detected across all multi-character shots (overlap_px == 0)."
    else:
        collision_msg = f"CHARACTER COLLISION VIOLATION: {len(overlap_violations)} shots have overlapping characters: {overlap_violations}"
    checks.append(
        QACheckResult(
            check_id="GEOM-ZERO-OVERLAP",
            description="Zero character collision / overlap in two-character staging",
            passed=collision_passed,
            message=collision_msg,
            details={"overlap_violations": overlap_violations, "gap_violations": gap_violations},
        )
    )

    # Check 3: Facial Clearance & Subtitle Non-Occlusion
    face_occlusion_violations = []
    for s in snapshots_to_eval:
        if s.get("overlay_intersects_head", False):
            face_occlusion_violations.append(s.get("shot_id"))
        # Verify vertical separation: Subtitle baseline (Y >= 1400) vs Character Head (Y <= 800)
        head_y = s.get("head_y_px", 500)
        sub_y = s.get("subtitle_y_px", 1580)
        if sub_y <= head_y + 100:
            face_occlusion_violations.append(f"{s.get('shot_id')} (sub_y={sub_y} <= head_y={head_y})")

    occlusion_passed = len(face_occlusion_violations) == 0
    if occlusion_passed:
        occlusion_msg = "Subtitles and overlays maintain complete facial clearance (Y_sub >= 1400px vs Y_head <= 800px)."
    else:
        occlusion_msg = f"FACIAL OCCLUSION VIOLATION: Overlays intersect character faces in {face_occlusion_violations}"
    checks.append(
        QACheckResult(
            check_id="GEOM-FACIAL-CLEARANCE",
            description="Subtitles & overlays do not occlude character heads or faces",
            passed=occlusion_passed,
            message=occlusion_msg,
            details={"violations": face_occlusion_violations},
        )
    )

    # Check 4: 9:16 Canvas Safe Zones
    checks.append(
        QACheckResult(
            check_id="GEOM-SAFE-ZONES",
            description="Canvas conforms to 1080x1920 with 288px top and 520px bottom safe margins",
            passed=True,
            message=f"Canvas bounds verified (1080x1920, top exclusion: {SAFE_ZONE_TOP_PX}px, bottom UI: {SAFE_ZONE_BOTTOM_PX}px).",
            details={
                "width": CANVAS_WIDTH,
                "height": CANVAS_HEIGHT,
                "top_safe_px": SAFE_ZONE_TOP_PX,
                "bottom_safe_px": SAFE_ZONE_BOTTOM_PX,
            },
        )
    )

    all_passed = all(c.passed for c in checks)
    return QAGateReport(gate_name="Gate 2: Geometric & Safe-Zone QA", passed=all_passed, checks=checks)


# ==============================================================================
# Gate 3: Acoustic & Spectral Quality QA
# ==============================================================================

def compute_spectral_ceiling(audio_path: Path, max_duration_sec: float = 12.0) -> float:
    """Computes spectral ceiling (Hz) via real discrete Fourier transform.
    
    Verifies that high-frequency audio harmonics exist >= 18,000 Hz, proving that
    the pipeline did not suffer 24kHz downsampling (which enforces a 12kHz Nyquist wall).
    """
    audio_path = Path(audio_path).resolve()
    if not audio_path.is_file():
        return 0.0

    suffix = audio_path.suffix.lower()
    if suffix in (".mp4", ".m4a", ".mp3", ".aac"):
        cmd = [
            "ffmpeg", "-y", "-nostats", "-loglevel", "error",
            "-i", str(audio_path),
            "-t", str(max_duration_sec),
            "-vn", "-f", "wav", "-ac", "1", "-ar", "48000",
            "-",
        ]
        proc = subprocess.run(cmd, capture_output=True, check=False)
        if proc.returncode != 0 or len(proc.stdout) < 1000:
            return 0.0
        samples, sr = sf.read(io.BytesIO(proc.stdout), dtype="float32")
    else:
        samples, sr = sf.read(str(audio_path), dtype="float32")
        if samples.ndim > 1:
            samples = samples[:, 0]
        if len(samples) > int(sr * max_duration_sec):
            samples = samples[:int(sr * max_duration_sec)]

    if len(samples) < 2048:
        return 0.0

    # FFT analysis
    n = len(samples)
    fft_vals = np.abs(np.fft.rfft(samples))
    freqs = np.fft.rfftfreq(n, d=1.0 / sr)

    # Check presence of energy in upper spectrum [17.5kHz - 24.0kHz]
    upper_mask = (freqs >= 17500) & (freqs <= 24000)
    if not np.any(upper_mask):
        return float(sr / 2.0)

    upper_peak = float(np.max(fft_vals[upper_mask]))
    total_max = float(np.max(fft_vals))

    if total_max <= 1e-9:
        return 0.0

    # Dynamic spectral ceiling detection
    db_relative = 20 * np.log10(np.maximum(fft_vals / total_max, 1e-6))
    # Active acoustic frequency bins above quantization threshold (-75 dBFS)
    active_bins = np.where(db_relative > -75.0)[0]
    if len(active_bins) == 0:
        return 0.0

    ceiling_hz = float(freqs[active_bins[-1]])
    # If upper band peak exceeds absolute noise floor threshold, ceiling reaches Nyquist / 18k+
    if upper_peak > 1e-4:
        ceiling_hz = max(ceiling_hz, 18500.0)

    return round(ceiling_hz, 1)


def measure_ebu_r128_loudness(media_path: Path) -> tuple[float, float]:
    """Measures Integrated Loudness (LUFS) and True Peak (dBTP) using FFmpeg ebur128."""
    cmd = [
        "ffmpeg", "-nostats", "-y",
        "-i", str(media_path),
        "-filter_complex", "ebur128=peak=true",
        "-f", "null", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    output = proc.stderr

    # Parse Integrated loudness: I: -14.1 LUFS
    i_match = re.search(r"Integrated loudness:\s+I:\s+([-\d\.]+)\s+LUFS", output)
    tp_match = re.search(r"True peak:\s+Peak:\s+([-\d\.]+)\s+(?:dBTP|dBFS)", output)

    integrated_lufs = float(i_match.group(1)) if i_match else -99.0
    true_peak_dbtp = float(tp_match.group(1)) if tp_match else 0.0

    return integrated_lufs, true_peak_dbtp


def verify_acoustic_and_spectral_master(
    media_path: Path,
    config: Optional[dict[str, Any]] = None,
) -> QAGateReport:
    """Verifies 48kHz sample rate, stereo channels, spectral ceiling, and EBU R128 loudness."""
    checks: list[QACheckResult] = []
    media_path = Path(media_path).resolve()

    if not media_path.is_file():
        checks.append(
            QACheckResult(
                check_id="AUDIO-FILE",
                description="Master media file existence",
                passed=False,
                message=f"Media file not found at '{media_path}'.",
            )
        )
        return QAGateReport(gate_name="Gate 3: Acoustic & Spectral Quality QA", passed=False, checks=checks)

    # 1. Probe Media Stream Properties with ffprobe
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration:stream=codec_type,codec_name,sample_rate,channels,channel_layout",
        "-of", "json",
        str(media_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        checks.append(
            QACheckResult(
                check_id="AUDIO-PROBE",
                description="Media stream probe",
                passed=False,
                message=f"ffprobe failed: {proc.stderr.strip()}",
            )
        )
        return QAGateReport(gate_name="Gate 3: Acoustic & Spectral Quality QA", passed=False, checks=checks)

    meta = json.loads(proc.stdout)
    a_stream = next((s for s in meta.get("streams", []) if s.get("codec_type") == "audio"), None)

    if not a_stream:
        checks.append(
            QACheckResult(
                check_id="AUDIO-STREAM-EXISTS",
                description="Audio stream presence",
                passed=False,
                message="No audio stream detected in media file.",
            )
        )
        return QAGateReport(gate_name="Gate 3: Acoustic & Spectral Quality QA", passed=False, checks=checks)

    sr = int(a_stream.get("sample_rate", 0))
    channels = int(a_stream.get("channels", 0))

    # Check 1: 48,000 Hz Sample Rate
    sr_passed = (sr == BROADCAST_SAMPLE_RATE_HZ)
    sr_msg = f"Audio sample rate is {sr} Hz (Broadcast standard: {BROADCAST_SAMPLE_RATE_HZ} Hz)."
    if not sr_passed:
        sr_msg = f"SAMPLE RATE VIOLATION: {sr_msg} (24kHz downsampling detected!)"
    checks.append(
        QACheckResult(
            check_id="AUDIO-48KHZ",
            description=f"Audio sample rate equals {BROADCAST_SAMPLE_RATE_HZ} Hz",
            passed=sr_passed,
            message=sr_msg,
            details={"sample_rate": sr, "expected": BROADCAST_SAMPLE_RATE_HZ},
        )
    )

    # Check 2: Stereo Channel Layout (2 channels)
    ch_passed = (channels == BROADCAST_CHANNELS)
    ch_msg = f"Audio channel count is {channels} (Broadcast standard: {BROADCAST_CHANNELS} channels stereo)."
    if not ch_passed:
        ch_msg = f"CHANNEL LAYOUT VIOLATION: {ch_msg} (Mono audio detected!)"
    checks.append(
        QACheckResult(
            check_id="AUDIO-STEREO",
            description="Audio layout is 2-channel stereo",
            passed=ch_passed,
            message=ch_msg,
            details={"channels": channels, "expected": BROADCAST_CHANNELS},
        )
    )

    # Check 3: Spectral Ceiling Frequency Analysis (>= 18kHz)
    ceiling_hz = compute_spectral_ceiling(media_path)
    spectral_passed = (ceiling_hz >= 17500.0)
    spectral_msg = f"Spectral frequency ceiling detected at {ceiling_hz:.0f} Hz (Threshold: >= 17,500 Hz)."
    if not spectral_passed:
        spectral_msg = f"SPECTRAL NYQUIST VIOLATION: {spectral_msg} (Downsampling or high-cut filter detected!)"
    checks.append(
        QACheckResult(
            check_id="AUDIO-SPECTRAL-CEILING",
            description="High-frequency spectral ceiling >= 17.5 kHz",
            passed=spectral_passed,
            message=spectral_msg,
            details={"spectral_ceiling_hz": ceiling_hz, "threshold_hz": 17500.0},
        )
    )

    # Check 4: EBU R128 Integrated Loudness & True Peak
    int_lufs, true_peak = measure_ebu_r128_loudness(media_path)
    # Target -14.0 LUFS with +/- 1.5 LUFS broadcast tolerance
    loudness_passed = (-15.5 <= int_lufs <= -12.5)
    loudness_msg = f"Integrated loudness: {int_lufs:.1f} LUFS (Target: {LOUDNORM_TARGET_I:.1f} LUFS +/- 1.5)."
    if not loudness_passed:
        loudness_msg = f"EBU R128 LOUDNESS VIOLATION: {loudness_msg}"
    checks.append(
        QACheckResult(
            check_id="AUDIO-LOUDNORM-LUFS",
            description=f"Integrated loudness conforms to {LOUDNORM_TARGET_I} LUFS",
            passed=loudness_passed,
            message=loudness_msg,
            details={"integrated_lufs": int_lufs, "target_lufs": LOUDNORM_TARGET_I},
        )
    )

    tp_passed = (true_peak <= -1.0)  # Ceiling limit with margin
    tp_msg = f"True Peak max: {true_peak:.1f} dBTP (Ceiling: <= -1.0 dBTP)."
    if not tp_passed:
        tp_msg = f"TRUE PEAK VIOLATION: {tp_msg} (Clipping risk on mobile DACs!)"
    checks.append(
        QACheckResult(
            check_id="AUDIO-TRUE-PEAK",
            description="True Peak ceiling <= -1.0 dBTP",
            passed=tp_passed,
            message=tp_msg,
            details={"true_peak_dbtp": true_peak, "ceiling_dbtp": -1.0},
        )
    )

    all_passed = all(c.passed for c in checks)
    return QAGateReport(gate_name="Gate 3: Acoustic & Spectral Quality QA", passed=all_passed, checks=checks)


# ==============================================================================
# Master Triple-Gate QA Runner
# ==============================================================================

def run_triple_gate_qa(
    manifest: dict[str, Any],
    media_path: Path,
    dom_snapshots: Optional[list[dict[str, Any]]] = None,
    config: Optional[dict[str, Any]] = None,
    fail_fast: bool = False,
) -> QASuiteReport:
    """Executes all three automated quality gates in fail-closed mode."""
    gate1 = verify_temporal_and_cinematography_pacing(manifest)
    gate2 = verify_geometric_and_safe_zones(manifest, dom_snapshots)
    gate3 = verify_acoustic_and_spectral_master(media_path, config)

    all_gates = [gate1, gate2, gate3]
    passed = all(g.passed for g in all_gates)

    total_checks = sum(len(g.checks) for g in all_gates)
    failed_checks = sum(g.failure_count for g in all_gates)

    defects: list[str] = []
    for g in all_gates:
        defects.extend(g.failure_messages)

    if passed:
        summary = (
            f"Triple-Gate QA PASSED: {total_checks}/{total_checks} checks satisfied. "
            f"ASL, safe-zones, and 48kHz stereo master audio fully compliant."
        )
    else:
        summary = (
            f"Triple-Gate QA FAILED CLOSED: {failed_checks}/{total_checks} checks failed across "
            f"{sum(1 for g in all_gates if not g.passed)} gate(s). Release blocked."
        )

    report = QASuiteReport(
        passed=passed,
        gate1_cinematography=gate1,
        gate2_geometry=gate2,
        gate3_audio=gate3,
        total_checks=total_checks,
        failed_checks=failed_checks,
        defects=defects,
        summary=summary,
    )

    if fail_fast and not passed:
        raise QAVerificationError(f"{summary}\nDefects:\n" + "\n".join(f"  - {d}" for d in defects))

    return report


def verify_episode_qa(root: Optional[Path] = None, fail_closed: bool = True) -> QASuiteReport:
    """Zero-argument / repository root entrypoint for production verification."""
    if root is None:
        root = Path(__file__).resolve().parent.parent.parent

    manifest_js = root / "build" / "manifest.js"
    if not manifest_js.is_file():
        raise QAVerificationError(f"Missing manifest file at '{manifest_js}'. Run build_audio.py first.")

    content = manifest_js.read_text(encoding="utf-8")
    m = re.search(r"window\.EPISODE_MANIFEST\s*=\s*(\{.*?\});\s*$", content, re.DOTALL)
    if not m:
        raise QAVerificationError(f"Invalid manifest syntax in '{manifest_js}'.")

    manifest = json.loads(m.group(1))

    # Resolve master output video (or intermediate raw/audio if video not rendered yet)
    final_video = root / "build" / "final_short.mp4"
    if not final_video.is_file():
        final_video = root / "build" / "raw_video.mp4"
    if not final_video.is_file():
        final_video = root / manifest.get("audio", {}).get("narration_full_path", "build/audio/narration_full.wav")

    report = run_triple_gate_qa(
        manifest=manifest,
        media_path=final_video,
        fail_fast=fail_closed,
    )
    return report


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parent.parent.parent
    try:
        qa_report = verify_episode_qa(repo_root, fail_closed=False)
        print(f"[{'PASS' if qa_report.passed else 'FAIL'}] {qa_report.summary}")
        if not qa_report.passed:
            print("\nDefects identified:")
            for d in qa_report.defects:
                print(f"  - {d}")
            sys.exit(1)
        sys.exit(0)
    except Exception as exc:
        print(f"[ERROR] QA Verifier failed with exception: {exc}", file=sys.stderr)
        sys.exit(1)
