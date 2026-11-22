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

  // Contextual Text Elements (Strictly No Subtitles - Production Typography)
  const contextualTitle = document.getElementById("contextual_title_container");
  const contextualSeriesTag = document.getElementById("contextual_series_tag");
  const contextualMainTitle = document.getElementById("contextual_main_title");
  const contextualCharLabel = document.getElementById("contextual_character_label_container");
  const contextualCharName = document.getElementById("contextual_char_name");
  const contextualCharTitle = document.getElementById("contextual_char_title");
  const contextualCta = document.getElementById("contextual_cta_container");

  const characterTitleMap = {
    "shani_dev": { name: "SHANI DEV", title: "Lord of Karma & Justice" },
    "ravana": { name: "LANKAPATI RAVANA", title: "Conqueror of the Three Worlds" },
    "surya_dev": { name: "SURYA DEV", title: "The Solar Deity" },
    "mandodari": { name: "QUEEN MANDODARI", title: "Empress of Lanka" },
    "shiva": { name: "DEVADHIDEV MAHADEV", title: "The Supreme Destroyer" }
  };
  const introducedChars = new Set();

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

      // Contextual Title Plaque (Scene 1)
      if (contextualTitle && (manifest.title || manifest.series_title || manifest.topic)) {
        if (contextualSeriesTag) {
          contextualSeriesTag.textContent = manifest.series_title || "SUTRADHAR";
        }
        if (contextualMainTitle) {
          contextualMainTitle.textContent = manifest.title || manifest.topic || "The Untold Legend";
        }
        const t_plaque_in = t_start + 0.8;
        const t_plaque_out = Math.min(t_start + 4.0, t_end - 0.4);
        masterTl.set(contextualTitle, { display: "block" }, t_plaque_in);
        masterTl.fromTo(contextualTitle,
          { opacity: 0, scale: 0.85, y: -25 },
          { opacity: 1, scale: 1.0, y: 0, duration: 0.75, ease: "back.out(1.6)" },
          t_plaque_in
        );
        masterTl.to(contextualTitle,
          { opacity: 0, y: -20, duration: 0.45, ease: "power2.in" },
          t_plaque_out
        );
        masterTl.set(contextualTitle, { display: "none" }, t_plaque_out + 0.45);
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

    // Contextual Character Introduction Label
    const charSlug = (scene.primary_character || scene.character || "").toLowerCase().trim();
    if (charSlug && !introducedChars.has(charSlug) && contextualCharLabel && contextualCharName) {
      introducedChars.add(charSlug);
      const meta = characterTitleMap[charSlug] || {
        name: charSlug.replace(/_/g, " ").toUpperCase(),
        title: "Legendary Figure"
      };
      const t_label_in = t_start + 0.6;
      const t_label_out = Math.min(t_label_in + 2.8, t_end - 0.4);

      masterTl.call(() => {
        contextualCharName.textContent = meta.name;
        if (contextualCharTitle) contextualCharTitle.textContent = meta.title;
      }, null, t_label_in);

      masterTl.set(contextualCharLabel, { display: "block" }, t_label_in);
      masterTl.fromTo(contextualCharLabel,
        { opacity: 0, x: -45 },
        { opacity: 1, x: 0, duration: 0.55, ease: "power2.out" },
        t_label_in
      );
      masterTl.to(contextualCharLabel,
        { opacity: 0, x: -25, duration: 0.40, ease: "power2.in" },
        t_label_out
      );
      masterTl.set(contextualCharLabel, { display: "none" }, t_label_out + 0.40);
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

    if (contextualCta) {
      masterTl.set(contextualCta, { display: "block" }, t_outro + 0.3);
      masterTl.fromTo(contextualCta,
        { opacity: 0, scale: 0.85, y: 30 },
        { opacity: 1, scale: 1.0, y: 0, duration: 0.70, ease: "back.out(1.5)" },
        t_outro + 0.3
      );
      masterTl.to(contextualCta, { opacity: 0, duration: 0.40, ease: "power2.in" }, total_dur - 1.8);
      masterTl.set(contextualCta, { display: "none" }, total_dur - 1.4);
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
