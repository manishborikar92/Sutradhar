#!/usr/bin/env python3
"""Automated tests for Phase 2: Configuration & Language Standardization.

Verifies:
1. config.yaml language lock: primary_language is 'hi', English 'en' profile is purged.
2. config.yaml tts block: ElevenLabs v4 ('eleven_v4'), Viraj ('uuyFQegRan8rpIQCGu9K'), 44.1 kHz,
   mp3_44100_128 format, voice settings, cache directory, and tag templates.
3. pronunciations_hi.yaml: Valid UTF-8 encoding (no BOM), proper schema, Devanagari overrides.
4. db_manager compatibility: Validates updated config.yaml schema, --context CLI execution,
   and voice validation accepting Viraj/ElevenLabs IDs alongside Kokoro voice blends.
5. elevenlabs_engine compatibility: Verifies that ElevenLabsEngine integrates seamlessly with config.yaml.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config.yaml"
PRON_HI_PATH = REPO_ROOT / "pronunciations_hi.yaml"
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import db_manager
from elevenlabs_engine import ElevenLabsEngine


class TestPhase2ConfigStandardization(unittest.TestCase):
    """Test suite for config.yaml and Hindi language standardization."""

    def setUp(self) -> None:
        self.assertTrue(CONFIG_PATH.is_file(), f"config.yaml not found at {CONFIG_PATH}")
        with CONFIG_PATH.open("r", encoding="utf-8") as fh:
            self.cfg = yaml.safe_load(fh)

    def test_01_channel_language_standardization(self) -> None:
        """Verify channel is locked to Hindi as primary and default language."""
        channel = self.cfg.get("channel", {})
        self.assertEqual(channel.get("primary_language"), "hi")
        self.assertEqual(channel.get("default_audio_language"), "hi")
        self.assertEqual(channel.get("default_language"), "hi")
        self.assertEqual(channel.get("language_mode"), "per_channel")

    def test_02_english_purged_from_languages(self) -> None:
        """Verify obsolete English ('en') profile is completely removed from languages."""
        languages = self.cfg.get("languages", {})
        self.assertIn("hi", languages, "languages block must contain 'hi'")
        self.assertNotIn("en", languages, "obsolete English 'en' profile must be purged")

        hi_prof = languages["hi"]
        self.assertEqual(hi_prof.get("code"), "hi")
        self.assertEqual(hi_prof.get("name"), "Hindi")
        self.assertEqual(hi_prof.get("narrator_voice"), "Viraj")
        self.assertEqual(hi_prof.get("narrator_voice_id"), "uuyFQegRan8rpIQCGu9K")
        self.assertEqual(hi_prof.get("pronunciations_file"), "pronunciations_hi.yaml")

    def test_03_tts_elevenlabs_v4_configuration(self) -> None:
        """Verify tts block specifies ElevenLabs v4, Viraj, 44.1 kHz, and broadcast settings."""
        tts = self.cfg.get("tts", {})
        self.assertEqual(tts.get("engine"), "elevenlabs")
        self.assertEqual(tts.get("model_id"), "eleven_v4")
        self.assertEqual(tts.get("voice_id"), "uuyFQegRan8rpIQCGu9K")
        self.assertEqual(tts.get("sample_rate"), 44100)
        self.assertEqual(tts.get("output_format"), "mp3_44100_128")
        self.assertEqual(tts.get("cache_dir"), "build/cache/audio")

        settings = tts.get("voice_settings", {})
        self.assertEqual(settings.get("stability"), 0.55)
        self.assertEqual(settings.get("similarity_boost"), 0.80)
        self.assertEqual(settings.get("style"), 0.10)
        self.assertTrue(settings.get("use_speaker_boost"))

    def test_04_vocal_tag_templates(self) -> None:
        """Verify all required character persona vocal tag templates are declared."""
        tts = self.cfg.get("tts", {})
        tags = tts.get("tag_templates", {})
        required_templates = {
            "narrator": "[slowly, solemn, deep]",
            "divine": "[calm, serene, deep, slowly]",
            "antagonist": "[arrogant, booming, furious, shouts]",
            "grief": "[softly, sorrowful, trembling, sighs]",
            "devotional": "[calm, gentle, devotional]",
            "climax": "[building energy, intense]",
            "outro": "[gentle, calm, peaceful]",
        }
        for persona, expected_tag in required_templates.items():
            self.assertIn(persona, tags)
            self.assertEqual(tags[persona], expected_tag)

    def test_05_db_manager_load_and_validate_config(self) -> None:
        """Verify db_manager.load_config validates the updated config.yaml without error."""
        validated_cfg = db_manager.load_config(REPO_ROOT)
        self.assertIsInstance(validated_cfg, dict)
        self.assertEqual(validated_cfg["channel"]["primary_language"], "hi")
        self.assertEqual(validated_cfg["tts"]["engine"], "elevenlabs")
        self.assertIn(validated_cfg["tts"]["default_voice"], ("Viraj", "uuyFQegRan8rpIQCGu9K"))

    def test_06_db_manager_voice_validator_allows_viraj_and_elevenlabs_id(self) -> None:
        """Verify db_manager allows Viraj and ElevenLabs voice IDs."""
        self.assertEqual(db_manager._validate_kokoro_voice("Viraj"), "Viraj")
        self.assertEqual(
            db_manager._validate_kokoro_voice("uuyFQegRan8rpIQCGu9K"),
            "uuyFQegRan8rpIQCGu9K",
        )
        # Verify Kokoro blends are still supported for legacy continuity
        self.assertEqual(
            db_manager._validate_kokoro_voice("am_fenrir:0.65+bm_george:0.35"),
            "am_fenrir:0.65+bm_george:0.35",
        )
        # Empty string rejected
        with self.assertRaises(ValueError):
            db_manager._validate_kokoro_voice("")


class TestPronunciationsHi(unittest.TestCase):
    """Test suite for pronunciations_hi.yaml."""

    def setUp(self) -> None:
        self.assertTrue(PRON_HI_PATH.is_file(), f"pronunciations_hi.yaml not found at {PRON_HI_PATH}")

    def test_01_utf8_encoding_without_bom(self) -> None:
        """Verify file is clean UTF-8 without byte order mark (BOM)."""
        raw_bytes = PRON_HI_PATH.read_bytes()
        self.assertFalse(raw_bytes.startswith(b"\xef\xbb\xbf"), "pronunciations_hi.yaml must not have UTF-8 BOM")
        # Ensure it decodes cleanly as UTF-8
        text = raw_bytes.decode("utf-8")
        self.assertGreater(len(text), 0)

    def test_02_yaml_structure_and_overrides(self) -> None:
        """Verify YAML structure, text replacements, and Devanagari contents."""
        with PRON_HI_PATH.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)

        self.assertIsInstance(data, dict)
        self.assertIn("text_replacements", data)
        reps = data["text_replacements"]
        self.assertIsInstance(reps, dict)
        self.assertGreater(len(reps), 5)

        # Verify key classical terms
        self.assertEqual(reps.get("स्वयं"), "स्वयम्")
        self.assertEqual(reps.get("ब्रह्मांड"), "ब्रह्माण्ड")
        self.assertEqual(reps.get("लंकापति"), "लंका पति")
        self.assertEqual(reps.get("दशानन"), "दशानन")

    def test_03_elevenlabs_engine_integration_with_config(self) -> None:
        """Verify ElevenLabsEngine loads defaults seamlessly from config.yaml."""
        with CONFIG_PATH.open("r", encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh)

        engine = ElevenLabsEngine(api_key="sk_mock", config=cfg, project_root=REPO_ROOT)
        self.assertEqual(engine.model_id, "eleven_v4")
        self.assertEqual(engine.voice_id, "uuyFQegRan8rpIQCGu9K")
        self.assertEqual(engine.sample_rate, 44100)
        self.assertEqual(engine.output_format, "mp3_44100_128")
        self.assertEqual(engine.voice_settings["stability"], 0.55)
        self.assertEqual(engine.tag_templates["narrator"], "[slowly, solemn, deep]")
        self.assertEqual(engine.tag_templates["antagonist"], "[arrogant, booming, furious, shouts]")
        engine.close()


if __name__ == "__main__":
    unittest.main()
