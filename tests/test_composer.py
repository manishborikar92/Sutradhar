"""Unit & integration test suite for Sutradhar Jinja2 Composer (v4.0).

Verifies:
1. Clean Jinja2 template rendering from templates/composition/ -> build/composition/.
2. Elimination of repo root code pollution (index.html/styles.css/engine.js never in repo root).
3. Standardized puppet dimensions (480x960px) and transform-origin: 50% 100%.
4. Proscenium arch and stage floor ellipse HTML/CSS structure.
5. Integration of ContinuousLifeEngine and Akshara lip-sync drivers.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.engine.composer import compose_episode, generate_composition
from scripts.engine.config import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    PUPPET_BASE_HEIGHT,
    PUPPET_BASE_WIDTH,
    PUPPET_TRANSFORM_ORIGIN,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestJinja2Composer(unittest.TestCase):
    """Tests modular composition rendering and artifact isolation."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.out_dir = Path(self.temp_dir.name) / "composition"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_zero_root_pollution(self) -> None:
        # Verify that generating composition does NOT write to repo root
        res = compose_episode(REPO_ROOT, output_dir=self.out_dir)
        self.assertEqual(res["status"], "ok")

        # Root files must NOT exist
        self.assertFalse((REPO_ROOT / "index.html").is_file(), "index.html must not exist in repo root!")
        self.assertFalse((REPO_ROOT / "styles.css").is_file(), "styles.css must not exist in repo root!")
        self.assertFalse((REPO_ROOT / "engine.js").is_file(), "engine.js must not exist in repo root!")

        # Files must exist inside target output dir
        self.assertTrue((self.out_dir / "index.html").is_file())
        self.assertTrue((self.out_dir / "styles.css").is_file())
        self.assertTrue((self.out_dir / "engine.js").is_file())

    def test_generated_html_structure(self) -> None:
        res = compose_episode(REPO_ROOT, output_dir=self.out_dir)
        html = (self.out_dir / "index.html").read_text(encoding="utf-8")

        # Proscenium Arch
        self.assertIn('id="proscenium_stage"', html)
        self.assertIn('class="stage-floor-shadow"', html)
        self.assertIn('class="proscenium-valance"', html)
        self.assertIn('class="proscenium-pillar pillar-left"', html)
        self.assertIn('class="proscenium-pillar pillar-right"', html)

        # Layers
        self.assertIn('id="backdrops_layer"', html)
        self.assertIn('id="characters_layer"', html)
        self.assertIn('id="subtitle_container"', html)

        # Standardized Puppet Wrapper
        self.assertIn('class="puppet-wrapper puppet-char"', html)
        self.assertIn(f"width: {PUPPET_BASE_WIDTH}px", html)
        self.assertIn(f"height: {PUPPET_BASE_HEIGHT}px", html)
        self.assertIn(f"transform-origin: {PUPPET_TRANSFORM_ORIGIN}", html)

    def test_generated_styles_css(self) -> None:
        compose_episode(REPO_ROOT, output_dir=self.out_dir)
        css = (self.out_dir / "styles.css").read_text(encoding="utf-8")

        # Puppet dimensions & transform-origin in CSS
        self.assertIn(".puppet-wrapper {", css)
        self.assertIn(f"width: {PUPPET_BASE_WIDTH}px;", css)
        self.assertIn(f"height: {PUPPET_BASE_HEIGHT}px;", css)
        self.assertIn(f"transform-origin: {PUPPET_TRANSFORM_ORIGIN};", css)

        # Proscenium styling
        self.assertIn(".stage-floor-shadow", css)
        self.assertIn(".proscenium-valance", css)
        self.assertIn(".proscenium-pillar", css)

    def test_generated_engine_js_contains_life_and_lipsync(self) -> None:
        compose_episode(REPO_ROOT, output_dir=self.out_dir)
        js = (self.out_dir / "engine.js").read_text(encoding="utf-8")

        # ContinuousLifeEngine
        self.assertIn("ContinuousLifeEngine", js)
        self.assertIn("Diaphragmatic Breathing", js)
        self.assertIn("Autonomous Blinking", js)
        self.assertIn("Eye Micro-Saccades", js)
        self.assertIn("Idle Weight Shift", js)

        # Akshara Lip-Sync
        self.assertIn("Akshara Lip-Sync Driver", js)
        self.assertIn("mouth_calm", js)
        self.assertIn("mouth_talk", js)
        self.assertIn("mouth_shout", js)

        # HyperFrames readiness
        self.assertIn("window.__hf_ready = true", js)


if __name__ == "__main__":
    unittest.main()
