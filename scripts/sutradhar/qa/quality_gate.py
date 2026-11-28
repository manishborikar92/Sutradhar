"""Fail-closed Quality Gate (zero synthetic dom_snapshots fabrication)."""

from __future__ import annotations

import json
import subprocess
import tempfile
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import kinocut
import numpy as np
from PIL import Image

from sutradhar.audio.sound_mixer import (
    DEFAULT_TARGET_LUFS,
    DEFAULT_TRUE_PEAK_DBTP,
    detect_silences,
    measure_loudness_ebur128,
    probe_audio_stream,
)
from sutradhar.audio.whisper_aligner import write_text_atomic
from sutradhar.config import load_config
from sutradhar.qa.hyperframes_runner import (
    run_chromium_runtime_probe,
    run_hf_check,
    run_hf_measure_look,
    select_storyboard_timestamps,
    stitch_contact_sheet,
    validate_runtime_probe_and_hf_check,
)
from sutradhar.qa.render_optimizer import DEFAULT_MAX_FILE_BYTES, validate_mp4_contract
from sutradhar.visual.storyboard_composer import (
    CAPTION_SAFE_BOTTOM_MAX,
    GROUND_TOLERANCE_PX,
    SHORTS_PILL_MAX_X,
    SHORTS_PILL_MAX_Y,
    SHORTS_PILL_MIN_X,
    SHORTS_PILL_MIN_Y,
    validate_storyboard_grounding,
)
from sutradhar.visual.thumbnail_builder import SHORTS_2X3_CROP_BOX
from thumbnail_utils import validate_local_thumbnail


class QualityGateError(RuntimeError):
    """Raised whenever any fail-closed QA gate fails."""


@dataclass
class QualityGateReport:
    """Structured fail-closed QA summary across geometry, motion, KinoCut, audio, and thumbnail."""

    passed: bool
    failures: list[str] = field(default_factory=list)
    geometry_gate: dict[str, Any] = field(default_factory=dict)
    mp4_gate: dict[str, Any] = field(default_factory=dict)
    motion_and_look_gate: dict[str, Any] = field(default_factory=dict)
    audio_gate: dict[str, Any] = field(default_factory=dict)
    thumbnail_gate: dict[str, Any] = field(default_factory=dict)
    report_path: Optional[Path] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "failures": self.failures,
            "geometry_gate": self.geometry_gate,
            "mp4_gate": self.mp4_gate,
            "motion_and_look_gate": self.motion_and_look_gate,
            "audio_gate": self.audio_gate,
            "thumbnail_gate": self.thumbnail_gate,
        }


def reject_synthetic_dom_snapshots(payload: dict[str, Any]) -> None:
    """Fail closed if a v2 QA payload attempts to supply legacy synthetic dom_snapshots."""
    if not isinstance(payload, dict):
        return
    if "dom_snapshots" in payload:
        raise QualityGateError(
            "Synthetic 'dom_snapshots' are strictly forbidden in v2 fail-closed QA; "
            "run real Chromium DOM + StoryboardIR geometry verification instead."
        )


def _decode_frame_array(mp4_path: Path, timestamp_sec: float, out_png: Path) -> np.ndarray:
    cmd = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-ss",
        f"{max(0.0, timestamp_sec):.3f}",
        "-i",
        str(mp4_path),
        "-frames:v",
        "1",
        str(out_png),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0 or not out_png.is_file():
        raise QualityGateError(f"Failed to decode MP4 frame at t={timestamp_sec:.2f}s: {proc.stderr.strip()}")
    with Image.open(out_png) as img:
        return np.asarray(img.convert("RGB"), dtype=np.float32)


