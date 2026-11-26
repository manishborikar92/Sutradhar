#!/usr/bin/env python3
"""Unit tests for scripts/thumbnail_utils.py validation, processing wait, and CDN comparison."""

from __future__ import annotations

import io
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import thumbnail_utils


def _encode_image(size: tuple[int, int], *, variant: str = "hero", fmt: str = "JPEG") -> bytes:
    im = Image.new("RGB", size, (16, 22, 59) if variant == "hero" else (180, 190, 200))
    if variant != "blank":
        draw = ImageDraw.Draw(im)
        w, h = size
        if variant == "hero":
            draw.rectangle([90, 255, w - 90, 650], fill=(246, 196, 83))
            draw.ellipse([w // 2 - 210, 820, w // 2 + 210, 1240], fill=(255, 247, 226))
        else:
            draw.rectangle([0, 0, w, h // 2], fill=(20, 80, 75))
            draw.polygon([(100, 1400), (980, 1400), (540, 400)], fill=(190, 60, 70))
    buf = io.BytesIO()
    im.save(buf, format=fmt, quality=92)
    return buf.getvalue()


class TestThumbnailUtils(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="sutradhar_thumb_test_"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_validate_local_thumbnail_accepts_valid_9_16_jpeg(self) -> None:
        p = self.tmp_dir / "valid_thumb.jpg"
        p.write_bytes(_encode_image((1080, 1920), variant="hero"))
        info = thumbnail_utils.validate_local_thumbnail(p)
        self.assertEqual((info["width"], info["height"]), (1080, 1920))
        self.assertEqual(info["format"], "JPEG")
        self.assertGreater(info["mean_stddev"], 4.0)

    def test_validate_local_thumbnail_rejects_corrupt_wrong_dims_blank_and_oversized(self) -> None:
        corrupt = self.tmp_dir / "corrupt.jpg"
        corrupt.write_bytes(b"\xFF\xD8\xFF\x00corrupt")
        with self.assertRaises(thumbnail_utils.ThumbnailValidationError):
            thumbnail_utils.validate_local_thumbnail(corrupt)

        landscape = self.tmp_dir / "landscape.jpg"
        landscape.write_bytes(_encode_image((1280, 720), variant="hero"))
        with self.assertRaises(thumbnail_utils.ThumbnailValidationError):
            thumbnail_utils.validate_local_thumbnail(landscape)

        blank = self.tmp_dir / "blank.jpg"
        blank.write_bytes(_encode_image((1080, 1920), variant="blank"))
        with self.assertRaises(thumbnail_utils.ThumbnailValidationError):
            thumbnail_utils.validate_local_thumbnail(blank)

        huge = self.tmp_dir / "huge.jpg"
        huge.write_bytes(b"\xFF\xD8\xFF" + b"0" * (2 * 1024 * 1024 + 50))
        with self.assertRaises(thumbnail_utils.ThumbnailValidationError):
            thumbnail_utils.validate_local_thumbnail(huge)

    def test_upload_waits_for_processing_and_verifies_cdn_parity(self) -> None:
        thumb_path = self.tmp_dir / "thumbnail.jpg"
        hero_bytes = _encode_image((1080, 1920), variant="hero")
        thumb_path.write_bytes(hero_bytes)

        call_order: list[str] = []
        poll_responses = [
            {
                "items": [
                    {
                        "status": {"uploadStatus": "uploaded"},
                        "processingDetails": {"processingStatus": "processing"},
                        "contentDetails": {"duration": "P0D"},
                    }
                ]
            },
            {
                "items": [
                    {
                        "status": {"uploadStatus": "processed"},
                        "processingDetails": {
                            "processingStatus": "succeeded",
                            "thumbnailsAvailability": "available",
                        },
                        "contentDetails": {"duration": "PT1M4S", "hasCustomThumbnail": True},
                        "snippet": {
                            "thumbnails": {
                                "maxres": {"url": "https://i.ytimg.com/vi/vid123/maxresdefault.jpg"},
                                "shortsAspectRatio": {
                                    "url": "https://i.ytimg.com/vi/vid123/sardefault.jpg",
                                    "width": 1080,
                                    "height": 1920,
                                },
                            }
                        },
                    }
                ]
            },
        ]
        # Reuse processed response for post-set read-back
        poll_responses.append(poll_responses[-1])

        def fake_vid_list_exec():
            call_order.append("videos.list")
            return poll_responses.pop(0) if len(poll_responses) > 1 else poll_responses[0]

        def fake_thumb_set_exec():
            call_order.append("thumbnails.set")
            return {
                "items": [
                    {
                        "maxres": {"url": "https://i.ytimg.com/vi/vid123/maxresdefault.jpg"},
                        "shortsAspectRatio": {
                            "url": "https://i.ytimg.com/vi/vid123/sardefault.jpg",
                            "width": 1080,
                            "height": 1920,
                        },
                    }
                ]
            }

        yt = MagicMock()
        yt.videos().list().execute.side_effect = fake_vid_list_exec
        yt.thumbnails().set().execute.side_effect = fake_thumb_set_exec

        res = thumbnail_utils.upload_thumbnail_and_verify(
            yt,
            "vid123",
            thumb_path,
            is_short=True,
            expected_build_dir=self.tmp_dir,
            media_upload_cls=MagicMock(),
            fetch_url_fn=lambda _u: (200, hero_bytes),
            sleep_fn=lambda _s: None,
        )
        self.assertTrue(res["verified"])
        self.assertTrue(res["match"])
        # Must poll processing at least twice BEFORE invoking thumbnails.set
        self.assertEqual(call_order[:3], ["videos.list", "videos.list", "thumbnails.set"])

    def test_upload_fails_if_shorts_aspect_ratio_missing_or_cdn_404(self) -> None:
        thumb_path = self.tmp_dir / "thumbnail.jpg"
        hero_bytes = _encode_image((1080, 1920), variant="hero")
        thumb_path.write_bytes(hero_bytes)

        yt = MagicMock()
        yt.videos().list().execute.return_value = {
            "items": [
                {
                    "status": {"uploadStatus": "processed"},
                    "processingDetails": {"processingStatus": "succeeded", "thumbnailsAvailability": "available"},
                    "contentDetails": {"hasCustomThumbnail": True},
                    "snippet": {"thumbnails": {"maxres": {"url": "https://i.ytimg.com/vi/v1/maxresdefault.jpg"}}},
                }
            ]
        }
        yt.thumbnails().set().execute.return_value = {
            "items": [{"maxres": {"url": "https://i.ytimg.com/vi/v1/maxresdefault.jpg"}}]
        }

        with self.assertRaises(thumbnail_utils.ThumbnailVerificationError) as ctx:
            thumbnail_utils.upload_thumbnail_and_verify(
                yt,
                "v1",
                thumb_path,
                is_short=True,
                media_upload_cls=MagicMock(),
                fetch_url_fn=lambda _u: (200, hero_bytes),
                sleep_fn=lambda _s: None,
            )
        self.assertIn("shortsAspectRatio", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
