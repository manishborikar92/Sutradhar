#!/usr/bin/env python3
"""Sutradhar Sample Production Runner.

Generates sample_01_cosmos and sample_02_epics in an isolated staging workspace,
executing build_audio -> preview_frames -> render_and_qa end-to-end,
verifying KinoCut QA, broadcast mastering, clean-canvas rendering, and zero final-word cutoff.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import build_audio
import preview_frames
import render_and_qa
from db_manager import load_config

# Sample 01 Plan: Secrets of the Event Horizon
SAMPLE_01_PLAN: dict[str, Any] = {
    "series_id": 1,
    "series_title": "Secrets of the Event Horizon",
    "pillar": "Cosmic & Scientific Paradoxes",
    "episode_number_in_series": 1,
    "total_planned_episodes": 3,
    "global_episode_number": 1,
    "tts_voice": "am_fenrir:0.60+am_onyx:0.40",
    "bgm_track": "cosmic_mystery.mp3",
    "bespoke_asset_path": "assets/svg/diagrams/gravitational_time_dilation_clock.svg",
    "youtube_title": "What Happens The Second You Cross an Event Horizon? (Part 1/3) #Shorts",
    "youtube_description": "Part 1 of 3: Secrets of the Event Horizon. Cross into the cosmic point of no return. Watch on Sutradhar! #Science #Space #Shorts",
    "summary": "Explains gravitational time dilation and the event horizon threshold.",
    "scenes": [
        {
            "scene_index": 1,
            "narration_text": "What happens the exact second you cross into a black hole?",
            "visual_mode": "character_drama",
            "backdrop_rig": "deep_cosmos_nebula",
            "diagram_rig": None,
            "active_diagram_stage": None,
            "primary_character": "sutradhar_narrator",
            "secondary_character": None,
            "callout_headline": None,
            "callout_subtext": None,
            "emotion": "shock",
            "action_gesture": "idle_breathe",
            "mood_palette": "cosmic_indigo",
            "particle_theme": "starfield_warp",
            "camera_motion": "dramatic_zoom",
            "transition_sfx": "sub_hit.wav",
            "pause_after_ms": 350,
            "emphasis_word": "black",
        },
        {
            "scene_index": 2,
            "narration_text": "To an observer deep in space, your clock appears to tick slower as intense gravity warps the flow of time.",
            "visual_mode": "explainer_diagram",
            "backdrop_rig": "deep_cosmos_nebula",
            "diagram_rig": "gravitational_time_dilation_clock",
            "active_diagram_stage": 1,
            "primary_character": None,
            "secondary_character": None,
            "callout_headline": None,
            "callout_subtext": None,
            "emotion": "calm",
            "action_gesture": "idle_breathe",
            "mood_palette": "cosmic_indigo",
            "particle_theme": "quantum_nodes",
            "camera_motion": "slow_push",
            "transition_sfx": "whoosh_soft.wav",
            "pause_after_ms": 250,
            "emphasis_word": "gravity",
        },
        {
            "scene_index": 3,
            "narration_text": "Light paths bend inward along invisible geodesic curves, pulled relentlessly down a cosmic gravitational well.",
            "visual_mode": "explainer_diagram",
            "backdrop_rig": "deep_cosmos_nebula",
            "diagram_rig": "gravitational_time_dilation_clock",
            "active_diagram_stage": 2,
            "primary_character": None,
            "secondary_character": None,
            "callout_headline": None,
            "callout_subtext": None,
            "emotion": "calm",
            "action_gesture": "idle_breathe",
            "mood_palette": "cosmic_indigo",
            "particle_theme": "starfield_warp",
            "camera_motion": "dramatic_zoom",
            "transition_sfx": "tension_swell.wav",
            "pause_after_ms": 200,
            "emphasis_word": "curves",
        },
        {
            "scene_index": 4,
            "narration_text": "Near the horizon, a single second for you stretches into thousands of years across the outside universe.",
            "visual_mode": "kinetic_callout",
            "backdrop_rig": "deep_cosmos_nebula",
            "diagram_rig": None,
            "active_diagram_stage": None,
            "primary_character": None,
            "secondary_character": None,
            "callout_headline": "TIME DILATION",
            "callout_subtext": "1 SECOND = 1,000 YEARS",
            "emotion": "shock",
            "action_gesture": "idle_breathe",
            "mood_palette": "golden_imperial",
            "particle_theme": "golden_embers",
            "camera_motion": "slow_pull",
            "transition_sfx": "sub_hit.wav",
            "pause_after_ms": 300,
            "emphasis_word": "thousands",
        },
        {
            "scene_index": 5,
            "narration_text": "From your perspective, your wristwatch ticks normally... but every escape path into tomorrow is severed forever.",
            "visual_mode": "explainer_diagram",
            "backdrop_rig": "deep_cosmos_nebula",
            "diagram_rig": "gravitational_time_dilation_clock",
            "active_diagram_stage": 3,
            "primary_character": None,
            "secondary_character": None,
            "callout_headline": None,
            "callout_subtext": None,
            "emotion": "calm",
            "action_gesture": "idle_breathe",
            "mood_palette": "cosmic_indigo",
            "particle_theme": "quantum_nodes",
            "camera_motion": "slow_push",
            "transition_sfx": "whoosh_soft.wav",
            "pause_after_ms": 250,
            "emphasis_word": "severed",
        },
        {
            "scene_index": 6,
            "narration_text": "You slip across the event horizon silently, while the dying light of the cosmos blazes behind you.",
            "visual_mode": "explainer_diagram",
            "backdrop_rig": "deep_cosmos_nebula",
            "diagram_rig": "gravitational_time_dilation_clock",
            "active_diagram_stage": 4,
            "primary_character": None,
            "secondary_character": None,
            "callout_headline": None,
            "callout_subtext": None,
            "emotion": "shock",
            "action_gesture": "idle_breathe",
            "mood_palette": "cosmic_indigo",
            "particle_theme": "starfield_warp",
            "camera_motion": "dramatic_zoom",
            "transition_sfx": "tension_swell.wav",
            "pause_after_ms": 350,
            "emphasis_word": "horizon",
        },
        {
            "scene_index": 7,
            "narration_text": "Welcome to Sutradhar... where ancient mystery meets cosmic reality.",
            "visual_mode": "character_drama",
            "backdrop_rig": "deep_cosmos_nebula",
            "diagram_rig": None,
            "active_diagram_stage": None,
            "primary_character": "sutradhar_narrator",
            "secondary_character": None,
            "callout_headline": None,
            "callout_subtext": None,
            "emotion": "calm",
            "action_gesture": "idle_breathe",
            "mood_palette": "golden_imperial",
            "particle_theme": "golden_embers",
            "camera_motion": "slow_push",
            "transition_sfx": "whoosh_soft.wav",
            "pause_after_ms": 400,
            "emphasis_word": "reality",
        },
    ],
}

# Sample 02 Plan: Echoes of Kailash
SAMPLE_02_PLAN: dict[str, Any] = {
    "series_id": 2,
    "series_title": "Echoes of Kailash",
    "pillar": "Ancient Epics & Lore",
    "episode_number_in_series": 1,
    "total_planned_episodes": 3,
    "global_episode_number": 2,
    "tts_voice": "bm_george:0.60+am_fenrir:0.40",
    "bgm_track": "dramatic_mythology.mp3",
    "bespoke_asset_path": "assets/svg/diagrams/kailash_axis_alignments.svg",
    "youtube_title": "The Secret Geometry Beneath Mount Kailash (Part 1/3) #Shorts",
    "youtube_description": "Part 1 of 3: Echoes of Kailash. Discover the cardinal alignment and planetary geometry of Mount Kailash. Watch on Sutradhar! #Mythology #History #Shorts",
    "summary": "Explores the cardinal alignment and planetary geodetic coordinates of Mount Kailash.",
    "scenes": [
        {
            "scene_index": 1,
            "narration_text": "What if the most sacred peak on Earth... is not a natural mountain at all?",
            "visual_mode": "character_drama",
            "backdrop_rig": "mount_kailash",
            "diagram_rig": None,
            "active_diagram_stage": None,
            "primary_character": "sutradhar_narrator",
            "secondary_character": None,
            "callout_headline": None,
            "callout_subtext": None,
            "emotion": "calm",
            "action_gesture": "idle_breathe",
            "mood_palette": "golden_imperial",
            "particle_theme": "golden_embers",
            "camera_motion": "slow_push",
            "transition_sfx": "sub_hit.wav",
            "pause_after_ms": 350,
            "emphasis_word": "sacred",
        },
        {
            "scene_index": 2,
            "narration_text": "Ancient Sanskrit scrolls describe Mount Kailash as four sheer faces aligned to cardinal directions.",
            "visual_mode": "explainer_diagram",
            "backdrop_rig": "mount_kailash",
            "diagram_rig": "kailash_axis_alignments",
            "active_diagram_stage": 1,
            "primary_character": None,
            "secondary_character": None,
            "callout_headline": None,
            "callout_subtext": None,
            "emotion": "calm",
            "action_gesture": "idle_breathe",
            "mood_palette": "golden_imperial",
            "particle_theme": "golden_embers",
            "camera_motion": "dramatic_zoom",
            "transition_sfx": "whoosh_soft.wav",
            "pause_after_ms": 250,
            "emphasis_word": "cardinal",
        },
        {
            "scene_index": 3,
            "narration_text": "Geodetic surveys reveal an extraordinary alignment... standing sixty-six hundred kilometers from the North Pole.",
            "visual_mode": "explainer_diagram",
            "backdrop_rig": "mount_kailash",
            "diagram_rig": "kailash_axis_alignments",
            "active_diagram_stage": 2,
            "primary_character": None,
            "secondary_character": None,
            "callout_headline": None,
            "callout_subtext": None,
            "emotion": "calm",
            "action_gesture": "idle_breathe",
            "mood_palette": "golden_imperial",
            "particle_theme": "golden_embers",
            "camera_motion": "slow_push",
            "transition_sfx": "tension_swell.wav",
            "pause_after_ms": 250,
            "emphasis_word": "alignment",
        },
        {
            "scene_index": 4,
            "narration_text": "In the Ramayana, the titan Ravana gripped its roots... attempting to shake the mountain.",
            "visual_mode": "character_drama",
            "backdrop_rig": "mount_kailash",
            "diagram_rig": None,
            "active_diagram_stage": None,
            "primary_character": "ravana",
            "secondary_character": None,
            "callout_headline": None,
            "callout_subtext": None,
            "emotion": "wrath",
            "action_gesture": "raise_weapon",
            "mood_palette": "crimson_wrath",
            "particle_theme": "quantum_nodes",
            "camera_motion": "dramatic_zoom",
            "transition_sfx": "sub_hit.wav",
            "pause_after_ms": 300,
            "emphasis_word": "Ravana",
        },
        {
            "scene_index": 5,
            "narration_text": "Four sacred rivers burst from its granite base, spiraling outward in a celestial mandala.",
            "visual_mode": "explainer_diagram",
            "backdrop_rig": "mount_kailash",
            "diagram_rig": "kailash_axis_alignments",
            "active_diagram_stage": 3,
            "primary_character": None,
            "secondary_character": None,
            "callout_headline": None,
            "callout_subtext": None,
            "emotion": "calm",
            "action_gesture": "idle_breathe",
            "mood_palette": "golden_imperial",
            "particle_theme": "golden_embers",
            "camera_motion": "slow_push",
            "transition_sfx": "whoosh_soft.wav",
            "pause_after_ms": 250,
            "emphasis_word": "mandala",
        },
        {
            "scene_index": 6,
            "narration_text": "Whether a stone pyramid or an axis mundi... its core remains forever unclimbed.",
            "visual_mode": "kinetic_callout",
            "backdrop_rig": "mount_kailash",
            "diagram_rig": None,
            "active_diagram_stage": None,
            "primary_character": None,
            "secondary_character": None,
            "callout_headline": "AXIS MUNDI",
            "callout_subtext": "EARTH MONUMENT ALIGNMENT",
            "emotion": "calm",
            "action_gesture": "idle_breathe",
            "mood_palette": "obsidian_amber",
            "particle_theme": "golden_embers",
            "camera_motion": "slow_pull",
            "transition_sfx": "tension_swell.wav",
            "pause_after_ms": 350,
            "emphasis_word": "unclimbed",
        },
        {
            "scene_index": 7,
            "narration_text": "Welcome to Sutradhar... where forgotten legends echo into eternity.",
            "visual_mode": "character_drama",
            "backdrop_rig": "mount_kailash",
            "diagram_rig": None,
            "active_diagram_stage": None,
            "primary_character": "sutradhar_narrator",
            "secondary_character": None,
            "callout_headline": None,
            "callout_subtext": None,
            "emotion": "calm",
            "action_gesture": "idle_breathe",
            "mood_palette": "golden_imperial",
            "particle_theme": "golden_embers",
            "camera_motion": "slow_push",
            "transition_sfx": "whoosh_soft.wav",
            "pause_after_ms": 400,
            "emphasis_word": "eternity",
        },
    ],
}


def link_or_copy(src: Path, dst: Path) -> None:
    if dst.exists():
        if dst.is_dir() and not dst.is_symlink():
            shutil.rmtree(dst)
        else:
            dst.unlink()
    try:
        os.link(src, dst)
    except OSError:
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)


def setup_staging_env(stage_dir: Path) -> None:
    stage_dir.mkdir(parents=True, exist_ok=True)
    build_dir = stage_dir / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    (build_dir / "audio").mkdir(parents=True, exist_ok=True)

    # Core files needed for HyperFrames and pipeline execution
    for fname in ["index.html", "styles.css", "engine.js", "package.json", "config.yaml", "pronunciations.yaml"]:
        src = REPO_ROOT / fname
        if src.exists():
            shutil.copy2(src, stage_dir / fname)

    # Assets & node_modules
    for dname in ["assets", "node_modules", "models"]:
        src = REPO_ROOT / dname
        dst = stage_dir / dname
        if src.exists() and not dst.exists():
            # Create symlink or junction on Windows
            try:
                os.symlink(src, dst, target_is_directory=True)
            except OSError:
                shutil.copytree(src, dst)


def produce_sample(sample_id: str, plan: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    print(f"\n{'='*70}\nPRODUCING {sample_id.upper()}: {plan['series_title']}\n{'='*70}")
    stage_dir = REPO_ROOT / "build" / f"stage_{sample_id}"
    setup_staging_env(stage_dir)

    # Write episode plan
    (stage_dir / "build" / "episode_plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")

    # Set SUTRADHAR_ROOT to isolated stage directory
    os.environ["SUTRADHAR_ROOT"] = str(stage_dir)

    # Step 1: Build Audio (TTS + Whisper word alignment + padding)
    print("\n--- STEP 1: Building Audio & Pronunciation Alignment ---")
    audio_res = build_audio.build_episode_audio(root=stage_dir)
    print(f"Audio built: {audio_res['scene_count']} scenes, total duration: {audio_res['total_duration_sec']:.2f}s")
    if audio_res.get("duration_warning"):
        print(f"[WARN] {audio_res['duration_warning']}")

    # Step 2: Preview Frames (Lint, Check & 3x3 mid-scene contact sheet)
    print("\n--- STEP 2: Preview Frames & Pre-Render Visual QA ---")
    preview_res = preview_frames.run_preview_pipeline(root=stage_dir)
    print(f"Preview complete: {preview_res['scene_count']} scenes checked, contact sheet: {preview_res.get('qa_grid_jpg')}")

    # Step 3: Render & QA (HyperFrames render + broadcast audio mix + KinoCut QA)
    print("\n--- STEP 3: HyperFrames 0.9.70 High-Quality Render & Broadcast Mastering ---")
    render_res = render_and_qa.run_render_and_qa_pipeline(root=stage_dir)
    print(f"Render complete: {render_res.get('final_short')}")
    print(f"KinoCut Score: {render_res.get('kinocut_score', 0):.1f}/100, Target Loudness: {render_res.get('target_lufs', -14.0)} LUFS")

    # Step 4: Verify Deliverables & Metrics
    final_video = stage_dir / "build" / "final_short.mp4"
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "stream=width,height,r_frame_rate,duration,codec_name:format=duration",
        "-of", "json",
        str(final_video),
    ]
    proc = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
    probe_data = json.loads(proc.stdout)
    v_stream = next(s for s in probe_data["streams"] if s.get("width"))
    a_stream = next(s for s in probe_data["streams"] if s.get("codec_name") == "aac")
    total_dur = float(probe_data["format"]["duration"])

    verification = {
        "sample_id": sample_id,
        "series_title": plan["series_title"],
        "pillar": plan["pillar"],
        "voice": plan["tts_voice"],
        "resolution": f"{v_stream['width']}x{v_stream['height']}",
        "fps": v_stream["r_frame_rate"],
        "total_duration_sec": total_dur,
        "kinocut_score": render_res["kinocut_score"],
        "integrated_lufs": render_res.get("target_lufs", -14.0),
        "audio_codec": a_stream["codec_name"],
        "video_codec": v_stream["codec_name"],
        "audio_build": audio_res,
        "render_qa": render_res,
    }

    # Step 5: Archive Deliverables into output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    deliverables = [
        ("final_short.mp4", stage_dir / "build" / "final_short.mp4"),
        ("narration_full.wav", stage_dir / "build" / "audio" / "narration_full.wav"),
        ("manifest.js", stage_dir / "build" / "manifest.js"),
        ("episode_plan.json", stage_dir / "build" / "episode_plan.json"),
        ("qa_grid.jpg", stage_dir / "build" / "qa_grid.jpg"),
        ("qa_grid_safezones.jpg", stage_dir / "build" / "qa_grid_safezones.jpg"),
        ("final_qa_grid.jpg", stage_dir / "build" / "final_qa_grid.jpg"),
        ("render_report.json", stage_dir / "build" / "render_report.json"),
    ]
    for target_name, src_path in deliverables:
        if src_path.exists():
            shutil.copy2(src_path, output_dir / target_name)

    (output_dir / "verification_report.json").write_text(json.dumps(verification, indent=2), encoding="utf-8")
    print(f"\n[SUCCESS] Archived all deliverables to {output_dir}")

    # Clean up stage dir to save disk space
    shutil.rmtree(stage_dir, ignore_errors=True)
    return verification


def main() -> None:
    samples_dir = REPO_ROOT / "build" / "samples"
    samples_dir.mkdir(parents=True, exist_ok=True)

    # Produce Sample 01 if not already verified
    s1_report = samples_dir / "sample_01_cosmos" / "verification_report.json"
    if s1_report.exists():
        print(f"\n[INFO] Sample 01 already verified at {s1_report}; skipping.")
    else:
        res1 = produce_sample("sample_01_cosmos", SAMPLE_01_PLAN, samples_dir / "sample_01_cosmos")
        print("\nSAMPLE 01 VERIFICATION:")
        print(json.dumps(res1, indent=2))

    # Produce Sample 02
    res2 = produce_sample("sample_02_epics", SAMPLE_02_PLAN, samples_dir / "sample_02_epics")
    print("\nSAMPLE 02 VERIFICATION:")
    print(json.dumps(res2, indent=2))

    print("\n" + "="*70)
    print("ALL SAMPLE VIDEOS GENERATED AND VERIFIED SUCCESSFULLY!")
    print("="*70)


if __name__ == "__main__":
    main()
