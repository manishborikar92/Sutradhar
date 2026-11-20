import os
import json
import shutil

OUTPUT_BASE = "build/benchmark_v2_1"
os.makedirs(OUTPUT_BASE, exist_ok=True)

# Read assets
with open("build/benchmark_v2_1/ravana_v2_4.svg", "r", encoding="utf-8") as f:
    ravana_svg = f.read()

with open("assets/svg/backdrops/mount_kailash.svg", "r", encoding="utf-8") as f:
    kailash_svg = f.read()

ravana_svg_scaled = ravana_svg.replace(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 1200" width="800" height="1200" id="ravana_puppet_rig">',
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 1200" width="100%" height="100%" id="ravana_puppet_rig" data-layout-allow-overflow="true" data-layout-ignore="true">'
)

kailash_svg_scaled = kailash_svg.replace(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1920" width="1080" height="1920">',
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1920" width="100%" height="100%" id="kailash_backdrop" data-layout-allow-overflow="true" data-layout-ignore="true">'
)

# Golden Lanka Skyline SVG
lanka_skyline_svg = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1920" width="100%" height="100%" id="lanka_skyline" data-layout-allow-overflow="true" data-layout-ignore="true">
  <defs>
    <linearGradient id="lanka_sky" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#2a0505"/>
      <stop offset="40%" stop-color="#4a100a"/>
      <stop offset="75%" stop-color="#802008"/>
      <stop offset="100%" stop-color="#260803"/>
    </linearGradient>
    <linearGradient id="gold_palace_lit" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#fff3b0"/>
      <stop offset="25%" stop-color="#ffd166"/>
      <stop offset="65%" stop-color="#c68a12"/>
      <stop offset="100%" stop-color="#523200"/>
    </linearGradient>
    <linearGradient id="gold_palace_shadow" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#b8860b"/>
      <stop offset="50%" stop-color="#6e4604"/>
      <stop offset="100%" stop-color="#2a1600"/>
    </linearGradient>
    <radialGradient id="palace_glow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#ffb703" stop-opacity="0.8"/>
      <stop offset="60%" stop-color="#d48b04" stop-opacity="0.3"/>
      <stop offset="100%" stop-color="#7a3e00" stop-opacity="0"/>
    </radialGradient>
  </defs>

  <rect width="1080" height="1920" fill="url(#lanka_sky)"/>

  <!-- Distant Golden Palaces & Spires (Far Layer) -->
  <g id="lanka_distant" opacity="0.65">
    <circle cx="540" cy="850" r="450" fill="url(#palace_glow)"/>
    <!-- Central Citadel Spire -->
    <path d="M 540 400 L 510 650 L 570 650 Z" fill="url(#gold_palace_lit)"/>
    <rect x="490" y="650" width="100" height="300" fill="url(#gold_palace_shadow)"/>
    <circle cx="540" cy="400" r="10" fill="#fff"/>
    <!-- Left Spires -->
    <path d="M 320 520 L 295 720 L 345 720 Z" fill="url(#gold_palace_lit)"/>
    <rect x="280" y="720" width="80" height="250" fill="url(#gold_palace_shadow)"/>
    <path d="M 180 620 L 160 800 L 200 800 Z" fill="url(#gold_palace_lit)"/>
    <rect x="150" y="800" width="60" height="200" fill="url(#gold_palace_shadow)"/>
    <!-- Right Spires -->
    <path d="M 760 520 L 735 720 L 785 720 Z" fill="url(#gold_palace_lit)"/>
    <rect x="720" y="720" width="80" height="250" fill="url(#gold_palace_shadow)"/>
    <path d="M 900 620 L 880 800 L 920 800 Z" fill="url(#gold_palace_lit)"/>
    <rect x="870" y="800" width="60" height="200" fill="url(#gold_palace_shadow)"/>
  </g>

  <!-- Midground Golden Lanka Citadel (Tiered Towers & Battlements) -->
  <g id="lanka_midground">
    <!-- Stepped Tiered Pavilion Center -->
    <path d="M 380 920 L 540 680 L 700 920 Z" fill="url(#gold_palace_lit)" stroke="#3d2100" stroke-width="2"/>
    <rect x="360" y="920" width="360" height="280" fill="url(#gold_palace_shadow)" stroke="#3d2100" stroke-width="2"/>
    <!-- Golden Arches and Amber Windows -->
    <path d="M 460 1020 Q 540 960 620 1020 L 620 1150 L 460 1150 Z" fill="#ffb703"/>
    <path d="M 400 1050 Q 430 1010 460 1050 L 460 1120 L 400 1120 Z" fill="#ffa200"/>
    <path d="M 620 1050 Q 650 1010 680 1050 L 680 1120 L 620 1120 Z" fill="#ffa200"/>

    <!-- Left Fortress Wing -->
    <path d="M 100 850 L 220 750 L 340 850 Z" fill="url(#gold_palace_lit)"/>
    <rect x="120" y="850" width="200" height="350" fill="url(#gold_palace_shadow)"/>
    <!-- Right Fortress Wing -->
    <path d="M 740 850 L 860 750 L 980 850 Z" fill="url(#gold_palace_lit)"/>
    <rect x="760" y="850" width="200" height="350" fill="url(#gold_palace_shadow)"/>
  </g>

  <!-- Foreground Fortress Wall & Dais -->
  <g id="lanka_foreground">
    <rect x="0" y="1200" width="1080" height="720" fill="#1f0904"/>
    <path d="M 0 1200 Q 540 1250 1080 1200 L 1080 1240 Q 540 1290 0 1240 Z" fill="url(#gold_palace_lit)"/>
    <!-- Carved Relief Frieze -->
    <line x1="0" y1="1260" x2="1080" y2="1260" stroke="#f5c242" stroke-width="4"/>
    <line x1="0" y1="1310" x2="1080" y2="1310" stroke="#b8860b" stroke-width="2"/>
    <path d="M 0 1260 L 40 1310 M 80 1260 L 120 1310 M 160 1260 L 200 1310 M 240 1260 L 280 1310 M 320 1260 L 360 1310 M 400 1260 L 440 1310 M 480 1260 L 520 1310 M 560 1260 L 600 1310 M 640 1260 L 680 1310 M 720 1260 L 760 1310 M 800 1260 L 840 1310 M 880 1260 L 920 1310 M 960 1260 L 1000 1310 M 1040 1260 L 1080 1310" stroke="#b8860b" stroke-width="2"/>
  </g>
