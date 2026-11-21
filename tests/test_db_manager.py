#!/usr/bin/env python3
"""Comprehensive specification-compliance test suite for scripts/db_manager.py."""

from __future__ import annotations

import importlib.util
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

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_MANAGER = REPO_ROOT / "scripts" / "db_manager.py"
REAL_CONFIG = REPO_ROOT / "config.yaml"


def load_db_manager_module() -> Any:
    spec = importlib.util.spec_from_file_location("db_manager_mod", DB_MANAGER)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_valid_bible(count: int = 3, prefix: str = "s1") -> dict[str, Any]:
    return {
        "arc_summary": "A multi-part scientific journey across gravitational horizons and deep time.",
        "continuity_notes": "Maintain escalating visual tension from outer orbit to singularity.",
        "episodes": [
            {
                "episode_number": i,
                "working_title": f"Event Horizon Paradox Part {i}",
                "hook": f"What breaks first when crossing boundary stage {i}?",
                "narrative_direction": (
                    f"Break down relativistic phenomenon {i} using escalating visual stakes."
                ),
                "planned_bespoke_asset": f"assets/svg/diagrams/{prefix}_ep{i}_diagram.svg",
                "cliffhanger_or_payoff": (
                    f"Plant the cliffhanger leading directly into part {i + 1}."
                    if i < count
                    else "Deliver the final evaporation payoff and subscribe invitation."
                ),
            }
            for i in range(1, count + 1)
        ],
    }


def make_valid_series_plan(
    title: str = "Secrets of the Event Horizon",
    pillar: str = "Cosmic & Scientific Paradoxes",
    bgm_track: str = "cosmic_mystery.mp3",
    count: int = 3,
    prefix: str = "s1",
) -> dict[str, Any]:
    return {
        "series_title": title,
        "pillar": pillar,
        "tts_voice": "am_fenrir:0.65+bm_george:0.35",
        "bgm_track": bgm_track,
        "total_planned_episodes": count,
        "series_bible_json": make_valid_bible(count=count, prefix=prefix),
    }


