#!/usr/bin/env python3
"""Sutradhar — Generalized Manifest-Driven Multi-Shot Composition Engine.

Generates root `index.html`, `styles.css`, and `engine.js` dynamically from
active `build/manifest.js` (or fallback manifest) and modular SVGs under `assets/svg/`.

Whitelisted zero-argument CLI invocation:
    python scripts/generate_composition.py

Can also be imported and called programmatically by preview_frames.py and render_and_qa.py:
    from generate_composition import generate_root_composition
    generate_root_composition(root)
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from db_manager import get_project_root, load_config  # noqa: E402


class CompositionError(RuntimeError):
    """Raised when composition generation or asset verification fails."""


FALLBACK_MANIFEST = {
    "schema_version": "2.0",
    "language": "en",
    "series_id": 1,
    "series_title": "Echoes of Kailash",
    "pillar": "Ancient Epics & Lore",
    "episode_number_in_series": 1,
    "total_planned_episodes": 3,
    "global_episode_number": 1,
    "youtube_title": "The Secret Geometry Beneath Mount Kailash (Part 1/3) #Shorts",
    "tts_voice": "bm_fable:0.55+am_fenrir:0.45",
    "bgm_track": "dramatic_mythology.mp3",
    "video": {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "safe_zones": {
            "top_clear_px": 288,
            "bottom_clear_px": 520,
            "left_clear_px": 48,
            "right_clear_px": 192,
        },
    },
    "audio": {
        "total_duration_sec": 41.50,
        "total_frames": 1245,
        "sample_rate": 24000,
        "narration_full_path": "build/audio/narration_full.wav",
    },
    "scenes": [
        {
            "scene_index": 1,
            "shot_type": "curtain_establishing",
            "backdrop_rig": "golden_lanka_citadel",
            "speaker_role": "narrator",
            "narration_text": "Beneath the golden spires of Lanka, ten crowned heads plotted what no mortal dared imagine.",
            "start_sec": 0.0,
            "end_sec": 7.42,
            "duration_sec": 7.42,
            "midpoint_sec": 3.71,
            "camera_motion": "push_in",
        },
        {
            "scene_index": 2,
            "shot_type": "character_medium",
            "backdrop_rig": "golden_lanka_citadel",
            "primary_character": "ravana",
            "speaker_role": "narrator",
            "narration_text": "King Ravana rose in fury, his ten heads burning with supreme defiance across the ancient earth.",
            "start_sec": 7.42,
            "end_sec": 14.85,
            "duration_sec": 7.43,
            "midpoint_sec": 11.14,
            "action_gesture": "raise_weapon",
            "pose_preset": "idle_royal",
            "camera_motion": "push_in",
        },
        {
            "scene_index": 3,
            "shot_type": "character_closeup_dialogue",
            "backdrop_rig": "golden_lanka_citadel",
            "primary_character": "ravana",
            "speaker_role": "character_dialogue",
            "narration_text": "Tremble Himalayas! Lanka's sovereign bows to no god!",
            "start_sec": 14.85,
            "end_sec": 21.20,
            "duration_sec": 6.35,
            "midpoint_sec": 18.02,
            "emotion": "wrath",
            "pose_preset": "wrath_dialogue",
            "camera_motion": "close_up",
        },
        {
            "scene_index": 4,
            "shot_type": "dramatic_climax",
            "backdrop_rig": "mount_kailash",
            "speaker_role": "narrator",
            "narration_text": "At Mount Kailash, Mahadev pressed a single toe upon the summit, splitting the bedrock beneath.",
            "start_sec": 21.20,
            "end_sec": 31.45,
            "duration_sec": 10.25,
            "midpoint_sec": 26.32,
            "camera_motion": "micro_shake",
        },
        {
            "scene_index": 5,
            "shot_type": "dramatic_climax",
            "backdrop_rig": "crushed_atmosphere",
            "primary_character": "ravana",
            "speaker_role": "narrator",
            "narration_text": "The mountain pressed down, trapping the sovereign until his arrogance dissolved into eternal hymns of praise.",
            "start_sec": 31.45,
            "end_sec": 41.50,
            "duration_sec": 10.05,
            "midpoint_sec": 36.48,
            "pose_preset": "humbled_braced",
            "camera_motion": "slow_pan",
        },
    ],
}


def load_manifest(build_dir: Path) -> dict[str, Any]:
    manifest_path = build_dir / "manifest.js"
    if manifest_path.is_file():
        content = manifest_path.read_text(encoding="utf-8")
        match = re.search(r"window\.EPISODE_MANIFEST\s*=\s*(\{.*?\});\s*$", content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
    return FALLBACK_MANIFEST


def generate_styles_css() -> str:
    return """/* Sutradhar v4.0 Master Theatrical Styles (Clean Canvas, Folk Art) */
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  width: 1080px;
  height: 1920px;
  background-color: #060814;
  overflow: hidden;
  position: relative;
  font-family: Georgia, serif;
}

#stage {
  width: 1080px;
  height: 1920px;
  position: absolute;
  top: 0;
  left: 0;
  overflow: hidden;
  transform-origin: 540px 960px;
}

/* Modular Shot Containers */
.shot-container {
  width: 1080px;
  height: 1920px;
  position: absolute;
  top: 0;
  left: 0;
  overflow: hidden;
  opacity: 0;
  display: none;
  transform-origin: 540px 960px;
}

.active-shot {
  display: block;
  opacity: 1;
}

/* Background SVGs */
.bg-svg {
  width: 1080px;
  height: 1920px;
  position: absolute;
  top: 0;
  left: 0;
}

/* Theatrical Velvet Curtains */
.curtain {
  position: absolute;
  top: 0;
  width: 550px;
  height: 1920px;
  background: linear-gradient(90deg, #1e0505 0%, #450a0a 30%, #7f1d1d 50%, #450a0a 75%, #0f0202 100%);
  box-shadow: 0 0 50px rgba(0,0,0,0.9);
  z-index: 100;
  overflow: hidden;
}

#curtain_left {
  left: 0;
  border-right: 4px solid #b45309;
}

#curtain_right {
  right: 0;
  border-left: 4px solid #b45309;
}

.curtain-fold {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 40px;
  background: linear-gradient(90deg, rgba(180,30,30,0.35), rgba(45,10,10,0.7));
}

/* Puppet Wrappers (Kathputli Articulated Rigs) */
.puppet-wrapper {
  position: absolute;
  top: 240px;
  left: 140px;
  width: 800px;
  height: 1200px;
  z-index: 40;
  transform-origin: 400px 700px;
  display: none;
  opacity: 0;
}

.puppet-wrapper svg {
  width: 100%;
  height: 100%;
  display: block;
}

/* Bespoke Diagram Wrapper */
.diagram-wrapper {
  position: absolute;
  top: 320px;
  left: 140px;
  width: 800px;
  height: 800px;
  z-index: 45;
  display: none;
  opacity: 0;
  transform-origin: 400px 400px;
}

/* Foreground Overlay Container */
.foreground-wrapper {
  position: absolute;
  top: -80px;
  left: 0;
  width: 1080px;
  height: 1920px;
  z-index: 60;
  pointer-events: none;
}

/* Floating Atmospheric Embers */
.ember {
  position: absolute;
  width: 6px;
  height: 6px;
  background: radial-gradient(circle, #fef08a 0%, #f59e0b 60%, transparent 100%);
  border-radius: 50%;
  pointer-events: none;
  z-index: 80;
  opacity: 0;
}

/* Screen Flashes */
#wrath_flash {
  position: absolute;
  top: 0;
  left: 0;
  width: 1080px;
  height: 1920px;
  background: radial-gradient(circle at 50% 40%, rgba(254, 240, 138, 0.65) 0%, rgba(234, 88, 12, 0.45) 50%, transparent 85%);
  z-index: 150;
  pointer-events: none;
  opacity: 0;
}

/* ========================================================================= */
/* THEATRICAL TRANSITIONS LAYER                                              */
/* ========================================================================= */
#transition_layer {
  position: absolute;
  top: 0;
  left: 0;
  width: 1080px;
  height: 1920px;
  pointer-events: none;
  z-index: 95;
  overflow: hidden;
}

#blind_wipe_container {
  position: absolute;
  top: 0;
  left: 0;
  width: 1080px;
  height: 1920px;
  display: none;
  pointer-events: none;
  z-index: 96;
}

.blind-slat {
  width: 1080px;
  height: 192px;
  background: linear-gradient(180deg, #180d05 0%, #291204 50%, #0f0602 100%);
  border-bottom: 2px solid #b45309;
  transform-origin: 50% 50%;
  transform: scaleY(0);
}

#border_wipe_bar {
  position: absolute;
  top: 0;
  left: 0;
  width: 90px;
  height: 1920px;
  background: linear-gradient(90deg, transparent 0%, rgba(180,83,9,0.8) 25%, #fef08a 50%, rgba(180,83,9,0.8) 75%, transparent 100%);
  box-shadow: 0 0 60px #f59e0b;
  display: none;
  pointer-events: none;
  z-index: 97;
  transform: translateX(-120px);
}

#iris_wipe_circle {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 120px;
  height: 120px;
  margin: -60px 0 0 -60px;
  border-radius: 50%;
  background: radial-gradient(circle, #fef08a 0%, #f59e0b 35%, #180d05 70%, #060814 100%);
  box-shadow: 0 0 80px #f59e0b;
  transform: scale(0);
  display: none;
  pointer-events: none;
  z-index: 96;
}

/* ========================================================================= */
/* DYNAMIC VFX LAYER                                                         */
/* ========================================================================= */
#vfx_layer {
  position: absolute;
  top: 0;
  left: 0;
  width: 1080px;
  height: 1920px;
  pointer-events: none;
  z-index: 85;
  overflow: hidden;
}

.vfx-element {
  position: absolute;
  top: 0;
  left: 0;
  width: 1080px;
  height: 1920px;
  pointer-events: none;
  display: none;
  opacity: 0;
}

.vfx-element svg {
  width: 100%;
  height: 100%;
  display: block;
  pointer-events: none;
}