</svg>
"""

# Common HTML template builder
def build_composition(lang, manifest_data):
    total_dur = manifest_data["total_duration_sec"]
    beats = manifest_data["beats"]
    
    # 12 warm embers (optimizing heavy overlay count)
    ember_divs = "\n".join([f'    <div class="ember" style="left: {((i*83)%980)+50}px; width: {5+(i%3)*2}px; height: {5+(i%3)*2}px;"></div>' for i in range(12)])

    html = f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
  <meta charset="UTF-8">
  <title>Sutradhar v2.1 — Multi-Shot Theatrical Benchmark ({lang.upper()})</title>
  <link rel="stylesheet" href="styles.css">
  <script src="assets/js/gsap.min.js"></script>
  <script src="manifest.js"></script>
  <script src="engine.js"></script>
</head>
<body data-composition-id="sutradhar_multishot_{lang}" data-width="1080" data-height="1920" data-duration="{total_dur:.2f}">

  <!-- MASTER THEATRICAL STAGE -->
  <div id="stage" data-layout-allow-overflow="true" data-layout-ignore="true">

    <!-- SHOT 1: GOLDEN LANKA COURT & HORIZON (Beat 1) -->
    <div id="shot_1_container" class="shot-layer active-shot" data-layout-allow-overflow="true" data-layout-ignore="true">
      <div class="shot-bg" data-layout-allow-overflow="true" data-layout-ignore="true">
        {lanka_skyline_svg}
      </div>
      <!-- Flanking Carved Sandstone Pillars -->
      <div class="pillar pillar-left" data-layout-ignore="true"></div>
      <div class="pillar pillar-right" data-layout-ignore="true"></div>
      <!-- Hanging Brass Diyas with Flickering Flames -->
      <div class="hanging-diya diya-left" data-layout-ignore="true">
        <div class="diya-chain"></div>
        <div class="diya-bowl"></div>
        <div class="diya-flame flame-1"></div>
      </div>
      <div class="hanging-diya diya-right" data-layout-ignore="true">
        <div class="diya-chain"></div>
        <div class="diya-bowl"></div>
        <div class="diya-flame flame-2"></div>
      </div>
    </div>

    <!-- SHOT 2: SANDSTONE THRONE ROOM & RAVANA ADVANCE (Beat 2) -->
    <div id="shot_2_container" class="shot-layer" data-layout-allow-overflow="true" data-layout-ignore="true">
      <div class="throne-hall-bg" data-layout-ignore="true">
        <div class="throne-arch"></div>
        <div class="throne-dais"></div>
      </div>
      <!-- Standing Fire Braziers on Dais -->
      <div class="brazier brazier-left" data-layout-ignore="true">
        <div class="brazier-bowl"></div>
        <div class="brazier-flame flame-3"></div>
      </div>
      <div class="brazier brazier-right" data-layout-ignore="true">
        <div class="brazier-bowl"></div>
        <div class="brazier-flame flame-4"></div>
      </div>
    </div>

    <!-- RAVANA PUPPET RIG (Shared by Shot 2, 3, 5 with dynamic transforms) -->
    <div id="puppet_wrapper" data-layout-allow-overflow="true" data-layout-ignore="true">
      {ravana_svg_scaled}
    </div>

    <!-- SHOT 4: SACRED MOUNT KAILASH VISTA & COSMIC STRIKE (Beat 4) -->
    <div id="shot_4_container" class="shot-layer" data-layout-allow-overflow="true" data-layout-ignore="true">
      <div class="kailash-bg" data-layout-allow-overflow="true" data-layout-ignore="true">
        {kailash_svg_scaled}
      </div>
      <!-- Divine Golden Strike Laser Beam -->
      <div id="divine_beam" data-layout-ignore="true"></div>
      <!-- Expanding Shockwave Rings -->
      <div id="shockwave_ring_1" class="shockwave" data-layout-ignore="true"></div>
      <div id="shockwave_ring_2" class="shockwave" data-layout-ignore="true"></div>
      <!-- Tumbling Rock Silhouettes -->
      <div class="rock rock-1" data-layout-ignore="true"></div>
      <div class="rock rock-2" data-layout-ignore="true"></div>
      <div class="rock rock-3" data-layout-ignore="true"></div>
    </div>

    <!-- SHOT 5: CRUSHED UNDER GRANITE OVERHANG (Beat 5) -->
    <div id="shot_5_container" class="shot-layer" data-layout-allow-overflow="true" data-layout-ignore="true">
      <!-- Dark Crushing Mountain Granite Overhang -->
      <div id="granite_overhang" data-layout-ignore="true"></div>
    </div>

    <!-- PARTING CRIMSON-AND-GOLD VELVET THEATRICAL CURTAINS (Shot 1) -->
    <div id="curtain_left" class="velvet-curtain" data-layout-allow-overflow="true" data-layout-ignore="true">
      <div class="gold-border"></div>
      <div class="gold-fringe"></div>
    </div>
    <div id="curtain_right" class="velvet-curtain" data-layout-allow-overflow="true" data-layout-ignore="true">
      <div class="gold-border"></div>
      <div class="gold-fringe"></div>
    </div>

    <!-- FLASH OVERLAY (Wrath burst & Lightning) -->
    <div id="wrath_flash" data-layout-ignore="true"></div>

    <!-- WARM FLOATING EMBER PARTICLES (Continuous across all shots) -->
    <div id="embers_container" data-layout-ignore="true">
{ember_divs}
    </div>

    <!-- VIGNETTE & WARM COLOR GRADE -->
    <div id="theatrical_vignette" data-layout-ignore="true"></div>

  </div>
</body>
</html>
"""
    return html

