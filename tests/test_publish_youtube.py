#!/usr/bin/env python3
"""Comprehensive Unit and Contract Tests for scripts/publish_youtube.py.

Verifies:
1. Zero CLI arguments contract.
2. Safety configuration locks (upload_mode in public, private_review, scheduled).
3. Missing input guards (final_short.mp4, episode_plan.json).
4. Offline / stub publishing behavior producing valid PublishResult (public and private_review).
5. Mocked Google API interaction (videos.insert, playlists, AI synthetic media disclosure).
6. Custom thumbnail generation and upload verification.
7. End-to-end integration piping publish_result.json into db_manager.py --record-published.
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

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import db_manager
import publish_youtube


def _make_test_jpeg_bytes(size: tuple[int, int] = (1080, 1920), variant: str = "hero") -> bytes:
    """Create a valid high-variance JPEG test image in memory."""
    import io
    from PIL import Image, ImageDraw

    im = Image.new("RGB", size, (18, 26, 62) if variant == "hero" else (210, 225, 190))
    draw = ImageDraw.Draw(im)
    w, h = size
    if variant == "hero":
        draw.rectangle([80, 260, w - 80, 620], fill=(246, 196, 83))
        draw.ellipse([w // 2 - 220, 820, w // 2 + 220, 1260], fill=(255, 244, 210))
        draw.rectangle([0, h - 420, w, h], fill=(95, 48, 28))
    else:
        draw.rectangle([0, 0, w, h // 2], fill=(40, 110, 115))
        draw.ellipse([120, 400, w - 120, 1500], fill=(25, 20, 35))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


class TestPublishYouTube(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="sutradhar_pub_test_"))
        self.build_dir = self.tmp_dir / "build"
        self.build_dir.mkdir(parents=True, exist_ok=True)

        # Copy real valid config
        shutil.copy2(REPO_ROOT / "config.yaml", self.tmp_dir / "config.yaml")
        self.cfg = db_manager.load_config(self.tmp_dir)

        # Baseline minimal episode_plan.json
        self.sample_plan = {
            "series_id": 1,
            "series_title": "Secrets of the Cosmos",
            "pillar": "Cosmic & Scientific Paradoxes",
            "episode_number_in_series": 1,
            "total_planned_episodes": 3,
            "global_episode_number": 1,
            "tts_voice": "bm_daniel",
            "bgm_track": "cosmic_mystery.mp3",
            "bespoke_asset_path": "assets/svg/diagrams/black_hole_anatomy.svg",
            "youtube_title": "What Lies Beyond The Horizon? (Part 1/3) #Shorts",
            "youtube_description": "Part 1 of 3: Deep cosmic journey. #Shorts",
            "summary": "Exploring event horizons.",
            "scenes": [
                {
                    "scene_index": i,
                    "narration_text": f"What happens when you cross event horizon stage {i}?",
                    "visual_mode": "character_drama" if i % 2 == 1 else "explainer_diagram",
                    "backdrop_rig": "deep_cosmos_nebula",
                    "diagram_rig": None if i % 2 == 1 else "black_hole_anatomy",
                    "active_diagram_stage": None if i % 2 == 1 else 1,
                    "primary_character": "sutradhar_narrator" if i % 2 == 1 else None,
                    "secondary_character": None,
                    "callout_headline": None,
                    "callout_subtext": None,
                    "emotion": "shock",
                    "action_gesture": "idle_breathe",
                    "mood_palette": "cosmic_indigo",
                    "particle_theme": "starfield_warp",
                    "camera_motion": "dramatic_zoom",
                    "transition_sfx": "sub_hit.wav",
                }
                for i in range(1, 8)
            ],
        }
        (self.build_dir / "episode_plan.json").write_text(json.dumps(self.sample_plan), encoding="utf-8")

        # Fake final_short.mp4
        (self.build_dir / "final_short.mp4").write_bytes(b"\x00\x00\x00\x20ftypisom" + b"\x00" * 1024)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_01_cli_zero_arguments(self) -> None:
        """CLI must reject dynamic arguments per Antigravity contract."""
        with patch("sys.argv", ["publish_youtube.py", "--force"]):
            ret = publish_youtube.main()
            self.assertEqual(ret, 1)

    def test_02_safety_guards(self) -> None:
        """Pipeline must enforce mode validity and allow_public_or_scheduled requirements."""
        import yaml

        # Mode without permission
        bad_cfg = dict(self.cfg)
        bad_cfg["publishing"] = {"upload_mode": "public", "allow_public_or_scheduled": False}
        (self.tmp_dir / "config.yaml").write_text(yaml.safe_dump(bad_cfg), encoding="utf-8")
        with self.assertRaises(publish_youtube.PublishPipelineError) as ctx:
            publish_youtube.run_publish_pipeline(self.tmp_dir)
        self.assertIn("Safety Violation", str(ctx.exception))

        bad_cfg_sched = dict(self.cfg)
        bad_cfg_sched["publishing"] = {"upload_mode": "scheduled", "allow_public_or_scheduled": False}
        (self.tmp_dir / "config.yaml").write_text(yaml.safe_dump(bad_cfg_sched), encoding="utf-8")
        with self.assertRaises(publish_youtube.PublishPipelineError) as ctx:
            publish_youtube.run_publish_pipeline(self.tmp_dir)
        self.assertIn("Safety Violation", str(ctx.exception))

        # Invalid upload_mode string
        bad_cfg2 = dict(self.cfg)
        bad_cfg2["publishing"] = {"upload_mode": "unsupported_mode", "allow_public_or_scheduled": True}
        (self.tmp_dir / "config.yaml").write_text(yaml.safe_dump(bad_cfg2), encoding="utf-8")
        with self.assertRaises((publish_youtube.PublishPipelineError, db_manager.StateError)) as ctx2:
            publish_youtube.run_publish_pipeline(self.tmp_dir)
        self.assertIn("upload_mode", str(ctx2.exception))

    def test_03_missing_inputs(self) -> None:
        """Must fail clearly if final_short.mp4 or episode_plan.json is absent."""
        (self.build_dir / "final_short.mp4").unlink()
        with self.assertRaises(publish_youtube.PublishPipelineError) as ctx:
            publish_youtube.run_publish_pipeline(self.tmp_dir)
        self.assertIn("Missing master video file", str(ctx.exception))

    def test_04_offline_stub_mode_public_and_private(self) -> None:
        """Must produce valid PublishResult without making external requests when offline."""
        import yaml

        # 1. Test Public Mode
        pub_cfg = dict(self.cfg)
        pub_cfg["publishing"] = {"upload_mode": "public", "allow_public_or_scheduled": True}
        (self.tmp_dir / "config.yaml").write_text(yaml.safe_dump(pub_cfg), encoding="utf-8")

        with patch.dict(os.environ, {"SUTRADHAR_OFFLINE_STUB": "1"}, clear=False):
            res = publish_youtube.run_publish_pipeline(self.tmp_dir)

            self.assertEqual(res["upload_status"], "PUBLISHED")
            self.assertEqual(res["upload_mode"], "public")
            self.assertEqual(res["privacy_status"], "public")
            self.assertIsNotNone(res["video_id"])
            self.assertIsNotNone(res["video_url"])
            self.assertIsNone(res["error_message"])

            # Verify file was written
            out_file = self.build_dir / "publish_result.json"
            self.assertTrue(out_file.is_file())

            # Validate against Pydantic model
            pub_model = db_manager.PublishResult.model_validate(res, context={"config": pub_cfg})
            self.assertEqual(pub_model.upload_status, "PUBLISHED")

        # 2. Test Private Review Mode
        priv_cfg = dict(self.cfg)
        priv_cfg["publishing"] = {"upload_mode": "private_review", "allow_public_or_scheduled": False}
        (self.tmp_dir / "config.yaml").write_text(yaml.safe_dump(priv_cfg), encoding="utf-8")

        with patch.dict(os.environ, {"SUTRADHAR_OFFLINE_STUB": "1"}, clear=False):
            res_priv = publish_youtube.run_publish_pipeline(self.tmp_dir)
            self.assertEqual(res_priv["upload_status"], "PRIVATE_REVIEW")
            self.assertEqual(res_priv["privacy_status"], "private")

    def test_05_mocked_live_public_upload(self) -> None:
        """Mock google-api-python-client to test full live flow in public mode with custom thumbnail."""
        import yaml
        pub_cfg = dict(self.cfg)
        pub_cfg["publishing"] = {"upload_mode": "public", "allow_public_or_scheduled": True}
        (self.tmp_dir / "config.yaml").write_text(yaml.safe_dump(pub_cfg), encoding="utf-8")

        mock_youtube = MagicMock()
        mock_videos = MagicMock()
        mock_insert = MagicMock()
        mock_insert.execute.return_value = {"id": "mock_yt_vid_public"}
        mock_insert.next_chunk.return_value = (None, {"id": "mock_yt_vid_public"})
        mock_videos.insert.return_value = mock_insert

        # Mock videos.list for processing wait + read-back verification
        mock_vid_list = MagicMock()
        mock_vid_list.execute.return_value = {
            "items": [
                {
                    "id": "mock_yt_vid_public",
                    "snippet": {
                        "title": self.sample_plan["youtube_title"][:100],
                        "description": self.sample_plan["youtube_description"][:5000],
                        "categoryId": "27",
                        "defaultLanguage": self.cfg["channel"]["primary_language"],
                        "defaultAudioLanguage": self.cfg["channel"]["primary_language"],
                        "thumbnails": {
                            "default": {"url": "https://i.ytimg.com/vi/mock_yt_vid_public/default.jpg"},
                            "maxres": {"url": "https://i.ytimg.com/vi/mock_yt_vid_public/maxresdefault.jpg"},
                            "shortsAspectRatio": {
                                "url": "https://i.ytimg.com/vi/mock_yt_vid_public/sardefault.jpg",
                                "width": 1080,
                                "height": 1920,
                            },
                        },
                    },
                    "status": {
                        "uploadStatus": "processed",
                        "privacyStatus": "public",
                        "selfDeclaredMadeForKids": False,
                        "containsSyntheticMedia": True,
                        "publishAt": None,
                    },
                    "processingDetails": {
                        "processingStatus": "succeeded",
                        "thumbnailsAvailability": "available",
                    },
                    "contentDetails": {
                        "hasCustomThumbnail": True,
                    },
                }
            ]
        }
        mock_videos.list.return_value = mock_vid_list
        mock_youtube.videos.return_value = mock_videos

        # Mock thumbnails.set
        mock_thumbnails = MagicMock()
        mock_thumb_set = MagicMock()
        mock_thumb_set.execute.return_value = {
            "items": [
                {
                    "default": {"url": "https://i.ytimg.com/vi/mock_yt_vid_public/default.jpg"},
                    "maxres": {"url": "https://i.ytimg.com/vi/mock_yt_vid_public/maxresdefault.jpg"},
                    "shortsAspectRatio": {
                        "url": "https://i.ytimg.com/vi/mock_yt_vid_public/sardefault.jpg",
                        "width": 1080,
                        "height": 1920,
                    },
                }
            ]
        }
        mock_thumbnails.set.return_value = mock_thumb_set
        mock_youtube.thumbnails.return_value = mock_thumbnails

        # Mock playlists
        mock_playlists = MagicMock()
        mock_pl_list = MagicMock()
        mock_pl_list.execute.return_value = {"items": []}
        mock_playlists.list.return_value = mock_pl_list

        mock_pl_insert = MagicMock()
        mock_pl_insert.execute.return_value = {"id": "mock_pl_888"}
        mock_playlists.insert.return_value = mock_pl_insert
        mock_youtube.playlists.return_value = mock_playlists

        # Mock playlistItems
        mock_pl_items = MagicMock()
        mock_pl_item_insert = MagicMock()
        mock_pl_item_insert.execute.return_value = {"id": "mock_pl_item_777"}
        mock_pl_items.insert.return_value = mock_pl_item_insert

        mock_pl_item_list = MagicMock()
        mock_pl_item_list.execute.return_value = {
            "items": [
                {"snippet": {"resourceId": {"videoId": "mock_yt_vid_public"}}}
            ]
        }
        mock_pl_items.list.return_value = mock_pl_item_list
        mock_youtube.playlistItems.return_value = mock_pl_items

        # Create real 1080x1920 JPEG thumbnail.jpg
        thumb_bytes = _make_test_jpeg_bytes((1080, 1920), "hero")
        (self.build_dir / "thumbnail.jpg").write_bytes(thumb_bytes)

        with patch.dict(
            os.environ,
            {
                "SUTRADHAR_OFFLINE_STUB": "0",
                "YOUTUBE_CLIENT_ID": "mock_client_id",
                "YOUTUBE_CLIENT_SECRET": "mock_secret",
                "YOUTUBE_REFRESH_TOKEN": "mock_refresh",
            },
        ):
            with patch("google.oauth2.credentials.Credentials") as mock_creds_cls, \
                 patch("googleapiclient.discovery.build", return_value=mock_youtube) as mock_build, \
                 patch("googleapiclient.http.MediaFileUpload"), \
                 patch("thumbnail_utils.fetch_cdn_image", return_value=(200, thumb_bytes)), \
                 patch("time.sleep"):

                res = publish_youtube.run_publish_pipeline(self.tmp_dir)

                self.assertEqual(res["video_id"], "mock_yt_vid_public")
                self.assertEqual(res["playlist_id"], "mock_pl_888")
                self.assertEqual(res["upload_status"], "PUBLISHED")
                self.assertEqual(res["privacy_status"], "public")

                # Verify synthetic media flag was set
                insert_kwargs = mock_videos.insert.call_args[1]
                body = insert_kwargs["body"]
                self.assertTrue(body["status"]["containsSyntheticMedia"])
                self.assertFalse(body["status"]["selfDeclaredMadeForKids"])
                self.assertEqual(body["status"]["privacyStatus"], "public")

                # Verify publish_verification.json was written including live CDN parity
                verif_file = self.build_dir / "publish_verification.json"
                self.assertTrue(verif_file.is_file())
                verif = json.loads(verif_file.read_text(encoding="utf-8"))
                self.assertEqual(verif["verification_verdict"], "PASSED")
                self.assertEqual(verif["thumbnail_upload_status"], "uploaded")
                self.assertTrue(verif["checks"]["thumbnail"]["match"])
                self.assertEqual(verif["checks"]["thumbnail"]["primary_slot"], "shortsAspectRatio")
                self.assertTrue(verif["checks"]["title"]["match"])
                self.assertTrue(verif["checks"]["privacyStatus"]["match"])
                self.assertTrue(verif["checks"]["playlist_membership"]["is_member"])

    def test_07_thumbnail_403_graceful_handling(self) -> None:
        """Channel without custom thumbnail permission (403) must not fail upload."""
        from googleapiclient.errors import HttpError
        import httplib2

        mock_youtube = MagicMock()
        mock_videos = MagicMock()
        mock_insert = MagicMock()
        mock_insert.execute.return_value = {"id": "mock_vid_403"}
        mock_insert.next_chunk.return_value = (None, {"id": "mock_vid_403"})
        mock_videos.insert.return_value = mock_insert

        mock_vid_list = MagicMock()
        mock_vid_list.execute.return_value = {
            "items": [
                {
                    "id": "mock_vid_403",
                    "snippet": {"title": self.sample_plan["youtube_title"][:100], "categoryId": "27"},
                    "status": {"uploadStatus": "processed", "privacyStatus": "public", "publishAt": None},
                    "processingDetails": {"processingStatus": "succeeded"},
                }
            ]
        }
        mock_videos.list.return_value = mock_vid_list
        mock_youtube.videos.return_value = mock_videos

        # Mock thumbnails.set raising 403 HttpError
        resp = httplib2.Response({"status": 403, "reason": "Forbidden"})
        http_err = HttpError(resp, b"The caller does not have permission for custom thumbnails.")
        mock_thumbnails = MagicMock()
        mock_thumbnails.set.side_effect = http_err
        mock_youtube.thumbnails.return_value = mock_thumbnails

        mock_playlists = MagicMock()
        mock_playlists.list.return_value.execute.return_value = {"items": []}
        mock_playlists.insert.return_value.execute.return_value = {"id": "mock_pl_403"}
        mock_youtube.playlists.return_value = mock_playlists

        mock_pl_items = MagicMock()
        mock_pl_items.insert.return_value.execute.return_value = {"id": "mock_item_403"}
        mock_pl_items.list.return_value.execute.return_value = {"items": []}
        mock_youtube.playlistItems.return_value = mock_pl_items

        (self.build_dir / "thumbnail.jpg").write_bytes(_make_test_jpeg_bytes((1080, 1920), "hero"))

        with patch.dict(
            os.environ,
            {
                "SUTRADHAR_OFFLINE_STUB": "0",
                "YOUTUBE_CLIENT_ID": "mock_client_id",
                "YOUTUBE_CLIENT_SECRET": "mock_secret",
                "YOUTUBE_REFRESH_TOKEN": "mock_refresh",
            },
        ):
            with patch("google.oauth2.credentials.Credentials"), \
                 patch("googleapiclient.discovery.build", return_value=mock_youtube), \
                 patch("googleapiclient.http.MediaFileUpload"), \
                 patch("time.sleep"):

                res = publish_youtube.run_publish_pipeline(self.tmp_dir)

                # Must not fail the upload
                self.assertEqual(res["upload_status"], "PUBLISHED")
                self.assertEqual(res["video_id"], "mock_vid_403")

                # Verify publish_verification.json records 403 status
                verif_file = self.build_dir / "publish_verification.json"
                self.assertTrue(verif_file.is_file())
                verif = json.loads(verif_file.read_text(encoding="utf-8"))
                self.assertEqual(verif["thumbnail_upload_status"], "403_forbidden_custom_thumbnails_pending")

    def test_09_thumbnail_validation_and_cdn_mismatch_fails(self) -> None:
        """Invalid local dimensions or live CDN auto-frame mismatch must fail closed."""
        # 1. Wrong 16:9 thumbnail must fail BEFORE touching YouTube upload API
        (self.build_dir / "thumbnail.jpg").write_bytes(_make_test_jpeg_bytes((1280, 720), "hero"))
        mock_youtube = MagicMock()
        with patch.dict(
            os.environ,
            {
                "SUTRADHAR_OFFLINE_STUB": "0",
                "YOUTUBE_CLIENT_ID": "mock_client_id",
                "YOUTUBE_CLIENT_SECRET": "mock_secret",
                "YOUTUBE_REFRESH_TOKEN": "mock_refresh",
            },
        ):
            with patch("google.oauth2.credentials.Credentials"), \
                 patch("googleapiclient.discovery.build", return_value=mock_youtube):
                res_bad = publish_youtube.run_publish_pipeline(self.tmp_dir)
                self.assertEqual(res_bad["upload_status"], "FAILED")
                self.assertIn("Invalid thumbnail dimensions", res_bad["error_message"])
                mock_youtube.videos.return_value.insert.assert_not_called()

        # 2. Valid local 1080x1920 thumbnail vs mismatched live CDN image (e.g., auto-frame oar2.jpg)
        local_bytes = _make_test_jpeg_bytes((1080, 1920), "hero")
        wrong_cdn_bytes = _make_test_jpeg_bytes((1080, 1920), "autoframe")
        (self.build_dir / "thumbnail.jpg").write_bytes(local_bytes)

        mock_yt2 = MagicMock()
        mock_yt2.videos().insert().next_chunk.return_value = (None, {"id": "mock_vid_mismatch"})
        mock_yt2.videos().list().execute.return_value = {
            "items": [
                {
                    "id": "mock_vid_mismatch",
                    "snippet": {
                        "thumbnails": {
                            "maxres": {"url": "https://i.ytimg.com/vi/mock_vid_mismatch/maxresdefault.jpg"},
                            "shortsAspectRatio": {
                                "url": "https://i.ytimg.com/vi/mock_vid_mismatch/sardefault.jpg",
                                "width": 1080,
                                "height": 1920,
                            },
                        }
                    },
                    "status": {"uploadStatus": "processed", "privacyStatus": "public"},
                    "processingDetails": {"processingStatus": "succeeded", "thumbnailsAvailability": "available"},
                    "contentDetails": {"hasCustomThumbnail": True},
                }
            ]
        }
        mock_yt2.thumbnails().set().execute.return_value = {
            "items": [
                {
                    "shortsAspectRatio": {
                        "url": "https://i.ytimg.com/vi/mock_vid_mismatch/sardefault.jpg",
                        "width": 1080,
                        "height": 1920,
                    }
                }
            ]
        }

        with patch.dict(
            os.environ,
            {
                "SUTRADHAR_OFFLINE_STUB": "0",
                "YOUTUBE_CLIENT_ID": "mock_client_id",
                "YOUTUBE_CLIENT_SECRET": "mock_secret",
                "YOUTUBE_REFRESH_TOKEN": "mock_refresh",
            },
        ):
            with patch("google.oauth2.credentials.Credentials"), \
                 patch("googleapiclient.discovery.build", return_value=mock_yt2), \
                 patch("googleapiclient.http.MediaFileUpload"), \
                 patch("thumbnail_utils.fetch_cdn_image", return_value=(200, wrong_cdn_bytes)), \
                 patch("time.sleep"):
                res_mm = publish_youtube.run_publish_pipeline(self.tmp_dir)
                self.assertEqual(res_mm["upload_status"], "FAILED")
                self.assertIn("does not match local", res_mm["error_message"])
                verif = json.loads((self.build_dir / "publish_verification.json").read_text(encoding="utf-8"))
                self.assertTrue(verif["verification_verdict"].startswith("FAILED:"))

    def test_06_e2e_db_manager_integration(self) -> None:
        """Piping publish_youtube output straight to db_manager.py --record-published must succeed in public mode."""
        loaded_cfg = db_manager.load_config(self.tmp_dir)
        db_manager.cmd_init(self.tmp_dir, loaded_cfg)
        conn = db_manager.connect_db(self.tmp_dir / "episodes.db")
        with db_manager.immediate_transaction(conn) as cur:
            cur.execute(
                """
                INSERT INTO series (series_title, pillar, tts_voice, bgm_track, total_planned_episodes, series_bible_json, status)
                VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE')
                """,
                ("Secrets of the Cosmos", "Cosmic & Scientific Paradoxes", "bm_daniel", "cosmic_mystery.mp3", 3, "{}")
            )

        # Run publish_youtube offline
        with patch.dict(os.environ, {"SUTRADHAR_OFFLINE_STUB": "1", "SUTRADHAR_ROOT": str(self.tmp_dir)}):
            res_pub = publish_youtube.run_publish_pipeline(self.tmp_dir)
            self.assertEqual(res_pub["upload_status"], "PUBLISHED")
            self.assertEqual(res_pub["privacy_status"], "public")

            # Run db_manager cmd_record_published
            db_res = db_manager.cmd_record_published(self.tmp_dir, loaded_cfg)
            self.assertEqual(db_res["action"], "record_published")
            self.assertEqual(db_res["episode_status"], "PUBLISHED")
            self.assertEqual(db_res["series_status"], "ACTIVE")
            self.assertEqual(db_res["completed_episodes"], 1)

    def test_07_description_citations_formatting(self) -> None:
        """Verify format_description_with_citations appends structured provenance to YouTube description."""
        base_desc = "The eternal confrontation between Ravana and Shani Dev. #Shorts #Mythology"
        research = {
            "source_tradition": "Skanda Purana, Kashi Khanda 32",
            "canonical_story_summary": "Ravana subjugates Shani, who subsequently casts his malefic drishti.",
            "key_verified_facts": [
                "Shani's gaze cannot be nullified once cast",
                "Ravana placed planets face down as footstools",
            ],
            "cross_checked_variants": "Valmiki Ramayana Yuddha Kanda mentions victory over planets.",
            "source_references": [
                "Skanda Purana Vol. 4",
                "Kashi Khanda 32.1-45",
            ],
        }

        formatted = publish_youtube.format_description_with_citations(base_desc, research)
        self.assertIn(base_desc, formatted)
        self.assertIn("--- Traditional Sources & References ---", formatted)
        self.assertIn("• Scripture / Source: Skanda Purana, Kashi Khanda 32", formatted)
        self.assertIn("• Variants / Tradition: Valmiki Ramayana Yuddha Kanda", formatted)
        self.assertIn("• Key Verified Facts:", formatted)
        self.assertIn("  - Shani's gaze cannot be nullified once cast", formatted)
        self.assertIn("• Authoritative References:", formatted)
        self.assertIn("  - Skanda Purana Vol. 4", formatted)

        # None or empty research leaves description intact
        self.assertEqual(publish_youtube.format_description_with_citations(base_desc, None), base_desc)
        self.assertEqual(publish_youtube.format_description_with_citations(base_desc, {}), base_desc)

    def test_08_recurring_series_playlist_creation_and_reuse(self) -> None:
        """Verify publishing to a recurring series finds existing playlist or creates it, while standalone skips playlist."""
        mock_youtube = MagicMock()

        # Simulate existing playlist found for "Shani Katha"
        mock_youtube.playlists().list().execute.return_value = {
            "items": [
                {"id": "PL_EXISTING_SHANI", "snippet": {"title": "Shani Katha"}, "status": {"privacyStatus": "public"}}
            ]
        }
        mock_youtube.videos().insert().execute.return_value = {"id": "mock_vid_shani"}
        mock_youtube.videos().insert().next_chunk.return_value = (None, {"id": "mock_vid_shani"})
        mock_youtube.playlistItems().insert().execute.return_value = {"id": "mock_item_id"}
        mock_youtube.videos().list().execute.return_value = {
            "items": [{"id": "mock_vid_shani", "snippet": {"title": "Test Title", "categoryId": "27"}, "status": {"privacyStatus": "public"}}]
        }
        mock_youtube.playlistItems().list().execute.return_value = {
            "items": [{"snippet": {"resourceId": {"videoId": "mock_vid_shani"}}}]
        }

        plan_shani = dict(self.sample_plan)
        plan_shani["content_format"] = "episodic_series"
        plan_shani["series_title"] = "Shani Katha"
        plan_shani["youtube_playlist_id"] = None  # Will discover existing playlist
        (self.build_dir / "episode_plan.json").write_text(json.dumps(plan_shani), encoding="utf-8")

        with patch.dict(
            os.environ,
            {
                "SUTRADHAR_OFFLINE_STUB": "0",
                "YOUTUBE_CLIENT_ID": "mock_client_id",
                "YOUTUBE_CLIENT_SECRET": "mock_secret",
                "YOUTUBE_REFRESH_TOKEN": "mock_refresh",
            },
        ):
            with patch("google.oauth2.credentials.Credentials"), \
                 patch("googleapiclient.discovery.build", return_value=mock_youtube), \
                 patch("googleapiclient.http.MediaFileUpload"):

                res = publish_youtube.run_publish_pipeline(self.tmp_dir)
                self.assertEqual(res["playlist_id"], "PL_EXISTING_SHANI")

                # Standalone test: does not add to playlist
                plan_standalone = dict(self.sample_plan)
                plan_standalone["content_format"] = "standalone"
                plan_standalone["series_title"] = None
                plan_standalone["youtube_playlist_id"] = None
                (self.build_dir / "episode_plan.json").write_text(json.dumps(plan_standalone), encoding="utf-8")

                res_standalone = publish_youtube.run_publish_pipeline(self.tmp_dir)
                self.assertIsNone(res_standalone["playlist_id"])


if __name__ == "__main__":
    unittest.main()