def verify_per_scene_motion_and_grid(
    mp4_path: Path,
    duration_sec: float,
    scene_ranges: list[tuple[float, float]],
    *,
    final_qa_grid_path: Path,
    final_qa_grid_safezones_path: Optional[Path] = None,
) -> dict[str, Any]:
    """Decode real MP4 frames for 15-frame QA grid + zero dead black frames + per-scene motion."""
    timestamps = select_storyboard_timestamps(duration_sec, scene_ranges=scene_ranges, count=15)
    black_frames: list[float] = []
    frozen_scenes: list[dict[str, Any]] = []
    scene_motion: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="sutradhar_qa_frames_", ignore_cleanup_errors=True) as td:
        td_path = Path(td)
        grid_imgs: list[Path] = []
        grid_labels: list[str] = []
        for idx, t in enumerate(timestamps):
            p = td_path / f"grid_{idx:02d}.png"
            arr = _decode_frame_array(mp4_path, t, p)
            mean_luma = float(np.mean(arr))
            if mean_luma < 4.0:
                black_frames.append(t)
            grid_imgs.append(p)
            grid_labels.append(f"#{idx + 1} t={t:.2f}s")

        cols = 5 if len(grid_imgs) >= 10 else 3
        stitch_contact_sheet(grid_imgs, grid_labels, final_qa_grid_path, cols=cols, thumb_w=270, thumb_h=480)
        if final_qa_grid_safezones_path is not None:
            stitch_contact_sheet(
                grid_imgs,
                grid_labels,
                final_qa_grid_safezones_path,
                cols=cols,
                thumb_w=270,
                thumb_h=480,
                overlay_safe_zones=True,
            )

        for idx, (s0, s1) in enumerate(scene_ranges):
            span = float(s1) - float(s0)
            t_a = min(max(0.05, float(s0) + min(0.25, span * 0.2)), max(0.05, duration_sec - 0.15))
            t_b = min(max(t_a + 0.1, float(s1) - min(0.25, span * 0.2)), max(0.1, duration_sec - 0.08))
            arr_a = _decode_frame_array(mp4_path, t_a, td_path / f"sc_{idx}_a.png")
            arr_b = _decode_frame_array(mp4_path, t_b, td_path / f"sc_{idx}_b.png")
            luma_a = float(np.mean(arr_a))
            luma_b = float(np.mean(arr_b))
            if luma_a < 4.0:
                black_frames.append(t_a)
            if luma_b < 4.0:
                black_frames.append(t_b)
            mad = float(np.mean(np.abs(arr_b - arr_a)))
            rec = {
                "scene_index": idx,
                "t_a": round(t_a, 3),
                "t_b": round(t_b, 3),
                "mad": round(mad, 4),
                "luma_a": round(luma_a, 2),
                "luma_b": round(luma_b, 2),
            }
            scene_motion.append(rec)
            if span >= 1.2 and mad < 0.05:
                frozen_scenes.append(rec)

    return {
        "grid_frame_count": len(timestamps),
        "final_qa_grid": str(final_qa_grid_path),
        "black_frames": black_frames,
        "frozen_scenes": frozen_scenes,
        "scene_motion": scene_motion,
    }


def _check_tail_quietness(wav_path: Optional[Path], mp4_path: Path, duration_sec: float, tail_sec: float = 0.7) -> dict[str, Any]:
    """Measure tail audio RMS over the trailing 0.7s to verify gentle outro headroom."""
    tail_start = max(0.0, float(duration_sec) - float(tail_sec))
    if wav_path is not None and Path(wav_path).is_file():
        with wave.open(str(wav_path), "rb") as wf:
            sr = wf.getframerate()
            ch = wf.getnchannels()
            sw = wf.getsampwidth()
            n_frames = wf.getnframes()
            tail_frames = min(n_frames, int(sr * tail_sec))
            wf.setpos(max(0, n_frames - tail_frames))
            raw = wf.readframes(tail_frames)
        if sw == 3:
            # 24-bit little-endian PCM
            b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
            s = (b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8) | (b[:, 2].astype(np.int32) << 16))
            s = np.where(s >= 0x800000, s - 0x1000000, s)
            samples = s.astype(np.float64) / float(0x800000)
        elif sw == 2:
            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0
        else:
            samples = np.frombuffer(raw, dtype=np.int32).astype(np.float64) / float(0x80000000)
        if samples.size == 0:
            rms_db = -90.0
        else:
            rms = float(np.sqrt(np.mean(samples * samples)))
            rms_db = float(20.0 * np.log10(max(rms, 1e-6)))
        return {"tail_window_sec": tail_sec, "tail_start_sec": round(tail_start, 3), "tail_rms_dbfs": round(rms_db, 2)}

    # Fallback via FFmpeg volumedetect on MP4 trailing window
    proc = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{tail_start:.3f}",
            "-i",
            str(mp4_path),
            "-vn",
            "-af",
            "volumedetect",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    rms_db = -90.0
    for line in proc.stderr.splitlines():
        if "mean_volume:" in line:
            try:
                rms_db = float(line.split("mean_volume:", 1)[1].strip().split()[0])
            except Exception:
                pass
    return {"tail_window_sec": tail_sec, "tail_start_sec": round(tail_start, 3), "tail_rms_dbfs": round(rms_db, 2)}


