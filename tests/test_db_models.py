#!/usr/bin/env python3
"""Unit and integration tests for Sutradhar Schema v4 modular foundation."""

from __future__ import annotations

import copy
import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from sutradhar.config import StateError, get_language_policy, load_config, validate_config
from sutradhar.db import (
    SCHEMA_VERSION,
    cmd_context,
    compute_pillar_rotation,
    connect_db,
    heal_and_backfill_live_db,
    migrate_database_schema,
)
from sutradhar.models import (
    EpisodePlan,
    EpisodePlanV2,
    StoryboardIR,
    ThumbnailSpec,
    count_billed_chars,
    devanagari_token_ratio,
    has_devanagari,
)


def _make_hindi_scenes(count: int = 5, long_pad: str = "") -> list[dict[str, Any]]:
    sample_lines = [
        "[slowly, solemn, deep] समुद्र मंथन के समय देव और दानव दोनों अमृत की खोज में थे।",
        "[calm, serene] लेकिन अमृत से पहले सागर की गहराई से भयानक हलाहल विष प्रकट हुआ।",
        "[intense] उस विष की ज्वाला से तीनों लोक और समस्त आकाश जलने लगे थे।",
        "[solemn, deep] तब जगत की रक्षा के लिए भगवान शिव ने उस विष को कंठ में धारण किया।",
        "[gentle, peaceful] इसी त्याग के कारण महादेव को नीलकंठ के नाम से पूजा जाता है।",
    ]
    scenes: list[dict[str, Any]] = []
    for idx in range(1, count + 1):
        line = sample_lines[(idx - 1) % len(sample_lines)]
        if idx == count and long_pad:
            line = f"{line} {long_pad}"
        scenes.append(
            {
                "scene_index": idx,
                "narration_text": line,
                "visual_mode": "character_drama",
                "backdrop_rig": "kailash_horizon",
                "primary_character": "shiva",
                "mood_palette": "kailash_himalayan",
                "particle_theme": "himalayan_snow",
                "camera_motion": "slow_push",
                "visual_spec": {
                    "atmosphere_mode": "dawn_epic",
                    "environment_preset": "kailash_horizon",
                    "horizon_y": 1142,
                    "camera_move": "push_slow",
                    "transition_in": "fade",
                    "bgm_mood": "dramatic",
                    "props": [
                        {
                            "id": "samudra_manthan_halahala" if idx == 1 else f"prop_{idx}",
                            "kind": "halahala_chalice" if idx == 1 else "flame",
                            "mount": "pedestal",
                            "x": 540.0,
                            "scale": 1.0,
                        }
                    ],
                    "characters": [
                        {
                            "id": "shiva",
                            "role": "protagonist",
                            "x": 540.0,
                            "surface_type": "rock",
                            "pose": "calm_standing",
                            "expr": "serene",
                            "turn": 0.0,
                        }
                    ],
                    "contextual_pill": {
                        "enabled": idx == 1,
                        "text": "Halahala" if idx == 1 else None,
                        "y_px": 320,
                    },
                },
            }
        )
    return scenes


def _make_v2_plan(long_pad: str = "") -> dict[str, Any]:
    scenes = _make_hindi_scenes(5, long_pad=long_pad)
    return {
        "content_format": "episodic_series",
        "series_id": 1,
        "series_title": "Shani Katha — Cosmic Justice",
        "pillar": "Ancient Epics & Lore",
        "episode_number_in_series": 2,
        "global_episode_number": 5,
        "tts_voice": "uuyFQegRan8rpIQCGu9K",
        "bgm_track": "dramatic_mythology.mp3",
        "bespoke_asset_path": "canvas_prop:samudra_manthan_halahala",
        "youtube_title": "Why Lord Shiva Held Poison in His Throat #Shorts",
        "youtube_description": "Pure English description explaining the Neelakantha Shiva episode. #Shorts",
        "youtube_tags": ["Shiva", "IndianMythology", "Shorts"],
        "summary": "Standalone English summary without cliffhangers.",
        "language": "hi",
        "audio_language": "hi",
        "caption_language": "hi",
        "metadata_language": "en",
        "thumbnail_language": "en",
        "thumbnail_spec": {
            "pill": "SAMUDRA MANTHAN",
            "headline_line1": "WHY SHIVA DRANK",
            "headline_line2": "COSMIC POISON",
            "sub_pill": "HINDI AUDIO • ENGLISH CAPTIONS",
            "font_weight": 800,
            "theme": "dawn_epic",
        },
        "storyboard_ir": StoryboardIR(scenes=[sc["visual_spec"] for sc in scenes]).model_dump(),
        "scenes": scenes,
    }


