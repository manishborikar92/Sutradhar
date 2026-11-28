#!/usr/bin/env python3
"""Comprehensive Unit and Contract Tests for scripts/publish_youtube.py (v2 Schema v4)."""

from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import db_manager
import publish_youtube


def _make_test_jpeg_bytes(size: tuple[int, int] = (1080, 1920), variant: str = "hero") -> bytes:
    """Create a valid high-variance JPEG test image in memory."""
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


def _make_v2_plan(
    *,
    content_format: str = "episodic_series",
    series_id: int | None = 1,
    series_title: str | None = "Secrets of the Cosmos",
) -> dict:
    ir_scenes = [
        {
            "atmosphere_mode": "cosmic_explainer",
            "environment_preset": "observatory_cosmos",
            "horizon_y": 1142,
            "camera_move": "slow_push_in",
            "transition_in": "fade",
            "bgm_mood": "cosmic",
            "props": [
                {"id": "brahmaloka_time_chakra", "kind": "brahmaloka_time_chakra", "mount": "sky", "x": 540.0, "y": 520.0}
            ],
            "characters": [
                {"id": "sutradhar_narrator", "role": "sutradhar_narrator", "x": 540.0, "surface_type": "floor", "pose": "gesture", "expr": "serene"}
            ],
        }
        for _ in range(5)
    ]
    return {
        "content_format": content_format,
        "series_id": series_id if content_format != "standalone" else None,
        "series_title": series_title if content_format != "standalone" else None,
        "pillar": "Cosmic & Scientific Paradoxes",
        "episode_number_in_series": 1 if content_format != "standalone" else None,
        "total_planned_episodes": 3 if content_format != "standalone" else None,
        "global_episode_number": 1,
        "tts_voice": "uuyFQegRan8rpIQCGu9K",
        "bgm_track": "cosmic_mystery.mp3",
        "bespoke_asset_path": "canvas_prop:brahmaloka_time_chakra",
        "youtube_title": "What Lies Beyond The Event Horizon? #Shorts",
        "youtube_description": "Explore Vedic cosmic time cycles and modern gravitational relativity.",
        "youtube_tags": [
            "Shorts", "Sutradhar", "Secrets of the Cosmos", "Space", "Relativity",
            "Vedic Science", "Cosmic Time", "Brahmaloka", "Ancient India", "Astronomy",
        ],
        "summary": "Exploring event horizons and Vedic cosmic time.",
        "language": "hi",
        "audio_language": "hi",
        "caption_language": "hi",
        "metadata_language": "en",
        "thumbnail_language": "en",
        "story_research": {
            "source_tradition": "Srimad Bhagavatam & Surya Siddhanta",
            "canonical_story_summary": "Vedic texts describe varying cosmic time scales across loka planes.",
            "key_verified_facts": ["Bhagavatam 9.3 contrasts Brahmaloka time with Bhuloka time."],
            "source_references": ["Srimad Bhagavatam 9.3.29-32", "Surya Siddhanta Ch. 1"],
        },
        "thumbnail_spec": {
            "pill": "COSMIC PARADOX",
            "headline_line1": "BEYOND THE",
            "headline_line2": "EVENT HORIZON",
            "sub_pill": "VEDIC RELATIVITY",
            "font_weight": 800,
            "theme": "observatory_cosmos",
        },
        "storyboard_ir": {
            "visual_direction_version": "v2_storycraft",
            "width": 1080,
            "height": 1920,
            "fps": 30,
            "horizon_y": 1142,
            "scenes": ir_scenes,
        },
        "scenes": [
            {
                "scene_index": i,
                "narration_text": f"[slowly, solemn, deep] ब्रह्माण्ड के इस अद्भुत रहस्य में समय की गति बदल जाती है भाग {i}।",
                "visual_mode": "character_drama",
                "backdrop_rig": "observatory_cosmos",
                "primary_character": "sutradhar_narrator",
                "emotion": "calm",
                "action_gesture": "idle_breathe",
                "mood_palette": "cosmic_indigo",
                "particle_theme": "starfield_warp",
                "camera_motion": "slow_push",
                "transition_sfx": "sub_hit.wav",
                "visual_spec": ir_scenes[i - 1],
            }
            for i in range(1, 6)
        ],
    }


