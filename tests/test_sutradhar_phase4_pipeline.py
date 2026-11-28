"""Phase 4 unit, negative fail-closed, and real end-to-end compilation/render/QA tests."""

from __future__ import annotations

import json
import math
import struct
import subprocess
import sys
import wave
from pathlib import Path
from unittest import mock

import pytest
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from sutradhar.config import load_config  # noqa: E402
from sutradhar.models import (  # noqa: E402
    CharacterPlacement,
    ContextualPill,
    EpisodePlanV2,
    PropPlacement,
    ScenePlan,
    SceneVisualSpec,
    StoryArc,
    StoryPhase,
    StoryResearch,
    StoryboardIR,
    ThumbnailSpec,
    count_billed_chars,
)
from sutradhar.qa.hyperframes_runner import (  # noqa: E402
    run_chromium_runtime_probe,
    validate_hf_check_report,
    validate_runtime_probe_and_hf_check,
)
from sutradhar.qa.quality_gate import (  # noqa: E402
    QualityGateError,
    _evaluate_kinocut_checks,
    _measure_full_res_temporal_motion,
    reject_synthetic_dom_snapshots,
    run_v2_quality_gate,
)
from sutradhar.qa.render_optimizer import (  # noqa: E402
    DEFAULT_MAX_FILE_BYTES,
    RenderOptimizeError,
    optimize_mp4_bitrate,
    validate_mp4_contract,
)
from sutradhar.visual.storyboard_composer import (  # noqa: E402
    CAPTION_SAFE_BOTTOM_MAX,
    CompositionError,
    SHORTS_PILL_MAX_X,
    SHORTS_PILL_MAX_Y,
    SHORTS_PILL_MIN_X,
    SHORTS_PILL_MIN_Y,
    compose_storyboard,
    parse_manifest_js,
)
from sutradhar.visual.thumbnail_builder import (  # noqa: E402
    ThumbnailBuildError,
    build_thumbnail,
)


def _write_speech_wav(path: Path, duration_sec: float = 2.4, freq_hz: float = 210.0) -> None:
    """Create a synthetic speech-like PCM WAV (48 kHz mono) for $0-budget Phase 4 tests."""
    sr = 48000
    n_total = int(sr * duration_sec)
    n_quiet_tail = min(int(sr * 0.45), int(n_total * 0.30))
    frames = bytearray()
    for i in range(n_total):
        if i >= n_total - n_quiet_tail:
            sample = 0
        else:
            t = i / sr
            env = 0.55 + 0.35 * math.sin(2 * math.pi * 3.2 * t)
            val = env * (0.65 * math.sin(2 * math.pi * freq_hz * t) + 0.25 * math.sin(2 * math.pi * freq_hz * 2.0 * t))
            sample = max(-32767, min(32767, int(val * 18000)))
        frames.extend(struct.pack("<h", sample))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(bytes(frames))


def _concat_wavs(wavs: list[Path], out_wav: Path, *, trailing_silence_sec: float = 0.8) -> None:
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(wavs[0]), "rb") as w0:
        params = w0.getparams()
    with wave.open(str(out_wav), "wb") as out:
        out.setparams(params)
        for p in wavs:
            with wave.open(str(p), "rb") as wi:
                out.writeframes(wi.readframes(wi.getnframes()))
        pad_frames = int(params.framerate * trailing_silence_sec)
        out.writeframes(b"\x00" * pad_frames * params.nchannels * params.sampwidth)