class TestSutradharPhase1Foundation(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = load_config(REPO_ROOT)

    def test_language_policy_and_tts_budget_validation(self) -> None:
        policy = get_language_policy(self.cfg)
        self.assertEqual(policy.audio_language, "hi")
        self.assertEqual(policy.caption_language, "hi")
        self.assertEqual(policy.metadata_language, "en")
        self.assertEqual(policy.thumbnail_language, "en")

        bad_meta = copy.deepcopy(self.cfg)
        bad_meta["channel"]["metadata_language"] = "hi"
        with self.assertRaises(StateError):
            validate_config(bad_meta, REPO_ROOT / "config.yaml")

        bad_tts = copy.deepcopy(self.cfg)
        bad_tts["tts"]["max_billed_chars_per_episode"] = 1200
        with self.assertRaises(StateError):
            validate_config(bad_tts, REPO_ROOT / "config.yaml")

    def test_episode_plan_v2_pre_tts_and_bilingual_guards(self) -> None:
        valid = _make_v2_plan()
        plan = EpisodePlanV2.model_validate(valid, context={"config": self.cfg})
        self.assertLessEqual(plan.total_billed_chars(), 900)
        self.assertGreaterEqual(devanagari_token_ratio(" ".join(s.narration_text for s in plan.scenes)), 0.70)
        self.assertEqual(plan.thumbnail_spec.font_weight, 800)

        # Reject > 900 billed chars before TTS call
        oversized = _make_v2_plan(long_pad=("अतिरिक्त विस्तार " * 55).strip())
        self.assertGreater(count_billed_chars(EpisodePlan.model_validate(oversized, context={"config": self.cfg}).scenes), 900)
        with self.assertRaises(ValueError) as ctx_len:
            EpisodePlanV2.model_validate(oversized, context={"config": self.cfg})
        self.assertIn("900 cap", str(ctx_len.exception))

        # Reject Devanagari inside YouTube title, description, tags, or thumbnail
        bad_title = _make_v2_plan()
        bad_title["youtube_title"] = "नीलकंठ महादेव #Shorts"
        with self.assertRaises(ValueError):
            EpisodePlanV2.model_validate(bad_title, context={"config": self.cfg})

        with self.assertRaises(ValueError):
            ThumbnailSpec(pill="महादेव", headline_line1="LINE ONE", headline_line2="LINE TWO")

        # Reject primarily English narration in EpisodePlanV2
        english_narration = _make_v2_plan()
        for sc in english_narration["scenes"]:
            sc["narration_text"] = "[slowly] This is pure English narration pretending to be Hindi audio."
        with self.assertRaises(ValueError) as ctx_hi:
            EpisodePlanV2.model_validate(english_narration, context={"config": self.cfg})
        self.assertIn("Devanagari", str(ctx_hi.exception))

    def test_hindi_and_english_anti_cliffhanger_guards(self) -> None:
        hi_cliff = _make_v2_plan()
        hi_cliff["scenes"][-1]["narration_text"] = "कहानी आगे अगले भाग में जारी रहेगा और सच सामने आएगा।"
        with self.assertRaises(ValueError) as ctx_hi:
            EpisodePlanV2.model_validate(hi_cliff, context={"config": self.cfg})
        self.assertIn("completeness violation", str(ctx_hi.exception).lower())

    def test_idempotent_v3_to_v4_migration_backfill_and_pillar_rotation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_root = Path(td)
            shutil.copy2(REPO_ROOT / "config.yaml", tmp_root / "config.yaml")
            (tmp_root / "assets").mkdir()
            db_path = tmp_root / "episodes.db"

            # Build synthetic pre-v4 DB preserving live schema nuances
            conn = sqlite3.connect(str(db_path))
            conn.executescript(
                """
                CREATE TABLE series (
                    series_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    series_title TEXT NOT NULL,
                    pillar TEXT NOT NULL,
                    tts_voice TEXT NOT NULL,
                    bgm_track TEXT NOT NULL,
                    total_planned_episodes INTEGER DEFAULT NULL,
                    completed_episodes INTEGER NOT NULL DEFAULT 0,
                    series_bible_json TEXT NOT NULL,
                    youtube_playlist_id TEXT,
                    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'COMPLETED')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE episodes (
                    episode_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    series_id INTEGER,
                    episode_number_in_series INTEGER,
                    global_episode_number INTEGER NOT NULL UNIQUE,
                    content_format TEXT NOT NULL DEFAULT 'episodic_series',
                    youtube_title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    bespoke_asset_path TEXT NOT NULL,
                    script_json TEXT NOT NULL,
                    research_sources_json TEXT,
                    youtube_video_id TEXT UNIQUE,
                    scheduled_publish_at TEXT,
                    status TEXT NOT NULL CHECK (status IN ('PUBLISHED', 'PRIVATE_REVIEW', 'FAILED')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE publishing_history (
                    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    episode_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    youtube_video_id TEXT NOT NULL,
                    playlist_id TEXT,
                    status TEXT NOT NULL,
                    verification_json TEXT,
                    recorded_at TEXT
                );
                INSERT INTO series VALUES (1, 'शनि कथा', 'Ancient Epics & Lore', 'Viraj', 'dramatic_mythology.mp3', NULL, 0, '{}', 'PL_1', 'ACTIVE', '2026-11-24');
                INSERT INTO series VALUES (2, 'Hidden History', 'Hidden History', 'Viraj', 'epic_history.mp3', NULL, 1, '{}', 'PL_2', 'ACTIVE', '2026-11-25');
                INSERT INTO episodes VALUES (1, 1, 1, 1, 'episodic_series', 'Ep 1', 'Sum 1', 'assets/svg/diagrams/shani_drishti_mandala.svg', '{"scenes": []}', NULL, 'cd1cc1mhfwg', NULL, 'PUBLISHED', '2026-11-24');
                INSERT INTO episodes VALUES (2, 2, 1, 2, 'episodic_series', 'Ep 2', 'Sum 2', 'assets/svg/backdrops/mehrauli_iron_pillar.svg', '{"scenes": []}', NULL, 'hcKmhzjQkz4', NULL, 'PUBLISHED', '2026-11-25');
                INSERT INTO episodes VALUES (4, NULL, NULL, 4, 'standalone', 'Ep 4', 'Sum 4', 'assets/svg/backdrops/samudra_manthan_halahala.svg', '{"pillar": "Cosmic & Scientific Paradoxes", "scenes": []}', NULL, '7PWFV7lQG6U', NULL, 'PUBLISHED', '2026-11-27');
                INSERT INTO publishing_history VALUES (1, 1, 'INITIAL_UPLOAD', 'Y63AyoTo-Jo', 'PL_1', 'PERMANENTLY_DELETED', NULL, '2026-11-24');
                """
            )
            conn.close()

            c2 = connect_db(db_path)
            try:
                self.assertTrue(migrate_database_schema(c2))
                self.assertEqual(int(c2.execute("PRAGMA user_version").fetchone()[0]), SCHEMA_VERSION)
                stats1 = heal_and_backfill_live_db(c2)
                self.assertEqual(stats1["series_repaired"], 1)
                self.assertIn("7PWFV7lQG6U", stats1["history_backfilled"])

                # Second run must be completely idempotent
                self.assertFalse(migrate_database_schema(c2))
                stats2 = heal_and_backfill_live_db(c2)
                self.assertEqual(stats2["series_repaired"], 0)
                self.assertEqual(stats2["history_backfilled"], [])

                s1 = c2.execute("SELECT completed_episodes, series_title_hi FROM series WHERE series_id = 1").fetchone()
                self.assertEqual(s1["completed_episodes"], 1)
                self.assertEqual(s1["series_title_hi"], "शनि कथा")
                self.assertFalse(has_devanagari(c2.execute("SELECT series_title_en FROM series WHERE series_id = 2").fetchone()["series_title_en"]))

                ep1 = c2.execute("SELECT bespoke_asset_path, legacy_asset_path FROM episodes WHERE episode_id = 1").fetchone()
                self.assertEqual(ep1["bespoke_asset_path"], "canvas_prop:shani_drishti_mandala")
                self.assertEqual(ep1["legacy_asset_path"], "assets/svg/diagrams/shani_drishti_mandala.svg")

                # Monthly budget aggregation ignores cache_hit=1 and counts cache_hit=0
                c2.execute(
                    "INSERT INTO audio_ledger (episode_id, scene_index, sha256_key, billed_chars, cache_hit) VALUES (1, 1, 'k1', 400, 0), (1, 2, 'k2', 350, 1)"
                )
                last_p, next_p = compute_pillar_rotation(c2, self.cfg["channel"]["pillars"])
                self.assertEqual(last_p, "Cosmic & Scientific Paradoxes")
                self.assertEqual(next_p, "Ancient Epics & Lore")
            finally:
                c2.close()

            ctx = cmd_context(tmp_root, self.cfg)
            self.assertEqual(ctx["monthly_tts_budget"]["spent_this_month_billed_chars"], 400)
            self.assertEqual(ctx["monthly_tts_budget"]["remaining_credits"], 29600)
            self.assertEqual(ctx["monthly_tts_budget"]["cache_hits_this_month"], 1)


if __name__ == "__main__":
    unittest.main()
