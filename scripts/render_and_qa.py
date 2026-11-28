#!/usr/bin/env python3
"""Sutradhar — Thin CLI Facade for Render, Audio Mastering & Fail-Closed QA Gate.

Whitelisted zero-argument CLI invocation:
    python scripts/render_and_qa.py

Reads:
    - build/episode_plan.json (EpisodePlanV2 + StoryboardIR + ThumbnailSpec)
    - build/audio/audio_manifest.json

Executes:
    - sutradhar.visual.storyboard_composer.compose_storyboard() (incl. 48 kHz stereo audio mix)
    - sutradhar.visual.thumbnail_builder.build_thumbnail() (1080x1920 JPEG + 2:3 Shorts crop)
    - sutradhar.qa.render_optimizer.render_episode_mp4() (<= 55 MiB H.264/AAC MP4)
    - sutradhar.qa.quality_gate.run_v2_quality_gate() (Chromium, KinoCut, ebur128, Whisper, thumbnail)

Writes:
    - build/final_short.mp4
    - build/final_qa_grid.jpg
    - build/final_qa_grid_safezones.jpg
    - build/thumbnail.jpg
    - build/thumbnail_2x3_crop.jpg
    - build/qa_report.json
    - build/render_report.json
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
from sutradhar.qa.quality_gate import QualityGateError, run_v2_quality_gate  # noqa: E402
from sutradhar.qa.render_optimizer import (  # noqa: E402
    DEFAULT_MAX_FILE_BYTES,
    RenderOptimizeError,
    render_episode_mp4,
)
from sutradhar.visual.storyboard_composer import (  # noqa: E402
    CompositionError,
    compose_storyboard,
    resolve_v2_episode_inputs,
)
from sutradhar.visual.thumbnail_builder import ThumbnailBuildError, build_thumbnail  # noqa: E402


class RenderPipelineError(RuntimeError):
    """Raised when rendering, audio mixing, thumbnail build, or fail-closed QA fails."""


def run_render_and_qa_pipeline(root: Path) -> dict[str, Any]:
    """Execute the full v2 storyboard composition, thumbnail build, MP4 encode, and QA gate."""
    cfg = load_config(root)
    build_dir = (root / cfg["paths"]["build_dir"]).resolve()
    try:
        plan_data, audio_manifest = resolve_v2_episode_inputs(root, cfg)
        thumb_spec = plan_data.get("thumbnail_spec")
        if not thumb_spec:
            raise RenderPipelineError("v2 episode_plan.json is missing required 'thumbnail_spec'.")

        comp = compose_storyboard(
            root,
            plan_data,
            audio_manifest=audio_manifest,
            output_dir=build_dir / "composition",
            mix_audio=True,
            cfg=cfg,
        )

        final_short = build_dir / "final_short.mp4"
        final_qa_grid = build_dir / "final_qa_grid.jpg"
        final_qa_grid_safezones = build_dir / "final_qa_grid_safezones.jpg"
        thumbnail_path = build_dir / "thumbnail.jpg"
        crop_path = build_dir / "thumbnail_2x3_crop.jpg"
        qa_report_path = build_dir / "qa_report.json"

        thumb_res = build_thumbnail(
            root,
            thumb_spec,
            thumbnail_path,
            crop_output_jpg=crop_path,
        )

        max_file_bytes = int((cfg.get("video") or {}).get("max_file_bytes", DEFAULT_MAX_FILE_BYTES))
        render_metrics = render_episode_mp4(
            root,
            comp.output_dir,
            final_short,
            duration_sec=comp.duration_sec,
            max_file_bytes=max_file_bytes,
        )

        qa_report = run_v2_quality_gate(
            root,
            composition_dir=comp.output_dir,
            mp4_path=final_short,
            thumbnail_jpg=thumbnail_path,
            crop_2x3_jpg=crop_path,
            master_wav_path=comp.master_wav,
            audio_manifest=audio_manifest,
            report_output_path=qa_report_path,
            final_qa_grid_path=final_qa_grid,
            final_qa_grid_safezones_path=final_qa_grid_safezones,
            cfg=cfg,
            max_file_bytes=max_file_bytes,
        )
    except (CompositionError, ThumbnailBuildError, RenderOptimizeError, QualityGateError) as exc:
        raise RenderPipelineError(str(exc)) from exc

    report = {
        "status": "ok",
        "action": "render_and_qa",
        "runtime_version": "v2_storycraft",
        "final_short": "build/final_short.mp4",
        "final_qa_grid_jpg": "build/final_qa_grid.jpg",
        "final_qa_grid_safezones_jpg": "build/final_qa_grid_safezones.jpg",
        "thumbnail_jpg": "build/thumbnail.jpg",
        "thumbnail_2x3_crop_jpg": "build/thumbnail_2x3_crop.jpg",
        "file_bytes": render_metrics["file_bytes"],
        "file_mib": render_metrics["file_mib"],
        "width": render_metrics["width"],
        "height": render_metrics["height"],
        "duration_sec": render_metrics["duration_sec"],
        "kinocut_dark_score": qa_report.motion_and_look_gate["kinocut"]["dark_score"],
        "kinocut_default_score": qa_report.motion_and_look_gate["kinocut"]["default_score"],
        "thumbnail_bytes": thumb_res.file_bytes,
        "v2_quality_gate": qa_report.to_dict(),
    }
    (build_dir / "render_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
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