def _make_sample_v2_plan_and_audio(
    tmp_path: Path,
    *,
    include_pill: bool = True,
    short_durations: tuple[float, ...] | None = None,
    trailing_silence_sec: float = 0.8,
) -> tuple[EpisodePlanV2, dict]:
    scene_specs = [
        ("कैलाश पर्वत पर महादेव शांत ध्यान में स्थित हैं।", 2.8, 210.0, "कैलाश", "kailash_horizon", "dawn_epic", "shiva", "floor", "palm_cup", "determined", [PropPlacement(id="trishul", kind="trishul", mount="floor", x=210.0, scale=1.0)], include_pill),
        ("ब्रह्मलोक में समय का चक्र ब्रह्मांड से तेज चलता है।", 1.4, 235.0, "ब्रह्मलोक", "brahmaloka_sabha", "palace_court", "brahma", "dais", "bless", "serene", [PropPlacement(id="brass_clock", kind="brass_clock", mount="pedestal", x=540.0, y=540.0, scale=1.0)], False),
        ("अंतरिक्ष में कालचक्र की गति गुरुत्वाकर्षण से बदलती है।", 1.4, 225.0, "कालचक्र", "observatory_cosmos", "cosmic_explainer", "sutradhar_narrator", "floor", "gesture", "serene", [PropPlacement(id="brahmaloka_time_chakra", kind="brahmaloka_time_chakra", mount="sky", x=540.0, y=520.0, scale=1.0)], False),
        ("हिमालय के आश्रम में ऋषियों ने यह सत्य जाना।", 1.4, 240.0, "हिमालय", "ashram_twilight", "dawn_epic", "ancient_scholar", "floor", "namaskar", "determined", [], False),
        ("द्वारका और कैलाश के बीच यही सनातन समय का नियम है।", 1.4, 220.0, "सनातन", "dwaraka_durbar", "palace_court", "vishnu", "dais", "bless", "serene", [], False),
    ]
    if short_durations is not None:
        assert len(short_durations) == len(scene_specs)
        scene_specs = [
            (spec[0], short_durations[idx], *spec[2:])
            for idx, spec in enumerate(scene_specs)
        ]

    wavs = []
    for idx, (_, dur, freq, *_) in enumerate(scene_specs, start=1):
        wp = tmp_path / f"scene_{idx}.wav"
        _write_speech_wav(wp, dur, freq)
        wavs.append(wp)
    narr_wav = tmp_path / "narration_full.wav"
    _concat_wavs(wavs, narr_wav, trailing_silence_sec=trailing_silence_sec)

    plan_scenes = []
    ir_scenes = []
    audio_scenes = []
    cursor = 0.0
    for idx, (text, dur, _, kw, env_id, mode, role, surf, pose, expr, props, pill_on) in enumerate(scene_specs, start=1):
        sc_dur = dur + (trailing_silence_sec if idx == len(scene_specs) else 0.0)
        plan_scenes.append(
            ScenePlan(
                scene_index=idx,
                narration_text=text,
                visual_mode="character_drama",
                backdrop_rig=env_id,
                primary_character=role,
                speaker_role="narrator",
                mood_palette=mode,
                particle_theme="golden_embers",
                camera_motion="slow_push",
                emphasis_word=kw,
                speed=0.9,
                pause_after_ms=300 if idx < len(scene_specs) else int(trailing_silence_sec * 1000),
            )
        )
        ir_scenes.append(
            SceneVisualSpec(
                atmosphere_mode=mode,
                environment_preset=env_id,
                horizon_y=1142,
                camera_move="slow_push_in" if idx % 2 else "drift",
                transition_in="fade" if idx == 1 else "iris",
                bgm_mood="epic",
                props=props,
                characters=[
                    CharacterPlacement(
                        id=f"hero_{role}_{idx}",
                        role=role,
                        x=540.0,
                        surface_type=surf,
                        pose=pose,
                        expr=expr,
                    )
                ],
                contextual_pill=ContextualPill(
                    enabled=pill_on,
                    text="KAILASH HORIZON" if pill_on else None,
                    subtext="MOUNT KAILASH" if pill_on else None,
                    y_px=310,
                ),
            )
        )
        toks = [t for t in text.replace("।", "").split() if t][:3]
        step = max(0.18, (dur - 0.15) / max(1, len(toks)))
        words = [
            {"text": tok, "start": round(cursor + 0.08 + j * step, 3), "end": round(cursor + 0.08 + (j + 0.85) * step, 3)}
            for j, tok in enumerate(toks)
        ]
        audio_scenes.append(
            {
                "scene_index": idx,
                "start_sec": round(cursor, 4),
                "end_sec": round(cursor + sc_dur, 4),
                "duration_sec": round(sc_dur, 4),
                "speed": 0.9,
                "narration_text": text,
                "billed_chars": count_billed_chars([plan_scenes[-1]]),
                "words": words,
            }
        )
        cursor += sc_dur

    total_dur = round(cursor, 4)
    ir = StoryboardIR(
        visual_direction_version="v2_storycraft",
        width=1080,
        height=1920,
        fps=30,
        horizon_y=1142,
        scenes=ir_scenes,
    )

    n_sc = len(plan_scenes)
    plan = EpisodePlanV2(
        content_format="standalone",
        story_arc=StoryArc(
            arc_title="Kailash Time Shift",
            premise="Sacred realms experience cosmic time differently across Kailash and Brahmaloka.",
            central_conflict="Mortal perception collides with cosmic relativity.",
            resolution="Vedic texts anticipated gravitational and relativistic dilation.",
            phases=[
                StoryPhase(
                    phase_index=1,
                    phase_name="Opening",
                    narrative_goal="Establish Kailash and Brahmaloka.",
                    target_duration_sec=max(5, int(round(total_dur))),
                    scenes=list(range(1, n_sc + 1)),
                )
            ],
            climax_scene_index=min(3, n_sc),
            resolution_scene_index=n_sc,
        ),
        story_research=StoryResearch(
            source_tradition="Shiva Purana",
            canonical_story_summary="Cosmic stillness of Shiva at Kailash contrasted with Brahmaloka assembly.",
            key_verified_facts=["Kailash twilight setting", "Brahmaloka assembly hall"],
            source_references=["Shiva Purana, Rudra Samhita"],
        ),
        target_duration_sec=50,
        target_duration_range={"min_seconds": 2, "max_seconds": 65},
        series_id=1,
        series_title="Sanatan Cosmos",
        pillar="mythology_science",
        episode_number_in_series=1,
        total_planned_episodes=5,
        global_episode_number=1,
        tts_voice="uuyFQegRan8rpIQCGu9K",
        bgm_track="dramatic_mythology.mp3",
        bespoke_asset_path="assets/characters/shiva.json",
        youtube_title="Why Time Slows Near Kailash | Sanatan Science",
        youtube_description="Explore Vedic relativity between Kailash and Brahmaloka. #SanatanScience #Shorts",
        youtube_tags=["sanatan", "kailash", "brahmaloka"],
        summary="Vedic spacetime contrast across sacred realms.",
        thumbnail_spec=ThumbnailSpec(
            pill="VEDIC RELATIVITY",
            headline_line1="TIME SLOWS",
            headline_line2="IN BRAHMALOKA",
            sub_pill="KAILASH TO COSMOS",
            font_weight=800,
            theme="kailash_horizon",
        ),
        storyboard_ir=ir,
        scenes=plan_scenes,
    )

    audio_manifest = {
        "total_duration_sec": total_dur,
        "audio": {
            "total_duration_sec": total_dur,
            "narration_wav_path": str(narr_wav),
        },
        "scenes": audio_scenes,
    }
    return plan, audio_manifest


def _encode_fast_mp4(
    mp4_path: Path,
    *,
    duration_sec: float,
    video_filter: str = "testsrc2=size=1080x1920:rate=30",
    vf_extra: str | None = None,
    audio_filter: str = "anullsrc=r=48000:cl=stereo",
    af_args: list[str] | None = None,
) -> None:
    """Encode a fast 1080x1920@30fps H.264/AAC MP4 for targeted QA gate tests."""
    v_src = f"{video_filter}:duration={duration_sec:.3f}" if "duration=" not in video_filter else video_filter
    if vf_extra:
        v_src = f"{v_src},{vf_extra}"
    a_src = audio_filter
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", v_src,
        "-f", "lavfi", "-i", a_src,
    ]
    if af_args:
        cmd.extend(["-af", *af_args])
    cmd.extend([
        "-t", f"{duration_sec:.3f}",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-ar", "48000",
        str(mp4_path),
    ])
    subprocess.run(cmd, check=True)


def _valid_probe_stub(duration_sec: float = 1.5) -> dict:
    return {
        "console_errors": [],
        "page_errors": [],
        "failed_requests": [],
        "loaded_fonts_main": [{"family": "Inter", "status": "loaded"}],
        "loaded_fonts_captions": [{"family": "Noto Sans Devanagari", "status": "loaded"}],
        "pill_boxes": [],
        "caption_checks": [{"t": 0.3, "bottom": 1350.0, "hasDevanagari": True}],
        "caption_mount_status": {"mounted": True, "hasChildren": True, "hasDevanagari": True},
        "hf_timeline_captions": {"mounted": True, "src": "captions/captions.html", "sourceFile": "captions/captions.html"},
        "idempotency_time_sec": round(duration_sec * 0.5, 3),
        "idempotency_mae": 0.0,
        "idempotency_passed": True,
    }


def _kc_passing_stub() -> list[dict]:
    return [
        {
            "overall_score": 92.0,
            "all_passed": True,
            "checks": [{"name": "temporal_motion", "passed": True, "score": 99.0, "details": {"static_fraction": 0.02}}],
        },
        {
            "overall_score": 60.0,
            "all_passed": False,
            "checks": [
                {"name": "color_balance", "passed": True, "score": 74.0},
                {"name": "temporal_motion", "passed": True, "score": 99.0, "details": {"static_fraction": 0.02}},
            ],
        },
    ]


def _make_dummy_thumb_and_crop(tmp_path: Path, stem: str = "t") -> tuple[Path, Path]:
    thumb_jpg = tmp_path / f"{stem}.jpg"
    crop_jpg = tmp_path / f"{stem}_2x3.jpg"
    Image.new("RGB", (1080, 1920), (20, 30, 60)).save(thumb_jpg, format="JPEG", quality=85)
    Image.new("RGB", (1080, 1620), (20, 30, 60)).save(crop_jpg, format="JPEG", quality=85)
    return thumb_jpg, crop_jpg