#vfx_laser_beam_container {
  position: absolute;
  top: 0;
  left: 0;
  width: 1080px;
  height: 1920px;
  z-index: 75;
  pointer-events: none;
  display: none;
  opacity: 0;
}

#vfx_sunburst_container {
  position: absolute;
  top: 360px;
  left: 140px;
  width: 800px;
  height: 800px;
  z-index: 55;
  pointer-events: none;
  display: none;
  opacity: 0;
  transform-origin: 400px 400px;
}

#vfx_screen_shatter_container {
  position: absolute;
  top: 0;
  left: 0;
  width: 1080px;
  height: 1920px;
  z-index: 88;
  pointer-events: none;
  display: none;
  opacity: 0;
}

#vfx_fracture_cracks_container {
  position: absolute;
  top: 0;
  left: 0;
  width: 1080px;
  height: 1920px;
  z-index: 50;
  pointer-events: none;
  display: none;
  opacity: 0;
}

#vfx_sound_ripple_container {
  position: absolute;
  top: 420px;
  left: 0;
  width: 1080px;
  height: 1080px;
  z-index: 52;
  pointer-events: none;
  display: none;
  opacity: 0;
  transform-origin: 540px 540px;
}

/* ========================================================================= */
/* INFOGRAPHIC ELEMENTS LAYER (Narrative Context & Visual Metaphors)         */
/* ========================================================================= */
#infographic_layer {
  position: absolute;
  top: 0;
  left: 0;
  width: 1080px;
  height: 1920px;
  pointer-events: none;
  z-index: 90;
  overflow: hidden;
}

.infographic-element {
  position: absolute;
  pointer-events: none;
  display: none;
  opacity: 0;
  transform-origin: 50% 50%;
}

.infographic-element svg {
  width: 100%;
  height: 100%;
  display: block;
  pointer-events: none;
}

#infographic_thought_bubble_container {
  top: 300px;
  left: 290px;
  width: 500px;
  height: 400px;
  transform-origin: 100px 350px;
}

#infographic_comparison_card_container {
  top: 500px;
  left: 240px;
  width: 600px;
  height: 400px;
  transform-origin: 300px 200px;
}

#infographic_symbol_infinity_container {
  top: 420px;
  left: 290px;
  width: 500px;
  height: 350px;
  transform-origin: 250px 175px;
}

#infographic_symbol_scales_container {
  top: 420px;
  left: 340px;
  width: 400px;
  height: 400px;
  transform-origin: 200px 200px;
}

/* ========================================================================= */
/* THEATRICAL OUTRO MARQUEE (Curtain Call Sequence)                          */
/* ========================================================================= */
#outro_marquee_container {
  position: absolute;
  top: 640px;
  left: 140px;
  width: 800px;
  height: 240px;
  z-index: 92;
  pointer-events: none;
  display: none;
  opacity: 0;
  transform-origin: 400px 120px;
}

#outro_marquee_container svg {
  width: 100%;
  height: 100%;
  display: block;
  pointer-events: none;
}

/* ========================================================================= */
/* UNIVERSAL HIERARCHICAL RIVET RIG (0px 0px Stable Joint Origins)            */
/* ========================================================================= */
#thigh_left_rot, #thigh_l_rot, #leg_left_group {
  transform: rotate(var(--rot-thigh-l, var(--rot-thigh-left, 0deg))) !important;
  transform-origin: 0px 0px !important;
}
#shin_left_rot, #calf_left_rot, #calf_l_rot {
  transform: rotate(var(--rot-calf-l, var(--rot-shin-left, 0deg))) !important;
  transform-origin: 0px 0px !important;
}
#foot_left_rot, #foot_l_rot {
  transform: rotate(var(--rot-foot-l, 0deg)) !important;
  transform-origin: 0px 0px !important;
}

#thigh_right_rot, #thigh_r_rot, #leg_right_group {
  transform: rotate(var(--rot-thigh-r, var(--rot-thigh-right, 0deg))) !important;
  transform-origin: 0px 0px !important;
}
#shin_right_rot, #calf_right_rot, #calf_r_rot {
  transform: rotate(var(--rot-calf-r, var(--rot-shin-right, 0deg))) !important;
  transform-origin: 0px 0px !important;
}
#foot_right_rot, #foot_r_rot {
  transform: rotate(var(--rot-foot-r, 0deg)) !important;
  transform-origin: 0px 0px !important;
}

/* Universal Front/Primary Arms */
#shoulder_front_left_rot, #shoulder_left_rot, #shoulder_l_rot {
  transform: rotate(var(--rot-shoulder-l, var(--rot-shoulder-front-left, 0deg))) !important;
  transform-origin: 0px 0px !important;
}
#elbow_front_left_rot, #elbow_left_rot, #elbow_l_rot {
  transform: rotate(var(--rot-elbow-l, var(--rot-elbow-front-left, 0deg))) !important;
  transform-origin: 0px 0px !important;
}
#wrist_front_left_rot, #wrist_left_rot, #wrist_l_rot {
  transform: rotate(var(--rot-wrist-l, var(--rot-wrist-front-left, 0deg))) !important;
  transform-origin: 0px 0px !important;
}

#shoulder_front_right_rot, #shoulder_right_rot, #shoulder_r_rot {
  transform: rotate(var(--rot-shoulder-r, var(--rot-shoulder-front-right, 0deg))) !important;
  transform-origin: 0px 0px !important;
}
#elbow_front_right_rot, #elbow_right_rot, #elbow_r_rot {
  transform: rotate(var(--rot-elbow-r, var(--rot-elbow-front-right, 0deg))) !important;
  transform-origin: 0px 0px !important;
}
#wrist_front_right_rot, #wrist_right_rot, #wrist_r_rot {
  transform: rotate(var(--rot-wrist-r, var(--rot-wrist-front-right, 0deg))) !important;
  transform-origin: 0px 0px !important;
}

/* Multi-arm Rigs (Rear Arms) */
#shoulder_rear_left_rot {
  transform: rotate(var(--rot-shoulder-rear-left, 0deg)) !important;
  transform-origin: 0px 0px !important;
}
#elbow_rear_left_rot {
  transform: rotate(var(--rot-elbow-rear-left, 0deg)) !important;
  transform-origin: 0px 0px !important;
}
#wrist_rear_left_rot {
  transform: rotate(var(--rot-wrist-rear-left, 0deg)) !important;
  transform-origin: 0px 0px !important;
}

#shoulder_rear_right_rot {
  transform: rotate(var(--rot-shoulder-rear-right, 0deg)) !important;
  transform-origin: 0px 0px !important;
}
#elbow_rear_right_rot {
  transform: rotate(var(--rot-elbow-rear-right, 0deg)) !important;
  transform-origin: 0px 0px !important;
}
#wrist_rear_right_rot {
  transform: rotate(var(--rot-wrist-rear-right, 0deg)) !important;
  transform-origin: 0px 0px !important;
}

/* Torso, Waist & Head */
#torso_group, .puppet-torso {
  transform: translate(var(--trans-torso-x, 0px), var(--trans-torso-y, 0px)) rotate(var(--rot-torso, 0deg)) !important;
  transform-origin: 400px 700px !important;
}
#kamarband, #dhoti_skirt {
  transform: translate(var(--trans-torso-x, 0px), var(--trans-torso-y, 0px)) !important;
}
#hip_left_joint {
  transform: translate(340px, calc(770px + var(--trans-torso-y, 0px))) !important;
}
#hip_right_joint {
  transform: translate(460px, calc(770px + var(--trans-torso-y, 0px))) !important;
}
#neck_rot {
  transform: rotate(var(--rot-neck, 0deg)) !important;
  transform-origin: 0px 0px !important;
}
#head_center, #head_group {
  transform: rotate(var(--rot-head, 0deg)) !important;
  transform-origin: 0px 0px !important;
}
#heads_fan_mount, #prabhavali_mount, #wrath_mount {
  transform: translate(400px, calc(345px + var(--trans-torso-y, 0px))) rotate(var(--rot-torso, 0deg)) !important;
}
"""


def generate_index_html(
    lang: str,
    duration_sec: float,
    scenes_html: list[str],
    puppets_html: list[str],
    vfx_html: str = "",
    infographics_html: str = "",
    outro_marquee_html: str = "",
) -> str:
    title = f"Sutradhar Shorts Composition ({lang.upper()}) - Clean Canvas"
    comp_id = "main"

    scenes_str = "\n".join(scenes_html)
    puppets_str = "\n".join(puppets_html)
    vfx_str = vfx_html if vfx_html else ""
    infographics_str = infographics_html if infographics_html else ""
    outro_marquee_str = outro_marquee_html if outro_marquee_html else ""

    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
  <meta charset="UTF-8">
  <title>{title}</title>
  <link rel="stylesheet" href="styles.css">
  <script src="assets/js/gsap.min.js"></script>
  <script src="build/manifest.js"></script>
  <script src="engine.js"></script>
</head>
<body data-composition-id="{comp_id}" data-width="1080" data-height="1920" data-duration="{duration_sec:.2f}">

  <!-- MASTER THEATRICAL STAGE -->
  <div id="stage" data-layout-allow-overflow="true" data-layout-ignore="true">

    <!-- SCREEN FLASH OVERLAY (Wrath & Divine Strike Impacts) -->
    <div id="wrath_flash" data-layout-ignore="true"></div>

    <!-- FLOATING ATMOSPHERIC EMBERS -->
    <div id="embers_layer" data-layout-ignore="true">
      <div class="ember" style="left: 80px;"></div>
      <div class="ember" style="left: 160px;"></div>
      <div class="ember" style="left: 240px;"></div>
      <div class="ember" style="left: 340px;"></div>
      <div class="ember" style="left: 420px;"></div>
      <div class="ember" style="left: 520px;"></div>
      <div class="ember" style="left: 610px;"></div>
      <div class="ember" style="left: 700px;"></div>
      <div class="ember" style="left: 790px;"></div>
      <div class="ember" style="left: 880px;"></div>
      <div class="ember" style="left: 960px;"></div>
      <div class="ember" style="left: 1020px;"></div>
      <div class="ember" style="left: 280px;"></div>
      <div class="ember" style="left: 480px;"></div>
      <div class="ember" style="left: 740px;"></div>
      <div class="ember" style="left: 840px;"></div>
    </div>

    <!-- THEATRICAL TRANSITIONS LAYER -->
    <div id="transition_layer" data-layout-ignore="true">
      <div id="blind_wipe_container" data-layout-ignore="true">
        <div class="blind-slat" data-layout-ignore="true"></div>
        <div class="blind-slat" data-layout-ignore="true"></div>
        <div class="blind-slat" data-layout-ignore="true"></div>
        <div class="blind-slat" data-layout-ignore="true"></div>
        <div class="blind-slat" data-layout-ignore="true"></div>
        <div class="blind-slat" data-layout-ignore="true"></div>
        <div class="blind-slat" data-layout-ignore="true"></div>
        <div class="blind-slat" data-layout-ignore="true"></div>
        <div class="blind-slat" data-layout-ignore="true"></div>
        <div class="blind-slat" data-layout-ignore="true"></div>
      </div>
      <div id="border_wipe_bar" data-layout-ignore="true"></div>
      <div id="iris_wipe_circle" data-layout-ignore="true"></div>
    </div>

    <!-- DYNAMIC VFX LAYER -->
    <div id="vfx_layer" data-layout-ignore="true">
{vfx_str}
    </div>

    <!-- INFOGRAPHIC ELEMENTS LAYER -->
    <div id="infographic_layer" data-layout-ignore="true">
{infographics_str}
    </div>

    <!-- THEATRICAL OUTRO MARQUEE -->
{outro_marquee_str}

    <!-- DYNAMIC MANIFEST SHOT CONTAINERS -->
{scenes_str}

    <!-- KATHPUTLI PUPPET RIGS -->
{puppets_str}

  </div>
</body>
</html>
"""


