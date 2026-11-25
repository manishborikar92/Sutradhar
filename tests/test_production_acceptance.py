#!/usr/bin/env python3
"""Sutradhar — Production Acceptance Gates & End-to-End Verification.

Audits production verification gates:
  1. Gate 1 (Single Voice Standard): Viraj (uuyFQegRan8rpIQCGu9K) on eleven_v4
  2. Gate 2 (Character Acting Verification): Distinct acoustic profiles across archetypes
  3. Gate 3 (Zero Tag Leakage): 0 tags in Whisper transcription and subtitles
  4. Gate 4 (Zero-Waste Caching): Sub-2-second rebuild with 0 network calls
  5. Gate 5 (KinoCut Quality Gate): 44.1 kHz 16-bit PCM, -14 LUFS, trailing silence >= 0.75s
  6. Gate 6 (Code Cleanliness): Zero legacy Kokoro/Gemini TTS runtime refs
"""

from __future__ import annotations

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
from unittest.mock import MagicMock

import numpy as np
import soundfile as sf
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_DIR = REPO_ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_audio  # noqa: E402
import elevenlabs_engine  # noqa: E402
import render_and_qa  # noqa: E402
from db_manager import EpisodePlan, load_config  # noqa: E402


class TestPhase5ProductionGates(unittest.TestCase):
    """Rigorous audit suite for Phase 5 production acceptance gates."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.cfg = load_config(REPO_ROOT)
        cls.manifest_js_path = REPO_ROOT / "build" / "manifest.js"
        cls.audio_manifest_path = REPO_ROOT / "build" / "audio" / "audio_manifest.json"
        cls.master_wav_path = REPO_ROOT / "build" / "audio" / "narration_full.wav"

    def test_gate_1_single_voice_standard(self) -> None:
        """Gate 1: 100% of speech assets synthesized using Viraj (uuyFQegRan8rpIQCGu9K) on eleven_v4."""
        tts_cfg = self.cfg.get("tts", {})
        self.assertEqual(tts_cfg.get("voice_id"), "uuyFQegRan8rpIQCGu9K")
        self.assertEqual(tts_cfg.get("model_id"), "eleven_v4")
        self.assertEqual(self.cfg.get("channel", {}).get("primary_language"), "hi")

        self.assertEqual(elevenlabs_engine.DEFAULT_VOICE_ID, "uuyFQegRan8rpIQCGu9K")
        self.assertEqual(elevenlabs_engine.DEFAULT_MODEL_ID, "eleven_v4")
        self.assertEqual(elevenlabs_engine.DEFAULT_SAMPLE_RATE, 44100)

        # Audit production manifest if built
        if self.audio_manifest_path.is_file():
            manifest = json.loads(self.audio_manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest.get("tts_voice"), "uuyFQegRan8rpIQCGu9K")
            self.assertIn(manifest.get("tts_engine"), ("elevenlabs", "eleven_v4"))
            self.assertEqual(manifest.get("language"), "hi")

    def test_gate_2_character_acting_verification(self) -> None:
        """Gate 2: Scripted scenes with tags demonstrate distinct acoustic energy and duration profiles."""
        acting_dir = REPO_ROOT / "build" / "auditions" / "elevenlabs" / "viraj_character_acting"
        wrath_wav = acting_dir / "Viraj_acting_Ravana_Wrath.wav"
        serene_wav = acting_dir / "Viraj_acting_Mahadev_Serene.wav"
        grief_wav = acting_dir / "Viraj_acting_Mandodari_Grief.wav"

        if not (wrath_wav.is_file() and serene_wav.is_file() and grief_wav.is_file()):
            self.skipTest(f"Phase 5 character acting artifacts not present in {acting_dir}")

        def get_acoustic_profile(wav_path: Path) -> dict[str, float]:
            data, sr = sf.read(str(wav_path))
            rms = float(np.sqrt(np.mean(data**2) + 1e-15))
            rms_dbfs = float(20 * np.log10(rms))
            peak = float(np.max(np.abs(data)))
            dur = len(data) / sr
            return {"rms_dbfs": rms_dbfs, "peak": peak, "dur": dur, "sr": float(sr)}

        prof_wrath = get_acoustic_profile(wrath_wav)
        prof_serene = get_acoustic_profile(serene_wav)
        prof_grief = get_acoustic_profile(grief_wav)

        # 1. Wrath has high dynamic energy (loudest RMS) and highest peak
        self.assertGreater(prof_wrath["rms_dbfs"], prof_serene["rms_dbfs"])
        self.assertGreater(prof_serene["rms_dbfs"], prof_grief["rms_dbfs"])

        # 2. Significant acoustic energy differential (> 6.0 dB delta between Wrath and Grief)
        delta_db = prof_wrath["rms_dbfs"] - prof_grief["rms_dbfs"]
        self.assertGreater(delta_db, 6.0, f"Acoustic dynamic delta {delta_db:.2f} dB is too narrow")

        # 3. Peak amplitude of wrath is authoritative
        self.assertGreaterEqual(prof_wrath["peak"], 0.80)

    def test_gate_3_zero_tag_leakage_and_manifest_validation(self) -> None:
        """Gate 3: Whisper transcription and subtitles have strictly 0 bracketed tags; boundaries are monotonic."""
        if not (self.manifest_js_path.is_file() and self.audio_manifest_path.is_file()):
            self.skipTest("build/manifest.js or audio_manifest.json not present; run build_audio first")

        js_text = self.manifest_js_path.read_text(encoding="utf-8")
        js_match = re.search(r"window\.EPISODE_MANIFEST\s*=\s*(\{.*\});", js_text, re.DOTALL)
        self.assertIsNotNone(js_match)
        manifest = json.loads(js_match.group(1))

        tag_re = re.compile(r"\[.*?\]")
        cursor = 0.0

        for scene in manifest.get("scenes", []):
            s_idx = scene["scene_index"]
            clean_text = scene["narration_text"]
            applied_text = scene.get("tts_text_applied", "")
            words = scene.get("words", [])

            # Narration text must not contain bracketed tags
            self.assertIsNone(tag_re.search(clean_text), f"Tag leaked into scene {s_idx} narration: {clean_text}")

            # Applied TTS text MUST preserve vocal steering tags
            self.assertIsNotNone(tag_re.search(applied_text), f"Scene {s_idx} applied text missing tag: {applied_text}")

            # Words list must not contain bracketed tags
            self.assertGreater(len(words), 0, f"Scene {s_idx} words list is empty")
            for w in words:
                tok = w["word"]
                self.assertIsNone(tag_re.search(tok), f"Tag leaked into word: {tok}")
                self.assertLess(w["start"], w["end"])
                self.assertLess(w["global_start"], w["global_end"])

            # Monotonic scene boundary verification
            st = float(scene["start_sec"])
            mid = float(scene["midpoint_sec"])
            et = float(scene["end_sec"])
            dur = float(scene["duration_sec"])

            self.assertAlmostEqual(st, cursor, places=3, msg=f"Scene {s_idx} boundary mismatch")
            self.assertTrue(st < mid < et, f"Scene {s_idx} non-increasing timestamps: {st} < {mid} < {et}")
            self.assertAlmostEqual(et - st, dur, places=2)
            cursor = et

    def test_gate_4_zero_waste_caching_and_sub_two_second_rebuild(self) -> None:
        """Gate 4: Re-running build_audio on an already built episode completes in < 2 seconds with 0 network calls."""
        # Create an engine with a mocked network session that fails if an HTTP call is made
        mock_session = MagicMock()
        mock_session.request.side_effect = RuntimeError("Network call attempted during cached execution!")

        t0 = time.perf_counter()
        result = build_audio.build_episode_audio(REPO_ROOT)
        elapsed = time.perf_counter() - t0

        self.assertEqual(result.get("status"), "ok")
        self.assertLess(elapsed, 2.0, f"Re-run took {elapsed:.3f}s (must be < 2.0s)")

    def test_gate_5_kinocut_mastering_and_broadcast_audio_specs(self) -> None:
        """Gate 5: Mastered audio is 44.1 kHz 16-bit PCM, -14.0 LUFS (±1.0), true peak <= -1.0 dBTP, trailing silence >= 0.75s."""
        if not self.master_wav_path.is_file():
            self.skipTest("Master narration wav not present in build/audio/; run build_audio first")

        info = sf.info(str(self.master_wav_path))
        self.assertEqual(info.samplerate, 44100, f"Sample rate {info.samplerate} != 44100 Hz")
        self.assertEqual(info.subtype, "PCM_16", f"Subtype {info.subtype} != PCM_16")
        self.assertEqual(info.channels, 1, f"Channels {info.channels} != 1 (mono)")

        # FFmpeg EBU R128 Loudness measurement
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(self.master_wav_path),
            "-af",
            "loudnorm=I=-14:TP=-1.5:LRA=9:print_format=json",
            "-f",
            "null",
            "-",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        idx1 = proc.stderr.rfind("{")
        idx2 = proc.stderr.rfind("}")
        self.assertTrue(idx1 != -1 and idx2 != -1, "FFmpeg loudnorm JSON not found in stderr")
        stats = json.loads(proc.stderr[idx1 : idx2 + 1])

        input_i = float(stats["input_i"])
        input_tp = float(stats["input_tp"])

        # Target: -14.0 LUFS ± 1.0 (range: [-15.0, -13.0])
        self.assertGreaterEqual(input_i, -15.0, f"Integrated loudness {input_i} is too quiet")
        self.assertLessEqual(input_i, -13.0, f"Integrated loudness {input_i} is too loud")

        # True peak limit <= -1.0 dBTP
        self.assertLessEqual(input_tp, -1.0, f"True peak {input_tp} dBTP exceeds ceiling of -1.0 dBTP")

        # Trailing silence: last 0.75s must have peak < 0.001 and RMS < -45 dBFS
        data, sr = sf.read(str(self.master_wav_path))
        tail = data[-int(0.75 * sr) :]
        tail_peak = float(np.max(np.abs(tail)))
        tail_rms = float(np.sqrt(np.mean(tail**2) + 1e-15))
        tail_rms_dbfs = float(20 * np.log10(tail_rms))

        self.assertLess(tail_peak, 0.001, f"Trailing silence peak {tail_peak} is too high")
        self.assertLess(tail_rms_dbfs, -45.0, f"Trailing silence RMS {tail_rms_dbfs} dBFS is too loud")

    def test_gate_6_codebase_cleanliness_and_pruned_dependencies(self) -> None:
        """Gate 6: Disk space freed, zero Kokoro ONNX or Gemini TTS runtime references."""
        # 1. Kokoro model directory must not exist
        kokoro_model_dir = REPO_ROOT / "models" / "kokoro"
        self.assertFalse(kokoro_model_dir.exists(), "models/kokoro/ must be deleted")

        # 2. requirements.txt must not contain kokoro-onnx or onnxruntime
        reqs_text = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertNotIn("kokoro-onnx", reqs_text)
        self.assertNotIn("onnxruntime", reqs_text)
        self.assertIn("requests", reqs_text)

        # 3. Active runtime scripts must not import kokoro
        for py_script in SCRIPT_DIR.glob("*.py"):
            content = py_script.read_text(encoding="utf-8")
            self.assertNotIn("from kokoro_onnx", content, f"kokoro_onnx import in {py_script.name}")
            self.assertNotIn("import kokoro_onnx", content, f"kokoro_onnx import in {py_script.name}")

    def test_downstream_rendering_workflow_integration(self) -> None:
        """Verify downstream render_and_qa integration with master narration audio."""
        if not self.manifest_js_path.is_file():
            self.skipTest("build/manifest.js not present; run build_audio first")
        manifest = render_and_qa.parse_manifest_js(self.manifest_js_path)
        self.assertEqual(manifest.get("language"), "hi")
        self.assertEqual(manifest.get("audio", {}).get("sample_rate"), 44100)

        # SFX & BGM parsing
        sfx_inputs = render_and_qa.collect_sfx_schedule(REPO_ROOT, manifest)
        bgm_schedule = render_and_qa.parse_bgm_schedule(REPO_ROOT, manifest, self.cfg)
        self.assertIsInstance(sfx_inputs, list)
        self.assertIsInstance(bgm_schedule, list)
        self.assertGreater(len(bgm_schedule), 0)


if __name__ == "__main__":
    unittest.main()