def test_parse_manifest_js_variants(tmp_path: Path) -> None:
    p1 = tmp_path / "m1.js"
    p1.write_text('// note\nwindow.EPISODE_MANIFEST = {"a": 1};\n', encoding="utf-8")
    assert parse_manifest_js(p1) == {"a": 1}

    p2 = tmp_path / "m2.js"
    p2.write_text('MANIFEST_DATA = {"b": 2};', encoding="utf-8")
    assert parse_manifest_js(p2) == {"b": 2}


def test_composer_enforces_parity_and_rejects_unknown_presets(tmp_path: Path) -> None:
    plan, audio_manifest = _make_sample_v2_plan_and_audio(tmp_path, short_durations=(0.5, 0.4, 0.4, 0.4, 0.4))

    # Missing storyboard_ir fails closed
    bad_plan = plan.model_copy(update={"storyboard_ir": None})
    with pytest.raises(CompositionError, match="storyboard_ir"):
        compose_storyboard(REPO_ROOT, bad_plan, audio_manifest=audio_manifest, output_dir=tmp_path / "c1", mix_audio=False)

    # Scene count mismatch fails closed
    bad_audio = dict(audio_manifest, scenes=audio_manifest["scenes"][:1])
    with pytest.raises(CompositionError, match="scene count mismatch"):
        compose_storyboard(REPO_ROOT, plan, audio_manifest=bad_audio, output_dir=tmp_path / "c2", mix_audio=False)

    # Unknown environment preset fails closed
    bad_ir = plan.storyboard_ir.model_copy(deep=True)
    bad_ir.scenes[0].environment_preset = "atlantis_underwater_invalid"
    with pytest.raises(CompositionError, match="unknown environment_preset"):
        compose_storyboard(
            REPO_ROOT,
            plan.model_copy(update={"storyboard_ir": bad_ir}),
            audio_manifest=audio_manifest,
            output_dir=tmp_path / "c3",
            mix_audio=False,
        )

    # Unknown prop fails closed
    bad_ir2 = plan.storyboard_ir.model_copy(deep=True)
    bad_ir2.scenes[0].props = [PropPlacement(id="laser_gun_invalid", kind="weapon", mount="floor", x=300.0)]
    with pytest.raises(CompositionError, match="unknown prop"):
        compose_storyboard(
            REPO_ROOT,
            plan.model_copy(update={"storyboard_ir": bad_ir2}),
            audio_manifest=audio_manifest,
            output_dir=tmp_path / "c4",
            mix_audio=False,
        )

    # Explicit ungrounded floor prop (> 6px off horizon) fails closed
    bad_ir3 = plan.storyboard_ir.model_copy(deep=True)
    bad_ir3.scenes[0].props = [PropPlacement(id="trishul", kind="trishul", mount="floor", x=220.0, y=900.0)]
    with pytest.raises(CompositionError, match="from support"):
        compose_storyboard(
            REPO_ROOT,
            plan.model_copy(update={"storyboard_ir": bad_ir3}),
            audio_manifest=audio_manifest,
            output_dir=tmp_path / "c5",
            mix_audio=False,
        )


def test_composer_mounts_single_fonts_no_threejs_and_auto_grounds_dais(tmp_path: Path) -> None:
    plan, audio_manifest = _make_sample_v2_plan_and_audio(tmp_path, include_pill=True)
    comp = compose_storyboard(
        REPO_ROOT,
        plan,
        audio_manifest=audio_manifest,
        output_dir=tmp_path / "comp",
        mix_audio=False,
        enable_contextual_pills=True,
    )
    assert comp.index_html.is_file()
    assert comp.captions_html.is_file()
    assert comp.captions_data_js.is_file()
    assert not list(comp.output_dir.rglob("three.module.min.js"))
    # Fonts mounted exactly once under fonts/
    assert len(list(comp.output_dir.rglob("fonts.css"))) == 1

    # Scene 1 brahma sits on surface_type="dais" -> composer auto-emits dais stage & sets footY = horizon_y - 98
    sc1 = comp.episode_runtime["scenes"][1]
    assert any(st["type"] == "dais" for st in sc1["stage_elements"])
    assert sc1["characters"][0]["y"] == 1142 - 98
    assert all(item["grounded"] and item["delta_px"] <= 6.0 for item in comp.grounding_report)

    # Pill emitted for scene 0 DOM overlay, disabled for scene 1
    assert comp.episode_runtime["scenes"][0]["pill_title"] == "KAILASH HORIZON"
    assert "pill_title" not in comp.episode_runtime["scenes"][1]
    html_txt = comp.index_html.read_text(encoding="utf-8")
    assert '<canvas id="world-canvas" width="1080" height="1920" data-layout-ignore="true"></canvas>' in html_txt


def test_reject_synthetic_dom_snapshots_and_oversized_mp4(tmp_path: Path) -> None:
    with pytest.raises(QualityGateError, match="dom_snapshots"):
        reject_synthetic_dom_snapshots({"dom_snapshots": [{"scene_index": 0, "ok": True}]})

    # Verify validate_mp4_contract fails closed when file exceeds max_file_bytes
    tiny_mp4 = tmp_path / "tiny.mp4"
    _encode_fast_mp4(tiny_mp4, duration_sec=1.0, video_filter="color=c=navy:s=1080x1920:r=30")
    assert tiny_mp4.stat().st_size > 5000
    with pytest.raises(RenderOptimizeError, match="guardrail"):
        validate_mp4_contract(tiny_mp4, max_file_bytes=4096)

    # Also test optimize_mp4_bitrate works cleanly when tightening an existing MP4
    opt_mp4 = tmp_path / "opt.mp4"
    metrics = optimize_mp4_bitrate(tiny_mp4, opt_mp4, max_file_bytes=DEFAULT_MAX_FILE_BYTES)
    assert metrics["file_bytes"] <= DEFAULT_MAX_FILE_BYTES
    assert (metrics["width"], metrics["height"]) == (1080, 1920)


def test_thumbnail_builder_and_kailash_bounds(tmp_path: Path) -> None:
    spec = ThumbnailSpec(
        pill="VEDIC RELATIVITY",
        headline_line1="TIME SLOWS",
        headline_line2="NEAR KAILASH",
        sub_pill="COSMIC PHYSICS",
        font_weight=800,
        theme="kailash_horizon",
    )
    thumb_jpg = tmp_path / "thumbnail.jpg"
    crop_jpg = tmp_path / "thumbnail_2x3_crop.jpg"
    res = build_thumbnail(REPO_ROOT, spec, thumb_jpg, crop_output_jpg=crop_jpg)
    assert (res.width, res.height) == (1080, 1920)
    assert res.file_bytes <= 2_097_152
    assert res.mean_stddev >= 4.0
    assert res.within_2x3_crop is True
    assert res.kailash_bounds_ok is True
    with Image.open(crop_jpg) as im:
        assert im.size == (1080, 1620)

    # Out-of-bounds Kailash x fails closed
    with pytest.raises(ThumbnailBuildError, match="Kailash geometry"):
        build_thumbnail(
            REPO_ROOT,
            spec,
            tmp_path / "bad_thumb.jpg",
            cover_config={"kailash": {"x": 50, "base_y": 1445, "scale": 1.15}},
        )


