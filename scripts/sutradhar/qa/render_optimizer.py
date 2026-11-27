"""Bitrate-bounded 1080x1920@30fps H.264 MP4 renderer and <= 55 MiB guardrail."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional

from sutradhar.qa.hyperframes_runner import _extract_json_blob, find_hyperframes_cli

DEFAULT_MAX_FILE_BYTES = 57_671_680  # 55 MiB exact ceiling
DEFAULT_WIDTH = 1080
DEFAULT_HEIGHT = 1920
DEFAULT_FPS = 30
DEFAULT_AUDIO_BITRATE_KBPS = 192


class RenderOptimizeError(RuntimeError):
    """Raised when rendering, bitrate optimization, or MP4 contract validation fails."""


def probe_media(file_path: Path) -> dict[str, Any]:
    """Run ffprobe returning format metadata (size, bit_rate, duration) and stream specs."""
    file_path = Path(file_path)
    if not file_path.is_file():
        raise RenderOptimizeError(f"Media file not found for ffprobe: {file_path}")
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        (
            "format=size,bit_rate,duration:"
            "stream=width,height,r_frame_rate,avg_frame_rate,codec_type,codec_name,"
            "pix_fmt,sample_rate,channels,has_b_frames"
        ),
        "-of",
        "json",
        str(file_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RenderOptimizeError(f"ffprobe failed on '{file_path}': {proc.stderr.strip()}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RenderOptimizeError(f"Invalid ffprobe JSON for '{file_path}': {exc}") from exc


def _parse_fps(rate_str: str) -> float:
    if not rate_str or rate_str == "0/0":
        return 0.0
    if "/" in rate_str:
        num, den = rate_str.split("/", 1)
        den_f = float(den)
        return float(num) / den_f if den_f > 0 else 0.0
    return float(rate_str)


def compute_target_bitrate_kbps(
    duration_sec: float,
    *,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    audio_kbps: int = DEFAULT_AUDIO_BITRATE_KBPS,
    budget_fraction: float = 0.86,
) -> int:
    """Compute a deterministic max video bitrate leaving headroom below max_file_bytes."""
    dur = max(1.0, float(duration_sec))
    effective_bytes = float(max_file_bytes) * float(budget_fraction)
    total_kbps = (effective_bytes * 8.0) / dur / 1000.0
    video_kbps = int(total_kbps - float(audio_kbps))
    return max(1600, min(6200, video_kbps))


def validate_mp4_contract(
    mp4_path: Path,
    *,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    require_audio: bool = True,
    expected_duration_sec: Optional[float] = None,
    duration_tolerance_sec: float = 0.75,
) -> dict[str, Any]:
    """Fail-closed validation of MP4 size (<= 55 MiB), video (1080x1920@30fps yuv420p), and audio."""
    mp4_path = Path(mp4_path)
    if not mp4_path.is_file():
        raise RenderOptimizeError(f"Rendered MP4 does not exist: {mp4_path}")
    file_bytes = mp4_path.stat().st_size
    if file_bytes <= 0:
        raise RenderOptimizeError(f"Rendered MP4 is empty: {mp4_path}")
    if file_bytes > max_file_bytes:
        mb = file_bytes / (1024 * 1024)
        max_mb = max_file_bytes / (1024 * 1024)
        raise RenderOptimizeError(
            f"MP4 file size {file_bytes} bytes ({mb:.2f} MiB) exceeds {max_file_bytes} bytes "
            f"({max_mb:.2f} MiB) guardrail"
        )

    probe = probe_media(mp4_path)
    fmt = probe.get("format") or {}
    streams = probe.get("streams") or []
    duration = float(fmt.get("duration") or 0.0)
    if expected_duration_sec is not None and abs(duration - float(expected_duration_sec)) > duration_tolerance_sec:
        raise RenderOptimizeError(
            f"MP4 duration {duration:.3f}s diverges from expected {expected_duration_sec:.3f}s "
            f"(tolerance={duration_tolerance_sec}s)"
        )

    vstream = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not vstream:
        raise RenderOptimizeError(f"MP4 missing video stream: {mp4_path}")
    width = int(vstream.get("width") or 0)
    height = int(vstream.get("height") or 0)
    if (width, height) != (DEFAULT_WIDTH, DEFAULT_HEIGHT):
        raise RenderOptimizeError(
            f"MP4 video dimensions must be {DEFAULT_WIDTH}x{DEFAULT_HEIGHT}, got {width}x{height}"
        )
    if vstream.get("codec_name") != "h264":
        raise RenderOptimizeError(f"MP4 video codec must be h264, got {vstream.get('codec_name')!r}")
    if vstream.get("pix_fmt") != "yuv420p":
        raise RenderOptimizeError(f"MP4 pix_fmt must be yuv420p, got {vstream.get('pix_fmt')!r}")

    fps = _parse_fps(str(vstream.get("avg_frame_rate") or vstream.get("r_frame_rate") or "0"))
    if not (29.5 <= fps <= 30.5):
        raise RenderOptimizeError(f"MP4 frame rate must be ~30fps, got {fps:.3f}")

    astream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if require_audio:
        if not astream:
            raise RenderOptimizeError(f"MP4 missing required audio stream: {mp4_path}")
        if astream.get("codec_name") != "aac":
            raise RenderOptimizeError(f"MP4 audio codec must be aac, got {astream.get('codec_name')!r}")
        sr = int(astream.get("sample_rate") or 0)
        ch = int(astream.get("channels") or 0)
        if sr != 48000 or ch != 2:
            raise RenderOptimizeError(f"MP4 audio must be 48000 Hz stereo, got {sr} Hz {ch} ch")

    return {
        "file_bytes": file_bytes,
        "file_mib": round(file_bytes / (1024 * 1024), 3),
        "duration_sec": round(duration, 4),
        "bit_rate_bps": int(fmt.get("bit_rate") or 0),
        "width": width,
        "height": height,
        "fps": round(fps, 3),
        "video_codec": vstream.get("codec_name"),
        "pix_fmt": vstream.get("pix_fmt"),
        "has_b_frames": int(vstream.get("has_b_frames") or 0),
        "audio_codec": astream.get("codec_name") if astream else None,
        "sample_rate": int(astream.get("sample_rate") or 0) if astream else None,
        "channels": int(astream.get("channels") or 0) if astream else None,
    }


def optimize_mp4_bitrate(
    input_mp4: Path,
    output_mp4: Optional[Path] = None,
    *,
    duration_sec: Optional[float] = None,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    crf: int = 18,
    require_audio: bool = True,
) -> dict[str, Any]:
    """Re-encode an MP4 with deterministic H.264 CRF+VBV rate caps so size <= max_file_bytes."""
    input_mp4 = Path(input_mp4).resolve()
    target_mp4 = Path(output_mp4).resolve() if output_mp4 else input_mp4
    probe = probe_media(input_mp4)
    dur = float(duration_sec or (probe.get("format") or {}).get("duration") or 1.0)
    target_mp4.parent.mkdir(parents=True, exist_ok=True)

    attempts = [
        (crf, compute_target_bitrate_kbps(dur, max_file_bytes=max_file_bytes, budget_fraction=0.84)),
        (max(crf + 3, 21), compute_target_bitrate_kbps(dur, max_file_bytes=max_file_bytes, budget_fraction=0.72)),
    ]

    with tempfile.TemporaryDirectory(prefix="sutradhar_vbv_", ignore_cleanup_errors=True) as td:
        tmp_out = Path(td) / "optimized.mp4"
        for use_crf, kbps in attempts:
            cmd = [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(input_mp4),
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                str(use_crf),
                "-maxrate",
                f"{kbps}k",
                "-bufsize",
                f"{kbps * 2}k",
                "-pix_fmt",
                "yuv420p",
                "-colorspace",
                "bt709",
                "-color_primaries",
                "bt709",
                "-color_trc",
                "bt709",
                "-movflags",
                "+faststart",
                "-c:a",
                "copy",
                str(tmp_out),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if proc.returncode != 0:
                raise RenderOptimizeError(f"FFmpeg VBV pass failed: {proc.stderr.strip()}")
            if tmp_out.stat().st_size <= max_file_bytes:
                shutil.move(str(tmp_out), str(target_mp4))
                return validate_mp4_contract(
                    target_mp4,
                    max_file_bytes=max_file_bytes,
                    require_audio=require_audio,
                    expected_duration_sec=dur,
                )

    raise RenderOptimizeError(
        f"Unable to compress {input_mp4} below {max_file_bytes} bytes after VBV pass"
    )


def render_episode_mp4(
    root: Path,
    project_dir: Path,
    output_mp4: Path,
    *,
    duration_sec: float,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    quality: str = "standard",
    crf: int = 18,
    workers: int = 4,
    fps: int = DEFAULT_FPS,
    require_audio: bool = True,
    timeout_sec: int = 900,
) -> dict[str, Any]:
    """Render HyperFrames composition with calibrated VBV ceiling and fail-closed <= 55 MiB gate."""
    root = Path(root).resolve()
    project_dir = Path(project_dir).resolve()
    output_mp4 = Path(output_mp4).resolve()
    output_mp4.parent.mkdir(parents=True, exist_ok=True)

    node_exe, hf_cli = find_hyperframes_cli(root)
    target_kbps = compute_target_bitrate_kbps(duration_sec, max_file_bytes=max_file_bytes)

    cmd = [
        node_exe,
        str(hf_cli),
        "render",
        str(project_dir),
        "-o",
        str(output_mp4),
        "--fps",
        str(fps),
        "--quality",
        quality,
        "--crf",
        str(crf),
        "--max-bitrate",
        f"{target_kbps}k",
        "--buffer-size",
        f"{target_kbps * 2}k",
        "--workers",
        str(workers),
        "--no-browser-gpu",
        "--quiet",
        "--json",
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=timeout_sec,
        check=False,
    )
    if proc.returncode != 0 or not output_mp4.is_file():
        raise RenderOptimizeError(
            f"HyperFrames render failed (exit={proc.returncode}): {(proc.stderr or proc.stdout)[-800:]}"
        )

    render_meta = {}
    try:
        render_meta = _extract_json_blob(proc.stdout)
    except Exception:
        render_meta = {}

    if output_mp4.stat().st_size > max_file_bytes:
        metrics = optimize_mp4_bitrate(
            output_mp4,
            output_mp4,
            duration_sec=duration_sec,
            max_file_bytes=max_file_bytes,
            crf=crf,
            require_audio=require_audio,
        )
        metrics["vbv_reencoded"] = True
    else:
        metrics = validate_mp4_contract(
            output_mp4,
            max_file_bytes=max_file_bytes,
            require_audio=require_audio,
            expected_duration_sec=duration_sec,
        )
        metrics["vbv_reencoded"] = False

    metrics["target_max_video_kbps"] = target_kbps
    metrics["hyperframes_render"] = render_meta
    return metrics
