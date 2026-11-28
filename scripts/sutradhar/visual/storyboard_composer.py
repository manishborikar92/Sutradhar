"""Pre-render StoryboardIR compiler for Sutradhar v2 Canvas2D/HyperFrames runtime."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from sutradhar.audio.caption_builder import build_caption_cues, write_captions_data_js
from sutradhar.audio.elevenlabs_tts import (
    DEFAULT_TAG_TEMPLATES,
    apply_pronunciations_preserving_tags,
    load_pronunciations,
    prepare_scene_tts_text,
    strip_audio_tags,
)
from sutradhar.audio.sound_mixer import mix_episode_audio
from sutradhar.audio.whisper_aligner import write_text_atomic
from sutradhar.config import load_config
from sutradhar.models import (
    EpisodePlan,
    EpisodePlanV2,
    StoryboardIR,
    count_billed_chars,
)

# Grounding & safety geometry constants (1080x1920 vertical Shorts canvas)
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1920
GROUND_TOLERANCE_PX = 6.0
DEFAULT_DAIS_HEIGHT = 98
LOTUS_DAIS_HEIGHT = 54
CAPTION_SAFE_BOTTOM_MAX = 1395
SHORTS_PILL_MIN_X = 48
SHORTS_PILL_MAX_X = 888
SHORTS_PILL_MIN_Y = 288
SHORTS_PILL_MAX_Y = 1248

# Normalize model default labels to character_engine.js canonical tokens
POSE_ALIASES: dict[str, str] = {
    "standing_hero": "neutral",
    "standing": "neutral",
    "hero": "neutral",
    "calm_standing": "neutral",
    "meditating": "neutral",
    "meditate": "neutral",
    "padmasana": "neutral",
}

SEATED_POSES: set[str] = {"meditating", "meditate", "padmasana"}

EXPR_ALIASES: dict[str, str] = {
    "calm": "serene",
    "peaceful": "serene",
    "angry": "determined",
    "wrath": "determined",
    "happy": "smile",
    "shocked": "fear",
}

ENGINE_POSES: set[str] = {
    "neutral",
    "namaskar",
    "gesture",
    "palm_cup",
    "drink",
    "shield",
    "pull",
    "bless",
    "clasp",
    "awed",
    "throat_reach",
    "veena_play",
    "strum",
}

ENGINE_EXPRS: set[str] = {"serene", "smile", "determined", "compassionate", "fear"}

TRANSITION_MAP: dict[str, str] = {
    "fade": "crossfade",
    "crossfade": "crossfade",
    "iris": "iris",
    "whip": "whip",
    "cut": "cut",
    "dissolve": "crossfade",
    "wipe_left": "whip",
    "wipe_right": "whip",
    "flash_cut": "cut",
}

ENGINE_PROP_ALIASES: set[str] = {"kalachakra", "iron_pillar", "cosmic_ocean"}

OCEAN_TERRAIN_PROPS: set[str] = {
    "samudra_manthan_halahala",
    "mount_mandara",
    "kurma_avatar",
    "vasuki_serpent",
    "cosmic_ocean",
}

AERIAL_CENTERED_PROPS: set[str] = {
    "brass_clock",
    "halahala_orb",
    "brahmaloka_time_chakra",
    "kalachakra",
    "earth_globe",
    "magnifying_sector_lens",
    "spacetime_comparator",
    "shani_drishti_mandala",
}

CAMERA_MOVE_PARAMS: dict[str, dict[str, float]] = {
    "static": {"base_zoom": 1.032, "amp_zoom": 0.008, "drift_zoom": 0.018, "pan_amp_x": 14.0},
    "slow_push_in": {"base_zoom": 1.055, "amp_zoom": 0.014, "drift_zoom": 0.048, "pan_amp_x": 27.0},
    "slow_pull_out": {"base_zoom": 1.080, "amp_zoom": 0.014, "drift_zoom": -0.042, "pan_amp_x": 27.0},
    "pan_left": {"base_zoom": 1.058, "amp_zoom": 0.014, "drift_zoom": 0.040, "pan_amp_x": 28.0},
    "pan_right": {"base_zoom": 1.058, "amp_zoom": 0.014, "drift_zoom": 0.040, "pan_amp_x": -28.0},
    "drift": {"base_zoom": 1.055, "amp_zoom": 0.015, "drift_zoom": 0.046, "pan_amp_x": 26.0},
}


class CompositionError(RuntimeError):
    """Raised when StoryboardIR, plan parity, presets, or grounding fail validation."""


@dataclass
class CompiledComposition:
    """Result returned after compiling a StoryboardIR composition bundle."""

    output_dir: Path
    index_html: Path
    captions_html: Path
    captions_data_js: Path
    master_wav: Optional[Path]
    compiled_metadata_json: Path
    duration_sec: float
    scene_count: int
    episode_runtime: dict[str, Any]
    grounding_report: list[dict[str, Any]] = field(default_factory=list)
    audio_mix_report: dict[str, Any] = field(default_factory=dict)


def parse_manifest_js(manifest_path: Path) -> dict[str, Any]:
    """Parse ``window.EPISODE_MANIFEST = {...};``, ``MANIFEST_DATA = {...};``, or raw JSON."""
    if not manifest_path.is_file():
        raise CompositionError(f"Missing manifest file at '{manifest_path}'. Run build_audio.py first.")
    raw = manifest_path.read_text(encoding="utf-8").strip()
    match = re.search(
        r"(?:window\.)?(?:EPISODE_MANIFEST|MANIFEST_DATA)\s*=\s*(\{.*\});?\s*$",
        raw,
        re.DOTALL,
    )
    payload_str = match.group(1) if match else raw
    if not payload_str.startswith("{"):
        raise CompositionError(f"Failed to parse manifest object from '{manifest_path}'.")
    try:
        data = json.loads(payload_str)
    except json.JSONDecodeError as exc:
        raise CompositionError(f"Invalid JSON in '{manifest_path}': {exc}") from exc
    if not isinstance(data, dict):
        raise CompositionError(f"Manifest root must be a JSON object: {manifest_path}")
    return data


def detect_v2_storyboard_run(root: Path, cfg: dict[str, Any]) -> bool:
    """Return True when build artifacts represent a v2 Canvas2D/StoryboardIR episode."""
    build_dir = (Path(root) / cfg["paths"]["build_dir"]).resolve()
    plan_path = build_dir / "episode_plan.json"
    if plan_path.is_file():
        try:
            plan_data = json.loads(plan_path.read_text(encoding="utf-8"))
            if isinstance(plan_data, dict):
                return plan_data.get("storyboard_ir") is not None
        except Exception:
            pass
    compiled_path = build_dir / "composition" / "storyboard_compiled.json"
    if compiled_path.is_file():
        return True
    manifest_js = build_dir / "manifest.js"
    if manifest_js.is_file():
        try:
            m = parse_manifest_js(manifest_js)
            if m.get("storyboard_ir") is not None or m.get("visual_direction_version") == "v2_storycraft":
                return True
        except Exception:
            pass
    return False


def resolve_v2_episode_inputs(root: Path, cfg: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load EpisodePlanV2 dict and Phase 3 audio_manifest dict from build_dir."""
    build_dir = (Path(root) / cfg["paths"]["build_dir"]).resolve()
    plan_path = build_dir / "episode_plan.json"
    if not plan_path.is_file():
        raise CompositionError(f"Missing v2 episode_plan.json at '{plan_path}'.")
    plan_data = json.loads(plan_path.read_text(encoding="utf-8"))

    audio_manifest_path = build_dir / "audio" / "audio_manifest.json"
    if audio_manifest_path.is_file():
        audio_manifest = json.loads(audio_manifest_path.read_text(encoding="utf-8"))
    elif (build_dir / "manifest.js").is_file():
        audio_manifest = parse_manifest_js(build_dir / "manifest.js")
    else:
        raise CompositionError(f"Missing Phase 3 audio_manifest.json at '{audio_manifest_path}'.")
    return plan_data, audio_manifest


