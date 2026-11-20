/**
 * Sutradhar HyperFrames 0.9.70 Visual Composition Engine
 * Deterministic frame-stepping, 2026 Shorts safe-zones, triple visual modes,
 * frame-locked canvas particles, and word-accurate karaoke subtitles.
 */

(function () {
  "use strict";

  // Safe fallback manifest for standalone inspection or initial lint
  const fallbackManifest = {
    schema_version: "1.0",
    series_id: 1,
    series_title: "Echoes of Kailash",
    pillar: "Ancient Epics & Lore",
    episode_number_in_series: 1,
    total_planned_episodes: 3,
    global_episode_number: 1,
    youtube_title: "The Secret Geometry Beneath Mount Kailash (Part 1/3) #Shorts",
    audio: {
      total_duration_sec: 45.0,
      total_frames: 1350,
      sample_rate: 24000,
    },
    scenes: [
      {
        scene_index: 1,
        narration_text: "Welcome to Sutradhar. What if the most sacred peak on Earth is an ancient monument?",
        caption_text: "Welcome to Sutradhar. What if the most sacred peak on Earth is an ancient monument?",
        visual_mode: "character_drama",
        backdrop_rig: "mount_kailash",
        primary_character: "sutradhar_narrator",
        secondary_character: null,
        diagram_rig: null,
        active_diagram_stage: null,
        callout_headline: null,
        callout_subtext: null,
        emotion: "calm",
        action_gesture: "idle_breathe",
        mood_palette: "golden_imperial",
        particle_theme: "golden_embers",
        camera_motion: "slow_push",
        start_sec: 0.0,
        end_sec: 6.0,
        duration_sec: 6.0,
        words: [
          { word: "Welcome", global_start: 0.2, global_end: 0.7 },
          { word: "to", global_start: 0.7, global_end: 0.9 },
          { word: "Sutradhar.", global_start: 0.9, global_end: 1.6 },
          { word: "What", global_start: 1.8, global_end: 2.1 },
          { word: "if", global_start: 2.1, global_end: 2.3 },
          { word: "the", global_start: 2.3, global_end: 2.5 },
          { word: "most", global_start: 2.5, global_end: 2.9 },
          { word: "sacred", global_start: 2.9, global_end: 3.4 },
          { word: "peak", global_start: 3.4, global_end: 3.8 },
          { word: "on", global_start: 3.8, global_end: 4.0 },
          { word: "Earth", global_start: 4.0, global_end: 4.5 },
          { word: "is", global_start: 4.5, global_end: 4.7 },
          { word: "an", global_start: 4.7, global_end: 4.9 },
          { word: "ancient", global_start: 4.9, global_end: 5.4 },
          { word: "monument?", global_start: 5.4, global_end: 5.9 }
        ]
      }
    ]
  };

  const manifest = window.EPISODE_MANIFEST || fallbackManifest;
  const rootEl = document.getElementById("root");
  const totalDuration = Number(manifest.audio?.total_duration_sec) || 45.0;

  // 1. Sync Root Composition Duration to Exact Audio Duration
  if (rootEl) {
    rootEl.setAttribute("data-duration", totalDuration.toFixed(2));
  }

  // 2. Setup Top Series Badge
  const badgePartEl = document.getElementById("badge-part");
  const badgeSeriesEl = document.getElementById("badge-series");
  if (badgePartEl) {
    badgePartEl.textContent = `PART ${manifest.episode_number_in_series || 1} OF ${manifest.total_planned_episodes || 3}`;
  }
  if (badgeSeriesEl) {
    badgeSeriesEl.textContent = String(manifest.series_title || "SUTRADHAR").toUpperCase();
  }

  // Helper: Synchronous SVG Template Cloner
  function cloneSvgTemplate(templateId) {
    const tmpl = document.getElementById(templateId);
    if (!tmpl) {
      console.warn(`[WARN] Missing SVG template: ${templateId}`);
      const fallback = document.createElement("div");
      fallback.innerHTML = `<svg viewBox="0 0 800 800" width="100%" height="100%"><circle cx="400" cy="400" r="200" fill="#333"/></svg>`;
      return fallback.firstElementChild;
    }
    return tmpl.content.firstElementChild.cloneNode(true);
  }

  // Helper: Seeded PRNG for Deterministic Frame-Locked Particles
  function seededPrng(seed) {
    let s = Math.sin(seed) * 10000;
    return s - Math.floor(s);
  }

  // Initialize Canvas Particles
  const canvas = document.getElementById("fx-canvas");
  const ctx = canvas ? canvas.getContext("2d") : null;
  const PARTICLE_COUNT = 90;
  const particles = [];
  for (let i = 0; i < PARTICLE_COUNT; i++) {
    particles.push({
      x: seededPrng(i * 1.33 + 7) * 1080,
      y: seededPrng(i * 2.71 + 13) * 1920,
      radius: 1.8 + seededPrng(i * 3.14 + 19) * 4.2,
      speedY: 25 + seededPrng(i * 4.11 + 23) * 55,
      speedX: -20 + seededPrng(i * 5.23 + 29) * 40,
      alpha: 0.35 + seededPrng(i * 6.07 + 31) * 0.55,
      phase: seededPrng(i * 7.19 + 37) * Math.PI * 2,
    });
  }

  function renderParticles(timeSec, theme) {
    if (!ctx) return;
    ctx.clearRect(0, 0, 1080, 1920);

    for (let i = 0; i < particles.length; i++) {
      const p = particles[i];
      let x, y, r, alpha, fillStyle;

      if (theme === "golden_embers") {
        // Floating upwards embers
        y = (p.y - p.speedY * timeSec) % 1920;
        if (y < 0) y += 1920;
        x = (p.x + Math.sin(timeSec * 1.2 + p.phase) * 25) % 1080;
        if (x < 0) x += 1080;
        r = p.radius * (0.8 + 0.3 * Math.sin(timeSec * 2.5 + p.phase));
        alpha = p.alpha * (0.6 + 0.4 * Math.cos(timeSec * 1.8 + p.phase));
        fillStyle = `rgba(255, 215, 0, ${alpha.toFixed(3)})`;
      } else if (theme === "starfield_warp") {
        // Starfield radial / vertical streak
        y = (p.y + p.speedY * 1.8 * timeSec) % 1920;
        x = (p.x + (p.x - 540) * 0.15 * Math.sin(timeSec * 0.8)) % 1080;
        if (x < 0) x += 1080;
        r = p.radius * 0.9;
        alpha = p.alpha * 0.85;
        fillStyle = `rgba(180, 220, 255, ${alpha.toFixed(3)})`;
      } else if (theme === "quantum_nodes") {
        // Network pulsating nodes
        x = (p.x + Math.cos(timeSec * 0.8 + p.phase) * 30) % 1080;
        y = (p.y + Math.sin(timeSec * 0.8 + p.phase) * 30) % 1920;
        if (x < 0) x += 1080;
        if (y < 0) y += 1920;
        r = p.radius * (0.7 + 0.5 * Math.sin(timeSec * 3.0 + p.phase));
        alpha = p.alpha * 0.75;
        fillStyle = `rgba(56, 189, 248, ${alpha.toFixed(3)})`;
      } else {
        // mystic_mist / gentle drift
        x = (p.x + timeSec * 15 + Math.sin(timeSec * 0.5 + p.phase) * 40) % 1080;
        y = (p.y - timeSec * 10 + Math.cos(timeSec * 0.5 + p.phase) * 20) % 1920;
        if (x < 0) x += 1080;
        if (y < 0) y += 1920;
        r = p.radius * 2.0;
        alpha = p.alpha * 0.35;
        fillStyle = `rgba(200, 210, 230, ${alpha.toFixed(3)})`;
      }

      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fillStyle = fillStyle;
      ctx.fill();
    }
  }

  // 3. Create Paused GSAP Master Timeline
  const tl = gsap.timeline({ paused: true });
  window.__timelines = window.__timelines || {};
  window.__timelines["main"] = tl;

  // Track canvas particle animation frame-locked with timeline
  const fxTracker = { time: 0, theme: "golden_embers" };
  tl.to(
    fxTracker,
    {
      time: totalDuration,
      duration: totalDuration,
      ease: "none",
      onUpdate: () => renderParticles(fxTracker.time, fxTracker.theme),
    },
    0
  );

  // 4. Mount and Animate Each Scene
  const sceneContainer = document.getElementById("scene-container");
  const captionTextEl = document.getElementById("caption-text");

  manifest.scenes.forEach((scene) => {
    const sStart = Number(scene.start_sec);
    const sDur = Number(scene.duration_sec);
    const sEnd = sStart + sDur;
    const moodClass = `mood-${scene.mood_palette || "golden_imperial"}`;

    // Update active particle theme for this scene
    tl.call(() => {
      fxTracker.theme = scene.particle_theme || "golden_embers";
    }, null, sStart);

    // Create Scene Clip Host
    const sceneClip = document.createElement("div");
    sceneClip.id = `scene_${scene.scene_index}`;
    sceneClip.className = `clip scene-host ${moodClass}`;
    sceneClip.setAttribute("data-start", sStart.toFixed(2));
    sceneClip.setAttribute("data-duration", sDur.toFixed(2));
    sceneClip.style.opacity = "0";

    // A. Backdrop Layer
    const backdropLayer = document.createElement("div");
    backdropLayer.className = "backdrop-layer";
    const bgTmplId = `tmpl-bg_${scene.backdrop_rig || "mount_kailash"}`;
    const bgSvg = cloneSvgTemplate(bgTmplId);
    backdropLayer.appendChild(bgSvg);
    sceneClip.appendChild(backdropLayer);

    // B. Focal Stage (Characters / Diagrams / Callouts)
    const focalStage = document.createElement("div");
    focalStage.className = "scene-focal-stage";

    if (scene.visual_mode === "character_drama") {
      const charHost = document.createElement("div");
      charHost.className = "character-host";
      const charTmplId = `tmpl-char_${scene.primary_character || "sutradhar_narrator"}`;
      const charSvg = cloneSvgTemplate(charTmplId);
      charHost.appendChild(charSvg);
      focalStage.appendChild(charHost);

      // Articulated Character Animations via GSAP Timeline
      const charBody = charSvg.querySelector("#char_body");
      const charHead = charSvg.querySelector("#char_head");
      const armRight = charSvg.querySelector("#arm_right");
      const eyesClosed = charSvg.querySelector("#eyes_closed");
      const eyesOpen = charSvg.querySelector("#eyes_open");

      // Breathing loop
      if (charBody) {
        tl.to(
          charBody,
          {
            scaleY: 1.025,
            transformOrigin: "400px 700px",
            duration: 1.4,
            repeat: Math.ceil(sDur / 1.4),
            yoyo: true,
            ease: "sine.inOut",
          },
          sStart
        );
      }

      // Head tilt
      if (charHead) {
        tl.to(
          charHead,
          {
            rotation: scene.emotion === "wrath" ? -4 : 3,
            transformOrigin: "400px 340px",
            duration: 2.0,
            repeat: Math.ceil(sDur / 2.0),
            yoyo: true,
            ease: "power1.inOut",
          },
          sStart
        );
      }

      // Gesture based on action_gesture
      if (armRight) {
        let targetRot = 0;
        if (scene.action_gesture === "raise_weapon") targetRot = -30;
        else if (scene.action_gesture === "point_accuse") targetRot = -15;
        else if (scene.action_gesture === "bless_hand") targetRot = -22;
        else targetRot = 5;

        tl.to(
          armRight,
          {
            rotation: targetRot,
            transformOrigin: "520px 480px",
            duration: 1.2,
            repeat: Math.ceil(sDur / 1.2),
            yoyo: true,
            ease: "sine.inOut",
          },
          sStart
        );
      }

      // Blinks
      if (eyesClosed && eyesOpen) {
        for (let b = sStart + 1.2; b < sEnd - 0.5; b += 2.2) {
          tl.set(eyesClosed, { opacity: 1 }, b);
          tl.set(eyesOpen, { opacity: 0 }, b);
          tl.set(eyesClosed, { opacity: 0 }, b + 0.15);
          tl.set(eyesOpen, { opacity: 1 }, b + 0.15);
        }
      }
    } else if (scene.visual_mode === "explainer_diagram") {
      const diagHost = document.createElement("div");
      diagHost.className = "diagram-host";
      const diagTmplId = `tmpl-diag_${scene.diagram_rig || "black_hole_anatomy"}`;
      const diagSvg = cloneSvgTemplate(diagTmplId);
      diagHost.appendChild(diagSvg);
      focalStage.appendChild(diagHost);

      // Progressive Stage Reveals (Stages 1..4)
      const targetStage = scene.active_diagram_stage || 1;
      const allDiagGroups = Array.from(diagSvg.querySelectorAll("g"));
      for (let s = 1; s <= 4; s++) {
        const stageGroup = allDiagGroups.find((el) => el.getAttribute("id") === "stage_" + s);
        if (stageGroup) {
          if (s <= targetStage) {
            stageGroup.style.opacity = "1";
            tl.fromTo(
              stageGroup,
              { opacity: 0, scale: 0.95, transformOrigin: "450px 450px" },
              { opacity: 1, scale: 1.0, duration: 0.6, ease: "power2.out" },
              sStart + 0.15 * s
            );
          } else {
            stageGroup.style.opacity = "0.15";
          }
        }
      }

      // Pulse Highlight Ring
      const highlightPulse = diagSvg.querySelector("#highlight_pulse");
      if (highlightPulse) {
        tl.to(
          highlightPulse,
          {
            scale: 1.18,
            opacity: 0.6,
            transformOrigin: "450px 450px",
            duration: 0.9,
            repeat: Math.ceil(sDur / 0.9),
            yoyo: true,
            ease: "sine.inOut",
          },
          sStart
        );
      }
    } else {
      // visual_mode: kinetic_callout
      const calloutCard = document.createElement("div");
      calloutCard.className = "callout-card";
      const headline = document.createElement("div");
      headline.className = "callout-card-headline";
      headline.textContent = scene.callout_headline || "CRITICAL MOMENT";
      const subtext = document.createElement("div");
      subtext.className = "callout-card-subtext";
      subtext.textContent = scene.callout_subtext || scene.caption_text;

      calloutCard.appendChild(headline);
      calloutCard.appendChild(subtext);
      focalStage.appendChild(calloutCard);

      tl.fromTo(
        calloutCard,
        { scale: 0.88, opacity: 0 },
        { scale: 1.0, opacity: 1, duration: 0.5, ease: "back.out(1.5)" },
        sStart + 0.1
      );
    }

    sceneClip.appendChild(focalStage);

    // Camera Motion & Backdrop Parallax (Smooth Multi-Plane Movement)
    if (scene.camera_motion === "dramatic_zoom") {
      tl.fromTo(
        backdropLayer,
        { scale: 1.02, y: 0 },
        { scale: 1.10, y: -20, duration: sDur, ease: "power1.out" },
        sStart
      );
      tl.fromTo(
        focalStage,
        { scale: 1.0 },
        { scale: 1.08, duration: sDur, ease: "power1.inOut" },
        sStart
      );
    } else {
      tl.fromTo(
        backdropLayer,
        { scale: 1.04, y: -12 },
        { scale: 1.09, y: 12, duration: sDur, ease: "sine.inOut" },
        sStart
      );
      tl.fromTo(
        focalStage,
        { scale: 1.02, y: 0 },
        { scale: 1.05, y: -16, duration: sDur, ease: "sine.inOut" },
        sStart
      );
    }

    // Clip visibility entrance / exit
    tl.set(sceneClip, { opacity: 1 }, sStart);
    tl.set(sceneClip, { opacity: 0 }, sEnd);

    if (sceneContainer) {
      sceneContainer.appendChild(sceneClip);
    }

    // C. Word-Accurate Karaoke Subtitles
    if (captionTextEl && Array.isArray(scene.words) && scene.words.length > 0) {
      // Build word spans HTML for this scene
      const wordSpans = scene.words
        .map(
          (w, idx) =>
            `<span id="w_${scene.scene_index}_${idx}" class="caption-word">${w.word} </span>`
        )
        .join("");

      // Populate text at scene start
      tl.call(() => {
        captionTextEl.innerHTML = wordSpans;
      }, null, sStart);

      // Animate word highlight at exact word timestamp
      scene.words.forEach((w, idx) => {
        const wStart = Number(w.global_start);
        const wEnd = Number(w.global_end);
        const wordDomId = "w_" + scene.scene_index + "_" + idx;

        tl.call(() => {
          const el = document.getElementById(wordDomId);
          if (el) el.classList.add("active");
        }, null, wStart);

        tl.call(() => {
          const el = document.getElementById(wordDomId);
          if (el) el.classList.remove("active");
        }, null, wEnd);
      });
    }
  });

  // Clear subtitles after finale
  if (captionTextEl) {
    tl.call(() => {
      captionTextEl.innerHTML = "";
    }, null, totalDuration);
  }

  console.log(`[INFO] Sutradhar Engine initialized: ${manifest.scenes?.length || 0} scenes, ${totalDuration.toFixed(2)}s`);
})();