styles_css = """
/* Sutradhar v2.1 Theatrical Multi-Shot Styling */
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  width: 1080px;
  height: 1920px;
  background: #080302;
  overflow: hidden;
  font-family: Georgia, serif;
}

#stage {
  position: absolute;
  top: 0;
  left: 0;
  width: 1080px;
  height: 1920px;
  overflow: hidden;
}

/* SHOT LAYERS: display none by default to exclude inactive overlays from DOM render tree */
.shot-layer {
  position: absolute;
  top: 0;
  left: 0;
  width: 1080px;
  height: 1920px;
  display: none;
  opacity: 0;
  pointer-events: none;
}

.active-shot {
  display: block;
  opacity: 1;
}

/* Sandstone Columns (Shot 1 & 2) */
.pillar {
  position: absolute;
  top: 0;
  width: 160px;
  height: 1920px;
  background: linear-gradient(90deg, #1f0d05 0%, #4a2410 40%, #733a1a 70%, #1f0d05 100%);
  border-right: 4px solid #b8860b;
  border-left: 4px solid #b8860b;
  box-shadow: 0 0 35px rgba(0,0,0,0.9);
}
.pillar-left { left: 0; }
.pillar-right { right: 0; transform: scaleX(-1); }

/* Hanging Diyas */
.hanging-diya {
  position: absolute;
  top: 0;
  width: 100px;
  height: 600px;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.diya-left { left: 180px; }
.diya-right { right: 180px; }
.diya-chain {
  width: 4px;
  height: 480px;
  background: repeating-linear-gradient(180deg, #ffd166 0px, #b8860b 8px, #523200 16px);
}
.diya-bowl {
  width: 80px;
  height: 35px;
  background: radial-gradient(circle at 50% 30%, #ffd166 0%, #b8860b 60%, #4a2e00 100%);
  border-radius: 0 0 40px 40px;
  box-shadow: 0 8px 25px rgba(255, 183, 3, 0.4);
}
.diya-flame, .brazier-flame {
  position: absolute;
  width: 24px;
  height: 45px;
  background: radial-gradient(ellipse at 50% 80%, #ffffff 0%, #ffd166 40%, #f77f00 70%, #d62828 100%);
  border-radius: 50% 50% 20% 20% / 80% 80% 20% 20%;
}
.diya-flame { top: 450px; }

/* Throne Room (Shot 2) */
.throne-hall-bg {
  position: absolute;
  top: 0;
  left: 0;
  width: 1080px;
  height: 1920px;
  background: radial-gradient(circle at 50% 40%, #3d1c08 0%, #1c0a02 70%, #0a0301 100%);
}
.throne-arch {
  position: absolute;
  top: 150px;
  left: 140px;
  width: 800px;
  height: 900px;
  border: 24px solid #b8860b;
  border-radius: 400px 400px 0 0;
}
.throne-dais {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 1080px;
  height: 600px;
  background: linear-gradient(180deg, #592b0c 0%, #2e1304 60%, #140701 100%);
  border-top: 12px solid #ffd166;
}

/* Fire Braziers */
.brazier {
  position: absolute;
  bottom: 300px;
  width: 140px;
  height: 400px;
}
.brazier-left { left: 80px; }
.brazier-right { right: 80px; }
.brazier-bowl {
  position: absolute;
  bottom: 220px;
  width: 140px;
  height: 70px;
  background: radial-gradient(circle at 50% 40%, #f5c242 0%, #b8860b 50%, #361f03 100%);
  border-radius: 0 0 70px 70px;
  border-top: 8px solid #ffd700;
}
.brazier-flame {
  bottom: 275px;
  left: 45px;
  width: 50px;
  height: 90px;
}

/* RAVANA PUPPET WRAPPER */
#puppet_wrapper {
  position: absolute;
  top: 360px;
  left: 140px;
  width: 800px;
  height: 1200px;
  z-index: 10;
  display: none;
  opacity: 0;
  filter: drop-shadow(0 20px 45px rgba(0,0,0,0.9));
}

/* Mount Kailash (Shot 4) */
#divine_beam {
  position: absolute;
  top: -100px;
  left: 515px;
  width: 50px;
  height: 800px;
  background: linear-gradient(180deg, rgba(255,255,255,0.95) 0%, rgba(255,224,102,0.85) 50%, rgba(245,159,0,0) 100%);
  border-radius: 25px;
  opacity: 0;
  transform-origin: top center;
}
.shockwave {
  position: absolute;
  top: 570px;
  left: 490px;
  width: 100px;
  height: 100px;
  border: 6px solid #fff3bf;
  border-radius: 50%;
  opacity: 0;
  transform: translate(-50%, -50%);
}
.rock {
  position: absolute;
  background: #0f141c;
  border: 2px solid #2d3748;
  opacity: 0;
}
.rock-1 { top: 650px; left: 420px; width: 35px; height: 28px; }
.rock-2 { top: 720px; right: 410px; width: 45px; height: 38px; }
.rock-3 { top: 800px; left: 480px; width: 55px; height: 42px; }

/* Granite Overhang (Shot 5) */
#granite_overhang {
  position: absolute;
  top: 0;
  left: 0;
  width: 1080px;
  height: 620px;
  background: linear-gradient(180deg, #07090f 0%, #141b27 75%, rgba(20,27,39,0) 100%);
  box-shadow: 0 25px 50px rgba(0,0,0,0.95);
}

/* Parting Velvet Curtains */
.velvet-curtain {
  position: absolute;
  top: 0;
  width: 550px;
  height: 1920px;
  background: linear-gradient(90deg, #450a0a 0%, #801212 40%, #b91c1c 70%, #450a0a 100%);
  z-index: 50;
  box-shadow: 0 0 50px rgba(0,0,0,0.95);
}
#curtain_left {
  left: 0;
  border-right: 14px solid #ffd166;
}
#curtain_right {
  right: 0;
  border-left: 14px solid #ffd166;
}
.gold-fringe {
  position: absolute;
  bottom: 0;
  width: 100%;
  height: 35px;
  background: repeating-linear-gradient(90deg, #ffd166 0px, #b8860b 10px, #523200 20px);
}

/* Flash overlay */
#wrath_flash {
  position: absolute;
  top: 0;
  left: 0;
  width: 1080px;
  height: 1920px;
  background: #ffffff;
  opacity: 0;
  pointer-events: none;
  z-index: 60;
}

/* Floating Embers */
#embers_container {
  position: absolute;
  top: 0;
  left: 0;
  width: 1080px;
  height: 1920px;
  pointer-events: none;
  z-index: 40;
}
.ember {
  position: absolute;
  background: #ffd43b;
  border-radius: 50%;
  opacity: 0;
}

/* Theatrical Vignette */
#theatrical_vignette {
  position: absolute;
  top: 0;
  left: 0;
  width: 1080px;
  height: 1920px;
  background: radial-gradient(circle at 50% 50%, transparent 60%, rgba(10, 3, 2, 0.70) 100%);
  pointer-events: none;
  z-index: 70;
}
"""