def test_fail_closed_fake_snapshot_in_quality_gate(tmp_path: Path) -> None:
    """Verify synthetic dom_snapshots in storyboard_compiled.json causes run_v2_quality_gate to fail closed immediately."""
    plan, audio_manifest = _make_sample_v2_plan_and_audio(tmp_path, short_durations=(0.5, 0.4, 0.4, 0.4, 0.4))
    comp = compose_storyboard(
        REPO_ROOT,
        plan,
        audio_manifest=audio_manifest,
        output_dir=tmp_path / "comp",
        mix_audio=False,
        enable_contextual_pills=True,
    )

    meta = json.loads(comp.compiled_metadata_json.read_text(encoding="utf-8"))
    meta["dom_snapshots"] = [{"scene_index": 0, "ok": True}]
    comp.compiled_metadata_json.write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(QualityGateError, match="dom_snapshots"):
        run_v2_quality_gate(
            REPO_ROOT,
            composition_dir=comp.output_dir,
            mp4_path=tmp_path / "missing.mp4",
            thumbnail_jpg=tmp_path / "missing.jpg",
        )


def test_end_to_end_v2_cli_preview_render_and_fail_closed_qa(tmp_path: Path) -> None:
    """Consolidated real E2E CLI test: preview_frames.main() -> render_and_qa.main() on a 4.35s Shorts episode."""
    from scripts import preview_frames, render_and_qa
    from sutradhar.audio.elevenlabs_tts import DEFAULT_TAG_TEMPLATES, load_pronunciations, prepare_scene_tts_text

    cfg = load_config(REPO_ROOT)
    # Scene 0 = 2.45s so contextual pill stays >= 2.0s on screen (0 craft warnings); scenes 1-4 = 0.3s each + 0.7s tail = 4.35s
    plan, audio_manifest = _make_sample_v2_plan_and_audio(
        tmp_path,
        include_pill=True,
        short_durations=(2.45, 0.30, 0.30, 0.30, 0.30),
        trailing_silence_sec=0.7,
    )
    reps = load_pronunciations(REPO_ROOT, cfg, lang="hi")
    plan_p3 = plan.model_copy(update={"scenes": [sc.model_copy(update={"speed": None}) for sc in plan.scenes]})

    phase3_manifest = {
        "audio": {"narration_full_path": audio_manifest["audio"]["narration_wav_path"]},
        "scenes": [],
    }
    for idx, (psc, asc) in enumerate(zip(plan_p3.scenes, audio_manifest["scenes"])):
        _, tagged = prepare_scene_tts_text(psc, idx, len(plan_p3.scenes), reps, DEFAULT_TAG_TEMPLATES, idx == 2)
        sc_copy = dict(asc)
        sc_copy["applied_speed"] = sc_copy.pop("speed")
        sc_copy["tts_text_applied"] = tagged
        sc_copy["billed_chars"] = len(tagged)
        sc_copy["alignment_match_ratio"] = round(0.81 + 0.03 * idx, 4)
        phase3_manifest["scenes"].append(sc_copy)

    build_dir = tmp_path / "build"
    (build_dir / "audio").mkdir(parents=True, exist_ok=True)
    (build_dir / "episode_plan.json").write_text(json.dumps(plan_p3.model_dump(), ensure_ascii=False), encoding="utf-8")
    (build_dir / "audio" / "audio_manifest.json").write_text(json.dumps(phase3_manifest), encoding="utf-8")

    cfg_tmp = json.loads(json.dumps(cfg))
    cfg_tmp["paths"]["build_dir"] = str(build_dir)

    # 1. Pre-render preview_frames.main(): real compose_storyboard + mix_audio + hf lint + 15-frame snapshot grid.
    #    (run_hf_check + run_chromium_runtime_probe run unmocked on this exact composition right below in render_and_qa.main().)
    with mock.patch("scripts.preview_frames.load_config", return_value=cfg_tmp), \
         mock.patch("scripts.preview_frames.get_project_root", return_value=REPO_ROOT), \
         mock.patch("scripts.preview_frames.run_hf_check", return_value={"ok": True, "exit_code": 0, "total_error_count": 0, "total_warning_count": 0, "craft": {"warningCount": 0}}), \
         mock.patch("scripts.preview_frames.run_chromium_runtime_probe", return_value=_valid_probe_stub(4.35)), \
         mock.patch.object(sys, "argv", ["preview_frames.py"]):
        assert preview_frames.main() == 0

    assert (build_dir / "composition" / "audio" / "master_mix.wav").is_file()
    assert (build_dir / "qa_grid.jpg").is_file()
    assert (build_dir / "qa_grid_safezones.jpg").is_file()
    assert (build_dir / "qa_report.json").is_file()

    preview_rep = json.loads((build_dir / "qa_report.json").read_text(encoding="utf-8"))
    assert preview_rep["lint_clean"] is True
    assert preview_rep["preview_sheet"]["frame_count"] == 15

    # 2. Full render_and_qa.main(): real build_thumbnail + real HyperFrames MP4 render + real fail-closed run_v2_quality_gate
    #    (stubbing KinoCut overall threshold only since 4.35s synth audio lacks speech score; real unmocked KinoCut is tested separately)
    with mock.patch("scripts.render_and_qa.load_config", return_value=cfg_tmp), \
         mock.patch("scripts.render_and_qa.get_project_root", return_value=REPO_ROOT), \
         mock.patch.object(sys, "argv", ["render_and_qa.py"]), \
         mock.patch("sutradhar.qa.quality_gate.kinocut.quality_check", side_effect=_kc_passing_stub()):
        assert render_and_qa.main() == 0

    final_mp4 = build_dir / "final_short.mp4"
    assert final_mp4.is_file() and final_mp4.stat().st_size <= DEFAULT_MAX_FILE_BYTES
    assert (build_dir / "final_qa_grid.jpg").is_file()
    assert (build_dir / "final_qa_grid_safezones.jpg").is_file()
    assert (build_dir / "thumbnail.jpg").is_file()
    assert (build_dir / "thumbnail_2x3_crop.jpg").is_file()
    assert (build_dir / "qa_report.json").is_file()
    assert (build_dir / "render_report.json").is_file()

    render_rep = json.loads((build_dir / "render_report.json").read_text(encoding="utf-8"))
    assert (render_rep["width"], render_rep["height"]) == (1080, 1920)
    gate = render_rep["v2_quality_gate"]
    assert gate["passed"] is True
    assert gate["mp4_gate"]["sample_rate"] == 48000 and gate["mp4_gate"]["channels"] == 2
    assert abs(gate["audio_gate"]["mp4_ebur128"]["integrated_lufs"] - (-14.0)) <= 0.5
    assert gate["audio_gate"]["mp4_ebur128"]["true_peak_dbtp"] <= -1.5

    whisper_qa = gate["audio_gate"]["whisper_alignment"]
    assert whisper_qa["available"] is True
    assert whisper_qa["scene_count"] == 5
    assert whisper_qa["min_match_ratio"] == 0.81
    assert whisper_qa["avg_match_ratio"] == 0.87
    assert [s["alignment_match_ratio"] for s in whisper_qa["per_scene"]] == [0.81, 0.84, 0.87, 0.9, 0.93]

    hf_chk = gate["geometry_gate"]["hyperframes_check"]
    assert hf_chk["ok"] is True
    assert hf_chk["total_error_count"] == 0
    assert hf_chk["total_warning_count"] == 0
    assert (hf_chk.get("craft") or {}).get("warningCount", 0) == 0

    p_probe = gate["geometry_gate"]["chromium_probe"]
    assert p_probe["console_errors"] == []
    assert p_probe["page_errors"] == []
    assert p_probe["idempotency_passed"] is True
    assert p_probe["idempotency_mae"] <= 0.5
    assert p_probe["hf_timeline_captions"]["mounted"] is True
    assert p_probe["caption_mount_status"]["mounted"] is True
    assert p_probe["caption_mount_status"]["hasChildren"] is True
    assert p_probe["caption_mount_status"]["hasDevanagari"] is True
    assert p_probe["caption_checks"] and all(b["bottom"] <= CAPTION_SAFE_BOTTOM_MAX for b in p_probe["caption_checks"])
    assert p_probe["pill_boxes"] and all(
        SHORTS_PILL_MIN_X <= p["left"] and p["right"] <= SHORTS_PILL_MAX_X
        and SHORTS_PILL_MIN_Y <= p["top"] and p["bottom"] <= SHORTS_PILL_MAX_Y
        for p in p_probe["pill_boxes"]
    )
    assert (gate["thumbnail_gate"]["width"], gate["thumbnail_gate"]["height"]) == (1080, 1920)
    assert gate["thumbnail_gate"]["crop_2x3_size"] == [1080, 1620]


