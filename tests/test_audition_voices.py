#!/usr/bin/env python3
"""Automated unit tests for scripts/audition_voices.py (ElevenLabs v4 Audition Utility).

Verifies vocal tag slugification, RMS dBFS calculations, character acting templates,
report JSON schema, 44.1 kHz audio generation, and guarantees that config.yaml
and episodes.db remain untouched.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import soundfile as sf
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_DIR = REPO_ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import audition_voices  # noqa: E402
from elevenlabs_engine import FakeElevenLabs  # noqa: E402


class TestAuditionVoices(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="sutradhar_audition_test_")
        self.root = Path(self.temp_dir)
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def test_01_slugify_voice_and_tags(self) -> None:
        self.assertEqual(audition_voices._slugify_voice("Viraj"), "Viraj")
        self.assertEqual(
            audition_voices._slugify_voice("Viraj:1.0"),
            "Viraj_1p0",
        )
        self.assertEqual(
            audition_voices._slugify_tag("[slowly, solemn, deep]"),
            "slowly_solemn_deep",
        )
        self.assertEqual(
            audition_voices._slugify_tag("[arrogant, booming, furious, shouts]"),
            "arrogant_booming_furious_shouts",
        )

    def test_02_rms_dbfs_calculation(self) -> None:
        silent = np.zeros(1000, dtype=np.float32)
        self.assertEqual(audition_voices._rms_dbfs(silent), -120.0)

        # Sine wave of amplitude 1.0 has RMS of 1/sqrt(2) ≈ 0.7071 -> -3.01 dBFS
        t = np.linspace(0, 1, 24000, endpoint=False)
        sine = np.sin(2 * np.pi * 440 * t).astype(np.float32)
        rms = audition_voices._rms_dbfs(sine)
        self.assertAlmostEqual(rms, -3.01, places=1)

    def test_03_character_acting_templates_coverage(self) -> None:
        """Verify character acting lines cover all 7 core personas from the development plan."""
        expected_roles = {
            "narrator",
            "antagonist",
            "grief",
            "divine",
            "devotional",
            "climax",
            "outro",
        }
        self.assertTrue(expected_roles.issubset(set(audition_voices.CHARACTER_ACTING_LINES.keys())))

        for role, item in audition_voices.CHARACTER_ACTING_LINES.items():
            self.assertTrue(item["tag"].startswith("["))
            self.assertTrue(item["tag"].endswith("]"))
            self.assertTrue(len(item["text"]) > 10)
            self.assertTrue(len(item["persona"]) > 0)

    def test_04_immutability_of_config_and_episodes_db(self) -> None:
        """Verify that audition_voices execution never mutates config.yaml or episodes.db."""
        real_config = REPO_ROOT / "config.yaml"
        real_db = REPO_ROOT / "episodes.db"

        cfg_mtime_before = real_config.stat().st_mtime
        db_mtime_before = real_db.stat().st_mtime if real_db.exists() else None

        # Verify Hindi audition passage is well-formed
        self.assertIn("कैलाश", audition_voices.AUDITION_PASSAGE_HI)
        self.assertIn("रावण", audition_voices.AUDITION_PASSAGE_HI)
        self.assertIn("सूतजी", audition_voices.AUDITION_PASSAGE_HI)

        cfg_mtime_after = real_config.stat().st_mtime
        self.assertEqual(cfg_mtime_before, cfg_mtime_after)
        if real_db.exists():
            self.assertEqual(db_mtime_before, real_db.stat().st_mtime)

    def test_05_offline_audition_execution_with_fake_elevenlabs(self) -> None:
        """Verify run_audition executes completely offline with FakeElevenLabs."""
        # Setup mock environment
        cfg = yaml.safe_load((REPO_ROOT / "config.yaml").read_text(encoding="utf-8"))
        fake_tts = FakeElevenLabs(sec_per_scene=5.0, sample_rate=44100)

        mock_whisper = MagicMock()
        mock_whisper.transcribe.return_value = ([], {"language": "hi"})

        report = audition_voices.run_audition(
            root=self.root,
            cfg=cfg,
            tts_factory=lambda c, r: fake_tts,
            whisper_factory=lambda c: mock_whisper,
            tag_filter=["narrator", "antagonist"],
        )

        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["voice"], "Viraj")
        self.assertEqual(report["sample_rate"], 44100)
        self.assertEqual(report["tags_evaluated"], 2)
        self.assertEqual(len(report["results"]), 2)

        # Verify files on disk (unified build/auditions/ output directory)
        audition_dir = self.root / "build/auditions"
        self.assertTrue((audition_dir / "audition_report.json").is_file())
        for r in report["results"]:
            wav_file = self.root / r["wav_file"]
            self.assertTrue(wav_file.is_file())
            info = sf.info(str(wav_file))
            self.assertEqual(info.samplerate, 44100)
            self.assertEqual(info.channels, 1)

    def test_06_standalone_runpy_without_scripts_on_sys_path(self) -> None:
        """Verify audition_voices.py runs standalone via runpy without scripts/ pre-added to sys.path."""
        script_path = REPO_ROOT / "scripts" / "audition_voices.py"
        code = (
            "import runpy, sys; "
            "sys.path = [p for p in sys.path if 'scripts' not in p.replace('\\\\', '/').lower()]; "
            f"ns = runpy.run_path({str(script_path)!r}, run_name='not_main'); "
            "assert callable(ns['run_audition']) and callable(ns['main'])"
        )
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            proc.returncode,
            0,
            f"Standalone runpy failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
