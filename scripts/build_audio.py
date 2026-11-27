#!/usr/bin/env python3
"""Sutradhar — Thin CLI Facade for Phase 3 Audio Pipeline (`sutradhar.audio`).

Whitelisted zero-argument CLI invocation:
    python scripts/build_audio.py
"""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Optional

import numpy as np
from pydantic import ValidationError

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from db_manager import (  # noqa: E402
    EpisodePlan,
    StateError,
    connect_db,
    emit_pacing_warnings,
    get_project_root,
    load_config,
    load_json_file,
    resolve_paths,
)
from sutradhar.audio.caption_builder import build_caption_cues  # noqa: E402
from sutradhar.audio.elevenlabs_tts import (  # noqa: E402
    DEFAULT_SAMPLE_RATE,
    DEFAULT_TAG_TEMPLATES,
    DEFAULT_VOICE_ID,
    DEFAULT_VOICE_SETTINGS,
    MAX_BILLED_CHARS,
    SOFT_WARN_BILLED_CHARS,
    ElevenLabsEngine,
    FakeElevenLabs,
    TTSBudgetError,
    apply_pronunciations,
    apply_pronunciations_preserving_tags,
    compute_scene_sha256,
    load_pronunciations as _load_pronunciations_map,
    prepare_scene_tts_text,
    record_audio_ledger,
    resolve_scene_tag,
    strip_audio_tags,
    validate_pre_tts_budget,
)
from sutradhar.audio.whisper_aligner import (  # noqa: E402
    DURATION_TOLERANCE_SEC,
    FINAL_SCENE_PAD_SEC,
    INTER_SCENE_PAD_SEC,
    MIN_PEAK_AMPLITUDE,
    SILENCE_THRESHOLD,
    TRIM_MARGIN_SEC,
    AudioBuildError,
    LazyWhisperProxy,
    align_narration_words,
    default_whisper_factory,
    measure_trailing_rms,
    probe_duration_sec,
    require_executable,
    transcribe_scene_adaptive,
    transcribe_scene_words,
    trim_and_pad_audio,
    two_pass_loudnorm,
    write_text_atomic,
    write_wav_atomic,
)

align_caption_words = align_narration_words
_LazyWhisperProxy = LazyWhisperProxy


def load_pronunciations(
    root: Path,
    cfg: dict[str, Any],
    lang: str = "hi",
) -> tuple[dict[str, str], list[tuple[str, str]]]:
    """Load pronunciation overrides as `(text_replacements, [])` for facade callers."""
    return _load_pronunciations_map(root, cfg, lang=lang), []


def verify_active_series_continuity_readonly(
    db_path: Path,
    ep_plan: EpisodePlan,
) -> None:
    if (
        getattr(ep_plan, "content_format", "episodic_series") == "standalone"
        or ep_plan.series_id is None
    ):
        return

    if not db_path.is_file():
        print(
            f"[WARN] Database not found at {db_path}; skipping active-series continuity check.",
            file=sys.stderr,
        )
        return

    conn: Optional[sqlite3.Connection] = None
    try:
        conn = connect_db(db_path)
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='series'"
        ).fetchone()
        if not table_exists:
            return
        active = conn.execute(
            "SELECT * FROM series WHERE series_id = ? AND status = 'ACTIVE'",
            (ep_plan.series_id,),
        ).fetchone()
    finally:
        if conn is not None:
            conn.close()

    if active is None:
        print(
            f"[WARN] No ACTIVE series #{ep_plan.series_id} in episodes.db; proceeding with standalone audio build.",
            file=sys.stderr,
        )
        return

    mismatches: list[str] = []
    if active["series_title"] != ep_plan.series_title:
        mismatches.append(f"series_title ('{ep_plan.series_title}' != '{active['series_title']}')")
    if active["pillar"] != ep_plan.pillar:
        mismatches.append(f"pillar ('{ep_plan.pillar}' != '{active['pillar']}')")
    if active["tts_voice"] != ep_plan.tts_voice:
        mismatches.append(f"tts_voice ('{ep_plan.tts_voice}' != '{active['tts_voice']}')")
    if active["bgm_track"] != ep_plan.bgm_track:
        mismatches.append(f"bgm_track ('{ep_plan.bgm_track}' != '{active['bgm_track']}')")
    expected_ep = int(active["completed_episodes"]) + 1
    if ep_plan.episode_number_in_series != expected_ep:
        mismatches.append(
            f"episode_number_in_series ({ep_plan.episode_number_in_series} != {expected_ep})"
        )
    if mismatches:
        raise AudioBuildError(
            "episode_plan.json does not match ACTIVE series in episodes.db: "
            + "; ".join(mismatches)
        )


