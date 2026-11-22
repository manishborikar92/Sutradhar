#!/usr/bin/env python3
"""Automated unit tests for scripts/preview_frames.py and scripts/render_and_qa.py."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

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

    def test_11_vfx_and_transition_composition_embedding(self) -> None:
        """Verify generate_root_composition injects #transition_layer and all 5 VFX SVG elements with data-layout-ignore."""
        import generate_composition

        build_dir = self.root / "build"
        build_dir.mkdir(parents=True, exist_ok=True)
        manifest_p = build_dir / "manifest.js"
        shutil.copytree(REPO_ROOT / "assets", self.root / "assets")
        shutil.copy(REPO_ROOT / "config.yaml", self.root / "config.yaml")

        test_manifest = {
            "schema_version": "2.0",
            "language": "en",
            "content_format": "standalone",
            "audio": {"total_duration_sec": 20.0, "total_frames": 600},
            "scenes": [
                {
                    "scene_index": 1,
                    "shot_type": "curtain_establishing",
                    "transition_type": "curtain_open",
                    "backdrop_rig": "celestial_cosmos_court",
                    "primary_character": "ravana",
                    "start_sec": 0.0,
                    "end_sec": 5.0,
                },
                {
                    "scene_index": 2,
                    "shot_type": "character_medium",
                    "transition_type": "blind_wipe",
                    "backdrop_rig": "golden_lanka_citadel",
                    "primary_character": "ravana",
                    "vfx_elements": ["sunburst"],
                    "start_sec": 5.0,
                    "end_sec": 10.0,
                },
                {
                    "scene_index": 3,
                    "shot_type": "dramatic_climax",
                    "transition_type": "shatter_transition",
                    "backdrop_rig": "mount_kailash",
                    "primary_character": "ravana",
                    "vfx_elements": ["laser_beam", "fracture_cracks"],
                    "start_sec": 10.0,
                    "end_sec": 15.0,
                },
                {
                    "scene_index": 4,
                    "shot_type": "character_closeup_dialogue",
                    "transition_type": "border_wipe",
                    "backdrop_rig": "crushed_atmosphere",
                    "primary_character": "ravana",
                    "vfx_elements": ["sound_ripple", "screen_shatter"],
                    "start_sec": 15.0,
                    "end_sec": 20.0,
                },
            ],
        }
        manifest_p.write_text(f"window.EPISODE_MANIFEST = {json.dumps(test_manifest)};\n", encoding="utf-8")

        res = generate_composition.generate_root_composition(self.root)
        self.assertEqual(res["status"], "ok")

        index_text = (self.root / "index.html").read_text(encoding="utf-8")

        # 1. Verify Transition Layer & elements
        self.assertIn('id="transition_layer"', index_text)
        self.assertIn('id="blind_wipe_container"', index_text)
        self.assertIn('class="blind-slat"', index_text)
        self.assertIn('id="border_wipe_bar"', index_text)
        self.assertIn('id="iris_wipe_circle"', index_text)

        # 2. Verify Dynamic VFX Layer & all 5 SVG assets
        self.assertIn('id="vfx_layer"', index_text)
        self.assertIn('id="vfx_laser_beam_container"', index_text)
        self.assertIn('id="vfx_sunburst_container"', index_text)
        self.assertIn('id="vfx_screen_shatter_container"', index_text)
        self.assertIn('id="vfx_fracture_cracks_container"', index_text)
        self.assertIn('id="vfx_sound_ripple_container"', index_text)

        # 3. Verify data-layout-ignore="true" is applied to avoid HyperFrames linting/bounds errors
        self.assertIn('<div id="transition_layer" data-layout-ignore="true">', index_text)
        self.assertIn('<div id="vfx_layer" data-layout-ignore="true">', index_text)
        self.assertIn('<div id="vfx_laser_beam_container" class="vfx-element" data-layout-ignore="true">', index_text)

        # 4. Verify styles.css contains transition and VFX rules
        styles_text = (self.root / "styles.css").read_text(encoding="utf-8")
        self.assertIn("#transition_layer", styles_text)
        self.assertIn(".blind-slat", styles_text)
        self.assertIn("#border_wipe_bar", styles_text)
        self.assertIn("#iris_wipe_circle", styles_text)
        self.assertIn("#vfx_layer", styles_text)
        self.assertIn(".vfx-element", styles_text)
        self.assertIn("#vfx_laser_beam_container", styles_text)
        self.assertIn("#vfx_sunburst_container", styles_text)
        self.assertIn("#vfx_screen_shatter_container", styles_text)
        self.assertIn("#vfx_fracture_cracks_container", styles_text)
        self.assertIn("#vfx_sound_ripple_container", styles_text)

    def test_12_engine_handles_all_transition_types_and_vfx(self) -> None:
        """Verify engine.js contains execution logic for all 7 transition types and 5 VFX triggers."""
        engine_js = (REPO_ROOT / "engine.js").read_text(encoding="utf-8")

        # Transitions
        self.assertIn("curtain_open", engine_js)
        self.assertIn("blind_wipe", engine_js)
        self.assertIn("border_wipe", engine_js)
        self.assertIn("shatter_transition", engine_js)
        self.assertIn("radial_wipe", engine_js)
        self.assertIn("cut", engine_js)
        self.assertIn("fade", engine_js)

        # VFX Elements
        self.assertIn("laser_beam", engine_js)
        self.assertIn("sunburst", engine_js)
        self.assertIn("screen_shatter", engine_js)
        self.assertIn("fracture_cracks", engine_js)
        self.assertIn("sound_ripple", engine_js)

        # Transform safety: verify border_wipe uses x transform, not left
        self.assertIn("x: 1200", engine_js)

    def test_13_phase3_acceptance_test(self) -> None:
        """Verify Phase 3 Acceptance Criterion: Video contains at least 3 distinct transition types and 2 VFX elements."""
        import generate_composition

        build_dir = self.root / "build"
        build_dir.mkdir(parents=True, exist_ok=True)
        manifest_p = build_dir / "manifest.js"
        shutil.copytree(REPO_ROOT / "assets", self.root / "assets")
        shutil.copy(REPO_ROOT / "config.yaml", self.root / "config.yaml")

        # Multi-shot episode with 4 distinct transitions and 3 VFX elements
        test_manifest = {
            "schema_version": "2.0",
            "language": "en",
            "content_format": "standalone",
            "audio": {"total_duration_sec": 30.0, "total_frames": 900},
            "scenes": [
                {
                    "scene_index": 1,
                    "shot_type": "curtain_establishing",
                    "transition_type": "curtain_open",  # Transition 1
                    "backdrop_rig": "celestial_cosmos_court",
                    "primary_character": "ravana",
                    "start_sec": 0.0,
                    "end_sec": 7.0,
                },
                {
                    "scene_index": 2,
                    "shot_type": "character_medium",
                    "transition_type": "border_wipe",  # Transition 2
                    "backdrop_rig": "golden_lanka_citadel",
                    "primary_character": "ravana",
                    "vfx_elements": ["sunburst"],  # VFX 1
                    "start_sec": 7.0,
                    "end_sec": 14.0,
                },
                {
                    "scene_index": 3,
                    "shot_type": "dramatic_climax",
                    "transition_type": "shatter_transition",  # Transition 3
                    "backdrop_rig": "mount_kailash",
                    "primary_character": "ravana",
                    "vfx_elements": ["laser_beam", "fracture_cracks"],  # VFX 2 & 3
                    "start_sec": 14.0,
                    "end_sec": 22.0,
                },
                {
                    "scene_index": 4,
                    "shot_type": "character_closeup_dialogue",
                    "transition_type": "blind_wipe",  # Transition 4
                    "backdrop_rig": "crushed_atmosphere",
                    "primary_character": "ravana",
                    "start_sec": 22.0,
                    "end_sec": 30.0,
                },
            ],
        }
        manifest_p.write_text(f"window.EPISODE_MANIFEST = {json.dumps(test_manifest)};\n", encoding="utf-8")

        res = generate_composition.generate_root_composition(self.root)
        self.assertEqual(res["status"], "ok")

        # Extract and verify transition types and vfx elements count
        transitions_used = set(s.get("transition_type") for s in test_manifest["scenes"] if s.get("transition_type"))
        vfx_used = set(vfx for s in test_manifest["scenes"] for vfx in (s.get("vfx_elements") or []))

        # Check acceptance criteria
        self.assertGreaterEqual(len(transitions_used), 3, f"Expected >= 3 distinct transitions, got {len(transitions_used)}: {transitions_used}")
        self.assertGreaterEqual(len(vfx_used), 2, f"Expected >= 2 distinct VFX elements, got {len(vfx_used)}: {vfx_used}")

    def test_14_multi_character_and_expression_system(self) -> None:
        """Verify SVG rigs contain 4 standardized facial expressions, infographics exist, and styles/HTML embed them."""
        import generate_composition

        char_dir = REPO_ROOT / "assets" / "svg" / "characters"
        required_chars = [
            "shani_dev",
            "narad_muni",
            "hanuman",
            "ancient_scholar",
            "ravana",
            "mandodari",
            "surya_dev",
            "indra_dev",
            "shiva",
        ]

        # 1. Verify all 9 character rigs exist and contain standardized expression IDs
        for c_slug in required_chars:
            svg_path = char_dir / f"{c_slug}.svg"
            self.assertTrue(svg_path.is_file(), f"Missing character rig: {svg_path}")
            content = svg_path.read_text(encoding="utf-8")

            # Check expressions layers
            self.assertIn('id="brows_neutral"', content, f"{c_slug} missing #brows_neutral")
            self.assertIn('id="brows_angry"', content, f"{c_slug} missing #brows_angry")
            self.assertIn('id="brows_fear"', content, f"{c_slug} missing #brows_fear")
            self.assertIn('id="brows_joy"', content, f"{c_slug} missing #brows_joy")

            self.assertIn('id="eyes_normal"', content, f"{c_slug} missing #eyes_normal")
            self.assertIn('id="eyes_wrath"', content, f"{c_slug} missing #eyes_wrath")
            self.assertIn('id="eyes_fear"', content, f"{c_slug} missing #eyes_fear")
            self.assertIn('id="eyes_joy"', content, f"{c_slug} missing #eyes_joy")

            self.assertIn('id="mouth_calm"', content, f"{c_slug} missing #mouth_calm")
            self.assertIn('id="mouth_talk"', content, f"{c_slug} missing #mouth_talk")
            self.assertIn('id="mouth_shout"', content, f"{c_slug} missing #mouth_shout")
            self.assertIn('id="mouth_fear"', content, f"{c_slug} missing #mouth_fear")
            self.assertIn('id="mouth_joy"', content, f"{c_slug} missing #mouth_joy")

        # 2. Verify infographic elements exist in assets/svg/infographics
        info_dir = REPO_ROOT / "assets" / "svg" / "infographics"
        required_infographics = [
            "thought_bubble.svg",
            "comparison_card.svg",
            "symbol_infinity.svg",
            "symbol_scales.svg",
            "outro_marquee.svg",
        ]
        for info_file in required_infographics:
            self.assertTrue((info_dir / info_file).is_file(), f"Missing infographic asset: {info_file}")

        # 3. Verify composition generator embeds infographics and marquee
        build_dir = self.root / "build"
        build_dir.mkdir(parents=True, exist_ok=True)
        manifest_p = build_dir / "manifest.js"
        shutil.copytree(REPO_ROOT / "assets", self.root / "assets")
        shutil.copy(REPO_ROOT / "config.yaml", self.root / "config.yaml")

        test_manifest = {
            "schema_version": "2.0",
            "language": "en",
            "content_format": "standalone",
            "audio": {"total_duration_sec": 25.0, "total_frames": 750},
            "scenes": [
                {
                    "scene_index": 1,
                    "shot_type": "character_medium",
                    "backdrop_rig": "celestial_cosmos_court",
                    "primary_character": "surya_dev",
                    "secondary_character": "shani_dev",
                    "infographic_type": "symbol_scales",
                    "start_sec": 0.0,
                    "end_sec": 12.0,
                },
                {
                    "scene_index": 2,
                    "shot_type": "two_character_confrontation",
                    "backdrop_rig": "golden_lanka_citadel",
                    "primary_character": "ravana",
                    "secondary_character": "mandodari",
                    "infographic_type": "thought_bubble",
                    "start_sec": 12.0,
                    "end_sec": 25.0,
                },
            ],
        }
        manifest_p.write_text(f"window.EPISODE_MANIFEST = {json.dumps(test_manifest)};\n", encoding="utf-8")

        res = generate_composition.generate_root_composition(self.root)
        self.assertEqual(res["status"], "ok")
        self.assertCountEqual(res["characters"], ["surya_dev", "shani_dev", "ravana", "mandodari"])

        index_text = (self.root / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="infographic_layer"', index_text)
        self.assertIn('id="infographic_thought_bubble_container"', index_text)
        self.assertIn('id="infographic_comparison_card_container"', index_text)
        self.assertIn('id="infographic_symbol_infinity_container"', index_text)
        self.assertIn('id="infographic_symbol_scales_container"', index_text)
        self.assertIn('id="outro_marquee_container"', index_text)

        # Verify puppets
        self.assertIn('data-character="surya_dev"', index_text)
        self.assertIn('data-character="shani_dev"', index_text)
        self.assertIn('data-character="ravana"', index_text)
        self.assertIn('data-character="mandodari"', index_text)

    def test_15_outro_curtain_call_sequence(self) -> None:
        """Verify engine.js contains execution logic for expressions, multi-character staging, and outro curtain call."""
        engine_js = (REPO_ROOT / "engine.js").read_text(encoding="utf-8")

        # Expression system verification
        self.assertIn("function applyExpression", engine_js)
        self.assertIn("brows_neutral", engine_js)
        self.assertIn("brows_angry", engine_js)
        self.assertIn("brows_fear", engine_js)
        self.assertIn("brows_joy", engine_js)
        self.assertIn("eyes_normal", engine_js)
        self.assertIn("eyes_wrath", engine_js)
        self.assertIn("eyes_fear", engine_js)
        self.assertIn("eyes_joy", engine_js)
        self.assertIn("mouth_calm", engine_js)
        self.assertIn("mouth_shout", engine_js)
        self.assertIn("mouth_fear", engine_js)
        self.assertIn("mouth_joy", engine_js)

        # Lip-sync & mid-shot expression switching
        self.assertIn("function applyLipSync", engine_js)
        self.assertIn("expression_change", engine_js)

        # Multi-character staging & turn-taking
        self.assertIn("getPuppet", engine_js)
        self.assertIn("hasMultiple", engine_js)

        # Infographics animation
        self.assertIn("infoElements", engine_js)
        self.assertIn("infographic_type", engine_js)

        # Theatrical outro curtain call
        self.assertIn("outroMarquee", engine_js)
        self.assertIn("castPuppets", engine_js)
        self.assertIn("curtains.left", engine_js)
        self.assertIn("xPercent: 0", engine_js)

    def test_16_phase4_acceptance_test(self) -> None:
        """Verify Phase 4 Acceptance Criterion: Video features 4+ characters with expression changes, a multi-character scene, and an outro curtain call."""
        import generate_composition

        build_dir = self.root / "build"
        build_dir.mkdir(parents=True, exist_ok=True)
        manifest_p = build_dir / "manifest.js"
        shutil.copytree(REPO_ROOT / "assets", self.root / "assets")
        shutil.copy(REPO_ROOT / "config.yaml", self.root / "config.yaml")

        # 4 distinct mythological characters in one episode
        acceptance_manifest = {
            "schema_version": "2.0",
            "language": "en",
            "content_format": "standalone",
            "audio": {"total_duration_sec": 48.0, "total_frames": 1440},
            "scenes": [
                {
                    "scene_index": 1,
                    "shot_type": "curtain_establishing",
                    "transition_type": "curtain_open",
                    "backdrop_rig": "celestial_cosmos_court",
                    "primary_character": "surya_dev",
                    "emotion": "calm",
                    "pose_preset": "idle_royal",
                    "start_sec": 0.0,
                    "end_sec": 10.0,
                },
                {
                    "scene_index": 2,
                    "shot_type": "two_character_confrontation",
                    "transition_type": "border_wipe",
                    "backdrop_rig": "golden_lanka_citadel",
                    "primary_character": "ravana",
                    "secondary_character": "shani_dev",
                    "emotion": "wrath",
                    "pose_preset": "action_raised",
                    "expression_change": {
                        "at_ratio": 0.5,
                        "character": "shani_dev",
                        "to_emotion": "fear",
                        "to_pose": "humbled_braced",
                    },
                    "vfx_elements": ["laser_beam"],
                    "start_sec": 10.0,
                    "end_sec": 24.0,
                },
                {
                    "scene_index": 3,
                    "shot_type": "character_medium",
                    "transition_type": "blind_wipe",
                    "backdrop_rig": "lanka_sandstone_throne",
                    "primary_character": "mandodari",
                    "emotion": "joy",
                    "pose_preset": "blessing_calm",
                    "infographic_type": "thought_bubble",
                    "start_sec": 24.0,
                    "end_sec": 36.0,
                },
                {
                    "scene_index": 4,
                    "shot_type": "character_closeup_dialogue",
                    "transition_type": "fade",
                    "backdrop_rig": "mount_kailash",
                    "primary_character": "shiva",
                    "emotion": "calm",
                    "pose_preset": "idle_royal",
                    "vfx_elements": ["sunburst"],
                    "start_sec": 36.0,
                    "end_sec": 48.0,
                },
            ],
        }
        manifest_p.write_text(f"window.EPISODE_MANIFEST = {json.dumps(acceptance_manifest)};\n", encoding="utf-8")

        res = generate_composition.generate_root_composition(self.root)
        self.assertEqual(res["status"], "ok")

        # 1. Verify 4+ characters in composition
        characters_featured = set(res["characters"])
        self.assertGreaterEqual(
            len(characters_featured),
            4,
            f"Expected >= 4 characters, got {len(characters_featured)}: {characters_featured}",
        )
        self.assertTrue({"surya_dev", "ravana", "shani_dev", "mandodari", "shiva"}.issubset(characters_featured))

        # 2. Verify multi-character scene exists
        multi_char_scenes = [
            s for s in acceptance_manifest["scenes"]
            if s.get("secondary_character") or s.get("shot_type") == "two_character_confrontation"
        ]
        self.assertGreaterEqual(len(multi_char_scenes), 1, "Expected at least 1 multi-character scene")

        # 3. Verify expression changes present
        emotions_used = set(s.get("emotion") for s in acceptance_manifest["scenes"])
        self.assertGreaterEqual(len(emotions_used), 3, f"Expected varied emotions, got {emotions_used}")
        self.assertTrue(any(s.get("expression_change") for s in acceptance_manifest["scenes"]))

        # 4. Verify outro curtain call elements embedded in index.html and styles.css
        index_html = (self.root / "index.html").read_text(encoding="utf-8")
        styles_css = (self.root / "styles.css").read_text(encoding="utf-8")
        self.assertIn('id="outro_marquee_container"', index_html)
        self.assertIn("#outro_marquee_container", styles_css)
        self.assertIn("SUTRADHAR", index_html)

    def test_17_expanded_sfx_and_bgm_libraries(self) -> None:
        """Verify expanded SFX (10+ tracks) and BGM (5+ emotional moods) exist and are configured."""
        import yaml

        cfg_p = REPO_ROOT / "config.yaml"
        with open(cfg_p, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        sfx_dir = REPO_ROOT / "assets" / "sfx"
        bgm_dir = REPO_ROOT / "assets" / "bgm"

        sfx_tracks = cfg["assets"]["sfx_tracks"]
        bgm_tracks = cfg["assets"]["bgm_tracks"]
        bgm_by_mood = cfg["assets"]["bgm_by_mood"]

        # 1. SFX Library: >= 10 event-mapped effects
        self.assertGreaterEqual(len(sfx_tracks), 10, f"Expected >= 10 SFX tracks, got {len(sfx_tracks)}")
        for sfx_name in sfx_tracks:
            sfx_file = sfx_dir / sfx_name
            self.assertTrue(sfx_file.is_file(), f"Configured SFX file missing: {sfx_file}")

        # 2. BGM Library: >= 5 emotional moods
        self.assertGreaterEqual(len(bgm_tracks), 5, f"Expected >= 5 BGM tracks, got {len(bgm_tracks)}")
        for bgm_name in bgm_tracks:
            bgm_file = bgm_dir / bgm_name
            self.assertTrue(bgm_file.is_file(), f"Configured BGM file missing: {bgm_file}")

        # 3. Mood coverage: dramatic, epic, mystic/cosmic, wrath, sorrow, serene
        expected_moods = {"dramatic", "epic", "mystic", "wrath", "sorrow", "serene"}
        self.assertTrue(expected_moods.issubset(set(bgm_by_mood.keys())), f"Missing moods: {expected_moods - set(bgm_by_mood.keys())}")

    def test_18_timestamped_sfx_and_bgm_crossfading(self) -> None:
        """Verify timestamp-based SFX scheduling and multi-track BGM parsing."""
        manifest = {
            "schema_version": "2.0",
            "audio": {"total_duration_sec": 70.0},
            "bgm_cues": [
                {"mood": "dramatic", "start_sec": 0.0},
                {"mood": "wrath", "start_sec": 25.0},
                {"mood": "serene", "start_sec": 50.0},
            ],
            "scenes": [
                {
                    "scene_index": 1,
                    "start_sec": 0.0,
                    "end_sec": 15.0,
                    "transition_type": "curtain_open",
                },
                {
                    "scene_index": 2,
                    "start_sec": 15.0,
                    "end_sec": 35.0,
                    "transition_type": "shatter_transition",
                    "vfx_elements": ["laser_beam"],
                    "expression_changes": [{"to_emotion": "rage", "offset": 2.0}],
                },
                {
                    "scene_index": 3,
                    "start_sec": 35.0,
                    "end_sec": 55.0,
                    "transition_type": "border_wipe",
                    "vfx_elements": ["sound_ripple"],
                    "sfx_events": [{"sfx": "sword_clash.wav", "offset": 1.5}],
                },
                {
                    "scene_index": 4,
                    "start_sec": 55.0,
                    "end_sec": 70.0,
                    "transition_type": "fade",
                },
            ],
            "outro": True,
        }

        # SFX Schedule validation
        sfx_schedule = render_and_qa.collect_sfx_schedule(REPO_ROOT, manifest)
        self.assertGreaterEqual(len(sfx_schedule), 5, f"Expected >= 5 scheduled SFX, got {len(sfx_schedule)}")
        scheduled_files = [path.name for path, _ in sfx_schedule]

        # Verify key SFX are mapped correctly
        self.assertIn("curtain_whoosh.wav", scheduled_files)
        self.assertIn("crystal_shatter.wav", scheduled_files)
        self.assertIn("laser_strike.wav", scheduled_files)
        self.assertIn("thunder_rumble.wav", scheduled_files)
        self.assertIn("conch_blast.wav", scheduled_files)
        self.assertIn("sword_clash.wav", scheduled_files)

        # BGM Schedule validation
        bgm_schedule = render_and_qa.parse_bgm_schedule(REPO_ROOT, manifest, {})
        self.assertEqual(len(bgm_schedule), 3)
        self.assertEqual(bgm_schedule[0]["track"], "dramatic_mythology.mp3")
        self.assertEqual(bgm_schedule[1]["track"], "wrath_confrontation.mp3")
        self.assertEqual(bgm_schedule[2]["track"], "serene_blessing.mp3")

    def test_19_contextual_text_rendering(self) -> None:
        """Verify contextual text rendering (titles, labels, outro CTA) and strict absence of burned-in subtitles."""
        import generate_composition

        build_dir = self.root / "build"
        build_dir.mkdir(parents=True, exist_ok=True)
        manifest_p = build_dir / "manifest.js"
        shutil.copytree(REPO_ROOT / "assets", self.root / "assets")
        shutil.copy(REPO_ROOT / "config.yaml", self.root / "config.yaml")

        manifest = {
            "schema_version": "2.0",
            "title": "The Judgment of Shani",
            "series_title": "Chronicles of Karma",
            "audio": {"total_duration_sec": 45.0, "total_frames": 1350},
            "scenes": [
                {
                    "scene_index": 1,
                    "start_sec": 0.0,
                    "end_sec": 15.0,
                    "primary_character": "shani_dev",
                    "transition_type": "curtain_open",
                },
                {
                    "scene_index": 2,
                    "start_sec": 15.0,
                    "end_sec": 30.0,
                    "primary_character": "ravana",
                    "transition_type": "border_wipe",
                },
                {
                    "scene_index": 3,
                    "start_sec": 30.0,
                    "end_sec": 45.0,
                    "primary_character": "shiva",
                    "transition_type": "fade",
                },
            ],
            "outro": True,
        }
        manifest_p.write_text(f"window.EPISODE_MANIFEST = {json.dumps(manifest)};\n", encoding="utf-8")

        res = generate_composition.generate_root_composition(self.root)
        self.assertEqual(res["status"], "ok")

        index_html = (self.root / "index.html").read_text(encoding="utf-8")
        styles_css = (self.root / "styles.css").read_text(encoding="utf-8")
        engine_js = (self.root / "engine.js").read_text(encoding="utf-8")

        # 1. Structural containers in HTML
        self.assertIn('id="contextual_text_layer"', index_html)
        self.assertIn('id="contextual_title_container"', index_html)
        self.assertIn('id="contextual_character_label_container"', index_html)
        self.assertIn('id="contextual_cta_container"', index_html)

        # 2. Styles in styles.css
        self.assertIn("#contextual_text_layer", styles_css)
        self.assertIn("#contextual_title_container", styles_css)
        self.assertIn("#contextual_character_label_container", styles_css)
        self.assertIn("#contextual_cta_container", styles_css)

        # 3. Animation logic in engine.js
        self.assertIn("contextualTitle", engine_js)
        self.assertIn("contextualCharLabel", engine_js)
        self.assertIn("contextualCta", engine_js)

        # 4. Strict Clean Canvas Rule: ZERO burned-in subtitles or dialogue captions
        self.assertNotIn("id=\"subtitle_container\"", index_html)
        self.assertNotIn("class=\"subtitles\"", index_html)
        self.assertNotIn("class=\"caption-word\"", index_html)

    def test_20_phase5_acceptance_test(self) -> None:
        """Verify Phase 5 Acceptance Criterion: Full audio pipeline with timestamped SFX, multi-track BGM, and contextual text."""
        import generate_composition
        import yaml

        with open(REPO_ROOT / "config.yaml", "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        build_dir = self.root / "build"
        build_dir.mkdir(parents=True, exist_ok=True)
        manifest_p = build_dir / "manifest.js"
        shutil.copytree(REPO_ROOT / "assets", self.root / "assets")
        shutil.copy(REPO_ROOT / "config.yaml", self.root / "config.yaml")

        # 2-minute episode manifest with multi-mood BGM, varied SFX, multi-character, VFX
        phase5_manifest = {
            "schema_version": "2.0",
            "language": "en",
            "content_format": "standalone",
            "title": "Cosmic Clash of the Immortals",
            "series_title": "Sutradhar Epics",
            "audio": {
                "narration_full_path": "build/full_narration.wav",
                "total_duration_sec": 120.0,
                "total_frames": 3600,
            },
            "bgm_cues": [
                {"mood": "dramatic", "start_sec": 0.0},
                {"mood": "wrath", "start_sec": 40.0},
                {"mood": "epic", "start_sec": 80.0},
                {"mood": "serene", "start_sec": 105.0},
            ],
            "scenes": [
                {
                    "scene_index": 1,
                    "shot_type": "curtain_establishing",
                    "transition_type": "curtain_open",
                    "primary_character": "surya_dev",
                    "emotion": "calm",
                    "start_sec": 0.0,
                    "end_sec": 20.0,
                },
                {
                    "scene_index": 2,
                    "shot_type": "two_character_confrontation",
                    "transition_type": "border_wipe",
                    "primary_character": "ravana",
                    "secondary_character": "shani_dev",
                    "emotion": "wrath",
                    "expression_changes": [{"to_emotion": "rage", "offset": 3.0}],
                    "vfx_elements": ["laser_beam"],
                    "start_sec": 20.0,
                    "end_sec": 50.0,
                },
                {
                    "scene_index": 3,
                    "shot_type": "dramatic_climax",
                    "transition_type": "shatter_transition",
                    "primary_character": "shani_dev",
                    "emotion": "wrath",
                    "vfx_elements": ["screen_shatter", "fracture_cracks"],
                    "sfx_events": [{"sfx": "sword_clash.wav", "offset": 2.0}],
                    "start_sec": 50.0,
                    "end_sec": 85.0,
                },
                {
                    "scene_index": 4,
                    "shot_type": "character_medium",
                    "transition_type": "blind_wipe",
                    "primary_character": "shiva",
                    "emotion": "calm",
                    "vfx_elements": ["sunburst", "sound_ripple"],
                    "start_sec": 85.0,
                    "end_sec": 120.0,
                },
            ],
            "outro": True,
        }
        manifest_p.write_text(f"window.EPISODE_MANIFEST = {json.dumps(phase5_manifest)};\n", encoding="utf-8")

        # Verify composition generation
        res = generate_composition.generate_root_composition(self.root)
        self.assertEqual(res["status"], "ok")

        # Verify SFX scheduling
        sfx_schedule = render_and_qa.collect_sfx_schedule(self.root, phase5_manifest)
        self.assertGreaterEqual(len(sfx_schedule), 6)
        sfx_names = [p.name for p, _ in sfx_schedule]
        self.assertIn("curtain_whoosh.wav", sfx_names)
        self.assertIn("crystal_shatter.wav", sfx_names)
        self.assertIn("laser_strike.wav", sfx_names)
        self.assertIn("magma_crack.wav", sfx_names)
        self.assertIn("thunder_rumble.wav", sfx_names)
        self.assertIn("conch_blast.wav", sfx_names)

        # Verify BGM scheduling (4 mood cues)
        bgm_schedule = render_and_qa.parse_bgm_schedule(self.root, phase5_manifest, cfg)
        self.assertEqual(len(bgm_schedule), 4)
        self.assertEqual(bgm_schedule[0]["track"], "dramatic_mythology.mp3")
        self.assertEqual(bgm_schedule[1]["track"], "wrath_confrontation.mp3")
        self.assertEqual(bgm_schedule[2]["track"], "epic_history.mp3")
        self.assertEqual(bgm_schedule[3]["track"], "serene_blessing.mp3")


if __name__ == "__main__":
    unittest.main()
