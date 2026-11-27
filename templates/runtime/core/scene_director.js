/**
 * Sutradhar v2 Declarative Episode Scene Director & Cover Renderer.
 * Keeps index.html and cover HTML compositions lean and modular (<60 lines).
 */

import {
  CANVAS_HEIGHT,
  CANVAS_WIDTH,
  DEFAULT_HORIZON_Y,
  applyCameraTransform,
  applyFocusRack,
  clamp,
  createParallaxOffsets,
  mountDeterministicRuntime,
  parseHexColor,
  resolveSceneAtTime,
  smooth,
} from "./seek_runtime.js";
import {
  createAtmosphericPools,
  drawBirdFlock,
  drawClouds,
  drawFloraSway,
  drawKailashSacredPeak,
  drawMilkyWayBand,
  drawMotes,
  drawPine,
  drawRidges,
  drawSky,
  drawSnowyBoulders,
  drawStars,
  drawSunOrAura,
} from "../backdrops/atmosphere_v1.js";
import {
  drawClockShrineNiche,
  drawColonnadePillar,
  drawPalaceInterior,
  drawRoyalMusicStage,
  drawSteppedDais,
} from "../backdrops/architectural_stage.js";
import { drawMythCharacter } from "../rigs/character_engine.js";
import { drawRegisteredProp } from "../props/props_library.js";
import {
  createFilmGrainPattern,
  drawAlphaCrossfade,
  drawBottomCaptionScrim,
  drawDipCut,
  drawRadialIrisWipe,
  drawThrottledGrain,
  drawVignette,
  drawWhipBlurOverlay,
} from "../fx/transitions.js";

function computeSpeechMouthOpen(t) {
  const cues = Array.isArray(window.CAPTIONS_DATA) ? window.CAPTIONS_DATA : [];
  for (let i = 0; i < cues.length; i++) {
    const words = Array.isArray(cues[i].words) ? cues[i].words : [];
    for (let j = 0; j < words.length; j++) {
      const w = words[j];
      if (t >= w.start && t <= w.end) {
        const p = (t - w.start) / Math.max(0.06, w.end - w.start);
        return clamp(Math.sin(p * Math.PI) * 0.72, 0.12, 0.78);
      }
    }
  }
  return 0;
}

