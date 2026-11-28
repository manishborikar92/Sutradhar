#!/usr/bin/env python3
"""Contract & integration tests for Sutradhar v2 rendering, runtime ES modules, thumbnails & QA gates."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

import yaml
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_DIR = REPO_ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from sutradhar.config import load_config  # noqa: E402
from sutradhar.models import (  # noqa: E402
    CharacterPlacement,
    ContextualPill,
    EpisodePlanV2,
    PropPlacement,
    ScenePlan,
    SceneVisualSpec,
    StoryboardIR,
    ThumbnailSpec,
)
from sutradhar.qa.hyperframes_runner import stitch_contact_sheet  # noqa: E402
from sutradhar.qa.quality_gate import (  # noqa: E402
    QualityGateError,
    reject_synthetic_dom_snapshots,
    verify_per_scene_motion_and_grid,
)
from sutradhar.qa.render_optimizer import (  # noqa: E402
    DEFAULT_MAX_FILE_BYTES,
    RenderOptimizeError,
    probe_media,
    validate_mp4_contract,
)
from sutradhar.visual.storyboard_composer import (  # noqa: E402
    CompositionError,
    compose_storyboard,
    detect_v2_storyboard_run,
    load_asset_registry,
    parse_manifest_js,
    validate_storyboard_grounding,
)
from sutradhar.visual.thumbnail_builder import (  # noqa: E402
    SHORTS_2X3_CROP_BOX,
    THEME_COVER_CONFIGS,
    save_shorts_2x3_crop,
)


class TestRenderPipelineV2(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="sutradhar_render_v2_")
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
        payload = {"schema_version": "4.0", "series_id": 42, "scenes": [{"scene_index": 1}]}
        manifest_path.write_text(
            f"// Comment\nwindow.EPISODE_MANIFEST = {json.dumps(payload)};\n",
            encoding="utf-8",
        )
        parsed = parse_manifest_js(manifest_path)
        self.assertEqual(parsed["series_id"], 42)
        self.assertEqual(len(parsed["scenes"]), 1)

        with self.assertRaises(CompositionError):
            parse_manifest_js(self.root / "nonexistent.js")

    def test_03_stitch_contact_sheet_and_safe_zones(self) -> None:
        img_paths = []
        for i in range(3):
            p = self.root / f"frame_{i}.png"
            Image.new("RGB", (360, 640), color=(50 * (i + 1), 30, 80)).save(p)
            img_paths.append(p)

        labels = ["Scene 1", "Scene 2", "Scene 3"]
        out_jpg = self.root / "test_grid.jpg"
        safe_zones = {"top_clear_px": 288, "bottom_clear_px": 520, "right_clear_px": 192, "left_clear_px": 48}

        stitch_contact_sheet(
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

        out_sz_jpg = self.root / "test_grid_sz.jpg"
        stitch_contact_sheet(
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

    def test_04_probe_media_and_mp4_bitrate_contract(self) -> None:
        dummy_mp4 = self.root / "dummy.mp4"
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-f", "lavfi", "-i", "testsrc2=size=1080x1920:rate=30:duration=1.2",
                "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                "-t", "1.2",
                "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-ar", "48000", "-ac", "2",
                str(dummy_mp4),
            ],
            capture_output=True,
            check=True,
        )
        info = probe_media(dummy_mp4)
        self.assertIn("format", info)
        self.assertAlmostEqual(float(info["format"]["duration"]), 1.2, places=1)

        self.assertEqual(DEFAULT_MAX_FILE_BYTES, 57_671_680)  # 55 MiB ceiling
        metrics = validate_mp4_contract(dummy_mp4, max_file_bytes=DEFAULT_MAX_FILE_BYTES, require_audio=True)
        self.assertEqual((metrics["width"], metrics["height"]), (1080, 1920))
        self.assertEqual(metrics["sample_rate"], 48000)

        with self.assertRaises(RenderOptimizeError):
            validate_mp4_contract(dummy_mp4, max_file_bytes=1024)

    def test_05_runtime_es_modules_and_determinism_contract(self) -> None:
        """Verify canonical Canvas2D + DOM ES runtime modules exist and uphold seek determinism."""
        expected_modules = [
            "core/seek_runtime.js",
            "core/scene_director.js",
            "backdrops/atmosphere_v1.js",
            "backdrops/architectural_stage.js",
            "rigs/character_engine.js",
            "props/props_library.js",
            "fx/transitions.js",
            "captions/captions.html.jinja2",
            "index.html.jinja2",
            "styles.css",
        ]
        rt_dir = REPO_ROOT / "templates" / "runtime"
        for rel in expected_modules:
            p = rt_dir / rel
            self.assertTrue(p.is_file(), f"Missing canonical runtime module: {p}")
            content = p.read_text(encoding="utf-8")
            code_only = "\n".join(
                ln for ln in content.splitlines()
                if not ln.lstrip().startswith(("*", "//", "/*"))
            )
            self.assertNotIn("Math.random(", code_only, f"Unseeded Math.random() forbidden in {rel}")
            self.assertNotIn("delayedCall(", code_only, f"gsap.delayedCall forbidden in {rel}")
            self.assertNotIn("repeat: -1", code_only, f"Infinite repeat forbidden in {rel}")

        seek_js = (rt_dir / "core" / "seek_runtime.js").read_text(encoding="utf-8")
        self.assertIn("mulberry32", seek_js)
        self.assertIn("hf-seek", seek_js)
        self.assertIn("ease: \"none\"", seek_js)

        captions_tpl = (rt_dir / "captions" / "captions.html.jinja2").read_text(encoding="utf-8")
        self.assertIn("Noto Sans Devanagari", captions_tpl)
        self.assertIn("hf-seek", captions_tpl)
        self.assertIn("max-height: 148px", captions_tpl)

    def test_06_thumbnail_template_and_2x3_crop_contract(self) -> None:
        """Verify cover_template.html.jinja2 font weights <= 800, THEME_COVER_CONFIGS, and 2:3 crop."""
        tpl_path = REPO_ROOT / "templates" / "thumbnail" / "cover_template.html.jinja2"
        self.assertTrue(tpl_path.is_file())
        tpl_txt = tpl_path.read_text(encoding="utf-8")
        self.assertNotIn("font-weight: 900", tpl_txt)
        self.assertIn("Inter", tpl_txt)
        self.assertIn("Cinzel", tpl_txt)

        spec = ThumbnailSpec(
            pill="SAMUDRA MANTHAN",
            headline_line1="WHY SHIVA",
            headline_line2="DRANK POISON",
            sub_pill="ORIGIN OF NEELAKANTHA",
            font_weight=800,
            theme="kailash_horizon",
        )
        self.assertEqual(spec.font_weight, 800)
        self.assertIn("kailash_horizon", THEME_COVER_CONFIGS)
        self.assertIn("cosmic_ocean_manthan", THEME_COVER_CONFIGS)

        src_jpg = self.root / "thumb.jpg"
        crop_jpg = self.root / "thumb_2x3.jpg"
        Image.new("RGB", (1080, 1920), (16, 24, 58)).save(src_jpg, format="JPEG", quality=92)
        save_shorts_2x3_crop(src_jpg, crop_jpg)
        self.assertEqual(SHORTS_2X3_CROP_BOX, (0, 150, 1080, 1770))
        with Image.open(crop_jpg) as cropped:
            self.assertEqual(cropped.size, (1080, 1620))

    def test_07_storyboard_composer_grounding_and_registry(self) -> None:
        """Verify load_asset_registry + compose_storyboard compile isolated bundle cleanly."""
        reg = load_asset_registry(REPO_ROOT)
        self.assertGreaterEqual(len(reg["characters"]), 10)
        self.assertGreaterEqual(len(reg["environments"]), 8)
        self.assertGreaterEqual(len(reg["props"]), 15)

        wav_path = self.root / "narr.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=f=220:r=44100:d=5.0", str(wav_path)],
            check=True,
        )

        lines = [
            "[slowly] कैलाश पर्वत पर महादेव ध्यान में स्थित हैं।",
            "[calm] ब्रह्मलोक में समय का चक्र भिन्न गति से चलता है।",
            "[intense] सागर मंथन से भयानक हलाहल विष प्रकट हुआ।",
            "[solemn] शिव ने करुणा से वह विष कंठ में धारण किया।",
            "[gentle] इसी त्याग से महादेव नीलकंठ कहलाए।",
        ]
        scenes = []
        ir_scenes = []
        audio_scenes = []
        for idx, txt in enumerate(lines, start=1):
            vis = SceneVisualSpec(
                atmosphere_mode="dawn_epic",
                environment_preset="kailash_horizon",
                horizon_y=1142,
                camera_move="slow_push_in",
                transition_in="fade",
                bgm_mood="dramatic",
                props=[PropPlacement(id="trishul", kind="trishul", mount="floor", x=220.0)] if idx == 1 else [],
                characters=[CharacterPlacement(id="shiva", role="shiva", x=540.0, surface_type="floor", pose="palm_cup", expr="determined")],
                contextual_pill=ContextualPill(enabled=False),
            )
            ir_scenes.append(vis)
            scenes.append(
                ScenePlan(
                    scene_index=idx,
                    narration_text=txt,
                    visual_mode="character_drama",
                    backdrop_rig="kailash_horizon",
                    primary_character="shiva",
                    mood_palette="kailash_himalayan",
                    particle_theme="himalayan_snow",
                    camera_motion="slow_push",
                    visual_spec=vis,
                )
            )
            s0 = float(idx - 1)
            audio_scenes.append(
                {
                    "scene_index": idx,
                    "start_sec": s0,
                    "end_sec": s0 + 1.0,
                    "duration_sec": 1.0,
                    "speed": 0.92,
                    "narration_text": txt,
                    "words": [{"word": txt.split()[1], "start": 0.1, "end": 0.6, "global_start": s0 + 0.1, "global_end": s0 + 0.6}],
                }
            )

        plan = EpisodePlanV2(
            content_format="standalone",
            global_episode_number=1,
            pillar="Ancient Epics & Lore",
            tts_voice="uuyFQegRan8rpIQCGu9K",
            bgm_track="dramatic_mythology.mp3",
            bespoke_asset_path="canvas_prop:trishul",
            youtube_title="Why Shiva Is Called Neelakantha #Shorts",
            youtube_description="Authentic Shiva Purana story. #Shorts",
            youtube_tags=[f"tag{i}" for i in range(10)],
            summary="Shiva saves the universe by holding poison in his throat.",
            thumbnail_spec=ThumbnailSpec(pill="SHIVA LORE", headline_line1="THE BLUE", headline_line2="THROAT", font_weight=800),
            storyboard_ir=StoryboardIR(scenes=ir_scenes),
            scenes=scenes,
        )
        audio_manifest = {"total_duration_sec": 5.0, "audio": {"narration_full_path": str(wav_path)}, "scenes": audio_scenes}

        comp = compose_storyboard(
            REPO_ROOT,
            plan,
            audio_manifest=audio_manifest,
            output_dir=self.root / "comp",
            mix_audio=False,
        )
        self.assertTrue(comp.index_html.is_file())
        self.assertTrue((comp.output_dir / "lib" / "gsap.min.js").is_file())
        self.assertEqual(validate_storyboard_grounding(comp.grounding_report), [])

    def test_08_canonical_audio_catalog_zero_duplicates(self) -> None:
        """Verify canonical assets/audio/{bgm,sfx} and assets/manifest.yaml have zero duplicate BGM MD5s."""
        manifest = yaml.safe_load((REPO_ROOT / "assets" / "manifest.yaml").read_text(encoding="utf-8"))
        audio_cat = manifest["audio"]
        self.assertEqual(audio_cat["bgm_dir"], "assets/audio/bgm")
        self.assertEqual(audio_cat["sfx_dir"], "assets/audio/sfx")

        bgm_hashes: set[str] = set()
        for key, entry in audio_cat["bgm"].items():
            fpath = REPO_ROOT / entry["file"]
            self.assertTrue(fpath.is_file(), f"Missing canonical BGM {fpath}")
            md5 = hashlib.md5(fpath.read_bytes()).hexdigest()
            self.assertNotIn(md5, bgm_hashes, f"Duplicate BGM MD5 for {key}: {md5}")
            bgm_hashes.add(md5)

        cfg = load_config(REPO_ROOT)
        for sfx_name in cfg["assets"]["sfx_tracks"]:
            self.assertTrue((REPO_ROOT / "assets" / "audio" / "sfx" / sfx_name).is_file())

    def test_09_quality_gate_motion_and_fail_closed_guards(self) -> None:
        with self.assertRaises(QualityGateError):
            reject_synthetic_dom_snapshots({"dom_snapshots": [{"ok": True}]})

        mp4 = self.root / "motion.mp4"
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-f", "lavfi", "-i", "testsrc2=size=360x640:rate=30:duration=2.0",
                "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                str(mp4),
            ],
            check=True,
        )
        grid_jpg = self.root / "final_grid.jpg"
        res = verify_per_scene_motion_and_grid(mp4, 2.0, [(0.0, 1.0), (1.0, 2.0)], final_qa_grid_path=grid_jpg)
        self.assertTrue(grid_jpg.is_file())
        self.assertEqual(res["black_frames"], [])
        self.assertEqual(res["frozen_scenes"], [])


if __name__ == "__main__":
    unittest.main()
