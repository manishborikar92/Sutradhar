import os
import json

# Update engine.js in video_en with transformOrigin: "0px 0px" and fixed flash
manifest_path = "build/benchmark_v2_1/audio/beat_manifest_en.json"
with open(manifest_path, "r", encoding="utf-8") as f:
    manifest_data = json.load(f)

total_dur = manifest_data["total_duration_sec"]
beats = manifest_data["beats"]

t_shot1_end = beats[0]["end_sec"]
t_shot2_end = beats[1]["end_sec"]
t_shot3_end = beats[2]["end_sec"]
t_shot4_end = beats[3]["end_sec"]
t_shot5_end = total_dur

engine_js = f"""// Sutradhar v2.1 Theatrical Multi-Shot Choreography Engine (EN) - Fixed Transform Origins
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
  
  // Puppet articulated joints
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

  // Initial states with explicit transform-origin: 0 0 locked to rivet pins!
  gsap.set([upperArmRearLeft, forearmRearLeft, weaponChandrahas,
            upperArmRearRight, forearmRearRight, weaponGada,
            upperArmFrontLeft, forearmFrontLeft,
            upperArmFrontRight, forearmFrontRight,
            thighLeft, shinLeft, thighRight, shinRight], {{ transformOrigin: "0px 0px" }});

  gsap.set(puppet, {{ display: "none", opacity: 0 }});
  gsap.set(eyesNormal, {{ opacity: 1 }});
  gsap.set(eyesWrath, {{ opacity: 0 }});
  gsap.set(browsNeutral, {{ opacity: 1 }});
  gsap.set(browsAngry, {{ opacity: 0 }});
  gsap.set(mouthCalm, {{ opacity: 1 }});
  gsap.set(mouthTalk, {{ opacity: 0 }});
  gsap.set(mouthShout, {{ opacity: 0 }});
  gsap.set(wrathSunburst, {{ opacity: 0, scale: 0.85, transformOrigin: "0px 0px" }});
  gsap.set(wrathFlash, {{ opacity: 0 }});

  // Finite repeat for flame flickers
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

  // Continuous floating embers
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
  // ==============================================================
  masterTl.set(shot1, {{ display: "block", opacity: 1 }}, 0.0);
  masterTl.to(curtainLeft, {{ xPercent: -102, duration: 1.8, ease: "power2.inOut" }}, 0.5);
  masterTl.to(curtainRight, {{ xPercent: 102, duration: 1.8, ease: "power2.inOut" }}, 0.5);
  masterTl.to(shot1, {{ scale: 1.15, duration: {t_shot1_end}, ease: "sine.inOut" }}, 0.0);

  // ==============================================================
  // SHOT 2 ({t_shot1_end}s -> {t_shot2_end}s): THRONE ROOM ADVANCE (Beat 2)
  // ==============================================================
  masterTl.set(shot1, {{ display: "none", opacity: 0 }}, {t_shot1_end});
  masterTl.set(shot2, {{ display: "block", opacity: 1 }}, {t_shot1_end});
  masterTl.set(puppet, {{ display: "block", opacity: 1, scale: 1.15, x: 0, y: -40 }}, {t_shot1_end});

  masterTl.to(stage, {{ scale: 1.08, duration: {t_shot2_end - t_shot1_end}, ease: "sine.inOut" }}, {t_shot1_end});

  // Stride animation (hips & knees)
  masterTl.to(thighLeft, {{ rotation: 8, duration: 0.9, yoyo: true, repeat: 3, ease: "sine.inOut", transformOrigin: "0px 0px" }}, {t_shot1_end});
  masterTl.to(shinLeft, {{ rotation: -12, duration: 0.9, yoyo: true, repeat: 3, ease: "sine.inOut", transformOrigin: "0px 0px" }}, {t_shot1_end});
  masterTl.to(thighRight, {{ rotation: -8, duration: 0.9, yoyo: true, repeat: 3, ease: "sine.inOut", transformOrigin: "0px 0px" }}, {t_shot1_end});
  masterTl.to(shinRight, {{ rotation: 12, duration: 0.9, yoyo: true, repeat: 3, ease: "sine.inOut", transformOrigin: "0px 0px" }}, {t_shot1_end});

  // Raising weapons upward into the sky with locked transform-origins
  masterTl.to(upperArmRearLeft, {{ rotation: 32, duration: 1.4, ease: "power2.out", transformOrigin: "0px 0px" }}, {t_shot1_end + 0.3});
  masterTl.to(forearmRearLeft, {{ rotation: 24, duration: 1.4, ease: "power2.out", transformOrigin: "0px 0px" }}, {t_shot1_end + 0.3});
  masterTl.to(weaponChandrahas, {{ rotation: 18, duration: 1.4, ease: "power2.out", transformOrigin: "0px 0px" }}, {t_shot1_end + 0.3});

  masterTl.to(upperArmRearRight, {{ rotation: -32, duration: 1.4, ease: "power2.out", transformOrigin: "0px 0px" }}, {t_shot1_end + 0.4});
  masterTl.to(forearmRearRight, {{ rotation: -24, duration: 1.4, ease: "power2.out", transformOrigin: "0px 0px" }}, {t_shot1_end + 0.4});
  masterTl.to(weaponGada, {{ rotation: -18, duration: 1.4, ease: "power2.out", transformOrigin: "0px 0px" }}, {t_shot1_end + 0.4});

  masterTl.to(upperArmFrontLeft, {{ rotation: -28, duration: 1.2, ease: "power2.out", transformOrigin: "0px 0px" }}, {t_shot1_end + 0.5});
  masterTl.to(forearmFrontLeft, {{ rotation: 22, duration: 1.2, ease: "power2.out", transformOrigin: "0px 0px" }}, {t_shot1_end + 0.5});

  masterTl.to(headsFan, {{ rotation: -3, duration: 1.8, yoyo: true, repeat: 1, ease: "sine.inOut", transformOrigin: "0px 60px" }}, {t_shot1_end + 0.5});

  // ==============================================================
  // SHOT 3 ({t_shot2_end}s -> {t_shot3_end}s): WRATHFUL DIALOGUE (Beat 3)
  // ==============================================================
  masterTl.to(puppet, {{ scale: 2.1, y: 340, duration: 0.35, ease: "power3.out" }}, {t_shot2_end});

  // Brief flash on dialogue explosion
  masterTl.fromTo(wrathFlash, {{ opacity: 0 }}, {{ opacity: 0.65, duration: 0.08, ease: "power1.in" }}, {t_shot2_end});
  masterTl.to(wrathFlash, {{ opacity: 0, duration: 0.25, ease: "power1.out" }}, {t_shot2_end + 0.08});

  masterTl.to(wrathSunburst, {{ opacity: 1, scale: 1.05, duration: 0.5, ease: "back.out(2)", transformOrigin: "0px 0px" }}, {t_shot2_end + 0.05});
  masterTl.to(wrathSunburst, {{ rotation: 45, duration: {t_shot3_end - t_shot2_end}, ease: "none", transformOrigin: "0px 0px" }}, {t_shot2_end + 0.05});

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
  masterTl.to(headsFan, {{ rotation: 3, duration: 0.18, yoyo: true, repeat: 10, ease: "sine.inOut", transformOrigin: "0px 60px" }}, {t_shot2_end + 0.5});

  // ==============================================================
  // SHOT 4 ({t_shot3_end}s -> {t_shot4_end}s): KAILASH COSMIC STRIKE (Beat 4)
  // ==============================================================
  masterTl.set(shot2, {{ display: "none", opacity: 0 }}, {t_shot3_end});
  masterTl.set(puppet, {{ display: "none", opacity: 0 }}, {t_shot3_end});
  masterTl.set(shot4, {{ display: "block", opacity: 1 }}, {t_shot3_end});

  masterTl.fromTo(shot4, {{ scale: 1.0 }}, {{ scale: 1.10, duration: {t_shot4_end - t_shot3_end}, ease: "sine.out" }}, {t_shot3_end});

  const t_strike = {t_shot3_end + (t_shot4_end - t_shot3_end) * 0.35:.3f};

  // Divine beam descends
  masterTl.fromTo(divineBeam,
    {{ opacity: 0, scaleY: 0 }},
    {{ opacity: 1, scaleY: 1, duration: 0.18, ease: "power4.in" }},
    t_strike
  );
  masterTl.to(divineBeam, {{ opacity: 0, duration: 0.35, ease: "power2.out" }}, t_strike + 0.25);

  // Impact flash: quick flash that completely resets to 0!
  masterTl.fromTo(wrathFlash,
    {{ opacity: 0 }},
    {{ opacity: 0.8, duration: 0.08, ease: "power1.in" }},
    t_strike + 0.15
  );
  masterTl.to(wrathFlash, {{ opacity: 0, duration: 0.3, ease: "power2.out" }}, t_strike + 0.23);

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
  // ==============================================================
  masterTl.set(shot4, {{ display: "none", opacity: 0 }}, {t_shot4_end});
  masterTl.set(shot5, {{ display: "block", opacity: 1 }}, {t_shot4_end});
  masterTl.set(puppet, {{ display: "block", opacity: 1, scale: 1.12, x: 0, y: 140 }}, {t_shot4_end});

  masterTl.set(mouthTalk, {{ opacity: 0 }}, {t_shot4_end});
  masterTl.set(mouthShout, {{ opacity: 0 }}, {t_shot4_end});
  masterTl.set(mouthCalm, {{ opacity: 1 }}, {t_shot4_end});
  masterTl.set(eyesWrath, {{ opacity: 0 }}, {t_shot4_end});
  masterTl.set(eyesNormal, {{ opacity: 1 }}, {t_shot4_end});
  masterTl.set(browsAngry, {{ opacity: 0 }}, {t_shot4_end});
  masterTl.set(browsNeutral, {{ opacity: 1 }}, {t_shot4_end});
  masterTl.set(wrathSunburst, {{ opacity: 0 }}, {t_shot4_end});

  // Cleanly anchored braced arms beneath rock overhang
  masterTl.set(upperArmRearLeft, {{ rotation: 38, transformOrigin: "0px 0px" }}, {t_shot4_end});
  masterTl.set(forearmRearLeft, {{ rotation: 32, transformOrigin: "0px 0px" }}, {t_shot4_end});
  masterTl.set(upperArmRearRight, {{ rotation: -38, transformOrigin: "0px 0px" }}, {t_shot4_end});
  masterTl.set(forearmRearRight, {{ rotation: -32, transformOrigin: "0px 0px" }}, {t_shot4_end});

  masterTl.set(upperArmFrontLeft, {{ rotation: 22, transformOrigin: "0px 0px" }}, {t_shot4_end});
  masterTl.set(forearmFrontLeft, {{ rotation: -12, transformOrigin: "0px 0px" }}, {t_shot4_end});
  masterTl.set(upperArmFrontRight, {{ rotation: -22, transformOrigin: "0px 0px" }}, {t_shot4_end});
  masterTl.set(forearmFrontRight, {{ rotation: 12, transformOrigin: "0px 0px" }}, {t_shot4_end});

  masterTl.to(puppet, {{ y: 190, duration: 4.5, ease: "sine.inOut" }}, {t_shot4_end + 0.5});
  masterTl.to(headsFan, {{ rotation: 4, y: 25, duration: 4.0, ease: "sine.inOut", transformOrigin: "0px 60px" }}, {t_shot4_end + 0.5});
  masterTl.to(document.querySelector("#granite_overhang"), {{ y: 55, duration: 4.5, ease: "sine.inOut" }}, {t_shot4_end + 0.5});

  masterTl.to(stage, {{ opacity: 0.92, duration: 2.0, ease: "sine.inOut" }}, {total_dur - 2.0:.3f});

  window.__timelines["sutradhar_multishot_en"] = masterTl;
  console.log("Registered timeline sutradhar_multishot_en with total duration: {total_dur:.3f}s");
}}

document.addEventListener("DOMContentLoaded", initTimeline);
"""

