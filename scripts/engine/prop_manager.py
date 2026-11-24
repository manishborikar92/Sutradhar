"""Sutradhar Video Engine — Dynamic Storytelling Props System (v4.0).

Replaces obsolete static vector diagrams with narrative-driven physicalized props:
1. Vedic Kundali: 12-house diamond mandala with 9 planetary nodes, capable of fracturing.
2. Planetary Staircase: 9 stacked planetary deities forming steps for royal ascent.
3. Subjugation Boot: Giant imperial conqueror boot representing oppression with crushing shockwaves.
4. Thought Bubbles: Cloud-framed visual metaphors (Infant Meghnada, Chest vs. Back drishti).
5. Cosmic Eye Beams: Clashing divine third eyes and high-energy radiating gaze beams.
6. Fire Braziers: Temple/court havan kund with animated layered flames and embers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Optional

from .config import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    GOLDEN_ZONE_X_MAX,
    GOLDEN_ZONE_X_MIN,
    GOLDEN_ZONE_Y_MAX,
    GOLDEN_ZONE_Y_MIN,
    PROP_COSMIC_EYE_BEAMS,
    PROP_FIRE_BRAZIER,
    PROP_PLANETARY_STAIRCASE,
    PROP_SUBJUGATION_BOOT,
    PROP_THOUGHT_BUBBLE_CHEST_VS_BACK,
    PROP_THOUGHT_BUBBLE_INFANT,
    PROP_VEDIC_KUNDALI,
)


class PropError(ValueError):
    """Raised when prop configuration or placement violates cinematographic invariants."""


@dataclass(frozen=True)
class PropDefinition:
    """Canonical specification of a storytelling prop."""

    prop_id: str
    name: str
    svg_filename: str
    base_width: int
    base_height: int
    default_anchor_x: int
    default_anchor_y: int
    default_scale: float
    layer_z_index: int
    animation_type: str
    description: str


PROP_CATALOG: Final[dict[str, PropDefinition]] = {
    PROP_VEDIC_KUNDALI: PropDefinition(
        prop_id=PROP_VEDIC_KUNDALI,
        name="Vedic Kundali Birth Chart",
        svg_filename="vedic_kundali.svg",
        base_width=520,
        base_height=520,
        default_anchor_x=540,
        default_anchor_y=860,
        default_scale=0.85,
        layer_z_index=25,
        animation_type="kundali_shatter",
        description="12-house Vedic birth chart mandala with 4-quadrant fracture capability.",
    ),
    PROP_PLANETARY_STAIRCASE: PropDefinition(
        prop_id=PROP_PLANETARY_STAIRCASE,
        name="Planetary Deity Staircase",
        svg_filename="planetary_staircase.svg",
        base_width=680,
        base_height=660,
        default_anchor_x=500,
        default_anchor_y=1380,
        default_scale=0.90,
        layer_z_index=20,
        animation_type="staircase_climb",
        description="9 stacked planetary deity steps for ascending narrative staging.",
    ),
    PROP_SUBJUGATION_BOOT: PropDefinition(
        prop_id=PROP_SUBJUGATION_BOOT,
        name="Subjugation Boot of Ravana",
        svg_filename="subjugation_boot.svg",
        base_width=440,
        base_height=440,
        default_anchor_x=520,
        default_anchor_y=1120,
        default_scale=0.95,
        layer_z_index=35,
        animation_type="boot_stomp",
        description="Giant ornate royal armor boot with crushing shockwave animation.",
    ),
    PROP_THOUGHT_BUBBLE_INFANT: PropDefinition(
        prop_id=PROP_THOUGHT_BUBBLE_INFANT,
        name="Thought Bubble — Infant Meghnada",
        svg_filename="thought_bubble_infant.svg",
        base_width=440,
        base_height=440,
        default_anchor_x=680,
        default_anchor_y=680,
        default_scale=0.80,
        layer_z_index=30,
        animation_type="bubble_float",
        description="Theatrical thought bubble showing infant Meghnada in divine cradle.",
    ),
    PROP_THOUGHT_BUBBLE_CHEST_VS_BACK: PropDefinition(
        prop_id=PROP_THOUGHT_BUBBLE_CHEST_VS_BACK,
        name="Thought Bubble — Chest vs Back Drishti",
        svg_filename="thought_bubble_chest_vs_back.svg",
        base_width=480,
        base_height=440,
        default_anchor_x=540,
        default_anchor_y=720,
        default_scale=0.85,
        layer_z_index=30,
        animation_type="medallion_pulse",
        description="Astrological visual metaphor: Front chest vs. bowed spine aspect.",
    ),
    PROP_COSMIC_EYE_BEAMS: PropDefinition(
        prop_id=PROP_COSMIC_EYE_BEAMS,
        name="Cosmic Eye Gaze Beams",
        svg_filename="cosmic_eye_beams.svg",
        base_width=540,
        base_height=720,
        default_anchor_x=540,
        default_anchor_y=880,
        default_scale=1.00,
        layer_z_index=28,
        animation_type="eye_beam_clash",
        description="Ravana and Shani Dev clashing third-eye laser gaze duel.",
    ),
    PROP_FIRE_BRAZIER: PropDefinition(
        prop_id=PROP_FIRE_BRAZIER,
        name="Theatrical Fire Brazier",
        svg_filename="fire_brazier.svg",
        base_width=320,
        base_height=480,
        default_anchor_x=220,
        default_anchor_y=1400,
        default_scale=0.85,
        layer_z_index=22,
        animation_type="brazier_flicker",
        description="Indian royal havan kund with multi-layer animated flames and embers.",
    ),
}


@dataclass
class PropInstance:
    """An instantiated prop ready for rendering into the Jinja2 template."""

    id: str
    prop_id: str
    svg: str
    style: str
    anchor_x: int
    anchor_y: int
    scale: float
    start_sec: float
    duration_sec: float
    animation_type: str


def get_prop_definition(prop_id: str) -> PropDefinition:
    """Retrieve canonical prop specification."""
    if prop_id in PROP_CATALOG:
        return PROP_CATALOG[prop_id]
    raise PropError(f"Unknown prop identifier '{prop_id}'. Available: {list(PROP_CATALOG.keys())}")


def solve_prop_layout(
    prop_id: str,
    anchor_x: Optional[int] = None,
    anchor_y: Optional[int] = None,
    scale: Optional[float] = None,
    z_index: Optional[int] = None,
) -> tuple[str, int, int, float]:
    """Calculate inline CSS and boundary-checked positioning for a prop."""
    prop_def = get_prop_definition(prop_id)

    x = anchor_x if anchor_x is not None else prop_def.default_anchor_x
    y = anchor_y if anchor_y is not None else prop_def.default_anchor_y
    sc = scale if scale is not None else prop_def.default_scale
    z = z_index if z_index is not None else prop_def.layer_z_index

    eff_w = int(prop_def.base_width * sc)
    eff_h = int(prop_def.base_height * sc)

    # Compute top-left placement centered on anchor_x, baseline on anchor_y
    left_px = x - (eff_w // 2)
    top_px = y - eff_h

    # Ensure within canvas boundaries
    left_px = max(20, min(CANVAS_WIDTH - eff_w - 20, left_px))
    top_px = max(100, min(CANVAS_HEIGHT - eff_h - 100, top_px))

    inline_style = (
        f"position: absolute; "
        f"left: {left_px}px; top: {top_px}px; "
        f"width: {eff_w}px; height: {eff_h}px; "
        f"z-index: {z}; pointer-events: none;"
    )
    return inline_style, x, y, sc


def load_prop_svg(props_dir: Path, prop_id: str) -> str:
    """Load SVG markup from disk."""
    prop_def = get_prop_definition(prop_id)
    svg_file = props_dir / prop_def.svg_filename
    if not svg_file.is_file():
        raise PropError(f"Prop SVG file not found at {svg_file}")
    return svg_file.read_text(encoding="utf-8")


def generate_gsap_prop_animation(
    prop_element_id: str,
    prop_id: str,
    start_sec: float,
    duration_sec: float,
    master_timeline_var: str = "masterTl",
) -> str:
    """Generate deterministic GSAP 3 animation code for a prop instance."""
    prop_def = get_prop_definition(prop_id)
    anim_type = prop_def.animation_type

    js_lines: list[str] = [
        f"  // Prop Animation: #{prop_element_id} ({prop_def.name}) at {start_sec:.2f}s - {start_sec + duration_sec:.2f}s",
        f"  (function() {{",
        f'    const pEl = document.getElementById("{prop_element_id}");',
        f"    if (!pEl) return;",
        f"    gsap.set(pEl, {{ opacity: 0 }});",
    ]

    # Fade in / Mount at start_sec
    js_lines.append(f'    {master_timeline_var}.to(pEl, {{ opacity: 1, duration: 0.35, ease: "power2.out" }}, {start_sec:.3f});')

    if anim_type == "kundali_shatter":
        # Fractures into 4 pieces at 60% of duration
        shatter_time = round(start_sec + duration_sec * 0.55, 3)
        js_lines.extend([
            f'    // Shatter Kundali Quadrants on impact',
            f'    {master_timeline_var}.call(() => {{',
            f'      const qTop = pEl.querySelector("#kundali_quad_top");',
            f'      const qRight = pEl.querySelector("#kundali_quad_right");',
            f'      const qBottom = pEl.querySelector("#kundali_quad_bottom");',
            f'      const qLeft = pEl.querySelector("#kundali_quad_left");',
            f'      if (qTop) gsap.to(qTop, {{ y: -80, rotation: -12, opacity: 0.3, duration: 0.6, ease: "power2.out" }});',
            f'      if (qRight) gsap.to(qRight, {{ x: 90, rotation: 15, opacity: 0.3, duration: 0.6, ease: "power2.out" }});',
            f'      if (qBottom) gsap.to(qBottom, {{ y: 80, rotation: 8, opacity: 0.3, duration: 0.6, ease: "power2.out" }});',
            f'      if (qLeft) gsap.to(qLeft, {{ x: -90, rotation: -18, opacity: 0.3, duration: 0.6, ease: "power2.out" }});',
            f'    }}, null, {shatter_time});',
        ])
    elif anim_type == "staircase_climb":
        # Sequential illumination of deity steps
        step_dt = round(duration_sec / 10.0, 3)
        for s_idx in range(1, 10):
            t_step = round(start_sec + s_idx * step_dt, 3)
            js_lines.append(
                f'    {master_timeline_var}.to(pEl.querySelectorAll(".stair-step")[{s_idx - 1}], {{ filter: "brightness(1.4)", duration: 0.2 }}, {t_step});'
            )
    elif anim_type == "boot_stomp":
        # Downward crush impact
        stomp_time = round(start_sec + 0.3, 3)
        js_lines.extend([
            f'    // Subjugation Boot Downward Stomp & Shockwave Expansion',
            f'    {master_timeline_var}.fromTo(pEl, {{ y: -120 }}, {{ y: 0, duration: 0.35, ease: "power3.in" }}, {start_sec:.3f});',
            f'    {master_timeline_var}.fromTo(pEl.querySelectorAll("#crush_shockwaves ellipse"), {{ scale: 0.2, opacity: 1 }}, {{ scale: 1.4, opacity: 0, duration: 0.5, stagger: 0.08, ease: "power2.out" }}, {stomp_time});',
        ])
    elif anim_type in ("bubble_float", "medallion_pulse"):
        # Gentle floating oscillation
        js_lines.extend([
            f'    // Thought Bubble Float Oscillation',
            f'    {master_timeline_var}.to(pEl, {{ y: "-=18", duration: {duration_sec / 2.0:.2f}, yoyo: true, repeat: 1, ease: "sine.inOut" }}, {start_sec:.3f});',
        ])
    elif anim_type == "eye_beam_clash":
        # Laser gaze pulse & midpoint clash spark
        spark_time = round(start_sec + 0.2, 3)
        js_lines.extend([
            f'    // Cosmic Eye Beam Clash Pulse',
            f'    {master_timeline_var}.fromTo(pEl.querySelector("#gaze_beam_energy"), {{ opacity: 0.3, scaleX: 0.6 }}, {{ opacity: 1, scaleX: 1.1, duration: 0.3, yoyo: true, repeat: 3, ease: "rough" }}, {spark_time});',
            f'    {master_timeline_var}.to(pEl.querySelector("#clash_midpoint"), {{ rotation: 360, duration: {duration_sec:.2f}, ease: "none" }}, {start_sec:.3f});',
        ])
    elif anim_type == "brazier_flicker":
        # Flame breathing loop
        js_lines.extend([
            f'    // Temple Brazier Flame Flicker',
            f'    {master_timeline_var}.to(pEl.querySelector("#flame_outer"), {{ scaleY: 1.12, duration: 0.25, yoyo: true, repeat: 7, ease: "sine.inOut", transformOrigin: "50% 100%" }}, {start_sec:.3f});',
        ])

    # Fade out at end
    fade_out_sec = round(start_sec + duration_sec, 3)
    js_lines.extend([
        f'    {master_timeline_var}.to(pEl, {{ opacity: 0, duration: 0.35, ease: "power2.in" }}, {fade_out_sec});',
        f"  }})();",
        "",
    ])
    return "\n".join(js_lines)
