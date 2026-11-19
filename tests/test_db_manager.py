#!/usr/bin/env python3
"""End-to-end CLI and state-machine test suite for scripts/db_manager.py."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_MANAGER = REPO_ROOT / "scripts" / "db_manager.py"
REAL_CONFIG = REPO_ROOT / "config.yaml"


def make_valid_scenes(bespoke_stem: str, count: int = 7) -> list[dict[str, Any]]:
    scenes: list[dict[str, Any]] = []
    for idx in range(1, count + 1):
        if idx == 1:
            scenes.append(
                {
                    "scene_index": idx,
                    "narration_text": (
                        "Cross this invisible cosmic boundary and the universe outside "
                        "ages millions of years in a single heartbeat."
                    ),
                    "caption_text": (
                        "Cross this invisible cosmic boundary and the universe outside "
                        "ages millions of years in a single heartbeat."
                    ),
                    "visual_mode": "explainer_diagram",
                    "backdrop_rig": "deep_cosmos_nebula",
                    "diagram_rig": bespoke_stem,
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
                }
            )
        elif idx % 2 == 0:
            scenes.append(
                {
                    "scene_index": idx,
                    "narration_text": (
                        "Gravity pulls harder on your feet than your head until "
                        "every atom stretches into a blazing cosmic thread."
                    ),
                    "caption_text": (
                        "Gravity pulls harder on your feet than your head until "
                        "every atom stretches into a blazing cosmic thread."
                    ),
                    "visual_mode": "character_drama",
                    "backdrop_rig": "deep_cosmos_nebula",
                    "diagram_rig": None,
                    "active_diagram_stage": None,
                    "primary_character": "sutradhar_narrator",
                    "secondary_character": None,
                    "callout_headline": None,
                    "callout_subtext": None,
                    "emotion": "shock",
                    "action_gesture": "raise_weapon",
                    "mood_palette": "cosmic_indigo",
                    "particle_theme": "quantum_nodes",
                    "camera_motion": "slow_push",
                    "transition_sfx": "whoosh_soft.wav",
                }
            )
        else:
            scenes.append(
                {
                    "scene_index": idx,
                    "narration_text": (
                        "Inside that trapped region of space every path forward points "
                        "straight toward the singularity at the center."
                    ),
                    "caption_text": (
                        "Inside that trapped region of space every path forward points "
                        "straight toward the singularity at the center."
                    ),
                    "visual_mode": "kinetic_callout",
                    "backdrop_rig": "quantum_grid_void",
                    "diagram_rig": None,
                    "active_diagram_stage": None,
                    "primary_character": None,
                    "secondary_character": None,
                    "callout_headline": "10,000,000x GRAVITY",
                    "callout_subtext": "Tidal shear at the horizon",
                    "emotion": "calm",
                    "action_gesture": "idle_breathe",
                    "mood_palette": "obsidian_amber",
                    "particle_theme": "starfield_warp",
                    "camera_motion": "slow_pull",
                    "transition_sfx": "riser_tension.wav",
                }
            )
    return scenes


class TestDbManager(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        shutil.copy2(REAL_CONFIG, self.root / "config.yaml")

        for rel in (
            "build/audio",
            "assets/bgm",
            "assets/sfx",
            "assets/svg/characters",
            "assets/svg/backdrops",
            "assets/svg/diagrams",
        ):
            (self.root / rel).mkdir(parents=True, exist_ok=True)

        # Seed dummy asset files for --context inventory verification
        (self.root / "assets/svg/characters/sutradhar_narrator.svg").write_text("<svg/>", encoding="utf-8")
        (self.root / "assets/svg/backdrops/deep_cosmos_nebula.svg").write_text("<svg/>", encoding="utf-8")
        (self.root / "assets/svg/diagrams/black_hole_anatomy.svg").write_text("<svg/>", encoding="utf-8")
        (self.root / "assets/bgm/cosmic_mystery.mp3").write_bytes(b"")
        (self.root / "assets/sfx/sub_hit.wav").write_bytes(b"")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_cli(self, flag: str) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "SUTRADHAR_ROOT": str(self.root)}
        return subprocess.run(
            [sys.executable, str(DB_MANAGER), flag],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

    def write_build_json(self, filename: str, payload: dict[str, Any]) -> None:
        (self.root / "build" / filename).write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )

    def test_full_lifecycle_and_guardrails(self) -> None:
        # 1. --context before --init must fail loudly
        res = self.run_cli("--context")
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("--init", res.stderr)

        # 2. --init (and idempotent re-run)
        res = self.run_cli("--init")
        self.assertEqual(res.returncode, 0, res.stderr)
        init_out = json.loads(res.stdout)
        self.assertEqual(init_out["status"], "ok")
        self.assertTrue((self.root / "episodes.db").is_file())

        res_repeat = self.run_cli("--init")
        self.assertEqual(res_repeat.returncode, 0, res_repeat.stderr)

        # 3. Initial --context check
        res = self.run_cli("--context")
        self.assertEqual(res.returncode, 0, res.stderr)
        ctx = json.loads(res.stdout)
        self.assertIsNone(ctx["active_series"])
        self.assertEqual(ctx["next_episode_number_in_series"], 1)
        self.assertEqual(ctx["next_global_episode_number"], 1)
        self.assertEqual(ctx["channel_config"]["primary_language"], "en")
        self.assertEqual(ctx["channel_config"]["upload_mode"], "private_review")
        self.assertIn("sutradhar_narrator", ctx["available_rigs"]["characters"])
        self.assertIn("cosmic_mystery.mp3", ctx["available_rigs"]["bgm"])

        # 4. Reject invalid new_series_plan.json (invalid pillar + wrong episode count)
        self.write_build_json(
            "new_series_plan.json",
            {
                "series_title": "Invalid Series",
                "pillar": "Not A Real Pillar",
                "tts_voice": "am_fenrir",
                "bgm_track": "cosmic_mystery.mp3",
                "total_planned_episodes": 2,
                "series_bible_json": {"episodes": [{"ep": 1}, {"ep": 2}]},
            },
        )
        res = self.run_cli("--create-series")
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("validation failed", res.stderr)

        # 5. Create valid 3-episode Series #1
        series1_plan = {
            "series_title": "Secrets of the Event Horizon",
            "pillar": "Cosmic & Scientific Paradoxes",
            "tts_voice": "am_fenrir:0.65+bm_george:0.35",
            "bgm_track": "cosmic_mystery.mp3",
            "total_planned_episodes": 3,
            "series_bible_json": {
                "arc_summary": "A 3-part descent into black hole physics.",
                "episodes": [
                    {"part": 1, "hook": "Time freezes at the edge."},
                    {"part": 2, "hook": "Spaghettification tears matter apart."},
                    {"part": 3, "hook": "Hawking radiation erases the black hole."},
                ],
            },
        }
        self.write_build_json("new_series_plan.json", series1_plan)
        res = self.run_cli("--create-series")
        self.assertEqual(res.returncode, 0, res.stderr)
        created = json.loads(res.stdout)
        self.assertEqual(created["series_id"], 1)
        self.assertEqual(created["series_status"], "ACTIVE")

        # 6. Reject creating a second series while Series #1 is ACTIVE
        self.write_build_json(
            "new_series_plan.json",
            {
                **series1_plan,
                "series_title": "Competing Series",
                "pillar": "Hidden History",
            },
        )
        res = self.run_cli("--create-series")
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("still ACTIVE", res.stderr)

        # 7. Reject invalid episode_plan.json (unfeatured bespoke asset)
        bad_ep1 = {
            "series_id": 1,
            "series_title": "Secrets of the Event Horizon",
            "pillar": "Cosmic & Scientific Paradoxes",
            "episode_number_in_series": 1,
            "total_planned_episodes": 3,
            "global_episode_number": 1,
            "tts_voice": "am_fenrir:0.65+bm_george:0.35",
            "bgm_track": "cosmic_mystery.mp3",
            "bespoke_asset_path": "assets/svg/diagrams/unused_diagram.svg",
            "youtube_title": "Time Stops at the Event Horizon (Part 1/3) #Shorts",
            "youtube_description": "Part 1 of 3 on Sutradhar. #Space #Shorts",
            "summary": "Explores extreme gravitational time dilation near an event horizon.",
            "scenes": make_valid_scenes("horizon_clock_dilation"),
        }
        self.write_build_json("episode_plan.json", bad_ep1)
        self.write_build_json(
            "publish_result.json",
            {
                "video_id": "vid_001",
                "playlist_id": "PL_SERIES_001",
                "upload_status": "PRIVATE_REVIEW",
                "scheduled_publish_at": None,
            },
        )
        res = self.run_cli("--record-published")
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("must be actively featured", res.stderr)

        # 8. Record a FAILED upload on Part 1 -> must NOT advance completed_episodes
        ep1 = {**bad_ep1, "bespoke_asset_path": "assets/svg/diagrams/horizon_clock_dilation.svg"}
        self.write_build_json("episode_plan.json", ep1)
        self.write_build_json(
            "publish_result.json",
            {
                "video_id": None,
                "playlist_id": "PL_SERIES_001",
                "upload_status": "FAILED",
                "error_message": "Simulated network timeout",
            },
        )
        res = self.run_cli("--record-published")
        self.assertEqual(res.returncode, 0, res.stderr)
        fail_out = json.loads(res.stdout)
        self.assertEqual(fail_out["completed_episodes"], 0)
        self.assertEqual(fail_out["series_status"], "ACTIVE")

        # Verify context still asks for Part 1 / Global 1
        ctx_after_fail = json.loads(self.run_cli("--context").stdout)
        self.assertEqual(ctx_after_fail["next_episode_number_in_series"], 1)
        self.assertEqual(ctx_after_fail["next_global_episode_number"], 1)
        self.assertEqual(ctx_after_fail["active_series"]["youtube_playlist_id"], "PL_SERIES_001")

        # 9. Retry Part 1 as PRIVATE_REVIEW -> succeeds cleanly, replaces FAILED row
        self.write_build_json(
            "publish_result.json",
            {
                "video_id": "vid_001",
                "playlist_id": "PL_SERIES_001",
                "upload_status": "PRIVATE_REVIEW",
                "scheduled_publish_at": None,
            },
        )
        res = self.run_cli("--record-published")
        self.assertEqual(res.returncode, 0, res.stderr)
        rec1 = json.loads(res.stdout)
        self.assertEqual(rec1["completed_episodes"], 1)
        self.assertEqual(rec1["series_status"], "ACTIVE")
        self.assertEqual(rec1["youtube_playlist_id"], "PL_SERIES_001")

        # 10. Reject mismatched playlist_id on Part 2 (transaction rollback check)
        ep2 = {
            **ep1,
            "episode_number_in_series": 2,
            "global_episode_number": 2,
            "bespoke_asset_path": "assets/svg/diagrams/spaghettification_gradient.svg",
            "youtube_title": "Why Black Holes Stretch You Into Atoms (Part 2/3) #Shorts",
            "scenes": make_valid_scenes("spaghettification_gradient"),
        }
        self.write_build_json("episode_plan.json", ep2)
        self.write_build_json(
            "publish_result.json",
            {
                "video_id": "vid_002",
                "playlist_id": "PL_WRONG_PLAYLIST",
                "upload_status": "PRIVATE_REVIEW",
            },
        )
        res = self.run_cli("--record-published")
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("Playlist mismatch", res.stderr)

        # Confirm rollback left completed_episodes at 1
        ctx_mid = json.loads(self.run_cli("--context").stdout)
        self.assertEqual(ctx_mid["active_series"]["completed_episodes"], 1)

        # 11. Record Part 2 & Part 3 cleanly -> Series #1 transitions ACTIVE -> COMPLETED
        self.write_build_json(
            "publish_result.json",
            {
                "video_id": "vid_002",
                "playlist_id": "PL_SERIES_001",
                "upload_status": "PRIVATE_REVIEW",
            },
        )
        res = self.run_cli("--record-published")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(json.loads(res.stdout)["completed_episodes"], 2)

        ep3 = {
            **ep1,
            "episode_number_in_series": 3,
            "global_episode_number": 3,
            "bespoke_asset_path": "assets/svg/diagrams/hawking_radiation_evaporation.svg",
            "youtube_title": "How Black Holes Slowly Die (Part 3/3) #Shorts",
            "scenes": make_valid_scenes("hawking_radiation_evaporation"),
        }
        self.write_build_json("episode_plan.json", ep3)
        self.write_build_json(
            "publish_result.json",
            {
                "video_id": "vid_003",
                "playlist_id": "PL_SERIES_001",
                "upload_status": "PRIVATE_REVIEW",
            },
        )
        res = self.run_cli("--record-published")
        self.assertEqual(res.returncode, 0, res.stderr)
        rec3 = json.loads(res.stdout)
        self.assertEqual(rec3["completed_episodes"], 3)
        self.assertEqual(rec3["series_status"], "COMPLETED")

        # 12. Verify --context after completion
        ctx_done = json.loads(self.run_cli("--context").stdout)
        self.assertIsNone(ctx_done["active_series"])
        self.assertEqual(ctx_done["next_episode_number_in_series"], 1)
        self.assertEqual(ctx_done["next_global_episode_number"], 4)
        self.assertEqual(ctx_done["last_completed_pillar"], "Cosmic & Scientific Paradoxes")
        self.assertEqual(len(ctx_done["completed_series_history"]), 1)
        self.assertEqual(len(ctx_done["previous_bespoke_assets"]), 3)

        # 13. Pillar rotation enforcement: same pillar must be rejected
        self.write_build_json(
            "new_series_plan.json",
            {
                **series1_plan,
                "series_title": "Dark Matter Enigmas",
                "pillar": "Cosmic & Scientific Paradoxes",
            },
        )
        res = self.run_cli("--create-series")
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("Pillar rotation violation", res.stderr)

        # 14. Different pillar succeeds for Series #2
        self.write_build_json(
            "new_series_plan.json",
            {
                **series1_plan,
                "series_title": "The Lost Library of Nalanda",
                "pillar": "Hidden History",
                "bgm_track": "epic_history.mp3",
            },
        )
        res = self.run_cli("--create-series")
        self.assertEqual(res.returncode, 0, res.stderr)
        s2 = json.loads(res.stdout)
        self.assertEqual(s2["series_id"], 2)
        self.assertEqual(s2["series_status"], "ACTIVE")

        # 15. Direct SQLite persistence check
        conn = sqlite3.connect(str(self.root / "episodes.db"))
        try:
            series_rows = conn.execute(
                "SELECT series_id, status, completed_episodes, youtube_playlist_id FROM series ORDER BY series_id"
            ).fetchall()
            ep_count = conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
        finally:
            conn.close()

        self.assertEqual(series_rows, [(1, "COMPLETED", 3, "PL_SERIES_001"), (2, "ACTIVE", 0, None)])
        self.assertEqual(ep_count, 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)