with open("build/benchmark_v2_1/video_en/engine.js", "w", encoding="utf-8") as f:
    f.write(engine_js)

# Also update granite overhang styling in styles.css so it looks like a real textured crushing mountain face
with open("build/benchmark_v2_1/video_en/styles.css", "r", encoding="utf-8") as f:
    css = f.read()

# Enhance granite overhang
css = css.replace(
    '/* Granite Overhang (Shot 5) */\n#granite_overhang {\n  position: absolute;\n  top: 0;\n  left: 0;\n  width: 1080px;\n  height: 620px;\n  background: linear-gradient(180deg, #07090f 0%, #141b27 75%, rgba(20,27,39,0) 100%);\n  box-shadow: 0 25px 50px rgba(0,0,0,0.95);\n}',
    '/* Granite Overhang (Shot 5) */\n#granite_overhang {\n  position: absolute;\n  top: 0;\n  left: 0;\n  width: 1080px;\n  height: 520px;\n  background: linear-gradient(180deg, #05070b 0%, #1a2233 60%, #2d3748 85%, #0f141c 100%);\n  border-bottom: 6px solid #4a5568;\n  clip-path: polygon(0 0, 1080px 0, 1080px 380px, 860px 480px, 540px 420px, 240px 510px, 0 410px);\n  box-shadow: 0 35px 70px rgba(0,0,0,0.99);\n}'
)
with open("build/benchmark_v2_1/video_en/styles.css", "w", encoding="utf-8") as f:
    f.write(css)

print("Updated video_en with transform origins and enhanced granite overhang.")
