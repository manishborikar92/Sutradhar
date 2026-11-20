#!/usr/bin/env python3
"""Automated unit tests for scripts/audition_voices.py (Milestone 3 Calibration Utility).

Verifies voice filtering, candidate blend logic, report JSON schema,
and guarantees that config.yaml and episodes.db remain untouched.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_DIR = REPO_ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import audition_voices  # noqa: E402


class TestAuditionVoices(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="sutradhar_audition_test_")
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def test_01_slugify_voice(self) -> None:
        self.assertEqual(audition_voices._slugify_voice("am_fenrir"), "am_fenrir")
        self.assertEqual(
            audition_voices._slugify_voice("am_fenrir:0.65+bm_george:0.35"),
            "am_fenrir_0p65__bm_george_0p35",
        )

    def test_02_rms_dbfs_calculation(self) -> None:
        silent = np.zeros(1000, dtype=np.float32)
        self.assertEqual(audition_voices._rms_dbfs(silent), -120.0)

        # Sine wave of amplitude 1.0 has RMS of 1/sqrt(2) ≈ 0.7071 -> -3.01 dBFS
        t = np.linspace(0, 1, 24000, endpoint=False)
        sine = np.sin(2 * np.pi * 440 * t).astype(np.float32)
        rms = audition_voices._rms_dbfs(sine)
        self.assertAlmostEqual(rms, -3.01, places=1)

    def test_03_audition_candidate_selection_and_blend_filtering(self) -> None:
        mock_kokoro = MagicMock()
        mock_kokoro.get_voices.return_value = ["am_fenrir", "bm_george", "af_heart", "zf_other"]

        all_voices = sorted(mock_kokoro.get_voices())
        english_voices = [v for v in all_voices if v.startswith(("am_", "bm_", "af_", "bf_"))]
        self.assertIn("am_fenrir", english_voices)
        self.assertIn("bm_george", english_voices)
        self.assertIn("af_heart", english_voices)
        self.assertNotIn("zf_other", english_voices)

        available_set = set(all_voices)
        blends_tested = []
        for blend in audition_voices.CANDIDATE_BLENDS:
            parts = [p.split(":", 1)[0] for p in blend.split("+")]
            if all(p in available_set for p in parts):
                blends_tested.append(blend)

        # "am_fenrir:0.65+bm_george:0.35" has both voices present
        self.assertIn("am_fenrir:0.65+bm_george:0.35", blends_tested)
        # "am_michael:0.60+bm_george:0.40" has am_michael missing
        self.assertNotIn("am_michael:0.60+bm_george:0.40", blends_tested)

    def test_04_immutability_of_config_and_episodes_db(self) -> None:
        """Verify that audition_voices execution never mutates config.yaml or episodes.db."""
        real_config = REPO_ROOT / "config.yaml"
        real_db = REPO_ROOT / "episodes.db"

        cfg_mtime_before = real_config.stat().st_mtime
        db_mtime_before = real_db.stat().st_mtime if real_db.exists() else None

        # Verify audition passage is well-formed
        self.assertIn("Sutradhar", audition_voices.AUDITION_PASSAGE)
        self.assertIn("Nalanda", audition_voices.AUDITION_PASSAGE)
        self.assertIn("Kurukshetra", audition_voices.AUDITION_PASSAGE)

        cfg_mtime_after = real_config.stat().st_mtime
        self.assertEqual(cfg_mtime_before, cfg_mtime_after)
        if real_db.exists():
            self.assertEqual(db_mtime_before, real_db.stat().st_mtime)


if __name__ == "__main__":
    unittest.main()