class TestPublishYouTube(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="sutradhar_pub_test_"))
        self.build_dir = self.tmp_dir / "build"
        self.build_dir.mkdir(parents=True, exist_ok=True)

        shutil.copy2(REPO_ROOT / "config.yaml", self.tmp_dir / "config.yaml")
        self.cfg = db_manager.load_config(self.tmp_dir)

        self.sample_plan = _make_v2_plan()
        (self.build_dir / "episode_plan.json").write_text(
            json.dumps(self.sample_plan, ensure_ascii=False), encoding="utf-8"
        )
        (self.build_dir / "final_short.mp4").write_bytes(b"\x00\x00\x00\x20ftypisom" + b"\x00" * 1024)

        thumb_bytes = _make_test_jpeg_bytes((1080, 1920), "hero")
        thumb_path = self.build_dir / "thumbnail.jpg"
        thumb_path.write_bytes(thumb_bytes)
        with Image.open(thumb_path) as im:
            im.crop((0, 150, 1080, 1770)).save(self.build_dir / "thumbnail_2x3_crop.jpg", format="JPEG", quality=92)
        (self.build_dir / "qa_report.json").write_text(json.dumps({"passed": True}), encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_01_cli_zero_arguments(self) -> None:
        with patch("sys.argv", ["publish_youtube.py", "--force"]):
            ret = publish_youtube.main()
            self.assertEqual(ret, 1)

    def test_02_safety_guards(self) -> None:
        import yaml

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

        bad_cfg2 = dict(self.cfg)
        bad_cfg2["publishing"] = {"upload_mode": "unsupported_mode", "allow_public_or_scheduled": True}
        (self.tmp_dir / "config.yaml").write_text(yaml.safe_dump(bad_cfg2), encoding="utf-8")
        with self.assertRaises((publish_youtube.PublishPipelineError, db_manager.StateError)) as ctx2:
            publish_youtube.run_publish_pipeline(self.tmp_dir)
        self.assertIn("upload_mode", str(ctx2.exception))

    def test_03_missing_inputs(self) -> None:
        (self.build_dir / "final_short.mp4").unlink()
        with self.assertRaises(publish_youtube.PublishPipelineError) as ctx:
            publish_youtube.run_publish_pipeline(self.tmp_dir)
        self.assertIn("Missing master video file", str(ctx.exception))

    def test_04_offline_stub_mode_public_and_private(self) -> None:
        import yaml

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

            out_file = self.build_dir / "publish_result.json"
            self.assertTrue(out_file.is_file())
            pub_model = db_manager.PublishResult.model_validate(res, context={"config": pub_cfg})
            self.assertEqual(pub_model.upload_status, "PUBLISHED")

        priv_cfg = dict(self.cfg)
        priv_cfg["publishing"] = {"upload_mode": "private_review", "allow_public_or_scheduled": False}
        (self.tmp_dir / "config.yaml").write_text(yaml.safe_dump(priv_cfg), encoding="utf-8")

        with patch.dict(os.environ, {"SUTRADHAR_OFFLINE_STUB": "1"}, clear=False):
            res_priv = publish_youtube.run_publish_pipeline(self.tmp_dir)
            self.assertEqual(res_priv["upload_status"], "PRIVATE_REVIEW")
            self.assertEqual(res_priv["privacy_status"], "private")

    def test_05_mocked_live_public_upload(self) -> None:
        import yaml

        pub_cfg = dict(self.cfg)
        pub_cfg["publishing"] = {"upload_mode": "public", "allow_public_or_scheduled": True}
        (self.tmp_dir / "config.yaml").write_text(yaml.safe_dump(pub_cfg), encoding="utf-8")

        expected_desc = publish_youtube.format_description_with_citations(
            self.sample_plan["youtube_description"],
            self.sample_plan["story_research"],
        )

        mock_youtube = MagicMock()
        mock_videos = MagicMock()
        mock_insert = MagicMock()
        mock_insert.execute.return_value = {"id": "mock_yt_vid_public"}
        mock_insert.next_chunk.return_value = (None, {"id": "mock_yt_vid_public"})
        mock_videos.insert.return_value = mock_insert

        mock_vid_list = MagicMock()
        mock_vid_list.execute.return_value = {
            "items": [
                {
                    "id": "mock_yt_vid_public",
                    "snippet": {
                        "title": self.sample_plan["youtube_title"],
                        "description": expected_desc,
                        "categoryId": "27",
                        "defaultLanguage": "en",
                        "defaultAudioLanguage": "hi",
                        "thumbnails": {
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
                    "processingDetails": {"processingStatus": "succeeded", "thumbnailsAvailability": "available"},
                    "contentDetails": {"hasCustomThumbnail": True},
                }
            ]
        }
        mock_videos.list.return_value = mock_vid_list
        mock_youtube.videos.return_value = mock_videos

        mock_thumbnails = MagicMock()
        mock_thumbnails.set.return_value.execute.return_value = {
            "items": [
                {
                    "shortsAspectRatio": {
                        "url": "https://i.ytimg.com/vi/mock_yt_vid_public/sardefault.jpg",
                        "width": 1080,
                        "height": 1920,
                    }
                }
            ]
        }
        mock_youtube.thumbnails.return_value = mock_thumbnails

        mock_playlists = MagicMock()
        mock_playlists.list.return_value.execute.return_value = {"items": []}
        mock_playlists.insert.return_value.execute.return_value = {"id": "mock_pl_888"}
        mock_youtube.playlists.return_value = mock_playlists

        mock_pl_items = MagicMock()
        mock_pl_items.insert.return_value.execute.return_value = {"id": "mock_pl_item_777"}
        mock_pl_items.list.return_value.execute.return_value = {
            "items": [{"snippet": {"resourceId": {"videoId": "mock_yt_vid_public"}}}]
        }
        mock_youtube.playlistItems.return_value = mock_pl_items

        thumb_bytes = (self.build_dir / "thumbnail.jpg").read_bytes()
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
                 patch("thumbnail_utils.fetch_cdn_image", return_value=(200, thumb_bytes)), \
                 patch("time.sleep"):

                res = publish_youtube.run_publish_pipeline(self.tmp_dir)
                self.assertEqual(res["video_id"], "mock_yt_vid_public")
                self.assertEqual(res["playlist_id"], "mock_pl_888")
                self.assertEqual(res["upload_status"], "PUBLISHED")
                self.assertEqual(res["privacy_status"], "public")

                insert_kwargs = mock_videos.insert.call_args[1]
                body = insert_kwargs["body"]
                self.assertTrue(body["status"]["containsSyntheticMedia"])
                self.assertFalse(body["status"]["selfDeclaredMadeForKids"])
                self.assertEqual(body["snippet"]["defaultLanguage"], "en")
                self.assertEqual(body["snippet"]["defaultAudioLanguage"], "hi")

                verif = json.loads((self.build_dir / "publish_verification.json").read_text(encoding="utf-8"))
                self.assertEqual(verif["verification_verdict"], "PASSED")
                self.assertEqual(verif["thumbnail_upload_status"], "uploaded")
                self.assertTrue(verif["checks"]["thumbnail"]["match"])
                self.assertTrue(verif["checks"]["playlist_membership"]["is_member"])

    def test_06_thumbnail_403_graceful_handling(self) -> None:
        from googleapiclient.errors import HttpError
        import httplib2

        mock_youtube = MagicMock()
        mock_youtube.videos().insert().next_chunk.return_value = (None, {"id": "mock_vid_403"})
        mock_youtube.videos().list().execute.return_value = {
            "items": [
                {
                    "id": "mock_vid_403",
                    "snippet": {"title": self.sample_plan["youtube_title"], "categoryId": "27"},
                    "status": {"uploadStatus": "processed", "privacyStatus": "public", "publishAt": None},
                    "processingDetails": {"processingStatus": "succeeded"},
                }
            ]
        }

        resp = httplib2.Response({"status": 403, "reason": "Forbidden"})
        mock_youtube.thumbnails().set.side_effect = HttpError(
            resp, b"The caller does not have permission for custom thumbnails."
        )
        mock_youtube.playlists().list().execute.return_value = {"items": []}
        mock_youtube.playlists().insert().execute.return_value = {"id": "mock_pl_403"}
        mock_youtube.playlistItems().insert().execute.return_value = {"id": "mock_item_403"}
        mock_youtube.playlistItems().list().execute.return_value = {"items": []}

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
                self.assertEqual(res["upload_status"], "PUBLISHED")
                self.assertEqual(res["video_id"], "mock_vid_403")
                verif = json.loads((self.build_dir / "publish_verification.json").read_text(encoding="utf-8"))
                self.assertEqual(verif["thumbnail_upload_status"], "403_forbidden_custom_thumbnails_pending")

    def test_07_thumbnail_validation_and_cdn_mismatch_fails(self) -> None:
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
                            "shortsAspectRatio": {
                                "url": "https://i.ytimg.com/vi/mock_vid_mismatch/sardefault.jpg",
                                "width": 1080,
                                "height": 1920,
                            }
                        }
                    },
                    "status": {"uploadStatus": "processed", "privacyStatus": "public"},
                    "processingDetails": {"processingStatus": "succeeded", "thumbnailsAvailability": "available"},
                    "contentDetails": {"hasCustomThumbnail": True},
                }
            ]
        }
        mock_yt2.thumbnails().set().execute.return_value = {
            "items": [{"shortsAspectRatio": {"url": "https://i.ytimg.com/vi/mock_vid_mismatch/sardefault.jpg"}}]
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

    def test_08_e2e_db_manager_integration(self) -> None:
        loaded_cfg = db_manager.load_config(self.tmp_dir)
        db_manager.cmd_init(self.tmp_dir, loaded_cfg)
        conn = db_manager.connect_db(self.tmp_dir / "episodes.db")
        try:
            with db_manager.immediate_transaction(conn) as cur:
                cur.execute(
                    """
                    INSERT INTO series (series_title, series_title_en, pillar, tts_voice, bgm_track, total_planned_episodes, series_bible_json, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'ACTIVE')
                    """,
                    ("Secrets of the Cosmos", "Secrets of the Cosmos", "Cosmic & Scientific Paradoxes", "uuyFQegRan8rpIQCGu9K", "cosmic_mystery.mp3", 3, "{}"),
                )
        finally:
            conn.close()

        with patch.dict(os.environ, {"SUTRADHAR_OFFLINE_STUB": "1", "SUTRADHAR_ROOT": str(self.tmp_dir)}):
            res_pub = publish_youtube.run_publish_pipeline(self.tmp_dir)
            self.assertEqual(res_pub["upload_status"], "PUBLISHED")
            self.assertEqual(res_pub["privacy_status"], "public")

            db_res = db_manager.cmd_record_published(self.tmp_dir, loaded_cfg)
            self.assertEqual(db_res["action"], "record_published")
            self.assertEqual(db_res["episode_status"], "PUBLISHED")
            self.assertEqual(db_res["series_status"], "ACTIVE")
            self.assertEqual(db_res["completed_episodes"], 1)

    def test_09_description_citations_formatting(self) -> None:
        base_desc = "The eternal confrontation between Ravana and Shani Dev. #Shorts #Mythology"
        research = {
            "source_tradition": "Skanda Purana, Kashi Khanda 32",
            "canonical_story_summary": "Ravana subjugates Shani, who subsequently casts his malefic drishti.",
            "key_verified_facts": [
                "Shani's gaze cannot be nullified once cast",
                "Ravana placed planets face down as footstools",
            ],
            "cross_checked_variants": "Valmiki Ramayana Yuddha Kanda mentions victory over planets.",
            "source_references": ["Skanda Purana Vol. 4", "Kashi Khanda 32.1-45"],
        }
        formatted = publish_youtube.format_description_with_citations(base_desc, research)
        self.assertIn(base_desc, formatted)
        self.assertIn("--- Traditional Sources & References ---", formatted)
        self.assertIn("• Scripture / Source: Skanda Purana, Kashi Khanda 32", formatted)
        self.assertEqual(publish_youtube.format_description_with_citations(base_desc, None), base_desc)
        self.assertEqual(publish_youtube.format_description_with_citations(base_desc, {}), base_desc)

    def test_10_recurring_series_playlist_creation_and_reuse(self) -> None:
        mock_youtube = MagicMock()
        mock_youtube.playlists().list().execute.return_value = {
            "items": [
                {"id": "PL_EXISTING_SHANI", "snippet": {"title": "Shani Katha", "defaultLanguage": "en"}, "status": {"privacyStatus": "public"}}
            ]
        }
        mock_youtube.videos().insert().next_chunk.return_value = (None, {"id": "mock_vid_shani"})
        mock_youtube.playlistItems().insert().execute.return_value = {"id": "mock_item_id"}
        mock_youtube.videos().list().execute.return_value = {
            "items": [
                {
                    "id": "mock_vid_shani",
                    "snippet": {
                        "title": "Test Title",
                        "categoryId": "27",
                        "thumbnails": {"shortsAspectRatio": {"url": "https://i.ytimg.com/vi/mock_vid_shani/sardefault.jpg"}},
                    },
                    "status": {"uploadStatus": "processed", "privacyStatus": "public"},
                    "processingDetails": {"processingStatus": "succeeded", "thumbnailsAvailability": "available"},
                    "contentDetails": {"hasCustomThumbnail": True},
                }
            ]
        }
        mock_youtube.thumbnails().set().execute.return_value = {
            "items": [{"shortsAspectRatio": {"url": "https://i.ytimg.com/vi/mock_vid_shani/sardefault.jpg"}}]
        }
        mock_youtube.playlistItems().list().execute.return_value = {
            "items": [{"snippet": {"resourceId": {"videoId": "mock_vid_shani"}}}]
        }

        thumb_bytes = (self.build_dir / "thumbnail.jpg").read_bytes()
        plan_shani = _make_v2_plan(content_format="episodic_series", series_id=1, series_title="Shani Katha")
        (self.build_dir / "episode_plan.json").write_text(json.dumps(plan_shani, ensure_ascii=False), encoding="utf-8")

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
                 patch("thumbnail_utils.fetch_cdn_image", return_value=(200, thumb_bytes)), \
                 patch("time.sleep"):

                res = publish_youtube.run_publish_pipeline(self.tmp_dir)
                self.assertEqual(res["playlist_id"], "PL_EXISTING_SHANI")

                plan_standalone = _make_v2_plan(content_format="standalone", series_id=None, series_title=None)
                (self.build_dir / "episode_plan.json").write_text(
                    json.dumps(plan_standalone, ensure_ascii=False), encoding="utf-8"
                )
                res_standalone = publish_youtube.run_publish_pipeline(self.tmp_dir)
                self.assertIsNone(res_standalone["playlist_id"])


if __name__ == "__main__":
    unittest.main()
