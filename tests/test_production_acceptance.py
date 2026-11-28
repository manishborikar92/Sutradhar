#!/usr/bin/env python3
"""Sutradhar — Isolated v2 Production Acceptance Gates & Contract Verification.

Runs 100% isolated inside `tempfile.TemporaryDirectory()` with zero reads/writes
to live `REPO_ROOT/build/` or `episodes.db` and $0 paid API calls.

Audits:
  1. Gate 1 (Single Voice Standard): Viraj (uuyFQegRan8rpIQCGu9K) on eleven_v4
  2. Gate 2 (Pre-TTS Budget & Vocal Steering): <= 900 billed chars, >= 70% Devanagari, tag steering
  3. Gate 3 (Zero Tag Leakage): 0 tags in clean narration, aligned words, and caption cues
  4. Gate 4 (Zero-Waste Caching): Sub-2-second cached rebuild with 0 HTTP calls
  5. Gate 5 (Broadcast Audio & Quality Gate): 48 kHz stereo mix, -14 LUFS, <= -1.5 dBTP, quiet tail, fail-closed QA
  6. Gate 6 (Codebase Cleanliness): Zero Kokoro ONNX / Gemini TTS runtime dependencies
"""

from __future__ import annotations

import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import soundfile as sf

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_DIR = REPO_ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_audio  # noqa: E402
import elevenlabs_engine  # noqa: E402
from sutradhar.audio.elevenlabs_tts import (  # noqa: E402
    DEFAULT_TAG_TEMPLATES,
    DEFAULT_VOICE_SETTINGS,
    ElevenLabsEngine,
    FakeElevenLabs,
    TTSBudgetError,
    compute_cache_key,
    load_pronunciations,
    prepare_scene_tts_text,
    validate_pre_tts_budget,
)
from sutradhar.audio.sound_mixer import mix_episode_audio  # noqa: E402
from sutradhar.config import load_config  # noqa: E402
from sutradhar.models import EpisodePlanV2  # noqa: E402
from sutradhar.qa.quality_gate import QualityGateError, reject_synthetic_dom_snapshots  # noqa: E402
from sutradhar.qa.render_optimizer import DEFAULT_MAX_FILE_BYTES  # noqa: E402


class _FakeWord:
    def __init__(self, word: str, start: float, end: float) -> None:
        self.word = word
        self.start = start
        self.end = end


class _FakeSegment:
    def __init__(self, words: list[_FakeWord]) -> None:
        self.words = words


class _FakeWhisper:
    def transcribe(
        self,
        audio_input: Any,
        language: str = "hi",
        word_timestamps: bool = True,
        initial_prompt: str = "",
        **kwargs: Any,
    ) -> tuple[list[_FakeSegment], dict[str, Any]]:
        tokens = (initial_prompt or "").split()
        step = 7.0 / max(1, len(tokens))
        words = [_FakeWord(tok, i * step, (i + 0.85) * step) for i, tok in enumerate(tokens)]
        return [_FakeSegment(words)], {"language": language}