function drawSingleScene(targetCtx, sc, t, localT, atmoPools) {
  const env = sc.environment || {};
  const horizonY = Number(env.horizon_y ?? DEFAULT_HORIZON_Y);
  const panAmpX = Number(sc.camera?.pan_amp_x ?? 9);
  const camPanX = Math.sin(t * 0.55) * panAmpX;
  const { ox, oy } = createParallaxOffsets(camPanX, 0);

  targetCtx.save();
  applyCameraTransform(targetCtx, t, localT, {
    baseZoom: sc.camera?.base_zoom ?? 1.016,
    ampZoom: sc.camera?.amp_zoom ?? 0.008,
    driftZoom: sc.camera?.drift_zoom ?? 0.014,
    panAmpX,
  });

  const mode = env.atmosphere_mode || "kailash_twilight";
  if (mode === "palace_interior" || mode === "durbar") {
    drawPalaceInterior(targetCtx, {
      ...(env.palette || {}),
      panOffsetX: camPanX,
      t,
      hasDiyas: env.has_diyas ?? true,
      horizonY,
    });
  } else {
    const sky = env.sky || { top: "#0B112B", mid: "#1F2654", bot: "#6E304B" };
    drawSky(targetCtx, parseHexColor(sky.top), parseHexColor(sky.mid), parseHexColor(sky.bot), CANVAS_WIDTH, CANVAS_HEIGHT);
    drawMilkyWayBand(targetCtx, env.milky_way ?? 0.35, ox, oy, CANVAS_WIDTH);
    drawStars(targetCtx, atmoPools.stars, t, env.star_alpha ?? 0.75, ox, oy);
    if (env.sun !== null) {
      const sun = env.sun || {};
      drawSunOrAura(
        targetCtx,
        sun.x ?? 540,
        sun.y ?? 740,
        sun.r ?? 360,
        sun.intensity ?? sun.glow ?? 0.75,
        sun.ray_strength ?? 0.14,
        sun.ray_count ?? 14,
        t,
        parseHexColor(sun.core_col || "#FFF3D6"),
        parseHexColor(sun.halo_col || "#FFB866"),
        parseHexColor(sun.mid_col || "#C95E7A")
      );
    }
    drawClouds(targetCtx, atmoPools.clouds, t, ox, oy, parseHexColor(env.cloud_color || "#FFD6AA"), env.cloud_alpha ?? 0.20, CANVAS_WIDTH);
    drawRidges(
      targetCtx,
      env.ridge_set === "cosmos" ? atmoPools.ridgesCosmos : atmoPools.ridgesKailash,
      ox,
      oy,
      env.warmth ?? 0.35,
      parseHexColor(env.haze_color || "#8E5E7C"),
      CANVAS_HEIGHT
    );
    if (env.has_kailash) {
      drawKailashSacredPeak(targetCtx, 540 + ox(0.24), horizonY + 12, env.kailash_scale ?? 1.24);
    }
    if (env.snow_boulders !== false) {
      drawSnowyBoulders(targetCtx, env.ground_top || "#27223B", env.ground_bot || "#141022", horizonY, camPanX, t, Boolean(env.has_diyas), CANVAS_WIDTH, CANVAS_HEIGHT);
    } else {
      const flGrad = targetCtx.createLinearGradient(0, horizonY, 0, CANVAS_HEIGHT);
      flGrad.addColorStop(0, env.ground_top || "#27223B");
      flGrad.addColorStop(1, env.ground_bot || "#141022");
      targetCtx.fillStyle = flGrad;
      targetCtx.fillRect(-160, horizonY, CANVAS_WIDTH + 320, CANVAS_HEIGHT - horizonY + 140);
    }
    if (env.flora !== false) {
      drawPine(targetCtx, 128 + ox(0.55), horizonY + 4, 240, t, "#151C28");
      drawPine(targetCtx, 956 + ox(0.55), horizonY + 4, 220, t, "#151C28");
      drawFloraSway(targetCtx, 0, CANVAS_WIDTH, horizonY + 4, t, "#1D243C", 18);
    }
    drawBirdFlock(targetCtx, t, ox, oy, env.bird_color || "rgba(42, 24, 52, 0.72)", CANVAS_WIDTH);
  }

  for (const st of sc.stage_elements || []) {
    if (st.type === "pillar") drawColonnadePillar(targetCtx, st.x, st.floorY ?? horizonY, st.topY ?? 0, st.w ?? 74);
    else if (st.type === "dais") drawSteppedDais(targetCtx, st.x ?? 540, st.floorY ?? horizonY, st.w ?? 390, st.h ?? 98, { cushion: Boolean(st.cushion) });
    else if (st.type === "clock_niche") drawClockShrineNiche(targetCtx, st.x ?? 540, st.y ?? 580, st.r ?? 135, horizonY);
    else if (st.type === "royal_music_stage") drawRoyalMusicStage(targetCtx, st.x ?? 540, st.daisBot ?? 1218, t);
  }

  for (const prop of sc.props || []) {
    drawRegisteredProp(targetCtx, prop, t, localT);
  }

  if (sc.focus_rack > 0) {
    applyFocusRack(targetCtx, sc.focus_rack);
  }

  const mouthDefault = computeSpeechMouthOpen(t);
  for (const ch of sc.characters || []) {
    drawMythCharacter(targetCtx, {
      ...ch,
      t,
      mouthOpen: ch.mouthOpen !== undefined ? ch.mouthOpen : (ch.speaking ? mouthDefault : 0),
    });
  }

  drawMotes(targetCtx, atmoPools.motes, t, parseHexColor(sc.mote_color || "#FFE8B0"), sc.mote_alpha ?? 0.45, ox, oy, CANVAS_WIDTH, CANVAS_HEIGHT);
  targetCtx.restore();
}