def generate_engine_js(lang, manifest_data):
    total_dur = manifest_data["total_duration_sec"]
    beats = manifest_data["beats"]
    
    b1 = beats[0]
    b2 = beats[1]
    b3 = beats[2]
    b4 = beats[3]
    b5 = beats[4]
    
    t_shot1_end = b1["end_sec"]
    t_shot2_end = b2["end_sec"]
    t_shot3_end = b3["end_sec"]
    t_shot4_end = b4["end_sec"]
    t_shot5_end = total_dur
    
    js = f"""// Sutradhar v2.1 Theatrical Multi-Shot Choreography Engine ({lang.upper()})
window.__timelines = window.__timelines || {{}};

function initTimeline() {{
  const masterTl = gsap.timeline({{ paused: true }});

  // Select DOM elements
  const stage = document.querySelector("#stage");
  const shot1 = document.querySelector("#shot_1_container");
  const shot2 = document.querySelector("#shot_2_container");
  const shot4 = document.querySelector("#shot_4_container");
  const shot5 = document.querySelector("#shot_5_container");
  
  const curtainLeft = document.querySelector("#curtain_left");
  const curtainRight = document.querySelector("#curtain_right");
  
  const puppet = document.querySelector("#puppet_wrapper");
  const wrathSunburst = document.querySelector("#wrath_sunburst");
  const wrathFlash = document.querySelector("#wrath_flash");
  
  // Puppet articulated joints & expression nodes
  const eyesNormal = document.querySelector("#eyes_normal");
  const eyesWrath = document.querySelector("#eyes_wrath");
  const browsNeutral = document.querySelector("#brows_neutral");
  const browsAngry = document.querySelector("#brows_angry");
  const mouthCalm = document.querySelector("#mouth_calm");
  const mouthTalk = document.querySelector("#mouth_talk");
  const mouthShout = document.querySelector("#mouth_shout");
  
  const upperArmRearLeft = document.querySelector("#upper_arm_rear_left_rot");
  const forearmRearLeft = document.querySelector("#forearm_rear_left_rot");
  const weaponChandrahas = document.querySelector("#weapon_chandrahas_rot");
  
  const upperArmRearRight = document.querySelector("#upper_arm_rear_right_rot");
  const forearmRearRight = document.querySelector("#forearm_rear_right_rot");
  const weaponGada = document.querySelector("#weapon_gada_rot");
  
  const upperArmFrontLeft = document.querySelector("#upper_arm_front_left_rot");
  const forearmFrontLeft = document.querySelector("#forearm_front_left_rot");
  const upperArmFrontRight = document.querySelector("#upper_arm_front_right_rot");
  const forearmFrontRight = document.querySelector("#forearm_front_right_rot");
  
  const thighLeft = document.querySelector("#thigh_left_rot");
  const shinLeft = document.querySelector("#shin_left_rot");
  const thighRight = document.querySelector("#thigh_right_rot");
  const shinRight = document.querySelector("#shin_right_rot");
  
  const headsFan = document.querySelector("#heads_fan");
  const headCenter = document.querySelector("#head_center");
  
  // Mount Kailash strike nodes
  const divineBeam = document.querySelector("#divine_beam");
  const shockwave1 = document.querySelector("#shockwave_ring_1");
  const shockwave2 = document.querySelector("#shockwave_ring_2");
  const rocks = document.querySelectorAll(".rock");
  
  const embers = document.querySelectorAll(".ember");
  const flames = document.querySelectorAll(".diya-flame, .brazier-flame");

  // Initial states
  gsap.set(puppet, {{ display: "none", opacity: 0 }});
  gsap.set(eyesNormal, {{ opacity: 1 }});
  gsap.set(eyesWrath, {{ opacity: 0 }});
  gsap.set(browsNeutral, {{ opacity: 1 }});
  gsap.set(browsAngry, {{ opacity: 0 }});
  gsap.set(mouthCalm, {{ opacity: 1 }});
  gsap.set(mouthTalk, {{ opacity: 0 }});
  gsap.set(mouthShout, {{ opacity: 0 }});
  gsap.set(wrathSunburst, {{ opacity: 0, scale: 0.85 }});

  // Finite repeat for flame flickers (finite 80 repeats, no infinite loops)
  flames.forEach((flame, i) => {{
    masterTl.to(flame, {{
      scaleY: 1.25,
      scaleX: 0.88,
      duration: 0.18 + (i % 3) * 0.04,
      repeat: 75,
      yoyo: true,
      ease: "sine.inOut"
    }}, 0.0);
  }});

  // Continuous floating embers (finite repeats across timeline)
  embers.forEach((ember, i) => {{
    const dur = 4.2 + (i % 3) * 1.0;
    const delay = (i * 0.4) % 3.0;
    masterTl.fromTo(ember,
      {{ y: 1950, x: "+=" + ((i % 4) * 30 - 45), opacity: 0 }},
      {{ y: -60, opacity: 0.85, duration: dur, ease: "none", repeat: 5 }},
      delay
    );
  }});

  // ==============================================================
  // SHOT 1 (0.0s -> {t_shot1_end}s): GOLDEN LANKA HORIZON (Beat 1)
  // Ornate velvet curtains part, revealing Golden Lanka Skyline
  // ==============================================================
  masterTl.set(shot1, {{ display: "block", opacity: 1 }}, 0.0);
  masterTl.to(curtainLeft, {{ xPercent: -102, duration: 1.8, ease: "power2.inOut" }}, 0.5);
  masterTl.to(curtainRight, {{ xPercent: 102, duration: 1.8, ease: "power2.inOut" }}, 0.5);
  // Continuous camera push-in into Lanka skyline (ensures zero dead stretches)
  masterTl.to(shot1, {{ scale: 1.15, duration: {t_shot1_end}, ease: "sine.inOut" }}, 0.0);

  // ==============================================================
  // SHOT 2 ({t_shot1_end}s -> {t_shot2_end}s): THRONE ROOM ADVANCE (Beat 2)
  // Cut to medium shot: Ravana advances forward raising weapons
  // ==============================================================
  masterTl.set(shot1, {{ display: "none", opacity: 0 }}, {t_shot1_end});
  masterTl.set(shot2, {{ display: "block", opacity: 1 }}, {t_shot1_end});
  masterTl.set(puppet, {{ display: "block", opacity: 1, scale: 1.15, x: 0, y: -40 }}, {t_shot1_end});

  // Continuous camera drift across Shot 2
  masterTl.to(stage, {{ scale: 1.08, duration: {t_shot2_end - t_shot1_end}, ease: "sine.inOut" }}, {t_shot1_end});

  // Stride animation (hips & knees)
  masterTl.to(thighLeft, {{ rotation: 8, duration: 0.9, yoyo: true, repeat: 3, ease: "sine.inOut" }}, {t_shot1_end});
  masterTl.to(shinLeft, {{ rotation: -12, duration: 0.9, yoyo: true, repeat: 3, ease: "sine.inOut" }}, {t_shot1_end});
  masterTl.to(thighRight, {{ rotation: -8, duration: 0.9, yoyo: true, repeat: 3, ease: "sine.inOut" }}, {t_shot1_end});
  masterTl.to(shinRight, {{ rotation: 12, duration: 0.9, yoyo: true, repeat: 3, ease: "sine.inOut" }}, {t_shot1_end});

  // Raising weapons upward into the sky (locked rivets, 0 detachment!)
  masterTl.to(upperArmRearLeft, {{ rotation: 32, duration: 1.4, ease: "power2.out" }}, {t_shot1_end + 0.3});
  masterTl.to(forearmRearLeft, {{ rotation: 24, duration: 1.4, ease: "power2.out" }}, {t_shot1_end + 0.3});
  masterTl.to(weaponChandrahas, {{ rotation: 18, duration: 1.4, ease: "power2.out" }}, {t_shot1_end + 0.3});

  masterTl.to(upperArmRearRight, {{ rotation: -32, duration: 1.4, ease: "power2.out" }}, {t_shot1_end + 0.4});
  masterTl.to(forearmRearRight, {{ rotation: -24, duration: 1.4, ease: "power2.out" }}, {t_shot1_end + 0.4});
  masterTl.to(weaponGada, {{ rotation: -18, duration: 1.4, ease: "power2.out" }}, {t_shot1_end + 0.4});

  masterTl.to(upperArmFrontLeft, {{ rotation: -28, duration: 1.2, ease: "power2.out" }}, {t_shot1_end + 0.5});
  masterTl.to(forearmFrontLeft, {{ rotation: 22, duration: 1.2, ease: "power2.out" }}, {t_shot1_end + 0.5});

  masterTl.to(headsFan, {{ rotation: -3, duration: 1.8, yoyo: true, repeat: 1, ease: "sine.inOut" }}, {t_shot1_end + 0.5});

  // ==============================================================
  // SHOT 3 ({t_shot2_end}s -> {t_shot3_end}s): WRATHFUL DIALOGUE (Beat 3)
  // Dynamic punch-in cut directly to Ravana's 5 Heads
  // Eyes ignite red, solar sunburst rotates, mouth shouts!
  // ==============================================================
  masterTl.to(puppet, {{ scale: 2.1, y: 340, duration: 0.35, ease: "power3.out" }}, {t_shot2_end});
  masterTl.to(wrathFlash, {{ opacity: 0.85, duration: 0.18, yoyo: true, repeat: 1, ease: "power1.inOut" }}, {t_shot2_end});

  masterTl.to(wrathSunburst, {{ opacity: 1, scale: 1.05, duration: 0.5, ease: "back.out(2)" }}, {t_shot2_end + 0.05});
  masterTl.to(wrathSunburst, {{ rotation: 45, duration: {t_shot3_end - t_shot2_end}, ease: "none" }}, {t_shot2_end + 0.05});

  masterTl.to(eyesNormal, {{ opacity: 0, duration: 0.2 }}, {t_shot2_end + 0.1});
  masterTl.to(eyesWrath, {{ opacity: 1, duration: 0.2 }}, {t_shot2_end + 0.1});
  masterTl.to(browsNeutral, {{ opacity: 0, duration: 0.2 }}, {t_shot2_end + 0.1});
  masterTl.to(browsAngry, {{ opacity: 1, duration: 0.2 }}, {t_shot2_end + 0.1});

  // Lip-sync mouth articulation during dialogue
  masterTl.set(mouthCalm, {{ opacity: 0 }}, {t_shot2_end + 0.2});
  masterTl.set(mouthTalk, {{ opacity: 1 }}, {t_shot2_end + 0.2});

  masterTl.set(mouthTalk, {{ opacity: 0 }}, {t_shot2_end + 0.7});
  masterTl.set(mouthShout, {{ opacity: 1 }}, {t_shot2_end + 0.7});

  masterTl.set(mouthShout, {{ opacity: 0 }}, {t_shot2_end + 1.4});
  masterTl.set(mouthTalk, {{ opacity: 1 }}, {t_shot2_end + 1.4});

  masterTl.set(mouthTalk, {{ opacity: 0 }}, {t_shot2_end + 2.0});
  masterTl.set(mouthShout, {{ opacity: 1 }}, {t_shot2_end + 2.0});

  masterTl.to(headCenter, {{ scale: 1.18, duration: 0.4, ease: "power2.out" }}, {t_shot2_end + 0.3});
  masterTl.to(headsFan, {{ rotation: 3, duration: 0.18, yoyo: true, repeat: 10, ease: "sine.inOut" }}, {t_shot2_end + 0.5});

  // ==============================================================
  // SHOT 4 ({t_shot3_end}s -> {t_shot4_end}s): KAILASH COSMIC STRIKE (Beat 4)
  // Complete cutaway to Mount Kailash vista under cosmic indigo sky
  // Shiva presses toe -> Divine beam strikes peak, shockwaves & rockslides
  // ==============================================================
  masterTl.set(shot2, {{ display: "none", opacity: 0 }}, {t_shot3_end});
  masterTl.set(puppet, {{ display: "none", opacity: 0 }}, {t_shot3_end});
  masterTl.set(shot4, {{ display: "block", opacity: 1 }}, {t_shot3_end});

  masterTl.fromTo(shot4, {{ scale: 1.0 }}, {{ scale: 1.10, duration: {t_shot4_end - t_shot3_end}, ease: "sine.out" }}, {t_shot3_end});

  const t_strike = {t_shot3_end + (t_shot4_end - t_shot3_end) * 0.35:.3f};

  masterTl.fromTo(divineBeam,
    {{ opacity: 0, scaleY: 0 }},
    {{ opacity: 1, scaleY: 1, duration: 0.18, ease: "power4.in" }},
    t_strike
  );
  masterTl.to(divineBeam, {{ opacity: 0, duration: 0.4, ease: "power2.out" }}, t_strike + 0.3);

  masterTl.to(wrathFlash, {{ opacity: 0.95, duration: 0.15, yoyo: true, repeat: 1, ease: "power2.inOut" }}, t_strike + 0.18);

  masterTl.fromTo(shockwave1,
    {{ width: 80, height: 80, opacity: 1 }},
    {{ width: 900, height: 900, opacity: 0, duration: 1.2, ease: "power2.out" }},
    t_strike + 0.18
  );
  masterTl.fromTo(shockwave2,
    {{ width: 60, height: 60, opacity: 1 }},
    {{ width: 1100, height: 1100, opacity: 0, duration: 1.4, ease: "power2.out" }},
    t_strike + 0.35
  );

  masterTl.to(stage, {{ x: 22, duration: 0.04, yoyo: true, repeat: 16, ease: "none" }}, t_strike + 0.18);

  rocks.forEach((rock, i) => {{
    masterTl.fromTo(rock,
      {{ opacity: 1, y: 0, rotation: 0 }},
      {{ y: 650, rotation: 180 + i * 90, opacity: 0.9, duration: 1.5 + i * 0.3, ease: "power2.in" }},
      t_strike + 0.25 + i * 0.15
    );
  }});

  // ==============================================================
  // SHOT 5 ({t_shot4_end}s -> {total_dur:.3f}s): CRUSHED SUBMISSION (Beat 5)
  // Return to Ravana pinned beneath granite overhang
  // Head bows reverently, mouth calm, golden prayer embers ascend
  // ==============================================================
  masterTl.set(shot4, {{ display: "none", opacity: 0 }}, {t_shot4_end});
  masterTl.set(shot5, {{ display: "block", opacity: 1 }}, {t_shot4_end});
  masterTl.set(puppet, {{ display: "block", opacity: 1, scale: 1.2, x: 0, y: 120 }}, {t_shot4_end});

  masterTl.set(mouthTalk, {{ opacity: 0 }}, {t_shot4_end});
  masterTl.set(mouthShout, {{ opacity: 0 }}, {t_shot4_end});
  masterTl.set(mouthCalm, {{ opacity: 1 }}, {t_shot4_end});
  masterTl.set(eyesWrath, {{ opacity: 0 }}, {t_shot4_end});
  masterTl.set(eyesNormal, {{ opacity: 1 }}, {t_shot4_end});
  masterTl.set(browsAngry, {{ opacity: 0 }}, {t_shot4_end});
  masterTl.set(browsNeutral, {{ opacity: 1 }}, {t_shot4_end});
  masterTl.set(wrathSunburst, {{ opacity: 0 }}, {t_shot4_end});

  // Arms braced upward supporting granite rock face (100% attached at rivets!)
  masterTl.set(upperArmRearLeft, {{ rotation: 40 }}, {t_shot4_end});
  masterTl.set(forearmRearLeft, {{ rotation: 35 }}, {t_shot4_end});
  masterTl.set(upperArmRearRight, {{ rotation: -40 }}, {t_shot4_end});
  masterTl.set(forearmRearRight, {{ rotation: -35 }}, {t_shot4_end});

  masterTl.set(upperArmFrontLeft, {{ rotation: 25 }}, {t_shot4_end});
  masterTl.set(forearmFrontLeft, {{ rotation: -15 }}, {t_shot4_end});
  masterTl.set(upperArmFrontRight, {{ rotation: -25 }}, {t_shot4_end});
  masterTl.set(forearmFrontRight, {{ rotation: 15 }}, {t_shot4_end});

  masterTl.to(puppet, {{ y: 180, duration: 4.5, ease: "sine.inOut" }}, {t_shot4_end + 0.5});
  masterTl.to(headsFan, {{ rotation: 4, y: 25, duration: 4.0, ease: "sine.inOut" }}, {t_shot4_end + 0.5});
  masterTl.to(document.querySelector("#granite_overhang"), {{ y: 45, duration: 4.5, ease: "sine.inOut" }}, {t_shot4_end + 0.5});

  masterTl.to(stage, {{ opacity: 0.92, duration: 2.0, ease: "sine.inOut" }}, {total_dur - 2.0:.3f});

  window.__timelines["sutradhar_multishot_{lang}"] = masterTl;
  console.log("Registered timeline sutradhar_multishot_{lang} with total duration: {total_dur:.3f}s");
}}

document.addEventListener("DOMContentLoaded", initTimeline);
"""
    return js

