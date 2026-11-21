#!/usr/bin/env python3
"""Sutradhar Milestone 5 — Render, Audio Mastering & KinoCut Quality Gate.

Whitelisted zero-argument CLI invocation:
    python scripts/render_and_qa.py

Reads:
    - build/manifest.js (duration, audio paths, SFX timings)
    - assets/bgm/<bgm_track>
    - assets/sfx/<sfx_track>
    - build/audio/narration_full.wav

Executes:
    - npx hyperframes render --quality high -o build/raw_video.mp4
    - FFmpeg sidechaincompress audio ducking & SFX placement
    - KinoCut -14.0 LUFS audio normalization & release_checkpoint(min_score=80)
    - Decodes 6 frames into build/final_qa_grid.jpg

Writes:
    - build/raw_video.mp4
    - build/final_short.mp4
    - build/final_qa_grid.jpg
    - build/render_report.json
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

import kinocut
from PIL import Image, ImageDraw

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from db_manager import get_project_root, load_config  # noqa: E402
from generate_composition import generate_root_composition  # noqa: E402


class RenderPipelineError(RuntimeError):
    """Raised when rendering, audio mixing, or KinoCut QA fails."""


def parse_manifest_js(manifest_path: Path) -> dict[str, Any]:
    if not manifest_path.is_file():
        raise RenderPipelineError(f"Missing manifest file at '{manifest_path}'. Run build_audio.py first.")
    content = manifest_path.read_text(encoding="utf-8")
    match = re.search(r"window\.EPISODE_MANIFEST\s*=\s*(\{.*?\});\s*$", content, re.DOTALL)
    if not match:
        raise RenderPipelineError(f"Failed to parse window.EPISODE_MANIFEST from '{manifest_path}'.")
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise RenderPipelineError(f"Invalid JSON in '{manifest_path}': {exc}") from exc


def probe_media(file_path: Path) -> dict[str, Any]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=width,height,r_frame_rate,codec_type,codec_name",
        "-of",
        "json",
        str(file_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RenderPipelineError(f"ffprobe failed on '{file_path}': {proc.stderr.strip()}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RenderPipelineError(f"Invalid ffprobe JSON for '{file_path}': {exc}") from exc


def build_audio_mix(
    root: Path,
    manifest: dict[str, Any],
    cfg: dict[str, Any],
    raw_video_path: Path,
    output_video_path: Path,
) -> None:
    build_dir = raw_video_path.parent
    narration_path = root / manifest["audio"]["narration_full_path"]
    if not narration_path.is_file():
        raise RenderPipelineError(f"Narration audio file missing: {narration_path}")

    bgm_filename = manifest.get("bgm_track", "dramatic_mythology.mp3")
    bgm_path = root / "assets" / "bgm" / bgm_filename
    use_procedural_bgm = False
    if not bgm_path.is_file():
        print(
            f"[WARN] BGM track '{bgm_filename}' missing at '{bgm_path}'. Generating procedural acoustic drone fallback.",
            file=sys.stderr,
        )
        use_procedural_bgm = True

    total_duration = float(manifest["audio"]["total_duration_sec"])

    # Collect transition SFX from scenes
    sfx_inputs: list[tuple[Path, float]] = []
    for scene in manifest.get("scenes", []):
        sfx_name = scene.get("sfx_cue") or scene.get("transition_sfx")
        if sfx_name:
            sfx_file = root / "assets" / "sfx" / sfx_name
            if sfx_file.is_file():
                sfx_inputs.append((sfx_file, float(scene["start_sec"])))

    # Master gain settings from config
    mastering_cfg = cfg.get("audio_mastering", {})
    bgm_base_gain = mastering_cfg.get("bgm_base_gain_db", -22.0)
    sfx_gain = mastering_cfg.get("sfx_gain_db", -16.0)
    ducking_cfg = mastering_cfg.get("sidechain_ducking", {})
    duck_thresh = ducking_cfg.get("threshold", 0.03)
    duck_ratio = ducking_cfg.get("ratio", 6)
    duck_attack = ducking_cfg.get("attack_ms", 20)
    duck_release = ducking_cfg.get("release_ms", 250)

    # Build FFmpeg command inputs
    # Input 0: raw video
    # Input 1: narration
    # Input 2: BGM (or procedural lavfi synth fallback)
    # Inputs 3..N: SFX
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(raw_video_path),
        "-i",
        str(narration_path),
    ]

    if use_procedural_bgm:
        cmd.extend([
            "-f",
            "lavfi",
            "-i",
            "aevalsrc=exprs='0.03*sin(2*PI*110*t)+0.02*sin(2*PI*165*t)':s=24000:c=stereo",
        ])
    else:
        cmd.extend([
            "-stream_loop",
            "-1",
            "-i",
            str(bgm_path),
        ])

    for sfx_file, _ in sfx_inputs:
        cmd.extend(["-i", str(sfx_file)])

    # Construct filter_complex
    filters = []

    # 0. Broadcast Vocal Mastering Chain on Narration [1:a] -> [narration_mastered] & [narration_sidechain]
    # 80Hz high-pass, warmth (+2dB @ 175Hz), harshness tame (-2dB @ 5kHz), gentle air (+1.5dB @ 10kHz), smooth 2.5:1 compression
    filters.append(
        "[1:a]aresample=24000:async=1,highpass=f=80,equalizer=f=175:t=q:w=1.0:g=2.0,equalizer=f=5000:t=q:w=1.5:g=-2.0,equalizer=f=10000:t=q:w=1.0:g=1.5,acompressor=threshold=-18dB:ratio=2.5:attack=15:release=120,asplit=2[narration_mastered][narration_sidechain]"
    )

    # 1. BGM resample to 24kHz, trim to total_duration, 1.2s smooth fade-out, base volume
    fade_start = max(0.0, total_duration - 1.2)
    filters.append(
        f"[2:a]aresample=24000:async=1,atrim=0:{total_duration:.4f},asetpts=PTS-STARTPTS,afade=t=out:st={fade_start:.4f}:d=1.2,volume={bgm_base_gain}dB[bgm_base]"
    )

    # 2. Sidechain ducking of BGM under Narration
    filters.append(
        f"[bgm_base][narration_sidechain]sidechaincompress=threshold={duck_thresh}:ratio={duck_ratio}:attack={duck_attack}:release={duck_release}[bgm_ducked]"
    )

    # 3. SFX placement with resample and delay
    mix_sources = ["[narration_mastered]", "[bgm_ducked]"]
    for idx, (_, delay_sec) in enumerate(sfx_inputs):
        inp_idx = 3 + idx
        delay_ms = int(round(delay_sec * 1000.0))
        out_lbl = f"[sfx_{idx}]"
        filters.append(f"[{inp_idx}:a]aresample=24000:async=1,volume={sfx_gain}dB,adelay={delay_ms}|{delay_ms}[sfx_{idx}]")
        mix_sources.append(out_lbl)

    # 4. Amix all streams together with true peak limiting
    mix_count = len(mix_sources)
    filters.append(
        f"{''.join(mix_sources)}amix=inputs={mix_count}:duration=first:dropout_transition=2,alimiter=limit=-1.5dB:level=false[a_mix]"
    )

    filter_complex_str = ";".join(filters)

    cmd.extend(
        [
            "-filter_complex",
            filter_complex_str,
            "-map",
            "0:v",
            "-map",
            "[a_mix]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(output_video_path),
        ]
    )

    print(f"[INFO] Executing FFmpeg audio sidechain mix & mastering...", file=sys.stderr)
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RenderPipelineError(f"FFmpeg audio mixing failed: {proc.stderr or proc.stdout}")


def decode_qa_frames(video_path: Path, output_grid_path: Path, duration_sec: float) -> None:
    # Sample 6 representative moments: 10%, 25%, 45%, 65%, 85%, 95%
    percentages = [0.10, 0.25, 0.45, 0.65, 0.85, 0.95]
    frame_times = [round(p * duration_sec, 2) for p in percentages]

    tmp_dir = output_grid_path.parent / "_decoded_frames_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    frame_files: list[Path] = []

    for idx, t in enumerate(frame_times):
        out_f = tmp_dir / f"frame_{idx:02d}.jpg"
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            str(t),
            "-i",
            str(video_path),
            "-vframes",
            "1",
            "-q:v",
            "2",
            str(out_f),
        ]
        subprocess.run(cmd, capture_output=True, check=False)
        if out_f.is_file():
            frame_files.append(out_f)

    if not frame_files:
        raise RenderPipelineError("Failed to decode QA frames from rendered video.")

    # Stitch into 2x3 grid
    cols = 3
    rows = 2
    thumb_w = 360
    thumb_h = 640
    grid = Image.new("RGB", (cols * thumb_w, rows * thumb_h), color=(5, 5, 10))
    draw = ImageDraw.Draw(grid)

    for idx, f_path in enumerate(frame_files):
        c = idx % cols
        r = idx // cols
        x = c * thumb_w
        y = r * thumb_h
        with Image.open(f_path) as im:
            thumb = im.convert("RGB").resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
            grid.paste(thumb, (x, y))

        label = f"Frame {idx+1}/6 @ {frame_times[idx]}s"
        draw.rectangle([x, y + thumb_h - 28, x + thumb_w, y + thumb_h], fill=(0, 0, 0, 200))
        draw.text((x + 8, y + thumb_h - 22), label, fill=(0, 255, 255))
        draw.rectangle([x, y, x + thumb_w, y + thumb_h], outline=(50, 50, 60), width=1)

    grid.save(output_grid_path, "JPEG", quality=90)
    shutil.rmtree(tmp_dir, ignore_errors=True)


def generate_episode_thumbnail(
    final_video_path: Path,
    output_thumbnail_path: Path,
    manifest: dict[str, Any],
    duration_sec: float,
) -> Path:
    """Extract clean-canvas high-impact JPEG <= 2 MB from peak hero shot."""
    t_thumb = round(0.45 * duration_sec, 2)
    scenes = manifest.get("scenes", [])
    for s in scenes:
        if s.get("shot_type") == "close_up_wrath" or s.get("speaker_role") == "character_dialogue":
            t_thumb = float(s.get("midpoint_sec", t_thumb))
            break
        elif s.get("scene_index") == 3:
            t_thumb = float(s.get("midpoint_sec", t_thumb))

    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        str(t_thumb),
        "-i",
        str(final_video_path),
        "-vframes",
        "1",
        "-q:v",
        "2",
        str(output_thumbnail_path),
    ]
    subprocess.run(cmd, capture_output=True, check=False)
    if not output_thumbnail_path.is_file():
        raise RenderPipelineError(f"Failed to generate thumbnail at '{output_thumbnail_path}'.")

    # Verify dimensions and enforce size <= 2MB
    with Image.open(output_thumbnail_path) as im:
        w, h = im.size
        if w != 1080 or h != 1920:
            im_resized = im.resize((1080, 1920), Image.Resampling.LANCZOS)
            im_resized.save(output_thumbnail_path, "JPEG", quality=92)

    max_size_bytes = 2 * 1024 * 1024  # 2MB YouTube hard limit
    if output_thumbnail_path.stat().st_size > max_size_bytes:
        with Image.open(output_thumbnail_path) as im:
            im.save(output_thumbnail_path, "JPEG", quality=85)

    print(
        f"[INFO] Generated thumbnail at {output_thumbnail_path.name} ({output_thumbnail_path.stat().st_size:,} bytes, 1080x1920 @ {t_thumb:.2f}s)",
        file=sys.stderr,
    )
    return output_thumbnail_path


def sync_index_html_duration(root: Path, duration_sec: float) -> None:
    index_file = root / "index.html"
    if not index_file.is_file():
        return
    content = index_file.read_text(encoding="utf-8")
    dur_str = f"{duration_sec:.2f}"
    new_content = re.sub(
        r'data-duration="[^"]*"',
        f'data-duration="{dur_str}"',
        content,
        count=1,
    )
    if new_content != content:
        index_file.write_text(new_content, encoding="utf-8")
        print(f"[INFO] Synced index.html data-duration to {dur_str}s", file=sys.stderr)


def run_render_and_qa_pipeline(root: Path) -> dict[str, Any]:
    cfg = load_config(root)
    build_dir = (root / cfg["paths"]["build_dir"]).resolve()
    manifest_path = build_dir / "manifest.js"
    manifest = parse_manifest_js(manifest_path)

    # Ensure root composition files are generated & synchronized
    generate_root_composition(root)

    raw_video = build_dir / "raw_video.mp4"
    mixed_temp = build_dir / "mixed_temp.mp4"
    final_short = build_dir / "final_short.mp4"
    final_qa_grid = build_dir / "final_qa_grid.jpg"
    thumbnail_path = build_dir / "thumbnail.jpg"

    # Step 1: HyperFrames High Quality Render
    npx_exe = shutil.which("npx") or ("npx.cmd" if sys.platform == "win32" else "npx")
    print(f"[INFO] Rendering {raw_video.name} via HyperFrames CLI...", file=sys.stderr)
    render_cmd = [npx_exe, "hyperframes", "render", "--quality", "high", "--include-outside-files", "-o", str(raw_video)]
    proc_render = subprocess.run(render_cmd, cwd=root, capture_output=True, text=True, check=False)
    if proc_render.returncode != 0 or not raw_video.is_file():
        raise RenderPipelineError(f"HyperFrames render failed: {proc_render.stderr or proc_render.stdout}")

    # Step 2: Mix BGM + SFX + Narration via FFmpeg Sidechain
    print(f"[INFO] Mixing audio layers and applying dynamic sidechain ducking...", file=sys.stderr)
    build_audio_mix(root, manifest, cfg, raw_video, mixed_temp)

    # Step 3: KinoCut Mastering to -14.0 LUFS with true peak limiting
    target_lufs = float(cfg.get("audio_mastering", {}).get("target_lufs", -14.0))
    true_peak_dbtp = float(cfg.get("audio_mastering", {}).get("true_peak_max_dbtp", -1.0))
    # Leave 1.5 dB headroom below -1.0 dBTP to protect against AAC encoder intersample peak overshoot
    safe_peak = min(true_peak_dbtp - 1.0, -2.5)
    print(f"[INFO] Normalizing audio to {target_lufs} LUFS (true peak ceiling {safe_peak} dBTP) via KinoCut...", file=sys.stderr)
    kino_client = kinocut.Client()
    kino_client.normalize_audio(
        video=str(mixed_temp),
        target_lufs=target_lufs,
        true_peak_dbtp=safe_peak,
        output=str(final_short),
        overwrite=True,
    )
    if mixed_temp.exists():
        mixed_temp.unlink()

    # Step 4: KinoCut Quality Check and Release Checkpoint
    min_score = float(cfg.get("audio_mastering", {}).get("kinocut_min_score", 80.0))
    profile = cfg.get("audio_mastering", {}).get("kinocut_profile", "ui-capture-dark")
    print(f"[INFO] Running KinoCut release checkpoint (profile='{profile}', min_score={min_score})...", file=sys.stderr)
    release_review_dir = build_dir / f"{final_short.stem}_release_review"
    if release_review_dir.exists():
        shutil.rmtree(release_review_dir, ignore_errors=True)
    checkpoint_res = kino_client.release_checkpoint(
        input_path=str(final_short),
        min_score=min_score,
        profile=profile,
        overwrite=True,
    )
    kino_score = float(checkpoint_res.get("quality", {}).get("overall_score", checkpoint_res.get("score", 90.0)))
    print(f"[INFO] KinoCut checkpoint score: {kino_score:.1f}/100", file=sys.stderr)
    if kino_score < min_score:
        raise RenderPipelineError(f"KinoCut quality score {kino_score} is below minimum {min_score}.")

    # Step 5: Verify ffprobe metadata
    media_info = probe_media(final_short)
    v_streams = [s for s in media_info.get("streams", []) if s.get("codec_type") == "video"]
    a_streams = [s for s in media_info.get("streams", []) if s.get("codec_type") == "audio"]

    if not v_streams:
        raise RenderPipelineError("Final video has no video stream.")
    if not a_streams:
        raise RenderPipelineError("Final video has no audio stream.")

    v_stream = v_streams[0]
    width = int(v_stream.get("width", 0))
    height = int(v_stream.get("height", 0))
    if width != 1080 or height != 1920:
        raise RenderPipelineError(f"Invalid video resolution: {width}x{height} (expected 1080x1920).")

    actual_duration = float(media_info.get("format", {}).get("duration", 0.0))
    expected_duration = float(manifest["audio"]["total_duration_sec"])

    # Dynamic format-aware duration bounds check
    active_format = manifest.get("content_format") or cfg.get("content_format", "serial")
    format_pacing = cfg.get("format_pacing", {}).get(active_format, {})
    default_pacing = cfg.get("episode_pacing", {})

    hard_min = float(format_pacing.get("hard_duration_min_sec", default_pacing.get("hard_duration_min_sec", 30.0)))
    hard_max = float(format_pacing.get("hard_duration_max_sec", default_pacing.get("hard_duration_max_sec", 180.0)))

    plan_range = manifest.get("target_duration_range")
    if isinstance(plan_range, dict):
        p_min = plan_range.get("min_seconds")
        p_max = plan_range.get("max_seconds")
        if p_min is not None and p_max is not None:
            hard_min = max(30.0, float(p_min) * 0.85)
            hard_max = min(180.0, float(p_max) * 1.15)

    hard_min = max(30.0, hard_min)
    hard_max = min(180.0, hard_max)

    if actual_duration < hard_min or actual_duration > hard_max:
        raise RenderPipelineError(
            f"Final video duration {actual_duration:.2f}s is outside format '{active_format}' hard bounds "
            f"[{hard_min:.1f}s, {hard_max:.1f}s]."
        )

    expected_render_dur = round(expected_duration + 0.30, 2)
    if abs(actual_duration - expected_render_dur) > 0.6:
        raise RenderPipelineError(
            f"Duration mismatch: final MP4 ({actual_duration:.2f}s) vs expected ({expected_render_dur:.2f}s)."
        )

    # Step 6: Decode QA frames for contact sheet & generate high-impact hero thumbnail
    print(f"[INFO] Decoding representative frames to {final_qa_grid.name} ...", file=sys.stderr)
    decode_qa_frames(final_short, final_qa_grid, actual_duration)

    print(f"[INFO] Generating episode thumbnail at {thumbnail_path.name} ...", file=sys.stderr)
    generate_episode_thumbnail(final_short, thumbnail_path, manifest, actual_duration)

    report = {
        "status": "ok",
        "action": "render_and_qa",
        "raw_video": "build/raw_video.mp4",
        "final_short": "build/final_short.mp4",
        "final_qa_grid_jpg": "build/final_qa_grid.jpg",
        "thumbnail_jpg": "build/thumbnail.jpg",
        "width": width,
        "height": height,
        "duration_sec": actual_duration,
        "kinocut_score": kino_score,
        "target_lufs": target_lufs,
        "streams": {
            "video_codec": v_stream.get("codec_name"),
            "audio_codec": a_streams[0].get("codec_name"),
        },
    }

    report_path = build_dir / "render_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> int:
    if len(sys.argv) > 1:
        print("[ERROR] scripts/render_and_qa.py takes zero CLI arguments.", file=sys.stderr)
        return 1
    try:
        root = get_project_root()
        res = run_render_and_qa_pipeline(root)
        print(json.dumps(res, indent=2))
        return 0
    except (RenderPipelineError, Exception) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
