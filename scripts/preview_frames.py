#!/usr/bin/env python3
"""Sutradhar — Thin CLI Facade for Pre-Render Visual QA & Preview Sheet.

Whitelisted zero-argument CLI invocation:
    python scripts/preview_frames.py

Reads:
    - build/episode_plan.json (EpisodePlanV2 + StoryboardIR)
    - build/audio/audio_manifest.json

Executes:
    - sutradhar.visual.storyboard_composer.compose_storyboard()
    - npx hyperframes lint + npx hyperframes check --strict --safe-zone shorts --json
    - Chromium deterministic runtime probe (__timelines, hf-seek, fonts, safe zones)
    - 15-frame storyboard preview contact sheet

Writes (atomically):
    - build/qa_grid.jpg
    - build/qa_grid_safezones.jpg
    - build/qa_report.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from db_manager import get_project_root, load_config  # noqa: E402
from sutradhar.qa.hyperframes_runner import (  # noqa: E402
    generate_storyboard_preview_sheet,
    run_chromium_runtime_probe,
    run_hf_check,
    run_hf_lint,
    validate_runtime_probe_and_hf_check,
)
from sutradhar.visual.storyboard_composer import (  # noqa: E402
    CAPTION_SAFE_BOTTOM_MAX,
    CompositionError,
    SHORTS_PILL_MAX_X,
    SHORTS_PILL_MAX_Y,
    SHORTS_PILL_MIN_X,
    SHORTS_PILL_MIN_Y,
    compose_storyboard,
    resolve_v2_episode_inputs,
)


class PreviewPipelineError(RuntimeError):
    """Raised when StoryboardIR compilation, linting, or visual QA fails."""


def run_preview_pipeline(root: Path) -> dict[str, Any]:
    """Compile v2 StoryboardIR bundle, verify runtime & safe zones, and stitch 15-frame QA grids."""
    cfg = load_config(root)
    build_dir = (root / cfg["paths"]["build_dir"]).resolve()
    try:
        plan_data, audio_manifest = resolve_v2_episode_inputs(root, cfg)
        comp = compose_storyboard(
            root,
            plan_data,
            audio_manifest=audio_manifest,
            output_dir=build_dir / "composition",
            mix_audio=True,
            cfg=cfg,
        )
    except CompositionError as exc:
        raise PreviewPipelineError(str(exc)) from exc

    lint_res = run_hf_lint(root, comp.output_dir)
    if not lint_res.get("ok"):
        raise PreviewPipelineError(
            f"hyperframes lint failed: errors={lint_res.get('errorCount')}, "
            f"warnings={lint_res.get('warningCount')}, findings={lint_res.get('findings')}"
        )

    check_res = run_hf_check(root, comp.output_dir, safe_zone="shorts", strict=True)
    probe_res = run_chromium_runtime_probe(root, comp.index_html, duration_sec=comp.duration_sec)
    validation_errors = validate_runtime_probe_and_hf_check(
        probe_res,
        check_res,
        caption_safe_bottom_max=CAPTION_SAFE_BOTTOM_MAX,
        pill_min_x=SHORTS_PILL_MIN_X,
        pill_max_x=SHORTS_PILL_MAX_X,
        pill_min_y=SHORTS_PILL_MIN_Y,
        pill_max_y=SHORTS_PILL_MAX_Y,
    )
    if validation_errors:
        raise PreviewPipelineError("Preview QA checks failed:\n- " + "\n- ".join(validation_errors))

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