def generate_engine_js() -> str:
    return """// Sutradhar v4.0 Master Choreography Engine
// Reads dynamic audio duration & scene timings from window.EPISODE_MANIFEST
window.__timelines = window.__timelines || {};

function initTimeline() {
  const manifest = window.EPISODE_MANIFEST || window.__audio_manifest;
  if (!manifest) {
    console.error("[ERROR] No EPISODE_MANIFEST found in window.");
    return;
  }

  const scenes = manifest.scenes || manifest.beats || [];
  if (scenes.length < 3) {
    console.error("[ERROR] EPISODE_MANIFEST must have at least 3 scenes/beats.", scenes);
    return;
  }

  const total_dur = Number(manifest.audio?.total_duration_sec || scenes[scenes.length - 1].end_sec);
  const masterTl = gsap.timeline({ paused: true });

  const stage = document.querySelector("#stage");
  const wrathFlash = document.querySelector("#wrath_flash");
  const embers = document.querySelectorAll(".ember");
  const curtains = {
    left: document.querySelector("#curtain_left"),
    right: document.querySelector("#curtain_right")
  };
  let curtainsOpened = false;

  // Theatrical Transitions Elements
  const blindWipeContainer = document.querySelector("#blind_wipe_container");
  const blindSlats = document.querySelectorAll(".blind-slat");
  const borderWipeBar = document.querySelector("#border_wipe_bar");
  const irisWipeCircle = document.querySelector("#iris_wipe_circle");

  // Dynamic VFX Layer Elements
  const vfxLaser = document.querySelector("#vfx_laser_beam_container");
  const vfxSunburst = document.querySelector("#vfx_sunburst_container");
  const vfxShatter = document.querySelector("#vfx_screen_shatter_container");
  const vfxCracks = document.querySelector("#vfx_fracture_cracks_container");
  const vfxRipple = document.querySelector("#vfx_sound_ripple_container");

  // Infographic Layer Elements
  const infoBubble = document.querySelector("#infographic_thought_bubble_container");
  const infoCompare = document.querySelector("#infographic_comparison_card_container");
  const infoInfinity = document.querySelector("#infographic_symbol_infinity_container");
  const infoScales = document.querySelector("#infographic_symbol_scales_container");

  // Outro Marquee Element
  const outroMarquee = document.querySelector("#outro_marquee_container");

  // Puppet elements map
  const allPuppets = Array.from(document.querySelectorAll(".puppet-wrapper"));
  const primaryPuppet = document.querySelector("#puppet_wrapper") || allPuppets[0];

  function getPuppet(nameOrIndex) {
    if (typeof nameOrIndex === "string" && nameOrIndex) {
      for (let i = 0; i < allPuppets.length; i++) {
        if (allPuppets[i].getAttribute("data-character") === nameOrIndex) {
          return allPuppets[i];
        }
      }
    } else if (typeof nameOrIndex === "number" && nameOrIndex >= 0 && nameOrIndex < allPuppets.length) {
      return allPuppets[nameOrIndex];
    }
    return null;
  }

  const infoElements = {
    thought_bubble: infoBubble,
    comparison_card: infoCompare,
    symbol_infinity: infoInfinity,
    symbol_scales: infoScales
  };

  // Standardized Kathputli Pose Presets
  function applyPose(puppetEl, pose, t_start, dur) {
    if (!puppetEl) return;
    const isFast = dur < 0.4;
    const ease = isFast ? "power2.out" : "sine.inOut";

    let poseVars = {};
    if (pose === "action_raised") {
      poseVars = {
        "--trans-torso-x": "0px",
        "--trans-torso-y": "0px",
        "--rot-torso": "2deg",
        "--rot-shoulder-l": "-28deg",
        "--rot-elbow-l": "32deg",
        "--rot-wrist-l": "10deg",
        "--rot-shoulder-r": "28deg",
        "--rot-elbow-r": "-32deg",
        "--rot-wrist-r": "-10deg",
        "--rot-shoulder-rear-left": "-28deg",
        "--rot-elbow-rear-left": "22deg",
        "--rot-shoulder-rear-right": "28deg",
        "--rot-elbow-rear-right": "-22deg",
        "--rot-shoulder-front-left": "-18deg",
        "--rot-elbow-front-left": "25deg",
        "--rot-shoulder-front-right": "18deg",
        "--rot-elbow-front-right": "-25deg",
        "--rot-thigh-l": "4deg",
        "--rot-calf-l": "-6deg",
        "--rot-thigh-r": "-4deg",
        "--rot-calf-r": "6deg",
        "--rot-head": "-3deg"
      };
    } else if (pose === "wrath_dialogue") {
      poseVars = {
        "--trans-torso-x": "0px",
        "--trans-torso-y": "15px",
        "--rot-torso": "4deg",
        "--rot-shoulder-l": "-20deg",
        "--rot-elbow-l": "25deg",
        "--rot-shoulder-r": "25deg",
        "--rot-elbow-r": "-25deg",
        "--rot-shoulder-front-left": "-20deg",
        "--rot-elbow-front-left": "25deg",
        "--rot-shoulder-front-right": "25deg",
        "--rot-elbow-front-right": "-25deg",
        "--rot-thigh-l": "8deg",
        "--rot-calf-l": "-10deg",
        "--rot-thigh-r": "-8deg",
        "--rot-calf-r": "10deg",
        "--rot-head": "2deg"
      };
    } else if (pose === "blessing_calm") {
      poseVars = {
        "--trans-torso-x": "0px",
        "--trans-torso-y": "0px",
        "--rot-torso": "0deg",
        "--rot-shoulder-l": "15deg",
        "--rot-elbow-l": "30deg",
        "--rot-wrist-l": "0deg",
        "--rot-shoulder-r": "-45deg",
        "--rot-elbow-r": "80deg",
        "--rot-wrist-r": "10deg",
        "--rot-shoulder-front-left": "15deg",
        "--rot-elbow-front-left": "30deg",
        "--rot-shoulder-front-right": "-45deg",
        "--rot-elbow-front-right": "80deg",
        "--rot-thigh-l": "0deg",
        "--rot-calf-l": "0deg",
        "--rot-thigh-r": "0deg",
        "--rot-calf-r": "0deg",
        "--rot-head": "0deg"
      };
    } else if (pose === "humbled_braced") {
      poseVars = {
        "--trans-torso-x": "0px",
        "--trans-torso-y": "80px",
        "--rot-torso": "2deg",
        "--rot-shoulder-l": "105deg",
        "--rot-elbow-l": "55deg",
        "--rot-shoulder-r": "-105deg",
        "--rot-elbow-r": "-55deg",
        "--rot-shoulder-front-left": "110deg",
        "--rot-elbow-front-left": "60deg",
        "--rot-shoulder-front-right": "-110deg",
        "--rot-elbow-front-right": "-60deg",
        "--rot-shoulder-rear-left": "-18deg",
        "--rot-elbow-rear-left": "18deg",
        "--rot-shoulder-rear-right": "18deg",
        "--rot-elbow-rear-right": "-18deg",
        "--rot-thigh-l": "40deg",
        "--rot-calf-l": "-55deg",
        "--rot-thigh-r": "-40deg",
        "--rot-calf-r": "55deg",
        "--rot-thigh-left": "40deg",
        "--rot-shin-left": "-55deg",
        "--rot-thigh-right": "-40deg",
        "--rot-shin-right": "55deg",
        "--rot-head": "-6deg"
      };
    } else {
      // Default: idle_royal
      poseVars = {
        "--trans-torso-x": "0px",
        "--trans-torso-y": "0px",
        "--rot-torso": "0deg",
        "--rot-shoulder-l": "0deg",
        "--rot-elbow-l": "0deg",
        "--rot-wrist-l": "0deg",
        "--rot-shoulder-r": "0deg",
        "--rot-elbow-r": "0deg",
        "--rot-wrist-r": "0deg",
        "--rot-shoulder-front-left": "0deg",
        "--rot-elbow-front-left": "0deg",
        "--rot-wrist-front-left": "0deg",
        "--rot-shoulder-front-right": "0deg",
        "--rot-elbow-front-right": "0deg",
        "--rot-wrist-front-right": "0deg",
        "--rot-shoulder-rear-left": "0deg",
        "--rot-elbow-rear-left": "0deg",
        "--rot-wrist-rear-left": "0deg",
        "--rot-shoulder-rear-right": "0deg",
        "--rot-elbow-rear-right": "0deg",
        "--rot-wrist-rear-right": "0deg",
        "--rot-thigh-l": "0deg",
        "--rot-calf-l": "0deg",
        "--rot-thigh-r": "0deg",
        "--rot-calf-r": "0deg",
        "--rot-thigh-left": "0deg",
        "--rot-shin-left": "0deg",
        "--rot-thigh-right": "0deg",
        "--rot-shin-right": "0deg",
        "--rot-head": "0deg"
      };
    }

    poseVars.duration = dur;
    poseVars.ease = ease;
    masterTl.to(puppetEl, poseVars, t_start);
  }

  // Switchable Facial Expression System (Calm, Wrath/Rage, Fear, Joy)
  function applyExpression(puppetEl, emotion, t_start, dur) {
    if (!puppetEl) return;
    const em = (emotion || "calm").toLowerCase().trim();
    const d = dur || 0.25;

    const bn = puppetEl.querySelector("#brows_neutral");
    const ba = puppetEl.querySelector("#brows_angry");
    const bf = puppetEl.querySelector("#brows_fear");
    const bj = puppetEl.querySelector("#brows_joy");

    const en = puppetEl.querySelector("#eyes_normal");
    const ew = puppetEl.querySelector("#eyes_wrath");
    const ef = puppetEl.querySelector("#eyes_fear");
    const ej = puppetEl.querySelector("#eyes_joy");

    const mc = puppetEl.querySelector("#mouth_calm");
    const mt = puppetEl.querySelector("#mouth_talk");
    const ms = puppetEl.querySelector("#mouth_shout");
    const mf = puppetEl.querySelector("#mouth_fear");
    const mj = puppetEl.querySelector("#mouth_joy");

    const wrathSunburst = puppetEl.querySelector("#wrath_sunburst");

    if (em === "wrath" || em === "rage") {
      if (bn) masterTl.to(bn, { opacity: 0, duration: d }, t_start);
      if (ba) masterTl.to(ba, { opacity: 1, duration: d }, t_start);
      if (bf) masterTl.to(bf, { opacity: 0, duration: d }, t_start);
      if (bj) masterTl.to(bj, { opacity: 0, duration: d }, t_start);

      if (en) masterTl.to(en, { opacity: 0, duration: d }, t_start);
      if (ew) masterTl.to(ew, { opacity: 1, duration: d }, t_start);
      if (ef) masterTl.to(ef, { opacity: 0, duration: d }, t_start);
      if (ej) masterTl.to(ej, { opacity: 0, duration: d }, t_start);

      if (mc) masterTl.to(mc, { opacity: 0, duration: d }, t_start);
      if (ms) masterTl.to(ms, { opacity: 1, duration: d }, t_start);
      if (mf) masterTl.to(mf, { opacity: 0, duration: d }, t_start);
      if (mj) masterTl.to(mj, { opacity: 0, duration: d }, t_start);
      if (mt) masterTl.to(mt, { opacity: 0, duration: d }, t_start);

      if (wrathSunburst) {
        masterTl.fromTo(wrathSunburst, { opacity: 0, scale: 0.85 }, { opacity: 0.65, scale: 1.05, duration: 0.45, ease: "back.out(2)" }, t_start);
      }
    } else if (em === "fear" || em === "shock") {
      if (bn) masterTl.to(bn, { opacity: 0, duration: d }, t_start);
      if (ba) masterTl.to(ba, { opacity: 0, duration: d }, t_start);
      if (bf) masterTl.to(bf, { opacity: 1, duration: d }, t_start);
      if (bj) masterTl.to(bj, { opacity: 0, duration: d }, t_start);

      if (en) masterTl.to(en, { opacity: 0, duration: d }, t_start);
      if (ew) masterTl.to(ew, { opacity: 0, duration: d }, t_start);
      if (ef) masterTl.to(ef, { opacity: 1, duration: d }, t_start);
      if (ej) masterTl.to(ej, { opacity: 0, duration: d }, t_start);

      if (mc) masterTl.to(mc, { opacity: 0, duration: d }, t_start);
      if (ms) masterTl.to(ms, { opacity: 0, duration: d }, t_start);
      if (mf) masterTl.to(mf, { opacity: 1, duration: d }, t_start);
      if (mj) masterTl.to(mj, { opacity: 0, duration: d }, t_start);
      if (mt) masterTl.to(mt, { opacity: 0, duration: d }, t_start);

      if (wrathSunburst) {
        masterTl.to(wrathSunburst, { opacity: 0, duration: d }, t_start);
      }
    } else if (em === "joy" || em === "smirk") {
      if (bn) masterTl.to(bn, { opacity: 0, duration: d }, t_start);
      if (ba) masterTl.to(ba, { opacity: 0, duration: d }, t_start);
      if (bf) masterTl.to(bf, { opacity: 0, duration: d }, t_start);
      if (bj) masterTl.to(bj, { opacity: 1, duration: d }, t_start);

      if (en) masterTl.to(en, { opacity: 0, duration: d }, t_start);
      if (ew) masterTl.to(ew, { opacity: 0, duration: d }, t_start);
      if (ef) masterTl.to(ef, { opacity: 0, duration: d }, t_start);
      if (ej) masterTl.to(ej, { opacity: 1, duration: d }, t_start);

      if (mc) masterTl.to(mc, { opacity: 0, duration: d }, t_start);
      if (ms) masterTl.to(ms, { opacity: 0, duration: d }, t_start);
      if (mf) masterTl.to(mf, { opacity: 0, duration: d }, t_start);
      if (mj) masterTl.to(mj, { opacity: 1, duration: d }, t_start);
      if (mt) masterTl.to(mt, { opacity: 0, duration: d }, t_start);

      if (wrathSunburst) {
        masterTl.to(wrathSunburst, { opacity: 0, duration: d }, t_start);
      }
    } else {
      // Default: calm / meditating
      if (bn) masterTl.to(bn, { opacity: 1, duration: d }, t_start);
      if (ba) masterTl.to(ba, { opacity: 0, duration: d }, t_start);
      if (bf) masterTl.to(bf, { opacity: 0, duration: d }, t_start);
      if (bj) masterTl.to(bj, { opacity: 0, duration: d }, t_start);

      if (en) masterTl.to(en, { opacity: 1, duration: d }, t_start);
      if (ew) masterTl.to(ew, { opacity: 0, duration: d }, t_start);
      if (ef) masterTl.to(ef, { opacity: 0, duration: d }, t_start);
      if (ej) masterTl.to(ej, { opacity: 0, duration: d }, t_start);

      if (mc) masterTl.to(mc, { opacity: 1, duration: d }, t_start);
      if (ms) masterTl.to(ms, { opacity: 0, duration: d }, t_start);
      if (mf) masterTl.to(mf, { opacity: 0, duration: d }, t_start);
      if (mj) masterTl.to(mj, { opacity: 0, duration: d }, t_start);
      if (mt) masterTl.to(mt, { opacity: 0, duration: d }, t_start);

      if (wrathSunburst) {
        masterTl.to(wrathSunburst, { opacity: 0, duration: d }, t_start);
      }
    }
  }

  // Lip-Sync Animation
  function applyLipSync(puppetEl, t_start, dur, baseEmotion) {
    if (!puppetEl) return;
    const mc = puppetEl.querySelector("#mouth_calm");
    const mt = puppetEl.querySelector("#mouth_talk");
    const ms = puppetEl.querySelector("#mouth_shout");
    if (!mc || !mt || !ms) return;

    const step = Math.max(0.35, dur / 6.0);
    masterTl.set(mc, { opacity: 0 }, t_start + 0.15);
    masterTl.set(mt, { opacity: 1 }, t_start + 0.15);
    masterTl.set(mt, { opacity: 0 }, t_start + 0.15 + step);
    masterTl.set(ms, { opacity: 1 }, t_start + 0.15 + step);
    masterTl.set(ms, { opacity: 0 }, t_start + 0.15 + step * 2);
    masterTl.set(mt, { opacity: 1 }, t_start + 0.15 + step * 2);
    masterTl.set(mt, { opacity: 0 }, t_start + 0.15 + step * 3);
    masterTl.set(ms, { opacity: 1 }, t_start + 0.15 + step * 3);
    masterTl.set(ms, { opacity: 0 }, t_start + dur - 0.25);
    masterTl.set(mt, { opacity: 0 }, t_start + dur - 0.25);
    applyExpression(puppetEl, baseEmotion, t_start + dur - 0.20, 0.20);
  }

  // Initial set for all puppets (hidden, calm expression)
  allPuppets.forEach(p => {
    gsap.set(p, {
      display: "none",
      opacity: 0,
      scale: 1.15,
      x: 0,
      y: 120,
      "--trans-torso-x": "0px",
      "--trans-torso-y": "0px",
      "--rot-torso": "0deg",
      "--rot-shoulder-l": "0deg",
      "--rot-elbow-l": "0deg",
      "--rot-wrist-l": "0deg",
      "--rot-shoulder-r": "0deg",
      "--rot-elbow-r": "0deg",
      "--rot-wrist-r": "0deg",
      "--rot-thigh-l": "0deg",
      "--rot-calf-l": "0deg",
      "--rot-thigh-r": "0deg",
      "--rot-calf-r": "0deg"
    });
    const bn = p.querySelector("#brows_neutral");
    const ba = p.querySelector("#brows_angry");
    const bf = p.querySelector("#brows_fear");
    const bj = p.querySelector("#brows_joy");
    const en = p.querySelector("#eyes_normal");
    const ew = p.querySelector("#eyes_wrath");
    const ef = p.querySelector("#eyes_fear");
    const ej = p.querySelector("#eyes_joy");
    const mc = p.querySelector("#mouth_calm");
    const mt = p.querySelector("#mouth_talk");
    const ms = p.querySelector("#mouth_shout");
    const mf = p.querySelector("#mouth_fear");
    const mj = p.querySelector("#mouth_joy");

    if (bn) gsap.set(bn, { opacity: 1 });
    if (ba) gsap.set(ba, { opacity: 0 });
    if (bf) gsap.set(bf, { opacity: 0 });
    if (bj) gsap.set(bj, { opacity: 0 });

    if (en) gsap.set(en, { opacity: 1 });
    if (ew) gsap.set(ew, { opacity: 0 });
    if (ef) gsap.set(ef, { opacity: 0 });
    if (ej) gsap.set(ej, { opacity: 0 });

    if (mc) gsap.set(mc, { opacity: 1 });
    if (mt) gsap.set(mt, { opacity: 0 });
    if (ms) gsap.set(ms, { opacity: 0 });
    if (mf) gsap.set(mf, { opacity: 0 });
    if (mj) gsap.set(mj, { opacity: 0 });
  });

  // Continuous floating embers across long-form or short-form timeline
  const emberRepeats = Math.max(8, Math.ceil(total_dur / 4.0));
  embers.forEach((ember, i) => {
    const dur = 4.5 + (i % 3) * 1.2;
    const delay = (i * 0.4) % 3.0;
    masterTl.fromTo(ember,
      { y: 1950, x: "+=" + ((i % 4) * 35 - 50), opacity: 0 },
      { y: -60, opacity: 0.85, duration: dur, ease: "none", repeat: emberRepeats },
      delay
    );
  });

  // =========================================================================
  // DYNAMIC SCENE CHOREOGRAPHY
  // =========================================================================
  scenes.forEach((scene, idx) => {
    const shotNum = idx + 1;
    const shotEl = document.getElementById("shot_" + shotNum + "_container");
    if (!shotEl) return;

    const t_start = Number(scene.start_sec);
    const t_end = Number(scene.end_sec);
    const dur = t_end - t_start;
    const shotType = (scene.shot_type || (idx === 0 ? "curtain_establishing" : "character_medium")).toLowerCase();
    const camMotion = (scene.camera_motion || "push_in").toLowerCase();
    const emotion = (scene.emotion || "calm").toLowerCase();
    const posePreset = scene.pose_preset || (shotType.includes("climax") ? "humbled_braced" : (shotType.includes("close") ? "wrath_dialogue" : "idle_royal"));
    const transitionType = (scene.transition_type || (idx === 0 ? "curtain_open" : "fade")).toLowerCase();
    const vfxElements = scene.vfx_elements || [];

    // Scene Transition Execution
    if (idx === 0) {
      masterTl.set(shotEl, { display: "block", opacity: 1 }, 0.0);
      if (transitionType === "curtain_open" && curtains.left && curtains.right && !curtainsOpened) {
        masterTl.to(curtains.left, { xPercent: -102, duration: 1.8, ease: "power2.inOut" }, t_start + 0.4);
        masterTl.to(curtains.right, { xPercent: 102, duration: 1.8, ease: "power2.inOut" }, t_start + 0.4);
        curtainsOpened = true;
      }
    } else {
      const prevShotEl = document.getElementById("shot_" + idx + "_container");

      if (transitionType === "blind_wipe" && blindWipeContainer && blindSlats.length > 0) {
        const t_trans = Math.max(0, t_start - 0.20);
        masterTl.set(blindWipeContainer, { display: "block" }, t_trans);
        masterTl.fromTo(blindSlats, { scaleY: 0 }, { scaleY: 1, duration: 0.20, stagger: 0.015, ease: "power2.in" }, t_trans);
        masterTl.set(shotEl, { display: "block", opacity: 1 }, t_start);
        if (prevShotEl) {
          masterTl.set(prevShotEl, { display: "none", opacity: 0 }, t_start);
        }
        masterTl.to(blindSlats, { scaleY: 0, duration: 0.20, stagger: 0.015, ease: "power2.out" }, t_start + 0.05);
        masterTl.set(blindWipeContainer, { display: "none" }, t_start + 0.35);
      }
      else if (transitionType === "border_wipe" && borderWipeBar) {
        const t_trans = Math.max(0, t_start - 0.22);
        masterTl.set(borderWipeBar, { display: "block", x: -120, opacity: 1 }, t_trans);
        masterTl.to(borderWipeBar, { x: 1200, duration: 0.45, ease: "power2.inOut" }, t_trans);
        masterTl.set(shotEl, { display: "block", opacity: 1 }, t_start);
        if (prevShotEl) {
          masterTl.set(prevShotEl, { display: "none", opacity: 0 }, t_start);
        }
        masterTl.set(borderWipeBar, { display: "none" }, t_start + 0.25);
      }
      else if (transitionType === "shatter_transition" && vfxShatter) {
        const t_trans = Math.max(0, t_start - 0.15);
        masterTl.set(vfxShatter, { display: "block", opacity: 1 }, t_trans);
        masterTl.fromTo(vfxShatter, { scale: 0.95 }, { scale: 1.05, duration: 0.15, ease: "power4.in" }, t_trans);
        if (wrathFlash) {
          masterTl.fromTo(wrathFlash, { opacity: 0 }, { opacity: 0.70, duration: 0.08, ease: "power1.in" }, t_trans + 0.05);
          masterTl.to(wrathFlash, { opacity: 0, duration: 0.15, ease: "power1.out" }, t_trans + 0.13);
        }
        masterTl.set(shotEl, { display: "block", opacity: 1 }, t_start);
        if (prevShotEl) {
          masterTl.set(prevShotEl, { display: "none", opacity: 0 }, t_start);
        }
        masterTl.to(vfxShatter, { opacity: 0, scale: 1.25, duration: 0.35, ease: "power2.out" }, t_start);
        masterTl.set(vfxShatter, { display: "none" }, t_start + 0.35);
      }
      else if (transitionType === "radial_wipe" && irisWipeCircle) {
        const t_trans = Math.max(0, t_start - 0.25);
        masterTl.set(irisWipeCircle, { display: "block", scale: 0, opacity: 1 }, t_trans);
        masterTl.to(irisWipeCircle, { scale: 24, duration: 0.25, ease: "power2.in" }, t_trans);
        masterTl.set(shotEl, { display: "block", opacity: 1 }, t_start);
        if (prevShotEl) {
          masterTl.set(prevShotEl, { display: "none", opacity: 0 }, t_start);
        }
        masterTl.to(irisWipeCircle, { opacity: 0, scale: 28, duration: 0.25, ease: "power2.out" }, t_start);
        masterTl.set(irisWipeCircle, { display: "none" }, t_start + 0.26);
      }
      else if (transitionType === "cut") {
        masterTl.set(shotEl, { display: "block", opacity: 1 }, t_start);
        if (prevShotEl) {
          masterTl.set(prevShotEl, { display: "none", opacity: 0 }, t_start);
        }
      }
      else {
        // Default: fade (smooth crossfade)
        masterTl.set(shotEl, { display: "block" }, t_start);
        masterTl.fromTo(shotEl, { opacity: 0 }, { opacity: 1, duration: 0.35, ease: "power2.inOut" }, t_start);
        if (prevShotEl) {
          masterTl.to(prevShotEl, { opacity: 0, duration: 0.35, ease: "power2.inOut" }, t_start);
          masterTl.set(prevShotEl, { display: "none" }, t_start + 0.35);
        }
      }
    }

    // Camera motion applied to shot container
    if (camMotion === "push_in") {
      masterTl.fromTo(shotEl, { scale: 1.0, y: 0 }, { scale: 1.15, y: -20, duration: dur, ease: "sine.inOut" }, t_start);
    } else if (camMotion === "pull_back") {
      masterTl.fromTo(shotEl, { scale: 1.15, y: -20 }, { scale: 1.0, y: 0, duration: dur, ease: "sine.inOut" }, t_start);
    } else if (camMotion === "slow_pan") {
      masterTl.fromTo(shotEl, { x: 25 }, { x: -25, duration: dur, ease: "sine.inOut" }, t_start);
    } else if (camMotion === "close_up") {
      masterTl.to(shotEl, { scale: 1.25, y: -35, duration: dur, ease: "power2.out" }, t_start);
    } else if (camMotion === "dramatic_zoom") {
      masterTl.fromTo(shotEl, { scale: 1.0, y: 0 }, { scale: 1.35, y: -50, duration: Math.min(dur, 1.2), ease: "power3.out" }, t_start);
    } else if (camMotion === "micro_shake") {
      masterTl.to(stage, { x: 15, duration: 0.04, yoyo: true, repeat: 14, ease: "none" }, t_start + 0.15);
    }

    // Puppet Resolution for Scene
    const p1 = getPuppet(scene.primary_character) || primaryPuppet;
    const p2 = getPuppet(scene.secondary_character) || (allPuppets.length > 1 && allPuppets[0] === p1 ? allPuppets[1] : allPuppets[0]);
    const p3 = getPuppet(scene.tertiary_character) || (allPuppets.length > 2 ? allPuppets[2] : null);
    const hasMultiple = !!(scene.secondary_character || shotType.includes("confrontation") || (scene.characters && scene.characters.length > 1));

    // Specific Shot Type & Puppet Choreography
    if (shotType === "curtain_establishing" || shotType === "wide_establishing") {
      if (curtains.left && curtains.right && !curtainsOpened) {
        masterTl.to(curtains.left, { xPercent: -102, duration: 1.8, ease: "power2.inOut" }, t_start + 0.4);
        masterTl.to(curtains.right, { xPercent: 102, duration: 1.8, ease: "power2.inOut" }, t_start + 0.4);
        curtainsOpened = true;
      }
      allPuppets.forEach(p => masterTl.set(p, { display: "none", opacity: 0 }, t_start));
    }
    else if (shotType === "landscape_cutaway") {
      allPuppets.forEach(p => masterTl.set(p, { display: "none", opacity: 0 }, t_start));
    }
    else if (shotType === "bespoke_diagram_reveal") {
      allPuppets.forEach(p => masterTl.set(p, { display: "none", opacity: 0 }, t_start));
      const diagEl = shotEl.querySelector(".diagram-wrapper");
      if (diagEl) {
        masterTl.set(diagEl, { display: "block" }, t_start);
        masterTl.fromTo(diagEl, { opacity: 0, scale: 0.90 }, { opacity: 1, scale: 1.05, duration: 1.2, ease: "power2.out" }, t_start + 0.2);
      }
    }
    else if (hasMultiple && p1 && p2 && p1 !== p2) {
      // MULTI-CHARACTER STAGING (2 or 3 puppets)
      allPuppets.forEach(p => {
        if (p !== p1 && p !== p2 && p !== p3) masterTl.set(p, { display: "none", opacity: 0 }, t_start);
      });

      if (p3) {
        // Triad council layout (Left, Center, Right)
        masterTl.set([p1, p2, p3], { display: "block", opacity: 1 }, t_start);
        masterTl.to(p2, { scale: 1.05, scaleX: 1.05, x: -260, y: 140, duration: 0.4, ease: "power2.out" }, t_start);
        masterTl.to(p1, { scale: 1.15, scaleX: 1.15, x: 0, y: 120, duration: 0.4, ease: "power2.out" }, t_start);
        masterTl.to(p3, { scale: 1.05, scaleX: -1.05, x: 260, y: 140, duration: 0.4, ease: "power2.out" }, t_start);

        applyPose(p1, posePreset, t_start, 0.4);
        applyExpression(p1, emotion, t_start, 0.3);
        applyPose(p2, "blessing_calm", t_start, 0.4);
        applyExpression(p2, "calm", t_start, 0.3);
        applyPose(p3, "idle_royal", t_start, 0.4);
        applyExpression(p3, "calm", t_start, 0.3);
      } else {
        // Dual character confrontation / dialogue exchange
        masterTl.set([p1, p2], { display: "block", opacity: 1 }, t_start);

        if (scene.speaker_role === "character_dialogue") {
          // Focus shift & scale swap: speaker is dominant
          masterTl.to(p1, { scale: 1.22, scaleX: 1.22, x: -190, y: 110, duration: 0.35, ease: "power2.out" }, t_start);
          masterTl.to(p2, { scale: 1.02, scaleX: -1.02, x: 190, y: 140, duration: 0.35, ease: "power2.out" }, t_start);

          applyPose(p1, posePreset || "action_raised", t_start, 0.35);
          applyExpression(p1, emotion, t_start, 0.3);
          applyLipSync(p1, t_start, dur, emotion);

          applyPose(p2, "blessing_calm", t_start, 0.35);
          applyExpression(p2, (emotion === "wrath" || emotion === "rage" ? "fear" : "calm"), t_start, 0.3);
        } else if (shotType === "two_character_confrontation" || shotType.includes("confrontation")) {
          // Dramatic face-off
          masterTl.to(p1, { scale: 1.12, scaleX: 1.12, x: -190, y: 130, duration: 0.4, ease: "power2.out" }, t_start);
          masterTl.to(p2, { scale: 1.12, scaleX: -1.12, x: 190, y: 130, duration: 0.4, ease: "power2.out" }, t_start);

          applyPose(p1, "action_raised", t_start, 0.4);
          applyExpression(p1, emotion === "calm" ? "wrath" : emotion, t_start, 0.3);

          applyPose(p2, (emotion === "wrath" || emotion === "rage" ? "humbled_braced" : "blessing_calm"), t_start, 0.4);
          applyExpression(p2, (emotion === "wrath" || emotion === "rage" ? "fear" : "calm"), t_start, 0.3);
        } else {
          // Standard multi-character medium
          masterTl.to(p1, { scale: 1.10, scaleX: 1.10, x: -180, y: 130, duration: 0.4, ease: "power2.out" }, t_start);
          masterTl.to(p2, { scale: 1.10, scaleX: -1.10, x: 180, y: 130, duration: 0.4, ease: "power2.out" }, t_start);

          applyPose(p1, posePreset, t_start, 0.4);
          applyExpression(p1, emotion, t_start, 0.3);
          applyPose(p2, "idle_royal", t_start, 0.4);
          applyExpression(p2, "calm", t_start, 0.3);
        }
      }
    }
    else if (shotType === "character_closeup_dialogue" || shotType === "close_up_wrath") {
      allPuppets.forEach(p => {
        if (p !== p1) masterTl.set(p, { display: "none", opacity: 0 }, t_start);
      });
      if (p1) {
        masterTl.set(p1, { display: "block", opacity: 1 }, t_start);
        masterTl.to(p1, { scale: 2.15, scaleX: 2.15, x: 0, y: 520, duration: 0.35, ease: "power3.out" }, t_start);

        if (wrathFlash && (emotion === "wrath" || emotion === "rage")) {
          masterTl.fromTo(wrathFlash, { opacity: 0 }, { opacity: 0.45, duration: 0.08, ease: "power1.in" }, t_start);
          masterTl.to(wrathFlash, { opacity: 0, duration: 0.20, ease: "power1.out" }, t_start + 0.08);
        }

        applyPose(p1, posePreset, t_start, 0.35);
        applyExpression(p1, emotion, t_start, 0.25);
        applyLipSync(p1, t_start, dur, emotion);
      }
    }
    else if (shotType === "dramatic_climax" || shotType === "cosmic_strike" || shotType === "crushed_submission") {
      allPuppets.forEach(p => {
        if (p !== p1) masterTl.set(p, { display: "none", opacity: 0 }, t_start);
      });
      if (p1) {
        masterTl.set(p1, { display: "block", opacity: 1 }, t_start);
        masterTl.to(p1, { scale: 1.18, scaleX: 1.18, x: 0, y: 180, duration: 0.3, ease: "power2.out" }, t_start);
        applyPose(p1, posePreset, t_start, 0.3);
        applyExpression(p1, emotion, t_start, 0.25);
      }

      if (wrathFlash) {
        masterTl.fromTo(wrathFlash, { opacity: 0 }, { opacity: 0.80, duration: 0.08, ease: "power1.in" }, t_start + 0.1);
        masterTl.to(wrathFlash, { opacity: 0, duration: 0.30, ease: "power2.out" }, t_start + 0.18);
      }

      const divineLaser = shotEl.querySelector("#divine_laser_beam");
      const boulders = shotEl.querySelector("#falling_boulders");
      if (divineLaser) {
        masterTl.fromTo(divineLaser, { opacity: 0, scaleY: 0 }, { opacity: 1, scaleY: 1, duration: 0.16, ease: "power4.in", transformOrigin: "540px 0px" }, t_start + 0.1);
        masterTl.to(divineLaser, { opacity: 0, duration: 0.40, ease: "power2.out" }, t_start + 0.3);
      }
      if (boulders) {
        masterTl.to(boulders, { opacity: 1, duration: 0.1 }, t_start + 0.25);
      }

      const fgMountain = shotEl.querySelector(".foreground-wrapper") || document.querySelector("#foreground_mountain_container");
      if (fgMountain) {
        masterTl.fromTo(fgMountain, { y: -10 }, { y: 65, duration: dur, ease: "sine.inOut" }, t_start);
      }
    }
    else {
      // Standard: character_medium / character_advance
      allPuppets.forEach(p => {
        if (p !== p1) masterTl.set(p, { display: "none", opacity: 0 }, t_start);
      });
      if (p1) {
        masterTl.set(p1, { display: "block", opacity: 1 }, t_start);
        masterTl.to(p1, { scale: 1.15, scaleX: 1.15, x: 0, y: 120, duration: 0.8, ease: "power2.out" }, t_start);
        applyPose(p1, posePreset, t_start, 0.8);
        applyExpression(p1, emotion, t_start, 0.3);

        masterTl.to(p1, {
          "--rot-thigh-l": "8deg",
          "--rot-calf-l": "-12deg",
          "--rot-thigh-left": "8deg",
          "--rot-shin-left": "-12deg",
          duration: 0.85,
          yoyo: true,
          repeat: Math.ceil(dur / 0.85),
          ease: "sine.inOut"
        }, t_start);

        masterTl.to(p1, {
          "--rot-thigh-r": "-8deg",
          "--rot-calf-r": "12deg",
          "--rot-thigh-right": "-8deg",
          "--rot-shin-right": "12deg",
          duration: 0.85,
          yoyo: true,
          repeat: Math.ceil(dur / 0.85),
          ease: "sine.inOut"
        }, t_start);
      }
    }

    // Mid-shot Expression Switching (scene.expression_change)
    if (scene.expression_change) {
      const expChange = scene.expression_change;
      const t_chg = expChange.at_sec !== undefined ? Number(expChange.at_sec) : (t_start + dur * (Number(expChange.at_ratio) || 0.5));
      const toEmotion = expChange.to_emotion || "fear";
      const targetChar = expChange.character ? getPuppet(expChange.character) : (p2 || p1);
      if (targetChar) {
        applyExpression(targetChar, toEmotion, t_chg, 0.25);
        if (expChange.to_pose) {
          applyPose(targetChar, expChange.to_pose, t_chg, 0.3);
        }
      }
    }

    // Dynamic Infographics Animation (thought_bubble, comparison_card, symbol_infinity, symbol_scales)
    if (scene.infographic_type) {
      const infoType = (scene.infographic_type || "").toLowerCase().trim();
      const infoEl = infoElements[infoType];
      if (infoEl) {
        const t_in = t_start + Math.min(0.25, dur * 0.1);
        const t_out = Math.max(t_in + 0.5, t_end - 0.35);
        masterTl.set(infoEl, { display: "block" }, t_in);
        masterTl.fromTo(infoEl,
          { opacity: 0, scale: 0.65, y: 35 },
          { opacity: 1, scale: 1.0, y: 0, duration: 0.45, ease: "back.out(1.8)" },
          t_in
        );
        if (infoType === "symbol_scales") {
          const crossbeam = infoEl.querySelector("#scale_crossbeam");
          if (crossbeam) {
            masterTl.fromTo(crossbeam,
              { rotation: -6 },
              { rotation: 6, duration: 1.0, yoyo: true, repeat: Math.max(1, Math.floor(dur / 1.2)), ease: "sine.inOut", transformOrigin: "200px 105px" },
              t_in + 0.2
            );
          }
        } else if (infoType === "symbol_infinity") {
          masterTl.to(infoEl, {
            scale: 1.08,
            duration: 0.7,
            yoyo: true,
            repeat: Math.max(1, Math.floor(dur / 0.8)),
            ease: "sine.inOut"
          }, t_in + 0.3);
        }
        masterTl.to(infoEl, { opacity: 0, scale: 0.85, duration: 0.30, ease: "power2.in" }, t_out);
        masterTl.set(infoEl, { display: "none" }, t_out + 0.30);
      }
    }

    // Dynamic VFX Elements Choreography
    vfxElements.forEach(vfxType => {
      const vType = vfxType.toLowerCase().trim();
      const t_vfx = t_start + Math.min(0.2, dur * 0.1);

      if (vType === "laser_beam" && vfxLaser) {
        masterTl.set(vfxLaser, { display: "block", opacity: 1 }, t_vfx);
        const laserCol = vfxLaser.querySelector("#laser_column");
        const impactBurst = vfxLaser.querySelector("#laser_impact_burst");
        const laserCore = vfxLaser.querySelector("#laser_core");

        if (laserCol) {
          masterTl.fromTo(laserCol, { scaleY: 0, opacity: 0 }, { scaleY: 1, opacity: 1, duration: 0.18, ease: "power4.in", transformOrigin: "540px 0px" }, t_vfx);
        }
        if (wrathFlash) {
          masterTl.fromTo(wrathFlash, { opacity: 0 }, { opacity: 0.85, duration: 0.08, ease: "power1.in" }, t_vfx + 0.12);
          masterTl.to(wrathFlash, { opacity: 0, duration: 0.25, ease: "power2.out" }, t_vfx + 0.20);
        }
        if (impactBurst) {
          masterTl.fromTo(impactBurst, { scale: 0.3, opacity: 0 }, { scale: 1.15, opacity: 1, duration: 0.22, ease: "back.out(2)", transformOrigin: "540px 1680px" }, t_vfx + 0.15);
        }
        if (laserCore) {
          masterTl.to(laserCore, { opacity: 0.65, yoyo: true, repeat: 4, duration: 0.05 }, t_vfx + 0.18);
        }
        const fadeDur = Math.min(0.5, dur * 0.3);
        const fadeStart = t_vfx + Math.min(0.6, dur * 0.5);
        masterTl.to(vfxLaser, { opacity: 0, duration: fadeDur, ease: "power2.out" }, fadeStart);
        masterTl.set(vfxLaser, { display: "none" }, fadeStart + fadeDur);
      }
      else if (vType === "sunburst" && vfxSunburst) {
        masterTl.set(vfxSunburst, { display: "block" }, t_vfx);
        masterTl.fromTo(vfxSunburst,
          { opacity: 0, scale: 0.25, rotation: 0 },
          { opacity: 0.90, scale: 1.15, rotation: 35, duration: 0.60, ease: "back.out(1.7)", transformOrigin: "400px 400px" },
          t_vfx
        );
        masterTl.to(vfxSunburst, {
          rotation: 90,
          duration: Math.max(1.5, dur - 0.5),
          ease: "none"
        }, t_vfx + 0.60);
        masterTl.to(vfxSunburst, {
          opacity: 0,
          scale: 1.25,
          duration: 0.45,
          ease: "power2.in"
        }, Math.max(t_vfx + 0.60, t_end - 0.45));
        masterTl.set(vfxSunburst, { display: "none" }, t_end);
      }
      else if (vType === "screen_shatter" && vfxShatter) {
        masterTl.set(vfxShatter, { display: "block" }, t_vfx);
        masterTl.fromTo(vfxShatter,
          { opacity: 0, scale: 0.95 },
          { opacity: 1, scale: 1.0, duration: 0.10, ease: "power4.in" },
          t_vfx
        );
        if (wrathFlash) {
          masterTl.fromTo(wrathFlash, { opacity: 0 }, { opacity: 0.65, duration: 0.08, ease: "power1.in" }, t_vfx + 0.05);
          masterTl.to(wrathFlash, { opacity: 0, duration: 0.20, ease: "power1.out" }, t_vfx + 0.13);
        }
        masterTl.to(stage, { x: 14, duration: 0.03, yoyo: true, repeat: 10, ease: "none" }, t_vfx + 0.08);

        masterTl.to("[id^='shard_nw']", { x: -80, y: -80, rotation: -14, duration: 0.45, ease: "power2.out" }, t_vfx + 0.08);
        masterTl.to("[id^='shard_ne']", { x: 80, y: -80, rotation: 14, duration: 0.45, ease: "power2.out" }, t_vfx + 0.08);
        masterTl.to("[id^='shard_sw']", { x: -80, y: 80, rotation: -12, duration: 0.45, ease: "power2.out" }, t_vfx + 0.08);
        masterTl.to("[id^='shard_se']", { x: 80, y: 80, rotation: 12, duration: 0.45, ease: "power2.out" }, t_vfx + 0.08);
        masterTl.to("[id^='shard_c']", { scale: 1.3, opacity: 0, duration: 0.40, ease: "power2.out" }, t_vfx + 0.08);

        masterTl.to(vfxShatter, { opacity: 0, duration: 0.35, ease: "power2.out" }, t_vfx + 0.40);
        masterTl.set(vfxShatter, { display: "none" }, t_vfx + 0.75);
      }
      else if (vType === "fracture_cracks" && vfxCracks) {
        masterTl.set(vfxCracks, { display: "block" }, t_vfx);
        masterTl.fromTo(vfxCracks,
          { opacity: 0, scaleY: 0.35 },
          { opacity: 0.95, scaleY: 1.0, duration: 0.40, ease: "power3.out", transformOrigin: "540px 1920px" },
          t_vfx
        );
        masterTl.to(stage, { y: 8, duration: 0.04, yoyo: true, repeat: 8, ease: "none" }, t_vfx + 0.15);
        const baseGlow = vfxCracks.querySelector("#fracture_base_glow");
        if (baseGlow) {
          masterTl.to(baseGlow, { opacity: 0.95, duration: 0.35, yoyo: true, repeat: Math.max(2, Math.floor(dur / 0.7)), ease: "sine.inOut" }, t_vfx + 0.30);
        }
        masterTl.to(vfxCracks, { opacity: 0, duration: 0.50, ease: "power2.in" }, Math.max(t_vfx + 0.50, t_end - 0.50));
        masterTl.set(vfxCracks, { display: "none" }, t_end);
      }
      else if (vType === "sound_ripple" && vfxRipple) {
        masterTl.set(vfxRipple, { display: "block" }, t_vfx);
        masterTl.fromTo(vfxRipple,
          { opacity: 0, scale: 0.30 },
          { opacity: 0.90, scale: 1.0, duration: 0.45, ease: "sine.out", transformOrigin: "540px 540px" },
          t_vfx
        );
        const r1 = vfxRipple.querySelector("#ripple_ring_1");
        const r2 = vfxRipple.querySelector("#ripple_ring_2");
        if (r1) {
          masterTl.fromTo(r1, { scale: 0.8, opacity: 1 }, { scale: 1.6, opacity: 0, duration: 1.0, ease: "power2.out", transformOrigin: "540px 540px", repeat: Math.max(1, Math.floor(dur / 1.3)) }, t_vfx + 0.1);
        }
        if (r2) {
          masterTl.fromTo(r2, { scale: 0.8, opacity: 0.9 }, { scale: 1.5, opacity: 0, duration: 1.2, delay: 0.2, ease: "power2.out", transformOrigin: "540px 540px", repeat: Math.max(1, Math.floor(dur / 1.3)) }, t_vfx + 0.2);
        }
        masterTl.to(vfxRipple, { opacity: 0, duration: 0.45, ease: "power2.in" }, Math.max(t_vfx + 0.50, t_end - 0.45));
        masterTl.set(vfxRipple, { display: "none" }, t_end);
      }
    });
  });

  // =========================================================================
  // THEATRICAL OUTRO & CURTAIN CALL (Manifest-Aware or Default End Sequence)
  // =========================================================================
  if (manifest.outro !== false && total_dur >= 6.0) {
    const t_outro = Math.max(0, total_dur - 3.5);

    if (outroMarquee) {
      masterTl.set(outroMarquee, { display: "block" }, t_outro);
      masterTl.fromTo(outroMarquee,
        { opacity: 0, scale: 0.6, y: 60 },
        { opacity: 1, scale: 1.0, y: 0, duration: 0.75, ease: "back.out(2)" },
        t_outro + 0.2
      );
    }

    // Cast Lineup (up to 4 puppets across stage in blessing pose)
    const castPuppets = allPuppets.slice(0, 4);
    const castCount = castPuppets.length;
    const xOffsets = castCount === 1 ? [0] :
                     castCount === 2 ? [-180, 180] :
                     castCount === 3 ? [-250, 0, 250] :
                     [-300, -100, 100, 300];

    castPuppets.forEach((p, cIdx) => {
      const xTarget = xOffsets[cIdx] || 0;
      const facing = xTarget > 0 ? -1 : 1;
      masterTl.set(p, { display: "block" }, t_outro);
      masterTl.to(p, {
        opacity: 1,
        scale: 0.95,
        scaleX: 0.95 * facing,
        x: xTarget,
        y: 280,
        duration: 0.8,
        ease: "power2.out"
      }, t_outro);
      applyPose(p, "blessing_calm", t_outro, 0.6);
      applyExpression(p, "joy", t_outro, 0.4);
    });

    // Curtains close shut
    if (curtains.left && curtains.right) {
      masterTl.to(curtains.left, { xPercent: 0, duration: 1.5, ease: "power2.inOut" }, total_dur - 1.8);
      masterTl.to(curtains.right, { xPercent: 0, duration: 1.5, ease: "power2.inOut" }, total_dur - 1.8);
    }
  }

  // Smooth final fade to black
  masterTl.to(stage, {
    opacity: 0,
    duration: 0.70,
    ease: "power2.in"
  }, Math.max(0, total_dur - 0.70));

  window.__timelines["main"] = masterTl;
  console.log(`[ENGINE] Registered master timeline 'main' with duration: ${total_dur.toFixed(2)}s`);
}

document.addEventListener("DOMContentLoaded", initTimeline);
"""


