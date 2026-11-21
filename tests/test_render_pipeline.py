#!/usr/bin/env python3
"""Automated unit tests for scripts/preview_frames.py and scripts/render_and_qa.py (Milestone 5)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_DIR = REPO_ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import preview_frames  # noqa: E402
import render_and_qa  # noqa: E402


class TestRenderPipeline(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="sutradhar_render_test_")
        self.root = Path(self.tmp)
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))

    def test_01_cli_rejects_dynamic_arguments(self) -> None:
        for script in [REPO_ROOT / "scripts/preview_frames.py", REPO_ROOT / "scripts/render_and_qa.py"]:
            proc = subprocess.run(
                [sys.executable, str(script), "--unexpected-arg"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn("zero CLI arguments", proc.stderr)

    def test_02_parse_manifest_js(self) -> None:
        manifest_path = self.root / "manifest.js"
        payload = {"schema_version": "1.0", "series_id": 42, "scenes": [{"scene_index": 1}]}
        manifest_path.write_text(
            f"// Comment\nwindow.EPISODE_MANIFEST = {json.dumps(payload)};\n",
            encoding="utf-8",
        )
        parsed = preview_frames.parse_manifest_js(manifest_path)
        self.assertEqual(parsed["series_id"], 42)
        self.assertEqual(len(parsed["scenes"]), 1)

        # Missing manifest raises PreviewPipelineError
        with self.assertRaises(preview_frames.PreviewPipelineError):
            preview_frames.parse_manifest_js(self.root / "nonexistent.js")

    def test_03_stitch_contact_sheet_and_safe_zones(self) -> None:
        # Create 3 dummy images
        img_paths = []
        for i in range(3):
            p = self.root / f"frame_{i}.png"
            im = Image.new("RGB", (360, 640), color=(50 * (i + 1), 30, 80))
            im.save(p)
            img_paths.append(p)

        labels = ["Scene 1", "Scene 2", "Scene 3"]
        out_jpg = self.root / "test_grid.jpg"
        safe_zones = {"top_clear_px": 288, "bottom_clear_px": 520, "right_clear_px": 192, "left_clear_px": 48}

        # Regular sheet
        preview_frames.stitch_contact_sheet(
            image_paths=img_paths,
            scene_labels=labels,
            output_path=out_jpg,
            cols=3,
            thumb_w=180,
            thumb_h=320,
            overlay_safe_zones=False,
        )
        self.assertTrue(out_jpg.is_file())
        with Image.open(out_jpg) as result_im:
            self.assertEqual(result_im.size, (180 * 3, 320))

        # Safe-zone overlay sheet
        out_sz_jpg = self.root / "test_grid_sz.jpg"
        preview_frames.stitch_contact_sheet(
            image_paths=img_paths,
            scene_labels=labels,
            output_path=out_sz_jpg,
            cols=3,
            thumb_w=180,
            thumb_h=320,
            overlay_safe_zones=True,
            safe_zones=safe_zones,
        )
        self.assertTrue(out_sz_jpg.is_file())

    def test_04_probe_media_validation(self) -> None:
        # Create a tiny 1-second audio file using ffmpeg to test probe_media
        dummy_wav = self.root / "dummy.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "1", str(dummy_wav)],
            capture_output=True,
            check=True,
        )
        info = render_and_qa.probe_media(dummy_wav)
        self.assertIn("format", info)
        self.assertAlmostEqual(float(info["format"]["duration"]), 1.0, places=1)

    def test_05_thumbnail_generation(self) -> None:
        """Verify generate_episode_thumbnail produces 1080x1920 JPEG <= 2 MB."""
        dummy_mp4 = self.root / "dummy.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "testsrc=size=1080x1920:rate=30",
                "-t",
                "2",
                "-pix_fmt",
                "yuv420p",
                str(dummy_mp4),
            ],
            capture_output=True,
            check=True,
        )
        thumb_out = self.root / "thumbnail.jpg"
        manifest = {
            "scenes": [
                {"scene_index": 1, "shot_type": "wide_establishing", "midpoint_sec": 0.5},
                {"scene_index": 2, "shot_type": "close_up_wrath", "midpoint_sec": 1.2},
            ]
        }
        res_thumb = render_and_qa.generate_episode_thumbnail(dummy_mp4, thumb_out, manifest, 2.0)
        self.assertTrue(res_thumb.is_file())
        self.assertLessEqual(res_thumb.stat().st_size, 2 * 1024 * 1024)

        with Image.open(res_thumb) as im:
            self.assertEqual(im.size, (1080, 1920))
            self.assertEqual(im.format, "JPEG")

    def test_06_multi_shot_composition_generation(self) -> None:
        """Verify generate_root_composition dynamically builds manifest-driven compositions for new cast."""
        import generate_composition

        build_dir = self.root / "build"
        build_dir.mkdir(parents=True, exist_ok=True)
        manifest_p = build_dir / "manifest.js"

        test_manifest = {
            "schema_version": "2.0",
            "language": "en",
            "audio": {"total_duration_sec": 12.0, "total_frames": 360},
            "scenes": [
                {
                    "scene_index": 1,
                    "shot_type": "curtain_establishing",
                    "backdrop_rig": "celestial_cosmos_court",
                    "start_sec": 0.0,
                    "end_sec": 4.0,
                },
                {
                    "scene_index": 2,
                    "shot_type": "character_medium",
                    "backdrop_rig": "ancient_nalanda_courtyard",
                    "primary_character": "ancient_scholar",
                    "start_sec": 4.0,
                    "end_sec": 8.0,
                },
                {
                    "scene_index": 3,
                    "shot_type": "two_character_confrontation",
                    "backdrop_rig": "forest_ashram_twilight",
                    "primary_character": "shani_dev",
                    "secondary_character": "narad_muni",
                    "start_sec": 8.0,
                    "end_sec": 12.0,
                },
            ],
        }
        manifest_p.write_text(f"window.EPISODE_MANIFEST = {json.dumps(test_manifest)};\n", encoding="utf-8")

        # Copy assets/ into self.root
        shutil.copytree(REPO_ROOT / "assets", self.root / "assets")
        shutil.copy(REPO_ROOT / "config.yaml", self.root / "config.yaml")

        res = generate_composition.generate_root_composition(self.root)
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["scenes_count"], 3)
        self.assertIn("ancient_scholar", res["characters"])
        self.assertIn("shani_dev", res["characters"])
        self.assertIn("narad_muni", res["characters"])

        index_text = (self.root / "index.html").read_text(encoding="utf-8")
        self.assertIn("shot_1_container", index_text)
        self.assertIn("shot_2_container", index_text)
        self.assertIn("shot_3_container", index_text)
        self.assertIn("celestial_cosmos_court", index_text)
        self.assertIn("ancient_nalanda_courtyard", index_text)
        self.assertIn("forest_ashram_twilight", index_text)

    def test_07_audio_mixing_resampling_and_synth_fallback(self) -> None:
        """Verify audio mixing pipeline handles resampling, fade-out, and procedural fallback."""
        build_dir = self.root / "build"
        build_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO_ROOT / "config.yaml", self.root / "config.yaml")
        (self.root / "assets" / "bgm").mkdir(parents=True, exist_ok=True)
        (self.root / "assets" / "sfx").mkdir(parents=True, exist_ok=True)

        raw_vid = build_dir / "raw_video.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=1080x1920:rate=30", "-t", "2", "-pix_fmt", "yuv420p", str(raw_vid)],
            capture_output=True,
            check=True,
        )

        narr_wav = build_dir / "narration.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=24000", "-t", "2", str(narr_wav)],
            capture_output=True,
            check=True,
        )

        manifest = {
            "bgm_track": "nonexistent_bgm_track.mp3",
            "audio": {
                "narration_full_path": "build/narration.wav",
                "total_duration_sec": 2.0,
            },
            "scenes": [
                {"scene_index": 1, "start_sec": 0.0, "end_sec": 2.0}
            ],
        }

        cfg = render_and_qa.load_config(self.root)
        out_vid = build_dir / "final_short.mp4"

        # Should execute with procedural synth fallback without crashing
        render_and_qa.build_audio_mix(
            root=self.root,
            manifest=manifest,
            cfg=cfg,
            raw_video_path=raw_vid,
            output_video_path=out_vid,
        )
        self.assertTrue(out_vid.is_file())
        info = render_and_qa.probe_media(out_vid)
        self.assertIn("format", info)


if __name__ == "__main__":
    unittest.main()