# Re-generate English and Hindi project folders
langs = ["en", "hi"]
for lang in langs:
    proj_dir = os.path.join(OUTPUT_BASE, f"video_{lang}")
    os.makedirs(os.path.join(proj_dir, "assets", "js"), exist_ok=True)
    shutil.copyfile("assets/js/gsap.min.js", os.path.join(proj_dir, "assets", "js", "gsap.min.js"))
    
    manifest_path = os.path.join(OUTPUT_BASE, "audio", f"beat_manifest_{lang}.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)
        
    manifest_js = f"window.__audio_manifest = {json.dumps(manifest_data, indent=2, ensure_ascii=False)};"
    with open(os.path.join(proj_dir, "manifest.js"), "w", encoding="utf-8") as f:
        f.write(manifest_js)
        
    with open(os.path.join(proj_dir, "styles.css"), "w", encoding="utf-8") as f:
        f.write(styles_css)
        
    html_content = build_composition(lang, manifest_data)
    with open(os.path.join(proj_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(html_content)
        
    engine_content = generate_engine_js(lang, manifest_data)
    with open(os.path.join(proj_dir, "engine.js"), "w", encoding="utf-8") as f:
        f.write(engine_content)
        
    print(f"Refined multi-shot project for {lang.upper()} -> {proj_dir} (duration: {manifest_data['total_duration_sec']}s)")