/**
 * Mounts deterministic multi-scene director onto `#world-canvas` and `#contextual-overlay`.
 */
export function createEpisodeDirector({ canvas, episodePlan, compositionId = "main" }) {
  const duration = Number(episodePlan.duration_sec || 60.0);
  const scenes = Array.isArray(episodePlan.scenes) ? episodePlan.scenes : [];
  const enablePills = Boolean(episodePlan.enable_contextual_pills);

  const ctx = canvas.getContext("2d");
  const blendCanvas = document.createElement("canvas");
  blendCanvas.width = CANVAS_WIDTH;
  blendCanvas.height = CANVAS_HEIGHT;

  const atmoPools = createAtmosphericPools(7731);
  const grainPattern = createFilmGrainPattern(8817, 128);
  const overlayEl = document.getElementById("contextual-overlay");
  const kickerEl = document.getElementById("ctx-kicker");
  const titleEl = document.getElementById("ctx-title");

  const updateContextualPill = (sc, localT, sceneDur) => {
    if (!overlayEl) return;
    if (!enablePills || !sc || (!sc.pill_kicker && !sc.pill_title)) {
      overlayEl.style.opacity = "0";
      return;
    }
    if (kickerEl) kickerEl.textContent = sc.pill_kicker || "";
    if (titleEl) titleEl.textContent = sc.pill_title || "";
    const fadeIn = smooth(localT / 0.35);
    const fadeOut = smooth((sceneDur - localT) / 0.35);
    overlayEl.style.opacity = String(clamp(Math.min(fadeIn, fadeOut), 0, 1));
  };

  const renderWorld = (rawT) => {
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);

    if (scenes.length === 0) {
      drawSky(ctx, parseHexColor("#0B112B"), parseHexColor("#1F2654"), parseHexColor("#6E304B"), CANVAS_WIDTH, CANVAS_HEIGHT);
      const zeroOff = () => 0;
      drawStars(ctx, atmoPools.stars, rawT, 0.8, zeroOff, zeroOff);
      drawKailashSacredPeak(ctx, 540, DEFAULT_HORIZON_Y + 12, 1.24);
      updateContextualPill(null, 0, 1);
    } else {
      const state = resolveSceneAtTime(scenes, rawT, duration);
      const sc = state.scene;
      const transDur = Number(sc.transition_duration_sec ?? 0.36);

      if (state.index > 0 && state.localT < transDur) {
        const prev = scenes[state.index - 1];
        const pFrac = clamp(state.localT / Math.max(0.05, transDur), 0, 1);
        const tType = sc.transition_type || "crossfade";
        const drawPrev = (target) => drawSingleScene(target, prev, state.t, prev.s1 - prev.s0, atmoPools);
        const drawNext = (target) => drawSingleScene(target, sc, state.t, state.localT, atmoPools);

        if (tType === "iris") drawRadialIrisWipe(ctx, drawPrev, drawNext, blendCanvas, 540, 880, pFrac);
        else if (tType === "whip") { drawNext(ctx); drawWhipBlurOverlay(ctx, Math.sin(pFrac * Math.PI)); }
        else if (tType === "dip") { (pFrac < 0.5 ? drawPrev : drawNext)(ctx); drawDipCut(ctx, Math.sin(pFrac * Math.PI)); }
        else drawAlphaCrossfade(ctx, drawPrev, drawNext, blendCanvas, pFrac);
      } else {
        drawSingleScene(ctx, sc, state.t, state.localT, atmoPools);
      }
      updateContextualPill(sc, state.localT, state.sceneDuration);
    }

    drawBottomCaptionScrim(ctx, 1210);
    drawVignette(ctx, episodePlan.vignette_strength ?? 0.42);
    drawThrottledGrain(ctx, grainPattern, rawT, { grainFps: 6, alpha: episodePlan.grain_alpha ?? 0.022 });
  };

  return mountDeterministicRuntime({ compositionId, duration, renderWorld });
}