def test_captions_mounted_as_sub_composition_in_index_html(tmp_path: Path) -> None:
    """Finding 1 fix: Verify #captions uses data-composition-src/data-composition-id (not data-include)."""
    plan, audio_manifest = _make_sample_v2_plan_and_audio(tmp_path, short_durations=(0.5, 0.4, 0.4, 0.4, 0.4))
    comp = compose_storyboard(
        REPO_ROOT,
        plan,
        audio_manifest=audio_manifest,
        output_dir=tmp_path / "comp",
        mix_audio=False,
    )
    html_text = comp.index_html.read_text(encoding="utf-8")
    assert 'data-composition-id="captions"' in html_text
    assert 'data-composition-src="captions/captions.html"' in html_text
    assert 'data-track-kind="captions"' in html_text
    assert "data-include=" not in html_text


def test_phase3_audio_manifest_narration_full_path_and_parity(tmp_path: Path) -> None:
    """Finding 2 fix: Verify compose_storyboard handles Phase 3 build_audio manifest shape & rejects tampered billed_chars."""
    from sutradhar.audio.elevenlabs_tts import DEFAULT_TAG_TEMPLATES, load_pronunciations, prepare_scene_tts_text

    cfg = load_config(REPO_ROOT)
    plan, audio_manifest = _make_sample_v2_plan_and_audio(tmp_path)
    reps = load_pronunciations(REPO_ROOT, cfg, lang="hi")
    updated_scenes = [sc.model_copy(update={"speed": None}) for sc in plan.scenes]
    plan_p3 = plan.model_copy(update={"scenes": updated_scenes})

    phase3_manifest = {
        "audio": {"narration_full_path": audio_manifest["audio"]["narration_wav_path"]},
        "scenes": [],
    }
    for idx, (psc, asc) in enumerate(zip(plan_p3.scenes, audio_manifest["scenes"])):
        _, tagged = prepare_scene_tts_text(psc, idx, len(plan_p3.scenes), reps, DEFAULT_TAG_TEMPLATES, idx == 2)
        sc_copy = dict(asc)
        sc_copy["applied_speed"] = sc_copy.pop("speed")
        sc_copy["tts_text_applied"] = tagged
        sc_copy["billed_chars"] = len(tagged)
        phase3_manifest["scenes"].append(sc_copy)

    comp = compose_storyboard(
        REPO_ROOT,
        plan_p3,
        audio_manifest=phase3_manifest,
        output_dir=tmp_path / "comp_p3",
        mix_audio=False,
        cfg=cfg,
    )
    assert comp.index_html.is_file()
    assert comp.duration_sec > 0
    assert comp.scene_count == len(plan_p3.scenes)

    # Tampered billed_chars (without matching tts_text_applied) must fail closed
    bad_manifest = json.loads(json.dumps(phase3_manifest))
    bad_manifest["scenes"][0].pop("tts_text_applied")
    bad_manifest["scenes"][0]["billed_chars"] = 999
    with pytest.raises(CompositionError, match="char count mismatch"):
        compose_storyboard(
            REPO_ROOT,
            plan_p3,
            audio_manifest=bad_manifest,
            output_dir=tmp_path / "comp_bad_chars",
            mix_audio=False,
            cfg=cfg,
        )


def test_observatory_cosmos_ground_floor_and_schema_compat(tmp_path: Path) -> None:
    """Finding 3 & 4 fix: observatory_cosmos ground floor, calm_standing/id fallback, pill_y_px, pedestal clock, stale staging."""
    from sutradhar.visual.storyboard_composer import POSE_ALIASES, detect_v2_storyboard_run

    assert POSE_ALIASES["calm_standing"] == "neutral"

    plan, audio_manifest = _make_sample_v2_plan_and_audio(tmp_path, include_pill=True)
    ir = plan.storyboard_ir.model_copy(deep=True)
    ir.scenes[0].characters[0] = CharacterPlacement(
        id="shiva", role="protagonist", x=540.0, surface_type="floor", pose="calm_standing", expr="serene"
    )
    ir.scenes[1].props = [PropPlacement(id="brass_clock", kind="brass_clock", mount="pedestal", x=540.0, y=None, scale=1.0)]
    plan_mod = plan.model_copy(update={"storyboard_ir": ir})

    comp_dir = tmp_path / "comp_compat"
    comp_dir.mkdir(parents=True, exist_ok=True)
    (comp_dir / "engine.js").write_text("stale", encoding="utf-8")
    (comp_dir / "runtime").mkdir(parents=True, exist_ok=True)
    (comp_dir / "runtime" / "obsolete_stale.js").write_text("stale", encoding="utf-8")

    # Omit enable_contextual_pills -> auto-enabled from scene 0 pill
    comp = compose_storyboard(
        REPO_ROOT,
        plan_mod,
        audio_manifest=audio_manifest,
        output_dir=comp_dir,
        mix_audio=False,
    )
    assert not (comp_dir / "engine.js").exists()
    assert not (comp_dir / "runtime" / "obsolete_stale.js").exists()

    assert comp.episode_runtime["enable_contextual_pills"] is True
    assert comp.episode_runtime["scenes"][0]["pill_title"] == "KAILASH HORIZON"
    assert comp.episode_runtime["scenes"][0]["pill_y_px"] == 310
    assert comp.episode_runtime["scenes"][0]["characters"][0]["id"] == "shiva"
    assert comp.episode_runtime["scenes"][0]["characters"][0]["pose"] == "neutral"

    # brass_clock(mount="pedestal", y=None) placed in elevated niche (y=540, not 1142)
    sc1_props = comp.episode_runtime["scenes"][1]["props"]
    assert sc1_props[0]["y"] == 540.0
    assert any(st.get("type") == "clock_niche" for st in comp.episode_runtime["scenes"][1]["stage_elements"])

    # observatory_cosmos floor propagated to runtime JSON
    sc2_env = comp.episode_runtime["scenes"][2]["environment"]
    assert sc2_env.get("ground_top") and sc2_env.get("ground_bot")

    # detect_v2_storyboard_run rejects stale compiled/manifest when episode_plan has storyboard_ir=None
    build_dir = tmp_path / "stale_build"
    (build_dir / "composition").mkdir(parents=True, exist_ok=True)
    (build_dir / "episode_plan.json").write_text(json.dumps({"storyboard_ir": None, "scenes": []}), encoding="utf-8")
    (build_dir / "composition" / "storyboard_compiled.json").write_text("{}", encoding="utf-8")
    (build_dir / "manifest.js").write_text('window.EPISODE_MANIFEST = {"visual_direction_version": "v2_storycraft"};', encoding="utf-8")
    assert detect_v2_storyboard_run(tmp_path, {"paths": {"build_dir": str(build_dir)}}) is False


