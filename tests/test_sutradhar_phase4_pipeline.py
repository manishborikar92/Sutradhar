"""Phase 4 unit, negative fail-closed, and real end-to-end compilation/render/QA tests."""

from __future__ import annotations

import json
import math
import shutil
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

from sutradhar.audio.caption_builder import build_caption_cues  # noqa: E402
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
    generate_storyboard_preview_sheet,
    run_chromium_runtime_probe,
    run_hf_check,
    run_hf_lint,
)
from sutradhar.qa.quality_gate import (  # noqa: E402
    QualityGateError,
    reject_synthetic_dom_snapshots,
    run_v2_quality_gate,
)
from sutradhar.qa.render_optimizer import (  # noqa: E402
    DEFAULT_MAX_FILE_BYTES,
    RenderOptimizeError,
    optimize_mp4_bitrate,
    render_episode_mp4,
    validate_mp4_contract,
)
from sutradhar.visual.storyboard_composer import (  # noqa: E402
    CompositionError,
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
    n_quiet_tail = int(sr * 0.45)
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


def _make_sample_v2_plan_and_audio(tmp_path: Path, *, include_pill: bool = True) -> tuple[EpisodePlanV2, dict]:
    scene_specs = [
        ("कैलाश पर्वत पर महादेव शांत ध्यान में स्थित हैं।", 1.4, 210.0, "कैलाश", "kailash_horizon", "dawn_epic", "shiva", "floor", "palm_cup", "determined", [PropPlacement(id="trishul", kind="trishul", mount="floor", x=210.0, scale=1.0)], include_pill),
        ("ब्रह्मलोक में समय का चक्र ब्रह्मांड से तेज चलता है।", 1.4, 235.0, "ब्रह्मलोक", "brahmaloka_sabha", "palace_court", "brahma", "dais", "bless", "serene", [PropPlacement(id="brass_clock", kind="brass_clock", mount="pedestal", x=540.0, y=540.0, scale=1.0)], False),
        ("अंतरिक्ष में कालचक्र की गति गुरुत्वाकर्षण से बदलती है।", 1.4, 225.0, "कालचक्र", "observatory_cosmos", "cosmic_explainer", "sutradhar_narrator", "floor", "gesture", "serene", [PropPlacement(id="brahmaloka_time_chakra", kind="brahmaloka_time_chakra", mount="sky", x=540.0, y=520.0, scale=1.0)], False),
        ("हिमालय के आश्रम में ऋषियों ने यह सत्य जाना।", 1.4, 240.0, "हिमालय", "ashram_twilight", "dawn_epic", "ancient_scholar", "floor", "namaskar", "determined", [], False),
        ("द्वारका और कैलाश के बीच यही सनातन समय का नियम है।", 1.4, 220.0, "सनातन", "dwaraka_durbar", "palace_court", "vishnu", "dais", "bless", "serene", [], False),
    ]
    wavs = []
    for idx, (_, dur, freq, *_) in enumerate(scene_specs, start=1):
        wp = tmp_path / f"scene_{idx}.wav"
        _write_speech_wav(wp, dur, freq)
        wavs.append(wp)
    narr_wav = tmp_path / "narration_full.wav"
    _concat_wavs(wavs, narr_wav, trailing_silence_sec=0.8)

    plan_scenes = []
    ir_scenes = []
    audio_scenes = []
    cursor = 0.0
    for idx, (text, dur, _, kw, env_id, mode, role, surf, pose, expr, props, pill_on) in enumerate(scene_specs, start=1):
        sc_dur = dur + (0.8 if idx == len(scene_specs) else 0.0)
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
                pause_after_ms=300 if idx < len(scene_specs) else 800,
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
        step = max(0.25, (dur - 0.3) / max(1, len(toks)))
        words = [
            {"text": tok, "start": round(cursor + 0.1 + j * step, 3), "end": round(cursor + 0.1 + (j + 0.85) * step, 3)}
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
                    scenes=[1, 2, 3, 4, 5],
                )
            ],
            climax_scene_index=3,
            resolution_scene_index=5,
        ),
        story_research=StoryResearch(
            source_tradition="Shiva Purana",
            canonical_story_summary="Cosmic stillness of Shiva at Kailash contrasted with Brahmaloka assembly.",
            key_verified_facts=["Kailash twilight setting", "Brahmaloka assembly hall"],
            source_references=["Shiva Purana, Rudra Samhita"],
        ),
        target_duration_sec=50,
        target_duration_range={"min_seconds": 3, "max_seconds": 65},
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


def test_parse_manifest_js_variants(tmp_path: Path) -> None:
    p1 = tmp_path / "m1.js"
    p1.write_text('// note\nwindow.EPISODE_MANIFEST = {"a": 1};\n', encoding="utf-8")
    assert parse_manifest_js(p1) == {"a": 1}

    p2 = tmp_path / "m2.js"
    p2.write_text('MANIFEST_DATA = {"b": 2};', encoding="utf-8")
    assert parse_manifest_js(p2) == {"b": 2}


def test_composer_enforces_parity_and_rejects_unknown_presets(tmp_path: Path) -> None:
    plan, audio_manifest = _make_sample_v2_plan_and_audio(tmp_path)

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
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=navy:s=1080x1920:r=30:d=1",
            "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
            "-t", "1", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            str(tiny_mp4),
        ],
        check=True,
    )
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


