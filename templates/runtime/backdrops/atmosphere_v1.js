/**
 * Sutradhar v2 V1 Atmospheric Backdrop Engine & Peak-Clamped Kailash Massif.
 * Integrates V1 multi-plane FogRidgeStack, celestial sun/rays, clouds, birds, flora sway,
 * snowy boulders, and mathematically bounded + ctx.clip()-masked Kailash snow ridges.
 */

import {
  CANVAS_HEIGHT,
  CANVAS_WIDTH,
  DEFAULT_HORIZON_Y,
  clamp,
  drawDiya,
  drawGlow,
  mixColor,
  mulberry32,
  parseHexColor,
  rgbaCss,
  wrap,
} from "../core/seek_runtime.js";

export function makeRidge(seed, base, amp, freq, width = CANVAS_WIDTH) {
  const r = mulberry32(seed);
  const p = [r() * 20, r() * 20, r() * 20];
  const pts = [];
  for (let x = -440; x <= width + 440; x += 10) {
    const h =
      0.56 * (1 - Math.abs(Math.sin(x * freq + p[0]))) +
      0.31 * (1 - Math.abs(Math.sin(x * freq * 2.3 + p[1]))) +
      0.13 * Math.sin(x * freq * 5.8 + p[2]);
    pts.push([x, base - amp * h]);
  }
  return pts;
}

export function createAtmosphericPools(seed = 409, width = CANVAS_WIDTH, height = CANVAS_HEIGHT) {
  const r = mulberry32(seed);
  const stars = Array.from({ length: 220 }, () => ({
    x: r() * width,
    y: r() * 1160,
    s: 0.9 + r() * 2.4,
    ph: r() * 6.28,
    tw: 0.9 + r() * 1.9,
  }));
  const clouds = Array.from({ length: 12 }, () => ({
    x: r() * 1700,
    y: 340 + r() * 640,
    s: 0.78 + r() * 1.18,
    v: 18 + r() * 26,
    d: 0.08 + r() * 0.34,
  }));
  const motes = Array.from({ length: 95 }, () => ({
    x: r() * width,
    y: r() * height,
    d: r(),
    ph: r() * 6.28,
    v: 16 + r() * 34,
  }));

  const ridgesKailash = [
    { pts: makeRidge(101, 1085, 310, 0.0044, width), n: parseHexColor("#222C58"), w: parseHexColor("#6874A6"), fog: 0.65, d: 0.16, a: 280, b: 1085 },
    { pts: makeRidge(202, 1130, 260, 0.0061, width), n: parseHexColor("#171E44"), w: parseHexColor("#4B5382"), fog: 0.42, d: 0.34, a: 230, b: 1130 },
    { pts: makeRidge(303, 1175, 195, 0.0094, width), n: parseHexColor("#111632"), w: parseHexColor("#2F335E"), fog: 0.20, d: 0.56, a: 170, b: 1175 },
  ];

  const ridgesCosmos = [
    { pts: makeRidge(11, 1030, 280, 0.0038, width), n: parseHexColor("#28306A"), w: parseHexColor("#6E4C8D"), fog: 0.74, d: 0.06, a: 280, b: 1030 },
    { pts: makeRidge(23, 1150, 245, 0.0049, width), n: parseHexColor("#1F2454"), w: parseHexColor("#533974"), fog: 0.60, d: 0.14, a: 245, b: 1150 },
    { pts: makeRidge(37, 1280, 210, 0.0061, width), n: parseHexColor("#16193E"), w: parseHexColor("#382658"), fog: 0.45, d: 0.28, a: 210, b: 1280 },
  ];

  return { stars, clouds, motes, ridgesKailash, ridgesCosmos };
}

export function drawSky(ctx, cTop, cMid, cBot, width = CANVAS_WIDTH, height = CANVAS_HEIGHT) {
  const g = ctx.createLinearGradient(0, 0, 0, height);
  g.addColorStop(0, rgbaCss(cTop));
  g.addColorStop(0.55, rgbaCss(cMid));
  g.addColorStop(1, rgbaCss(cBot));
  ctx.fillStyle = g;
  ctx.fillRect(-120, -120, width + 240, height + 240);
}