def test_fail_closed_quality_gate_real_kinocut_and_ebur128(tmp_path: Path) -> None:
    """Finding 4.5 fix: Direct unmocked run_v2_quality_gate raises QualityGateError on real KinoCut + ebur128 failures."""
    plan, audio_manifest = _make_sample_v2_plan_and_audio(
        tmp_path,
        short_durations=(0.30, 0.25, 0.25, 0.25, 0.25),
        trailing_silence_sec=0.7,
    )
    cfg = load_config(REPO_ROOT)
    comp = compose_storyboard(
        REPO_ROOT, plan, audio_manifest=audio_manifest,
        output_dir=tmp_path / "comp_real_fail", mix_audio=False, cfg=cfg,
    )
    thumb_jpg, crop_jpg = _make_dummy_thumb_and_crop(tmp_path, "kc_ebur")

    # Real 2.0s (60-frame) static solid-navy 1080x1920 MP4 with quiet -28 dB audio -> unmocked KinoCut + ebur128 both fail!
    bad_mp4 = tmp_path / "bad_static_quiet.mp4"
    dur = comp.duration_sec
    _encode_fast_mp4(
        bad_mp4,
        duration_sec=dur,
        video_filter="color=c=#080c18:s=1080x1920:r=30",
        audio_filter=f"sine=frequency=220:sample_rate=48000:duration={dur:.3f}",
        af_args=["volume=-28dB,apad"],
    )

    with mock.patch("sutradhar.qa.quality_gate.run_chromium_runtime_probe", return_value=_valid_probe_stub(dur)), \
         mock.patch("sutradhar.qa.quality_gate.run_hf_measure_look", return_value={"skipped": True}), \
         mock.patch(
             "sutradhar.qa.quality_gate.verify_per_scene_motion_and_grid",
             return_value={"grid_frame_count": 15, "final_qa_grid": "stub", "black_frames": [], "frozen_scenes": [], "scene_motion": []},
         ), \
         mock.patch("sutradhar.qa.quality_gate.validate_local_thumbnail", return_value={"bytes": 50000, "width": 1080, "height": 1920}):
        with pytest.raises(QualityGateError) as exc_info:
            run_v2_quality_gate(
                REPO_ROOT,
                composition_dir=comp.output_dir,
                mp4_path=bad_mp4,
                thumbnail_jpg=thumb_jpg,
                crop_2x3_jpg=crop_jpg,
                cfg=cfg,
                run_hf_shorts_check=False,
            )
    msg = str(exc_info.value)
    assert ("KinoCut" in msg or "static" in msg) and "integrated loudness" in msg


def test_fail_closed_quality_gate_real_chromium_and_hf_check_defects(tmp_path: Path) -> None:
    """Finding 4.5 fix: Real Chromium probe & hf check fail closed on unmounted captions, overflow, and hf-seek MAE."""
    plan, audio_manifest = _make_sample_v2_plan_and_audio(
        tmp_path,
        short_durations=(0.45, 0.30, 0.25, 0.25, 0.25),
        trailing_silence_sec=0.8,
    )
    cfg = load_config(REPO_ROOT)
    comp = compose_storyboard(
        REPO_ROOT, plan, audio_manifest=audio_manifest,
        output_dir=tmp_path / "comp_real_probe", mix_audio=True, cfg=cfg,
    )
    out_mp4 = tmp_path / "final.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", f"testsrc2=size=1080x1920:rate=30:duration={comp.duration_sec:.3f}",
            "-i", str(comp.master_wav),
            "-t", f"{comp.duration_sec:.3f}", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-ar", "48000",
            str(out_mp4),
        ],
        check=True,
    )
    thumb_jpg, crop_jpg = _make_dummy_thumb_and_crop(tmp_path, "probe_def")

    orig_index = comp.index_html.read_text(encoding="utf-8")
    orig_caps = comp.captions_html.read_text(encoding="utf-8")

    # 1. Unmounted #captions (data-include instead of data-composition-src) -> full real run_v2_quality_gate(..., run_hf_shorts_check=True) fails closed
    comp.index_html.write_text(
        orig_index.replace('data-composition-src="captions/captions.html"', 'data-include="captions/captions.html"'),
        encoding="utf-8",
    )
    with mock.patch("sutradhar.qa.quality_gate.kinocut.quality_check", side_effect=_kc_passing_stub()), \
         mock.patch("sutradhar.qa.quality_gate.validate_local_thumbnail", return_value={"bytes": 50000, "width": 1080, "height": 1920}):
        with pytest.raises(QualityGateError, match="captions sub-composition not mounted"):
            run_v2_quality_gate(
                REPO_ROOT, composition_dir=comp.output_dir, mp4_path=out_mp4,
                thumbnail_jpg=thumb_jpg, crop_2x3_jpg=crop_jpg,
                master_wav_path=comp.master_wav, cfg=cfg, run_hf_shorts_check=True,
            )

    # 2+3. Caption overflow (> 1395px) AND non-deterministic hf-seek MAE > 0.5 -> one real Chromium probe + validate_runtime_probe_and_hf_check catches both
    comp.index_html.write_text(orig_index, encoding="utf-8")
    comp.captions_html.write_text(orig_caps.replace("top: 1244px;", "top: 1365px;"), encoding="utf-8")
    jitter_script = (
        '<script>window.addEventListener("load",()=>{window.__hfCalls=0;window.addEventListener("hf-seek",()=>{'
        'window.__hfCalls++;const c=document.getElementById("world-canvas");'
        'if(c&&window.__hfCalls>=4){const x=c.getContext("2d");x.fillStyle="#ffffff";x.fillRect(0,0,1080,1920);}'
        '});});</script></body>'
    )
    comp.index_html.write_text(orig_index.replace("</body>", jitter_script), encoding="utf-8")
    probe_defects = run_chromium_runtime_probe(
        REPO_ROOT,
        comp.index_html,
        duration_sec=comp.duration_sec,
        caption_sample_times=[0.2],
    )
    defect_errs = validate_runtime_probe_and_hf_check(
        probe_defects,
        caption_safe_bottom_max=CAPTION_SAFE_BOTTOM_MAX,
        pill_min_x=SHORTS_PILL_MIN_X,
        pill_max_x=SHORTS_PILL_MAX_X,
        pill_min_y=SHORTS_PILL_MIN_Y,
        pill_max_y=SHORTS_PILL_MAX_Y,
    )
    assert any("caption bottom" in err for err in defect_errs)
    assert any("hf-seek" in err and "MAE" in err for err in defect_errs)


