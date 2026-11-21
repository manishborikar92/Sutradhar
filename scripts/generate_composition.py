#!/usr/bin/env python3
"""Sutradhar Composition Generator & Multi-Shot Synchronizer.

Generates root `index.html`, `styles.css`, and `engine.js` from the active
assets/svg/ and build/manifest.js (or fallback manifest).

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
            "shot_type": "wide_establishing",
            "speaker_role": "narrator",
            "narration_text": "Beneath the golden spires of Lanka, ten crowned heads plotted what no mortal dared imagine.",
            "start_sec": 0.0,
            "end_sec": 7.42,
            "duration_sec": 7.42,
            "midpoint_sec": 3.71,
        },
        {
            "scene_index": 2,
            "shot_type": "character_advance",
            "speaker_role": "narrator",
            "narration_text": "King Ravana rose in fury, his ten heads burning with supreme defiance across the ancient earth.",
            "start_sec": 7.42,
            "end_sec": 14.85,
            "duration_sec": 7.43,
            "midpoint_sec": 11.14,
        },
        {
            "scene_index": 3,
            "shot_type": "close_up_wrath",
            "speaker_role": "character_dialogue",
            "narration_text": "Tremble Himalayas! Lanka's sovereign bows to no god!",
            "start_sec": 14.85,
            "end_sec": 21.20,
            "duration_sec": 6.35,
            "midpoint_sec": 18.02,
        },
        {
            "scene_index": 4,
            "shot_type": "cosmic_strike",
            "speaker_role": "narrator",
            "narration_text": "At Mount Kailash, Mahadev pressed a single toe upon the summit, splitting the bedrock beneath.",
            "start_sec": 21.20,
            "end_sec": 31.45,
            "duration_sec": 10.25,
            "midpoint_sec": 26.32,
        },
        {
            "scene_index": 5,
            "shot_type": "crushed_submission",
            "speaker_role": "narrator",
            "narration_text": "The mountain pressed down, trapping the sovereign until his arrogance dissolved into eternal hymns of praise.",
            "start_sec": 31.45,
            "end_sec": 41.50,
            "duration_sec": 10.05,
            "midpoint_sec": 36.48,
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
    return """/* Sutradhar v2.2 Master Theatrical Styles (Clean Canvas, Folk Art) */
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

/* Shot Containers */
.shot-container {
  width: 1080px;
  height: 1920px;
  position: absolute;
  top: 0;
  left: 0;
  overflow: hidden;
  opacity: 0;
  display: none;
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

/* Velvet Theatrical Curtains (Shot 1) */
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

/* Puppet Wrapper */
#puppet_wrapper {
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

/* Shot 5 Granite Foregound Container */
#foreground_mountain_container {
  position: absolute;
  top: -80px;
  left: 0;
  width: 1080px;
  height: 1920px;
  z-index: 60;
  pointer-events: none;
}

/* ========================================================================= */
/* HIERARCHICAL RIVET RIG (CSS Custom Properties with 0px 0px Joint Origins) */
/* ========================================================================= */
#leg_left_group {
  transform: rotate(var(--rot-thigh-left, 0deg)) !important;
  transform-origin: 0px 0px !important;
}
#shin_left_rot {
  transform: rotate(var(--rot-shin-left, 0deg)) !important;
  transform-origin: 0px 0px !important;
}

#leg_right_group {
  transform: rotate(var(--rot-thigh-right, 0deg)) !important;
  transform-origin: 0px 0px !important;
}
#shin_right_rot {
  transform: rotate(var(--rot-shin-right, 0deg)) !important;
  transform-origin: 0px 0px !important;
}

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

#shoulder_front_left_rot {
  transform: rotate(var(--rot-shoulder-front-left, 0deg)) !important;
  transform-origin: 0px 0px !important;
}
#elbow_front_left_rot {
  transform: rotate(var(--rot-elbow-front-left, 0deg)) !important;
  transform-origin: 0px 0px !important;
}
#wrist_front_left_rot {
  transform: rotate(var(--rot-wrist-front-left, 0deg)) !important;
  transform-origin: 0px 0px !important;
}

