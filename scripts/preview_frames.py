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
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from db_manager import get_project_root, load_config  # noqa: E402
from scripts.engine.composer import compose_episode  # noqa: E402
from sutradhar.qa.hyperframes_runner import (  # noqa: E402
    HyperFramesError,
    generate_storyboard_preview_sheet,
    run_chromium_runtime_probe,
    run_hf_check,
    run_hf_lint,
    stitch_contact_sheet as _shared_stitch_contact_sheet,
)
from sutradhar.visual.storyboard_composer import (  # noqa: E402
    CompositionError,
    compose_storyboard,
    detect_v2_storyboard_run,
    parse_manifest_js as _shared_parse_manifest_js,
    resolve_v2_episode_inputs,
)


class PreviewPipelineError(RuntimeError):
    """Raised when preview extraction or visual QA fails."""


def parse_manifest_js(manifest_path: Path) -> dict[str, Any]:
    """Parse episode manifest JS using shared sutradhar.visual helper."""
    try:
        return _shared_parse_manifest_js(manifest_path)
    except CompositionError as exc:
        raise PreviewPipelineError(str(exc)) from exc


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
    """Delegate contact-sheet rendering to shared sutradhar.qa helper."""
    try:
        _shared_stitch_contact_sheet(
            image_paths,
            scene_labels,
            output_path,
            cols=cols,
            thumb_w=thumb_w,
            thumb_h=thumb_h,
            overlay_safe_zones=overlay_safe_zones,
            safe_zones=safe_zones,
        )
    except HyperFramesError as exc:
        raise PreviewPipelineError(str(exc)) from exc


def _run_v2_preview_pipeline(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    build_dir = (root / cfg["paths"]["build_dir"]).resolve()
    plan_data, audio_manifest = resolve_v2_episode_inputs(root, cfg)
    comp = compose_storyboard(
        root,
        plan_data,
        audio_manifest=audio_manifest,
        output_dir=build_dir / "composition",
        mix_audio=True,
        cfg=cfg,
    )
    lint_res = run_hf_lint(root, comp.output_dir)
    check_res = run_hf_check(root, comp.output_dir, safe_zone="shorts", strict=True)
    probe_res = run_chromium_runtime_probe(root, comp.index_html, duration_sec=comp.duration_sec)
    if probe_res["console_errors"] or probe_res["page_errors"] or probe_res["failed_requests"]:
        raise PreviewPipelineError(
            f"Chromium runtime errors during preview: {probe_res['console_errors']} {probe_res['page_errors']}"
        )
    if not probe_res["idempotency_passed"]:
        raise PreviewPipelineError(
            f"hf-seek({probe_res['idempotency_time_sec']}s) pixel-parity MAE={probe_res['idempotency_mae']} > 0.5"
        )
    if not check_res.get("ok"):
        raise PreviewPipelineError(
            f"hyperframes check --strict --safe-zone shorts failed: {check_res.get('errors')} {check_res.get('warnings')}"
        )

    scene_ranges = [(float(sc["s0"]), float(sc["s1"])) for sc in comp.episode_runtime["scenes"]]
    qa_grid_jpg = build_dir / "qa_grid.jpg"
    qa_grid_safezones_jpg = build_dir / "qa_grid_safezones.jpg"
    sheet_info = generate_storyboard_preview_sheet(
        root,
        comp.output_dir,
        comp.duration_sec,
        qa_grid_jpg,
        scene_ranges=scene_ranges,
        safe_zone_jpg=qa_grid_safezones_jpg,
        count=15,
    )

    qa_report = {
        "status": "ok",
        "action": "preview_frames",
        "runtime_version": "v2_storycraft",
        "scene_count": comp.scene_count,
        "duration_sec": comp.duration_sec,
        "qa_grid_jpg": "build/qa_grid.jpg",
        "qa_grid_safezones_jpg": "build/qa_grid_safezones.jpg",
        "lint_clean": lint_res.get("ok", lint_res.get("exit_code") == 0),
        "hyperframes_check": check_res,
        "chromium_probe": probe_res,
        "preview_sheet": sheet_info,
    }
    (build_dir / "qa_report.json").write_text(json.dumps(qa_report, indent=2), encoding="utf-8")
    return qa_report


def run_preview_pipeline(root: Path) -> dict[str, Any]:
    cfg = load_config(root)
    if detect_v2_storyboard_run(root, cfg):
        return _run_v2_preview_pipeline(root, cfg)

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