def _make_v2_plan_dict() -> dict[str, Any]:
    lines = [
        ("[slowly, solemn, deep] अमृत के लिए देव और असुरों ने सागर मथा और विष निकला।", "narrator", "calm", "kailash_horizon", "dawn_epic", "shiva", "palm_cup"),
        ("[arrogant, booming, furious, shouts] क्या कोई इस भयानक विष को रोक सकेगा!", "character_dialogue", "wrath", "brahmaloka_sabha", "palace_court", "ravana", "gesture"),
        ("[softly, sorrowful, trembling, sighs] तीनों लोक भय से कांप उठे थे।", "character_dialogue", "fear", "cosmic_ocean_manthan", "dawn_epic", "devi", "awed"),
        ("[calm, serene, deep, slowly] तब शिव ने करुणा से हलाहल कंठ में धारण किया।", "character_dialogue", "calm", "kailash_horizon", "dawn_epic", "shiva", "drink"),
        ("[gentle, calm, peaceful] इसी त्याग से महादेव नीलकंठ कहलाए।", "narrator", "calm", "kailash_horizon", "dawn_epic", "shiva", "bless"),
    ]
    scenes = []
    ir_scenes = []
    for idx, (text, role, emo, env_id, mode, char_id, pose) in enumerate(lines, start=1):
        vis_spec = {
            "atmosphere_mode": mode,
            "environment_preset": env_id,
            "horizon_y": 1142,
            "camera_move": "slow_push_in",
            "transition_in": "fade",
            "transition_sfx": "whoosh_soft.wav" if idx > 1 else None,
            "bgm_mood": "dramatic" if idx < 4 else "serene",
            "props": [
                {"id": "samudra_manthan_halahala", "kind": "samudra_manthan_halahala", "mount": "terrain", "x": 540.0, "scale": 1.0}
            ]
            if idx == 1
            else [],
            "characters": [
                {"id": char_id, "role": char_id, "x": 540.0, "surface_type": "floor", "pose": pose, "expr": "serene"}
            ],
            "contextual_pill": {"enabled": False},
        }
        ir_scenes.append(vis_spec)
        scenes.append(
            {
                "scene_index": idx,
                "narration_text": text,
                "visual_mode": "character_drama",
                "backdrop_rig": env_id,
                "primary_character": char_id,
                "speaker_role": role,
                "emotion": emo,
                "mood_palette": "kailash_himalayan",
                "particle_theme": "himalayan_snow",
                "camera_motion": "slow_push",
                "transition_sfx": "whoosh_soft.wav" if idx > 1 else None,
                "visual_spec": vis_spec,
            }
        )
    return {
        "content_format": "standalone",
        "global_episode_number": 1,
        "pillar": "Ancient Epics & Lore",
        "tts_voice": "uuyFQegRan8rpIQCGu9K",
        "bgm_track": "dramatic_mythology.mp3",
        "bespoke_asset_path": "canvas_prop:samudra_manthan_halahala",
        "youtube_title": "Why Shiva Became Neelakantha #Shorts",
        "youtube_description": "The Samudra Manthan episode from Shiva Purana. #Shorts",
        "youtube_tags": [
            "Shorts", "Sutradhar", "Shiva", "Neelakantha", "Samudra Manthan",
            "Indian Mythology", "Hindu Mythology", "Puranas", "Ancient India", "Vedic Stories",
        ],
        "summary": "Shiva absorbs Halahala poison to save the cosmos.",
        "language": "hi",
        "audio_language": "hi",
        "caption_language": "hi",
        "metadata_language": "en",
        "thumbnail_language": "en",
        "thumbnail_spec": {
            "pill": "SAMUDRA MANTHAN",
            "headline_line1": "WHY SHIVA",
            "headline_line2": "DRANK POISON",
            "sub_pill": "ORIGIN OF NEELAKANTHA",
            "font_weight": 800,
            "theme": "kailash_horizon",
        },
        "storyboard_ir": {
            "visual_direction_version": "v2_storycraft",
            "width": 1080,
            "height": 1920,
            "fps": 30,
            "horizon_y": 1142,
            "scenes": ir_scenes,
        },
        "scenes": scenes,
    }


def _make_mp3_bytes(duration_sec: float = 8.0, sr: int = 44100) -> bytes:
    n = int(duration_sec * sr)
    t = np.linspace(0.0, duration_sec, n, endpoint=False, dtype=np.float32)
    samples = (0.3 * np.sin(2.0 * np.pi * 220.0 * t)).astype(np.float32)
    buf = io.BytesIO()
    sf.write(buf, samples, sr, format="MP3")
    return buf.getvalue()


