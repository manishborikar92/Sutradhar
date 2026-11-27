/**
 * Sutradhar v2 Deterministic Seek Runtime, Math Utilities & Camera Rig.
 * Zero Math.random(), zero Date.now(), zero repeat:-1, 100% hf-seek idempotent.
 */

export const CANVAS_WIDTH = 1080;
export const CANVAS_HEIGHT = 1920;
export const DEFAULT_HORIZON_Y = 1142;

export const clamp = (v, lo = 0, hi = 1) => (v < lo ? lo : v > hi ? hi : v);
export const lerp = (a, b, t) => a + (b - a) * clamp(t, 0, 1);
export const smooth = (t) => {
  const c = clamp(t, 0, 1);
  return c * c * (3 - 2 * c);
};
export const easeOutCubic = (t) => 1 - Math.pow(1 - clamp(t, 0, 1), 3);
export const easeOutBack = (t) => {
  const c = clamp(t, 0, 1);
  const c1 = 1.70158;
  return 1 + (c1 + 1) * Math.pow(c - 1, 3) + c1 * Math.pow(c - 1, 2);
};
export const wrap = (v, m) => ((v % m) + m) % m;
export const safeR = (r) => Math.max(1, r);

export function parseHexColor(hex) {
  return [1, 3, 5].map((i) => parseInt(hex.substr(i, 2), 16));
}

export function mixColor(a, b, t) {
  const k = clamp(t, 0, 1);
  return a.map((v, i) => v + (b[i] - v) * k);
}

export function rgbaCss(rgb, a = 1) {
  return `rgba(${rgb[0] | 0},${rgb[1] | 0},${rgb[2] | 0},${clamp(a, 0, 1).toFixed(3)})`;
}

/**
 * Deterministic 32-bit Mulberry32 PRNG returning floats in [0, 1).
 */
export function mulberry32(seed) {
  let a = seed >>> 0;
  return function next() {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function drawGlow(ctx, x, y, rIn, rOut, colIn, colOut = "rgba(0, 0, 0, 0)") {
  const rad = safeR(rOut);
  const g = ctx.createRadialGradient(x, y, safeR(rIn), x, y, rad);
  g.addColorStop(0, colIn);
  g.addColorStop(1, colOut);
  ctx.fillStyle = g;
  ctx.beginPath();
  ctx.arc(x, y, rad, 0, Math.PI * 2);
  ctx.fill();
}

/**
 * Compute parallax offset helpers for depth factors in [0.03 .. 1.0].
 */
export function createParallaxOffsets(panX = 0, panY = 0) {
  return {
    ox: (depthFactor = 1.0) => panX * depthFactor,
    oy: (depthFactor = 1.0) => panY * depthFactor,
  };
}

/**
 * Apply subtle rack-focus dimming behind foreground hero elements.
 */
export function applyFocusRack(ctx, strength, width = CANVAS_WIDTH, height = CANVAS_HEIGHT) {
  const alpha = clamp(strength, 0, 0.75);
  if (alpha <= 0.01) return;
  ctx.fillStyle = `rgba(6, 8, 22, ${alpha.toFixed(3)})`;
  ctx.fillRect(-120, -120, width + 240, height + 240);
}

/**
 * Apply subtle camera breathing zoom + horizontal drift around stage center.
 */
export function applyCameraTransform(ctx, t, localT, opts = {}) {
  const width = opts.width || CANVAS_WIDTH;
  const height = opts.height || CANVAS_HEIGHT;
  const baseZoom = opts.baseZoom ?? 1.016;
  const ampZoom = opts.ampZoom ?? 0.008;
  const driftZoom = opts.driftZoom ?? 0.014;
  const panAmpX = opts.panAmpX ?? 9;
  const panY = opts.panY ?? 0;

  const camZoom = baseZoom + Math.sin(t * 0.48) * ampZoom + (localT / 16) * driftZoom;
  const camPanX = Math.sin(t * 0.55) * panAmpX;

  ctx.translate(width * 0.5 + camPanX, height * 0.5 + panY);
  ctx.scale(camZoom, camZoom);
  ctx.translate(-width * 0.5, -height * 0.5);
}

/**
 * Find the active scene index and local elapsed time for absolute timestamp `t`.
 */
export function resolveSceneAtTime(scenes, rawT, totalDuration) {
  const t = clamp(Number(rawT) || 0, 0, totalDuration);
  let idx = 0;
  for (let i = 0; i < scenes.length; i++) {
    if (t >= scenes[i].s0 && t < scenes[i].s1) {
      idx = i;
      break;
    }
    if (i === scenes.length - 1) idx = i;
  }
  const sc = scenes[idx];
  return {
    t,
    index: idx,
    scene: sc,
    localT: Math.max(0, t - sc.s0),
    sceneDuration: Math.max(0.001, sc.s1 - sc.s0),
  };
}

/**
 * Register a HyperFrames-compliant paused GSAP timeline + synchronous hf-seek listener
 * and font readiness probe.
 */
export function mountDeterministicRuntime({ compositionId, duration, renderWorld }) {
  const gsapApi = window.gsap;
  if (!gsapApi) {
    throw new Error("GSAP must be loaded before mounting deterministic runtime.");
  }

  let currentT = 0;
  const renderAt = (timeSec) => {
    currentT = clamp(Number(timeSec) || 0, 0, duration);
    if (typeof renderWorld === "function") {
      renderWorld(currentT);
    }
  };

  window.renderWorld = renderAt;

  const proxy = { t: 0 };
  const tl = gsapApi.timeline({ paused: true });
  tl.fromTo(
    proxy,
    { t: 0 },
    {
      t: duration,
      duration,
      ease: "none",
      onUpdate: () => renderAt(proxy.t),
    },
    0
  );

  window.addEventListener("hf-seek", (evt) => {
    const targetTime = evt && evt.detail ? evt.detail.time : undefined;
    if (typeof targetTime === "number" && Number.isFinite(targetTime)) {
      proxy.t = clamp(targetTime, 0, duration);
      renderAt(proxy.t);
    }
  });

  renderAt(0);

  if (document.fonts && document.fonts.ready) {
    window.__sutradharFontsReady = document.fonts.ready.then(() => {
      renderAt(currentT);
      return true;
    });
  } else {
    window.__sutradharFontsReady = Promise.resolve(true);
  }

  window.__timelines = window.__timelines || {};
  window.__timelines[compositionId] = tl;
  return tl;
}