def _load_preset_dir(directory: Path, label: str) -> dict[str, dict[str, Any]]:
    if not directory.is_dir():
        raise CompositionError(f"Asset {label} directory not found: {directory}")
    presets: dict[str, dict[str, Any]] = {}
    for p in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:
            raise CompositionError(f"Invalid {label} preset JSON {p}: {exc}") from exc
        if not isinstance(payload, dict):
            raise CompositionError(f"{label} preset must be a JSON object: {p}")
        presets[p.stem] = payload
    return presets


def load_asset_registry(root: Path) -> dict[str, Any]:
    """Load v2 asset manifest and JSON presets for environments, characters, and props."""
    manifest_path = root / "assets" / "manifest.yaml"
    if not manifest_path.is_file():
        raise CompositionError(f"Asset manifest not found: {manifest_path}")
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise CompositionError("assets/manifest.yaml must be a mapping")
    schema_version = str(manifest.get("schema_version", ""))
    if not schema_version.startswith("2."):
        raise CompositionError(
            f"Unsupported assets/manifest.yaml schema_version={schema_version!r} (expected 2.x)"
        )
    runtime_cfg = manifest.get("runtime") or {}
    for key in ("shell_template", "stylesheet", "captions_template", "thumbnail_template"):
        rel = runtime_cfg.get(key)
        if not rel or not (root / rel).is_file():
            raise CompositionError(f"Missing required runtime asset for {key}: {rel!r}")
    for mod in runtime_cfg.get("modules") or []:
        if not (root / mod).is_file():
            raise CompositionError(f"Missing required runtime JS module: {mod}")

    return {
        "manifest": manifest,
        "environments": _load_preset_dir(root / "assets" / "environments", "environments"),
        "characters": _load_preset_dir(root / "assets" / "characters", "characters"),
        "props": _load_preset_dir(root / "assets" / "props", "props"),
        "runtime": runtime_cfg,
    }


def _coerce_episode_plan(plan: EpisodePlanV2 | EpisodePlan | dict[str, Any]) -> EpisodePlanV2:
    if isinstance(plan, (EpisodePlanV2, EpisodePlan)):
        data = plan.model_dump()
    elif isinstance(plan, dict):
        data = dict(plan)
    else:
        raise CompositionError(f"Unsupported episode_plan type: {type(plan).__name__}")
    try:
        return EpisodePlanV2.model_validate(data)
    except Exception as exc:
        raise CompositionError(f"EpisodePlan validation failed: {exc}") from exc