def make_valid_scenes(bespoke_stem: str, count: int = 7) -> list[dict[str, Any]]:
    scenes: list[dict[str, Any]] = []
    for idx in range(1, count + 1):
        if idx == 1:
            text = (
                "Cross this invisible cosmic boundary and the universe outside "
                "ages millions of years in a single heartbeat."
            )
            scenes.append(
                {
                    "scene_index": idx,
                    "narration_text": text,
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
            text = (
                "Gravity pulls harder on your feet than your head until "
                "every atom stretches into a blazing cosmic thread."
            )
            scenes.append(
                {
                    "scene_index": idx,
                    "narration_text": text,
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
            text = (
                "Inside that trapped region of space every path forward points "
                "straight toward the singularity at the center."
            )
            scenes.append(
                {
                    "scene_index": idx,
                    "narration_text": text,
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
                    "transition_sfx": "tension_swell.wav",
                }
            )
    return scenes


def make_valid_episode_plan(
    series_id: int = 1,
    ep_in_series: int = 1,
    global_ep: int = 1,
    total_eps: int = 3,
    bespoke_stem: str = "s1_ep1_diagram",
    title: str = "Time Stops at the Event Horizon (Part 1/3) #Shorts",
) -> dict[str, Any]:
    return {
        "series_id": series_id,
        "series_title": "Secrets of the Event Horizon",
        "pillar": "Cosmic & Scientific Paradoxes",
        "episode_number_in_series": ep_in_series,
        "total_planned_episodes": total_eps,
        "global_episode_number": global_ep,
        "tts_voice": "am_fenrir:0.65+bm_george:0.35",
        "bgm_track": "cosmic_mystery.mp3",
        "bespoke_asset_path": f"assets/svg/diagrams/{bespoke_stem}.svg",
        "youtube_title": title,
        "youtube_description": "Part of the Event Horizon series on Sutradhar. #Space #Shorts",
        "summary": "Explores extreme gravitational time dilation near an event horizon.",
        "scenes": make_valid_scenes(bespoke_stem),
    }


class TestDbManagerCompliance(unittest.TestCase):
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

        (self.root / "assets/svg/characters/sutradhar_narrator.svg").write_text("<svg/>", encoding="utf-8")
        (self.root / "assets/svg/backdrops/deep_cosmos_nebula.svg").write_text("<svg/>", encoding="utf-8")
        (self.root / "assets/svg/diagrams/black_hole_anatomy.svg").write_text("<svg/>", encoding="utf-8")
        (self.root / "assets/bgm/cosmic_mystery.mp3").write_bytes(b"")
        (self.root / "assets/sfx/sub_hit.wav").write_bytes(b"")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "SUTRADHAR_ROOT": str(self.root)}
        return subprocess.run(
            [sys.executable, str(DB_MANAGER), *args],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

    def write_build_json(self, filename: str, payload: Any) -> None:
        (self.root / "build" / filename).write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )

    def update_config(self, mutator: Any) -> None:
        cfg_path = self.root / "config.yaml"
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        mutator(cfg)
        cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

    def init_and_create_default_series(self) -> None:
        self.assertEqual(self.run_cli("--init").returncode, 0)
        self.write_build_json("new_series_plan.json", make_valid_series_plan())
        res = self.run_cli("--create-series")
        self.assertEqual(res.returncode, 0, res.stderr)

    # 1. CLI commands, malformed input, and stdout/stderr separation
    def test_01_cli_error_cases_and_stdout_stderr_separation(self) -> None:
        # Missing flag & mutually exclusive flags -> stderr only, stdout empty
        for bad_args in ((), ("--init", "--context"), ("--unknown",)):
            res = self.run_cli(*bad_args)
            self.assertNotEqual(res.returncode, 0)
            self.assertEqual(res.stdout.strip(), "")
            self.assertTrue(len(res.stderr.strip()) > 0)

        # Commands before --init fail cleanly to stderr
        for flag in ("--context", "--create-series", "--record-published"):
            res = self.run_cli(flag)
            self.assertEqual(res.returncode, 1)
            self.assertEqual(res.stdout.strip(), "")
            self.assertIn("--init", res.stderr)

        # --init succeeds with valid JSON on stdout and empty stderr
        res = self.run_cli("--init")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stderr.strip(), "")
        self.assertEqual(json.loads(res.stdout)["status"], "ok")

        # Missing input JSON files fail cleanly
        res = self.run_cli("--create-series")
        self.assertEqual(res.returncode, 1)
        self.assertEqual(res.stdout.strip(), "")
        self.assertIn("new_series_plan.json", res.stderr)

        # Malformed JSON file fails cleanly
        (self.root / "build/new_series_plan.json").write_text("{broken json", encoding="utf-8")
        res = self.run_cli("--create-series")
        self.assertEqual(res.returncode, 1)
        self.assertIn("Malformed JSON", res.stderr)

    # 2. Invalid config.yaml handling
    def test_02_invalid_config_handling(self) -> None:
        self.assertEqual(self.run_cli("--init").returncode, 0)

        # Unsupported language lock violation
        self.update_config(lambda c: c["channel"].__setitem__("primary_language", "es"))
        res = self.run_cli("--context")
        self.assertEqual(res.returncode, 1)
        self.assertIn("language lock violated", res.stderr)

        # Restore and test invalid upload_mode
        shutil.copy2(REAL_CONFIG, self.root / "config.yaml")
        self.update_config(lambda c: c["publishing"].__setitem__("upload_mode", "public_yolo"))
        res = self.run_cli("--context")
        self.assertEqual(res.returncode, 1)
        self.assertIn("upload_mode", res.stderr)

        # Restore and test non-boolean allow_public_or_scheduled
        shutil.copy2(REAL_CONFIG, self.root / "config.yaml")
        self.update_config(lambda c: c["publishing"].__setitem__("allow_public_or_scheduled", "false"))
        res = self.run_cli("--context")
        self.assertEqual(res.returncode, 1)
        self.assertIn("must be a boolean", res.stderr)

        # Missing config.yaml
        (self.root / "config.yaml").unlink()
        res = self.run_cli("--context")
        self.assertEqual(res.returncode, 1)
        self.assertIn("Missing configuration file", res.stderr)

    # 3. Complete vs incomplete Series Bible validation
    def test_03_series_bible_completeness_validation(self) -> None:
        self.assertEqual(self.run_cli("--init").returncode, 0)

        invalid_bibles = [
            {},  # Empty dict
            {"notes": "Only free text, no episodes"},  # Missing arc_summary & episodes
            {"arc_summary": "Valid summary long enough for check.", "episodes": [{}, {}, {}]},  # Incomplete ep dicts
            {
                "arc_summary": "Valid summary long enough for check.",
                "episodes": make_valid_bible(count=2)["episodes"],  # Wrong length (2 vs 3)
            },
            {
                # Non-sequential episode numbers [1, 3, 2]
                "arc_summary": "Valid summary long enough for check.",
                "episodes": [
                    {**ep, "episode_number": num}
                    for ep, num in zip(make_valid_bible(count=3)["episodes"], [1, 3, 2])
                ],
            },
            {
                # Missing required hook field
                "arc_summary": "Valid summary long enough for check.",
                "episodes": [
                    {k: v for k, v in ep.items() if k != "hook"}
                    for ep in make_valid_bible(count=3)["episodes"]
                ],
            },
            {
                # Duplicate planned_bespoke_asset across episodes
                "arc_summary": "Valid summary long enough for check.",
                "episodes": [
                    {**ep, "planned_bespoke_asset": "assets/svg/diagrams/same_asset.svg"}
                    for ep in make_valid_bible(count=3)["episodes"]
                ],
            },
            {
                # Invalid asset path (nested subdirectory)
                "arc_summary": "Valid summary long enough for check.",
                "episodes": [
                    {**ep, "planned_bespoke_asset": f"assets/svg/diagrams/nested/ep{i}.svg"}
                    for i, ep in enumerate(make_valid_bible(count=3)["episodes"], start=1)
                ],
            },
        ]

        for idx, bad_bible in enumerate(invalid_bibles):
            plan = make_valid_series_plan()
            plan["series_bible_json"] = bad_bible
            self.write_build_json("new_series_plan.json", plan)
            res = self.run_cli("--create-series")
            self.assertEqual(res.returncode, 1, f"Case {idx} should have failed: {bad_bible}")
            self.assertIn("validation failed", res.stderr)

        # Valid bible passed as JSON string must succeed
        str_plan = make_valid_series_plan()
        str_plan["series_bible_json"] = json.dumps(make_valid_bible(count=3))
        self.write_build_json("new_series_plan.json", str_plan)
        res = self.run_cli("--create-series")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(json.loads(res.stdout)["series_id"], 1)

    # 4. Narration single source & clean canvas schema enforcement
    def test_04_narration_and_caption_consistency(self) -> None:
        self.init_and_create_default_series()

        ep = make_valid_episode_plan()
        # Passing forbidden legacy caption_text must fail validation
        ep["scenes"][0]["caption_text"] = "Forbidden redundant caption."
        self.write_build_json("episode_plan.json", ep)
        self.write_build_json(
            "publish_result.json",
            {"video_id": "vid_cap_01", "playlist_id": "PL_CAP", "upload_status": "PRIVATE_REVIEW"},
        )
        res = self.run_cli("--record-published")
        self.assertEqual(res.returncode, 1)
        self.assertIn("Extra inputs are not permitted", res.stderr)

        # Ensure DB remained untouched (0 completed episodes)
        ctx = json.loads(self.run_cli("--context").stdout)
        self.assertEqual(ctx["active_series"]["completed_episodes"], 0)

        # Removing caption_text and setting pause_after_ms & emphasis_word succeeds
        del ep["scenes"][0]["caption_text"]
        ep["scenes"][0]["pause_after_ms"] = 250
        ep["scenes"][0]["emphasis_word"] = "boundary"
        self.write_build_json("episode_plan.json", ep)
        res = self.run_cli("--record-published")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(json.loads(res.stdout)["completed_episodes"], 1)

    # 5. Publishing safety & private_review lock enforcement
    def test_05_publishing_safety_private_review_lock(self) -> None:
        self.init_and_create_default_series()
        ep = make_valid_episode_plan()
        self.write_build_json("episode_plan.json", ep)

        # Under locked config (upload_mode=private_review, allow_public_or_scheduled=false):
        self.update_config(lambda c: c["publishing"].update({"upload_mode": "private_review", "allow_public_or_scheduled": False}))
        forbidden_payloads = [
            # Attempt 1: PUBLISHED status
            {
                "video_id": "vid_pub_01",
                "playlist_id": "PL_LOCK",
                "upload_status": "PUBLISHED",
                "scheduled_publish_at": None,
            },
            # Attempt 2: PRIVATE_REVIEW carrying a scheduled_publish_at timestamp
            {
                "video_id": "vid_pub_02",
                "playlist_id": "PL_LOCK",
                "upload_status": "PRIVATE_REVIEW",
                "scheduled_publish_at": "2026-11-25T13:00:00Z",
            },
            # Attempt 3: Manually spoofed upload_mode="scheduled"
            {
                "video_id": "vid_pub_03",
                "playlist_id": "PL_LOCK",
                "upload_status": "PRIVATE_REVIEW",
                "upload_mode": "scheduled",
            },
            # Attempt 4: Manually spoofed privacy_status="public"
            {
                "video_id": "vid_pub_04",
                "playlist_id": "PL_LOCK",
                "upload_status": "PRIVATE_REVIEW",
                "privacy_status": "public",
            },
            # Attempt 5: Unknown extra key trying to sneak publishAt
            {
                "video_id": "vid_pub_05",
                "playlist_id": "PL_LOCK",
                "upload_status": "PRIVATE_REVIEW",
                "publishAt": "2026-11-25T13:00:00Z",
            },
            # Attempt 6: FAILED carrying a scheduled timestamp while locked
            {
                "video_id": None,
                "playlist_id": "PL_LOCK",
                "upload_status": "FAILED",
                "scheduled_publish_at": "2026-11-25T13:00:00Z",
            },
        ]

        for idx, payload in enumerate(forbidden_payloads):
            self.write_build_json("publish_result.json", payload)
            res = self.run_cli("--record-published")
            self.assertEqual(res.returncode, 1, f"Payload #{idx} bypassed safety lock: {payload}")
            self.assertIn("publish_result.json validation failed", res.stderr)

        # Verify zero partial DB mutations occurred across all 6 rejected attempts
        ctx = json.loads(self.run_cli("--context").stdout)
        self.assertEqual(ctx["active_series"]["completed_episodes"], 0)
        self.assertIsNone(ctx["active_series"]["youtube_playlist_id"])

        # Even if upload_mode is flipped to 'scheduled', allow_public_or_scheduled=false MUST still block PUBLISHED
        self.update_config(lambda c: c["publishing"].__setitem__("upload_mode", "scheduled"))
        self.write_build_json(
            "publish_result.json",
            {
                "video_id": "vid_pub_06",
                "playlist_id": "PL_LOCK",
                "upload_status": "PUBLISHED",
                "scheduled_publish_at": "2026-11-25T13:00:00Z",
            },
        )
        res = self.run_cli("--record-published")
        self.assertEqual(res.returncode, 1)
        self.assertIn("Publishing safety lock active", res.stderr)

        # Restore private_review config -> valid PRIVATE_REVIEW succeeds
        shutil.copy2(REAL_CONFIG, self.root / "config.yaml")
        self.write_build_json(
            "publish_result.json",
            {
                "video_id": "vid_priv_01",
                "playlist_id": "PL_LOCK",
                "upload_status": "PRIVATE_REVIEW",
                "upload_mode": "private_review",
                "privacy_status": "private",
                "scheduled_publish_at": None,
            },
        )
        res = self.run_cli("--record-published")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(json.loads(res.stdout)["episode_status"], "PRIVATE_REVIEW")

        # When BOTH upload_mode='scheduled' AND allow_public_or_scheduled=True -> PUBLISHED with ISO-8601 succeeds
        self.update_config(
            lambda c: c["publishing"].update(
                {"upload_mode": "scheduled", "allow_public_or_scheduled": True}
            )
        )
        ep2 = make_valid_episode_plan(ep_in_series=2, global_ep=2, bespoke_stem="s1_ep2_diagram")
        self.write_build_json("episode_plan.json", ep2)
        self.write_build_json(
            "publish_result.json",
            {
                "video_id": "vid_sched_02",
                "playlist_id": "PL_LOCK",
                "upload_status": "PUBLISHED",
                "upload_mode": "scheduled",
                "privacy_status": "private",
                "scheduled_publish_at": "2026-11-25T13:00:00Z",
            },
        )
        res = self.run_cli("--record-published")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(json.loads(res.stdout)["episode_status"], "PUBLISHED")

    # 6. Failed upload recording & gapless retry
    def test_06_failed_upload_and_gapless_retry(self) -> None:
        self.init_and_create_default_series()
        ep1 = make_valid_episode_plan()
        self.write_build_json("episode_plan.json", ep1)

        # Record FAILED (even with whitespace video_id, normalized cleanly to NULL)
        self.write_build_json(
            "publish_result.json",
            {
                "video_id": "   ",
                "playlist_id": "PL_RETRY",
                "upload_status": "FAILED",
                "error_message": "Simulated 503 upload failure",
            },
        )
        res = self.run_cli("--record-published")
        self.assertEqual(res.returncode, 0, res.stderr)
        out = json.loads(res.stdout)
        self.assertEqual(out["episode_status"], "FAILED")
        self.assertIsNone(out["youtube_video_id"])
        self.assertEqual(out["completed_episodes"], 0)
        self.assertEqual(out["series_status"], "ACTIVE")

        # Context must still point to Part 1 / Global 1
        ctx = json.loads(self.run_cli("--context").stdout)
        self.assertEqual(ctx["next_episode_number_in_series"], 1)
        self.assertEqual(ctx["next_global_episode_number"], 1)
        self.assertEqual(ctx["active_series"]["youtube_playlist_id"], "PL_RETRY")

        # Retry Part 1 as PRIVATE_REVIEW replaces FAILED row atomically
        self.write_build_json(
            "publish_result.json",
            {
                "video_id": "vid_retry_ok",
                "playlist_id": "PL_RETRY",
                "upload_status": "PRIVATE_REVIEW",
            },
        )
        res = self.run_cli("--record-published")
        self.assertEqual(res.returncode, 0, res.stderr)
        out2 = json.loads(res.stdout)
        self.assertEqual(out2["completed_episodes"], 1)
        self.assertEqual(out2["global_episode_number"], 1)

        conn = sqlite3.connect(str(self.root / "episodes.db"))
        try:
            rows = conn.execute("SELECT status, youtube_video_id FROM episodes").fetchall()
        finally:
            conn.close()
        self.assertEqual(rows, [("PRIVATE_REVIEW", "vid_retry_ok")])

    # 7. Granular field, voice, BGM/SFX, rig, visual-mode, title & ISO timestamp validators
    def test_07_field_and_visual_mode_validators(self) -> None:
        self.assertEqual(self.run_cli("--init").returncode, 0)

        # Invalid Kokoro blend weights (sum = 0.50)
        bad_voice = make_valid_series_plan()
        bad_voice["tts_voice"] = "am_fenrir:0.25+bm_george:0.25"
        self.write_build_json("new_series_plan.json", bad_voice)
        self.assertEqual(self.run_cli("--create-series").returncode, 1)

        # Unconfigured BGM track
        bad_bgm = make_valid_series_plan(bgm_track="unlisted_track.mp3")
        self.write_build_json("new_series_plan.json", bad_bgm)
        res = self.run_cli("--create-series")
        self.assertEqual(res.returncode, 1)
        self.assertIn("not in configured BGM tracks", res.stderr)

        # Create valid series to test episode validators
        self.write_build_json("new_series_plan.json", make_valid_series_plan())
        self.assertEqual(self.run_cli("--create-series").returncode, 0)
        self.write_build_json(
            "publish_result.json",
            {"video_id": "vid_val", "playlist_id": "PL_VAL", "upload_status": "PRIVATE_REVIEW"},
        )

        def assert_ep_rejected(mutator: Any, expected_msg: str) -> None:
            ep = make_valid_episode_plan()
            mutator(ep)
            self.write_build_json("episode_plan.json", ep)
            r = self.run_cli("--record-published")
            self.assertEqual(r.returncode, 1, f"Expected failure containing '{expected_msg}'")
            self.assertIn(expected_msg, r.stderr)

        # Unconfigured SFX
        assert_ep_rejected(lambda e: e["scenes"][0].__setitem__("transition_sfx", "laser.wav"), "sfx_tracks")
        # Scene count too low (4)
        assert_ep_rejected(lambda e: e.__setitem__("scenes", e["scenes"][:4]), "scenes count")
        # Non-sequential scene_index
        assert_ep_rejected(lambda e: e["scenes"][2].__setitem__("scene_index", 9), "strictly sequential")
        # character_drama missing primary_character
        assert_ep_rejected(lambda e: e["scenes"][1].__setitem__("primary_character", None), "primary_character")
        # character_drama duplicate secondary_character
        assert_ep_rejected(
            lambda e: e["scenes"][1].__setitem__("secondary_character", "sutradhar_narrator"),
            "cannot duplicate primary_character",
        )
        # character_drama stray active_diagram_stage
        assert_ep_rejected(lambda e: e["scenes"][1].__setitem__("active_diagram_stage", 2), "must be null")
        # explainer_diagram missing active_diagram_stage
        assert_ep_rejected(lambda e: e["scenes"][0].__setitem__("active_diagram_stage", None), "active_diagram_stage")
        # kinetic_callout missing callout_headline
        assert_ep_rejected(lambda e: e["scenes"][2].__setitem__("callout_headline", None), "callout_headline")
        # YouTube title > 100 chars
        assert_ep_rejected(lambda e: e.__setitem__("youtube_title", "A" * 101), "100")
        # YouTube title with forbidden angle bracket
        assert_ep_rejected(lambda e: e.__setitem__("youtube_title", "Black <Hole> Mystery #Shorts"), "'<' or '>'")
        # Rig naming convention violation (.svg suffix in slug)
        assert_ep_rejected(lambda e: e["scenes"][0].__setitem__("backdrop_rig", "bad_rig.svg"), "lowercase slug")
        # Bespoke asset category mismatch (diagram path used only as backdrop_rig)
        def set_category_mismatch(e: dict[str, Any]) -> None:
            e["bespoke_asset_path"] = "assets/svg/backdrops/s1_ep1_diagram.svg"
        assert_ep_rejected(set_category_mismatch, "backdrop_rig")

        # Naive ISO-8601 timestamp (no timezone) rejected even when unlocked
        self.update_config(
            lambda c: c["publishing"].update({"upload_mode": "scheduled", "allow_public_or_scheduled": True})
        )
        self.write_build_json("episode_plan.json", make_valid_episode_plan())
        self.write_build_json(
            "publish_result.json",
            {
                "video_id": "vid_ts",
                "playlist_id": "PL_VAL",
                "upload_status": "PUBLISHED",
                "scheduled_publish_at": "2026-11-25T13:00:00",
            },
        )
        res = self.run_cli("--record-published")
        self.assertEqual(res.returncode, 1)
        self.assertIn("explicit timezone", res.stderr)

    # 8. Transaction rollback on validation & SQLite IntegrityError
    def test_08_transaction_rollback_on_validation_and_db_errors(self) -> None:
        self.init_and_create_default_series()

        # Record Part 1 with playlist_id=None so series.youtube_playlist_id stays NULL
        ep1 = make_valid_episode_plan(ep_in_series=1, global_ep=1, bespoke_stem="s1_ep1_diagram")
        self.write_build_json("episode_plan.json", ep1)
        self.write_build_json(
            "publish_result.json",
            {"video_id": "vid_unique_001", "playlist_id": None, "upload_status": "PRIVATE_REVIEW"},
        )
        self.assertEqual(self.run_cli("--record-published").returncode, 0)

        # Part 2 attempts duplicate youtube_video_id WHILE also passing a new playlist_id.
        # SQLite IntegrityError on INSERT must roll back the prior UPDATE series.youtube_playlist_id!
        ep2 = make_valid_episode_plan(ep_in_series=2, global_ep=2, bespoke_stem="s1_ep2_diagram")
        self.write_build_json("episode_plan.json", ep2)
        self.write_build_json(
            "publish_result.json",
            {
                "video_id": "vid_unique_001",
                "playlist_id": "PL_MUST_ROLLBACK",
                "upload_status": "PRIVATE_REVIEW",
            },
        )
        res = self.run_cli("--record-published")
        self.assertEqual(res.returncode, 1)
        self.assertIn("SQLite integrity error", res.stderr)

        ctx = json.loads(self.run_cli("--context").stdout)
        self.assertEqual(ctx["active_series"]["completed_episodes"], 1)
        self.assertIsNone(ctx["active_series"]["youtube_playlist_id"])

        # Now set valid playlist on Part 2, then verify playlist mismatch on Part 3 rolls back cleanly
        self.write_build_json(
            "publish_result.json",
            {"video_id": "vid_unique_002", "playlist_id": "PL_REAL", "upload_status": "PRIVATE_REVIEW"},
        )
        self.assertEqual(self.run_cli("--record-published").returncode, 0)

        ep3 = make_valid_episode_plan(ep_in_series=3, global_ep=3, bespoke_stem="s1_ep3_diagram")
        self.write_build_json("episode_plan.json", ep3)
        self.write_build_json(
            "publish_result.json",
            {"video_id": "vid_unique_003", "playlist_id": "PL_WRONG", "upload_status": "PRIVATE_REVIEW"},
        )
        res = self.run_cli("--record-published")
        self.assertEqual(res.returncode, 1)
        self.assertIn("Playlist mismatch", res.stderr)

        ctx2 = json.loads(self.run_cli("--context").stdout)
        self.assertEqual(ctx2["active_series"]["completed_episodes"], 2)
        self.assertEqual(ctx2["active_series"]["youtube_playlist_id"], "PL_REAL")

    # 9. Duplicate episode, bespoke asset reuse & continuity checks
    def test_09_duplicate_episode_and_bespoke_asset_protection(self) -> None:
        self.init_and_create_default_series()

        ep1 = make_valid_episode_plan(ep_in_series=1, global_ep=1, bespoke_stem="s1_ep1_diagram")
        self.write_build_json("episode_plan.json", ep1)
        self.write_build_json(
            "publish_result.json",
            {"video_id": "vid_d1", "playlist_id": "PL_D", "upload_status": "PRIVATE_REVIEW"},
        )
        self.assertEqual(self.run_cli("--record-published").returncode, 0)

        # Re-recording Episode 1 slot must be rejected
        self.write_build_json(
            "publish_result.json",
            {"video_id": "vid_d1_dup", "playlist_id": "PL_D", "upload_status": "PRIVATE_REVIEW"},
        )
        res = self.run_cli("--record-published")
        self.assertEqual(res.returncode, 1)
        self.assertIn("Expected episode_number_in_series=2", res.stderr)

        # Reusing Part 1's bespoke_asset_path on Part 2 must be rejected
        ep2_dup_asset = make_valid_episode_plan(ep_in_series=2, global_ep=2, bespoke_stem="s1_ep1_diagram")
        self.write_build_json("episode_plan.json", ep2_dup_asset)
        self.write_build_json(
            "publish_result.json",
            {"video_id": "vid_d2", "playlist_id": "PL_D", "upload_status": "PRIVATE_REVIEW"},
        )
        res = self.run_cli("--record-published")
        self.assertEqual(res.returncode, 1)
        self.assertIn("was already used", res.stderr)

        # Continuity mismatch on tts_voice must be rejected
        ep2_bad_voice = make_valid_episode_plan(ep_in_series=2, global_ep=2, bespoke_stem="s1_ep2_diagram")
        ep2_bad_voice["tts_voice"] = "am_michael"
        self.write_build_json("episode_plan.json", ep2_bad_voice)
        res = self.run_cli("--record-published")
        self.assertEqual(res.returncode, 1)
        self.assertIn("does not match ACTIVE series tts_voice", res.stderr)

    # 10. Direct SQLite constraints, foreign keys & partial unique indexes
    def test_10_database_constraints_and_foreign_keys(self) -> None:
        self.init_and_create_default_series()
        mod = load_db_manager_module()
        conn = mod.connect_db(self.root / "episodes.db")
        try:
            fk_enabled = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
            self.assertEqual(fk_enabled, 1)

            # Foreign key violation: episode referencing non-existent series_id=999
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO episodes (
                        series_id, episode_number_in_series, global_episode_number,
                        youtube_title, summary, bespoke_asset_path, script_json,
                        youtube_video_id, scheduled_publish_at, status
                    ) VALUES (999, 1, 1, 'T', 'S', 'assets/svg/diagrams/x.svg', '{}', 'v999', NULL, 'PRIVATE_REVIEW')
                    """
                )

            # Single ACTIVE series partial unique index enforcement
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO series (
                        series_title, pillar, tts_voice, bgm_track,
                        total_planned_episodes, completed_episodes, series_bible_json, status
                    ) VALUES ('Rogue Active', 'Hidden History', 'am_fenrir', 'epic_history.mp3', 3, 0, '{}', 'ACTIVE')
                    """
                )

            # Insert valid episode for series 1, then test ON DELETE RESTRICT & unique non-failed slot
            conn.execute(
                """
                INSERT INTO episodes (
                    series_id, episode_number_in_series, global_episode_number,
                    youtube_title, summary, bespoke_asset_path, script_json,
                    youtube_video_id, scheduled_publish_at, status
                ) VALUES (1, 1, 1, 'T1', 'S1', 'assets/svg/diagrams/a.svg', '{}', 'v1', NULL, 'PRIVATE_REVIEW')
                """
            )

            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("DELETE FROM series WHERE series_id = 1")

            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO episodes (
                        series_id, episode_number_in_series, global_episode_number,
                        youtube_title, summary, bespoke_asset_path, script_json,
                        youtube_video_id, scheduled_publish_at, status
                    ) VALUES (1, 1, 2, 'T1 Dup', 'S1', 'assets/svg/diagrams/b.svg', '{}', 'v2', NULL, 'PRIVATE_REVIEW')
                    """
                )
        finally:
            conn.close()

    # 11. End-to-end series completion, pillar rotation & Series #2 creation
    def test_11_full_series_lifecycle_completion_and_pillar_rotation(self) -> None:
        self.init_and_create_default_series()

        # Cannot create another series while Series #1 is ACTIVE
        self.write_build_json(
            "new_series_plan.json",
            make_valid_series_plan(
                title="Competing Series",
                pillar="Hidden History",
                bgm_track="epic_history.mp3",
                prefix="s2",
            ),
        )
        res = self.run_cli("--create-series")
        self.assertEqual(res.returncode, 1)
        self.assertIn("still ACTIVE", res.stderr)

        # Complete all 3 episodes under PRIVATE_REVIEW
        for part in (1, 2, 3):
            ep = make_valid_episode_plan(
                series_id=1,
                ep_in_series=part,
                global_ep=part,
                total_eps=3,
                bespoke_stem=f"s1_ep{part}_diagram",
                title=f"Event Horizon Secret (Part {part}/3) #Shorts",
            )
            self.write_build_json("episode_plan.json", ep)
            self.write_build_json(
                "publish_result.json",
                {
                    "video_id": f"vid_s1_p{part}",
                    "playlist_id": "PL_S1",
                    "upload_status": "PRIVATE_REVIEW",
                },
            )
            res = self.run_cli("--record-published")
            self.assertEqual(res.returncode, 0, res.stderr)
            out = json.loads(res.stdout)
            self.assertEqual(out["completed_episodes"], part)
            self.assertEqual(out["series_status"], "COMPLETED" if part == 3 else "ACTIVE")

        # Verify --context after completion
        ctx = json.loads(self.run_cli("--context").stdout)
        self.assertIsNone(ctx["active_series"])
        self.assertEqual(ctx["next_episode_number_in_series"], 1)
        self.assertEqual(ctx["next_global_episode_number"], 4)
        self.assertEqual(ctx["last_completed_pillar"], "Cosmic & Scientific Paradoxes")
        self.assertEqual(ctx["channel_config"]["completed_private_review_episodes"], 3)
        self.assertEqual(len(ctx["completed_series_history"]), 1)
        self.assertEqual(len(ctx["previous_bespoke_assets"]), 3)

        # Pillar rotation violation: repeating Cosmic & Scientific Paradoxes must fail
        self.write_build_json(
            "new_series_plan.json",
            make_valid_series_plan(
                title="Dark Matter Enigmas",
                pillar="Cosmic & Scientific Paradoxes",
                bgm_track="cosmic_mystery.mp3",
                prefix="s2a",
            ),
        )
        res = self.run_cli("--create-series")
        self.assertEqual(res.returncode, 1)
        self.assertIn("Pillar rotation violation", res.stderr)

        # Reusing a bespoke asset from Series #1 inside Series #2's bible must fail
        s2_reuse = make_valid_series_plan(
            title="The Lost Library of Nalanda",
            pillar="Hidden History",
            bgm_track="epic_history.mp3",
            prefix="s1",  # Collides with s1_ep1_diagram.svg
        )
        self.write_build_json("new_series_plan.json", s2_reuse)
        res = self.run_cli("--create-series")
        self.assertEqual(res.returncode, 1)
        self.assertIn("already used", res.stderr)

        # Valid Series #2 on rotated pillar with fresh bespoke assets succeeds
        s2_valid = make_valid_series_plan(
            title="The Lost Library of Nalanda",
            pillar="Hidden History",
            bgm_track="epic_history.mp3",
            prefix="s2",
        )
        self.write_build_json("new_series_plan.json", s2_valid)
        res = self.run_cli("--create-series")
        self.assertEqual(res.returncode, 0, res.stderr)
        s2_out = json.loads(res.stdout)
        self.assertEqual(s2_out["series_id"], 2)
        self.assertEqual(s2_out["series_status"], "ACTIVE")

    def test_12_standalone_episode_plan_validation(self) -> None:
        """Verify EpisodePlan model allows standalone format without series fields."""
        mod = load_db_manager_module()
        cfg = mod.load_config(self.root)
        plan_data = make_valid_episode_plan()
        plan_data["content_format"] = "standalone"
        plan_data["series_id"] = None
        plan_data["series_title"] = None
        plan_data["episode_number_in_series"] = None
        plan_data["total_planned_episodes"] = None
        plan_data["target_duration_sec"] = 150.0
        plan_data["target_duration_range"] = {"min_seconds": 120.0, "max_seconds": 180.0}

        plan = mod.EpisodePlan.model_validate(plan_data, context={"config": cfg})
        self.assertEqual(plan.content_format, "standalone")
        self.assertIsNone(plan.series_id)
        self.assertIsNone(plan.series_title)
        self.assertEqual(plan.target_duration_sec, 150.0)

        # serial format must require series_id
        plan_data["content_format"] = "serial"
        with self.assertRaises(ValueError) as ctx:
            mod.EpisodePlan.model_validate(plan_data, context={"config": cfg})
        self.assertIn("series_id is required", str(ctx.exception))

    def test_13_story_arc_pydantic_validation(self) -> None:
        """Verify StoryPhase and StoryArc structured storytelling models."""
        mod = load_db_manager_module()

        phase = mod.StoryPhase(
            phase_index=1,
            phase_name="hook",
            narrative_goal="Intriguing question drawing audience into cosmic mystery.",
            target_duration_sec=15.0,
        )
        self.assertEqual(phase.phase_name, "hook")
        self.assertEqual(phase.target_duration_sec, 15.0)

        arc = mod.StoryArc(
            arc_title="Mythological Confrontation",
            premise="Ravana ascends to conquer the planetary spheres in celestial arrogance.",
            central_conflict="Shani resists submission as cosmic arbiter of deeds.",
            resolution="Shani casts his downward glance, crushing Ravana's pride beneath cosmic destiny.",
            phases=[
                mod.StoryPhase(phase_index=1, phase_name="hook", narrative_goal="Initial cosmic dilemma.", target_duration_sec=15.0),
                mod.StoryPhase(phase_index=2, phase_name="premise", narrative_goal="Golden court context.", target_duration_sec=18.0),
                mod.StoryPhase(phase_index=3, phase_name="rising_action", narrative_goal="Escalation of planetary chains.", target_duration_sec=22.0),
                mod.StoryPhase(phase_index=4, phase_name="escalation", narrative_goal="Direct defiance of fate.", target_duration_sec=22.0),
                mod.StoryPhase(phase_index=5, phase_name="confrontation", narrative_goal="Clash of titans.", target_duration_sec=25.0),
                mod.StoryPhase(phase_index=6, phase_name="climax", narrative_goal="Downward glance released.", target_duration_sec=18.0),
                mod.StoryPhase(phase_index=7, phase_name="resolution", narrative_goal="Shattered illusions.", target_duration_sec=15.0),
                mod.StoryPhase(phase_index=8, phase_name="concluding_thought", narrative_goal="Philosophical wrap.", target_duration_sec=15.0),
            ],
            thematic_lesson="Pride inevitably bends before universal law.",
        )
        self.assertEqual(len(arc.phases), 8)
        self.assertEqual(arc.arc_title, "Mythological Confrontation")

    def test_14_flexible_scene_count_validation(self) -> None:
        """Verify 5 to 15 scenes are allowed; <5 and >15 are rejected."""
        mod = load_db_manager_module()
        cfg = mod.load_config(self.root)

        def make_n_scenes(n: int) -> list[dict[str, Any]]:
            base_scenes = make_valid_scenes("test_asset")
            if n <= len(base_scenes):
                res = base_scenes[:n]
            else:
                res = list(base_scenes)
                while len(res) < n:
                    idx = len(res) + 1
                    res.append({
                        "scene_index": idx,
                        "narration_text": f"Extra scene narration text number {idx} describing epic story beats in detail.",
                        "visual_mode": "kinetic_callout",
                        "backdrop_rig": "quantum_grid_void",
                        "diagram_rig": None,
                        "active_diagram_stage": None,
                        "primary_character": None,
                        "secondary_character": None,
                        "callout_headline": f"STAGE {idx}",
                        "callout_subtext": "Chronological progression",
                        "emotion": "calm",
                        "action_gesture": "idle_breathe",
                        "mood_palette": "obsidian_amber",
                        "particle_theme": "starfield_warp",
                        "camera_motion": "slow_pull",
                        "transition_sfx": "tension_swell.wav",
                    })
            for i, sc in enumerate(res):
                sc["scene_index"] = i + 1
            return res

        base_plan = make_valid_episode_plan(bespoke_stem="test_asset")
        base_plan["content_format"] = "episodic_series"

        # 5 scenes -> valid for episodic_series
        base_plan["scenes"] = make_n_scenes(5)
        p5 = mod.EpisodePlan.model_validate(base_plan, context={"config": cfg})
        self.assertEqual(len(p5.scenes), 5)

        # 10 scenes -> valid for episodic_series
        base_plan["scenes"] = make_n_scenes(10)
        p10 = mod.EpisodePlan.model_validate(base_plan, context={"config": cfg})
        self.assertEqual(len(p10.scenes), 10)

        # 15 scenes -> valid for episodic_series
        base_plan["scenes"] = make_n_scenes(15)
        p15 = mod.EpisodePlan.model_validate(base_plan, context={"config": cfg})
        self.assertEqual(len(p15.scenes), 15)

        # 4 scenes -> invalid (< 5)
        base_plan["scenes"] = make_n_scenes(4)
        with self.assertRaises(ValueError) as ctx4:
            mod.EpisodePlan.model_validate(base_plan, context={"config": cfg})
        self.assertIn("scenes count must be between 5 and 15 (got 4)", str(ctx4.exception))

        # 16 scenes -> invalid (> 15)
        base_plan["scenes"] = make_n_scenes(16)
        with self.assertRaises(ValueError) as ctx16:
            mod.EpisodePlan.model_validate(base_plan, context={"config": cfg})
        self.assertIn("scenes count must be between 5 and 15 (got 16)", str(ctx16.exception))

        # Serial format pacing enforcement (5..8 scenes)
        serial_plan = make_valid_episode_plan(bespoke_stem="test_asset")
        serial_plan["content_format"] = "serial"
        serial_plan["scenes"] = make_n_scenes(8)
        p_serial = mod.EpisodePlan.model_validate(serial_plan, context={"config": cfg})
        self.assertEqual(len(p_serial.scenes), 8)

        serial_plan["scenes"] = make_n_scenes(9)
        with self.assertRaises(ValueError) as ctx_serial:
            mod.EpisodePlan.model_validate(serial_plan, context={"config": cfg})
        self.assertIn("scenes count must be between 5 and 8 (got 9)", str(ctx_serial.exception))

    def test_15_standalone_publishing_db_recording(self) -> None:
        """Verify cmd_record_published records standalone episodes without requiring active series."""
        mod = load_db_manager_module()
        self.assertEqual(self.run_cli("--init").returncode, 0)

        # Write standalone episode plan
        bespoke_stem = "standalone_diagram"
        plan = make_valid_episode_plan(bespoke_stem=bespoke_stem)
        plan["content_format"] = "standalone"
        plan["series_id"] = None
        plan["series_title"] = None
        plan["episode_number_in_series"] = None
        plan["total_planned_episodes"] = None
        plan["global_episode_number"] = 1
        plan["bespoke_asset_path"] = f"assets/svg/diagrams/{bespoke_stem}.svg"
        plan["youtube_title"] = "Standalone Epic Tale of Cosmic Balance #Mythology"
        self.write_build_json("episode_plan.json", plan)

        # Write publish result
        pub_result = {
            "video_id": "standalone_vid_999",
            "playlist_id": None,
            "upload_status": "PRIVATE_REVIEW",
        }
        self.write_build_json("publish_result.json", pub_result)

        res = self.run_cli("--record-published")
        self.assertEqual(res.returncode, 0, res.stderr)
        out = json.loads(res.stdout)
        self.assertEqual(out["content_format"], "standalone")
        self.assertIsNone(out["series_id"])
        self.assertEqual(out["youtube_video_id"], "standalone_vid_999")

        # Verify DB contents
        conn = mod.connect_db(self.root / "episodes.db")
        row = conn.execute("SELECT * FROM episodes WHERE youtube_video_id = 'standalone_vid_999'").fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertIsNone(row["series_id"])
        self.assertEqual(row["content_format"], "standalone")
        self.assertEqual(row["status"], "PRIVATE_REVIEW")


if __name__ == "__main__":
    unittest.main(verbosity=2)