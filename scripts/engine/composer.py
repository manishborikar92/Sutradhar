"""Sutradhar Video Engine — Jinja2 Composition Assembler (v4.0).

Generates decoupled, modular HTML5/CSS/JS stage compositions under `build/composition/`
using Jinja2 templates under `templates/composition/`.

Eliminates root code pollution (never writes index.html/styles.css/engine.js to repo root).
Integrates ContinuousLifeEngine and Akshara lip-sync timelines.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader

from .config import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    FPS,
    PUPPET_BASE_HEIGHT,
    PUPPET_BASE_WIDTH,
    PUPPET_TRANSFORM_ORIGIN,
    TWO_SHOT_P1_X,
    TWO_SHOT_P2_X,
    TWO_SHOT_SCALE,
)
from .lipsync_engine import build_lipsync_timeline, generate_gsap_lipsync
from .puppet_rig import (
    ContinuousLifeEngine,
    get_pose,
    get_puppet_wrapper_css,
    validate_pose,
)

logger = logging.getLogger("sutradhar.composer")


class CompositionError(RuntimeError):
    """Raised when composition assembly or asset resolution fails."""


FALLBACK_MANIFEST: dict[str, Any] = {
    "schema_version": "4.0",
    "language": "hi",
    "youtube_title": "कैलाश रहस्य #Shorts",
    "audio": {
        "total_duration_sec": 41.50,
        "sample_rate": 48000,
        "narration_full_path": "build/audio/narration_full.wav",
    },
    "scenes": [
        {
            "scene_index": 1,
            "shot_type": "establishing_wide",
            "backdrop_rig": "golden_lanka_citadel",
            "speaker_role": "narrator",
            "narration_text": "Beneath the golden spires of Lanka, ten crowned heads plotted what no mortal dared imagine.",
            "start_sec": 0.0,
            "end_sec": 7.42,
            "duration_sec": 7.42,
            "camera_motion": "push_in",
        },
        {
            "scene_index": 2,
            "shot_type": "full_two_shot",
            "backdrop_rig": "golden_lanka_citadel",
            "primary_character": "ravana",
            "secondary_character": "shani_dev",
            "speaker_role": "narrator",
            "narration_text": "King Ravana rose in fury, his ten heads burning with supreme defiance across the ancient earth.",
            "start_sec": 7.42,
            "end_sec": 14.85,
            "duration_sec": 7.43,
            "pose_preset": "idle_royal",
            "camera_motion": "push_in",
            "words": [
                {"word": "राजा", "start_sec": 7.5, "end_sec": 8.0},
                {"word": "रावण", "start_sec": 8.1, "end_sec": 8.7},
                {"word": "क्रोध", "start_sec": 9.0, "end_sec": 9.6},
                {"word": "में", "start_sec": 9.7, "end_sec": 10.0},
                {"word": "गर्जना", "start_sec": 10.2, "end_sec": 11.0},
                {"word": "करता", "start_sec": 11.1, "end_sec": 11.7},
                {"word": "है!", "start_sec": 11.8, "end_sec": 12.5},
            ],
        },
        {
            "scene_index": 3,
            "shot_type": "medium_close_up",
            "backdrop_rig": "golden_lanka_citadel",
            "primary_character": "shani_dev",
            "speaker_role": "character_dialogue",
            "narration_text": "Tremble Himalayas! Lanka's sovereign bows to no god!",
            "start_sec": 14.85,
            "end_sec": 22.0,
            "duration_sec": 7.15,
            "pose_preset": "humbled_braced",
            "camera_motion": "push_in",
            "words": [
                {"word": "कर्म", "start_sec": 15.0, "end_sec": 15.6},
                {"word": "का", "start_sec": 15.7, "end_sec": 16.0},
                {"word": "फल", "start_sec": 16.1, "end_sec": 16.7},
                {"word": "अवश्य", "start_sec": 17.0, "end_sec": 17.8},
                {"word": "मिलेगा।", "start_sec": 18.0, "end_sec": 19.0},
            ],
        },
    ],
}


def parse_manifest_js(manifest_path: Path) -> dict[str, Any]:
    """Parses build/manifest.js containing window.EPISODE_MANIFEST = {...}."""
    if not manifest_path.is_file():
        raise CompositionError(f"Manifest not found at {manifest_path}")
    content = manifest_path.read_text(encoding="utf-8")
    match = re.search(r"window\.EPISODE_MANIFEST\s*=\s*(\{.*?\});\s*$", content, re.DOTALL)
    if not match:
        raise CompositionError(f"Failed to parse window.EPISODE_MANIFEST from {manifest_path}")
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise CompositionError(f"Invalid JSON in {manifest_path}: {exc}") from exc


def compose_episode(
    root: Path,
    manifest: Optional[dict[str, Any]] = None,
    output_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """Assembles Jinja2 composition templates into build/composition/.

    Args:
        root: Sutradhar project root directory.
        manifest: Pre-loaded manifest dict. If omitted, loads build/manifest.js.
        output_dir: Target output directory. Defaults to root / "build" / "composition".

    Returns:
        Summary dict containing status, generated file paths, and scene counts.
    """
    root = Path(root).resolve()
    default_root = Path(__file__).resolve().parent.parent.parent

    templates_dir = root / "templates" / "composition"
    if not templates_dir.is_dir():
        templates_dir = default_root / "templates" / "composition"

    assets_dir = root / "assets" / "svg"
    if not assets_dir.is_dir():
        assets_dir = default_root / "assets" / "svg"

    backdrops_dir = assets_dir / "backdrops"
    if not backdrops_dir.is_dir():
        backdrops_dir = default_root / "assets" / "svg" / "backdrops"

    characters_dir = assets_dir / "characters"
    if not characters_dir.is_dir():
        characters_dir = default_root / "assets" / "svg" / "characters"

    if output_dir is None:
        out_dir = root / "build" / "composition"
    else:
        out_dir = Path(output_dir).resolve()

    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Resolve Manifest
    if manifest is None:
        m_path = root / "build" / "manifest.js"
        if m_path.is_file():
            manifest = parse_manifest_js(m_path)
        else:
            manifest = FALLBACK_MANIFEST

    scenes = manifest.get("scenes", [])
    if not scenes:
        raise CompositionError("Manifest contains no scenes to compose.")

    total_duration_sec = float(
        manifest.get("audio", {}).get(
            "total_duration_sec",
            scenes[-1].get("end_sec", 40.0),
        )
    )

    # 2. Setup Jinja2 Environment
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    # 3. Collect Unique Characters & Puppets
    unique_chars: list[str] = []
    for sc in scenes:
        p1 = sc.get("primary_character")
        if p1 and p1 not in unique_chars:
            unique_chars.append(p1)
        p2 = sc.get("secondary_character")
        if p2 and p2 not in unique_chars:
            unique_chars.append(p2)

    puppets_data: list[dict[str, Any]] = []
    life_engine = ContinuousLifeEngine()
    life_engine_snippets: list[str] = []
    lipsync_snippets: list[str] = []

    for idx, c_name in enumerate(unique_chars):
        char_svg_path = characters_dir / f"{c_name}.svg"
        if not char_svg_path.is_file():
            # If named character SVG missing, fallback to sutradhar_narrator or first available
            fallback = next(characters_dir.glob("*.svg"), None)
            if fallback:
                char_svg_path = fallback
            else:
                continue

        svg_content = char_svg_path.read_text(encoding="utf-8")
        wrapper_id = f"puppet_{c_name}"

        # Standard two-shot positioning & 480x960 dimensions
        if idx == 0:
            left_px = TWO_SHOT_P1_X - (PUPPET_BASE_WIDTH // 2)  # Centered at 300px -> left: 60px
            transform = f"scale({TWO_SHOT_SCALE})"
        else:
            left_px = TWO_SHOT_P2_X - (PUPPET_BASE_WIDTH // 2)  # Centered at 740px -> left: 500px
            transform = f"scale({-TWO_SHOT_SCALE}, {TWO_SHOT_SCALE})"  # Flipped facing left

        inline_style = (
            f"top: 460px; left: {left_px}px; "
            f"width: {PUPPET_BASE_WIDTH}px; height: {PUPPET_BASE_HEIGHT}px; "
            f"transform-origin: {PUPPET_TRANSFORM_ORIGIN}; transform: {transform};"
        )

        puppets_data.append(
            {
                "wrapper_id": wrapper_id,
                "character_name": c_name,
                "svg": svg_content,
                "inline_style": inline_style,
            }
        )

        # Generate ContinuousLifeEngine GSAP for this puppet
        life_engine_snippets.append(life_engine.generate_gsap_code(wrapper_id, total_duration_sec))

        # Collect word timestamps spoken by this character across scenes for Akshara lip-sync
        char_words: list[dict[str, Any]] = []
        for sc in scenes:
            speaker = sc.get("primary_character") or sc.get("speaker_role")
            if speaker == c_name or (idx == 0 and speaker in ("narrator", None)):
                for w in sc.get("words", []):
                    char_words.append(w)

        if char_words:
            emotion = scenes[0].get("emotion", "calm")
            tl = build_lipsync_timeline(char_words, emotion=emotion)
            lipsync_snippets.append(generate_gsap_lipsync(tl, wrapper_id))

    # 4. Process Shots & Backdrops
    shots_data: list[dict[str, Any]] = []
    word_cues_data: list[dict[str, Any]] = []

    for sc_idx, sc in enumerate(scenes):
        shot_id = str(sc.get("scene_index", sc_idx + 1))
        shot_type = sc.get("shot_type", "medium_shot")
        bg_name = sc.get("backdrop_rig") or "golden_lanka_citadel"
        bg_file = backdrops_dir / f"{bg_name}.svg"

        if not bg_file.is_file():
            fallback_bg = next(backdrops_dir.glob("*.svg"), None)
            bg_svg = fallback_bg.read_text(encoding="utf-8") if fallback_bg else "<svg></svg>"
        else:
            bg_svg = bg_file.read_text(encoding="utf-8")

        # Poses
        pose_name = sc.get("pose_preset") or "idle_royal"
        primary_pose = get_pose(pose_name)
        # Validate pose strictly
        valid_p1_pose = validate_pose(primary_pose, clamp=True)

        p2_pose_name = sc.get("secondary_pose_preset") or "humbled_braced"
        valid_p2_pose = validate_pose(get_pose(p2_pose_name), clamp=True)

        shots_data.append(
            {
                "shot_id": shot_id,
                "shot_type": shot_type,
                "start_sec": round(float(sc.get("start_sec", 0.0)), 3),
                "end_sec": round(float(sc.get("end_sec", 0.0)), 3),
                "duration_sec": round(float(sc.get("duration_sec", 0.0)), 3),
                "camera_motion": sc.get("camera_motion", "push_in"),
                "backdrop_svg": bg_svg,
                "foreground_svg": None,
                "primary_character": sc.get("primary_character"),
                "primary_pose_json": json.dumps(valid_p1_pose),
                "secondary_character": sc.get("secondary_character"),
                "secondary_pose_json": json.dumps(valid_p2_pose),
            }
        )

        # Word Subtitle Cues
        for w in sc.get("words", []):
            word_cues_data.append(
                {
                    "word": w.get("word", ""),
                    "start_sec": round(float(w.get("start_sec", 0.0)), 3),
                    "end_sec": round(float(w.get("end_sec", 0.0)), 3),
                    "is_keyword": bool(w.get("is_keyword", False)),
                    "line_index": sc_idx,
                }
            )

    # 5. Render Templates
    tpl_index = env.get_template("index.html.jinja2")
    tpl_styles = env.get_template("styles.css.jinja2")
    tpl_engine = env.get_template("engine.js.jinja2")

    render_ctx = {
        "language": manifest.get("language", "hi"),
        "youtube_title": manifest.get("youtube_title", "Sutradhar Episode"),
        "total_duration_sec": total_duration_sec,
        "audio_path": "../../build/audio/narration_full.wav",
        "shots": shots_data,
        "puppets": puppets_data,
        "props": [],
        "vfx_elements": [],
        "word_cues": word_cues_data,
        "life_engine_code": "\n".join(life_engine_snippets),
        "lipsync_code": "\n".join(lipsync_snippets),
    }

    index_out = out_dir / "index.html"
    styles_out = out_dir / "styles.css"
    engine_out = out_dir / "engine.js"

    gsap_src = default_root / "node_modules" / "gsap" / "dist" / "gsap.min.js"
    if gsap_src.is_file():
        shutil.copy2(gsap_src, out_dir / "gsap.min.js")

    index_out.write_text(tpl_index.render(render_ctx), encoding="utf-8")
    styles_out.write_text(tpl_styles.render(render_ctx), encoding="utf-8")
    engine_out.write_text(tpl_engine.render(render_ctx), encoding="utf-8")

    logger.info("Assembled modular composition to %s", out_dir)

    return {
        "status": "ok",
        "composition_dir": str(out_dir),
        "index_path": str(index_out),
        "styles_path": str(styles_out),
        "engine_path": str(engine_out),
        "scenes_count": len(shots_data),
        "characters": unique_chars,
        "duration_sec": total_duration_sec,
        "total_duration_sec": total_duration_sec,
    }


def generate_composition(root: Optional[Path] = None) -> dict[str, Any]:
    """Zero-argument / default entrypoint for composition assembly."""
    if root is None:
        root = Path(__file__).resolve().parent.parent.parent
    return compose_episode(root)


if __name__ == "__main__":
    proj_root = Path(__file__).resolve().parent.parent.parent
    res = generate_composition(proj_root)
    print(f"[INFO] Composition generated at {res['composition_dir']} ({res['scenes_count']} shots, {len(res['characters'])} puppets)")