def default_elevenlabs_factory(cfg: dict[str, Any], root: Path) -> ElevenLabsEngine:
    return ElevenLabsEngine(config=cfg, project_root=root)


def _instantiate_tts_engine(raw_factory: Any, cfg: dict[str, Any], root: Path) -> Any:
    if not callable(raw_factory):
        return raw_factory
    params = list(inspect.signature(raw_factory).parameters.values())
    if not params:
        return raw_factory()
    if len(params) == 1:
        return raw_factory(cfg)
    return raw_factory(cfg, root)


def _compute_scene_speed(
    scene: Any,
    cfg: dict[str, Any],
    active_lang: str,
    is_dialogue: bool,
    is_climax_scene: bool,
) -> float:
    if getattr(scene, "speed", None) is not None:
        return float(scene.speed)

    lang_prof = cfg.get("languages", {}).get(active_lang, {})
    default_narr = float(lang_prof.get("narrator_speed", cfg.get("tts", {}).get("speed", 0.92)))
    default_diag = float(lang_prof.get("character_dialogue_speed", 0.90))
    base_speed = default_diag if is_dialogue else default_narr

    emotion = getattr(scene, "emotion", "calm")
    shot_type = getattr(scene, "shot_type", None) or ""
    multiplier = 1.0
    if (
        emotion in ("wrath", "rage", "shock")
        or shot_type in ("dramatic_climax", "confrontation", "climax")
        or is_climax_scene
    ):
        multiplier = 1.04
    elif emotion in ("calm", "meditating") or shot_type in (
        "curtain_establishing",
        "philosophical_outro",
    ):
        multiplier = 0.96
    elif emotion == "smirk":
        multiplier = 1.01

    return round(min(1.15, max(0.80, base_speed * multiplier)), 3)


def _compute_scene_pause(
    scene: Any,
    idx: int,
    total_scenes: int,
    scenes: list[Any],
    is_climax_scene: bool,
    is_dialogue: bool,
) -> float:
    if idx == total_scenes - 1:
        return FINAL_SCENE_PAD_SEC
    custom_ms = getattr(scene, "pause_after_ms", None)
    if custom_ms and custom_ms > 0:
        return custom_ms / 1000.0
    shot_type = getattr(scene, "shot_type", None) or ""
    next_is_dialogue = (
        idx + 1 < total_scenes
        and getattr(scenes[idx + 1], "speaker_role", "narrator") == "character_dialogue"
    )
    if is_climax_scene or shot_type in ("dramatic_climax", "revelation"):
        return 0.40
    if next_is_dialogue or is_dialogue:
        return 0.18
    return INTER_SCENE_PAD_SEC


def _posix_rel(path: Path, root: Path) -> str:
    return PurePosixPath(path.relative_to(root).as_posix()).as_posix()


def _resolve_duration_bounds(ep_plan: Any, cfg: dict[str, Any]) -> tuple[str, float, float, float, float]:
    active_format = getattr(ep_plan, "content_format", None) or cfg.get("content_format", "episodic_series")
    format_pacing = cfg.get("format_pacing", {}).get(active_format, {})
    default_pacing = cfg.get("episode_pacing", {})

    hard_min = float(format_pacing.get("hard_duration_min_sec", default_pacing.get("hard_duration_min_sec", 30.0)))
    hard_max = float(format_pacing.get("hard_duration_max_sec", default_pacing.get("hard_duration_max_sec", 180.0)))
    target_min = float(format_pacing.get("target_duration_min_sec", default_pacing.get("target_duration_min_sec", 40.0)))
    target_max = float(format_pacing.get("target_duration_max_sec", default_pacing.get("target_duration_max_sec", 120.0)))

    plan_range = getattr(ep_plan, "target_duration_range", None)
    if isinstance(plan_range, dict):
        p_min = plan_range.get("min_seconds")
        p_max = plan_range.get("max_seconds")
        if p_min is not None and p_max is not None:
            target_min = float(p_min)
            target_max = float(p_max)
            hard_min = max(30.0, target_min * 0.85)
            hard_max = min(180.0, target_max * 1.15)

    return active_format, max(30.0, hard_min), min(180.0, hard_max), target_min, target_max