def _load_audio_manifest(audio_manifest: dict[str, Any] | Path) -> dict[str, Any]:
    if isinstance(audio_manifest, Path):
        if not audio_manifest.is_file():
            raise CompositionError(f"Audio manifest file not found: {audio_manifest}")
        try:
            data = json.loads(audio_manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CompositionError(f"Invalid audio manifest JSON {audio_manifest}: {exc}") from exc
    elif isinstance(audio_manifest, dict):
        data = dict(audio_manifest)
    else:
        raise CompositionError(f"Unsupported audio_manifest type: {type(audio_manifest).__name__}")
    if not isinstance(data.get("scenes"), list) or not data["scenes"]:
        raise CompositionError("audio_manifest must contain a non-empty 'scenes' list")
    return data


def _load_or_build_captions(
    captions: list[dict[str, Any]] | Path | None,
    audio_manifest: dict[str, Any],
    plan: EpisodePlanV2,
    total_duration: float,
) -> list[dict[str, Any]]:
    if isinstance(captions, Path):
        if not captions.is_file():
            raise CompositionError(f"Captions file not found: {captions}")
        raw = captions.read_text(encoding="utf-8").strip()
        raw = re.sub(r"^(?:window\.)?CAPTIONS_DATA\s*=\s*", "", raw, count=1)
        if raw.endswith(";"):
            raw = raw[:-1].strip()
        parsed = json.loads(raw)
        if not isinstance(parsed, list):
            raise CompositionError(f"Captions data must be a JSON list: {captions}")
        cues = parsed
    elif isinstance(captions, list):
        cues = list(captions)
    elif captions is None:
        story_kws = [sc.emphasis_word for sc in plan.scenes if sc.emphasis_word]
        cues = build_caption_cues(
            audio_manifest["scenes"],
            total_duration,
            story_keywords=story_kws,
        )
    else:
        raise CompositionError(f"Unsupported captions type: {type(captions).__name__}")

    if not cues:
        raise CompositionError("Compiled composition requires non-empty caption cues")

    normalized: list[dict[str, Any]] = []
    for cue in cues:
        words_norm = []
        for w in cue.get("words") or []:
            tok = str(w.get("word") if w.get("word") is not None else w.get("text", "")).strip()
            if not tok:
                continue
            words_norm.append(
                {
                    "text": tok,
                    "word": tok,
                    "start": float(w.get("start", cue.get("start", 0.0))),
                    "end": float(w.get("end", cue.get("end", 0.0))),
                    "kw": bool(w.get("kw", False)),
                }
            )
        if words_norm:
            normalized.append(
                {
                    "start": float(cue.get("start", words_norm[0]["start"])),
                    "end": float(cue.get("end", words_norm[-1]["end"])),
                    "words": words_norm,
                }
            )
    if not normalized:
        raise CompositionError("No valid caption words remain after normalization")
    return normalized


def verify_plan_audio_parity(
    plan: EpisodePlanV2,
    audio_manifest: dict[str, Any],
    *,
    root: Path | None = None,
    cfg: dict[str, Any] | None = None,
) -> tuple[StoryboardIR, float]:
    """Fail closed on any mismatch between EpisodePlan, StoryboardIR, and audio manifest."""
    if plan.storyboard_ir is None:
        raise CompositionError("EpisodePlanV2.storyboard_ir is required for v2 composition")
    ir = plan.storyboard_ir
    if (ir.width, ir.height, ir.fps) != (CANVAS_WIDTH, CANVAS_HEIGHT, 30):
        raise CompositionError(
            f"StoryboardIR geometry must be 1080x1920@30fps, got {ir.width}x{ir.height}@{ir.fps}"
        )

    plan_scenes = plan.scenes
    ir_scenes = ir.scenes
    audio_scenes = audio_manifest["scenes"]
    if not (len(plan_scenes) == len(ir_scenes) == len(audio_scenes)):
        raise CompositionError(
            f"Plan-before-render scene count mismatch: plan={len(plan_scenes)}, "
            f"storyboard_ir={len(ir_scenes)}, audio_manifest={len(audio_scenes)}"
        )

    text_reps: dict[str, str] = {}
    tag_templates = DEFAULT_TAG_TEMPLATES
    if root is not None:
        resolved_cfg = cfg if cfg is not None else load_config(Path(root))
        lang = getattr(plan, "audio_language", None) or getattr(plan, "language", "hi") or "hi"
        text_reps = load_pronunciations(Path(root), resolved_cfg, lang=lang)
        tag_templates = (resolved_cfg.get("tts") or {}).get("tag_templates") or DEFAULT_TAG_TEMPLATES
    climax_idx = getattr(getattr(plan, "story_arc", None), "climax_scene_index", None)

    sum_dur = 0.0
    total_scenes = len(plan_scenes)
    for idx, (psc, asc) in enumerate(zip(plan_scenes, audio_scenes)):
        a_idx = asc.get("scene_index")
        if a_idx is not None and int(a_idx) != int(psc.scene_index):
            raise CompositionError(
                f"Scene {idx} index mismatch: plan={psc.scene_index}, audio={a_idx}"
            )
        dur = float(asc.get("duration_sec", 0.0))
        if dur <= 0.0:
            raise CompositionError(f"Scene {idx} audio duration_sec must be > 0, got {dur}")
        sum_dur += dur

        a_speed_raw = asc.get("speed") if asc.get("speed") is not None else asc.get("applied_speed")
        if a_speed_raw is not None:
            a_speed = float(a_speed_raw)
            if psc.speed is not None:
                if abs(a_speed - float(psc.speed)) > 0.015:
                    raise CompositionError(
                        f"Scene {idx} spoken speed mismatch: plan={psc.speed}, audio={a_speed}"
                    )
            elif not (0.5 <= a_speed <= 1.5):
                raise CompositionError(
                    f"Scene {idx} applied_speed {a_speed} outside valid [0.5, 1.5] bounds"
                )

        if asc.get("narration_text") is not None:
            plan_clean = strip_audio_tags(psc.narration_text).strip()
            aud_clean = strip_audio_tags(str(asc["narration_text"])).strip()
            if plan_clean and aud_clean != plan_clean:
                raise CompositionError(
                    f"Scene {idx} narration text mismatch between plan and audio_manifest"
                )

        if asc.get("billed_chars") is not None:
            raw_chars = count_billed_chars([psc])
            clean_text, prepared_tts = prepare_scene_tts_text(
                psc,
                idx,
                total_scenes,
                text_reps,
                tag_templates,
                is_climax_scene=(climax_idx == psc.scene_index),
            )
            actual_chars = int(asc["billed_chars"])
            tts_text = asc.get("tts_text_applied") or asc.get("synth_text")
            if tts_text is not None:
                tts_str = str(tts_text)
                if actual_chars != len(tts_str):
                    raise CompositionError(
                        f"Scene {idx} narration char count mismatch: "
                        f"prepared_text={len(tts_str)}, audio={actual_chars}"
                    )
                stripped_tts = strip_audio_tags(tts_str).strip()
                expected_phonetic = apply_pronunciations_preserving_tags(clean_text, text_reps).strip()
                if stripped_tts not in (clean_text, expected_phonetic):
                    # Allow legacy/custom pronunciation substitution only when token overlap is high
                    clean_toks = set(clean_text.split())
                    tts_toks = set(stripped_tts.split())
                    overlap = len(clean_toks & tts_toks) / max(1, len(clean_toks))
                    if overlap < 0.70:
                        raise CompositionError(
                            f"Scene {idx} tts_text_applied diverges from plan narration (overlap={overlap:.2f})"
                        )
            elif actual_chars not in (raw_chars, len(prepared_tts)):
                raise CompositionError(
                    f"Scene {idx} narration char count mismatch: plan={raw_chars}, "
                    f"prepared={len(prepared_tts)}, audio={actual_chars}"
                )

    total_duration = float(
        audio_manifest.get("total_duration_sec")
        or (audio_manifest.get("audio") or {}).get("total_duration_sec")
        or sum_dur
    )
    if total_duration <= 0.0:
        raise CompositionError(f"Total audio duration must be > 0, got {total_duration}")
    if abs(total_duration - sum_dur) > 0.15:
        raise CompositionError(
            f"Audio total_duration_sec ({total_duration:.3f}s) diverges from scene sum ({sum_dur:.3f}s)"
        )
    return ir, total_duration


def _find_or_add_dais(
    stage_elements: list[dict[str, Any]],
    x: float,
    floor_y: int,
    *,
    height: int = DEFAULT_DAIS_HEIGHT,
    cushion: bool = False,
) -> float:
    for st in stage_elements:
        if st.get("type") == "royal_music_stage" and abs(float(st.get("x", 540.0)) - x) <= 140.0:
            return float(st.get("daisBot", 1218)) - 92.0
        if st.get("type") == "dais" and abs(float(st.get("x", 540.0)) - x) <= 120.0:
            if cushion:
                st["cushion"] = True
            return float(st.get("floorY", floor_y)) - float(st.get("h", DEFAULT_DAIS_HEIGHT))
    stage_elements.append(
        {
            "type": "dais",
            "x": round(float(x), 1),
            "floorY": floor_y,
            "w": 390,
            "h": height,
            "cushion": cushion,
        }
    )
    return float(floor_y - height)


def _find_dais_top_only(stage_elements: list[dict[str, Any]], x: float) -> Optional[float]:
    for st in stage_elements:
        if st.get("type") == "royal_music_stage" and abs(float(st.get("x", 540.0)) - x) <= 140.0:
            return float(st.get("daisBot", 1218)) - 92.0
        if st.get("type") == "dais" and abs(float(st.get("x", 540.0)) - x) <= 120.0:
            return float(st.get("floorY", 1142)) - float(st.get("h", DEFAULT_DAIS_HEIGHT))
    return None


def _build_env_dict(env_preset: dict[str, Any], sc_vis: Any, horizon_y: int) -> dict[str, Any]:
    env_id = env_preset["id"]
    env: dict[str, Any] = {
        "preset_id": env_id,
        "atmosphere_mode": sc_vis.atmosphere_mode,
        "horizon_y": horizon_y,
    }
    for opt in ("palette", "sky", "sun", "terrain", "grid", "stars_alpha", "motes_color", "has_diyas", "include_curtains", "ground_top", "ground_bot"):
        if opt in env_preset:
            val = env_preset[opt]
            env[opt] = dict(val) if isinstance(val, dict) else val

    overrides = getattr(sc_vis, "environment_overrides", None)
    if isinstance(overrides, dict) and overrides:
        palette_keys = {"wall_top", "wall_bot", "dado_top", "floor_a", "floor_b", "curtain", "carpet"}
        for ok, ov in overrides.items():
            if ok == "palette" and isinstance(ov, dict):
                env["palette"] = {**(env.get("palette") or {}), **ov}
            elif ok in palette_keys:
                env["palette"] = {**(env.get("palette") or {}), ok: ov}
            elif ok not in ("preset_id", "horizon_y"):
                env[ok] = dict(ov) if isinstance(ov, dict) else ov

    if env_id == "kailash_horizon":
        env.setdefault("has_kailash", True)
        env.setdefault("flora", True)
        env.setdefault("snow_boulders", True)
        env.setdefault("ridge_set", "kailash")
    elif env_id == "ashram_twilight":
        env.setdefault("flora", True)
        env.setdefault("snow_boulders", False)
        env.setdefault("ridge_set", "kailash")
    elif env_id == "cosmic_ocean_manthan":
        env.setdefault("flora", False)
        env.setdefault("snow_boulders", False)
        env.setdefault("ridge_set", False)
    elif env_id == "observatory_cosmos":
        env.setdefault("flora", False)
        env.setdefault("snow_boulders", False)
        env.setdefault("ridge_set", "cosmos")
    return env


def _normalize_pose_and_expr(
    raw_pose: str,
    raw_expr: str,
    char_preset: dict[str, Any],
    role: str,
    scene_idx: int,
) -> tuple[str, str, bool]:
    pose_key = raw_pose.strip()
    seated = pose_key in SEATED_POSES
    norm_pose = POSE_ALIASES.get(pose_key, pose_key)
    supported_poses = set(char_preset.get("supported_poses") or ENGINE_POSES)
    if norm_pose not in ENGINE_POSES or norm_pose not in supported_poses:
        raise CompositionError(
            f"Scene {scene_idx} character {role!r} uses unsupported pose {raw_pose!r} "
            f"(supported={sorted(supported_poses)})"
        )

    expr_key = raw_expr.strip()
    norm_expr = EXPR_ALIASES.get(expr_key, expr_key)
    supported_exprs = set(char_preset.get("supported_expressions") or ENGINE_EXPRS)
    if norm_expr not in ENGINE_EXPRS or norm_expr not in supported_exprs:
        raise CompositionError(
            f"Scene {scene_idx} character {role!r} uses unsupported expr {raw_expr!r} "
            f"(supported={sorted(supported_exprs)})"
        )
    return norm_pose, norm_expr, seated


def _resolve_prop_key(raw_id: str, raw_kind: str, prop_presets: dict[str, dict[str, Any]], scene_idx: int) -> str:
    known = set(prop_presets.keys()) | ENGINE_PROP_ALIASES
    if raw_id in known:
        return raw_id
    if raw_kind in known:
        return raw_kind
    raise CompositionError(
        f"Scene {scene_idx} references unknown prop id={raw_id!r}, kind={raw_kind!r}"
    )


def _compile_scene_visuals(
    scene_idx: int,
    sc_vis: Any,
    sc_plan: Any,
    s0: float,
    s1: float,
    registry: dict[str, Any],
    *,
    enable_contextual_pills: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    env_presets = registry["environments"]
    char_presets = registry["characters"]
    prop_presets = registry["props"]

    env_id = sc_vis.environment_preset
    if env_id not in env_presets:
        raise CompositionError(f"Scene {scene_idx} references unknown environment_preset={env_id!r}")
    env_preset = env_presets[env_id]
    preset_mode = env_preset.get("atmosphere_mode")
    if preset_mode and preset_mode != sc_vis.atmosphere_mode:
        raise CompositionError(
            f"Scene {scene_idx} atmosphere_mode {sc_vis.atmosphere_mode!r} conflicts with "
            f"environment_preset {env_id!r} ({preset_mode!r})"
        )

    horizon_y = int(sc_vis.horizon_y)
    if not (850 <= horizon_y <= 1500):
        raise CompositionError(f"Scene {scene_idx} horizon_y={horizon_y} outside [850, 1500]")

    stage_elements: list[dict[str, Any]] = []
    if env_id in ("brahmaloka_sabha", "dwaraka_durbar", "lanka_citadel"):
        stage_elements.extend(
            [
                {"type": "pillar", "x": 115, "floorY": horizon_y, "topY": 0, "w": 68},
                {"type": "pillar", "x": 965, "floorY": horizon_y, "topY": 0, "w": 68},
            ]
        )

    grounding_checks: list[dict[str, Any]] = []

    # Resolve characters & ground supports first so dais placements exist for props/telemetry
    runtime_chars: list[dict[str, Any]] = []
    for ch in sc_vis.characters:
        # Support lookup by role first, then fall back to character id
        if ch.role in char_presets:
            preset_key = ch.role
        elif ch.id in char_presets:
            preset_key = ch.id
        else:
            raise CompositionError(f"Scene {scene_idx} references unknown character role={ch.role!r} id={ch.id!r}")
        c_preset = char_presets[preset_key]
        if not (90.0 <= float(ch.x) <= 990.0):
            raise CompositionError(
                f"Scene {scene_idx} character {ch.role!r} x={ch.x} clipped outside safe horizontal margin [90, 990]"
            )
        norm_pose, norm_expr, pose_seated = _normalize_pose_and_expr(
            ch.pose, ch.expr, c_preset, preset_key, scene_idx
        )
        seated = bool(ch.seated) if getattr(ch, "seated", None) is not None else pose_seated
        default_scale = float((c_preset.get("proportions") or {}).get("defaultScale", 1.0))

        if ch.surface_type == "dais":
            support_top_y = _find_or_add_dais(stage_elements, float(ch.x), horizon_y, height=DEFAULT_DAIS_HEIGHT, cushion=seated)
            support_kind = "dais"
        elif ch.surface_type == "lotus":
            seated = True
            support_top_y = _find_or_add_dais(stage_elements, float(ch.x), horizon_y, height=LOTUS_DAIS_HEIGHT, cushion=True)
            support_kind = "lotus"
        elif ch.surface_type in ("floor", "terrain", "rock"):
            support_top_y = float(horizon_y)
            support_kind = ch.surface_type
        else:
            raise CompositionError(f"Scene {scene_idx} invalid surface_type={ch.surface_type!r}")

        foot_y = support_top_y
        delta_px = abs(foot_y - support_top_y)
        speaking = (
            (sc_plan.speaker_role == "character_dialogue" and preset_key == sc_plan.primary_character)
            or (
                sc_plan.speaker_role == "narrator"
                and (preset_key == "sutradhar_narrator" or preset_key == sc_plan.primary_character or len(runtime_chars) == 0)
            )
        )

        ch_dict: dict[str, Any] = {
            "id": preset_key,
            "instance_id": ch.id,
            "role": preset_key,
            "x": round(float(ch.x), 2),
            "y": round(foot_y, 2),
            "scale": round(default_scale, 3),
            "pose": norm_pose,
            "expr": norm_expr,
            "turn": float(ch.turn),
            "seated": seated,
            "speaking": bool(speaking),
            "surface_type": ch.surface_type,
        }
        if preset_key == "shiva" and norm_pose == "palm_cup":
            ch_dict["halahalaInHand"] = 0.9
        if preset_key == "shiva" and (
            norm_pose == "drink" or "नीलकंठ" in str(getattr(sc_plan, "narration_text", ""))
        ):
            ch_dict["neelakantha"] = 1.0
        if ch.gaze_target:
            ch_dict["gaze_target"] = ch.gaze_target
        runtime_chars.append(ch_dict)
        grounding_checks.append(
            {
                "scene_index": scene_idx,
                "entity": "character",
                "id": ch.id,
                "role": ch.role,
                "surface_type": support_kind,
                "x": float(ch.x),
                "footY": foot_y,
                "support_top_y": support_top_y,
                "delta_px": round(delta_px, 3),
                "grounded": delta_px <= GROUND_TOLERANCE_PX,
            }
        )

    # Resolve props & grounding checks
    runtime_props: list[dict[str, Any]] = []
    for p in sc_vis.props:
        canonical = _resolve_prop_key(p.id, p.kind, prop_presets, scene_idx)
        if not (48.0 <= float(p.x) <= 1032.0):
            raise CompositionError(
                f"Scene {scene_idx} prop {p.id!r} x={p.x} clipped outside safe horizontal margin [48, 1032]"
            )
        mount = p.mount
        explicit_y = float(p.y) if p.y is not None else None
        prop_dict: dict[str, Any] = {
            "id": canonical,
            "instance_id": p.id,
            "x": round(float(p.x), 2),
            "scale": round(float(p.scale), 3),
            "mount": mount,
        }
        if getattr(p, "params", None):
            prop_dict["params"] = dict(p.params)
            for pk, pv in p.params.items():
                if pk not in ("id", "instance_id", "x", "y", "floorY", "r", "mount", "scale"):
                    prop_dict[pk] = pv

        if mount == "sky" or (
            canonical in AERIAL_CENTERED_PROPS
            and mount == "pedestal"
            and (explicit_y is None or explicit_y < horizon_y - 200)
        ):
            py = explicit_y if explicit_y is not None else 540.0
            if not (80.0 <= py <= horizon_y - 60.0):
                raise CompositionError(
                    f"Scene {scene_idx} sky/aerial prop {p.id!r} y={py} outside aerial band [80, {horizon_y - 60}]"
                )
            if canonical == "brass_clock" and not any(st.get("type") == "clock_niche" for st in stage_elements):
                stage_elements.append({"type": "clock_niche", "x": round(float(p.x), 1), "y": round(py, 1), "r": 135})
            prop_dict["y"] = round(py, 2)
            prop_dict["r"] = round(128.0 * float(p.scale), 1)
            support_top_y = py
            delta_px = 0.0
        elif mount == "dais":
            dais_top = _find_dais_top_only(stage_elements, float(p.x))
            if dais_top is None:
                dais_top = _find_or_add_dais(stage_elements, float(p.x), horizon_y, height=DEFAULT_DAIS_HEIGHT)
            py = explicit_y if explicit_y is not None else dais_top
            delta_px = abs(py - dais_top)
            if delta_px > GROUND_TOLERANCE_PX:
                raise CompositionError(
                    f"Scene {scene_idx} dais prop {p.id!r} y={py} is {delta_px:.1f}px from dais top {dais_top}"
                )
            prop_dict["y"] = round(py, 2)
            prop_dict["floorY"] = round(py, 2)
            support_top_y = dais_top
        elif mount in ("floor", "table", "pedestal"):
            if mount == "pedestal":
                # Pedestal props get elevated placement on a dais
                dais_top = _find_dais_top_only(stage_elements, float(p.x))
                if dais_top is None:
                    dais_top = _find_or_add_dais(stage_elements, float(p.x), horizon_y, height=DEFAULT_DAIS_HEIGHT)
                support_top_y = dais_top
            else:
                support_top_y = float(horizon_y)
            py = explicit_y if explicit_y is not None else support_top_y
            delta_px = abs(py - support_top_y)
            if delta_px > GROUND_TOLERANCE_PX:
                raise CompositionError(
                    f"Scene {scene_idx} grounded prop {p.id!r} ({mount}) y={py} is {delta_px:.1f}px from support {support_top_y}"
                )
            prop_dict["y"] = round(py, 2)
            prop_dict["floorY"] = round(py, 2)
        elif mount == "terrain":
            if canonical in OCEAN_TERRAIN_PROPS:
                support_top_y = float(horizon_y - 137)
                py = explicit_y if explicit_y is not None else support_top_y
                if not (horizon_y - 190 <= py <= horizon_y + 12):
                    raise CompositionError(
                        f"Scene {scene_idx} ocean terrain prop {p.id!r} y={py} outside [{horizon_y - 190}, {horizon_y + 12}]"
                    )
                delta_px = 0.0
            else:
                support_top_y = float(horizon_y)
                py = explicit_y if explicit_y is not None else support_top_y
                delta_px = abs(py - support_top_y)
                if delta_px > GROUND_TOLERANCE_PX:
                    raise CompositionError(
                        f"Scene {scene_idx} terrain prop {p.id!r} y={py} is {delta_px:.1f}px from terrain {support_top_y}"
                    )
            prop_dict["y"] = round(py, 2)
            prop_dict["floorY"] = round(py, 2)
        else:
            raise CompositionError(f"Scene {scene_idx} unsupported prop mount={mount!r}")

        runtime_props.append(prop_dict)
        grounding_checks.append(
            {
                "scene_index": scene_idx,
                "entity": "prop",
                "id": p.id,
                "canonical_id": canonical,
                "mount": mount,
                "x": float(p.x),
                "y": prop_dict["y"],
                "support_top_y": support_top_y,
                "delta_px": round(delta_px, 3),
                "grounded": delta_px <= GROUND_TOLERANCE_PX,
            }
        )

    cam_params = CAMERA_MOVE_PARAMS.get(sc_vis.camera_move, CAMERA_MOVE_PARAMS["drift"])
    t_type = TRANSITION_MAP.get(sc_vis.transition_in, "crossfade")

    scene_dict: dict[str, Any] = {
        "scene_index": scene_idx,
        "s0": round(s0, 4),
        "s1": round(s1, 4),
        "environment": _build_env_dict(env_preset, sc_vis, horizon_y),
        "camera": cam_params,
        "transition_type": t_type,
        "transition_duration_sec": 0.36 if scene_idx > 0 else 0.0,
        "stage_elements": stage_elements,
        "props": runtime_props,
        "characters": runtime_chars,
    }

    pill = sc_vis.contextual_pill
    if enable_contextual_pills and pill.enabled and (pill.text or pill.subtext):
        if not (SHORTS_PILL_MIN_Y <= int(pill.y_px) <= SHORTS_PILL_MAX_Y):
            raise CompositionError(
                f"Scene {scene_idx} contextual_pill y_px={pill.y_px} outside Shorts band [{SHORTS_PILL_MIN_Y}, {SHORTS_PILL_MAX_Y}]"
            )
        if pill.subtext:
            scene_dict["pill_kicker"] = pill.subtext
        if pill.text:
            scene_dict["pill_title"] = pill.text
        scene_dict["pill_y_px"] = int(pill.y_px)

    return scene_dict, grounding_checks


def validate_storyboard_grounding(grounding_report: list[dict[str, Any]]) -> list[str]:
    """Return human-readable errors for any ungrounded entity in grounding_report."""
    errors: list[str] = []
    for item in grounding_report:
        if not item.get("grounded", False) or float(item.get("delta_px", 999.0)) > GROUND_TOLERANCE_PX:
            errors.append(
                f"scene {item.get('scene_index')} {item.get('entity')} {item.get('id')}: "
                f"delta_px={item.get('delta_px')} > {GROUND_TOLERANCE_PX}"
            )
    return errors


def _stage_runtime_bundle(root: Path, output_dir: Path, registry: dict[str, Any]) -> None:
    """Mount single copy of runtime assets (fonts, gsap, runtime modules) without legacy bloat."""
    # Clean stale root-level runtime files & staged subdirs before writing fresh bundle
    for stale_name in ("engine.js", "gsap.min.js", "world.js"):
        stale_file = output_dir / stale_name
        if stale_file.is_file():
            stale_file.unlink(missing_ok=True)
    for reset_sub in ("runtime", "captions"):
        sub_path = output_dir / reset_sub
        if sub_path.is_dir():
            shutil.rmtree(sub_path)

    for sub in ("fonts", "lib", "runtime", "captions", "audio"):
        (output_dir / sub).mkdir(parents=True, exist_ok=True)

    shutil.copytree(root / "assets" / "fonts", output_dir / "fonts", dirs_exist_ok=True)
    gsap_src = root / "assets" / "js" / "gsap.min.js"
    if not gsap_src.is_file():
        raise CompositionError(f"Missing gsap.min.js runtime dependency: {gsap_src}")
    shutil.copy2(gsap_src, output_dir / "lib" / "gsap.min.js")

    rt_src = root / "templates" / "runtime"
    shutil.copytree(rt_src, output_dir / "runtime", dirs_exist_ok=True)
    # Remove any three.js remnants if ever present; Phase 2 runtime uses pure Canvas2D
    for unwanted in output_dir.rglob("three.module.min.js"):
        unwanted.unlink(missing_ok=True)

    shutil.copy2(root / registry["runtime"]["stylesheet"], output_dir / "styles.css")


def compose_storyboard(
    root: Path,
    episode_plan: EpisodePlanV2 | EpisodePlan | dict[str, Any],
    *,
    audio_manifest: dict[str, Any] | Path,
    output_dir: Path | None = None,
    captions: list[dict[str, Any]] | Path | None = None,
    mix_audio: bool = True,
    master_wav_path: Path | None = None,
    cfg: dict[str, Any] | None = None,
    enable_contextual_pills: bool = False,
    vignette_strength: float = 0.40,
    grain_alpha: float = 0.022,
) -> CompiledComposition:
    """Compile EpisodePlanV2 + StoryboardIR + Phase 3 audio into a HyperFrames composition."""
    from jinja2 import Environment, FileSystemLoader

    root = Path(root).resolve()
    registry = load_asset_registry(root)
    plan = _coerce_episode_plan(episode_plan)
    a_manifest = _load_audio_manifest(audio_manifest)
    ir, total_duration = verify_plan_audio_parity(plan, a_manifest, root=root, cfg=cfg)

    # Auto-enable contextual pills when any scene has an enabled pill with text
    if not enable_contextual_pills:
        for sv in ir.scenes:
            if sv.contextual_pill.enabled and (sv.contextual_pill.text or sv.contextual_pill.subtext):
                enable_contextual_pills = True
                break

    target_dir = (output_dir or (root / "build" / "composition")).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    runtime_scenes: list[dict[str, Any]] = []
    grounding_report: list[dict[str, Any]] = []
    cursor = 0.0
    for idx, (sc_vis, sc_plan, sc_aud) in enumerate(zip(ir.scenes, plan.scenes, a_manifest["scenes"])):
        dur = float(sc_aud["duration_sec"])
        s0 = float(sc_aud["start_sec"]) if sc_aud.get("start_sec") is not None else cursor
        s1 = float(sc_aud["end_sec"]) if sc_aud.get("end_sec") is not None else (s0 + dur)
        cursor = s1
        rt_scene, sc_grounding = _compile_scene_visuals(
            idx,
            sc_vis,
            sc_plan,
            s0,
            s1,
            registry,
            enable_contextual_pills=enable_contextual_pills,
        )
        runtime_scenes.append(rt_scene)
        grounding_report.extend(sc_grounding)

    grounding_errors = validate_storyboard_grounding(grounding_report)
    if grounding_errors:
        raise CompositionError("Storyboard grounding validation failed: " + "; ".join(grounding_errors))

    cues = _load_or_build_captions(captions, a_manifest, plan, total_duration)

    _stage_runtime_bundle(root, target_dir, registry)
    captions_js_path = target_dir / "captions" / "captions_data.js"
    write_captions_data_js(cues, captions_js_path)

    # Audio handling: copy pre-mixed WAV or mix cleanly using Phase 3 sound_mixer
    audio_out_path: Optional[Path] = target_dir / "audio" / "master_mix.wav"
    audio_mix_report: dict[str, Any] = {}
    if master_wav_path is not None:
        src_wav = Path(master_wav_path)
        if not src_wav.is_file():
            raise CompositionError(f"Provided master_wav_path not found: {src_wav}")
        if src_wav.resolve() != audio_out_path.resolve():
            shutil.copy2(src_wav, audio_out_path)
    elif mix_audio:
        resolved_cfg = cfg if cfg is not None else load_config(root)
        narration_ref = (
            (a_manifest.get("audio") or {}).get("narration_wav_path")
            or (a_manifest.get("audio") or {}).get("narration_full_path")
            or a_manifest.get("narration_wav_path")
            or a_manifest.get("narration_full_path")
        )
        narration_path = Path(narration_ref) if narration_ref else None
        if narration_path is not None and not narration_path.is_absolute():
            narration_path = root / narration_path
        if narration_path is None or not narration_path.is_file():
            raise CompositionError(
                f"Cannot mix episode audio: narration WAV not found ({narration_ref!r})"
            )
        mixer_manifest = {
            "pillar": plan.pillar,
            "bgm_track": plan.bgm_track,
            "audio": {
                "total_duration_sec": total_duration,
                "narration_wav_path": str(narration_path),
            },
            "storyboard_ir": ir.model_dump(),
            "scenes": [
                {
                    **sc_aud,
                    "sfx_cue": sc_plan.sfx_cue,
                    "transition_sfx": sc_vis.transition_sfx or sc_plan.transition_sfx,
                    "visual_spec": sc_vis.model_dump(),
                }
                for sc_aud, sc_plan, sc_vis in zip(a_manifest["scenes"], plan.scenes, ir.scenes)
            ],
        }
        audio_mix_report = mix_episode_audio(
            root,
            mixer_manifest,
            resolved_cfg,
            narration_path=narration_path,
            output_wav_path=audio_out_path,
            allow_synth_fallback=False,
        )
    else:
        audio_out_path = None

    episode_runtime = {
        "visual_direction_version": ir.visual_direction_version,
        "duration_sec": round(total_duration, 4),
        "enable_contextual_pills": bool(enable_contextual_pills),
        "vignette_strength": float(vignette_strength),
        "grain_alpha": float(grain_alpha),
        "scenes": runtime_scenes,
    }

    rt_env = Environment(loader=FileSystemLoader(str(root / "templates" / "runtime")))
    index_html_path = target_dir / "index.html"
    index_rendered = rt_env.get_template("index.html.jinja2").render(
        title=plan.youtube_title,
        fonts_css="fonts/fonts.css",
        styles_css="styles.css",
        gsap_src="lib/gsap.min.js",
        captions_data_js="captions/captions_data.js",
        captions_src="captions/captions.html",
        runtime_base="./runtime",
        audio_src="audio/master_mix.wav" if audio_out_path is not None else "",
        include_captions=True,
        duration_sec=round(total_duration, 4),
        episode_runtime_json=json.dumps(episode_runtime, ensure_ascii=False),
    )
    write_text_atomic(index_html_path, index_rendered)

    cap_env = Environment(loader=FileSystemLoader(str(root / "templates" / "runtime" / "captions")))
    captions_html_path = target_dir / "captions" / "captions.html"
    captions_rendered = cap_env.get_template("captions.html.jinja2").render(
        fonts_css="../fonts/fonts.css",
        gsap_src="../lib/gsap.min.js",
        captions_data_js="captions_data.js",
        duration_sec=round(total_duration, 4),
    )
    write_text_atomic(captions_html_path, captions_rendered)

    audio_alignment_scenes: list[dict[str, Any]] = []
    ratios: list[float] = []
    for asc in a_manifest.get("scenes") or []:
        ratio_raw = asc.get("alignment_match_ratio")
        ratio_val = round(float(ratio_raw), 4) if ratio_raw is not None else None
        if ratio_val is not None:
            ratios.append(ratio_val)
        audio_alignment_scenes.append(
            {
                "scene_index": asc.get("scene_index"),
                "alignment_match_ratio": ratio_val,
            }
        )
    audio_alignment = {
        "available": len(ratios) > 0,
        "scene_count": len(audio_alignment_scenes),
        "avg_match_ratio": round(sum(ratios) / len(ratios), 4) if ratios else None,
        "min_match_ratio": round(min(ratios), 4) if ratios else None,
        "per_scene": audio_alignment_scenes,
    }

    compiled_meta = {
        "schema_version": "2.0.0",
        "episode_title": plan.youtube_title,
        "series_id": plan.series_id,
        "duration_sec": round(total_duration, 4),
        "scene_count": len(runtime_scenes),
        "captions_count": len(cues),
        "enable_contextual_pills": bool(enable_contextual_pills),
        "grounding_report": grounding_report,
        "audio_mix_report": audio_mix_report,
        "audio_alignment": audio_alignment,
        "episode_runtime": episode_runtime,
    }
    compiled_meta_path = target_dir / "storyboard_compiled.json"
    write_text_atomic(compiled_meta_path, json.dumps(compiled_meta, indent=2, ensure_ascii=False))

    return CompiledComposition(
        output_dir=target_dir,
        index_html=index_html_path,
        captions_html=captions_html_path,
        captions_data_js=captions_js_path,
        master_wav=audio_out_path,
        compiled_metadata_json=compiled_meta_path,
        duration_sec=round(total_duration, 4),
        scene_count=len(runtime_scenes),
        episode_runtime=episode_runtime,
        grounding_report=grounding_report,
        audio_mix_report=audio_mix_report,
    )
