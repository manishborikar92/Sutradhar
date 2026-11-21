// Sutradhar v4.0 Master Choreography Engine
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

  // Puppet elements map
  const allPuppets = Array.from(document.querySelectorAll(".puppet-wrapper"));
  const primaryPuppet = document.querySelector("#puppet_wrapper") || allPuppets[0];

  // Helper to apply standardized puppet pose presets
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

  // Initial set for all puppets (hidden)
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
    const en = p.querySelector("#eyes_normal");
    const ew = p.querySelector("#eyes_wrath");
    const mc = p.querySelector("#mouth_calm");
    const mt = p.querySelector("#mouth_talk");
    const ms = p.querySelector("#mouth_shout");
    if (bn) gsap.set(bn, { opacity: 1 });
    if (ba) gsap.set(ba, { opacity: 0 });
    if (en) gsap.set(en, { opacity: 1 });
    if (ew) gsap.set(ew, { opacity: 0 });
    if (mc) gsap.set(mc, { opacity: 1 });
    if (mt) gsap.set(mt, { opacity: 0 });
    if (ms) gsap.set(ms, { opacity: 0 });
  });

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

    // Shot container display & fade-in
    masterTl.set(shotEl, { display: "block" }, t_start);
    if (idx === 0) {
      masterTl.set(shotEl, { opacity: 1 }, 0.0);
    } else {
      masterTl.fromTo(shotEl, { opacity: 0 }, { opacity: 1, duration: 0.30, ease: "power2.inOut" }, t_start);
    }

    // Previous shot fade-out
    if (idx > 0) {
      const prevShotEl = document.getElementById("shot_" + idx + "_container");
      if (prevShotEl) {
        masterTl.to(prevShotEl, { opacity: 0, duration: 0.30, ease: "power2.inOut" }, t_start);
        masterTl.set(prevShotEl, { display: "none" }, t_start + 0.30);
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
    } else if (camMotion === "micro_shake") {
      masterTl.to(stage, { x: 15, duration: 0.04, yoyo: true, repeat: 14, ease: "none" }, t_start + 0.15);
    }

    // Specific Shot Type Choreography
    if (shotType === "curtain_establishing" || shotType === "wide_establishing") {
      // Opening velvet curtains
      if (curtains.left && curtains.right) {
        masterTl.to(curtains.left, { xPercent: -102, duration: 1.8, ease: "power2.inOut" }, t_start + 0.4);
        masterTl.to(curtains.right, { xPercent: 102, duration: 1.8, ease: "power2.inOut" }, t_start + 0.4);
      }
      // Puppets hidden
      allPuppets.forEach(p => masterTl.set(p, { display: "none", opacity: 0 }, t_start));
    }
    else if (shotType === "landscape_cutaway") {
      // Environment focus
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
    else if (shotType === "character_closeup_dialogue" || shotType === "close_up_wrath") {
      if (primaryPuppet) {
        masterTl.set(primaryPuppet, { display: "block", opacity: 1 }, t_start);
        masterTl.to(primaryPuppet, { scale: 2.15, x: 0, y: 520, duration: 0.35, ease: "power3.out" }, t_start);

        // Flash pulse
        if (wrathFlash && emotion === "wrath") {
          masterTl.fromTo(wrathFlash, { opacity: 0 }, { opacity: 0.45, duration: 0.08, ease: "power1.in" }, t_start);
          masterTl.to(wrathFlash, { opacity: 0, duration: 0.20, ease: "power1.out" }, t_start + 0.08);
        }

        // Apply dialogue pose
        applyPose(primaryPuppet, posePreset, t_start, 0.35);

        // Face expressions
        const bn = primaryPuppet.querySelector("#brows_neutral");
        const ba = primaryPuppet.querySelector("#brows_angry");
        const en = primaryPuppet.querySelector("#eyes_normal");
        const ew = primaryPuppet.querySelector("#eyes_wrath");
        const mc = primaryPuppet.querySelector("#mouth_calm");
        const mt = primaryPuppet.querySelector("#mouth_talk");
        const ms = primaryPuppet.querySelector("#mouth_shout");
        const wrathSunburst = primaryPuppet.querySelector("#wrath_sunburst");

        if (emotion === "wrath") {
          if (bn && ba) {
            masterTl.to(bn, { opacity: 0, duration: 0.15 }, t_start + 0.1);
            masterTl.to(ba, { opacity: 1, duration: 0.15 }, t_start + 0.1);
          }
          if (en && ew) {
            masterTl.to(en, { opacity: 0, duration: 0.15 }, t_start + 0.1);
            masterTl.to(ew, { opacity: 1, duration: 0.15 }, t_start + 0.1);
          }
          if (wrathSunburst) {
            masterTl.fromTo(wrathSunburst, { opacity: 0, scale: 0.85 }, { opacity: 0.65, scale: 1.05, duration: 0.45, ease: "back.out(2)" }, t_start + 0.05);
            masterTl.to(wrathSunburst, { rotation: 45, duration: dur, ease: "none" }, t_start + 0.05);
          }
        }

        // Lip-sync toggling
        if (mc && mt && ms) {
          const step = Math.max(0.4, dur / 6.0);
          masterTl.set(mc, { opacity: 0 }, t_start + 0.15);
          masterTl.set(mt, { opacity: 1 }, t_start + 0.15);
          masterTl.set(mt, { opacity: 0 }, t_start + 0.15 + step);
          masterTl.set(ms, { opacity: 1 }, t_start + 0.15 + step);
          masterTl.set(ms, { opacity: 0 }, t_start + 0.15 + step * 2);
          masterTl.set(mt, { opacity: 1 }, t_start + 0.15 + step * 2);
          masterTl.set(mt, { opacity: 0 }, t_start + 0.15 + step * 3);
          masterTl.set(ms, { opacity: 1 }, t_start + 0.15 + step * 3);
          masterTl.set(ms, { opacity: 0 }, t_end - 0.25);
          masterTl.set(mc, { opacity: 1 }, t_end - 0.25);
        }
      }
    }
    else if (shotType === "two_character_confrontation") {
      const p1 = primaryPuppet;
      const p2 = allPuppets.length > 1 ? allPuppets[1] : null;
      if (p1) {
        masterTl.set(p1, { display: "block", opacity: 1, scale: 1.10, x: -180, y: 130 }, t_start);
        applyPose(p1, "action_raised", t_start, 0.4);
      }
      if (p2) {
        masterTl.set(p2, { display: "block", opacity: 1, scale: 1.10, x: 180, y: 130, scaleX: -1.10 }, t_start);
        applyPose(p2, "blessing_calm", t_start, 0.4);
      }
    }
    else if (shotType === "dramatic_climax" || shotType === "cosmic_strike" || shotType === "crushed_submission") {
      if (primaryPuppet) {
        masterTl.set(primaryPuppet, { display: "block", opacity: 1, scale: 1.18, x: 0, y: 180 }, t_start);
        applyPose(primaryPuppet, posePreset, t_start, 0.3);
      }

      // Climax strike flash
      if (wrathFlash) {
        masterTl.fromTo(wrathFlash, { opacity: 0 }, { opacity: 0.80, duration: 0.08, ease: "power1.in" }, t_start + 0.1);
        masterTl.to(wrathFlash, { opacity: 0, duration: 0.30, ease: "power2.out" }, t_start + 0.18);
      }

      // Mount Kailash / Strike SVG elements if present
      const divineLaser = shotEl.querySelector("#divine_laser_beam");
      const boulders = shotEl.querySelector("#falling_boulders");
      if (divineLaser) {
        masterTl.fromTo(divineLaser, { opacity: 0, scaleY: 0 }, { opacity: 1, scaleY: 1, duration: 0.16, ease: "power4.in", transformOrigin: "540px 0px" }, t_start + 0.1);
        masterTl.to(divineLaser, { opacity: 0, duration: 0.40, ease: "power2.out" }, t_start + 0.3);
      }
      if (boulders) {
        masterTl.to(boulders, { opacity: 1, duration: 0.1 }, t_start + 0.25);
      }

      // Foreground mountain underside pressing down if present
      const fgMountain = shotEl.querySelector(".foreground-wrapper") || document.querySelector("#foreground_mountain_container");
      if (fgMountain) {
        masterTl.fromTo(fgMountain, { y: -10 }, { y: 65, duration: dur, ease: "sine.inOut" }, t_start);
      }
    }
    else {
      // Standard: character_medium / character_advance
      if (primaryPuppet) {
        masterTl.set(primaryPuppet, { display: "block", opacity: 1, scale: 1.15, x: 0, y: 120 }, t_start);
        applyPose(primaryPuppet, posePreset, t_start, 0.8);

        // Puppet subtle stride kinematics
        masterTl.to(primaryPuppet, {
          "--rot-thigh-l": "8deg",
          "--rot-calf-l": "-12deg",
          "--rot-thigh-left": "8deg",
          "--rot-shin-left": "-12deg",
          duration: 0.85,
          yoyo: true,
          repeat: Math.ceil(dur / 0.85),
          ease: "sine.inOut"
        }, t_start);

        masterTl.to(primaryPuppet, {
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
  });

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