def test_remediation_fail_closed_warnings_true_peak_and_shared_probe_validation(tmp_path: Path) -> None:
    """Verify craft/sub-report warnings fail closed, MP4 true peak <= -1.5 dBTP is strict, and shared probe checks reject drift."""
    # 1. HyperFrames returns ok=True even when craft.warningCount=1 -> validate_hf_check_report must fail closed
    craft_warn_payload = {
        "ok": True,
        "exit_code": 0,
        "lint": {"errorCount": 0, "warningCount": 0, "findings": []},
        "runtime": {"errorCount": 0, "warningCount": 0, "findings": []},
        "layout": {"errorCount": 0, "warningCount": 0, "findings": []},
        "motion": {"errorCount": 0, "warningCount": 0, "findings": []},
        "contrast": {"errorCount": 0, "warningCount": 0, "findings": []},
        "craft": {
            "errorCount": 0,
            "warningCount": 1,
            "findings": [{"code": "text_below_floor", "severity": "warning", "message": "20px < 28px"}],
        },
        "audio": {"errorCount": 0, "warningCount": 0, "findings": []},
    }
    errs = validate_hf_check_report(craft_warn_payload)
    assert errs and "warnings=1" in errs[0] and "text_below_floor" in errs[0]

    # 2. Shared probe validator rejects unmounted hf_timeline_captions & out-of-bounds contextual pill
    bad_probe = {
        "console_errors": [],
        "page_errors": [],
        "failed_requests": [],
        "loaded_fonts_main": [{"family": "Inter", "status": "loaded"}],
        "idempotency_passed": True,
        "idempotency_time_sec": 12.6,
        "idempotency_mae": 0.0,
        "caption_mount_status": {"mounted": True, "hasChildren": True, "hasDevanagari": True},
        "caption_checks": [{"t": 1.0, "bottom": 1350.0}],
        "hf_timeline_captions": {"mounted": False},
        "pill_boxes": [{"left": 20.0, "right": 920.0, "top": 296.0, "bottom": 380.0, "scrollHeight": 84, "clientHeight": 84}],
    }
    probe_errs = validate_runtime_probe_and_hf_check(bad_probe, craft_warn_payload)
    assert any("hf_timeline_captions" in e or "timeline #captions" in e for e in probe_errs)
    assert any("contextual pill out of Shorts bounds" in e for e in probe_errs)
    assert any("text_below_floor" in e for e in probe_errs)

    # 3. Quality gate enforces literal MP4 true peak <= -1.5 dBTP (rejects -1.2 dBTP; no +0.5 dB loophole)
    plan, audio_manifest = _make_sample_v2_plan_and_audio(
        tmp_path,
        short_durations=(0.20, 0.20, 0.20, 0.20, 0.20),
        trailing_silence_sec=0.5,
    )
    for idx, asc in enumerate(audio_manifest["scenes"], start=1):
        asc["alignment_match_ratio"] = round(0.70 + 0.05 * idx, 4)
    cfg = load_config(REPO_ROOT)
    comp = compose_storyboard(
        REPO_ROOT, plan, audio_manifest=audio_manifest,
        output_dir=tmp_path / "comp_tp", mix_audio=False, cfg=cfg,
    )
    dummy_wav = tmp_path / "dummy_tp.wav"
    _write_speech_wav(dummy_wav, duration_sec=comp.duration_sec)
    out_mp4 = tmp_path / "tp_test.mp4"
    _encode_fast_mp4(out_mp4, duration_sec=comp.duration_sec)
    thumb_jpg, crop_jpg = _make_dummy_thumb_and_crop(tmp_path, "tp")

    with mock.patch("sutradhar.qa.quality_gate.kinocut.quality_check", side_effect=_kc_passing_stub()), \
         mock.patch(
             "sutradhar.qa.quality_gate.measure_loudness_ebur128",
             side_effect=[
                 {"integrated_lufs": -14.0, "true_peak_dbtp": -2.2, "lra_lu": 3.0},
                 {"integrated_lufs": -14.0, "true_peak_dbtp": -1.2, "lra_lu": 3.0},
             ],
         ), \
         mock.patch("sutradhar.qa.quality_gate.run_chromium_runtime_probe", return_value=_valid_probe_stub(comp.duration_sec)), \
         mock.patch("sutradhar.qa.quality_gate.run_hf_measure_look", return_value={"skipped": True}), \
         mock.patch(
             "sutradhar.qa.quality_gate.verify_per_scene_motion_and_grid",
             return_value={"grid_frame_count": 15, "final_qa_grid": "stub", "black_frames": [], "frozen_scenes": [], "scene_motion": []},
         ), \
         mock.patch("sutradhar.qa.quality_gate.detect_silences", return_value=[]), \
         mock.patch("sutradhar.qa.quality_gate._check_tail_quietness", return_value={"tail_rms_dbfs": -70.0}), \
         mock.patch("sutradhar.qa.quality_gate.validate_local_thumbnail", return_value={"bytes": 50000, "width": 1080, "height": 1920}):
        with pytest.raises(QualityGateError, match=r"MP4 true_peak -1\.20 dBTP > -1\.50 dBTP"):
            run_v2_quality_gate(
                REPO_ROOT,
                composition_dir=comp.output_dir,
                mp4_path=out_mp4,
                thumbnail_jpg=thumb_jpg,
                crop_2x3_jpg=crop_jpg,
                master_wav_path=dummy_wav,
                audio_manifest=audio_manifest,
                cfg=cfg,
                run_hf_shorts_check=False,
            )


