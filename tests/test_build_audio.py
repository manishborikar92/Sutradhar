#!/usr/bin/env python3
"""Automated unit & integration tests for scripts/build_audio.py (Milestone 3)."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
BUILD_AUDIO_SCRIPT = REPO_ROOT / "scripts" / "build_audio.py"
DB_MANAGER_SCRIPT = REPO_ROOT / "scripts" / "db_manager.py"
REAL_CONFIG = REPO_ROOT / "config.yaml"
REAL_PRONUNCIATIONS = REPO_ROOT / "pronunciations.yaml"


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeKokoro:
    """Deterministic offline Kokoro stub generating real 24kHz audio waveforms."""

    def __init__(self, sec_per_scene: float = 5.4, fail_on_call: int = -1, silent: bool = False) -> None:
        self.sec_per_scene = sec_per_scene
        self.fail_on_call = fail_on_call
        self.silent = silent
        self.calls: list[dict[str, Any]] = []
        self._voices = {
            "am_fenrir": np.ones((1, 256), dtype=np.float32) * 1.0,
            "bm_george": np.ones((1, 256), dtype=np.float32) * 3.0,
            "am_michael": np.ones((1, 256), dtype=np.float32) * 2.0,
        }

    def get_voices(self) -> list[str]:
        return list(self._voices.keys())

    def get_voice_style(self, voice_id: str) -> np.ndarray:
        return self._voices[voice_id]

    def create(
        self, text: str, voice: Any, speed: float = 1.0, lang: str = "en-us"
    ) -> tuple[np.ndarray, int]:
        call_idx = len(self.calls) + 1
        self.calls.append({"text": text, "voice": voice, "speed": speed, "lang": lang})
        if call_idx == self.fail_on_call:
            raise RuntimeError("Simulated ONNX synthesis error")
        sr = 24000
        n_samples = int(round(self.sec_per_scene * sr))
        if self.silent:
            return np.zeros(n_samples, dtype=np.float32), sr
        t = np.linspace(0.0, self.sec_per_scene, n_samples, endpoint=False, dtype=np.float32)
        wave = (0.25 * np.sin(2.0 * np.pi * 220.0 * t)).astype(np.float32)
        return wave, sr


class FakeWord:
    def __init__(self, word: str, start: float, end: float) -> None:
        self.word = word
        self.start = start
        self.end = end


class FakeSegment:
    def __init__(self, words: list[FakeWord]) -> None:
        self.words = words


class FakeWhisper:
    """Deterministic faster-whisper stub emitting evenly timed words from initial_prompt."""

    def __init__(self, drop_word_idx: int = -1, empty: bool = False) -> None:
        self.drop_word_idx = drop_word_idx
        self.empty = empty

    def transcribe(
        self,
        audio_path: str,
        language: str = "en",
        word_timestamps: bool = True,
        initial_prompt: str = "",
        **kwargs: Any,
    ) -> tuple[list[FakeSegment], dict[str, Any]]:
        if self.empty:
            return [], {"language": language}
        tokens = initial_prompt.split()
        step = 5.0 / max(1, len(tokens))
        words: list[FakeWord] = []
        for idx, tok in enumerate(tokens):
            if idx == self.drop_word_idx:
                continue
            words.append(FakeWord(tok, idx * step, (idx + 0.9) * step))
        return [FakeSegment(words)], {"language": language}


def make_episode_plan(
    voice: str = "am_fenrir:0.65+bm_george:0.35",
    scene_count: int = 7,
) -> dict[str, Any]:
    scenes: list[dict[str, Any]] = []
    for idx in range(1, scene_count + 1):
        narration = (
            f"Scene {idx}: Sutradhar reveals how Ravana faced Mount Kailash while "
            "ancient astronomers at Nalanda measured cosmic cycles."
        )
        if idx == 1:
            scenes.append(
                {
                    "scene_index": idx,
                    "narration_text": narration,
                    "visual_mode": "explainer_diagram",
                    "backdrop_rig": "deep_cosmos_nebula",
                    "diagram_rig": "kailash_axis_diagram",
                    "active_diagram_stage": 1,
                    "primary_character": None,
                    "secondary_character": None,
                    "callout_headline": None,
                    "callout_subtext": None,
                    "emotion": "calm",
                    "action_gesture": "idle_breathe",
                    "mood_palette": "cosmic_indigo",
                    "particle_theme": "starfield_warp",
                    "camera_motion": "dramatic_zoom",
                    "transition_sfx": "sub_hit.wav",
                    "pause_after_ms": 200,
                    "emphasis_word": "Kailash",
                }
            )
        else:
            scenes.append(
                {
                    "scene_index": idx,
                    "narration_text": narration,
                    "visual_mode": "character_drama",
                    "backdrop_rig": "mount_kailash",
                    "diagram_rig": None,
                    "active_diagram_stage": None,
                    "primary_character": "sutradhar_narrator",
                    "secondary_character": None,
                    "callout_headline": None,
                    "callout_subtext": None,
                    "emotion": "calm",
                    "action_gesture": "idle_breathe",
                    "mood_palette": "golden_imperial",
                    "particle_theme": "golden_embers",
                    "camera_motion": "slow_push",
                    "transition_sfx": "whoosh_soft.wav",
                    "pause_after_ms": 150,
                    "emphasis_word": "Ravana",
                }
            )
    return {
        "series_id": 1,
        "series_title": "Echoes of Kailash",
        "pillar": "Ancient Epics & Lore",
        "episode_number_in_series": 1,
        "total_planned_episodes": 3,
        "global_episode_number": 1,
        "tts_voice": voice,
        "bgm_track": "dramatic_mythology.mp3",
        "bespoke_asset_path": "assets/svg/diagrams/kailash_axis_diagram.svg",
        "youtube_title": "The Hidden Geometry of Kailash (Part 1/3) #Shorts",
        "youtube_description": "Part 1 of 3 on Sutradhar. #History #Shorts",
        "summary": "Explores mythic and astronomical accounts surrounding Mount Kailash.",
        "scenes": scenes,
    }


class TestBuildAudio(unittest.TestCase):
    def setUp(self) -> None:
        self.mod = load_module(BUILD_AUDIO_SCRIPT, "build_audio_mod")
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        shutil.copy2(REAL_CONFIG, self.root / "config.yaml")
        shutil.copy2(REAL_PRONUNCIATIONS, self.root / "pronunciations.yaml")
        (self.root / "build/audio").mkdir(parents=True, exist_ok=True)
        (self.root / "models/kokoro").mkdir(parents=True, exist_ok=True)
        # Link real model files if present for fast offline testing
        real_onnx = REPO_ROOT / "models/kokoro/kokoro-v1.0.onnx"
        real_voices = REPO_ROOT / "models/kokoro/voices-v1.0.bin"
        if real_onnx.exists() and real_voices.exists():
            try:
                os.link(real_onnx, self.root / "models/kokoro/kokoro-v1.0.onnx")
                os.link(real_voices, self.root / "models/kokoro/voices-v1.0.bin")
            except OSError:
                shutil.copy2(real_onnx, self.root / "models/kokoro/kokoro-v1.0.onnx")
                shutil.copy2(real_voices, self.root / "models/kokoro/voices-v1.0.bin")
        else:
            (self.root / "models/kokoro/kokoro-v1.0.onnx").write_bytes(b"stub-onnx")
            (self.root / "models/kokoro/voices-v1.0.bin").write_bytes(b"stub-voices")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_plan(self, payload: dict[str, Any]) -> None:
        (self.root / "build/episode_plan.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )

    # 1. Pronunciation override logic (whole-word, case-insensitive, longest-first)
    def test_01_pronunciation_substitution_preserves_canonical_boundaries(self) -> None:
        replacements = {
            "Purana": "Poo-raa-nuh",
            "Puranas": "Poo-raa-nuhs",
            "Sutradhar": "Soo-truh-dhaar",
            "Mohenjo-daro": "Mo-hen-jo daa-ro",
            "Ravana": "Raa-vuh-nuh",
        }
        src = "SUTRADHAR reads the Puranas about Ravana and Mohenjo-daro, not Puranasaurus."
        out = self.mod.apply_pronunciations(src, replacements)
        self.assertIn("Soo-truh-dhaar", out)
        self.assertIn("Poo-raa-nuhs", out)
        self.assertIn("Raa-vuh-nuh", out)
        self.assertIn("Mo-hen-jo daa-ro", out)
        self.assertIn("Puranasaurus", out)  # Whole-word boundary preserved

    # 2. Voice validation & weighted vector blending
    def test_02_kokoro_voice_resolution_and_blend_math(self) -> None:
        kokoro = FakeKokoro()
        self.assertEqual(self.mod.resolve_kokoro_voice(kokoro, "am_fenrir"), "am_fenrir")

        blended = self.mod.resolve_kokoro_voice(kokoro, "am_fenrir:0.65+bm_george:0.35")
        self.assertIsInstance(blended, np.ndarray)
        # Expected: 0.65 * 1.0 + 0.35 * 3.0 = 1.70
        self.assertTrue(np.allclose(blended, 1.70, atol=1e-4))

        with self.assertRaises(self.mod.AudioBuildError):
            self.mod.resolve_kokoro_voice(kokoro, "am_nonexistent")

    # 3. Deterministic alignment handles dropped words & preserves monotonicity
    def test_03_alignment_gap_fill_and_monotonicity(self) -> None:
        caption = "Sutradhar explains Ravana near Kailash."
        whisper_words = [
            {"word": "Soo-truh-dhaar", "start": 0.10, "end": 0.65},
            {"word": "explains", "start": 0.70, "end": 1.15},
            # Intentionally drop "Ravana" to test gap interpolation
            {"word": "near", "start": 1.75, "end": 2.00},
            {"word": "Kailash", "start": 2.05, "end": 2.65},
        ]
        words, ratio = self.mod.align_caption_words(
            caption_text=caption,
            whisper_words=whisper_words,
            scene_duration=3.0,
            global_offset=10.0,
        )
        self.assertEqual([w["word"] for w in words], caption.split())
        self.assertGreater(ratio, 0.4)
        for idx, w in enumerate(words):
            self.assertGreaterEqual(w["end"], w["start"])
            self.assertAlmostEqual(w["global_start"], 10.0 + w["start"], places=3)
            if idx > 0:
                self.assertGreaterEqual(w["start"], words[idx - 1]["end"])

    # 4. Full end-to-end build produces WAVs, ffprobe durations & valid manifest.js
    def test_04_end_to_end_audio_build_and_manifest_contract(self) -> None:
        self.write_plan(make_episode_plan(scene_count=7))
        fake_kokoro = FakeKokoro(sec_per_scene=5.5)  # 7 * ~5.62s = ~39.4s (inside 36-46s target)
        fake_whisper = FakeWhisper(drop_word_idx=2)

        result = self.mod.build_episode_audio(
            root=self.root,
            kokoro_factory=lambda m, v: fake_kokoro,
            whisper_factory=lambda c: fake_whisper,
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["scene_count"], 7)
        self.assertIsNone(result["duration_warning"])
        self.assertTrue(36.0 <= result["total_duration_sec"] <= 46.0)

        # Verify pronunciation was applied to TTS input while narration remained canonical
        self.assertIn("Sootradaar", fake_kokoro.calls[0]["text"])
        self.assertIn("Raavana", fake_kokoro.calls[0]["text"])

        # Verify files on disk
        for idx in range(1, 8):
            self.assertTrue((self.root / f"build/audio/scene_{idx}.wav").is_file())
        self.assertTrue((self.root / "build/audio/narration_full.wav").is_file())
        manifest_file = self.root / "build/manifest.js"
        self.assertTrue(manifest_file.is_file())

        raw_js = manifest_file.read_text(encoding="utf-8")
        prefix = "window.EPISODE_MANIFEST = "
        json_body = raw_js.split(prefix, 1)[1].strip().rstrip(";")
        manifest = json.loads(json_body)
        self.assertEqual(len(manifest["scenes"]), 7)
        self.assertEqual(manifest["audio"]["narration_full_path"], "build/audio/narration_full.wav")
        self.assertIn("Sutradhar", manifest["scenes"][0]["narration_text"])
        self.assertIn("Sootradaar", manifest["scenes"][0]["tts_text_applied"])
        self.assertEqual(
            [w["word"] for w in manifest["scenes"][0]["words"]],
            manifest["scenes"][0]["narration_text"].split(),
        )

    # 5. Duration bounds enforcement (hard <34s / >50s fail; 35s warns cleanly)
    def test_05_duration_hard_and_target_bounds(self) -> None:
        self.write_plan(make_episode_plan(scene_count=7))

        # Too short (~21s < 34s) -> hard error
        with self.assertRaises(self.mod.AudioBuildError) as ctx_short:
            self.mod.build_episode_audio(
                root=self.root,
                kokoro_factory=lambda m, v: FakeKokoro(sec_per_scene=2.5),
                whisper_factory=lambda c: FakeWhisper(),
            )
        self.assertIn("violates hard bounds", str(ctx_short.exception))

        # Too long (~56s > 50s) -> hard error
        with self.assertRaises(self.mod.AudioBuildError) as ctx_long:
            self.mod.build_episode_audio(
                root=self.root,
                kokoro_factory=lambda m, v: FakeKokoro(sec_per_scene=7.5),
                whisper_factory=lambda c: FakeWhisper(),
            )
        self.assertIn("violates hard bounds", str(ctx_long.exception))

        # Between hard & target (~34.8s) -> succeeds with duration_warning
        res_warn = self.mod.build_episode_audio(
            root=self.root,
            kokoro_factory=lambda m, v: FakeKokoro(sec_per_scene=4.7),
            whisper_factory=lambda c: FakeWhisper(),
        )
        self.assertIsNotNone(res_warn["duration_warning"])

    # 6. Clean-Canvas contract enforcement (reject empty narration and validate pauses)
    def test_06_rejects_narration_caption_mismatch(self) -> None:
        plan = make_episode_plan()
        plan["scenes"][0]["narration_text"] = "   "
        self.write_plan(plan)
        with self.assertRaises(self.mod.AudioBuildError) as ctx:
            self.mod.build_episode_audio(
                root=self.root,
                kokoro_factory=lambda m, v: FakeKokoro(),
                whisper_factory=lambda c: FakeWhisper(),
            )
        self.assertIn("scenes.0.narration_text", str(ctx.exception))

    # 7. Graceful error handling: missing models, silent TTS, synthesis error, empty Whisper
    def test_07_graceful_failure_modes(self) -> None:
        self.write_plan(make_episode_plan())

        # Missing model when auto-download disabled
        (self.root / "models/kokoro/kokoro-v1.0.onnx").unlink()
        old_env = os.environ.get("SUTRADHAR_ALLOW_MODEL_DOWNLOAD")
        os.environ["SUTRADHAR_ALLOW_MODEL_DOWNLOAD"] = "0"
        try:
            with self.assertRaises(self.mod.AudioBuildError) as ctx_missing:
                self.mod.build_episode_audio(
                    root=self.root,
                    kokoro_factory=lambda m, v: FakeKokoro(),
                    whisper_factory=lambda c: FakeWhisper(),
                )
            self.assertIn("Kokoro model file", str(ctx_missing.exception))
        finally:
            if old_env is None:
                os.environ.pop("SUTRADHAR_ALLOW_MODEL_DOWNLOAD", None)
            else:
                os.environ["SUTRADHAR_ALLOW_MODEL_DOWNLOAD"] = old_env

        # Restore model link -> test silent output rejection
        real_onnx = REPO_ROOT / "models/kokoro/kokoro-v1.0.onnx"
        if real_onnx.exists():
            try:
                os.link(real_onnx, self.root / "models/kokoro/kokoro-v1.0.onnx")
            except OSError:
                shutil.copy2(real_onnx, self.root / "models/kokoro/kokoro-v1.0.onnx")
        else:
            (self.root / "models/kokoro/kokoro-v1.0.onnx").write_bytes(b"stub-onnx")
        with self.assertRaises(self.mod.AudioBuildError) as ctx_silent:
            self.mod.build_episode_audio(
                root=self.root,
                kokoro_factory=lambda m, v: FakeKokoro(silent=True),
                whisper_factory=lambda c: FakeWhisper(),
            )
        self.assertIn("silent or non-finite", str(ctx_silent.exception))

        # Synthesis exception mid-episode -> clean error, no manifest.js written
        with self.assertRaises(self.mod.AudioBuildError) as ctx_fail:
            self.mod.build_episode_audio(
                root=self.root,
                kokoro_factory=lambda m, v: FakeKokoro(fail_on_call=3),
                whisper_factory=lambda c: FakeWhisper(),
            )
        self.assertIn("scene 3", str(ctx_fail.exception))
        self.assertFalse((self.root / "build/manifest.js").exists())

        # Empty Whisper detection -> clean error
        with self.assertRaises(self.mod.AudioBuildError) as ctx_empty:
            self.mod.build_episode_audio(
                root=self.root,
                kokoro_factory=lambda m, v: FakeKokoro(),
                whisper_factory=lambda c: FakeWhisper(empty=True),
            )
        self.assertIn("zero spoken words", str(ctx_empty.exception))

    # 8. CLI strictly rejects dynamic arguments (Antigravity whitelist safety)
    def test_08_cli_rejects_dynamic_arguments(self) -> None:
        env = {**os.environ, "SUTRADHAR_ROOT": str(self.root)}
        proc = subprocess.run(
            [sys.executable, str(BUILD_AUDIO_SCRIPT), "--unexpected-flag"],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout.strip(), "")
        self.assertIn("zero CLI arguments", proc.stderr)

    # 9. Rejection and quarantine of corrupt / truncated model files
    def test_09_corrupt_model_rejection_and_quarantine(self) -> None:
        cfg = self.mod.load_config(self.root)
        corrupt_onnx = self.root / "models/kokoro/kokoro-v1.0.onnx"
        if corrupt_onnx.exists():
            corrupt_onnx.unlink()
        corrupt_onnx.write_bytes(b"corrupt-truncated-data")

        # When auto-download is disabled, must raise AudioBuildError
        old_env = os.environ.get("SUTRADHAR_ALLOW_MODEL_DOWNLOAD")
        os.environ["SUTRADHAR_ALLOW_MODEL_DOWNLOAD"] = "0"
        try:
            with self.assertRaises(self.mod.AudioBuildError) as ctx:
                self.mod.ensure_kokoro_models(self.root, cfg)
            self.assertIn("invalid", str(ctx.exception).lower())
        finally:
            if old_env is None:
                os.environ.pop("SUTRADHAR_ALLOW_MODEL_DOWNLOAD", None)
            else:
                os.environ["SUTRADHAR_ALLOW_MODEL_DOWNLOAD"] = old_env

        # Verify quarantine utility moves file to _quarantine/<timestamp>/
        quarantined = self.mod._quarantine_corrupt_file(corrupt_onnx, "Test quarantine")
        self.assertTrue(quarantined.is_file())
        self.assertFalse(corrupt_onnx.exists())
        self.assertIn("_quarantine", str(quarantined))

    # 10. Structural Protobuf and ZIP archive validation
    def test_10_structural_validation(self) -> None:
        bogus_onnx = self.root / "models/kokoro/bogus.onnx"
        bogus_onnx.write_bytes(b"NOT_A_VALID_ONNX_PROTOBUF")
        with self.assertRaises(self.mod.AudioBuildError) as ctx_onnx:
            self.mod._validate_file_structural(bogus_onnx)
        self.assertIn("Protobuf parsing", str(ctx_onnx.exception))

        bogus_bin = self.root / "models/kokoro/bogus.bin"
        bogus_bin.write_bytes(b"NOT_A_VALID_ZIP_ARCHIVE")
        with self.assertRaises(self.mod.AudioBuildError) as ctx_bin:
            self.mod._validate_file_structural(bogus_bin)
        self.assertIn("ZIP validation", str(ctx_bin.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)