_KINOCUT_PROXY_DURATION_THRESHOLD_SEC = 25.0
_KINOCUT_PROXY_SHORT_SIDE_PX = 270
_KINOCUT_STATIC_FRAME_FLOOR = 0.35


def _probe_video_stream_basics(mp4_path: Path) -> tuple[int, int, float, str, str]:
    """Return (width, height, duration_sec, pix_fmt, color_range) for the primary video stream."""
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,pix_fmt,color_range:format=duration",
            "-of",
            "json",
            str(mp4_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise QualityGateError(f"ffprobe failed on '{mp4_path}': {proc.stderr.strip()}")
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise QualityGateError(f"Invalid ffprobe JSON for '{mp4_path}': {exc}") from exc
    stream = (payload.get("streams") or [{}])[0]
    fmt = payload.get("format") or {}
    return (
        int(stream.get("width") or 0),
        int(stream.get("height") or 0),
        float(fmt.get("duration") or 0.0),
        str(stream.get("pix_fmt") or "yuv420p"),
        str(stream.get("color_range") or ""),
    )


def _measure_full_res_temporal_motion(
    mp4_path: Path,
    *,
    width: int,
    height: int,
    pix_fmt: str = "yuv420p",
    color_range: str = "",
    static_frame_floor: float = _KINOCUT_STATIC_FRAME_FLOOR,
    timeout_sec: int = 120,
) -> dict[str, Any]:
    """Compute exact full-resolution inter-frame luma difference matching KinoCut's tblend YAVG floor."""
    if width <= 0 or height <= 0:
        raise QualityGateError(f"Invalid video dimensions for temporal motion check: {width}x{height}")

    frame_bytes = width * height
    full_range = color_range.lower() in {"pc", "jpeg", "full"} or pix_fmt.lower().startswith("yuvj")
    range_scale = (219.0 / 255.0) if full_range else 1.0

    proc = subprocess.Popen(
        [
            "ffmpeg",
            "-v",
            "error",
            "-nostdin",
            "-i",
            str(mp4_path),
            "-an",
            "-vf",
            "extractplanes=y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "gray",
            "-",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    diffs: list[float] = []
    prev: Optional[np.ndarray] = None
    assert proc.stdout is not None and proc.stderr is not None
    try:
        while True:
            buf = proc.stdout.read(frame_bytes)
            if not buf:
                break
            if len(buf) != frame_bytes:
                raise QualityGateError(
                    f"Truncated luma frame from ffmpeg ({len(buf)} != {frame_bytes} bytes) on '{mp4_path}'"
                )
            cur = np.frombuffer(buf, dtype=np.uint8)
            if prev is not None:
                abs_diff = np.maximum(cur, prev) - np.minimum(cur, prev)
                diffs.append(float(abs_diff.mean()) * range_scale)
            prev = cur
        stderr_text = proc.stderr.read().decode("utf-8", errors="replace").strip()
        returncode = proc.wait(timeout=timeout_sec)
    except subprocess.TimeoutExpired as exc:
        proc.kill()
        proc.wait()
        raise QualityGateError(f"Full-resolution temporal motion ffmpeg pass timed out after {timeout_sec}s") from exc
    finally:
        if proc.stdout is not None:
            proc.stdout.close()
        if proc.stderr is not None:
            proc.stderr.close()

    if returncode != 0:
        raise QualityGateError(f"Full-resolution temporal motion ffmpeg pass failed (rc={returncode}): {stderr_text}")
    if not diffs:
        raise QualityGateError(f"Full-resolution temporal motion produced zero frame pairs for '{mp4_path}'")

    sorted_diffs = sorted(diffs)
    n = len(sorted_diffs)
    median = sorted_diffs[n // 2] if n % 2 else (sorted_diffs[n // 2 - 1] + sorted_diffs[n // 2]) / 2.0
    static_count = sum(1 for v in diffs if v < static_frame_floor)
    return {
        "static_fraction": static_count / n,
        "mean_motion": sum(diffs) / n,
        "median_motion": median,
        "frames_analyzed": n,
        "static_frame_floor": static_frame_floor,
        "method": "ffmpeg_extractplanes_y_diff",
    }


def _build_kinocut_analysis_proxy(
    mp4_path: Path,
    proxy_path: Path,
    *,
    width: int,
    height: int,
    short_side_px: int = _KINOCUT_PROXY_SHORT_SIDE_PX,
) -> tuple[int, int]:
    """Encode an aspect-preserving fast analysis proxy so KinoCut signalstats/ffprobe stays well under 120s."""
    if width <= height:
        pw = max(2, short_side_px - (short_side_px % 2))
        ph = max(2, int(round(height * (pw / width) / 2.0)) * 2)
    else:
        ph = max(2, short_side_px - (short_side_px % 2))
        pw = max(2, int(round(width * (ph / height) / 2.0)) * 2)

    proc = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-nostdin",
            "-i",
            str(mp4_path),
            "-vf",
            f"scale={pw}:{ph}",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "16",
            "-c:a",
            "copy",
            str(proxy_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0 or not proxy_path.is_file():
        raise QualityGateError(f"Failed to create KinoCut analysis proxy: {proc.stderr.strip()}")
    return pw, ph


def _extract_temporal_motion_result(
    kc_def: dict[str, Any],
    kc_dark: dict[str, Any],
) -> tuple[Optional[float], Optional[dict[str, Any]], bool, list[str]]:
    """Extract temporal_motion static_fraction and fail closed with diagnostics if missing or failed."""
    tm_def = next((c for c in kc_def.get("checks", []) if c.get("name") == "temporal_motion"), None)
    tm_dark = next((c for c in kc_dark.get("checks", []) if c.get("name") == "temporal_motion"), None)
    tm_check = tm_def if tm_def is not None else tm_dark
    if tm_check is None:
        return None, None, False, ["KinoCut temporal_motion check missing from quality_check report"]

    failures: list[str] = []
    chosen_diag: Optional[dict[str, Any]] = None
    for label, check in (("default", tm_def), ("ui-capture-dark", tm_dark)):
        if check is None:
            continue
        details = check.get("details") or {}
        diag = details.get("diagnostic")
        if isinstance(diag, dict) and (diag.get("stage") or diag.get("message")):
            if chosen_diag is None:
                chosen_diag = diag
            stage = diag.get("stage", "unknown")
            msg = diag.get("message", "analysis failed")
            failures.append(f"KinoCut temporal_motion ({label}) failed ({stage}: {msg})")

    details = tm_check.get("details") or {}
    raw_sf = details.get("static_fraction")
    if raw_sf is None:
        if not failures:
            msg = tm_check.get("message") or "missing static_fraction"
            failures.append(f"KinoCut temporal_motion missing static_fraction: {msg}")
        return None, chosen_diag, bool(tm_check.get("passed", False)), failures

    return float(raw_sf), chosen_diag, bool(tm_check.get("passed", True)), failures


def _evaluate_kinocut_checks(
    mp4_path: Path,
    cfg: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Run dual-profile KinoCut checks (ui-capture-dark + default) and enforce thresholds."""
    qa_cfg = cfg.get("qa", {})
    dark_min = float(qa_cfg.get("kinocut_dark_min_score", 88.0))
    def_min = float(qa_cfg.get("kinocut_default_min_score", 55.0))
    max_static = float(qa_cfg.get("max_static_fraction", 0.15))

    width, height, duration_sec, pix_fmt, color_range = _probe_video_stream_basics(mp4_path)
    use_proxy = (
        duration_sec > _KINOCUT_PROXY_DURATION_THRESHOLD_SEC
        and width * height > 360 * 640
    )

    proxy_meta: Optional[dict[str, Any]] = None
    full_res_tm: Optional[dict[str, Any]] = None

    if use_proxy:
        with tempfile.TemporaryDirectory(prefix="sutradhar_kc_proxy_", ignore_cleanup_errors=True) as td:
            proxy_path = Path(td) / "kinocut_proxy.mp4"
            pw, ph = _build_kinocut_analysis_proxy(mp4_path, proxy_path, width=width, height=height)
            proxy_meta = {
                "width": pw,
                "height": ph,
                "source_width": width,
                "source_height": height,
                "duration_sec": round(duration_sec, 3),
            }
            kc_dark = kinocut.quality_check(str(proxy_path), profile="ui-capture-dark")
            kc_def = kinocut.quality_check(str(proxy_path))
        full_res_tm = _measure_full_res_temporal_motion(
            mp4_path,
            width=width,
            height=height,
            pix_fmt=pix_fmt,
            color_range=color_range,
        )
    else:
        kc_dark = kinocut.quality_check(str(mp4_path), profile="ui-capture-dark")
        kc_def = kinocut.quality_check(str(mp4_path))

    failures: list[str] = []
    dark_score = float(kc_dark.get("overall_score", 0.0))
    dark_all_passed = bool(kc_dark.get("all_passed", False))
    def_score = float(kc_def.get("overall_score", 0.0))

    cb_check = next((c for c in kc_def.get("checks", []) if c.get("name") == "color_balance"), None)
    cb_passed = bool(cb_check.get("passed")) if cb_check else False

    proxy_or_direct_sf, tm_diag, tm_passed, tm_failures = _extract_temporal_motion_result(kc_def, kc_dark)
    failures.extend(tm_failures)

    if use_proxy:
        # Only use full-res static_fraction when KinoCut temporal_motion itself completed without diagnostic errors.
        static_fraction: Optional[float] = (
            float(full_res_tm["static_fraction"]) if (full_res_tm is not None and not tm_failures) else None
        )
    else:
        static_fraction = proxy_or_direct_sf

    if dark_score < dark_min or not dark_all_passed:
        failures.append(
            f"KinoCut ui-capture-dark failed: score={dark_score} (min={dark_min}), all_passed={dark_all_passed}"
        )
    if def_score < def_min:
        failures.append(f"KinoCut default failed: score={def_score} (min={def_min})")
    if not cb_passed:
        failures.append(f"KinoCut color_balance failed: {cb_check}")
    if static_fraction is not None and static_fraction > max_static:
        failures.append(
            f"KinoCut static_fraction={static_fraction:.4f} exceeds max {max_static:.4f}"
        )
    elif not use_proxy and static_fraction is not None and not tm_passed and not tm_failures:
        failures.append(
            f"KinoCut temporal_motion failed (static_fraction={static_fraction:.4f})"
        )

    summary = {
        "dark_score": dark_score,
        "dark_all_passed": dark_all_passed,
        "default_score": def_score,
        "color_balance_passed": cb_passed,
        "static_fraction": round(static_fraction, 4) if static_fraction is not None else None,
        "temporal_motion_diagnostic": tm_diag,
        "full_res_temporal_motion": full_res_tm,
        "analysis_proxy": proxy_meta,
        "dark": kc_dark,
        "default": kc_def,
    }
    return summary, failures


def _extract_whisper_alignment_summary(
    *,
    audio_manifest: Optional[dict[str, Any] | Path],
    audio_manifest_path: Optional[Path],
    compiled_meta: dict[str, Any],
    composition_dir: Path,
) -> dict[str, Any]:
    """Extract per-scene Whisper alignment_match_ratio stats from audio_manifest or compiled metadata."""
    manifest_data: Optional[dict[str, Any]] = None
    manifest_source: Optional[str] = None

    candidate_path: Optional[Path] = None
    if isinstance(audio_manifest, dict):
        manifest_data = audio_manifest
        manifest_source = "audio_manifest_arg"
    elif audio_manifest is not None:
        candidate_path = Path(audio_manifest)
    elif audio_manifest_path is not None:
        candidate_path = Path(audio_manifest_path)
    elif (composition_dir.parent / "audio" / "audio_manifest.json").is_file():
        candidate_path = composition_dir.parent / "audio" / "audio_manifest.json"

    if manifest_data is None and candidate_path is not None and candidate_path.is_file():
        try:
            manifest_data = json.loads(candidate_path.read_text(encoding="utf-8"))
            manifest_source = str(candidate_path)
        except Exception:
            manifest_data = None

    if isinstance(manifest_data, dict) and isinstance(manifest_data.get("scenes"), list):
        per_scene: list[dict[str, Any]] = []
        ratios: list[float] = []
        for idx, sc in enumerate(manifest_data["scenes"]):
            if not isinstance(sc, dict):
                continue
            sc_idx = sc.get("scene_index", idx + 1)
            raw_ratio = sc.get("alignment_match_ratio")
            ratio_val = round(float(raw_ratio), 4) if raw_ratio is not None else None
            if ratio_val is not None:
                ratios.append(ratio_val)
            per_scene.append(
                {
                    "scene_index": sc_idx,
                    "alignment_match_ratio": ratio_val,
                }
            )
        if ratios or per_scene:
            return {
                "available": len(ratios) > 0,
                "source": manifest_source,
                "scene_count": len(per_scene),
                "avg_match_ratio": round(sum(ratios) / len(ratios), 4) if ratios else None,
                "min_match_ratio": round(min(ratios), 4) if ratios else None,
                "per_scene": per_scene,
            }

    compiled_align = compiled_meta.get("audio_alignment")
    if isinstance(compiled_align, dict) and compiled_align.get("per_scene"):
        return {
            "source": "storyboard_compiled.json",
            **compiled_align,
        }

    return {
        "available": False,
        "source": None,
        "scene_count": 0,
        "avg_match_ratio": None,
        "min_match_ratio": None,
        "per_scene": [],
    }


def run_v2_quality_gate(
    root: Path,
    *,
    composition_dir: Path,
    mp4_path: Path,
    thumbnail_jpg: Path,
    crop_2x3_jpg: Optional[Path] = None,
    master_wav_path: Optional[Path] = None,
    audio_manifest: Optional[dict[str, Any] | Path] = None,
    audio_manifest_path: Optional[Path] = None,
    report_output_path: Optional[Path] = None,
    final_qa_grid_path: Optional[Path] = None,
    final_qa_grid_safezones_path: Optional[Path] = None,
    cfg: Optional[dict[str, Any]] = None,
    no_craft: bool = False,
    run_hf_shorts_check: bool = True,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
) -> QualityGateReport:
    """Execute all 5 fail-closed QA gates; raises QualityGateError on any failure."""
    root = Path(root).resolve()
    composition_dir = Path(composition_dir).resolve()
    mp4_path = Path(mp4_path).resolve()
    thumbnail_jpg = Path(thumbnail_jpg).resolve()
    crop_path = (
        Path(crop_2x3_jpg).resolve()
        if crop_2x3_jpg
        else thumbnail_jpg.with_name(f"{thumbnail_jpg.stem}_2x3_crop.jpg")
    )
    resolved_cfg = cfg if cfg is not None else load_config(root)

    compiled_meta_path = composition_dir / "storyboard_compiled.json"
    if not compiled_meta_path.is_file():
        raise QualityGateError(f"Missing storyboard_compiled.json in {composition_dir}")
    compiled_meta = json.loads(compiled_meta_path.read_text(encoding="utf-8"))
    reject_synthetic_dom_snapshots(compiled_meta)

    ep_rt = compiled_meta.get("episode_runtime") or {}
    duration_sec = float(compiled_meta.get("duration_sec") or ep_rt.get("duration_sec") or 0.0)
    scenes = ep_rt.get("scenes") or []
    scene_ranges = [(float(sc["s0"]), float(sc["s1"])) for sc in scenes]
    failures: list[str] = []

    # 1. Geometry, grounding, live Chromium DOM & HyperFrames Shorts Check Gate
    grounding_errors = validate_storyboard_grounding(compiled_meta.get("grounding_report") or [])
    if grounding_errors:
        failures.extend(f"grounding: {e}" for e in grounding_errors)

    probe_res = run_chromium_runtime_probe(
        root,
        composition_dir / "index.html",
        duration_sec=duration_sec,
    )

    hf_check_res: dict[str, Any] = {"skipped": True}
    if run_hf_shorts_check:
        hf_check_res = run_hf_check(
            root,
            composition_dir,
            safe_zone="shorts",
            strict=True,
            no_craft=no_craft,
        )

    failures.extend(
        validate_runtime_probe_and_hf_check(
            probe_res,
            hf_check_res if run_hf_shorts_check else None,
            caption_safe_bottom_max=CAPTION_SAFE_BOTTOM_MAX,
            pill_min_x=SHORTS_PILL_MIN_X,
            pill_max_x=SHORTS_PILL_MAX_X,
            pill_min_y=SHORTS_PILL_MIN_Y,
            pill_max_y=SHORTS_PILL_MAX_Y,
        )
    )

    geometry_gate = {
        "grounding_entities": len(compiled_meta.get("grounding_report") or []),
        "grounding_tolerance_px": GROUND_TOLERANCE_PX,
        "chromium_probe": probe_res,
        "hyperframes_check": hf_check_res,
    }

    # 2. MP4 Stream & <= 55 MiB Bitrate Guardrail Gate
    mp4_gate: dict[str, Any] = {}
    try:
        mp4_gate = validate_mp4_contract(
            mp4_path,
            max_file_bytes=max_file_bytes,
            require_audio=True,
            expected_duration_sec=duration_sec,
        )
    except Exception as exc:
        failures.append(f"mp4 contract failed: {exc}")
        mp4_gate = {"error": str(exc)}

    # 3. Real Frame Motion, Final QA Grid, Measure Look & Dual-Profile KinoCut Gate
    grid_out = final_qa_grid_path or (mp4_path.parent / "final_qa_grid.jpg")
    motion_res = verify_per_scene_motion_and_grid(
        mp4_path,
        duration_sec,
        scene_ranges,
        final_qa_grid_path=grid_out,
        final_qa_grid_safezones_path=final_qa_grid_safezones_path,
    )
    if motion_res["black_frames"]:
        failures.append(f"dead black frames detected at t={motion_res['black_frames']}")
    if motion_res["frozen_scenes"]:
        failures.append(f"frozen/static scenes detected: {motion_res['frozen_scenes']}")

    hf_look = run_hf_measure_look(root, mp4_path)
    kc_summary, kc_failures = _evaluate_kinocut_checks(mp4_path, resolved_cfg)
    failures.extend(kc_failures)

    motion_and_look_gate = {
        "per_scene_motion": motion_res,
        "hyperframes_measure_look": hf_look,
        "kinocut": kc_summary,
    }

    # 4. Real Audio Gate (ebur128, true peak <= -1.5 dBTP, sample rate, quiet tail, silence drops, Whisper match ratios)
    audio_master_cfg = resolved_cfg.get("audio_mastering", {})
    target_lufs = float(audio_master_cfg.get("target_lufs", DEFAULT_TARGET_LUFS))
    lufs_tol = float(audio_master_cfg.get("lufs_tolerance", 0.5))
    max_tp = float(audio_master_cfg.get("true_peak_max_dbtp", DEFAULT_TRUE_PEAK_DBTP))

    wav_candidate = Path(master_wav_path) if master_wav_path else (composition_dir / "audio" / "master_mix.wav")
    if wav_candidate.is_file():
        wav_ebur = measure_loudness_ebur128(wav_candidate)
        if wav_ebur["true_peak_dbtp"] > max_tp:
            failures.append(
                f"master_mix.wav true_peak {wav_ebur['true_peak_dbtp']:.2f} dBTP > {max_tp:.2f} dBTP"
            )
    else:
        wav_ebur = None

    mp4_ebur = measure_loudness_ebur128(mp4_path)
    if abs(mp4_ebur["integrated_lufs"] - target_lufs) > lufs_tol:
        failures.append(
            f"MP4 integrated loudness {mp4_ebur['integrated_lufs']:.2f} LUFS outside {target_lufs} ± {lufs_tol}"
        )
    if mp4_ebur["true_peak_dbtp"] > max_tp:
        failures.append(
            f"MP4 true_peak {mp4_ebur['true_peak_dbtp']:.2f} dBTP > {max_tp:.2f} dBTP"
        )

    mp4_audio_stream = probe_audio_stream(mp4_path)
    if mp4_audio_stream["sample_rate"] != 48000 or mp4_audio_stream["channels"] != 2:
        failures.append(
            f"MP4 audio stream must be 48000 Hz stereo, got {mp4_audio_stream}"
        )

    silences = detect_silences(mp4_path, noise_db=-45.0, min_duration=1.5)
    # Reject unscheduled long silence drops inside active body (outside final tail)
    mid_silences = [s for s in silences if float(s["start"]) < max(0.0, duration_sec - 1.2)]
    if mid_silences:
        failures.append(f"unscheduled mid-episode silence drops >= 1.5s: {mid_silences}")

    tail_info = _check_tail_quietness(wav_candidate if wav_candidate.is_file() else None, mp4_path, duration_sec, tail_sec=0.7)
    if tail_info["tail_rms_dbfs"] > -16.0:
        failures.append(
            f"ending tail 0.7s RMS {tail_info['tail_rms_dbfs']} dBFS too loud (expected quiet outro <= -16.0 dBFS)"
        )

    whisper_alignment = _extract_whisper_alignment_summary(
        audio_manifest=audio_manifest,
        audio_manifest_path=audio_manifest_path,
        compiled_meta=compiled_meta,
        composition_dir=composition_dir,
    )

    audio_gate = {
        "master_wav_ebur128": wav_ebur,
        "mp4_ebur128": mp4_ebur,
        "mp4_audio_stream": mp4_audio_stream,
        "mid_episode_silences": mid_silences,
        "tail_check": tail_info,
        "whisper_alignment": whisper_alignment,
    }

    # 5. Thumbnail + 2:3 Shorts Center-Crop Gate
    thumb_gate: dict[str, Any] = {}
    try:
        t_val = validate_local_thumbnail(
            thumbnail_jpg,
            expected_size=(1080, 1920),
            max_bytes=2_097_152,
            min_stddev=4.0,
            allowed_formats=("JPEG",),
        )
        if int(t_val["bytes"]) < 10_240:
            raise QualityGateError(f"Thumbnail too small ({t_val['bytes']} < 10240 bytes)")
        if not crop_path.is_file():
            raise QualityGateError(f"Missing 2:3 Shorts verification crop: {crop_path}")
        with Image.open(crop_path) as cim:
            crop_size = cim.size
        expected_crop_size = (
            SHORTS_2X3_CROP_BOX[2] - SHORTS_2X3_CROP_BOX[0],
            SHORTS_2X3_CROP_BOX[3] - SHORTS_2X3_CROP_BOX[1],
        )
        if crop_size != expected_crop_size:
            raise QualityGateError(f"2:3 crop size must be {expected_crop_size}, got {crop_size}")
        thumb_gate = {**t_val, "crop_2x3_jpg": str(crop_path), "crop_2x3_size": list(crop_size)}
    except Exception as exc:
        failures.append(f"thumbnail gate failed: {exc}")
        thumb_gate = {"error": str(exc)}

    report = QualityGateReport(
        passed=(len(failures) == 0),
        failures=failures,
        geometry_gate=geometry_gate,
        mp4_gate=mp4_gate,
        motion_and_look_gate=motion_and_look_gate,
        audio_gate=audio_gate,
        thumbnail_gate=thumb_gate,
    )
    if report_output_path is not None:
        report_output_path = Path(report_output_path).resolve()
        write_text_atomic(report_output_path, json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        report.report_path = report_output_path

    if not report.passed:
        raise QualityGateError("Quality Gate FAILED:\n- " + "\n- ".join(failures))
    return report
