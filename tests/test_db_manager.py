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

            # Multi-series support: multiple ACTIVE series are now allowed
            conn.execute(
                """
                INSERT INTO series (
                    series_title, pillar, tts_voice, bgm_track,
                    total_planned_episodes, completed_episodes, series_bible_json, status
                ) VALUES ('Second Active', 'Hidden History', 'am_fenrir', 'epic_history.mp3', 3, 0, '{}', 'ACTIVE')
                """
            )
            active_count = conn.execute("SELECT COUNT(*) FROM series WHERE status = 'ACTIVE'").fetchone()[0]
            self.assertEqual(active_count, 2)

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

        # Cannot create duplicate series with identical title
        self.write_build_json(
            "new_series_plan.json",
            make_valid_series_plan(
                title="Secrets of the Event Horizon",
                pillar="Hidden History",
                bgm_track="epic_history.mp3",
                prefix="s2",
            ),
        )
        res = self.run_cli("--create-series")
        self.assertEqual(res.returncode, 1)
        self.assertIn("already exists", res.stderr)

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

        # Episodic series format pacing enforcement (5..15 scenes)
        ep_plan = make_valid_episode_plan(bespoke_stem="test_asset")
        ep_plan["content_format"] = "episodic_series"
        ep_plan["scenes"] = make_n_scenes(8)
        p_ep = mod.EpisodePlan.model_validate(ep_plan, context={"config": cfg})
        self.assertEqual(len(p_ep.scenes), 8)

        ep_plan["scenes"] = make_n_scenes(16)
        with self.assertRaises(ValueError) as ctx_over:
            mod.EpisodePlan.model_validate(ep_plan, context={"config": cfg})
        self.assertIn("scenes count must be between 5 and 15", str(ctx_over.exception))

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

    def test_16_narrative_templates_and_story_arc_models(self) -> None:
        """Verify narrative arc templates and StoryArc/StoryPhase model validation."""
        mod = load_db_manager_module()
        self.assertIn("eight_phase_complete_arc", mod.NARRATIVE_TEMPLATES)
        self.assertIn("five_phase_compact_arc", mod.NARRATIVE_TEMPLATES)
        self.assertIn("in_medias_res", mod.NARRATIVE_TEMPLATES)

        eight_tmpl = mod.NARRATIVE_TEMPLATES["eight_phase_complete_arc"]
        self.assertEqual(len(eight_tmpl["phases"]), 8)
        self.assertEqual(eight_tmpl["phases"][0]["structure_type"], "hook")
        self.assertEqual(eight_tmpl["phases"][5]["structure_type"], "climax")
        self.assertEqual(eight_tmpl["phases"][6]["structure_type"], "resolution")

        five_tmpl = mod.NARRATIVE_TEMPLATES["five_phase_compact_arc"]
        self.assertEqual(len(five_tmpl["phases"]), 5)

        # Test StoryArc model instantiation
        arc = mod.StoryArc(
            arc_title="Clash of the Planetary Titans",
            premise="Ravana subjects the Navagrahas to serve as stepping stones.",
            central_conflict="Shani refuses moral submission and turns his gaze downward.",
            resolution="Ravana's pride is shattered as the gaze precipitates his doom.",
            narrative_structure="eight_phase_complete_arc",
            climax_scene_index=7,
            resolution_scene_index=8,
            phases=[
                mod.StoryPhase(
                    phase_index=1,
                    phase_name="Hook",
                    structure_type="hook",
                    narrative_goal="Shocking visual of Shani beneath the throne.",
                    scenes=[1],
                ),
                mod.StoryPhase(
                    phase_index=2,
                    phase_name="Climax & Resolution",
                    structure_type="climax",
                    narrative_goal="Downward glance seals fate.",
                    scenes=[7, 8],
                ),
            ],
            thematic_lesson="Even kings cannot escape the gravity of justice.",
        )
        self.assertEqual(arc.climax_scene_index, 7)
        self.assertEqual(arc.resolution_scene_index, 8)
        self.assertEqual(len(arc.phases), 2)

    def test_17_story_completeness_validation(self) -> None:
        """Verify EpisodePlan enforces story completeness across formats."""
        mod = load_db_manager_module()
        cfg = yaml.safe_load((self.root / "config.yaml").read_text(encoding="utf-8"))

        base_plan = make_valid_episode_plan(bespoke_stem="test_asset")
        base_plan["content_format"] = "standalone"
        base_plan["series_id"] = None
        base_plan["series_title"] = None
        base_plan["episode_number_in_series"] = None
        base_plan["total_planned_episodes"] = None

        # 1. Valid complete story arc passes cleanly
        base_plan["story_arc"] = {
            "arc_title": "The Fall of Lanka's Hubris",
            "premise": "Ravana imprisons cosmic forces within his citadel.",
            "central_conflict": "Will cosmic law bend to mortal tyranny?",
            "resolution": "Justice triumphs completely and cosmic harmony returns to the realms.",
            "narrative_structure": "eight_phase_complete_arc",
            "climax_scene_index": 5,
            "resolution_scene_index": 7,
            "phases": [
                {"phase_index": 1, "phase_name": "Hook", "narrative_goal": "Opening mystery.", "scenes": [1, 2]},
                {"phase_index": 2, "phase_name": "Climax", "narrative_goal": "The strike.", "scenes": [5, 6, 7]},
            ],
        }
        plan_obj = mod.EpisodePlan.model_validate(base_plan, context={"config": cfg})
        self.assertIsNotNone(plan_obj.story_arc)

        # 2. Climax after resolution fails validation
        bad_plan = json.loads(json.dumps(base_plan))
        bad_plan["story_arc"]["climax_scene_index"] = 7
        bad_plan["story_arc"]["resolution_scene_index"] = 4
        with self.assertRaises(ValueError) as ctx_order:
            mod.EpisodePlan.model_validate(bad_plan, context={"config": cfg})
        self.assertIn("cannot come after", str(ctx_order.exception))

        # 3. Invalid scene index in phase fails validation
        bad_plan2 = json.loads(json.dumps(base_plan))
        bad_plan2["story_arc"]["phases"][0]["scenes"] = [1, 99]
        with self.assertRaises(ValueError) as ctx_idx:
            mod.EpisodePlan.model_validate(bad_plan2, context={"config": cfg})
        self.assertIn("references invalid scene_index 99", str(ctx_idx.exception))

        # 4. Standalone video with dangling cliffhanger fails validation
        bad_plan3 = json.loads(json.dumps(base_plan))
        bad_plan3["scenes"][-1]["narration_text"] = "Will Lanka survive? To be continued in Part 2 next week."
        with self.assertRaises(ValueError) as ctx_cliff:
            mod.EpisodePlan.model_validate(bad_plan3, context={"config": cfg})
        self.assertIn("Standalone story completeness violation", str(ctx_cliff.exception))
        self.assertIn("to be continued", str(ctx_cliff.exception))

    def test_18_episodic_series_bible_schema(self) -> None:
        """Verify SeriesBibleEpisode and NewSeriesPlan support episodic series format."""
        mod = load_db_manager_module()
        cfg = yaml.safe_load((self.root / "config.yaml").read_text(encoding="utf-8"))

        episodic_bible = {
            "arc_summary": "An anthology of cosmic justice through mythological encounters.",
            "content_format": "episodic_series",
            "continuity_notes": "Each episode features a self-contained clash resolved by cosmic law.",
            "episodes": [
                {
                    "episode_number": 1,
                    "working_title": "Shani and the Stepping Stone",
                    "hook": "Why did the demon king face his stairs downward?",
                    "narrative_direction": "Explore Ravana's hubris and Shani's gaze.",
                    "planned_bespoke_asset": "assets/svg/diagrams/ep1_diagram.svg",
                    "cliffhanger_or_payoff": "Ravana's pride cracks under Shani's unwavering gaze.",
                    "standalone_story_synopsis": "Ravana forces Shani face down, but Shani's glance turns Lanka's fortune.",
                    "central_conflict": "Mortal arrogance attempts to conquer divine justice.",
                    "resolution": "Shani's gaze seals the doom of Lanka, delivering complete poetic justice.",
                    "series_connection": "Sets up the recurring theme of cosmic karma for future episodes.",
                },
                {
                    "episode_number": 2,
                    "working_title": "The Liberation by Maruti",
                    "hook": "Who could survive entering the prison of the planetary god?",
                    "narrative_direction": "Hanuman encounters Shani trapped in Lanka's vaults.",
                    "planned_bespoke_asset": "assets/svg/diagrams/ep2_diagram.svg",
                    "cliffhanger_or_payoff": "Hanuman breaks the chains with selfless devotion.",
                    "standalone_story_synopsis": "Hanuman frees Shani and receives the blessing that protects devotees.",
                    "central_conflict": "Physical chains versus spiritual devotion.",
                    "resolution": "Shani grants the eternal boon of protection to all who honor the wind-god.",
                    "series_connection": "Deepens the lore of the Navagrahas across the epic.",
                },
                {
                    "episode_number": 3,
                    "working_title": "The Test of King Harishchandra",
                    "hook": "Can a king surrender his crown, family, and breath for truth?",
                    "narrative_direction": "The ultimate test of cosmic rectitude.",
                    "planned_bespoke_asset": "assets/svg/diagrams/ep3_diagram.svg",
                    "cliffhanger_or_payoff": "Truth vindicated at the burning ghats.",
                    "standalone_story_synopsis": "Harishchandra endures the supreme trial without breaking his vow of truth.",
                    "central_conflict": "Uncompromising truth versus relentless suffering.",
                    "resolution": "The gods restore his kingdom, crowning truth as supreme eternal law.",
                    "series_connection": "Final celebration of cosmic dharma in the trilogy.",
                },
            ],
        }

        series_plan = {
            "content_format": "episodic_series",
            "series_title": "Chronicles of Cosmic Justice",
            "pillar": "Ancient Epics & Lore",
            "tts_voice": "am_fenrir:0.65+bm_george:0.35",
            "bgm_track": "dramatic_mythology.mp3",
            "total_planned_episodes": 3,
            "series_bible_json": episodic_bible,
        }

        # Validate with NewSeriesPlan
        plan_obj = mod.NewSeriesPlan.model_validate(series_plan, context={"config": cfg})
        self.assertEqual(plan_obj.content_format, "episodic_series")
        self.assertEqual(len(plan_obj.series_bible_json.episodes), 3)
        self.assertEqual(
            plan_obj.series_bible_json.episodes[0].central_conflict,
            "Mortal arrogance attempts to conquer divine justice.",
        )
        self.assertIn("doom of Lanka", plan_obj.series_bible_json.episodes[0].resolution)

    def test_19_context_output_autonomous_planning_guidelines(self) -> None:
        """Verify db_manager.py --context provides rich autonomous storytelling guidelines."""
        self.assertEqual(self.run_cli("--init").returncode, 0)
        res = self.run_cli("--context")
        self.assertEqual(res.returncode, 0, res.stderr)
        out = json.loads(res.stdout)

        guidelines = out["autonomous_planning_guidelines"]
        self.assertIn("narrative_templates", guidelines)
        self.assertIn("eight_phase_complete_arc", guidelines["narrative_templates"])
        self.assertIn("five_phase_compact_arc", guidelines["narrative_templates"])
        self.assertIn("in_medias_res", guidelines["narrative_templates"])

        self.assertIn("story_completeness_rules", guidelines)
        self.assertIn("standalone_mandate", guidelines["story_completeness_rules"])
        self.assertIn("pacing_rules", guidelines)

    def test_20_acceptance_standalone_eight_phase_complete_story(self) -> None:
        """Verify acceptance criterion: complete 8-phase standalone story resolves central conflict."""
        mod = load_db_manager_module()
        self.assertEqual(self.run_cli("--init").returncode, 0)
        cfg = yaml.safe_load((self.root / "config.yaml").read_text(encoding="utf-8"))

        bespoke_stem = "shani_staircase_diagram"
        (self.root / f"assets/svg/diagrams/{bespoke_stem}.svg").write_text("<svg/>", encoding="utf-8")

        # Construct 8 scenes corresponding to the 8 phases
        scenes = []
        phase_names = [
            ("Hook / Opening Mystery", "hook", "shock", "curtain_establishing"),
            ("Premise & Backstory", "premise", "calm", "slow_push"),
            ("Rising Action / First Move", "rising_action", "calm", "pan_left"),
            ("Complication / Escalation", "escalation", "smirk", "slow_pull"),
            ("Direct Confrontation", "confrontation", "wrath", "dramatic_zoom"),
            ("Dramatic Climax", "climax", "shock", "dramatic_zoom"),
            ("Conflict Resolution", "resolution", "calm", "slow_pull"),
            ("Concluding Thought / Lesson", "concluding_thought", "meditating", "slow_push"),
        ]

        for i, (p_name, s_type, emo, cam) in enumerate(phase_names, start=1):
            if i == 1:
                v_mode = "explainer_diagram"
                diag_rig = bespoke_stem
                p_char = None
                diag_stage = 1
            else:
                v_mode = "character_drama"
                diag_rig = None
                p_char = "sutradhar_narrator"
                diag_stage = None

            scenes.append(
                {
                    "scene_index": i,
                    "narration_text": f"Scene {i} narration establishing dramatic mythological stakes and moral reckoning.",
                    "visual_mode": v_mode,
                    "backdrop_rig": "deep_cosmos_nebula",
                    "diagram_rig": diag_rig,
                    "active_diagram_stage": diag_stage,
                    "primary_character": p_char,
                    "secondary_character": None,
                    "callout_headline": None,
                    "callout_subtext": None,
                    "emotion": emo,
                    "action_gesture": "idle_breathe",
                    "mood_palette": "obsidian_amber",
                    "particle_theme": "golden_embers",
                    "camera_motion": cam,
                    "transition_sfx": "sub_hit.wav",
                }
            )

        standalone_plan = {
            "content_format": "standalone",
            "series_id": None,
            "series_title": None,
            "episode_number_in_series": None,
            "total_planned_episodes": None,
            "global_episode_number": 1,
            "pillar": "Ancient Epics & Lore",
            "tts_voice": "am_fenrir:0.65+bm_george:0.35",
            "bgm_track": "dramatic_mythology.mp3",
            "bespoke_asset_path": f"assets/svg/diagrams/{bespoke_stem}.svg",
            "youtube_title": "Why Ravana Made Shani His Staircase #Mythology",
            "youtube_description": "The complete untold story of Ravana's hubris and Shani's fatal glance. #Shorts",
            "summary": "Ravana subjugates the Navagrahas, but Shani's downward glance brings Lanka's ultimate downfall.",
            "target_duration_sec": 120.0,
            "target_duration_range": {"min_seconds": 100.0, "max_seconds": 140.0},
            "narrative_structure": "eight_phase_complete_arc",
            "story_arc": {
                "arc_title": "The Humbling of Ravana",
                "premise": "Ravana imprisons the planetary deities to serve as stepping stones for his throne.",
                "central_conflict": "Ravana demands that Shani submit; Shani refuses spiritual subjugation.",
                "resolution": "Shani casts his dread glance downward upon Lanka's foundations, sealing the golden city's doom.",
                "narrative_structure": "eight_phase_complete_arc",
                "climax_scene_index": 6,
                "resolution_scene_index": 7,
                "phases": [
                    {"phase_index": idx, "phase_name": p[0], "structure_type": p[1], "narrative_goal": f"Execute phase {idx} goal.", "scenes": [idx]}
                    for idx, p in enumerate(phase_names, start=1)
                ],
                "thematic_lesson": "No monarch's crown can overturn the eternal law of karma.",
            },
            "scenes": scenes,
        }

        # 1. Validate EpisodePlan
        plan_obj = mod.EpisodePlan.model_validate(standalone_plan, context={"config": cfg})
        self.assertEqual(plan_obj.content_format, "standalone")
        self.assertEqual(len(plan_obj.scenes), 8)
        self.assertEqual(plan_obj.story_arc.climax_scene_index, 6)
        self.assertEqual(plan_obj.story_arc.resolution_scene_index, 7)

        # 2. Record published standalone episode into SQLite
        self.write_build_json("episode_plan.json", standalone_plan)
        pub_result = {
            "video_id": "shani_katha_ep1_vid",
            "playlist_id": None,
            "upload_status": "PUBLISHED",
            "privacy_status": "public",
        }
        self.write_build_json("publish_result.json", pub_result)

        res = self.run_cli("--record-published")
        self.assertEqual(res.returncode, 0, res.stderr)
        out = json.loads(res.stdout)
        self.assertEqual(out["content_format"], "standalone")
        self.assertEqual(out["youtube_video_id"], "shani_katha_ep1_vid")
        self.assertEqual(out["episode_status"], "PUBLISHED")

    def test_21_open_ended_multi_series_concurrent_rotation(self) -> None:
        """Verify Phase 6: multiple open-ended series can be active concurrently and rotated seamlessly."""
        mod = load_db_manager_module()
        self.assertEqual(self.run_cli("--init").returncode, 0)
        cfg = yaml.safe_load((self.root / "config.yaml").read_text(encoding="utf-8"))

        # Create Series 1: Shani Katha (open-ended recurring universe)
        s1_plan = {
            "content_format": "episodic_series",
            "series_title": "Shani Katha",
            "pillar": "Ancient Epics & Lore",
            "tts_voice": "am_fenrir:0.65+bm_george:0.35",
            "bgm_track": "dramatic_mythology.mp3",
            "total_planned_episodes": None,  # Open-ended
            "series_bible_json": {
                "arc_summary": "Stories of cosmic karma and karmic justice through Lord Shani.",
                "content_format": "episodic_series",
                "episodes": [
                    {
                        "episode_number": 1,
                        "working_title": "Ravana and the Staircase of Planets",
                        "hook": "Why did the demon king position the planets downward?",
                        "narrative_direction": "Explore Ravana's ego vs Shani's cosmic role.",
                        "planned_bespoke_asset": "assets/svg/diagrams/s1_ep1.svg",
                        "satisfying_takeaway": "No tyrant can escape the cosmic law of karma.",
                    }
                ],
            },
        }
        self.write_build_json("new_series_plan.json", s1_plan)
        res1 = self.run_cli("--create-series")
        self.assertEqual(res1.returncode, 0, res1.stderr)
        out1 = json.loads(res1.stdout)
        self.assertEqual(out1["series_id"], 1)
        self.assertEqual(out1["series_status"], "ACTIVE")

        # Create Series 2: Ancient Indian Engineering (concurrent active series!)
        s2_plan = {
            "content_format": "episodic_series",
            "series_title": "Ancient Indian Engineering",
            "pillar": "Hidden History",
            "tts_voice": "am_fenrir:0.65+bm_george:0.35",
            "bgm_track": "epic_history.mp3",
            "total_planned_episodes": None,  # Open-ended
            "series_bible_json": {
                "arc_summary": "Forgotten architectural and metallurgical marvels of ancient India.",
                "content_format": "episodic_series",
                "episodes": [
                    {
                        "episode_number": 1,
                        "working_title": "The Rustless Iron Pillar of Delhi",
                        "hook": "How has ancient wrought iron resisted corrosion for 1600 years?",
                        "narrative_direction": "Examine high phosphorus metallurgy and misawite coating.",
                        "planned_bespoke_asset": "assets/svg/diagrams/s2_ep1.svg",
                        "satisfying_takeaway": "Ancient metallurgy mastered protective film chemistry centuries before modern science.",
                    }
                ],
            },
        }
        self.write_build_json("new_series_plan.json", s2_plan)
        res2 = self.run_cli("--create-series")
        self.assertEqual(res2.returncode, 0, res2.stderr)
        out2 = json.loads(res2.stdout)
        self.assertEqual(out2["series_id"], 2)
        self.assertEqual(out2["series_status"], "ACTIVE")

        # Verify context lists both series as ACTIVE
        ctx_res = self.run_cli("--context")
        self.assertEqual(ctx_res.returncode, 0)
        ctx = json.loads(ctx_res.stdout)
        active_ids = [s["series_id"] for s in ctx["active_series_list"]]
        self.assertEqual(active_ids, [1, 2])

        # Record Episode 1 in Series 1
        (self.root / "assets/svg/diagrams/s1_ep1.svg").write_text("<svg/>", encoding="utf-8")
        ep1_s1 = make_valid_episode_plan(
            series_id=1, ep_in_series=1, global_ep=1, bespoke_stem="s1_ep1",
            title="When Ravana Made Shani His Staircase | Shani Katha"
        )
        ep1_s1["content_format"] = "episodic_series"
        ep1_s1["total_planned_episodes"] = None
        ep1_s1["series_title"] = "Shani Katha"
        ep1_s1["pillar"] = "Ancient Epics & Lore"
        ep1_s1["bgm_track"] = "dramatic_mythology.mp3"
        self.write_build_json("episode_plan.json", ep1_s1)
        self.write_build_json("publish_result.json", {"video_id": "vid_s1_e1", "playlist_id": "PL_SHANI", "upload_status": "PUBLISHED"})
        rec_res1 = self.run_cli("--record-published")
        self.assertEqual(rec_res1.returncode, 0, rec_res1.stderr)

        # Record Episode 1 in Series 2 (Rotation to second series!)
        (self.root / "assets/svg/diagrams/s2_ep1.svg").write_text("<svg/>", encoding="utf-8")
        ep1_s2 = make_valid_episode_plan(
            series_id=2, ep_in_series=1, global_ep=2, bespoke_stem="s2_ep1",
            title="The Rustless Iron Pillar of Delhi | Ancient Indian Engineering"
        )
        ep1_s2["content_format"] = "episodic_series"
        ep1_s2["total_planned_episodes"] = None
        ep1_s2["series_title"] = "Ancient Indian Engineering"
        ep1_s2["pillar"] = "Hidden History"
        ep1_s2["bgm_track"] = "epic_history.mp3"
        self.write_build_json("episode_plan.json", ep1_s2)
        self.write_build_json("publish_result.json", {"video_id": "vid_s2_e1", "playlist_id": "PL_ENG", "upload_status": "PUBLISHED"})
        rec_res2 = self.run_cli("--record-published")
        self.assertEqual(rec_res2.returncode, 0, rec_res2.stderr)

        # Record Episode 2 in Series 1 (Rotation BACK to first series!)
        (self.root / "assets/svg/diagrams/s1_ep2.svg").write_text("<svg/>", encoding="utf-8")
        ep2_s1 = make_valid_episode_plan(
            series_id=1, ep_in_series=2, global_ep=3, bespoke_stem="s1_ep2",
            title="Shani's Gaze Upon Mount Kailash | Shani Katha"
        )
        ep2_s1["content_format"] = "episodic_series"
        ep2_s1["total_planned_episodes"] = None
        ep2_s1["series_title"] = "Shani Katha"
        ep2_s1["pillar"] = "Ancient Epics & Lore"
        ep2_s1["bgm_track"] = "dramatic_mythology.mp3"
        self.write_build_json("episode_plan.json", ep2_s1)
        self.write_build_json("publish_result.json", {"video_id": "vid_s1_e2", "playlist_id": "PL_SHANI", "upload_status": "PUBLISHED"})
        rec_res3 = self.run_cli("--record-published")
        self.assertEqual(rec_res3.returncode, 0, rec_res3.stderr)

        # Verify Series 1 and Series 2 both remain ACTIVE with accurate counts
        conn = mod.connect_db(self.root / "episodes.db")
        try:
            s1_row = conn.execute("SELECT completed_episodes, status FROM series WHERE series_id = 1").fetchone()
            s2_row = conn.execute("SELECT completed_episodes, status FROM series WHERE series_id = 2").fetchone()
            self.assertEqual(s1_row["completed_episodes"], 2)
            self.assertEqual(s1_row["status"], "ACTIVE")
            self.assertEqual(s2_row["completed_episodes"], 1)
            self.assertEqual(s2_row["status"], "ACTIVE")
        finally:
            conn.close()

    def test_22_story_research_provenance_validation(self) -> None:
        """Verify StoryResearch model and database serialization of source provenance."""
        mod = load_db_manager_module()
        self.assertEqual(self.run_cli("--init").returncode, 0)
        cfg = yaml.safe_load((self.root / "config.yaml").read_text(encoding="utf-8"))

        research_data = {
            "source_tradition": "Skanda Purana, Kashi Khanda, Chapter 32",
            "canonical_story_summary": "Ravana subjugates the Navagrahas, placing them face-down as footstools. Narada tricks Ravana into letting Shani turn face-up, whereupon Shani's drishti dooms Lanka.",
            "key_verified_facts": [
                "Ravana imprisoned all nine Grahas during Meghanada's birth",
                "Shani's gaze was inverted to nullify malefic influence",
                "Narada provoked Ravana's pride to reverse Shani's position",
            ],
            "cross_checked_variants": "Valmiki Ramayana Yuddha Kanda mentions Ravana's mastery over planets; Skanda Purana details the specific interaction with Shani.",
            "source_references": [
                "Skanda Purana (Motilal Banarsidass English Translation, Vol. 4)",
                "Kashi Khanda Purvabhaga 32.1-45",
            ],
        }

        # 1. Valid StoryResearch
        res_obj = mod.StoryResearch.model_validate(research_data)
        self.assertEqual(res_obj.source_tradition, "Skanda Purana, Kashi Khanda, Chapter 32")
        self.assertEqual(len(res_obj.key_verified_facts), 3)

        # 2. Missing mandatory fields rejected
        bad_research = dict(research_data)
        bad_research.pop("source_tradition")
        with self.assertRaises(mod.ValidationError):
            mod.StoryResearch.model_validate(bad_research)

        # 3. Attach to EpisodePlan and record into DB
        bespoke_stem = "research_test_diagram"
        (self.root / f"assets/svg/diagrams/{bespoke_stem}.svg").write_text("<svg/>", encoding="utf-8")
        plan = make_valid_episode_plan(bespoke_stem=bespoke_stem)
        plan["content_format"] = "standalone"
        plan["series_id"] = None
        plan["series_title"] = None
        plan["episode_number_in_series"] = None
        plan["total_planned_episodes"] = None
        plan["global_episode_number"] = 1
        plan["bespoke_asset_path"] = f"assets/svg/diagrams/{bespoke_stem}.svg"
        plan["youtube_title"] = "When Shani's Gaze Sealed Lanka's Doom #Mythology"
        plan["story_research"] = research_data

        self.write_build_json("episode_plan.json", plan)
        self.write_build_json("publish_result.json", {"video_id": "vid_res_1", "playlist_id": None, "upload_status": "PUBLISHED"})
        res = self.run_cli("--record-published")
        self.assertEqual(res.returncode, 0, res.stderr)

        # 4. Read back from SQLite
        conn = mod.connect_db(self.root / "episodes.db")
        try:
            row = conn.execute("SELECT research_sources_json FROM episodes WHERE episode_id = 1").fetchone()
            self.assertIsNotNone(row["research_sources_json"])
            saved_research = json.loads(row["research_sources_json"])
            self.assertEqual(saved_research["source_tradition"], "Skanda Purana, Kashi Khanda, Chapter 32")
            self.assertEqual(len(saved_research["key_verified_facts"]), 3)
        finally:
            conn.close()

    def test_23_universal_anti_cliffhanger_rejection_across_formats(self) -> None:
        """Verify that BOTH standalone and episodic_series formats strictly reject cliffhanger endings."""
        mod = load_db_manager_module()
        cfg = yaml.safe_load((self.root / "config.yaml").read_text(encoding="utf-8"))

        for fmt in ("standalone", "episodic_series"):
            plan = make_valid_episode_plan(bespoke_stem="cliff_test")
            plan["content_format"] = fmt
            if fmt == "standalone":
                plan["series_id"] = None
                plan["series_title"] = None
                plan["episode_number_in_series"] = None
                plan["total_planned_episodes"] = None
            else:
                plan["series_id"] = 1
                plan["series_title"] = "Test Series"
                plan["episode_number_in_series"] = 1
                plan["total_planned_episodes"] = 3

            # Cliffhanger in last scene text
            plan["scenes"][-1]["narration_text"] = "Will the cosmic order hold? Find out in part 2 next time."
            with self.assertRaises(ValueError) as ctx:
                mod.EpisodePlan.model_validate(plan, context={"config": cfg})
            self.assertIn("story completeness violation", str(ctx.exception).lower())
            self.assertIn("part 2", str(ctx.exception).lower())

    def test_24_satisfying_takeaway_and_topic_history_in_context(self) -> None:
        """Verify SeriesBibleEpisode supports satisfying_takeaway and cmd_context returns topic history."""
        mod = load_db_manager_module()
        self.assertEqual(self.run_cli("--init").returncode, 0)

        # 1. SeriesBibleEpisode with satisfying_takeaway syncs automatically
        ep_bible = mod.SeriesBibleEpisode.model_validate({
            "episode_number": 1,
            "working_title": "The Cosmic Scale",
            "hook": "Can a feather outweigh the burden of royal hubris?",
            "narrative_direction": "Explore philosophical balance in ancient lore.",
            "planned_bespoke_asset": "assets/svg/diagrams/scale_diagram.svg",
            "satisfying_takeaway": "Justice restores harmony, proving righteousness outweighs worldly dominion.",
        })
        self.assertEqual(ep_bible.cliffhanger_or_payoff, ep_bible.satisfying_takeaway)

        # 2. Add an episode and verify cmd_context includes previously_covered_topics
        (self.root / "assets/svg/diagrams/scale_diagram.svg").write_text("<svg/>", encoding="utf-8")
        plan = make_valid_episode_plan(bespoke_stem="scale_diagram")
        plan["content_format"] = "standalone"
        plan["series_id"] = None
        plan["series_title"] = None
        plan["episode_number_in_series"] = None
        plan["total_planned_episodes"] = None
        plan["global_episode_number"] = 1
        plan["bespoke_asset_path"] = "assets/svg/diagrams/scale_diagram.svg"
        plan["youtube_title"] = "The Feather and the Iron Throne | Cosmic Lore"
        plan["summary"] = "A sage tests the weight of an emperor's soul against the feather of truth."

        self.write_build_json("episode_plan.json", plan)
        self.write_build_json("publish_result.json", {"video_id": "vid_scale_1", "playlist_id": None, "upload_status": "PUBLISHED"})
        res = self.run_cli("--record-published")
        self.assertEqual(res.returncode, 0)

        ctx_res = self.run_cli("--context")
        self.assertEqual(ctx_res.returncode, 0)
        ctx = json.loads(ctx_res.stdout)
        self.assertIn("previously_covered_topics", ctx)
        self.assertEqual(len(ctx["previously_covered_topics"]), 1)
        self.assertEqual(ctx["previously_covered_topics"][0]["youtube_title"], "The Feather and the Iron Throne | Cosmic Lore")


if __name__ == "__main__":
    unittest.main(verbosity=2)