def generate_root_composition(root: Optional[Path] = None) -> dict[str, Any]:
    if root is None:
        root = get_project_root()

    cfg = load_config(root)
    build_dir = (root / cfg["paths"]["build_dir"]).resolve()
    build_dir.mkdir(parents=True, exist_ok=True)

    manifest_file = build_dir / "manifest.js"
    if not manifest_file.is_file():
        default_js = (
            "// Default placeholder manifest for HyperFrames inspection\n"
            f"window.EPISODE_MANIFEST = {json.dumps(FALLBACK_MANIFEST, indent=2)};\n"
        )
        manifest_file.write_text(default_js, encoding="utf-8")

    manifest = load_manifest(build_dir)
    lang = manifest.get("language", cfg.get("channel", {}).get("primary_language", "en"))
    total_dur = float(manifest.get("audio", {}).get("total_duration_sec", 41.50))
    render_dur = round(total_dur + 0.30, 2)

    svg_root = root / "assets" / "svg"
    backdrops_dir = svg_root / "backdrops"
    characters_dir = svg_root / "characters"
    diagrams_dir = svg_root / "diagrams"

    scenes = manifest.get("scenes") or manifest.get("beats") or []
    if not scenes:
        scenes = FALLBACK_MANIFEST["scenes"]

    # 1. Resolve Backdrops and Diagrams for each scene
    scenes_html: list[str] = []
    referenced_characters: list[str] = []

    for i, sc in enumerate(scenes):
        shot_num = i + 1
        shot_type = sc.get("shot_type", "character_medium").lower()

        # Resolve Backdrop
        bg_rig = sc.get("backdrop_rig")
        bg_svg_content = ""
        if bg_rig:
            bg_path = backdrops_dir / f"{bg_rig}.svg"
            if bg_path.is_file():
                bg_svg_content = bg_path.read_text(encoding="utf-8")
        if not bg_svg_content:
            # Fallback backdrops based on scene index or available
            candidates = ["golden_lanka_citadel", "mount_kailash", "crushed_atmosphere", "celestial_cosmos_court", "ancient_nalanda_courtyard"]
            for cand in candidates:
                p = backdrops_dir / f"{cand}.svg"
                if p.is_file():
                    bg_svg_content = p.read_text(encoding="utf-8")
                    break

        if not bg_svg_content:
            raise CompositionError("No valid backdrop SVG found in assets/svg/backdrops/")

        # Optional Diagram
        diagram_html = ""
        diag_rig = sc.get("diagram_rig")
        if not diag_rig and sc.get("bespoke_diagram_asset"):
            diag_rig = Path(sc["bespoke_diagram_asset"]).stem
        if not diag_rig and sc.get("diagram_asset"):
            diag_rig = Path(sc["diagram_asset"]).stem
        if diag_rig:
            diag_path = diagrams_dir / f"{diag_rig}.svg"
            if diag_path.is_file():
                diagram_html = f"""      <!-- Bespoke Diagram: {diag_rig} -->
      <div class="diagram-wrapper" data-layout-ignore="true">
        {diag_path.read_text(encoding='utf-8')}
      </div>"""

        # Curtains for Establishing Shot
        curtains_html = ""
        if i == 0 and ("curtain" in shot_type or "establishing" in shot_type):
            curtains_html = """      <!-- Royal Velvet Curtains Parting -->
      <div id="curtain_left" class="curtain" data-layout-ignore="true">
        <div class="curtain-fold" style="left: 60px;"></div>
        <div class="curtain-fold" style="left: 180px;"></div>
        <div class="curtain-fold" style="left: 300px;"></div>
        <div class="curtain-fold" style="left: 420px;"></div>
      </div>
      <div id="curtain_right" class="curtain" data-layout-ignore="true">
        <div class="curtain-fold" style="right: 60px;"></div>
        <div class="curtain-fold" style="right: 180px;"></div>
        <div class="curtain-fold" style="right: 300px;"></div>
        <div class="curtain-fold" style="right: 420px;"></div>
      </div>"""

        # Optional Foreground
        fg_html = ""
        fg_rig = sc.get("foreground_rig")
        if fg_rig:
            fg_path = backdrops_dir / f"{fg_rig}.svg"
            if fg_path.is_file():
                fg_html = f"""      <div class="foreground-wrapper" data-layout-ignore="true">
        {fg_path.read_text(encoding='utf-8')}
      </div>"""
        elif (shot_num == 5 or "crushed" in shot_type) and (backdrops_dir / "granite_underside.svg").is_file():
            granite_svg = (backdrops_dir / "granite_underside.svg").read_text(encoding="utf-8")
            fg_html = f"""      <div id="foreground_mountain_container" class="foreground-wrapper" data-layout-ignore="true">
        {granite_svg}
      </div>"""

        active_cls = " active-shot" if i == 0 else ""
        shot_html = f"""    <!-- SHOT {shot_num}: ({shot_type}) -->
    <div id="shot_{shot_num}_container" class="shot-container{active_cls}" data-shot-type="{shot_type}" data-layout-allow-overflow="true" data-layout-ignore="true">
      <div class="bg-svg" data-layout-ignore="true">
        {bg_svg_content}
      </div>
{curtains_html}
{diagram_html}
{fg_html}
    </div>"""
        scenes_html.append(shot_html)

        # Collect referenced characters
        for char_key in ("primary_character", "secondary_character", "tertiary_character"):
            c_val = sc.get(char_key)
            if c_val and c_val not in referenced_characters:
                referenced_characters.append(c_val)
        if sc.get("characters"):
            for c_val in sc["characters"]:
                if c_val and c_val not in referenced_characters:
                    referenced_characters.append(c_val)
        if sc.get("expression_change") and sc["expression_change"].get("character"):
            c_val = sc["expression_change"]["character"]
            if c_val and c_val not in referenced_characters:
                referenced_characters.append(c_val)

    # If no characters referenced in scenes, default to ravana or available character
    if not referenced_characters:
        if (characters_dir / "ravana.svg").is_file():
            referenced_characters.append("ravana")
        else:
            avail = [p.stem for p in characters_dir.glob("*.svg")]
            if avail:
                referenced_characters.append(avail[0])

    # 2. Embed Character Puppets
    puppets_html: list[str] = []
    for idx, c_name in enumerate(referenced_characters):
        char_path = characters_dir / f"{c_name}.svg"
        if not char_path.is_file():
            continue
        char_svg = char_path.read_text(encoding="utf-8")
        # Ensure the primary puppet has #puppet_wrapper for backward compatibility
        wrapper_id = "puppet_wrapper" if idx == 0 else f"puppet_{c_name}"
        p_html = f"""    <div id="{wrapper_id}" class="puppet-wrapper puppet-char" data-character="{c_name}" data-layout-allow-overflow="true" data-layout-ignore="true">
      {char_svg}
    </div>"""
        puppets_html.append(p_html)

    # 3. Resolve Dynamic VFX Elements
    vfx_dir = svg_root / "vfx"
    vfx_elements_html: list[str] = []
    vfx_assets = [
        ("vfx_laser_beam_container", "laser_beam.svg"),
        ("vfx_sunburst_container", "sunburst.svg"),
        ("vfx_screen_shatter_container", "screen_shatter.svg"),
        ("vfx_fracture_cracks_container", "fracture_cracks.svg"),
        ("vfx_sound_ripple_container", "sound_ripple.svg"),
    ]
    for container_id, filename in vfx_assets:
        file_path = vfx_dir / filename
        if file_path.is_file():
            svg_text = file_path.read_text(encoding="utf-8")
            if "data-layout-ignore" not in svg_text:
                svg_text = svg_text.replace("<svg ", '<svg data-layout-ignore="true" ', 1)
            vfx_elements_html.append(
                f'      <div id="{container_id}" class="vfx-element" data-layout-ignore="true">\n'
                f"        {svg_text}\n"
                f"      </div>"
            )
    vfx_html = "\n".join(vfx_elements_html)

    # 4. Resolve Infographic Elements
    infographics_dir = svg_root / "infographics"
    infographics_elements_html: list[str] = []
    infographic_assets = [
        ("infographic_thought_bubble_container", "thought_bubble.svg"),
        ("infographic_comparison_card_container", "comparison_card.svg"),
        ("infographic_symbol_infinity_container", "symbol_infinity.svg"),
        ("infographic_symbol_scales_container", "symbol_scales.svg"),
    ]
    for container_id, filename in infographic_assets:
        file_path = infographics_dir / filename
        if file_path.is_file():
            svg_text = file_path.read_text(encoding="utf-8")
            if "data-layout-ignore" not in svg_text:
                svg_text = svg_text.replace("<svg ", '<svg data-layout-ignore="true" ', 1)
            infographics_elements_html.append(
                f'      <div id="{container_id}" class="infographic-element" data-layout-ignore="true">\n'
                f"        {svg_text}\n"
                f"      </div>"
            )
    infographics_html = "\n".join(infographics_elements_html)

    # 5. Theatrical Outro Marquee
    outro_marquee_html = ""
    marquee_path = infographics_dir / "outro_marquee.svg"
    if marquee_path.is_file():
        svg_text = marquee_path.read_text(encoding="utf-8")
        if "data-layout-ignore" not in svg_text:
            svg_text = svg_text.replace("<svg ", '<svg data-layout-ignore="true" ', 1)
        outro_marquee_html = (
            f'    <div id="outro_marquee_container" data-layout-ignore="true">\n'
            f"      {svg_text}\n"
            f"    </div>"
        )

    # 6. Write styles.css
    styles_path = root / "styles.css"
    styles_path.write_text(generate_styles_css(), encoding="utf-8")

    # 7. Write engine.js
    engine_path = root / "engine.js"
    engine_path.write_text(generate_engine_js(), encoding="utf-8")

    # 8. Write index.html
    index_path = root / "index.html"
    index_content = generate_index_html(
        lang=lang,
        duration_sec=render_dur,
        scenes_html=scenes_html,
        puppets_html=puppets_html,
        vfx_html=vfx_html,
        infographics_html=infographics_html,
        outro_marquee_html=outro_marquee_html,
    )
    index_path.write_text(index_content, encoding="utf-8")

    return {
        "status": "ok",
        "action": "generate_composition",
        "language": lang,
        "duration_sec": render_dur,
        "scenes_count": len(scenes),
        "characters": referenced_characters,
        "index_html": str(index_path),
        "styles_css": str(styles_path),
        "engine_js": str(engine_path),
    }


def main() -> int:
    if len(sys.argv) > 1:
        print("[ERROR] scripts/generate_composition.py takes zero CLI arguments.", file=sys.stderr)
        return 1
    try:
        res = generate_root_composition()
        print(json.dumps(res, indent=2))
        return 0
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
