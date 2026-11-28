#!/usr/bin/env python3
"""Unit, integration, and cross-document consistency tests (`sutradhar.publishing`)."""

from __future__ import annotations

import io
import json
import os
import re
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

import db_manager  # noqa: E402
import publish_youtube  # noqa: E402
import thumbnail_utils  # noqa: E402
from sutradhar.publishing import (  # noqa: E402
    MetadataPolicyError,
    PlaylistResolutionError,
    ThumbnailValidationError,
    build_video_metadata,
    list_channel_playlists_paginated,
    publish_episode,
    resolve_or_create_series_playlist,
    update_playlists,
    update_thumbnail_only,
    validate_2x3_crop_bounds,
    validate_english_metadata,
    validate_english_playlist_title,
    verify_live_channel_state,
    verify_live_sardefault_parity,
)


def _make_jpeg_bytes(size: tuple[int, int] = (1080, 1920), *, variant: str = "hero") -> bytes:
    im = Image.new("RGB", size, (14, 22, 56) if variant == "hero" else (210, 220, 200))
    draw = ImageDraw.Draw(im)
    w, h = size
    if variant == "hero":
        draw.rectangle([80, 240, w - 80, 620], fill=(246, 196, 83))
        draw.ellipse([w // 2 - 220, 820, w // 2 + 220, 1260], fill=(255, 244, 210))
        draw.rectangle([0, h - 420, w, h], fill=(92, 46, 26))
    elif variant == "alt":
        draw.rectangle([0, 0, w, h // 2], fill=(25, 115, 105))
        draw.polygon([(120, 1450), (960, 1450), (540, 380)], fill=(195, 65, 70))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def _make_v2_episode_plan(*, content_format: str = "episodic_series", series_id: int | None = 1) -> dict:
    return {
        "content_format": content_format,
        "series_id": series_id if content_format != "standalone" else None,
        "series_title": "Hidden History of Ancient India" if content_format != "standalone" else None,
        "pillar": "Hidden History",
        "episode_number_in_series": 1 if content_format != "standalone" else None,
        "total_planned_episodes": None,
        "global_episode_number": 1,
        "tts_voice": "uuyFQegRan8rpIQCGu9K",
        "bgm_track": "epic_history.mp3",
        "bespoke_asset_path": "canvas_prop:meru_route_scroll",
        "youtube_title": "How Ancient Indian Astronomers Mapped the Sky #Shorts",
        "youtube_description": (
            "Discover how ancient Indian observatories and astronomical manuals computed cosmic cycles "
            "with remarkable precision."
        ),
        "youtube_tags": [
            "Shorts",
            "Sutradhar",
            "Sutradhar Chronicles",
            "Ancient India",
            "Indian History",
            "Hidden History",
            "Vedic Astronomy",
            "Surya Siddhanta",
            "Nalanda",
            "Indian Science",
            "Cosmic Time",
        ],
        "summary": "A concise exploration of ancient Indian astronomical calculation and heritage.",
        "language": "hi",
        "audio_language": "hi",
        "caption_language": "hi",
        "metadata_language": "en",
        "thumbnail_language": "en",
        "target_duration_sec": 48.0,
        "story_research": {
            "source_tradition": "Aryabhatiya & Surya Siddhanta",
            "canonical_story_summary": "Classical Indian astronomical texts record planetary cycles and sidereal calculations.",
            "key_verified_facts": ["Aryabhatiya Golapada describes celestial sphere geometry."],
            "source_references": ["Aryabhatiya — Golapada", "Surya Siddhanta — Chapter 1"],
        },
        "thumbnail_spec": {
            "pill": "HIDDEN HISTORY",
            "headline_line1": "ANCIENT SKY",
            "headline_line2": "OBSERVATORY",
            "sub_pill": "VEDIC ASTRONOMY",
            "font_weight": 800,
            "theme": "nalanda_archival",
        },
        "storyboard_ir": {
            "visual_direction_version": "v2_storycraft",
            "width": 1080,
            "height": 1920,
            "fps": 30,
            "horizon_y": 1142,
            "scenes": [
                {
                    "atmosphere_mode": "archival",
                    "environment_preset": "nalanda_archival",
                    "horizon_y": 1142,
                    "camera_move": "slow_push_in",
                    "transition_in": "fade",
                    "bgm_mood": "epic",
                    "props": [{"id": "meru_route_scroll", "kind": "meru_route_scroll", "mount": "table", "x": 540}],
                    "characters": [{"id": "ancient_scholar", "role": "scholar", "x": 420, "surface_type": "floor", "pose": "gesture", "expr": "determined"}],
                }
                for _ in range(5)
            ],
        },
        "scenes": [
            {
                "scene_index": i,
                "narration_text": f"[slowly, solemn, deep] प्राचीन भारत के खगोलशास्त्र में ब्रह्माण्ड का अद्भुत गणित छिपा था भाग {i}।",
                "visual_mode": "character_drama",
                "backdrop_rig": "nalanda_archival",
                "primary_character": "ancient_scholar",
                "emotion": "calm",
                "action_gesture": "idle_breathe",
                "mood_palette": "golden_imperial",
                "particle_theme": "golden_embers",
                "camera_motion": "slow_push",
                "speaker_role": "narrator",
                "visual_spec": {
                    "atmosphere_mode": "archival",
                    "environment_preset": "nalanda_archival",
                    "horizon_y": 1142,
                    "camera_move": "slow_push_in",
                    "transition_in": "fade",
                    "bgm_mood": "epic",
                    "props": [{"id": "meru_route_scroll", "kind": "meru_route_scroll", "mount": "table", "x": 540}],
                    "characters": [{"id": "ancient_scholar", "role": "scholar", "x": 420, "surface_type": "floor", "pose": "gesture", "expr": "determined"}],
                },
            }
            for i in range(1, 6)
        ],
    }


class TestPhase5Publishing(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="sutradhar_p5_test_"))
        self.build_dir = self.tmp_dir / "build"
        self.build_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / "config.yaml", self.tmp_dir / "config.yaml")
        self.cfg = db_manager.load_config(self.tmp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # 1. Thumbnail Verifier & 2:3 Crop Bounds
    # ------------------------------------------------------------------

    def test_01_thumbnail_2x3_crop_and_sardefault_ep3_boundary(self) -> None:
        thumb_path = self.build_dir / "thumbnail.jpg"
        crop_path = self.build_dir / "thumbnail_2x3_crop.jpg"
        hero_bytes = _make_jpeg_bytes((1080, 1920), variant="hero")
        thumb_path.write_bytes(hero_bytes)

        with Image.open(thumb_path) as im:
            im.crop((0, 150, 1080, 1770)).save(crop_path, format="JPEG", quality=92)

        crop_info = validate_2x3_crop_bounds(thumb_path, crop_path=crop_path)
        self.assertEqual(crop_info["crop_size"], [1080, 1620])
        self.assertTrue(crop_info["crop_file_verified"])

        # Wrong crop size must fail closed
        wrong_crop = self.build_dir / "bad_crop.jpg"
        wrong_crop.write_bytes(_make_jpeg_bytes((1080, 1920), variant="hero"))
        with self.assertRaises(ThumbnailValidationError):
            validate_2x3_crop_bounds(thumb_path, crop_path=wrong_crop)

        # Ep 1-2 historical baselines are exempt from sardefault.jpg enforcement
        ep2_item = {"id": "hcKmhzjQkz4", "snippet": {"thumbnails": {}}, "contentDetails": {"hasCustomThumbnail": False}}
        res_ep2 = verify_live_sardefault_parity(ep2_item, thumb_path, global_episode_number=2)
        self.assertFalse(res_ep2["enforced"])
        self.assertTrue(res_ep2["legacy_baseline"])
        self.assertTrue(res_ep2["passed"])

        # Ep 3+ requires live 1080x1920 sardefault.jpg matching MAE <= 12 & dhash <= 16
        ep3_missing = {"id": "ep3_vid", "snippet": {"thumbnails": {"maxres": {"url": "https://x/m.jpg"}}}, "contentDetails": {"hasCustomThumbnail": True}}
        res_missing = verify_live_sardefault_parity(ep3_missing, thumb_path, global_episode_number=3)
        self.assertTrue(res_missing["enforced"])
        self.assertFalse(res_missing["passed"])

        ep3_ok = {
            "id": "ep3_vid",
            "snippet": {"thumbnails": {"shortsAspectRatio": {"url": "https://i.ytimg.com/vi/ep3_vid/sardefault.jpg"}}},
            "contentDetails": {"hasCustomThumbnail": True},
        }
        res_ok = verify_live_sardefault_parity(
            ep3_ok,
            thumb_path,
            global_episode_number=3,
            fetch_url_fn=lambda _u: (200, hero_bytes),
        )
        self.assertTrue(res_ok["passed"])
        self.assertLessEqual(res_ok["similarity"]["mae"], 12.0)

        # Mismatched CDN image fails closed
        alt_bytes = _make_jpeg_bytes((1080, 1920), variant="alt")
        res_bad = verify_live_sardefault_parity(
            ep3_ok,
            thumb_path,
            global_episode_number=4,
            fetch_url_fn=lambda _u: (200, alt_bytes),
        )
        self.assertFalse(res_bad["passed"])

    # ------------------------------------------------------------------
    # 2. Metadata Policy & Paginated Playlist Resolution
    # ------------------------------------------------------------------

    def test_02_metadata_policy_bilingual_guards_and_paginated_playlists(self) -> None:
        plan = _make_v2_episode_plan()
        meta = build_video_metadata(plan, self.cfg, strict_v2=True)
        self.assertEqual(meta["defaultLanguage"], "en")
        self.assertEqual(meta["defaultAudioLanguage"], "hi")
        self.assertEqual(meta["categoryId"], "27")
        self.assertIn("--- Traditional Sources & References ---", meta["description"])
        self.assertTrue(10 <= len(meta["tags"]) <= 15)

        # Devanagari in title/description/tags/playlist must raise MetadataPolicyError
        with self.assertRaises(MetadataPolicyError):
            validate_english_metadata("जब रावण #Shorts", "English description text", ["a"] * 10)
        with self.assertRaises(MetadataPolicyError):
            validate_english_metadata("Valid Title #Shorts", "Devanagari वर्णन leaked", ["a"] * 10)
        with self.assertRaises(MetadataPolicyError):
            validate_english_metadata("Valid Title #Shorts", "English description text", ["Shorts"] * 9 + ["शिव"])
        with self.assertRaises(MetadataPolicyError):
            validate_english_metadata("Missing Hashtag", "English description text", [f"tag{i}" for i in range(10)])
        with self.assertRaises(MetadataPolicyError):
            validate_english_metadata("Valid Title #Shorts", "English description text", ["only_one"])
        with self.assertRaises(MetadataPolicyError):
            validate_english_playlist_title("शनि कथा")

        # Paginated playlists.list across 2 pages finds series on page 2
        yt = MagicMock()
        yt.playlists().list().execute.side_effect = [
            {"items": [{"id": "PL_1", "snippet": {"title": "Other Series", "defaultLanguage": "en"}, "status": {"privacyStatus": "public"}}], "nextPageToken": "PAGE_2"},
            {"items": [{"id": "PL_2", "snippet": {"title": "Hidden History of Ancient India", "defaultLanguage": "en"}, "status": {"privacyStatus": "public"}}]},
        ]
        found_all = list_channel_playlists_paginated(yt)
        self.assertEqual(len(found_all), 2)

        yt.playlists().list().execute.side_effect = [
            {"items": [{"id": "PL_1", "snippet": {"title": "Other Series", "defaultLanguage": "en"}, "status": {"privacyStatus": "public"}}], "nextPageToken": "PAGE_2"},
            {"items": [{"id": "PL_2", "snippet": {"title": "Hidden History of Ancient India", "defaultLanguage": "en"}, "status": {"privacyStatus": "public"}}]},
        ]
        pl_id = resolve_or_create_series_playlist(yt, series_title="Hidden History of Ancient India", auto_create=False)
        self.assertEqual(pl_id, "PL_2")

        # Fail closed when playlist lookup fails
        yt_err = MagicMock()
        yt_err.playlists().list().execute.side_effect = RuntimeError("network timeout")
        with self.assertRaises(PlaylistResolutionError):
            resolve_or_create_series_playlist(yt_err, series_title="Hidden History of Ancient India")

    # ------------------------------------------------------------------
    # 3. Atomic --publish + Rollback Safety + Maintenance Flags
    # ------------------------------------------------------------------

    def _seed_v2_build_and_db(self, *, plan: dict | None = None) -> tuple[dict, bytes]:
        db_manager.cmd_init(self.tmp_dir, self.cfg)
        conn = db_manager.connect_db(self.tmp_dir / "episodes.db")
        try:
            with db_manager.immediate_transaction(conn) as cur:
                cur.execute(
                    """
                    INSERT INTO series (
                        series_title, series_title_en, pillar, tts_voice, bgm_track,
                        total_planned_episodes, completed_episodes, series_bible_json, status
                    ) VALUES (?, ?, ?, ?, ?, NULL, 0, '{}', 'ACTIVE')
                    """,
                    (
                        "Hidden History of Ancient India",
                        "Hidden History of Ancient India",
                        "Hidden History",
                        "uuyFQegRan8rpIQCGu9K",
                        "epic_history.mp3",
                    ),
                )
        finally:
            conn.close()

        ep_plan = plan or _make_v2_episode_plan()
        (self.build_dir / "episode_plan.json").write_text(json.dumps(ep_plan, ensure_ascii=False), encoding="utf-8")
        (self.build_dir / "final_short.mp4").write_bytes(b"\x00\x00\x00\x20ftypisom" + b"\x00" * 4096)

        hero_bytes = _make_jpeg_bytes((1080, 1920), variant="hero")
        thumb_path = self.build_dir / "thumbnail.jpg"
        thumb_path.write_bytes(hero_bytes)
        with Image.open(thumb_path) as im:
            im.crop((0, 150, 1080, 1770)).save(self.build_dir / "thumbnail_2x3_crop.jpg", format="JPEG", quality=92)

        (self.build_dir / "qa_report.json").write_text(
            json.dumps(
                {
                    "passed": True,
                    "mp4_gate": {"duration_sec": 48.0},
                    "motion_and_look_gate": {"kinocut": {"dark_score": 92.5, "static_fraction": 0.04}},
                }
            ),
            encoding="utf-8",
        )
        return ep_plan, hero_bytes

    def test_03_atomic_publish_commits_episodes_and_publishing_history(self) -> None:
        ep_plan, hero_bytes = self._seed_v2_build_and_db()
        desc_expected = publish_youtube.format_description_with_citations(
            ep_plan["youtube_description"], ep_plan["story_research"]
        )

        mock_yt = MagicMock()
        mock_yt.videos().insert().next_chunk.return_value = (None, {"id": "vid_p5_ok"})
        mock_yt.playlists().list().execute.return_value = {"items": []}
        mock_yt.playlists().insert().execute.return_value = {"id": "PL_P5_NEW"}
        mock_yt.playlistItems().insert().execute.return_value = {"id": "PLI_1"}
        mock_yt.playlistItems().list().execute.return_value = {
            "items": [{"snippet": {"resourceId": {"videoId": "vid_p5_ok"}}}]
        }
        mock_yt.thumbnails().set().execute.return_value = {
            "items": [
                {
                    "shortsAspectRatio": {
                        "url": "https://i.ytimg.com/vi/vid_p5_ok/sardefault.jpg",
                        "width": 1080,
                        "height": 1920,
                    }
                }
            ]
        }
        mock_yt.videos().list().execute.return_value = {
            "items": [
                {
                    "id": "vid_p5_ok",
                    "snippet": {
                        "title": ep_plan["youtube_title"],
                        "description": desc_expected,
                        "categoryId": "27",
                        "defaultLanguage": "en",
                        "defaultAudioLanguage": "hi",
                        "thumbnails": {
                            "maxres": {"url": "https://i.ytimg.com/vi/vid_p5_ok/maxresdefault.jpg"},
                            "shortsAspectRatio": {
                                "url": "https://i.ytimg.com/vi/vid_p5_ok/sardefault.jpg",
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

        with patch.dict(
            os.environ,
            {
                "SUTRADHAR_OFFLINE_STUB": "0",
                "YOUTUBE_CLIENT_ID": "cid",
                "YOUTUBE_CLIENT_SECRET": "csec",
                "YOUTUBE_REFRESH_TOKEN": "rtok",
            },
        ), patch("googleapiclient.http.MediaFileUpload"), patch(
            "thumbnail_utils.fetch_cdn_image", return_value=(200, hero_bytes)
        ), patch("time.sleep"):
            res = publish_episode(self.tmp_dir, youtube_client=mock_yt)

        self.assertEqual(res["upload_status"], "PUBLISHED")
        self.assertEqual(res["video_id"], "vid_p5_ok")
        self.assertEqual(res["playlist_id"], "PL_P5_NEW")

        conn = db_manager.connect_db(self.tmp_dir / "episodes.db")
        try:
            ep_row = conn.execute("SELECT * FROM episodes WHERE youtube_video_id = 'vid_p5_ok'").fetchone()
            self.assertIsNotNone(ep_row)
            self.assertEqual(ep_row["status"], "PUBLISHED")
            self.assertEqual(ep_row["video_url"], "https://youtu.be/vid_p5_ok")
            self.assertIsNotNone(ep_row["published_at"])
            self.assertAlmostEqual(float(ep_row["kinocut_score"]), 92.5, places=1)
            self.assertAlmostEqual(float(ep_row["static_fraction"]), 0.04, places=2)

            hist_row = conn.execute("SELECT * FROM publishing_history WHERE youtube_video_id = 'vid_p5_ok'").fetchone()
            self.assertIsNotNone(hist_row)
            self.assertEqual(hist_row["playlist_id"], "PL_P5_NEW")
            self.assertEqual(hist_row["cdn_thumbnail_url"], "https://i.ytimg.com/vi/vid_p5_ok/sardefault.jpg")
            self.assertLessEqual(float(hist_row["cdn_mae"]), 12.0)

            series_row = conn.execute("SELECT completed_episodes, youtube_playlist_id FROM series WHERE series_id = 1").fetchone()
            self.assertEqual(series_row["completed_episodes"], 1)
            self.assertEqual(series_row["youtube_playlist_id"], "PL_P5_NEW")
        finally:
            conn.close()

    def test_04_cdn_failure_and_playlist_failure_rollback_safely(self) -> None:
        _, _ = self._seed_v2_build_and_db()
        wrong_bytes = _make_jpeg_bytes((1080, 1920), variant="alt")

        # 1. Failed QA report blocks publish before any YouTube call
        (self.build_dir / "qa_report.json").write_text(json.dumps({"passed": False, "failures": ["dark_score < 88"]}), encoding="utf-8")
        with self.assertRaises(publish_youtube.PublishPipelineError):
            publish_episode(self.tmp_dir, youtube_client=MagicMock())
        (self.build_dir / "qa_report.json").write_text(json.dumps({"passed": True}), encoding="utf-8")

        # 2. CDN parity mismatch must return FAILED and NOT write episode to DB
        mock_yt = MagicMock()
        mock_yt.videos().insert().next_chunk.return_value = (None, {"id": "vid_cdn_fail"})
        mock_yt.playlists().list().execute.return_value = {
            "items": [{"id": "PL_OK", "snippet": {"title": "Hidden History of Ancient India", "defaultLanguage": "en"}, "status": {"privacyStatus": "public"}}]
        }
        mock_yt.playlistItems().insert().execute.return_value = {"id": "PLI_1"}
        mock_yt.thumbnails().set().execute.return_value = {
            "items": [{"shortsAspectRatio": {"url": "https://i.ytimg.com/vi/vid_cdn_fail/sardefault.jpg"}}]
        }
        mock_yt.videos().list().execute.return_value = {
            "items": [
                {
                    "id": "vid_cdn_fail",
                    "snippet": {"thumbnails": {"shortsAspectRatio": {"url": "https://i.ytimg.com/vi/vid_cdn_fail/sardefault.jpg"}}},
                    "status": {"uploadStatus": "processed"},
                    "processingDetails": {"processingStatus": "succeeded", "thumbnailsAvailability": "available"},
                    "contentDetails": {"hasCustomThumbnail": True},
                }
            ]
        }

        with patch.dict(
            os.environ,
            {
                "SUTRADHAR_OFFLINE_STUB": "0",
                "YOUTUBE_CLIENT_ID": "cid",
                "YOUTUBE_CLIENT_SECRET": "csec",
                "YOUTUBE_REFRESH_TOKEN": "rtok",
            },
        ), patch("googleapiclient.http.MediaFileUpload"), patch(
            "thumbnail_utils.fetch_cdn_image", return_value=(200, wrong_bytes)
        ), patch("time.sleep"):
            res = publish_episode(self.tmp_dir, youtube_client=mock_yt)

        self.assertEqual(res["upload_status"], "FAILED")
        self.assertIn("does not match local", res["error_message"])
        conn = db_manager.connect_db(self.tmp_dir / "episodes.db")
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM publishing_history").fetchone()[0], 0)
        finally:
            conn.close()

        # 3. Playlist assignment failure for episodic_series must fail closed (not warn & continue)
        mock_yt_pl = MagicMock()
        mock_yt_pl.videos().insert().next_chunk.return_value = (None, {"id": "vid_pl_fail"})
        mock_yt_pl.playlists().list().execute.return_value = {
            "items": [{"id": "PL_OK", "snippet": {"title": "Hidden History of Ancient India", "defaultLanguage": "en"}, "status": {"privacyStatus": "public"}}]
        }
        mock_yt_pl.playlistItems().insert.side_effect = RuntimeError("playlist quota error")
        with patch.dict(
            os.environ,
            {
                "SUTRADHAR_OFFLINE_STUB": "0",
                "YOUTUBE_CLIENT_ID": "cid",
                "YOUTUBE_CLIENT_SECRET": "csec",
                "YOUTUBE_REFRESH_TOKEN": "rtok",
            },
        ), patch("googleapiclient.http.MediaFileUpload"):
            res_pl = publish_episode(self.tmp_dir, youtube_client=mock_yt_pl)
        self.assertEqual(res_pl["upload_status"], "FAILED")
        self.assertIn("Failed assigning video", res_pl["error_message"])

    def test_05_update_playlists_update_thumbnail_and_verify_only(self) -> None:
        ep_plan, hero_bytes = self._seed_v2_build_and_db()
        conn = db_manager.connect_db(self.tmp_dir / "episodes.db")
        try:
            with db_manager.immediate_transaction(conn) as cur:
                cur.execute("UPDATE series SET youtube_playlist_id = 'PL_EXIST_1' WHERE series_id = 1")
                cur.execute(
                    """
                    INSERT INTO episodes (
                        series_id, episode_number_in_series, global_episode_number, content_format,
                        youtube_title, summary, bespoke_asset_path, script_json, youtube_video_id,
                        thumbnail_asset_path, status
                    ) VALUES (1, 1, 3, 'episodic_series', ?, ?, 'canvas_prop:meru_route_scroll', '{}', 'ep3_live_id', 'build/thumbnail.jpg', 'PUBLISHED')
                    """,
                    (ep_plan["youtube_title"], ep_plan["summary"]),
                )
                ep_id = int(cur.lastrowid)
                cur.execute(
                    "INSERT INTO publishing_history (episode_id, action, youtube_video_id, playlist_id, status) VALUES (?, 'PUBLISHED', 'ep3_live_id', 'PL_EXIST_1', 'PUBLISHED')",
                    (ep_id,),
                )
        finally:
            conn.close()

        # 1. --update-playlists syncs mismatched title/language
        yt_pl = MagicMock()
        yt_pl.playlists().list().execute.return_value = {
            "items": [{"id": "PL_EXIST_1", "snippet": {"title": "Old Title", "defaultLanguage": None}, "status": {"privacyStatus": "private"}}]
        }
        up_res = update_playlists(self.tmp_dir, youtube_client=yt_pl)
        self.assertEqual(up_res["status"], "ok")
        yt_pl.playlists().update.assert_called_once()

        # 2. --update-thumbnail uploads thumbnail only and appends THUMBNAIL_UPDATED history
        yt_th = MagicMock()
        yt_th.videos().list().execute.return_value = {
            "items": [
                {
                    "id": "ep3_live_id",
                    "snippet": {
                        "thumbnails": {
                            "shortsAspectRatio": {"url": "https://i.ytimg.com/vi/ep3_live_id/sardefault.jpg", "width": 1080, "height": 1920}
                        }
                    },
                    "status": {"uploadStatus": "processed"},
                    "processingDetails": {"processingStatus": "succeeded", "thumbnailsAvailability": "available"},
                    "contentDetails": {"hasCustomThumbnail": True},
                }
            ]
        }
        yt_th.thumbnails().set().execute.return_value = {
            "items": [{"shortsAspectRatio": {"url": "https://i.ytimg.com/vi/ep3_live_id/sardefault.jpg"}}]
        }
        with patch("googleapiclient.http.MediaFileUpload"), patch(
            "thumbnail_utils.fetch_cdn_image", return_value=(200, hero_bytes)
        ), patch("time.sleep"):
            th_res = update_thumbnail_only(self.tmp_dir, video_id="ep3_live_id", youtube_client=yt_th)
        self.assertEqual(th_res["status"], "ok")
        yt_th.videos().insert.assert_not_called()

        conn = db_manager.connect_db(self.tmp_dir / "episodes.db")
        try:
            cnt = conn.execute("SELECT COUNT(*) FROM publishing_history WHERE action = 'THUMBNAIL_UPDATED'").fetchone()[0]
            self.assertEqual(cnt, 1)
        finally:
            conn.close()

        # 3. --verify-only performs zero writes and passes when live matches DB
        yt_ro = MagicMock()
        yt_ro.playlists().list().execute.return_value = {
            "items": [{"id": "PL_EXIST_1", "snippet": {"title": "Hidden History of Ancient India", "defaultLanguage": "en"}, "status": {"privacyStatus": "public"}}]
        }
        yt_ro.playlistItems().list().execute.return_value = {
            "items": [{"snippet": {"resourceId": {"videoId": "ep3_live_id"}}}]
        }
        yt_ro.videos().list().execute.return_value = {
            "items": [
                {
                    "id": "ep3_live_id",
                    "snippet": {
                        "title": ep_plan["youtube_title"],
                        "description": "English description",
                        "tags": ["Shorts", "Sutradhar"],
                        "defaultLanguage": "en",
                        "defaultAudioLanguage": "hi",
                        "thumbnails": {
                            "shortsAspectRatio": {"url": "https://i.ytimg.com/vi/ep3_live_id/sardefault.jpg", "width": 1080, "height": 1920}
                        },
                    },
                    "status": {"uploadStatus": "processed"},
                    "processingDetails": {"processingStatus": "succeeded"},
                    "contentDetails": {"hasCustomThumbnail": True},
                }
            ]
        }
        ro_res = verify_live_channel_state(self.tmp_dir, youtube_client=yt_ro, fetch_url_fn=lambda _u: (200, hero_bytes))
        self.assertEqual(ro_res["status"], "ok")
        self.assertTrue(ro_res["read_only"])
        yt_ro.videos().insert.assert_not_called()
        yt_ro.videos().update.assert_not_called()
        yt_ro.playlists().update.assert_not_called()
        yt_ro.thumbnails().set.assert_not_called()

        # 4. Expired/revoked OAuth refresh token surfaces clean PublishPipelineError
        yt_auth_fail = MagicMock()
        yt_auth_fail.playlists().list().execute.side_effect = RuntimeError("invalid_grant: Token has been expired or revoked.")
        with self.assertRaises(publish_youtube.PublishPipelineError) as ctx_auth:
            verify_live_channel_state(self.tmp_dir, youtube_client=yt_auth_fail)
        self.assertIn("invalid_grant", str(ctx_auth.exception))

    # ------------------------------------------------------------------
    # 4. Cross-Document, Manifest & Context Consistency Gate
    # ------------------------------------------------------------------

    def test_06_documentation_manifests_and_context_consistency(self) -> None:
        instructions = (REPO_ROOT / "docs" / "INSTRUCTIONS.md").read_text(encoding="utf-8")
        setup_ops = (REPO_ROOT / "docs" / "SETUP_AND_OPERATIONS.md").read_text(encoding="utf-8")
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        pkg = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
        reqs = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")

        # 16-Part spec structure & reasonable dense length
        instr_lines = instructions.splitlines()
        self.assertGreaterEqual(len(instr_lines), 180)
        self.assertLessEqual(len(instr_lines), 450)
        for sec in range(1, 17):
            self.assertRegex(instructions, rf"(?m)^## {sec}\.\s")

        # Zero legacy contradictions across rewritten docs
        for name, text in [("INSTRUCTIONS.md", instructions), ("SETUP_AND_OPERATIONS.md", setup_ops), ("README.md", readme)]:
            for forbidden in (
                "--auth-only",
                "800x1200",
                "480x960",
                "#38bdf8",
                "100% in Hindi",
                "65+ full Shorts",
                "7-Command",
                "7 static commands",
                "7 static CLI",
                "Zero burned-in captions",
                "zero captions",
                "8:1 ratio",
                "ratio: 8",
            ):
                self.assertNotIn(forbidden, text, f"Stale contradictory phrase '{forbidden}' found in {name}")

            # Unified production constants must align across all 3 docs
            self.assertIn("6.5", text, f"Missing unified 6.5 ducking ratio in {name}")
            self.assertIn("sardefault.jpg", text, f"Missing sardefault.jpg verification in {name}")
            self.assertIn("publish_youtube.py", text, f"Missing publish_youtube.py in {name}")

        # Key specs in INSTRUCTIONS.md aligned with config.yaml & code
        self.assertIn("<= 55 MiB", instructions)
        self.assertIn("<= 900", instructions)
        self.assertIn("760–840", instructions)
        self.assertIn("faster-whisper small", instructions)
        self.assertIn("rect.bottom <= 1395px", instructions)
        self.assertIn("88.0", instructions)
        self.assertIn("55.0", instructions)

        # package.json & requirements.txt hygiene
        self.assertEqual(pkg["dependencies"]["hyperframes"], "^0.9.70")
        self.assertIn("--strict", pkg["scripts"]["hf:check"])
        self.assertIn("--safe-zone shorts", pkg["scripts"]["hf:check"])
        self.assertIn("--json", pkg["scripts"]["hf:check"])

        self.assertNotIn("huggingface-hub", reqs)
        self.assertNotIn("google-auth-oauthlib", reqs)
        self.assertIn("google-auth-httplib2", reqs)
        self.assertIn("Jinja2", reqs)

        # db_manager --context aligns cleanly with config.yaml language & budget locks
        ctx = db_manager.cmd_context(REPO_ROOT, db_manager.load_config(REPO_ROOT))
        self.assertEqual(ctx["schema_version"], 4)
        self.assertEqual(ctx["language_policy"]["audio_language"], "hi")
        self.assertEqual(ctx["language_policy"]["metadata_language"], "en")
        self.assertEqual(ctx["monthly_tts_budget"]["monthly_limit"], 30000)
        self.assertEqual(ctx["monthly_tts_budget"]["max_billed_chars_per_episode"], 900)


if __name__ == "__main__":
    unittest.main()