#shoulder_front_right_rot {
  transform: rotate(var(--rot-shoulder-front-right, 0deg)) !important;
  transform-origin: 0px 0px !important;
}
#elbow_front_right_rot {
  transform: rotate(var(--rot-elbow-front-right, 0deg)) !important;
  transform-origin: 0px 0px !important;
}
#wrist_front_right_rot {
  transform: rotate(var(--rot-wrist-front-right, 0deg)) !important;
  transform-origin: 0px 0px !important;
}

#torso_group {
  transform: translate(var(--trans-torso-x, 0px), var(--trans-torso-y, 0px)) rotate(var(--rot-torso, 0deg)) !important;
  transform-origin: 400px 700px !important;
}
#kamarband {
  transform: translate(var(--trans-torso-x, 0px), var(--trans-torso-y, 0px)) !important;
}
#dhoti_skirt {
  transform: translate(var(--trans-torso-x, 0px), var(--trans-torso-y, 0px)) !important;
}
#hip_left_joint {
  transform: translate(340px, calc(770px + var(--trans-torso-y, 0px))) !important;
}
#hip_right_joint {
  transform: translate(460px, calc(770px + var(--trans-torso-y, 0px))) !important;
}
#heads_fan_mount {
  transform: translate(400px, calc(375px + var(--trans-torso-y, 0px))) rotate(var(--rot-torso, 0deg)) !important;
}
#prabhavali_mount {
  transform: translate(400px, calc(345px + var(--trans-torso-y, 0px))) rotate(var(--rot-torso, 0deg)) !important;
}
#wrath_mount {
  transform: translate(400px, calc(310px + var(--trans-torso-y, 0px))) !important;
}
"""


def generate_index_html(
    lang: str,
    duration_sec: float,
    lanka_svg: str,
    kailash_svg: str,
    granite_svg: str,
    crushed_atmosphere_svg: str,
    ravana_svg: str,
) -> str:
    title = f"Sutradhar Shorts Composition ({lang.upper()}) - Clean Canvas"
    comp_id = "main"

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

    <!-- SHOT 1: FULL-BLEED LANKA CITADEL & VISTA (Beat 1) -->
    <div id="shot_1_container" class="shot-container active-shot" data-layout-allow-overflow="true" data-layout-ignore="true">
      <div class="bg-svg" data-layout-ignore="true">
        {lanka_svg}
      </div>
      <!-- Royal Velvet Curtains Parting -->
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
      </div>
    </div>

    <!-- SHOT 2: ROYAL SANDSTONE COURT ADVANCE (Beat 2) -->
    <div id="shot_2_container" class="shot-container" data-layout-allow-overflow="true" data-layout-ignore="true">
      <div class="bg-svg" data-layout-ignore="true">
        {lanka_svg}
      </div>
    </div>

    <!-- SHOT 3: WRATHFUL CLOSE-UP & DIALOGUE (Beat 3) -->
    <div id="shot_3_container" class="shot-container" data-layout-allow-overflow="true" data-layout-ignore="true">
      <div class="bg-svg" data-layout-ignore="true">
        {lanka_svg}
      </div>
    </div>

    <!-- SHOT 4: MOUNT KAILASH COSMIC STRIKE (Beat 4) -->
    <div id="shot_4_container" class="shot-container" data-layout-allow-overflow="true" data-layout-ignore="true">
      <div class="bg-svg" data-layout-ignore="true">
        {kailash_svg}
      </div>
    </div>

    <!-- SHOT 5: FOREGROUND GRANITE CRUSHING CROUCHED RAVANA (Beat 5) -->
    <div id="shot_5_container" class="shot-container" data-layout-allow-overflow="true" data-layout-ignore="true">
      <div class="bg-svg" data-layout-ignore="true">
        {crushed_atmosphere_svg}
      </div>
      <!-- FOREGROUND GRANITE UNDERSIDE: Mountain physically presses DOWN -->
      <div id="foreground_mountain_container" data-layout-ignore="true">
        {granite_svg}
      </div>
    </div>

    <!-- CENTRAL KATHPUTLI PUPPET RIG (Shared across Shots 2, 3, 5) -->
    <div id="puppet_wrapper" data-layout-allow-overflow="true" data-layout-ignore="true">
      {ravana_svg}
    </div>

  </div>
</body>
</html>
"""