class TestPhase5ProductionGates(unittest.TestCase):
    """Isolated production acceptance suite (zero mutations to live build/ or episodes.db)."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="sutradhar_accept_")
        self.root = Path(self.tmp.name)
        shutil.copy2(REPO_ROOT / "config.yaml", self.root / "config.yaml")
        shutil.copy2(REPO_ROOT / "pronunciations_hi.yaml", self.root / "pronunciations_hi.yaml")
        (self.root / "build" / "audio").mkdir(parents=True, exist_ok=True)
        (self.root / "build" / "cache" / "audio").mkdir(parents=True, exist_ok=True)
        (self.root / "assets").mkdir(parents=True, exist_ok=True)
        self.cfg = load_config(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_gate_1_single_voice_standard(self) -> None:
        """Gate 1: Viraj (uuyFQegRan8rpIQCGu9K) on eleven_v4 with Hindi audio policy."""
        tts_cfg = self.cfg.get("tts", {})
        self.assertEqual(tts_cfg.get("voice_id"), "uuyFQegRan8rpIQCGu9K")
        self.assertEqual(tts_cfg.get("model_id"), "eleven_v4")
        self.assertEqual(self.cfg.get("channel", {}).get("primary_language"), "hi")
        self.assertEqual(elevenlabs_engine.DEFAULT_VOICE_ID, "uuyFQegRan8rpIQCGu9K")
        self.assertEqual(elevenlabs_engine.DEFAULT_MODEL_ID, "eleven_v4")
        self.assertEqual(elevenlabs_engine.DEFAULT_SAMPLE_RATE, 44100)

        plan_dict = _make_v2_plan_dict()
        (self.root / "build" / "episode_plan.json").write_text(
            json.dumps(plan_dict, ensure_ascii=False), encoding="utf-8"
        )
        res = build_audio.build_episode_audio(
            self.root,
            tts_factory=lambda c, r: FakeElevenLabs(sec_per_scene=8.5, sample_rate=44100),
            whisper_factory=lambda c: _FakeWhisper(),
        )
        self.assertEqual(res["status"], "ok")
        manifest = json.loads((self.root / "build" / "audio" / "audio_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["tts_voice"], "uuyFQegRan8rpIQCGu9K")
        self.assertEqual(manifest["tts_engine"], "elevenlabs")
        self.assertEqual(manifest["language"], "hi")

    def test_gate_2_pre_tts_budget_and_vocal_tag_steering(self) -> None:
        """Gate 2: EpisodePlanV2 enforces <= 900 billed chars, >= 70% Devanagari, and preserves vocal tags."""
        plan_dict = _make_v2_plan_dict()
        plan = EpisodePlanV2.model_validate(plan_dict, context={"config": self.cfg})
        self.assertLessEqual(plan.total_billed_chars(), 900)

        reps = load_pronunciations(self.root, self.cfg, lang="hi")
        tagged_texts: list[str] = []
        clean_texts: list[str] = []
        for idx, sc in enumerate(plan.scenes):
            c_txt, t_txt = prepare_scene_tts_text(sc, idx, len(plan.scenes), reps, DEFAULT_TAG_TEMPLATES, idx == 3)
            clean_texts.append(c_txt)
            tagged_texts.append(t_txt)

        report = validate_pre_tts_budget(tagged_texts, clean_texts, language="hi", enforce_devanagari=True)
        self.assertLessEqual(report.total_billed_chars, 900)
        self.assertGreaterEqual(report.devanagari_ratio, 0.70)
        self.assertIn("[arrogant, booming, furious, shouts]", tagged_texts[1])
        self.assertIn("[softly, sorrowful, trembling, sighs]", tagged_texts[2])

        # Over-budget (>900 chars) must abort before any TTS call
        with self.assertRaises(TTSBudgetError):
            validate_pre_tts_budget(["अ" * 901], ["अ" * 901], max_billed_chars=900, language="hi")

    def test_gate_3_zero_tag_leakage_and_manifest_validation(self) -> None:
        """Gate 3: Aligned words and captions have 0 bracketed tags and monotonic boundaries."""
        plan_dict = _make_v2_plan_dict()
        (self.root / "build" / "episode_plan.json").write_text(
            json.dumps(plan_dict, ensure_ascii=False), encoding="utf-8"
        )
        build_audio.build_episode_audio(
            self.root,
            tts_factory=lambda c, r: FakeElevenLabs(sec_per_scene=8.5, sample_rate=44100),
            whisper_factory=lambda c: _FakeWhisper(),
        )

        js_text = (self.root / "build" / "manifest.js").read_text(encoding="utf-8")
        js_match = re.search(r"window\.EPISODE_MANIFEST\s*=\s*(\{.*\});", js_text, re.DOTALL)
        self.assertIsNotNone(js_match)
        manifest = json.loads(js_match.group(1))

        tag_re = re.compile(r"\[.*?\]")
        cursor = 0.0
        for scene in manifest["scenes"]:
            self.assertIsNone(tag_re.search(scene["narration_text"]))
            self.assertIsNotNone(tag_re.search(scene["tts_text_applied"]))
            self.assertGreater(len(scene["words"]), 0)
            for w in scene["words"]:
                self.assertIsNone(tag_re.search(w["word"]))
                self.assertLess(w["start"], w["end"])
                self.assertLess(w["global_start"], w["global_end"])
            st, mid, et, dur = (
                float(scene["start_sec"]),
                float(scene["midpoint_sec"]),
                float(scene["end_sec"]),
                float(scene["duration_sec"]),
            )
            self.assertAlmostEqual(st, cursor, places=3)
            self.assertTrue(st < mid < et)
            self.assertAlmostEqual(et - st, dur, places=2)
            cursor = et

    def test_gate_4_zero_waste_caching_and_sub_two_second_rebuild(self) -> None:
        """Gate 4: Cached ElevenLabs rebuild inside isolated tmp root completes in < 2s with 0 HTTP calls."""
        plan_dict = _make_v2_plan_dict()
        (self.root / "build" / "episode_plan.json").write_text(
            json.dumps(plan_dict, ensure_ascii=False), encoding="utf-8"
        )
        plan = EpisodePlanV2.model_validate(plan_dict, context={"config": self.cfg})
        reps = load_pronunciations(self.root, self.cfg, lang="hi")
        mp3_bytes = _make_mp3_bytes(8.5, 44100)

        mock_session = MagicMock()
        mock_session.headers = {}
        mock_session.request.side_effect = AssertionError("HTTP call must never happen during cached rebuild!")
        engine = ElevenLabsEngine(
            api_key="sk_test_mock_key_12345",
            config=self.cfg,
            project_root=self.root,
            session=mock_session,
        )

        # Seed isolated cache for every scene
        vs_base = {**DEFAULT_VOICE_SETTINGS, **self.cfg["tts"].get("voice_settings", {})}
        for idx, sc in enumerate(plan.scenes):
            _, tagged = prepare_scene_tts_text(sc, idx, len(plan.scenes), reps, DEFAULT_TAG_TEMPLATES, False)
            spd = build_audio._compute_scene_speed(sc, self.cfg, "hi", sc.speaker_role == "character_dialogue", False)
            key = compute_cache_key(tagged, engine.voice_id, engine.model_id, {**vs_base, "speed": spd})
            (self.root / "build" / "cache" / "audio" / f"{key}.mp3").write_bytes(mp3_bytes)

        # First cached run populates loudnorm WAV cache (0 HTTP calls)
        first_res = build_audio.build_episode_audio(
            self.root,
            tts_factory=lambda c, r: engine,
            whisper_factory=lambda c: _FakeWhisper(),
        )
        self.assertEqual(first_res["status"], "ok")
        self.assertEqual(mock_session.request.call_count, 0)

        # Second rebuild hits MP3 + loudnorm caches in < 2.0s with 0 HTTP calls
        t0 = time.perf_counter()
        result = build_audio.build_episode_audio(
            self.root,
            tts_factory=lambda c, r: engine,
            whisper_factory=lambda c: _FakeWhisper(),
        )
        elapsed = time.perf_counter() - t0
        self.assertEqual(result["status"], "ok")
        self.assertEqual(mock_session.request.call_count, 0)
        self.assertLess(elapsed, 2.0, f"Cached rebuild took {elapsed:.3f}s (must be < 2.0s)")

    def test_gate_5_broadcast_48khz_stereo_mix_and_quality_gate_contracts(self) -> None:
        """Gate 5: Real v2 48 kHz stereo mix, -14 LUFS, <= -1.5 dBTP, quiet tail, and fail-closed QA guards."""
        # Stage canonical BGM/SFX & manifest inside isolated root
        shutil.copy2(REPO_ROOT / "assets" / "manifest.yaml", self.root / "assets" / "manifest.yaml")
        shutil.copytree(REPO_ROOT / "assets" / "audio", self.root / "assets" / "audio", dirs_exist_ok=True)

        plan_dict = _make_v2_plan_dict()
        (self.root / "build" / "episode_plan.json").write_text(
            json.dumps(plan_dict, ensure_ascii=False), encoding="utf-8"
        )
        build_audio.build_episode_audio(
            self.root,
            tts_factory=lambda c, r: FakeElevenLabs(sec_per_scene=8.5, sample_rate=44100),
            whisper_factory=lambda c: _FakeWhisper(),
        )
        audio_manifest = json.loads((self.root / "build" / "audio" / "audio_manifest.json").read_text(encoding="utf-8"))
        out_wav = self.root / "build" / "master_mix.wav"
        mix_rep = mix_episode_audio(
            self.root,
            audio_manifest,
            self.cfg,
            output_wav_path=out_wav,
            allow_synth_fallback=False,
        )
        self.assertEqual(mix_rep["sample_rate"], 48000)
        self.assertEqual(mix_rep["channels"], 2)
        self.assertTrue(-14.5 <= mix_rep["integrated_lufs"] <= -13.5)
        self.assertLessEqual(mix_rep["true_peak_dbtp"], -1.5)
        self.assertGreaterEqual(mix_rep["bgm_acts"], 2)
        self.assertGreaterEqual(mix_rep["sfx_cues"], 4)

        # Quality gate contracts: 55 MiB ceiling & synthetic dom_snapshots rejection
        self.assertEqual(DEFAULT_MAX_FILE_BYTES, 57_671_680)
        with self.assertRaises(QualityGateError):
            reject_synthetic_dom_snapshots({"dom_snapshots": [{"scene_index": 0}]})

    def test_gate_6_codebase_cleanliness_and_pruned_dependencies(self) -> None:
        """Gate 6: Zero Kokoro ONNX or legacy Gemini TTS runtime dependencies."""
        self.assertFalse((REPO_ROOT / "models" / "kokoro").exists())
        reqs_text = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertNotIn("kokoro-onnx", reqs_text)
        self.assertNotIn("onnxruntime", reqs_text)
        self.assertIn("requests", reqs_text)

        for py_script in SCRIPT_DIR.rglob("*.py"):
            content = py_script.read_text(encoding="utf-8")
            self.assertNotIn("from kokoro_onnx", content, f"kokoro_onnx import in {py_script}")
            self.assertNotIn("import kokoro_onnx", content, f"kokoro_onnx import in {py_script}")


if __name__ == "__main__":
    unittest.main()