def build_episode_audio(
    root: Path,
    tts_factory: Optional[Callable[..., Any]] = None,
    whisper_factory: Optional[Callable[[dict[str, Any]], Any]] = None,
    strict_budget: Optional[bool] = None,
    ledger_db_path: Optional[Path] = None,
    episode_id: Optional[int] = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Execute pre-TTS budget validation, speech synthesis, word alignment, and mastering."""
    require_executable("ffprobe")

    cfg = load_config(root)
    paths = resolve_paths(root, cfg)
    build_dir = paths["build_dir"]
    audio_dir = build_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    ep_path = build_dir / "episode_plan.json"
    raw_ep = load_json_file(ep_path, "episode_plan.json")
    try:
        ep_plan = EpisodePlan.model_validate(raw_ep, context={"config": cfg})
    except ValidationError as exc:
        raise AudioBuildError(f"episode_plan.json validation failed:\n{exc}") from exc

    emit_pacing_warnings(ep_plan, cfg)
    verify_active_series_continuity_readonly(paths["db_file"], ep_plan)

    active_lang = getattr(ep_plan, "language", cfg["channel"].get("primary_language", "hi"))
    text_reps = _load_pronunciations_map(root, cfg, lang=active_lang)

    tts_cfg = cfg.get("tts", {})
    expected_sr = int(tts_cfg.get("sample_rate", DEFAULT_SAMPLE_RATE))
    tag_templates = {**DEFAULT_TAG_TEMPLATES, **tts_cfg.get("tag_templates", {})}
    voice_settings = {**DEFAULT_VOICE_SETTINGS, **tts_cfg.get("voice_settings", {})}
    max_billed_chars = int(tts_cfg.get("max_billed_chars_per_episode", MAX_BILLED_CHARS))
    warn_billed_chars = int(tts_cfg.get("target_billed_chars_max", SOFT_WARN_BILLED_CHARS))

    # Prepare clean + tag-preserving phonetic text and speeds BEFORE instantiating/calling TTS
    total_scenes = len(ep_plan.scenes)
    prepared: list[dict[str, Any]] = []
    for idx, scene in enumerate(ep_plan.scenes):
        is_climax = (
            getattr(ep_plan, "story_arc", None) is not None
            and getattr(ep_plan.story_arc, "climax_scene_index", None) == scene.scene_index
        )
        is_dialogue = getattr(scene, "speaker_role", "narrator") == "character_dialogue"
        clean_text, tagged_text = prepare_scene_tts_text(
            scene, idx, total_scenes, text_reps, tag_templates, is_climax
        )
        speed = _compute_scene_speed(scene, cfg, active_lang, is_dialogue, is_climax)
        scene_vs = {**voice_settings, "speed": speed}
        prepared.append(
            {
                "idx": idx,
                "scene": scene,
                "clean_text": clean_text,
                "tagged_text": tagged_text,
                "speed": speed,
                "voice_settings": scene_vs,
                "is_climax": is_climax,
                "is_dialogue": is_dialogue,
            }
        )

    raw_factory = tts_factory or kwargs.get("elevenlabs_factory") or default_elevenlabs_factory
    tts_engine = _instantiate_tts_engine(raw_factory, cfg, root)

    # Check if an already-synthesized legacy episode (pre-Phase 3 [pause]-stripped cache)
    # is 100% cached on disk so Gate 4 rebuilds execute with 0 API calls in < 2s.
    is_live_engine = isinstance(tts_engine, ElevenLabsEngine) and not isinstance(
        tts_engine, FakeElevenLabs
    )
    if is_live_engine:
        for item in prepared:
            if tts_engine.is_scene_cached(item["tagged_text"], voice_settings=item["voice_settings"]):
                item["synth_text"] = item["tagged_text"]
                item["is_cached"] = True
            else:
                legacy_phonetic = apply_pronunciations(item["clean_text"], text_reps)
                legacy_tag = resolve_scene_tag(
                    item["scene"], item["idx"], total_scenes, tag_templates, item["is_climax"]
                )
                legacy_tagged = f"{legacy_tag} {legacy_phonetic}".strip()
                if strict_budget is not True and tts_engine.is_scene_cached(
                    legacy_tagged, voice_settings=item["voice_settings"]
                ):
                    item["synth_text"] = legacy_tagged
                    item["is_cached"] = True
                else:
                    item["synth_text"] = item["tagged_text"]
                    item["is_cached"] = False
    else:
        for item in prepared:
            item["synth_text"] = item["tagged_text"]
            item["is_cached"] = False

    has_cache_miss = is_live_engine and any(not item["is_cached"] for item in prepared)
    has_v2_policy_fields = bool(
        getattr(ep_plan, "thumbnail_spec", None)
        or getattr(ep_plan, "audio_language", None)
        or getattr(ep_plan, "caption_language", None)
    )
    enforce_hard_budget = (
        strict_budget is True
        or (
            strict_budget is None
            and (has_cache_miss or has_v2_policy_fields)
        )
    )
    if enforce_hard_budget:
        validate_pre_tts_budget(
            [item["synth_text"] for item in prepared],
            [item["clean_text"] for item in prepared],
            max_billed_chars=max_billed_chars,
            warn_billed_chars=warn_billed_chars,
            language=active_lang,
            enforce_devanagari=(strict_budget is True or active_lang == "hi"),
        )

    whisper_builder = whisper_factory or default_whisper_factory
    whisper_model = whisper_builder(cfg)
    fps = int(cfg["video"]["fps"])
    width = int(cfg["video"]["width"])
    height = int(cfg["video"]["height"])

    for stale in audio_dir.glob("scene_*.wav"):
        try:
            stale.unlink()
        except OSError:
            pass

    concat_chunks: list[np.ndarray] = []
    manifest_scenes: list[dict[str, Any]] = []
    cursor_sec = 0.0

    for item in prepared:
        idx = item["idx"]
        scene = item["scene"]
        clean_text = item["clean_text"]
        tagged_text = item["tagged_text"]
        synth_text = item["synth_text"]
        speed = item["speed"]
        scene_vs = item["voice_settings"]
        is_climax = item["is_climax"]
        is_dialogue = item["is_dialogue"]

        was_cached = bool(item["is_cached"])
        try:
            if hasattr(tts_engine, "synthesize_scene"):
                samples, sr = tts_engine.synthesize_scene(synth_text, voice_settings=scene_vs)
            elif hasattr(tts_engine, "synthesize"):
                samples, sr = tts_engine.synthesize(synth_text, voice_settings=scene_vs)
            else:
                raise AudioBuildError(
                    f"TTS engine {type(tts_engine)} does not expose a supported synthesis method."
                )
        except Exception as exc:
            raise AudioBuildError(
                f"Speech synthesis failed on scene {scene.scene_index}: {exc}"
            ) from exc

        if ledger_db_path is not None:
            vid = getattr(tts_engine, "voice_id", DEFAULT_VOICE_ID)
            mid = getattr(tts_engine, "model_id", "eleven_v4")
            record_audio_ledger(
                ledger_db_path,
                scene_index=scene.scene_index,
                sha256_key=compute_scene_sha256(synth_text, vid, mid, scene_vs),
                billed_chars=len(synth_text),
                model_id=mid,
                voice_id=vid,
                cache_hit=was_cached,
                episode_id=episode_id,
            )

        sr = int(sr)
        if expected_sr != sr:
            expected_sr = sr

        pad_sec = _compute_scene_pause(scene, idx, total_scenes, ep_plan.scenes, is_climax, is_dialogue)
        scene_wav = audio_dir / f"scene_{scene.scene_index}.wav"
        processed = trim_and_pad_audio(samples, expected_sr, pad_tail_sec=pad_sec)
        write_wav_atomic(scene_wav, processed, expected_sr)
        scene_dur = probe_duration_sec(scene_wav)

        whisper_words, _ = transcribe_scene_adaptive(
            whisper_model=whisper_model,
            wav_path=scene_wav,
            narration_text=clean_text,
            language="hi" if active_lang == "hi" else "en",
            scene_duration=scene_dur,
            use_cache=True,
        )
        aligned_words, match_ratio = align_narration_words(
            narration_text=clean_text,
            whisper_words=whisper_words,
            scene_duration=scene_dur,
            global_offset=cursor_sec,
            wav_path=scene_wav,
        )

        start_sec = round(cursor_sec, 4)
        end_sec = round(cursor_sec + scene_dur, 4)
        midpoint_sec = round(start_sec + scene_dur / 2.0, 4)

        scene_entry = scene.model_dump()
        scene_entry.update(
            {
                "speaker_role": "character_dialogue" if is_dialogue else "narrator",
                "narration_text": clean_text,
                "tts_text_applied": synth_text,
                "billed_chars": len(synth_text),
                "audio_path": _posix_rel(scene_wav, root),
                "duration_sec": scene_dur,
                "start_sec": start_sec,
                "end_sec": end_sec,
                "midpoint_sec": midpoint_sec,
                "start_frame": int(round(start_sec * fps)),
                "end_frame": int(round(end_sec * fps)),
                "alignment_match_ratio": match_ratio,
                "words": aligned_words,
                "applied_speed": speed,
                "applied_pause_sec": pad_sec,
            }
        )
        manifest_scenes.append(scene_entry)
        concat_chunks.append(processed)
        cursor_sec = end_sec

    assert expected_sr is not None and concat_chunks
    full_audio = np.concatenate(concat_chunks)
    full_wav = audio_dir / "narration_full.wav"
    write_wav_atomic(full_wav, full_audio, expected_sr)
    full_duration = probe_duration_sec(full_wav)

    sum_duration = round(sum(s["duration_sec"] for s in manifest_scenes), 4)
    if abs(full_duration - sum_duration) > DURATION_TOLERANCE_SEC:
        raise AudioBuildError(
            f"Duration mismatch: narration_full.wav={full_duration}s vs "
            f"sum(scenes)={sum_duration}s (tolerance={DURATION_TOLERANCE_SEC}s)."
        )

    active_format, hard_min, hard_max, target_min, target_max = _resolve_duration_bounds(ep_plan, cfg)
    if full_duration < hard_min or full_duration > hard_max:
        raise AudioBuildError(
            f"Total narration duration {full_duration:.2f}s violates hard bounds "
            f"[{hard_min:.0f}s, {hard_max:.0f}s] for format '{active_format}'. Adjust script word count in build/episode_plan.json."
        )

    norm_wav = audio_dir / "narration_norm.wav"
    cache_dir = audio_dir.parent / "cache" / "audio"
    try:
        raw_bytes = full_wav.read_bytes()
        loudnorm_key = hashlib.md5(
            raw_bytes + f"loudnorm_-14.0_-1.5_{expected_sr}".encode("utf-8")
        ).hexdigest()
        cached_master = cache_dir / f"{loudnorm_key}.wav"
        if cached_master.is_file() and cached_master.stat().st_size > 0:
            shutil.copyfile(cached_master, full_wav)
            full_duration = probe_duration_sec(full_wav)
        else:
            two_pass_loudnorm(
                full_wav,
                norm_wav,
                target_lufs=-14.0,
                target_tp=-1.5,
                sample_rate=expected_sr,
            )
            if norm_wav.is_file() and norm_wav.stat().st_size > 0:
                try:
                    cache_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(norm_wav, cached_master)
                except Exception:
                    pass
                os.replace(norm_wav, full_wav)
                full_duration = probe_duration_sec(full_wav)
    except Exception as exc:
        print(f"[WARN] Loudnorm normalization bypassed: {exc}", file=sys.stderr)
        if norm_wav.exists():
            try:
                norm_wav.unlink()
            except OSError:
                pass

    trailing_rms = measure_trailing_rms(full_wav, tail_sec=0.50)
    if trailing_rms >= -65.0:
        raise AudioBuildError(
            f"Hiss detected in trailing silence: {trailing_rms:.1f} dBFS (must be < -65 dBFS)"
        )

    duration_warning: Optional[str] = None
    if full_duration < target_min or full_duration > target_max:
        duration_warning = (
            f"Total narration duration {full_duration:.2f}s is outside target retention "
            f"sweet spot [{target_min:.0f}s, {target_max:.0f}s] (within hard bounds)."
        )
        print(f"[WARN] {duration_warning}", file=sys.stderr)

    try:
        from scripts.engine.beat_planner import decompose_episode_into_beats

        decomposed_beats = [b.to_dict() for b in decompose_episode_into_beats(manifest_scenes)]
    except Exception:
        decomposed_beats = manifest_scenes

    caption_cues = build_caption_cues(manifest_scenes, full_duration)

    manifest_payload = {
        "schema_version": "4.0",
        "language": active_lang,
        "content_format": active_format,
        "series_id": ep_plan.series_id,
        "series_title": ep_plan.series_title,
        "pillar": ep_plan.pillar,
        "episode_number_in_series": ep_plan.episode_number_in_series,
        "total_planned_episodes": ep_plan.total_planned_episodes,
        "global_episode_number": ep_plan.global_episode_number,
        "youtube_title": ep_plan.youtube_title,
        "duration_target_seconds": getattr(ep_plan, "target_duration_sec", None),
        "target_duration_range": getattr(ep_plan, "target_duration_range", None),
        "story_arc": ep_plan.story_arc.model_dump() if getattr(ep_plan, "story_arc", None) else None,
        "narrative_structure": getattr(ep_plan, "narrative_structure", None),
        "tts_engine": cfg["tts"]["engine"],
        "tts_voice": ep_plan.tts_voice,
        "bgm_track": ep_plan.bgm_track,
        "bespoke_asset_path": ep_plan.bespoke_asset_path,
        "video": {
            "width": width,
            "height": height,
            "fps": fps,
            "safe_zones": cfg["video"]["safe_zones"],
        },
        "audio": {
            "sample_rate": expected_sr,
            "narration_full_path": _posix_rel(full_wav, root),
            "total_duration_sec": full_duration,
            "total_frames": int(round(full_duration * fps)),
            "trailing_silence_rms_dbfs": trailing_rms,
        },
        "scenes": manifest_scenes,
        "caption_cues": caption_cues,
        "beats": decomposed_beats,
        "micro_beats": decomposed_beats,
    }

    manifest_path = build_dir / "manifest.js"
    manifest_js = (
        "// Auto-generated by scripts/build_audio.py — do not edit manually.\n"
        f"window.EPISODE_MANIFEST = {json.dumps(manifest_payload, indent=2, ensure_ascii=False)};\n"
    )
    write_text_atomic(manifest_path, manifest_js)

    audio_manifest_path = audio_dir / "audio_manifest.json"
    write_text_atomic(
        audio_manifest_path,
        json.dumps(manifest_payload, indent=2, ensure_ascii=False),
    )

    return {
        "status": "ok",
        "action": "build_audio",
        "language": active_lang,
        "episode_number_in_series": ep_plan.episode_number_in_series,
        "global_episode_number": ep_plan.global_episode_number,
        "tts_voice": ep_plan.tts_voice,
        "sample_rate": expected_sr,
        "scene_count": len(manifest_scenes),
        "total_duration_sec": full_duration,
        "trailing_silence_rms_dbfs": trailing_rms,
        "narration_full_wav": _posix_rel(full_wav, root),
        "manifest_js": _posix_rel(manifest_path, root),
        "avg_alignment_match_ratio": round(
            sum(s["alignment_match_ratio"] for s in manifest_scenes) / len(manifest_scenes), 4
        ),
        "duration_warning": duration_warning,
    }


def _resolve_cli_ledger_db(root: Path) -> Optional[Path]:
    """Resolve `audio_ledger` DB path for CLI builds without mutating live DB under pytest."""
    try:
        cfg = load_config(root)
        db_path = resolve_paths(root, cfg)["db_file"].resolve()
    except Exception:
        return None
    if not db_path.is_file():
        return None
    repo_live_db = (SCRIPT_DIR.parent / "episodes.db").resolve()
    if db_path == repo_live_db and os.environ.get("PYTEST_CURRENT_TEST"):
        return None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            has_ledger = bool(
                conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='audio_ledger'"
                ).fetchone()
            )
        finally:
            conn.close()
    except sqlite3.Error:
        return None
    return db_path if has_ledger else None


def main() -> int:
    if len(sys.argv) > 1:
        print(
            "[ERROR] scripts/build_audio.py takes zero CLI arguments "
            "(strict Antigravity whitelist compliance).",
            file=sys.stderr,
        )
        return 1
    try:
        root = get_project_root()
        result = build_episode_audio(root, ledger_db_path=_resolve_cli_ledger_db(root))
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except KeyboardInterrupt:
        print("[ERROR] Audio build interrupted by user.", file=sys.stderr)
        return 130
    except (AudioBuildError, StateError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"[FATAL] Unexpected error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
