/**
 * Sutradhar v2 Deterministic Transitions & Compression-Safe Film Treatments.
 * Includes alpha xfade, directional whip smear, radial iris wipe, dip cut, bottom scrim,
 * vignette, and <= 6 fps quantized micro-grain (preventing H.264 bitrate bloat).
 */

import {
  CANVAS_HEIGHT,
  CANVAS_WIDTH,
  clamp,
  mulberry32,
  smooth,
} from "../core/seek_runtime.js";

export function drawAlphaCrossfade(ctx, drawPrevFn, drawNextFn, blendCanvas, progress) {
  const bCtx = blendCanvas.getContext("2d");
  const mixAlpha = smooth(progress);
  drawPrevFn(ctx);
  bCtx.setTransform(1, 0, 0, 1, 0, 0);
  bCtx.clearRect(0, 0, blendCanvas.width, blendCanvas.height);
  drawNextFn(bCtx);
  ctx.save();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.globalAlpha = mixAlpha;
  ctx.drawImage(blendCanvas, 0, 0);
  ctx.restore();
}

export function drawWhipBlurOverlay(ctx, intensity, width = CANVAS_WIDTH, height = CANVAS_HEIGHT, tint = "#101630") {
  if (intensity <= 0.02) return;
  ctx.save();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.globalAlpha = clamp(intensity * 0.65, 0, 0.65);
  ctx.fillStyle = tint;
  ctx.fillRect(0, 0, width, height);
  ctx.strokeStyle = "rgba(255, 232, 168, 0.55)";
  ctx.lineWidth = 8;
  for (let y = 180; y < height - 180; y += 90) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
  }
  ctx.restore();
}

export function drawRadialIrisWipe(ctx, drawUnderFn, drawOverFn, blendCanvas, cx, cy, progress) {
  const bCtx = blendCanvas.getContext("2d");
  const p = smooth(progress);
  drawUnderFn(ctx);
  bCtx.setTransform(1, 0, 0, 1, 0, 0);
  bCtx.clearRect(0, 0, blendCanvas.width, blendCanvas.height);
  drawOverFn(bCtx);

  const maxR = Math.hypot(
    Math.max(cx, blendCanvas.width - cx),
    Math.max(cy, blendCanvas.height - cy)
  );
  ctx.save();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.beginPath();
  ctx.arc(cx, cy, Math.max(1, p * maxR), 0, Math.PI * 2);
  ctx.clip();
  ctx.drawImage(blendCanvas, 0, 0);
  ctx.restore();
}

export function drawDipCut(ctx, progress, color = "#04050E", width = CANVAS_WIDTH, height = CANVAS_HEIGHT) {
  const p = clamp(progress, 0, 1);
  if (p <= 0.005) return;
  ctx.save();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.globalAlpha = p;
  ctx.fillStyle = color;
  ctx.fillRect(0, 0, width, height);
  ctx.restore();
}

export function drawBottomCaptionScrim(ctx, topY = 1210, width = CANVAS_WIDTH, height = CANVAS_HEIGHT) {
  const botGrad = ctx.createLinearGradient(0, topY, 0, height);
  botGrad.addColorStop(0, "rgba(4, 5, 14, 0)");
  botGrad.addColorStop(0.28, "rgba(4, 5, 14, 0.28)");
  botGrad.addColorStop(1, "rgba(3, 4, 12, 0.68)");
  ctx.fillStyle = botGrad;
  ctx.fillRect(0, topY, width, height - topY);
}

export function drawVignette(ctx, strength = 0.44, width = CANVAS_WIDTH, height = CANVAS_HEIGHT) {
  const vig = ctx.createRadialGradient(width * 0.5, height * 0.5, 420, width * 0.5, height * 0.5, 1140);
  vig.addColorStop(0, "rgba(0,0,0,0)");
  vig.addColorStop(1, `rgba(6,8,18,${clamp(strength, 0, 0.85).toFixed(3)})`);
  ctx.fillStyle = vig;
  ctx.fillRect(0, 0, width, height);
}

export function createFilmGrainPattern(seed = 8817, size = 128) {
  const cv = document.createElement("canvas");
  cv.width = size;
  cv.height = size;
  const g = cv.getContext("2d");
  const img = g.createImageData(size, size);
  const rn = mulberry32(seed);
  for (let i = 0; i < img.data.length; i += 4) {
    const v = (rn() * 255) | 0;
    img.data[i] = v;
    img.data[i + 1] = v;
    img.data[i + 2] = v;
    img.data[i + 3] = 255;
  }
  g.putImageData(img, 0, 0);
  return cv;
}

/**
 * Throttled/static film grain: caps temporal jitter to <= 6 fps (default 6 fps, or 0 for static)
 * and alpha <= 0.03 so H.264 inter-frame temporal compression stays crisp and <= 55 MB.
 */
export function drawThrottledGrain(ctx, patternCanvas, t, opts = {}) {
  const width = opts.width || CANVAS_WIDTH;
  const height = opts.height || CANVAS_HEIGHT;
  const grainFps = clamp(opts.grainFps ?? 6, 0, 6);
  const alpha = clamp(opts.alpha ?? 0.025, 0, 0.03);
  if (alpha <= 0.001) return;

  const size = patternCanvas.width || 128;
  const stepIdx = grainFps > 0 ? Math.floor(t * grainFps) : 0;
  const gx = -((stepIdx * 37) % size);
  const gy = -((stepIdx * 53) % size);

  ctx.save();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.globalAlpha = alpha;
  const pat = ctx.createPattern(patternCanvas, "repeat");
  ctx.translate(gx, gy);
  ctx.fillStyle = pat;
  ctx.fillRect(-size, -size, width + size * 2, height + size * 2);
  ctx.restore();
}