/**
 * Renders 1080x1920 vertical thumbnail cover onto `#thumb-canvas` using shared runtime modules.
 */
export function renderCoverComposition(canvas, coverConfig = {}) {
  const ctx = canvas.getContext("2d");
  const pools = createAtmosphericPools(Number(coverConfig.seed || 701));
  const zeroOff = () => 0;

  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);

  const horizonY = Number(coverConfig.horizon_y ?? 1445);
  const backdrop = coverConfig.backdrop || "cosmic_dawn";

  if (backdrop === "palace_interior") {
    drawPalaceInterior(ctx, {
      ...(coverConfig.palette || {}),
      t: Number(coverConfig.t ?? 1.0),
      hasDiyas: coverConfig.has_diyas ?? true,
      horizonY,
    });
  } else {
    const sky = coverConfig.sky || { top: "#0A102C", mid: "#192252", bot: "#3A1C32" };
    drawSky(ctx, parseHexColor(sky.top), parseHexColor(sky.mid), parseHexColor(sky.bot), CANVAS_WIDTH, CANVAS_HEIGHT);
    const maxY = Number(coverConfig.star_max_y ?? 980);
    drawStars(ctx, pools.stars.filter((s) => s.y <= maxY), 0.0, Number(coverConfig.star_alpha ?? 0.80), zeroOff, zeroOff);

    if (coverConfig.sunburst !== false) {
      const sb = coverConfig.sunburst || {};
      const cx = Number(sb.x ?? 540);
      const cy = Number(sb.y ?? 1140);
      const rayCount = Number(sb.rays ?? 18);
      ctx.save();
      ctx.translate(cx, cy);
      for (let i = 0; i < rayCount; i++) {
        const a = (i / rayCount) * Math.PI * 2;
        ctx.fillStyle = i % 2 === 0
          ? (sb.color_even || "rgba(255, 214, 102, 0.16)")
          : (sb.color_odd || "rgba(74, 245, 178, 0.08)");
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.lineTo(Math.cos(a - 0.1) * 950, Math.sin(a - 0.1) * 950);
        ctx.lineTo(Math.cos(a + 0.1) * 950, Math.sin(a + 0.1) * 950);
        ctx.closePath();
        ctx.fill();
      }
      ctx.restore();
    }

    if (coverConfig.kailash !== false) {
      const k = coverConfig.kailash || {};
      drawKailashSacredPeak(
        ctx,
        Number(k.x ?? 540),
        Number(k.base_y ?? 1452),
        Number(k.scale ?? 1.66),
        k.snow_tint || "rgba(226, 240, 255, 0.72)",
        k.shadow_tint || "#181E46",
        Number(k.gold_rim ?? 0.75)
      );
    }

    ctx.fillStyle = coverConfig.floor_color || "#2E2036";
    ctx.fillRect(0, horizonY, CANVAS_WIDTH, CANVAS_HEIGHT - horizonY);
    ctx.fillStyle = coverConfig.floor_trim || "#E6B245";
    ctx.fillRect(0, horizonY - 4, CANVAS_WIDTH, 8);
    ctx.strokeStyle = "rgba(0, 0, 0, 0.28)";
    ctx.lineWidth = 2.5;
    for (let i = -6; i <= 6; i++) {
      ctx.beginPath();
      ctx.moveTo(540 + i * 70, horizonY);
      ctx.lineTo(540 + i * 195, CANVAS_HEIGHT);
      ctx.stroke();
    }
  }

  for (const prop of coverConfig.props || []) {
    drawRegisteredProp(ctx, prop, Number(coverConfig.t ?? 1.0), 1.0);
  }
  for (const ch of coverConfig.characters || []) {
    drawMythCharacter(ctx, { t: Number(coverConfig.t ?? 1.0), ...ch });
  }
}