def generate_engine_js() -> str:
    return """// Sutradhar v2.2 Master Choreography Engine
// Reads dynamic audio duration & scene timings from window.EPISODE_MANIFEST
window.__timelines = window.__timelines || {};

function initTimeline() {
  const manifest = window.EPISODE_MANIFEST || window.__audio_manifest;
  if (!manifest) {
    console.error("[ERROR] No EPISODE_MANIFEST found in window.");
    return;
  }

  const scenes = manifest.scenes || manifest.beats || [];
  if (scenes.length < 5) {
    console.error("[ERROR] EPISODE_MANIFEST must have at least 5 scenes/beats for multi-shot Kathputli.", scenes);
    return;
  }

  const lang = manifest.language || "en";
  const b1 = scenes[0];
  const b2 = scenes[1];
  const b3 = scenes[2];
  const b4 = scenes[3];
  const b5 = scenes[4];

  const t_shot1_start = Number(b1.start_sec);
  const t_shot1_end = Number(b1.end_sec);

  const t_shot2_start = Number(b2.start_sec);
  const t_shot2_end = Number(b2.end_sec);

  const t_shot3_start = Number(b3.start_sec);
  const t_shot3_end = Number(b3.end_sec);

  const t_shot4_start = Number(b4.start_sec);
  const t_shot4_end = Number(b4.end_sec);

  const t_shot5_start = Number(b5.start_sec);
  const t_shot5_end = Number(b5.end_sec);

  // Dynamic strike time in Shot 4
  const s4_dur = t_shot4_end - t_shot4_start;
  const t_strike = lang === "hi"
    ? t_shot4_start + Math.min(2.40, s4_dur * 0.40)
    : t_shot4_start + Math.min(1.25, s4_dur * 0.35);

  const total_dur = Number(manifest.audio?.total_duration_sec || t_shot5_end);

  const masterTl = gsap.timeline({ paused: true });

  // Select Stage & Shot Containers
  const stage = document.querySelector("#stage");
  const shot1 = document.querySelector("#shot_1_container");
  const shot2 = document.querySelector("#shot_2_container");
  const shot3 = document.querySelector("#shot_3_container");
  const shot4 = document.querySelector("#shot_4_container");
  const shot5 = document.querySelector("#shot_5_container");

  const curtainLeft = document.querySelector("#curtain_left");
  const curtainRight = document.querySelector("#curtain_right");
  const puppet = document.querySelector("#puppet_wrapper");
  const wrathFlash = document.querySelector("#wrath_flash");
  const embers = document.querySelectorAll(".ember");

  // Puppet elements inside SVG
  const wrathSunburst = puppet.querySelector("#wrath_sunburst");
  const browsNeutral = puppet.querySelector("#brows_neutral");
  const browsAngry = puppet.querySelector("#brows_angry");
  const eyesNormal = puppet.querySelector("#eyes_normal");
  const eyesWrath = puppet.querySelector("#eyes_wrath");
  const mouthCalm = puppet.querySelector("#mouth_calm");
  const mouthTalk = puppet.querySelector("#mouth_talk");
  const mouthShout = puppet.querySelector("#mouth_shout");
  const headCenter = puppet.querySelector("#head_center");
  const headsFan = puppet.querySelector("#heads_fan");

  // Shot 4 Kailash strike elements
  const divineLaser = shot4.querySelector("#divine_laser_beam");
  const strikeFractures = shot4.querySelector("#strike_fractures");
  const shockwave1 = shot4.querySelector("#shockwave_ring1");
  const shockwave2 = shot4.querySelector("#shockwave_ring2");
  const shockwave3 = shot4.querySelector("#shockwave_ring3");
  const boulders = shot4.querySelector("#falling_boulders");

  // Shot 5 Granite Foreground elements
  const fgMountain = document.querySelector("#foreground_mountain_container");
  const contactSparks = fgMountain ? fgMountain.querySelector("#contact_sparks") : null;

  // Initial Puppet Rig Styling
  gsap.set(puppet, {
    display: "none",
    opacity: 0,
    "--trans-torso-x": "0px",
    "--trans-torso-y": "0px",
    "--rot-torso": "0deg",
    "--rot-shoulder-rear-left": "0deg",
    "--rot-elbow-rear-left": "0deg",
    "--rot-wrist-rear-left": "0deg",
    "--rot-shoulder-rear-right": "0deg",
    "--rot-elbow-rear-right": "0deg",
    "--rot-wrist-rear-right": "0deg",
    "--rot-shoulder-front-left": "0deg",
    "--rot-elbow-front-left": "0deg",
    "--rot-wrist-front-left": "0deg",
    "--rot-shoulder-front-right": "0deg",
    "--rot-elbow-front-right": "0deg",
    "--rot-wrist-front-right": "0deg",
    "--rot-thigh-left": "0deg",
    "--rot-shin-left": "0deg",
    "--rot-thigh-right": "0deg",
    "--rot-shin-right": "0deg"
  });

  if (browsNeutral) gsap.set(browsNeutral, { opacity: 1 });
  if (browsAngry) gsap.set(browsAngry, { opacity: 0 });
  if (eyesNormal) gsap.set(eyesNormal, { opacity: 1 });
  if (eyesWrath) gsap.set(eyesWrath, { opacity: 0 });
  if (mouthCalm) gsap.set(mouthCalm, { opacity: 1 });
  if (mouthTalk) gsap.set(mouthTalk, { opacity: 0 });
  if (mouthShout) gsap.set(mouthShout, { opacity: 0 });
  if (wrathSunburst) gsap.set(wrathSunburst, { opacity: 0 });
  if (wrathFlash) gsap.set(wrathFlash, { opacity: 0 });

  // Continuous floating embers
  embers.forEach((ember, i) => {
    const dur = 4.5 + (i % 3) * 1.2;
    const delay = (i * 0.4) % 3.0;
    masterTl.fromTo(ember,
      { y: 1950, x: "+=" + ((i % 4) * 35 - 50), opacity: 0 },
      { y: -60, opacity: 0.85, duration: dur, ease: "none", repeat: 8 },
      delay
    );
  });

  // =========================================================================
  // SHOT 1 (t_shot1_start -> t_shot1_end): FULL-BLEED LANKA VISTA (Beat 1)
  // =========================================================================
  masterTl.set(shot1, { display: "block", opacity: 1 }, 0.0);
  // Parting velvet curtains
  if (curtainLeft && curtainRight) {
    masterTl.to(curtainLeft, { xPercent: -102, duration: 1.8, ease: "power2.inOut" }, 0.4);
    masterTl.to(curtainRight, { xPercent: 102, duration: 1.8, ease: "power2.inOut" }, 0.4);
  }
  // Majestic slow push-in on golden citadel
  masterTl.to(shot1, { scale: 1.18, y: -25, duration: t_shot1_end, ease: "sine.inOut" }, 0.0);

  // Transition 1 -> 2 (Smooth 0.30s Cross-Dissolve)
  const t_trans1 = Math.max(0, t_shot1_end - 0.30);
  masterTl.set(shot2, { display: "block", opacity: 0 }, t_trans1);
  masterTl.to(shot1, { opacity: 0, duration: 0.30, ease: "power2.inOut" }, t_trans1);
  masterTl.to(shot2, { opacity: 1, duration: 0.30, ease: "power2.inOut" }, t_trans1);
  masterTl.set(shot1, { display: "none" }, t_shot1_end);

  // =========================================================================
  // SHOT 2 (t_shot2_start -> t_shot2_end): ROYAL THRONE COURT ADVANCE (Beat 2)
  // =========================================================================
  masterTl.set(puppet, {
    display: "block",
    opacity: 1,
    scale: 1.15,
    x: 0,
    y: 120
  }, t_shot2_start);

  masterTl.fromTo(shot2, { scale: 1.0 }, { scale: 1.08, duration: t_shot2_end - t_shot2_start, ease: "sine.inOut" }, t_shot2_start);

  // Puppet stride kinematics
  masterTl.to(puppet, {
    "--rot-thigh-left": "8deg",
    "--rot-shin-left": "-12deg",
    duration: 0.85,
    yoyo: true,
    repeat: Math.ceil((t_shot2_end - t_shot2_start) / 0.85),
    ease: "sine.inOut"
  }, t_shot2_start);

  masterTl.to(puppet, {
    "--rot-thigh-right": "-8deg",
    "--rot-shin-right": "12deg",
    duration: 0.85,
    yoyo: true,
    repeat: Math.ceil((t_shot2_end - t_shot2_start) / 0.85),
    ease: "sine.inOut"
  }, t_shot2_start);

  // Heroic inward weapon brandishing (zero clipping)
  masterTl.to(puppet, {
    "--rot-shoulder-rear-left": "-28deg",
    "--rot-elbow-rear-left": "22deg",
    "--rot-shoulder-rear-right": "28deg",
    "--rot-elbow-rear-right": "-22deg",
    "--rot-shoulder-front-left": "-18deg",
    "--rot-elbow-front-left": "25deg",
    "--rot-shoulder-front-right": "18deg",
    "--rot-elbow-front-right": "-25deg",
    duration: 1.4,
    ease: "power2.out"
  }, t_shot2_start + 0.3);

  if (headsFan) {
    masterTl.to(headsFan, { rotation: -2.5, duration: 1.6, yoyo: true, repeat: 2, ease: "sine.inOut", transformOrigin: "0px 60px" }, t_shot2_start + 0.5);
  }

  // Transition 2 -> 3 (Punch-in Zoom + Flash)
  const t_trans2 = t_shot3_start;
  masterTl.set(shot2, { display: "none" }, t_trans2);
  masterTl.set(shot3, { display: "block", opacity: 1 }, t_trans2);

  // =========================================================================
  // SHOT 3 (t_shot3_start -> t_shot3_end): WRATHFUL DIALOGUE & CLIMAX (Beat 3)
  // =========================================================================
  masterTl.to(puppet, { scale: 2.15, y: 520, duration: 0.35, ease: "power3.out" }, t_trans2);

  // Scarlet wrath flash
  if (wrathFlash) {
    masterTl.fromTo(wrathFlash, { opacity: 0 }, { opacity: 0.50, duration: 0.08, ease: "power1.in" }, t_trans2);
    masterTl.to(wrathFlash, { opacity: 0, duration: 0.20, ease: "power1.out" }, t_trans2 + 0.08);
  }

  // Wrath sunburst rotation
  if (wrathSunburst) {
    masterTl.fromTo(wrathSunburst,
      { opacity: 0, scale: 0.85, rotation: 0 },
      { opacity: 0.65, scale: 1.05, duration: 0.45, ease: "back.out(2)", transformOrigin: "0px 0px" },
      t_trans2 + 0.05
    );
    masterTl.to(wrathSunburst,
      { rotation: 50, duration: t_shot3_end - t_shot3_start, ease: "none" },
      t_trans2 + 0.05
    );
  }

  // Facial expression swap
  if (browsNeutral && browsAngry) {
    masterTl.to(browsNeutral, { opacity: 0, duration: 0.15 }, t_trans2 + 0.1);
    masterTl.to(browsAngry, { opacity: 1, duration: 0.15 }, t_trans2 + 0.1);
  }
  if (eyesNormal && eyesWrath) {
    masterTl.to(eyesNormal, { opacity: 0, duration: 0.15 }, t_trans2 + 0.1);
    masterTl.to(eyesWrath, { opacity: 1, duration: 0.15 }, t_trans2 + 0.1);
  }

  // Lip-sync articulation
  if (mouthCalm && mouthTalk && mouthShout) {
    masterTl.set(mouthCalm, { opacity: 0 }, t_trans2 + 0.15);
    masterTl.set(mouthTalk, { opacity: 1 }, t_trans2 + 0.15);

    masterTl.set(mouthTalk, { opacity: 0 }, t_trans2 + 0.65);
    masterTl.set(mouthShout, { opacity: 1 }, t_trans2 + 0.65);

    masterTl.set(mouthShout, { opacity: 0 }, t_trans2 + 1.45);
    masterTl.set(mouthTalk, { opacity: 1 }, t_trans2 + 1.45);

    masterTl.set(mouthTalk, { opacity: 0 }, t_trans2 + 2.15);
    masterTl.set(mouthShout, { opacity: 1 }, t_trans2 + 2.15);
  }

  if (headCenter) {
    masterTl.to(headCenter, { scale: 1.18, duration: 0.35, ease: "power2.out" }, t_trans2 + 0.2);
  }
  if (headsFan) {
    masterTl.to(headsFan, { rotation: 3, duration: 0.16, yoyo: true, repeat: 14, ease: "sine.inOut", transformOrigin: "0px 60px" }, t_trans2 + 0.3);
  }

  // Transition 3 -> 4 (Smooth 0.30s Cross-Dissolve to Kailash)
  const t_trans3 = Math.max(0, t_shot4_start - 0.30);
  masterTl.set(shot4, { display: "block", opacity: 0 }, t_trans3);
  masterTl.to(shot3, { opacity: 0, duration: 0.30, ease: "power2.inOut" }, t_trans3);
  masterTl.to(puppet, { opacity: 0, duration: 0.25, ease: "power2.inOut" }, t_trans3);
  masterTl.to(shot4, { opacity: 1, duration: 0.30, ease: "power2.inOut" }, t_trans3);
  masterTl.set(shot3, { display: "none" }, t_shot4_start);
  masterTl.set(puppet, { display: "none" }, t_shot4_start);

  // =========================================================================
  // SHOT 4 (t_shot4_start -> t_shot4_end): MOUNT KAILASH COSMIC STRIKE (Beat 4)
  // =========================================================================
  masterTl.fromTo(shot4, { scale: 1.0 }, { scale: 1.12, duration: t_shot4_end - t_shot4_start, ease: "sine.out" }, t_shot4_start);

  // Divine laser strike at t_strike
  if (divineLaser) {
    masterTl.fromTo(divineLaser,
      { opacity: 0, scaleY: 0 },
      { opacity: 1, scaleY: 1, duration: 0.16, ease: "power4.in", transformOrigin: "540px 0px" },
      t_strike
    );
    masterTl.to(divineLaser, { opacity: 0, duration: 0.40, ease: "power2.out" }, t_strike + 0.22);
  }

  // Strike flash
  if (wrathFlash) {
    masterTl.fromTo(wrathFlash,
      { opacity: 0 },
      { opacity: 0.85, duration: 0.08, ease: "power1.in", immediateRender: false },
      t_strike + 0.12
    );
    masterTl.to(wrathFlash, { opacity: 0, duration: 0.32, ease: "power2.out" }, t_strike + 0.20);
  }

  // Kailash fault line fractures appear
  if (strikeFractures) {
    masterTl.to(strikeFractures, { opacity: 1, duration: 0.15 }, t_strike + 0.15);
  }

  // Expanding shockwaves
  if (shockwave1) {
    masterTl.fromTo(shockwave1,
      { opacity: 1, attr: { rx: 90, ry: 32 } },
      { opacity: 0, attr: { rx: 420, ry: 150 }, duration: 1.1, ease: "power2.out" },
      t_strike + 0.15
    );
  }
  if (shockwave2) {
    masterTl.fromTo(shockwave2,
      { opacity: 0.9, attr: { rx: 120, ry: 40 } },
      { opacity: 0, attr: { rx: 650, ry: 220 }, duration: 1.3, ease: "power2.out" },
      t_strike + 0.30
    );
  }

  // Stage camera rumble
  masterTl.to(stage, { x: 20, duration: 0.04, yoyo: true, repeat: 18, ease: "none" }, t_strike + 0.15);

  // Falling boulders
  if (boulders) {
    masterTl.to(boulders, { opacity: 1, duration: 0.1 }, t_strike + 0.25);
    const boulderNodes = boulders.querySelectorAll("g");
    boulderNodes.forEach((bld, i) => {
      masterTl.fromTo(bld,
        { y: 0, rotation: 0 },
        { y: 720, rotation: 160 + i * 85, duration: 1.4 + i * 0.25, ease: "power2.in" },
        t_strike + 0.25 + i * 0.12
      );
    });
  }

  // Transition 4 -> 5 (Flash & Impact Cut)
  const t_trans4 = t_shot5_start;
  masterTl.set(shot4, { display: "none" }, t_trans4);
  masterTl.set(shot5, { display: "block", opacity: 1 }, t_trans4);

  // =========================================================================
  // SHOT 5 (t_shot5_start -> t_shot5_end): CRUSHED SUBMISSION (Beat 5)
  // Foreground massive mountain pressing DOWN on crouched Ravana
  // =========================================================================
  masterTl.set(puppet, {
    display: "block",
    opacity: 1,
    scale: 1.18,
    x: 0,
    y: 200,
    // Crouched warrior squat kinematics
    "--trans-torso-y": "80px",
    "--rot-thigh-left": "40deg",
    "--rot-shin-left": "-55deg",
    "--rot-thigh-right": "-40deg",
    "--rot-shin-right": "55deg",
    // Arms reaching UPWARD bracing against crushing mountain stone
    "--rot-shoulder-front-left": "110deg",
    "--rot-elbow-front-left": "60deg",
    "--rot-shoulder-front-right": "-110deg",
    "--rot-elbow-front-right": "-60deg",
    "--rot-shoulder-rear-left": "-18deg",
    "--rot-elbow-rear-left": "18deg",
    "--rot-shoulder-rear-right": "18deg",
    "--rot-elbow-rear-right": "-18deg",
    "--rot-torso": "2deg"
  }, t_trans4);

  // Expression: Strained pious submission
  if (browsNeutral && browsAngry) {
    masterTl.set(browsNeutral, { opacity: 0 }, t_trans4);
    masterTl.set(browsAngry, { opacity: 1 }, t_trans4);
  }
  if (eyesNormal && eyesWrath) {
    masterTl.set(eyesWrath, { opacity: 0 }, t_trans4);
    masterTl.set(eyesNormal, { opacity: 1 }, t_trans4);
  }
  if (mouthCalm && mouthTalk && mouthShout) {
    masterTl.set(mouthShout, { opacity: 0 }, t_trans4);
    masterTl.set(mouthTalk, { opacity: 0 }, t_trans4);
    masterTl.set(mouthCalm, { opacity: 1 }, t_trans4);
  }
  if (wrathSunburst) {
    masterTl.set(wrathSunburst, { opacity: 0 }, t_trans4);
  }

  // Foreground mountain underside pressing DOWN directly onto bracing hands
  if (fgMountain) {
    masterTl.fromTo(fgMountain,
      { y: -10 },
      { y: 65, duration: t_shot5_end - t_shot5_start, ease: "sine.inOut" },
      t_trans4
    );
  }

  // Trembling strained puppet under crushing weight
  masterTl.to(puppet, {
    y: "+=35",
    "--trans-torso-y": "95px",
    duration: t_shot5_end - t_shot5_start,
    ease: "sine.inOut"
  }, t_trans4);

  if (headCenter) {
    masterTl.to(headCenter, {
      rotation: -4,
      y: 15,
      duration: t_shot5_end - t_shot5_start,
      ease: "sine.inOut"
    }, t_trans4);
  }

  // Contact friction sparks shimmering at impact
  if (contactSparks) {
    masterTl.to(contactSparks, {
      opacity: 0.4,
      yoyo: true,
      repeat: 20,
      duration: 0.15,
      ease: "sine.inOut"
    }, t_trans4 + 0.2);
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

    # 1. Ensure build/manifest.js exists
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

    # 2. Read SVGs from assets/svg/
    svg_root = root / "assets" / "svg"
    ravana_path = svg_root / "characters" / "ravana.svg"
    lanka_path = svg_root / "backdrops" / "golden_lanka_citadel.svg"
    kailash_path = svg_root / "backdrops" / "mount_kailash.svg"
    granite_path = svg_root / "backdrops" / "granite_underside.svg"
    crushed_path = svg_root / "backdrops" / "crushed_atmosphere.svg"

    for asset_name, p in [
        ("ravana.svg", ravana_path),
        ("golden_lanka_citadel.svg", lanka_path),
        ("mount_kailash.svg", kailash_path),
        ("granite_underside.svg", granite_path),
        ("crushed_atmosphere.svg", crushed_path),
    ]:
        if not p.is_file():
            raise CompositionError(f"Required SVG asset missing at '{p}'")

    ravana_svg = ravana_path.read_text(encoding="utf-8")
    lanka_svg = lanka_path.read_text(encoding="utf-8")
    kailash_svg = kailash_path.read_text(encoding="utf-8")
    granite_svg = granite_path.read_text(encoding="utf-8")
    crushed_atmosphere_svg = crushed_path.read_text(encoding="utf-8")

    # 3. Write styles.css
    styles_path = root / "styles.css"
    styles_path.write_text(generate_styles_css(), encoding="utf-8")

    # 4. Write engine.js
    engine_path = root / "engine.js"
    engine_path.write_text(generate_engine_js(), encoding="utf-8")

    # 5. Write index.html
    index_path = root / "index.html"
    index_content = generate_index_html(
        lang=lang,
        duration_sec=render_dur,
        lanka_svg=lanka_svg,
        kailash_svg=kailash_svg,
        granite_svg=granite_svg,
        crushed_atmosphere_svg=crushed_atmosphere_svg,
        ravana_svg=ravana_svg,
    )
    index_path.write_text(index_content, encoding="utf-8")

    return {
        "status": "ok",
        "action": "generate_composition",
        "language": lang,
        "duration_sec": render_dur,
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