def test_kinocut_temporal_motion_timeout_diagnostic_not_masked(tmp_path: Path) -> None:
    """Verify temporal_motion timeout/missing static_fraction surfaces details.diagnostic instead of silent 1.0."""
    plan, audio_manifest = _make_sample_v2_plan_and_audio(
        tmp_path,
        short_durations=(0.20, 0.20, 0.20, 0.20, 0.20),
        trailing_silence_sec=0.5,
    )
    cfg = load_config(REPO_ROOT)
    comp = compose_storyboard(
        REPO_ROOT, plan, audio_manifest=audio_manifest,
        output_dir=tmp_path / "comp_tm_diag", mix_audio=False, cfg=cfg,
    )
    dummy_wav = tmp_path / "dummy_diag.wav"
    _write_speech_wav(dummy_wav, duration_sec=comp.duration_sec)
    out_mp4 = tmp_path / "tm_diag.mp4"
    _encode_fast_mp4(out_mp4, duration_sec=comp.duration_sec)
    thumb_jpg, crop_jpg = _make_dummy_thumb_and_crop(tmp_path, "diag")

    timeout_diag = {"stage": "ffprobe_tblend_motion", "message": "ffprobe timed out"}
    kc_timeout_pair = [
        {
            "overall_score": 93.0,
            "all_passed": True,
            "checks": [
                {
                    "name": "temporal_motion",
                    "passed": False,
                    "score": 0.0,
                    "message": "Could not analyze temporal motion (analysis failed)",
                    "details": {"diagnostic": timeout_diag},
                }
            ],
        },
        {
            "overall_score": 60.5,
            "all_passed": False,
            "checks": [
                {"name": "color_balance", "passed": True, "score": 70.3},
                {
                    "name": "temporal_motion",
                    "passed": False,
                    "score": 0.0,
                    "message": "Could not analyze temporal motion (analysis failed)",
                    "details": {"diagnostic": timeout_diag},
                },
            ],
        },
    ]

    with mock.patch("sutradhar.qa.quality_gate.kinocut.quality_check", side_effect=kc_timeout_pair):
        summary, kc_failures = _evaluate_kinocut_checks(out_mp4, cfg)
    assert summary["static_fraction"] is None
    assert summary["temporal_motion_diagnostic"] == timeout_diag
    assert any("ffprobe_tblend_motion: ffprobe timed out" in f for f in kc_failures)
    assert not any("static_fraction=1.0000" in f for f in kc_failures)

    # Also verify missing static_fraction without diagnostic fails closed without inventing 1.0
    kc_missing_sf = [
        {"overall_score": 93.0, "all_passed": True, "checks": [{"name": "temporal_motion", "passed": False, "score": 0.0, "details": {}}]},
        {"overall_score": 60.5, "all_passed": False, "checks": [
            {"name": "color_balance", "passed": True, "score": 70.3},
            {"name": "temporal_motion", "passed": False, "score": 0.0, "message": "missing metric", "details": {}},
        ]},
    ]
    with mock.patch("sutradhar.qa.quality_gate.kinocut.quality_check", side_effect=kc_missing_sf):
        summary_missing, missing_failures = _evaluate_kinocut_checks(out_mp4, cfg)
    assert summary_missing["static_fraction"] is None
    assert any("missing static_fraction" in f for f in missing_failures)

    # Verify run_v2_quality_gate writes qa_report.json with static_fraction=None and raises diagnostic error
    qa_report_path = tmp_path / "qa_diag_report.json"
    with mock.patch("sutradhar.qa.quality_gate.kinocut.quality_check", side_effect=kc_timeout_pair), \
         mock.patch("sutradhar.qa.quality_gate.measure_loudness_ebur128", return_value={"integrated_lufs": -14.0, "true_peak_dbtp": -2.2, "lra_lu": 3.0}), \
         mock.patch("sutradhar.qa.quality_gate.run_chromium_runtime_probe", return_value=_valid_probe_stub(comp.duration_sec)), \
         mock.patch("sutradhar.qa.quality_gate.run_hf_measure_look", return_value={"skipped": True}), \
         mock.patch(
             "sutradhar.qa.quality_gate.verify_per_scene_motion_and_grid",
             return_value={"grid_frame_count": 15, "final_qa_grid": "stub", "black_frames": [], "frozen_scenes": [], "scene_motion": []},
         ), \
         mock.patch("sutradhar.qa.quality_gate.detect_silences", return_value=[]), \
         mock.patch("sutradhar.qa.quality_gate._check_tail_quietness", return_value={"tail_rms_dbfs": -70.0}), \
         mock.patch("sutradhar.qa.quality_gate.validate_local_thumbnail", return_value={"bytes": 50000, "width": 1080, "height": 1920}):
        with pytest.raises(QualityGateError, match=r"ffprobe_tblend_motion: ffprobe timed out"):
            run_v2_quality_gate(
                REPO_ROOT,
                composition_dir=comp.output_dir,
                mp4_path=out_mp4,
                thumbnail_jpg=thumb_jpg,
                crop_2x3_jpg=crop_jpg,
                master_wav_path=dummy_wav,
                audio_manifest=audio_manifest,
                report_output_path=qa_report_path,
                cfg=cfg,
                run_hf_shorts_check=False,
            )
    written = json.loads(qa_report_path.read_text(encoding="utf-8"))
    assert written["passed"] is False
    assert written["motion_and_look_gate"]["kinocut"]["static_fraction"] is None
    assert written["motion_and_look_gate"]["kinocut"]["temporal_motion_diagnostic"] == timeout_diag


def test_kinocut_long_short_proxy_and_full_res_temporal_motion(tmp_path: Path) -> None:
    """Verify proxy-triggered 1080x1920 Shorts run unmocked KinoCut + full-res Y-plane motion cleanly without timeout."""
    import time

    cfg = load_config(REPO_ROOT)
    moving_mp4 = tmp_path / "dark_moving_2_5s.mp4"
    _encode_fast_mp4(
        moving_mp4,
        duration_sec=2.5,
        video_filter="testsrc2=size=1080x1920:rate=30",
        vf_extra="eq=brightness=-0.25:saturation=0.6",
        audio_filter="sine=frequency=220:sample_rate=48000:duration=2.5",
        af_args=["volume=+6dB"],
    )

    t0 = time.perf_counter()
    with mock.patch("sutradhar.qa.quality_gate._KINOCUT_PROXY_DURATION_THRESHOLD_SEC", 2.0):
        summary, kc_failures = _evaluate_kinocut_checks(moving_mp4, cfg)
    elapsed = time.perf_counter() - t0

    assert elapsed < 30.0, f"Proxy KinoCut gate took too long: {elapsed:.2f}s"
    assert kc_failures == [], f"Unexpected KinoCut failures: {kc_failures}"
    assert summary["analysis_proxy"] is not None
    assert summary["analysis_proxy"]["width"] == 270
    assert summary["analysis_proxy"]["height"] == 480
    assert summary["full_res_temporal_motion"] is not None
    assert summary["full_res_temporal_motion"]["method"] == "ffmpeg_extractplanes_y_diff"
    assert summary["full_res_temporal_motion"]["frames_analyzed"] >= 70
    assert summary["static_fraction"] is not None and summary["static_fraction"] <= 0.15
    assert summary["temporal_motion_diagnostic"] is None
    assert summary["dark_score"] >= 88.0 and summary["dark_all_passed"] is True
    assert summary["default_score"] >= 55.0 and summary["color_balance_passed"] is True

    # Also verify _measure_full_res_temporal_motion detects a truly static 2s 1080x1920 clip accurately
    static_mp4 = tmp_path / "static_2s.mp4"
    _encode_fast_mp4(static_mp4, duration_sec=2.0, video_filter="color=c=#20242c:s=1080x1920:r=30")
    static_tm = _measure_full_res_temporal_motion(static_mp4, width=1080, height=1920)
    assert static_tm["static_fraction"] == 1.0
    assert static_tm["frames_analyzed"] >= 58
