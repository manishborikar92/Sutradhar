"""Unit tests for Phase 3 Dynamic Mythological Storytelling Props System.

Verifies:
1. Canonical prop catalog registry (6 core mythological props).
2. Boundary-checked Golden Action Zone layout solver.
3. SVG markup loading from disk for all props.
4. Deterministic GSAP 3 animation code generation for each animation type.
5. Error handling on unknown prop IDs and invalid configurations.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.engine.config import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    PROP_COSMIC_EYE_BEAMS,
    PROP_FIRE_BRAZIER,
    PROP_PLANETARY_STAIRCASE,
    PROP_SUBJUGATION_BOOT,
    PROP_THOUGHT_BUBBLE_CHEST_VS_BACK,
    PROP_THOUGHT_BUBBLE_INFANT,
    PROP_VEDIC_KUNDALI,
)
from scripts.engine.prop_manager import (
    PROP_CATALOG,
    PropDefinition,
    PropError,
    generate_gsap_prop_animation,
    get_prop_definition,
    load_prop_svg,
    solve_prop_layout,
)


class TestPropCatalog:
    """Verifies that all 6 required mythological props are registered."""

    @pytest.mark.parametrize(
        "prop_id",
        [
            PROP_VEDIC_KUNDALI,
            PROP_PLANETARY_STAIRCASE,
            PROP_SUBJUGATION_BOOT,
            PROP_THOUGHT_BUBBLE_INFANT,
            PROP_THOUGHT_BUBBLE_CHEST_VS_BACK,
            PROP_COSMIC_EYE_BEAMS,
            PROP_FIRE_BRAZIER,
        ],
    )
    def test_canonical_props_exist(self, prop_id: str):
        prop_def = get_prop_definition(prop_id)
        assert isinstance(prop_def, PropDefinition)
        assert prop_def.prop_id == prop_id
        assert prop_def.base_width > 0
        assert prop_def.base_height > 0
        assert 0.1 <= prop_def.default_scale <= 2.0
        assert prop_def.layer_z_index >= 10
        assert prop_def.svg_filename.endswith(".svg")
        assert len(prop_def.description) > 0

    def test_unknown_prop_raises_error(self):
        with pytest.raises(PropError, match="Unknown prop identifier"):
            get_prop_definition("modern_flowchart_diagram")


class TestPropLayoutSolver:
    """Verifies Golden Zone placement and canvas boundary clamping."""

    def test_default_layout_for_kundali(self):
        style, x, y, sc = solve_prop_layout(PROP_VEDIC_KUNDALI)
        assert "position: absolute;" in style
        assert "z-index: 25;" in style
        assert "pointer-events: none;" in style
        assert x == 540
        assert y == 860
        assert sc == 0.85

    def test_boundary_clamping_left_and_right(self):
        # Extreme left
        style_l, _, _, _ = solve_prop_layout(PROP_VEDIC_KUNDALI, anchor_x=-500)
        assert "left: 20px;" in style_l

        # Extreme right
        style_r, _, _, _ = solve_prop_layout(PROP_VEDIC_KUNDALI, anchor_x=3000)
        assert "left: 618px;" in style_r  # 1080 - (520 * 0.85) - 20 = 1080 - 442 - 20 = 618px

    def test_boundary_clamping_top_and_bottom(self):
        # Extreme top
        style_t, _, _, _ = solve_prop_layout(PROP_VEDIC_KUNDALI, anchor_y=-200)
        assert "top: 100px;" in style_t

        # Extreme bottom
        style_b, _, _, _ = solve_prop_layout(PROP_VEDIC_KUNDALI, anchor_y=5000)
        assert "top: 1378px;" in style_b  # 1920 - 442 - 100 = 1378px


class TestPropSvgMarkup:
    """Verifies that all SVG files exist and contain appropriate theatrical elements."""

    @pytest.mark.parametrize("prop_id", list(PROP_CATALOG.keys()))
    def test_load_prop_svg_disk(self, prop_id: str):
        props_dir = REPO_ROOT / "assets" / "svg" / "props"
        svg = load_prop_svg(props_dir, prop_id)
        assert "<svg" in svg
        assert "</svg>" in svg
        assert 'xmlns="http://www.w3.org/2000/svg"' in svg

    def test_kundali_quadrants_exist(self):
        props_dir = REPO_ROOT / "assets" / "svg" / "props"
        svg = load_prop_svg(props_dir, PROP_VEDIC_KUNDALI)
        assert 'id="kundali_quad_top"' in svg
        assert 'id="kundali_quad_right"' in svg
        assert 'id="kundali_quad_bottom"' in svg
        assert 'id="kundali_quad_left"' in svg
        assert 'id="infinity_glyph"' in svg

    def test_boot_crush_shockwaves_exist(self):
        props_dir = REPO_ROOT / "assets" / "svg" / "props"
        svg = load_prop_svg(props_dir, PROP_SUBJUGATION_BOOT)
        assert 'id="crush_shockwaves"' in svg

    def test_fire_brazier_flames_exist(self):
        props_dir = REPO_ROOT / "assets" / "svg" / "props"
        svg = load_prop_svg(props_dir, PROP_FIRE_BRAZIER)
        assert 'id="flame_outer"' in svg
        assert 'id="brazier_bowl"' in svg


class TestPropGsapAnimations:
    """Verifies GSAP animation snippet generation for each prop type."""

    def test_kundali_shatter_animation(self):
        code = generate_gsap_prop_animation("p_kundali", PROP_VEDIC_KUNDALI, start_sec=2.0, duration_sec=4.0)
        assert "masterTl.to(pEl, { opacity: 1" in code
        assert "kundali_quad_top" in code
        assert "kundali_quad_right" in code
        assert "masterTl.to(pEl, { opacity: 0" in code

    def test_boot_stomp_animation(self):
        code = generate_gsap_prop_animation("p_boot", PROP_SUBJUGATION_BOOT, start_sec=5.0, duration_sec=3.0)
        assert "masterTl.fromTo(pEl, { y: -120 }" in code
        assert "crush_shockwaves" in code

    def test_staircase_climb_animation(self):
        code = generate_gsap_prop_animation("p_stairs", PROP_PLANETARY_STAIRCASE, start_sec=1.0, duration_sec=5.0)
        assert ".stair-step" in code
        assert "brightness(1.4)" in code

    def test_bubble_float_animation(self):
        code = generate_gsap_prop_animation("p_bubble", PROP_THOUGHT_BUBBLE_INFANT, start_sec=0.0, duration_sec=3.0)
        assert 'y: "-=18"' in code
        assert 'yoyo: true' in code

    def test_eye_beam_clash_animation(self):
        code = generate_gsap_prop_animation("p_beam", PROP_COSMIC_EYE_BEAMS, start_sec=2.5, duration_sec=3.5)
        assert "#gaze_beam_energy" in code
        assert "#clash_midpoint" in code

    def test_brazier_flicker_animation(self):
        code = generate_gsap_prop_animation("p_fire", PROP_FIRE_BRAZIER, start_sec=0.5, duration_sec=4.0)
        assert "#flame_outer" in code
        assert "scaleY: 1.12" in code
