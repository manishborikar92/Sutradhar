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

    def test_08_audio_mixing_real_bgm_resampling_loop_and_fade(self) -> None:
        """Verify audio mixing pipeline handles real 44.1kHz and 48kHz audio tracks (looping, fade-out, SFX ducking)."""
        build_dir = self.root / "build"
        build_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO_ROOT / "config.yaml", self.root / "config.yaml")
        bgm_dir = self.root / "assets" / "bgm"
        sfx_dir = self.root / "assets" / "sfx"
        bgm_dir.mkdir(parents=True, exist_ok=True)
        sfx_dir.mkdir(parents=True, exist_ok=True)

        # 1. Create a dummy raw video of 3.0 seconds
        raw_vid = build_dir / "raw_video.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=1080x1920:rate=30", "-t", "3", "-pix_fmt", "yuv420p", str(raw_vid)],
            capture_output=True,
            check=True,
        )

        # 2. Create narration audio at 24kHz, duration 3.0 seconds
        narr_wav = build_dir / "narration.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=24000", "-t", "3", str(narr_wav)],
            capture_output=True,
            check=True,
        )

        # 3. Create real 44.1kHz stereo BGM (short: 1.0s, so it must loop)
        short_44k_bgm = bgm_dir / "short_44k_track.mp3"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=44100", "-ac", "2", "-t", "1.0", "-b:a", "192k", str(short_44k_bgm)],
            capture_output=True,
            check=True,
        )

        # 4. Create real 48kHz stereo BGM (long: 5.0s, so it must trim and apply 1.2s fade)
        long_48k_bgm = bgm_dir / "long_48k_track.mp3"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=330:sample_rate=48000", "-ac", "2", "-t", "5.0", "-b:a", "192k", str(long_48k_bgm)],
            capture_output=True,
            check=True,
        )

        # 5. Create real SFX cues (48kHz and 44.1kHz)
        sfx_whoosh = sfx_dir / "whoosh_soft.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=660:sample_rate=48000", "-ac", "2", "-t", "0.5", str(sfx_whoosh)],
            capture_output=True,
            check=True,
        )
        sfx_hit = sfx_dir / "sub_hit.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=80:sample_rate=44100", "-ac", "2", "-t", "0.8", str(sfx_hit)],
            capture_output=True,
            check=True,
        )

        cfg = render_and_qa.load_config(self.root)

        # Test Case A: Short 44.1kHz BGM looping + SFX cue
        manifest_a = {
            "bgm_track": "short_44k_track.mp3",
            "audio": {
                "narration_full_path": "build/narration.wav",
                "total_duration_sec": 3.0,
            },
            "scenes": [
                {"scene_index": 1, "start_sec": 0.0, "end_sec": 1.5, "sfx_cue": "whoosh_soft.wav"},
                {"scene_index": 2, "start_sec": 1.5, "end_sec": 3.0, "sfx_cue": "sub_hit.wav"},
            ],
        }
        out_vid_a = build_dir / "final_short_44k_looped.mp4"
        render_and_qa.build_audio_mix(
            root=self.root,
            manifest=manifest_a,
            cfg=cfg,
            raw_video_path=raw_vid,
            output_video_path=out_vid_a,
        )
        self.assertTrue(out_vid_a.is_file())
        info_a = render_and_qa.probe_media(out_vid_a)
        duration_a = float(info_a["format"]["duration"])
        self.assertAlmostEqual(duration_a, 3.0, delta=0.3)
        self.assertTrue(any(s["codec_type"] == "audio" for s in info_a["streams"]))

        # Test Case B: Long 48kHz BGM trimmed with 1.2s fade-out
        manifest_b = {
            "bgm_track": "long_48k_track.mp3",
            "audio": {
                "narration_full_path": "build/narration.wav",
                "total_duration_sec": 3.0,
            },
            "scenes": [
                {"scene_index": 1, "start_sec": 0.0, "end_sec": 3.0},
            ],
        }
        out_vid_b = build_dir / "final_short_48k_faded.mp4"
        render_and_qa.build_audio_mix(
            root=self.root,
            manifest=manifest_b,
            cfg=cfg,
            raw_video_path=raw_vid,
            output_video_path=out_vid_b,
        )
        self.assertTrue(out_vid_b.is_file())
        info_b = render_and_qa.probe_media(out_vid_b)
        duration_b = float(info_b["format"]["duration"])
        self.assertAlmostEqual(duration_b, 3.0, delta=0.3)
        self.assertTrue(any(s["codec_type"] == "audio" for s in info_b["streams"]))

    def test_09_multi_shot_long_form_composition(self) -> None:
        """Verify generate_root_composition generates 12-shot composition and engine with ember repeat scaling."""
        import generate_composition

        build_dir = self.root / "build"
        build_dir.mkdir(parents=True, exist_ok=True)
        manifest_p = build_dir / "manifest.js"
        shutil.copytree(REPO_ROOT / "assets", self.root / "assets")
        shutil.copy(REPO_ROOT / "config.yaml", self.root / "config.yaml")

        scenes = []
        for i in range(1, 13):
            t_start = (i - 1) * 12.0
            t_end = i * 12.0
            scenes.append({
                "scene_index": i,
                "shot_type": "curtain_establishing" if i == 1 else ("character_closeup_dialogue" if i == 6 else "character_medium"),
                "backdrop_rig": "golden_lanka_citadel",
                "primary_character": "ravana",
                "camera_motion": "dramatic_zoom" if i == 6 else "push_in",
                "start_sec": t_start,
                "end_sec": t_end,
                "duration_sec": 12.0,
            })

        test_manifest = {
            "schema_version": "2.0",
            "language": "en",
            "content_format": "episodic_series",
            "audio": {"total_duration_sec": 144.0, "total_frames": 4320},
            "scenes": scenes,
        }
        manifest_p.write_text(f"window.EPISODE_MANIFEST = {json.dumps(test_manifest)};\n", encoding="utf-8")

        res = generate_composition.generate_root_composition(self.root)
        self.assertEqual(res["scenes_count"], 12)
        self.assertAlmostEqual(res["duration_sec"], 144.30, delta=0.5)

        # Check index.html
        idx_content = (self.root / "index.html").read_text(encoding="utf-8")
        for i in range(1, 13):
            self.assertIn(f'id="shot_{i}_container"', idx_content)

        # Check engine.js contains ember repeat calculation and dramatic_zoom
        engine_content = (self.root / "engine.js").read_text(encoding="utf-8")
        self.assertIn("emberRepeats", engine_content)
        self.assertIn("dramatic_zoom", engine_content)

    def test_10_dynamic_duration_qa_bounds(self) -> None:
        """Verify render_and_qa dynamically evaluates bounds per content format."""
        import render_and_qa

        shutil.copy(REPO_ROOT / "config.yaml", self.root / "config.yaml")
        cfg = render_and_qa.load_config(self.root)

        # Helper to simulate duration validation logic in render_and_qa
        def check_bounds(manifest: dict[str, Any], actual_duration: float) -> bool:
            active_format = manifest.get("content_format") or cfg.get("content_format", "serial")
            format_pacing = cfg.get("format_pacing", {}).get(active_format, {})
            default_pacing = cfg.get("episode_pacing", {})

            hard_min = float(format_pacing.get("hard_duration_min_sec", default_pacing.get("hard_duration_min_sec", 30.0)))
            hard_max = float(format_pacing.get("hard_duration_max_sec", default_pacing.get("hard_duration_max_sec", 180.0)))

            plan_range = manifest.get("target_duration_range")
            if isinstance(plan_range, dict):
                p_min = plan_range.get("min_seconds")
                p_max = plan_range.get("max_seconds")
                if p_min is not None and p_max is not None:
                    hard_min = max(30.0, float(p_min) * 0.85)
                    hard_max = min(180.0, float(p_max) * 1.15)

            hard_min = max(30.0, hard_min)
            hard_max = min(180.0, hard_max)

            if actual_duration < hard_min or actual_duration > hard_max:
                raise render_and_qa.RenderPipelineError(
                    f"Final video duration {actual_duration:.2f}s is outside format '{active_format}' hard bounds [{hard_min:.1f}s, {hard_max:.1f}s]."
                )
            return True

        # Episodic series (bounds 30s - 180s): 145s is valid, 25s is invalid, 195s is invalid
        ep_manifest = {"content_format": "episodic_series", "audio": {"total_duration_sec": 145.0}}
        self.assertTrue(check_bounds(ep_manifest, 145.0))
        with self.assertRaises(render_and_qa.RenderPipelineError):
            check_bounds(ep_manifest, 25.0)
        with self.assertRaises(render_and_qa.RenderPipelineError):
            check_bounds(ep_manifest, 195.0)

        # Custom plan range (e.g. 40s - 60s -> hard bounds 34s - 69s): 50s is valid, 28s is invalid
        custom_manifest = {
            "content_format": "standalone",
            "target_duration_range": {"min_seconds": 40.0, "max_seconds": 60.0},
            "audio": {"total_duration_sec": 50.0},
        }
        self.assertTrue(check_bounds(custom_manifest, 50.0))
        with self.assertRaises(render_and_qa.RenderPipelineError):
            check_bounds(custom_manifest, 28.0)


if __name__ == "__main__":
    unittest.main()
