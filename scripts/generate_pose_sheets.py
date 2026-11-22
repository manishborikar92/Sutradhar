#!/usr/bin/env python3
"""Sutradhar — Character Pose Verification Sheet Generator.

Renders 4-pose verification contact sheets under `build/phase4_qa/<char>_pose_sheet.png`
(Idle, Action Raised inside x: 90..990, Close-up Dialogue with open mouth, Alternate/Calm)
via `npx hyperframes snapshot` and PIL stitching.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from generate_composition import generate_root_composition, FALLBACK_MANIFEST  # noqa: E402

BUILD_DIR = ROOT_DIR / "build"
QA_DIR = BUILD_DIR / "phase4_qa"
CHARACTERS = [
    "shani_dev",
    "narad_muni",
    "hanuman",
    "ancient_scholar",
    "ravana",
    "mandodari",
    "surya_dev",
    "indra_dev",
    "shiva",
    "sutradhar_narrator",
]


def make_char_manifest(char_name: str) -> dict[str, Any]:
    return {
        "schema_version": "2.0",
        "language": "en",
        "series_id": 99,
        "series_title": f"Pose QA: {char_name}",
        "pillar": "Ancient Epics & Lore",
        "episode_number_in_series": 1,
        "total_planned_episodes": 3,
        "global_episode_number": 99,
        "youtube_title": f"Pose QA: {char_name}",
        "tts_voice": "bm_fable:0.55+am_fenrir:0.45",
        "bgm_track": "dramatic_mythology.mp3",
        "video": {
            "width": 1080,
            "height": 1920,
            "fps": 30,
            "safe_zones": {
                "top_clear_px": 288,
                "bottom_clear_px": 520,
                "left_clear_px": 48,
                "right_clear_px": 192,
            },
        },
        "audio": {
            "total_duration_sec": 4.00,
            "total_frames": 120,
            "sample_rate": 24000,
            "narration_full_path": "build/audio/narration_full.wav",
        },
        "scenes": [
            {
                "scene_index": 1,
                "shot_type": "character_medium",
                "backdrop_rig": "celestial_cosmos_court",
                "primary_character": char_name,
                "speaker_role": "narrator",
                "narration_text": f"{char_name} stands in serene contemplation before the cosmic assembly.",
                "start_sec": 0.0,
                "end_sec": 1.0,
                "duration_sec": 1.0,
                "midpoint_sec": 0.5,
                "pose_preset": "idle_royal",
                "emotion": "calm",
                "camera_motion": "slow_pan",
            },
            {
                "scene_index": 2,
                "shot_type": "character_medium",
                "backdrop_rig": "celestial_cosmos_court",
                "primary_character": char_name,
                "speaker_role": "narrator",
                "narration_text": f"{char_name} raises their weapon and celestial prop with focused wrathful intent.",
                "start_sec": 1.0,
                "end_sec": 2.0,
                "duration_sec": 1.0,
                "midpoint_sec": 1.5,
                "action_gesture": "raise_weapon",
                "pose_preset": "action_raised",
                "emotion": "wrath",
                "camera_motion": "push_in",
            },
            {
                "scene_index": 3,
                "shot_type": "character_medium",
                "backdrop_rig": "celestial_cosmos_court",
                "primary_character": char_name,
                "speaker_role": "narrator",
                "narration_text": f"{char_name} recoils in fearful awe before the overwhelming cosmic mandate.",
                "start_sec": 2.0,
                "end_sec": 3.0,
                "duration_sec": 1.0,
                "midpoint_sec": 2.5,
                "pose_preset": "humbled_braced",
                "emotion": "fear",
                "camera_motion": "close_up",
            },
            {
                "scene_index": 4,
                "shot_type": "character_medium",
                "backdrop_rig": "celestial_cosmos_court",
                "primary_character": char_name,
                "speaker_role": "narrator",
                "narration_text": f"{char_name} bestows peaceful wisdom and joyful protection upon all realms.",
                "start_sec": 3.0,
                "end_sec": 4.0,
                "duration_sec": 1.0,
                "midpoint_sec": 3.5,
                "action_gesture": "bless_hand",
                "pose_preset": "blessing_calm",
                "emotion": "joy",
                "camera_motion": "pull_back",
            },
        ],
    }


def render_all_pose_sheets() -> list[Path]:
    QA_DIR.mkdir(parents=True, exist_ok=True)
    manifest_js_path = BUILD_DIR / "manifest.js"

    # Backup existing manifest.js if any
    backup_manifest = manifest_js_path.read_text(encoding="utf-8") if manifest_js_path.is_file() else None

    rendered_sheets: list[Path] = []
    labels = [
        "Pose 1: Idle Royal [Calm]",
        "Pose 2: Action Raised [Wrath]",
        "Pose 3: Humbled Braced [Fear]",
        "Pose 4: Blessing Calm [Joy]",
    ]

    try:
        for char_name in CHARACTERS:
            print(f"\n[INFO] Generating 4-pose QA sheet for {char_name}...")
            # 1. Write character manifest
            char_m = make_char_manifest(char_name)
            manifest_js_path.write_text(
                f"window.EPISODE_MANIFEST = {json.dumps(char_m, indent=2)};\n",
                encoding="utf-8",
            )

            # 2. Re-generate composition
            generate_root_composition(ROOT_DIR)

            # 3. Run hyperframes snapshot
            snap_dir = QA_DIR / f"snaps_{char_name}"
            if snap_dir.exists():
                shutil.rmtree(snap_dir)
            snap_dir.mkdir(parents=True, exist_ok=True)

            cmd = [
                "npx.cmd" if sys.platform == "win32" else "npx",
                "hyperframes",
                "snapshot",
                "--at",
                "0.5,1.5,2.5,3.5",
                "--no-end",
                "--output",
                str(snap_dir),
            ]
            res = subprocess.run(cmd, cwd=str(ROOT_DIR), capture_output=True, text=True)
            if res.returncode != 0:
                print(f"[WARN] HyperFrames snapshot failed for {char_name}:\n{res.stderr}")
                continue

            # Locate captured PNG frames
            png_files = sorted(snap_dir.glob("frame-*.png"))
            if len(png_files) < 4:
                print(f"[WARN] Expected 4 frames for {char_name}, got {len(png_files)} in {snap_dir}")
                continue

            # 4. Stitch into 2x2 grid (1080x1920)
            sheet = Image.new("RGB", (1080, 1920), color=(10, 12, 20))
            draw = ImageDraw.Draw(sheet)

            positions = [(0, 0), (540, 0), (0, 960), (540, 960)]
            for idx, (p_file, (px, py), lbl) in enumerate(zip(png_files[:4], positions, labels)):
                with Image.open(p_file) as im:
                    resized = im.convert("RGB").resize((540, 960), Image.Resampling.LANCZOS)
                    sheet.paste(resized, (px, py))

                # Border
                draw.rectangle([px, py, px + 540, py + 960], outline=(180, 140, 40), width=3)
                # Label Banner
                draw.rectangle([px + 10, py + 15, px + 530, py + 65], fill=(15, 18, 30), outline=(200, 160, 50), width=2)
                draw.text((px + 20, py + 26), f"[{char_name.upper()}] {lbl}", fill=(255, 225, 120))

            sheet_path = QA_DIR / f"{char_name}_pose_sheet.png"
            sheet.save(sheet_path, "PNG")
            print(f"[SUCCESS] Saved {sheet_path} ({sheet_path.stat().st_size:,} bytes)")
            rendered_sheets.append(sheet_path)

    finally:
        # Restore original manifest or fallback manifest
        if backup_manifest:
            manifest_js_path.write_text(backup_manifest, encoding="utf-8")
        else:
            manifest_js_path.write_text(
                f"window.EPISODE_MANIFEST = {json.dumps(FALLBACK_MANIFEST, indent=2)};\n",
                encoding="utf-8",
            )
        generate_root_composition(ROOT_DIR)

    return rendered_sheets


if __name__ == "__main__":
    sheets = render_all_pose_sheets()
    print(f"\n[DONE] Rendered {len(sheets)}/{len(CHARACTERS)} character pose verification sheets.")
