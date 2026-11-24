#!/usr/bin/env python3
"""Sutradhar — Pre-Render Visual QA & Snapshot Grid Generator.

Whitelisted zero-argument CLI invocation:
    python scripts/preview_frames.py

Reads:
    - build/manifest.js (midpoint timestamps, scene count, safe zones)

Executes:
    - npx hyperframes lint
    - npx hyperframes check --json
    - npx hyperframes snapshot --at <t1,t2,...>

Writes (atomically):
    - build/qa_grid.jpg (labeled 3x3 mid-scene contact sheet)
    - build/qa_grid_safezones.jpg (contact sheet with 2026 YouTube Shorts safe-zone overlays)
    - build/qa_report.json
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

from PIL import Image, ImageDraw, ImageFont

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from db_manager import get_project_root, load_config  # noqa: E402
from scripts.engine.composer import compose_episode  # noqa: E402


class PreviewPipelineError(RuntimeError):
    """Raised when preview extraction or visual QA fails."""


def parse_manifest_js(manifest_path: Path) -> dict[str, Any]:
    if not manifest_path.is_file():
        raise PreviewPipelineError(f"Missing manifest file at '{manifest_path}'. Run build_audio.py first.")
    content = manifest_path.read_text(encoding="utf-8")
    match = re.search(r"window\.EPISODE_MANIFEST\s*=\s*(\{.*?\});\s*$", content, re.DOTALL)
    if not match:
        raise PreviewPipelineError(f"Failed to parse window.EPISODE_MANIFEST from '{manifest_path}'.")
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise PreviewPipelineError(f"Invalid JSON in '{manifest_path}': {exc}") from exc


def stitch_contact_sheet(
    image_paths: list[Path],
    scene_labels: list[str],
    output_path: Path,
    cols: int = 3,
    thumb_w: int = 360,
    thumb_h: int = 640,
    overlay_safe_zones: bool = False,
    safe_zones: Optional[dict[str, int]] = None,
) -> None:
    n = len(image_paths)
    if n == 0:
        raise PreviewPipelineError("No snapshot images provided to stitch.")
    rows = (n + cols - 1) // cols
    sheet_w = cols * thumb_w
    sheet_h = rows * thumb_h

    sheet = Image.new("RGB", (sheet_w, sheet_h), color=(10, 10, 15))
    draw = ImageDraw.Draw(sheet)

    # Scale factors for safe-zone overlay on thumbnail (native is 1080x1920)
    sx = thumb_w / 1080.0
    sy = thumb_h / 1920.0

    for idx, (img_p, label) in enumerate(zip(image_paths, scene_labels)):
        col = idx % cols
        row = idx // cols
        x_off = col * thumb_w
        y_off = row * thumb_h

        if img_p.is_file():
            with Image.open(img_p) as im:
                thumb = im.convert("RGB").resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
                sheet.paste(thumb, (x_off, y_off))
        else:
            draw.rectangle([x_off, y_off, x_off + thumb_w, y_off + thumb_h], fill=(40, 20, 20))
            draw.text((x_off + 20, y_off + thumb_h // 2), f"Missing: {img_p.name}", fill=(255, 100, 100))

        # Draw Safe-Zone Guide Overlay if requested
        if overlay_safe_zones and safe_zones:
            top_px = int(safe_zones.get("top_clear_px", 288) * sy)
            bot_px = int(thumb_h - (safe_zones.get("bottom_clear_px", 520) * sy))
            right_px = int(thumb_w - (safe_zones.get("right_clear_px", 192) * sx))
            left_px = int(safe_zones.get("left_clear_px", 48) * sx)

            # Shaded danger zones (translucent red)
            overlay = Image.new("RGBA", (thumb_w, thumb_h), (0, 0, 0, 0))
            ov_draw = ImageDraw.Draw(overlay)
            # Top blocked area
            ov_draw.rectangle([0, 0, thumb_w, top_px], fill=(255, 0, 0, 45))
            # Bottom blocked area
            ov_draw.rectangle([0, bot_px, thumb_w, thumb_h], fill=(255, 0, 0, 60))
            # Right blocked area
            ov_draw.rectangle([right_px, top_px, thumb_w, bot_px], fill=(255, 0, 0, 45))

            # Safe area outline (bright cyan)
            ov_draw.rectangle([left_px, top_px, right_px, bot_px], outline=(0, 255, 255, 180), width=2)

            sheet.paste(overlay, (x_off, y_off), mask=overlay)

        # Label Banner at bottom of thumbnail
        banner_h = 32
        draw.rectangle([x_off, y_off + thumb_h - banner_h, x_off + thumb_w, y_off + thumb_h], fill=(0, 0, 0, 220))
        draw.text((x_off + 8, y_off + thumb_h - banner_h + 8), label, fill=(255, 215, 0))

        # Cell border
        draw.rectangle([x_off, y_off, x_off + thumb_w, y_off + thumb_h], outline=(60, 60, 70), width=1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(".tmp.jpg")
    sheet.save(tmp_path, "JPEG", quality=90)
    os.replace(tmp_path, output_path)


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


def run_preview_pipeline(root: Path) -> dict[str, Any]:
    cfg = load_config(root)
    build_dir = (root / cfg["paths"]["build_dir"]).resolve()
    manifest_path = build_dir / "manifest.js"
    manifest = parse_manifest_js(manifest_path)

    # Ensure composition files are generated & synchronized
    compose_episode(root)

    scenes = manifest.get("scenes", [])
    if not scenes:
        raise PreviewPipelineError("No scenes found in manifest.js.")

    midpoints = [round(float(s["midpoint_sec"]), 2) for s in scenes]
    midpoints_str = ",".join(str(m) for m in midpoints)

    npx_exe = shutil.which("npx") or ("npx.cmd" if sys.platform == "win32" else "npx")

    print(f"[INFO] Running HyperFrames lint...", file=sys.stderr)
    lint_proc = subprocess.run([npx_exe, "hyperframes", "lint", "build/composition"], cwd=root, capture_output=True, text=True, check=False)
    lint_clean = lint_proc.returncode == 0
    if not lint_clean:
        print(f"[WARN] HyperFrames lint output:\n{lint_proc.stderr or lint_proc.stdout}", file=sys.stderr)

    print(f"[INFO] Capturing {len(midpoints)} scene snapshots at [{midpoints_str}]...", file=sys.stderr)
    cmd_snap = [npx_exe, "hyperframes", "snapshot", "build/composition", "--at", midpoints_str]
    snap_proc = subprocess.run(cmd_snap, cwd=root, capture_output=True, text=True, check=False)
    if snap_proc.returncode != 0:
        raise PreviewPipelineError(f"hyperframes snapshot failed: {snap_proc.stderr or snap_proc.stdout}")

    # Discover snapshot directory from output or recent snapshot directory
    out_text = snap_proc.stdout + "\n" + snap_proc.stderr
    match_dir = re.search(r"snapshots saved to\s+(.*?)(?:\r?\n|$)", out_text)
    snap_dir: Optional[Path] = None
    if match_dir:
        candidate = Path(match_dir.group(1).strip())
        if candidate.is_dir():
            snap_dir = candidate

    if not snap_dir:
        # Fallback: scan composition and root .hyperframes/artifacts/snapshots
        for base_snaps in [
            root / "build" / "composition" / ".hyperframes" / "artifacts" / "snapshots",
            root / ".hyperframes" / "artifacts" / "snapshots",
        ]:
            if base_snaps.is_dir():
                subdirs = sorted(base_snaps.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
                if subdirs and subdirs[0].is_dir():
                    snap_dir = subdirs[0]
                    break

    if not snap_dir or not snap_dir.is_dir():
        raise PreviewPipelineError(f"Could not locate snapshot output directory. Output:\n{out_text}")

    # Gather frame PNGs (matching frame-*.png or at-*.png)
    frame_files = sorted(list(snap_dir.glob("frame-*.png")) + list(snap_dir.glob("at-*.png")))
    if not frame_files:
        raise PreviewPipelineError(f"Zero snapshot frame PNGs found in {snap_dir}")

    # Match frame files to scenes
    scene_frames = frame_files[: len(scenes)]
    scene_labels = [
        f"S{s['scene_index']} ({(s.get('shot_type') or s.get('visual_mode') or 'shot')[:6]}) @ {s['midpoint_sec']}s"
        for s in scenes
    ]

    safe_zones = cfg.get("video", {}).get("safe_zones", {})

    qa_grid_jpg = build_dir / "qa_grid.jpg"
    qa_grid_safezones_jpg = build_dir / "qa_grid_safezones.jpg"

    print(f"[INFO] Stitching labeled contact sheet -> {qa_grid_jpg.name} ...", file=sys.stderr)
    stitch_contact_sheet(
        image_paths=scene_frames,
        scene_labels=scene_labels,
        output_path=qa_grid_jpg,
        overlay_safe_zones=False,
    )

    print(f"[INFO] Stitching safe-zone overlay contact sheet -> {qa_grid_safezones_jpg.name} ...", file=sys.stderr)
    stitch_contact_sheet(
        image_paths=scene_frames,
        scene_labels=scene_labels,
        output_path=qa_grid_safezones_jpg,
        overlay_safe_zones=True,
        safe_zones=safe_zones,
    )

    qa_report = {
        "status": "ok",
        "action": "preview_frames",
        "scene_count": len(scenes),
        "midpoints_sec": midpoints,
        "qa_grid_jpg": "build/qa_grid.jpg",
        "qa_grid_safezones_jpg": "build/qa_grid_safezones.jpg",
        "snapshot_dir": str(snap_dir),
        "lint_clean": lint_clean,
    }

    report_path = build_dir / "qa_report.json"
    report_path.write_text(json.dumps(qa_report, indent=2), encoding="utf-8")
    return qa_report


def main() -> int:
    if len(sys.argv) > 1:
        print("[ERROR] scripts/preview_frames.py takes zero CLI arguments.", file=sys.stderr)
        return 1
    try:
        root = get_project_root()
        res = run_preview_pipeline(root)
        print(json.dumps(res, indent=2))
        return 0
    except (PreviewPipelineError, Exception) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