export function drawMilkyWayBand(ctx, alpha, ox, oy, width = CANVAS_WIDTH) {
  if (alpha <= 0.01) return;
  ctx.save();
  ctx.translate(width * 0.5 + ox(0.03), 580 + oy(0.03));
  ctx.rotate(-0.42);
  const g = ctx.createRadialGradient(0, 0, 20, 0, 0, 620);
  g.addColorStop(0, `rgba(170, 155, 255, ${(0.14 * alpha).toFixed(3)})`);
  g.addColorStop(0.45, `rgba(210, 150, 195, ${(0.07 * alpha).toFixed(3)})`);
  g.addColorStop(1, "rgba(120, 110, 220, 0)");
  ctx.scale(1.6, 0.38);
  ctx.fillStyle = g;
  ctx.beginPath();
  ctx.arc(0, 0, 620, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

export function drawStars(ctx, stars, t, alpha, ox, oy) {
  if (alpha <= 0.01) return;
  ctx.save();
  for (const st of stars) {
    const a = alpha * (0.28 + 0.72 * Math.abs(Math.sin(t * st.tw + st.ph)));
    ctx.fillStyle = `rgba(255, 246, 224, ${a.toFixed(3)})`;
    ctx.beginPath();
    ctx.arc(st.x + ox(0.03), st.y + oy(0.03), st.s, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();
}


export function drawSunOrAura(ctx, sx, sy, rad, intensity, rayStrength, rayCount, t, coreCol, haloCol, midCol) {
  if (intensity <= 0.01) return;
  const g = ctx.createRadialGradient(sx, sy, 18, sx, sy, rad);
  g.addColorStop(0, rgbaCss(coreCol, intensity));
  g.addColorStop(0.32, rgbaCss(haloCol, intensity * 0.56));
  g.addColorStop(0.70, rgbaCss(midCol, intensity * 0.22));
  g.addColorStop(1, rgbaCss(midCol, 0));
  ctx.fillStyle = g;
  ctx.beginPath();
  ctx.arc(sx, sy, rad, 0, Math.PI * 2);
  ctx.fill();

  if (rayStrength > 0.008 && rayCount > 0) {
    ctx.save();
    ctx.translate(sx, sy);
    ctx.globalCompositeOperation = "lighter";
    ctx.fillStyle = rgbaCss(coreCol, rayStrength * intensity);
    const step = (Math.PI * 2) / rayCount;
    for (let i = 0; i < rayCount; i++) {
      ctx.rotate(step + Math.sin(t * 0.55 + i) * 0.008);
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.lineTo(1950, -108);
      ctx.lineTo(1950, 108);
      ctx.closePath();
      ctx.fill();
    }
    ctx.restore();
  }
}

export function drawClouds(ctx, clouds, t, ox, oy, col, baseAlpha, width = CANVAS_WIDTH) {
  for (const c of clouds) {
    const cx = wrap(c.x + t * c.v, width + 760) - 380 + ox(c.d);
    const cy = c.y + oy(c.d);
    for (const [dx, dy, rx, ry] of [
      [-110, 10, 125, 52],
      [-48, -18, 112, 62],
      [14, -32, 134, 72],
      [78, -8, 112, 56],
      [134, 14, 102, 44],
    ]) {
      ctx.save();
      ctx.translate(cx + dx * c.s, cy + dy * c.s);
      ctx.scale(1, ry / rx);
      const g = ctx.createRadialGradient(0, 0, 0, 0, 0, rx * c.s);
      g.addColorStop(0, rgbaCss(col, baseAlpha));
      g.addColorStop(1, rgbaCss(col, 0));
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(0, 0, rx * c.s, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }
  }
}

export function drawRidges(ctx, layers, ox, oy, p, hazeCol, height = CANVAS_HEIGHT) {
  for (const l of layers) {
    const x0 = ox(l.d);
    const y0 = oy(l.d);
    const col = mixColor(l.n, l.w, p);
    ctx.beginPath();
    ctx.moveTo(l.pts[0][0] + x0, height + 500);
    for (const [px, py] of l.pts) ctx.lineTo(px + x0, py + y0);
    ctx.lineTo(l.pts[l.pts.length - 1][0] + x0, height + 500);
    ctx.closePath();
    const lg = ctx.createLinearGradient(0, l.b - l.a + y0, 0, l.b - l.a + y0 + 420);
    lg.addColorStop(0, rgbaCss(col));
    lg.addColorStop(1, rgbaCss(mixColor(col, hazeCol, l.fog)));
    ctx.fillStyle = lg;
    ctx.fill();

    ctx.strokeStyle = `rgba(255, 236, 210, ${(0.14 + 0.16 * p).toFixed(3)})`;
    ctx.lineWidth = 2.4;
    ctx.beginPath();
    for (let i = 0; i < l.pts.length; i++) {
      if (i === 0) ctx.moveTo(l.pts[i][0] + x0, l.pts[i][1] + y0);
      else ctx.lineTo(l.pts[i][0] + x0, l.pts[i][1] + y0);
    }
    ctx.stroke();
  }
}

export function drawBirdFlock(ctx, t, ox, oy, col = "rgba(42, 24, 52, 0.72)", width = CANVAS_WIDTH) {
  ctx.save();
  ctx.strokeStyle = col;
  ctx.lineWidth = 4.0;
  ctx.lineCap = "round";
  for (let i = 0; i < 6; i++) {
    const bx = width + 180 - ((t * 115 + i * 74) % (width + 420)) + ox(0.24);
    const by = 480 + Math.abs(i - 2.5) * 30 + Math.sin(t * 1.4 + i * 0.5) * 22 + oy(0.24);
    const flap = Math.sin(t * 9.2 + i * 0.8) * 14;
    ctx.beginPath();
    ctx.moveTo(bx - 22, by + flap * 0.45);
    ctx.quadraticCurveTo(bx - 9, by - 11 - flap, bx, by);
    ctx.quadraticCurveTo(bx + 9, by - 11 - flap, bx + 22, by + flap * 0.45);
    ctx.stroke();
  }
  ctx.restore();
}

export function drawPine(ctx, x, y, h, t, col) {
  ctx.save();
  ctx.fillStyle = col;
  ctx.beginPath();
  const n = 8;
  const w = h * 0.21;
  for (let i = 0; i < n; i++) {
    const f = i / n;
    const ty = y - h * f * 0.92;
    const tw = w * (1 - f * 0.78);
    const sx = Math.sin(t * 1.3 + x * 0.01) * 14 * f * f;
    ctx.moveTo(x - tw + sx * 0.5, ty);
    ctx.lineTo(x + sx, ty - h * 0.21);
    ctx.lineTo(x + tw + sx * 0.5, ty);
  }
  ctx.fill();
  ctx.fillRect(x - 6, y - 32, 12, 68);
  ctx.restore();
}

export function drawFloraSway(ctx, x0, x1, baseY, t, col, step = 16) {
  ctx.save();
  ctx.strokeStyle = col;
  ctx.lineWidth = 4;
  ctx.lineCap = "round";
  for (let gx = x0; gx < x1; gx += step) {
    const gh = 24 + ((gx * 7) % 22);
    const sw = Math.sin(t * 2.2 + gx * 0.05) * 10 + 5;
    ctx.beginPath();
    ctx.moveTo(gx, baseY);
    ctx.quadraticCurveTo(gx + sw * 0.3, baseY - gh * 0.6, gx + sw, baseY - gh);
    ctx.stroke();
  }
  ctx.restore();
}

export function drawMotes(ctx, motes, t, col, alphaScale, ox, oy, width = CANVAS_WIDTH, height = CANVAS_HEIGHT) {
  ctx.save();
  ctx.globalCompositeOperation = "lighter";
  for (const q of motes) {
    const mx = wrap(q.x + Math.sin(t * 0.72 + q.ph) * 46, width + 220) - 110 + ox(0.3 + q.d * 0.9);
    const my = wrap(q.y - t * q.v * (0.65 + q.d), height + 220) - 110 + oy(0.3 + q.d * 0.9);
    const a = (0.24 + 0.56 * Math.abs(Math.sin(t * 1.7 + q.ph))) * (0.55 + 0.45 * q.d) * alphaScale;
    const rad = 1.6 + q.d * 4.4;
    ctx.fillStyle = rgbaCss(col, a * 0.22);
    ctx.beginPath();
    ctx.arc(mx, my, rad * 4.0, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = rgbaCss(col, a);
    ctx.beginPath();
    ctx.arc(mx, my, rad, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();
}

/**
 * Deterministic rising fire embers and drifting smoke wisps for crimson/fire climax scenes.
 */
export function drawFireEmbersAndSmoke(ctx, motes, t, ox, oy, width = CANVAS_WIDTH, height = CANVAS_HEIGHT) {
  ctx.save();
  // Soft drifting smoke wisps across upper/mid frame
  for (let i = 0; i < 7; i++) {
    const sx = wrap(i * 190 + t * (28 + (i % 3) * 11), width + 420) - 210 + ox(0.25);
    const sy = 360 + (i % 4) * 180 + Math.sin(t * 0.9 + i * 1.7) * 28 + oy(0.2);
    const rx = 180 + (i % 3) * 45;
    const ry = 68 + (i % 2) * 24;
    ctx.save();
    ctx.translate(sx, sy);
    ctx.scale(1, ry / rx);
    const sg = ctx.createRadialGradient(0, 0, 8, 0, 0, rx);
    sg.addColorStop(0, "rgba(38, 14, 12, 0.34)");
    sg.addColorStop(0.55, "rgba(72, 22, 14, 0.16)");
    sg.addColorStop(1, "rgba(24, 8, 8, 0)");
    ctx.fillStyle = sg;
    ctx.beginPath();
    ctx.arc(0, 0, rx, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  // Rising glowing fire embers
  ctx.globalCompositeOperation = "lighter";
  for (let i = 0; i < motes.length; i++) {
    const q = motes[i];
    const ex = wrap(q.x + Math.sin(t * 1.45 + q.ph) * 62, width + 180) - 90 + ox(0.4 + q.d * 0.8);
    const ey = wrap(q.y - t * (q.v * 1.9 + 42) * (0.7 + q.d * 0.8), height + 200) - 100 + oy(0.4 + q.d * 0.8);
    const flicker = 0.45 + 0.55 * Math.abs(Math.sin(t * 4.2 + q.ph));
    const rad = 2.0 + q.d * 4.2;
    ctx.fillStyle = `rgba(255, 112, 36, ${(0.24 * flicker).toFixed(3)})`;
    ctx.beginPath();
    ctx.arc(ex, ey, rad * 3.8, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = `rgba(255, 214, 108, ${(0.78 * flicker).toFixed(3)})`;
    ctx.beginPath();
    ctx.arc(ex, ey, rad, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();
}


export function drawSnowyBoulders(ctx, floorTopCol, floorBotCol, horizonY = DEFAULT_HORIZON_Y, panOffsetX = 0, t = 0, hasDiyas = false, width = CANVAS_WIDTH, height = CANVAS_HEIGHT) {
  const fg = ctx.createLinearGradient(0, horizonY - 24, 0, height);
  fg.addColorStop(0, floorTopCol);
  fg.addColorStop(0.35, floorBotCol);
  fg.addColorStop(1, "#090B16");
  ctx.fillStyle = fg;
  ctx.fillRect(-60, horizonY - 12, width + 120, height - horizonY + 80);

  ctx.fillStyle = "rgba(220, 232, 252, 0.20)";
  ctx.beginPath();
  ctx.moveTo(-40, horizonY - 8);
  for (let x = -40; x <= width + 60; x += 64) {
    ctx.lineTo(x, horizonY - 14 + Math.sin(x * 0.03 + panOffsetX * 0.01) * 7);
  }
  ctx.lineTo(width + 60, horizonY + 12);
  ctx.lineTo(-40, horizonY + 12);
  ctx.closePath();
  ctx.fill();

  for (const [bx, bw, bh] of [[85, 195, 92], [995, 205, 98]]) {
    ctx.fillStyle = "#1B2038";
    ctx.strokeStyle = "#0B0D1C";
    ctx.lineWidth = 2.8;
    ctx.beginPath();
    ctx.moveTo(bx - bw, horizonY + 60);
    ctx.lineTo(bx - bw * 0.55, horizonY - bh * 0.65);
    ctx.lineTo(bx + bw * 0.15, horizonY - bh);
    ctx.lineTo(bx + bw, horizonY + 60);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = "rgba(226, 236, 255, 0.65)";
    ctx.beginPath();
    ctx.moveTo(bx - bw * 0.52, horizonY - bh * 0.62);
    ctx.lineTo(bx + bw * 0.15, horizonY - bh);
    ctx.lineTo(bx + bw * 0.45, horizonY - bh * 0.48);
    ctx.quadraticCurveTo(bx, horizonY - bh * 0.35, bx - bw * 0.52, horizonY - bh * 0.62);
    ctx.closePath();
    ctx.fill();
  }

  ctx.strokeStyle = "rgba(255, 224, 150, 0.12)";
  ctx.lineWidth = 1.6;
  for (let k = 1; k <= 6; k++) {
    const hy = horizonY + Math.pow(k / 6, 1.4) * (height - horizonY);
    ctx.beginPath();
    ctx.moveTo(0, hy);
    ctx.lineTo(width, hy);
    ctx.stroke();
  }

  if (hasDiyas) {
    for (const dx of [185, 895]) {
      drawDiya(ctx, dx, horizonY + 14, t, {
        phase: dx,
        radiusW: 16,
        radiusH: 7,
        flameW: 5.5,
        flameH: 10,
        glowR: 48,
        glowAlpha: 0.72,
        flickerSpeed: 8.6,
        flickerAmp: 0.15,
      });
    }
  }
}

export const KAILASH_SILHOUETTE_POINTS = [
  [-430, 40],
  [-290, -118],
  [-228, -142],
  [-175, -196],
  [-120, -242],
  [-56, -342],
  [-18, -386],
  [14, -396],
  [48, -360],
  [118, -264],
  [175, -195],
  [240, -162],
  [320, -104],
  [430, 40],
];

/**
 * Bounded snow gullies in local mountain coordinates (each well inside KAILASH_SILHOUETTE_POINTS).
 */
export const KAILASH_SNOW_GULLIES = [
  [-118, -178, 46, 26],
  [102, -202, 52, 32],
  [26, -172, 46, 36],
];

export function traceKailashSilhouette(ctx) {
  ctx.beginPath();
  ctx.moveTo(KAILASH_SILHOUETTE_POINTS[0][0], KAILASH_SILHOUETTE_POINTS[0][1]);
  for (let i = 1; i < KAILASH_SILHOUETTE_POINTS.length; i++) {
    ctx.lineTo(KAILASH_SILHOUETTE_POINTS[i][0], KAILASH_SILHOUETTE_POINTS[i][1]);
  }
  ctx.closePath();
}

/**
 * Fixed Sacred Snow-Draped Kailash Massif:
 * All snow caps, facet shadows, and diagonal glacial gullies are mathematically bounded
 * AND strictly clipped via `ctx.clip()` to the outer silhouette path so zero snow fin ever overhangs.
 */
export function drawKailashSacredPeak(
  targetCtx,
  cx,
  baseY,
  s = 1.24,
  snowTint = "rgba(235, 242, 255, 0.78)",
  shadowTint = "#1E224A",
  goldRim = 0.6
) {
  targetCtx.save();
  targetCtx.translate(cx, baseY);
  targetCtx.scale(s, s);

  const mg = targetCtx.createLinearGradient(-320, -400, 260, 40);
  mg.addColorStop(0, shadowTint);
  mg.addColorStop(0.55, "#323D72");
  mg.addColorStop(1, "#202752");
  targetCtx.fillStyle = mg;
  traceKailashSilhouette(targetCtx);
  targetCtx.fill();

  // Clip EVERY facet shadow, snow cap, and diagonal gully strictly inside outer mountain path!
  targetCtx.save();
  traceKailashSilhouette(targetCtx);
  targetCtx.clip();

  // Sculpted rock ridge facet shadow on left side
  targetCtx.fillStyle = "rgba(12, 16, 38, 0.42)";
  targetCtx.beginPath();
  targetCtx.moveTo(4, -392);
  targetCtx.lineTo(-18, -386);
  targetCtx.lineTo(-120, -242);
  targetCtx.lineTo(-430, 40);
  targetCtx.lineTo(-25, 40);
  targetCtx.lineTo(-12, -220);
  targetCtx.closePath();
  targetCtx.fill();

  // Secondary rocky mid-ridge crags for volumetric depth on right face
  targetCtx.fillStyle = "rgba(72, 84, 138, 0.28)";
  targetCtx.beginPath();
  targetCtx.moveTo(14, -396);
  targetCtx.lineTo(48, -360);
  targetCtx.lineTo(118, -264);
  targetCtx.lineTo(84, -140);
  targetCtx.lineTo(2, -190);
  targetCtx.closePath();
  targetCtx.fill();

  // Organic asymmetrical glacial snow crown (sunlit & shadowed halves)
  targetCtx.fillStyle = snowTint;
  targetCtx.beginPath();
  targetCtx.moveTo(-56, -342);
  targetCtx.lineTo(-18, -386);
  targetCtx.lineTo(14, -396);
  targetCtx.lineTo(48, -360);
  targetCtx.lineTo(94, -290);
  targetCtx.quadraticCurveTo(56, -304, 34, -270);
  targetCtx.quadraticCurveTo(10, -296, -14, -256);
  targetCtx.quadraticCurveTo(-48, -286, -84, -298);
  targetCtx.closePath();
  targetCtx.fill();

  // Subtle cool shadow on left side of summit snow cap so peak reads 3D behind foreground hero
  targetCtx.fillStyle = "rgba(42, 58, 108, 0.34)";
  targetCtx.beginPath();
  targetCtx.moveTo(-56, -342);
  targetCtx.lineTo(-18, -386);
  targetCtx.lineTo(14, -396);
  targetCtx.lineTo(6, -280);
  targetCtx.quadraticCurveTo(-36, -288, -84, -298);
  targetCtx.closePath();
  targetCtx.fill();

  // Strictly bounded glacial snow gullies (never jutting past perimeter)
  targetCtx.fillStyle = snowTint;
  for (const [gx, gy, gw, gh] of KAILASH_SNOW_GULLIES) {
    targetCtx.beginPath();
    targetCtx.moveTo(gx - gw, gy);
    targetCtx.quadraticCurveTo(gx, gy - gh, gx + gw, gy + 12);
    targetCtx.quadraticCurveTo(gx + 10, gy + 6, gx - gw, gy);
    targetCtx.closePath();
    targetCtx.fill();
  }

  // Subtle base Himalayan twilight mist band
  const mist = targetCtx.createLinearGradient(0, -140, 0, 40);
  mist.addColorStop(0, "rgba(180, 200, 238, 0)");
  mist.addColorStop(1, "rgba(148, 168, 224, 0.22)");
  targetCtx.fillStyle = mist;
  targetCtx.fillRect(-440, -140, 880, 185);

  targetCtx.restore(); // end silhouette clip

  // Crisp outer mountain outline
  targetCtx.strokeStyle = "#10142A";
  targetCtx.lineWidth = 3.2;
  traceKailashSilhouette(targetCtx);
  targetCtx.stroke();

  if (goldRim > 0) {
    targetCtx.strokeStyle = `rgba(176, 204, 250, ${(goldRim * 0.42).toFixed(3)})`;
    targetCtx.lineWidth = 2.2;
    targetCtx.beginPath();
    targetCtx.moveTo(-290, -118);
    targetCtx.lineTo(-175, -196);
    targetCtx.lineTo(-56, -342);
    targetCtx.lineTo(-18, -386);
    targetCtx.lineTo(14, -396);
    targetCtx.stroke();

    targetCtx.strokeStyle = `rgba(255, 226, 152, ${goldRim.toFixed(3)})`;
    targetCtx.lineWidth = 3.2;
    targetCtx.beginPath();
    targetCtx.moveTo(14, -396);
    targetCtx.lineTo(48, -360);
    targetCtx.lineTo(118, -264);
    targetCtx.lineTo(175, -195);
    targetCtx.lineTo(320, -104);
    targetCtx.stroke();
  }

  targetCtx.restore();
}

/**
 * Draw subtle celestial blueprint grid for `cosmic_explainer` / `observatory_cosmos` scenes.
 */
export function drawCosmicGrid(
  ctx,
  spacing = 60,
  color = "rgba(92, 182, 255, 0.08)",
  width = CANVAS_WIDTH,
  height = CANVAS_HEIGHT
) {
  const step = Math.max(24, Number(spacing) || 60);
  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.2;
  for (let x = 0; x <= width; x += step) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
    ctx.stroke();
  }
  for (let y = 0; y <= height; y += step) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
  }
  // Subtle observatory celestial rings centered in clear visual stage
  for (const r of [240, 400, 560]) {
    ctx.beginPath();
    ctx.arc(width * 0.5, 680, r, 0, Math.PI * 2);
    ctx.stroke();
  }
  ctx.restore();
}