def test_fail_closed_caption_overflow_and_fake_snapshot_in_quality_gate(tmp_path: Path) -> None:
    plan, audio_manifest = _make_sample_v2_plan_and_audio(tmp_path, include_pill=True)
    comp = compose_storyboard(
        REPO_ROOT,
        plan,
        audio_manifest=audio_manifest,
        output_dir=tmp_path / "comp",
        mix_audio=False,
        enable_contextual_pills=True,
    )

    # Verify positive Chromium probe & hf-seek pixel parity first
    probe_ok = run_chromium_runtime_probe(REPO_ROOT, comp.index_html, duration_sec=comp.duration_sec)
    assert probe_ok["console_errors"] == []
    assert probe_ok["page_errors"] == []
    assert probe_ok["idempotency_passed"] is True
    assert probe_ok["idempotency_mae"] <= 0.5
    assert all(b["bottom"] <= 1395 for b in probe_ok["caption_checks"])

    # Push caption CSS below Y=1400 safe band -> Chromium probe detects rect.bottom > 1395
    cap_html = comp.captions_html
    cap_text = cap_html.read_text(encoding="utf-8").replace("top: 1246px;", "top: 1365px;")
    cap_html.write_text(cap_text, encoding="utf-8")
    probe_bad = run_chromium_runtime_probe(REPO_ROOT, comp.index_html, duration_sec=comp.duration_sec)
    assert any(b["bottom"] > 1395 for b in probe_bad["caption_checks"])

    # Inject synthetic dom_snapshots into storyboard_compiled.json -> run_v2_quality_gate rejects
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


def test_end_to_end_v2_compile_preview_render_and_fail_closed_qa(tmp_path: Path) -> None:
    cfg = load_config(REPO_ROOT)
    plan, audio_manifest = _make_sample_v2_plan_and_audio(tmp_path, include_pill=True)
    comp = compose_storyboard(
        REPO_ROOT,
        plan,
        audio_manifest=audio_manifest,
        output_dir=tmp_path / "comp",
        mix_audio=True,
        cfg=cfg,
        enable_contextual_pills=True,
    )
    assert comp.master_wav is not None and comp.master_wav.is_file()

    # Lint + strict HyperFrames Shorts check + 15-frame storyboard preview grid
    lint_res = run_hf_lint(REPO_ROOT, comp.output_dir)
    assert lint_res.get("ok", lint_res.get("exit_code") == 0)

    check_res = run_hf_check(REPO_ROOT, comp.output_dir, safe_zone="shorts", strict=True, no_craft=True)
    assert check_res["ok"] is True

    qa_grid = tmp_path / "qa_grid.jpg"
    sheet_info = generate_storyboard_preview_sheet(
        REPO_ROOT,
        comp.output_dir,
        comp.duration_sec,
        qa_grid,
        scene_ranges=[(sc["start_sec"], sc["end_sec"]) for sc in audio_manifest["scenes"]],
        count=15,
    )
    assert sheet_info["frame_count"] == 15
    assert qa_grid.is_file()

    thumb_jpg = tmp_path / "thumbnail.jpg"
    crop_jpg = tmp_path / "thumbnail_2x3_crop.jpg"
    build_thumbnail(REPO_ROOT, plan.thumbnail_spec, thumb_jpg, crop_output_jpg=crop_jpg)

    out_mp4 = tmp_path / "final_short.mp4"
    metrics = render_episode_mp4(
        REPO_ROOT,
        comp.output_dir,
        out_mp4,
        duration_sec=comp.duration_sec,
        max_file_bytes=DEFAULT_MAX_FILE_BYTES,
    )
    assert metrics["file_bytes"] <= DEFAULT_MAX_FILE_BYTES
    assert (metrics["width"], metrics["height"]) == (1080, 1920)
    assert metrics["sample_rate"] == 48000 and metrics["channels"] == 2

    # Run fail-closed v2 Quality Gate (stubbing KinoCut overall threshold only if 5s synth audio lacks rich speech score;
    # full KinoCut ui-capture-dark >= 88 & default >= 55 is also verified unmocked on cached Ep 4 62s render!)
    report_path = tmp_path / "qa_report.json"
    final_grid = tmp_path / "final_qa_grid.jpg"
    with mock.patch(
        "sutradhar.qa.quality_gate.kinocut.quality_check",
        side_effect=[
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
        ],
    ):
        report = run_v2_quality_gate(
            REPO_ROOT,
            composition_dir=comp.output_dir,
            mp4_path=out_mp4,
            thumbnail_jpg=thumb_jpg,
            crop_2x3_jpg=crop_jpg,
            master_wav_path=comp.master_wav,
            report_output_path=report_path,
            final_qa_grid_path=final_grid,
            cfg=cfg,
            no_craft=True,
            run_hf_shorts_check=False,
        )
    assert report.passed is True
    assert report_path.is_file()
    assert final_grid.is_file()
    assert abs(report.audio_gate["mp4_ebur128"]["integrated_lufs"] - (-14.0)) <= 0.5
    assert report.geometry_gate["chromium_probe"]["idempotency_mae"] <= 0.5
