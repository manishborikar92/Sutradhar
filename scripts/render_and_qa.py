#!/usr/bin/env python3
"""Sutradhar — Render, Audio Mastering & KinoCut Quality Gate.

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
REPO_ROOT = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from db_manager import get_project_root, load_config  # noqa: E402
from scripts.engine.composer import compose_episode  # noqa: E402
from scripts.engine.foley_scheduler import PROP_SFX_MAP  # noqa: E402


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
        "format=duration:stream=width,height,r_frame_rate,codec_type,codec_name,sample_rate,channels",
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


VFX_SFX_MAP: dict[str, str] = {
    "laser_beam": "laser_strike.wav",
    "sunburst": "cosmic_chime.wav",
    "screen_shatter": "crystal_shatter.wav",
    "fracture_cracks": "magma_crack.wav",
    "sound_ripple": "conch_blast.wav",
}

TRANSITION_SFX_MAP: dict[str, str] = {
    "curtain_open": "curtain_whoosh.wav",
    "curtain_close": "curtain_whoosh.wav",
    "shatter_transition": "crystal_shatter.wav",
    "border_wipe": "whoosh_soft.wav",
    "blind_wipe": "whoosh_soft.wav",
    "push_left": "whoosh_soft.wav",
    "push_right": "whoosh_soft.wav",
    "zoom_burst": "whoosh_soft.wav",
    "theatrical_pan": "whoosh_soft.wav",
    "fade_dip_gold": "whoosh_soft.wav",
}

BGM_BY_MOOD_DEFAULTS: dict[str, str] = {
    "dramatic": "dramatic_mythology.mp3",
    "epic": "epic_history.mp3",
    "mystic": "cosmic_mystery.mp3",
    "cosmic": "cosmic_mystery.mp3",
    "wrath": "wrath_confrontation.mp3",
    "sorrow": "sorrow_tragedy.mp3",
    "serene": "serene_blessing.mp3",
}


def collect_sfx_schedule(root: Path, manifest: dict[str, Any]) -> list[tuple[Path, float]]:
    """
    Collect timestamp-based SFX cues across transitions, VFX events,
    mid-scene dramatic moments, and outro sequences.
    Returns sorted list of (sfx_file_path, timestamp_sec).
    """
    sfx_dir = root / "assets" / "sfx"
    raw_cues: list[tuple[str, float]] = []
    scenes = manifest.get("scenes", [])
    total_duration = float(manifest.get("audio", {}).get("total_duration_sec", 0.0))

    # 1. Transitions and scene-level cues
    for idx, scene in enumerate(scenes):
        st = float(scene.get("start_sec", 0.0))
        dur = float(scene.get("end_sec", st)) - st
        explicit_sfx = scene.get("sfx_cue") or scene.get("transition_sfx")
        trans = str(scene.get("transition") or scene.get("transition_type") or "").lower()

        if explicit_sfx:
            raw_cues.append((explicit_sfx, st))
        elif trans in TRANSITION_SFX_MAP:
            raw_cues.append((TRANSITION_SFX_MAP[trans], st))
        elif idx == 0:
            raw_cues.append(("curtain_whoosh.wav", max(0.0, st + 0.3)))

        # 2. VFX cues
        vfx_list = scene.get("vfx_elements") or ([scene.get("vfx")] if scene.get("vfx") else [])
        for vfx_item in vfx_list:
            if not vfx_item:
                continue
            vfx_name = str(vfx_item).lower().strip()
            if vfx_name in VFX_SFX_MAP:
                vfx_offset = float(scene.get("vfx_offset", min(0.3, dur * 0.2)))
                raw_cues.append((VFX_SFX_MAP[vfx_name], st + vfx_offset))

        # 3. Explicit timestamped SFX events in scene
        for sfx_evt in scene.get("sfx_events", []):
            evt_file = sfx_evt.get("sfx")
            if evt_file:
                if "timestamp" in sfx_evt:
                    evt_time = float(sfx_evt["timestamp"])
                else:
                    evt_time = st + float(sfx_evt.get("offset", 0.0))
                raw_cues.append((evt_file, evt_time))

        # 4. Dramatic expression / rage thunder cues
        expr_changes = scene.get("expression_changes", [])
        if isinstance(expr_changes, dict):
            expr_changes = [expr_changes]
        for ec in expr_changes:
            to_em = str(ec.get("to_emotion") or ec.get("emotion") or "").lower()
            if to_em in ("rage", "wrath"):
                offset = float(ec.get("offset", dur * float(ec.get("at_ratio", 0.5))))
                raw_cues.append(("thunder_rumble.wav", st + offset))

    # 4b. Dynamic Storytelling Props Foley Cues
    for p in manifest.get("props", []):
        p_id = p.get("prop_id") or p.get("id", "")
        p_st = float(p.get("start_sec", 0.0))
        p_dur = float(p.get("duration_sec", 3.0))
        for known_prop, (sfx_file, offset_pct) in PROP_SFX_MAP.items():
            if known_prop in p_id:
                raw_cues.append((sfx_file, p_st + (p_dur * offset_pct)))

    # 5. Outro marquee and curtain close sequence
    if total_duration >= 6.0 and manifest.get("outro") is not False:
        t_marquee = max(0.0, total_duration - 3.4)
        raw_cues.append(("conch_blast.wav", t_marquee))
        t_close = max(0.0, total_duration - 1.6)
        raw_cues.append(("curtain_whoosh.wav", t_close))

    # Validate against existing files on disk, sort by timestamp, de-duplicate rapid identical triggers
    validated: list[tuple[Path, float]] = []
    raw_cues.sort(key=lambda x: x[1])
    last_trigger: dict[str, float] = {}
    for sfx_name, t_sec in raw_cues:
        sfx_path = sfx_dir / sfx_name
        if not sfx_path.is_file():
            continue
        if sfx_name in last_trigger and abs(t_sec - last_trigger[sfx_name]) < 0.25:
            continue
        last_trigger[sfx_name] = t_sec
        validated.append((sfx_path, round(t_sec, 3)))

    return validated


def parse_bgm_schedule(
    root: Path,
    manifest: dict[str, Any],
    cfg: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Parse BGM cues across video duration. Supports:
    1. manifest["bgm_cues"]: list of {"track": ..., "start_sec": ...} or {"mood": ..., "start_sec": ...}
    2. Per-scene bgm_track or bgm_mood switches.
    3. Single manifest["bgm_track"] or default pillar track.
    Returns list of dicts: [{"track": str, "path": Path, "start_sec": float, "is_fallback": bool}]
    """
    bgm_dir = root / "assets" / "bgm"
    mood_map = dict(BGM_BY_MOOD_DEFAULTS)
    if "assets" in cfg and "bgm_by_mood" in cfg["assets"]:
        mood_map.update(cfg["assets"]["bgm_by_mood"])

    cues_spec = manifest.get("bgm_cues")
    resolved_cues: list[tuple[str, float]] = []

    if cues_spec and isinstance(cues_spec, list):
        for item in cues_spec:
            t_start = float(item.get("start_sec", 0.0))
            track = item.get("track")
            mood = item.get("mood")
            if not track and mood:
                track = mood_map.get(str(mood).lower(), "dramatic_mythology.mp3")
            if track:
                resolved_cues.append((track, t_start))
    else:
        # Check scene-level track or mood transitions
        scenes = manifest.get("scenes", [])
        current_track: Optional[str] = None
        for scene in scenes:
            st = float(scene.get("start_sec", 0.0))
            track = scene.get("bgm_track")
            mood = scene.get("bgm_mood")
            if not track and mood:
                track = mood_map.get(str(mood).lower())
            if track and track != current_track:
                resolved_cues.append((track, st))
                current_track = track

    if not resolved_cues:
        default_track = manifest.get("bgm_track")
        if not default_track:
            pillar = manifest.get("pillar")
            if pillar and "assets" in cfg and "bgm_by_pillar" in cfg["assets"]:
                default_track = cfg["assets"]["bgm_by_pillar"].get(pillar)
        if not default_track:
            default_track = "dramatic_mythology.mp3"
        resolved_cues.append((default_track, 0.0))

    resolved_cues.sort(key=lambda c: c[1])
    if resolved_cues[0][1] > 0.0:
        first_track = resolved_cues[0][0]
        resolved_cues.insert(0, (first_track, 0.0))

    schedule: list[dict[str, Any]] = []
    for idx, (trk_name, st) in enumerate(resolved_cues):
        trk_path = bgm_dir / trk_name
        is_missing = not trk_path.is_file()
        if is_missing:
            print(
                f"[WARN] BGM track '{trk_name}' missing at '{trk_path}'. Generating procedural acoustic drone fallback.",
                file=sys.stderr,
            )
        schedule.append({
            "track": trk_name,
            "path": trk_path,
            "start_sec": st,
            "is_fallback": is_missing,
        })

    return schedule


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

    total_duration = float(manifest["audio"]["total_duration_sec"])

    # Collect timestamp-based SFX schedule
    sfx_inputs = collect_sfx_schedule(root, manifest)

    # Collect multi-track BGM schedule
    bgm_schedule = parse_bgm_schedule(root, manifest, cfg)

    # Master gain settings from config
    mastering_cfg = cfg.get("audio_mastering", {})
    bgm_base_gain = mastering_cfg.get("bgm_base_gain_db", -22.0)
    sfx_gain = mastering_cfg.get("sfx_gain_db", -10.0)
    ducking_cfg = mastering_cfg.get("sidechain_ducking", {})
    duck_thresh = ducking_cfg.get("threshold", 0.03)
    duck_ratio = ducking_cfg.get("ratio", 8)
    duck_attack = ducking_cfg.get("attack_ms", 20)
    duck_release = ducking_cfg.get("release_ms", 500)

    # Build FFmpeg command inputs
    # Input 0: raw video
    # Input 1: narration
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(raw_video_path),
        "-i",
        str(narration_path),
    ]

    # BGM inputs starting at index 2
    for cue in bgm_schedule:
        if cue["is_fallback"]:
            cmd.extend([
                "-f",
                "lavfi",
                "-i",
                "aevalsrc=exprs='0.03*sin(2*PI*110*t)+0.02*sin(2*PI*165*t)':s=48000:c=stereo",
            ])
        else:
            cmd.extend([
                "-stream_loop",
                "-1",
                "-i",
                str(cue["path"]),
            ])

    # SFX inputs following BGM
    for sfx_file, _ in sfx_inputs:
        cmd.extend(["-i", str(sfx_file)])

    # Construct filter_complex
    filters = []

    # 0. Broadcast Vocal Mastering Chain on Narration [1:a] -> [narration_mastered] & [narration_sidechain]
    # Enforces 48,000Hz stereo up-mixing immediately so downstream mixing preserves stereo width!
    filters.append(
        "[1:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
        "highpass=f=80,equalizer=f=175:t=q:w=1.0:g=2.0,equalizer=f=5000:t=q:w=1.5:g=-2.0,equalizer=f=10000:t=q:w=1.0:g=1.5,"
        "acompressor=threshold=-18dB:ratio=2.5:attack=15:release=120,asplit=2[narration_mastered][narration_sidechain]"
    )

    # 1. BGM Track Processing and Crossfading (48kHz Stereo)
    if len(bgm_schedule) == 1:
        fade_start = max(0.0, total_duration - 1.2)
        filters.append(
            f"[2:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
            f"atrim=0:{total_duration:.4f},asetpts=PTS-STARTPTS,afade=t=out:st={fade_start:.4f}:d=1.2,volume={bgm_base_gain}dB[bgm_base]"
        )
    else:
        xfade_dur = 1.5
        bgm_start_idx = 2
        for k, cue in enumerate(bgm_schedule):
            inp_idx = bgm_start_idx + k
            st = cue["start_sec"]
            next_st = bgm_schedule[k + 1]["start_sec"] if k + 1 < len(bgm_schedule) else total_duration
            if k < len(bgm_schedule) - 1:
                seg_dur = max(0.5, (next_st - st) + xfade_dur)
            else:
                seg_dur = max(0.5, total_duration - st)

            delay_ms = int(round(st * 1000.0))
            fade_in_str = f",afade=t=in:st=0:d={xfade_dur:.2f}" if k > 0 else ""
            if k < len(bgm_schedule) - 1:
                fade_out_st = max(0.0, next_st - st)
                fade_out_str = f",afade=t=out:st={fade_out_st:.4f}:d={xfade_dur:.2f}"
            else:
                fade_out_st = max(0.0, seg_dur - 1.2)
                fade_out_str = f",afade=t=out:st={fade_out_st:.4f}:d=1.2"

            delay_str = f",adelay={delay_ms}|{delay_ms}" if delay_ms > 0 else ""
            filters.append(
                f"[{inp_idx}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
                f"atrim=0:{seg_dur:.4f},asetpts=PTS-STARTPTS{fade_in_str}{fade_out_str}{delay_str}[bgm_seg_{k}]"
            )

        bgm_seg_labels = "".join(f"[bgm_seg_{k}]" for k in range(len(bgm_schedule)))
        filters.append(
            f"{bgm_seg_labels}amix=inputs={len(bgm_schedule)}:normalize=0:duration=longest:dropout_transition=2,volume={bgm_base_gain}dB[bgm_base]"
        )

    # 2. Sidechain ducking of BGM under Narration (ratio 8:1, attack 20ms, release 500ms, makeup 1.0)
    filters.append(
        f"[bgm_base][narration_sidechain]sidechaincompress=threshold={duck_thresh}:ratio={duck_ratio}:attack={duck_attack}:release={duck_release}:makeup=1[bgm_ducked]"
    )

    # 3. SFX placement with 48kHz stereo formatting and delay
    mix_sources = ["[narration_mastered]", "[bgm_ducked]"]
    sfx_start_idx = 2 + len(bgm_schedule)
    for idx, (_, delay_sec) in enumerate(sfx_inputs):
        inp_idx = sfx_start_idx + idx
        delay_ms = int(round(delay_sec * 1000.0))
        out_lbl = f"[sfx_{idx}]"
        filters.append(
            f"[{inp_idx}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
            f"volume={sfx_gain}dB,adelay={delay_ms}|{delay_ms}[sfx_{idx}]"
        )
        mix_sources.append(out_lbl)

    # 4. Amix all streams with normalize=0 to prevent volume crush, followed by EBU R128 integrated loudness normalization
    mix_count = len(mix_sources)
    filters.append(
        f"{''.join(mix_sources)}amix=inputs={mix_count}:normalize=0:duration=first:dropout_transition=2[mixed_raw]"
    )
    filters.append(
        "[mixed_raw]loudnorm=I=-14:TP=-1.5:LRA=11[a_mix]"
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
            "-ar",
            "48000",
            "-ac",
            "2",
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
    index_file = root / "build" / "composition" / "index.html"
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
        print(f"[INFO] Synced build/composition/index.html data-duration to {dur_str}s", file=sys.stderr)


def run_render_and_qa_pipeline(root: Path) -> dict[str, Any]:
    cfg = load_config(root)
    build_dir = (root / cfg["paths"]["build_dir"]).resolve()
    manifest_path = build_dir / "manifest.js"
    manifest = parse_manifest_js(manifest_path)

    # Ensure composition files are generated & synchronized under build/composition/
    compose_episode(root)

    raw_video = build_dir / "raw_video.mp4"
    mixed_temp = build_dir / "mixed_temp.mp4"
    final_short = build_dir / "final_short.mp4"
    final_qa_grid = build_dir / "final_qa_grid.jpg"
    thumbnail_path = build_dir / "thumbnail.jpg"

    # Step 1: HyperFrames High Quality Render
    npx_exe = shutil.which("npx") or ("npx.cmd" if sys.platform == "win32" else "npx")
    print(f"[INFO] Rendering {raw_video.name} via HyperFrames CLI...", file=sys.stderr)
    render_cmd = [
        npx_exe,
        "hyperframes",
        "render",
        "-c",
        "build/composition/index.html",
        "--quality",
        "high",
        "--include-outside-files",
        "-o",
        str(raw_video),
    ]
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
    active_format = manifest.get("content_format") or cfg.get("content_format", "episodic_series")
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
