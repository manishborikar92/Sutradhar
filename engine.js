// Sutradhar v2.2 Master Choreography Engine
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
