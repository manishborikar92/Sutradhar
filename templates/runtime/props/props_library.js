/**
 * Sutradhar v2 Declarative Mythic, Archival & Cosmic Props Library.
 * Consolidates Episode 4 (Kurma, Vasuki, Mandara, Ocean, Halahala, Kalash, Trishul),
 * Candidate B (Brass Clock, Hourglass Stand, Route Scroll, Magnifying Lens, Comparator,
 * Earth Globe, Wedding Mandap), V1 (Kalachakra), and Historical Monuments (Iron Pillar).
 */

import {
  CANVAS_HEIGHT,
  CANVAS_WIDTH,
  clamp,
  drawGlow,
  drawHalahalaOrb,
  easeOutBack,
  easeOutCubic,
  lerp,
  mixColor,
  parseHexColor,
  rgbaCss,
  safeR,
  smooth,
} from "../core/seek_runtime.js";

export { drawHalahalaOrb };

export function drawGroundedTrishul(ctx, x, floorY, h = 430) {
  ctx.save();
  ctx.translate(x, floorY);
  ctx.fillStyle = "rgba(8,6,14,0.45)";
  ctx.beginPath();
  ctx.ellipse(0, 2, 34, 10, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#5B647E";
  ctx.strokeStyle = "#1E2436";
  ctx.lineWidth = 2.4;
  ctx.beginPath();
  ctx.roundRect(-24, -20, 48, 20, 5);
  ctx.fill();
  ctx.stroke();

  ctx.strokeStyle = "#F6C453";
  ctx.lineWidth = 9;
  ctx.lineCap = "round";
  ctx.beginPath();
  ctx.moveTo(0, -18);
  ctx.lineTo(0, -h);
  ctx.stroke();

  ctx.fillStyle = "#D46A28";
  ctx.strokeStyle = "#3B1E12";
  ctx.lineWidth = 2.2;
  ctx.beginPath();
  ctx.moveTo(-22, -h + 74);
  ctx.lineTo(22, -h + 90);
  ctx.lineTo(22, -h + 74);
  ctx.lineTo(-22, -h + 90);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();

  ctx.strokeStyle = "#FFE07D";
  ctx.lineWidth = 7;
  ctx.beginPath();
  ctx.moveTo(0, -h + 10);
  ctx.lineTo(0, -h - 74);
  ctx.moveTo(0, -h + 18);
  ctx.quadraticCurveTo(-38, -h - 10, -28, -h - 58);
  ctx.moveTo(0, -h + 18);
  ctx.quadraticCurveTo(38, -h - 10, 28, -h - 58);
  ctx.stroke();
  ctx.restore();
}

export function drawKurmaAvatar(ctx, x, y, scale = 1.0) {
  ctx.save();
  ctx.translate(x, y);
  ctx.scale(scale, scale);

  ctx.fillStyle = "#B87A24";
  ctx.strokeStyle = "#2E1512";
  ctx.lineWidth = 2.6;
  for (const side of [-1, 1]) {
    ctx.beginPath();
    ctx.ellipse(side * 168, -6, 46, 14, side * -0.25, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  }

  const kg = ctx.createRadialGradient(0, -18, 12, 0, 0, 185);
  kg.addColorStop(0, "#FFE082");
  kg.addColorStop(0.55, "#B87A24");
  kg.addColorStop(1, "#3A2616");
  ctx.fillStyle = kg;
  ctx.strokeStyle = "#FFE594";
  ctx.lineWidth = 3.4;
  ctx.beginPath();
  ctx.ellipse(0, 0, 178, 66, 0, Math.PI, Math.PI * 2);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();

  ctx.strokeStyle = "rgba(42, 20, 8, 0.78)";
  ctx.lineWidth = 2.4;
  for (const [sx, sy, sr] of [[0, -34, 24], [-64, -26, 20], [64, -26, 20], [-122, -16, 15], [122, -16, 15]]) {
    ctx.beginPath();
    for (let h = 0; h < 6; h++) {
      const a = (h / 6) * Math.PI * 2;
      const px = sx + Math.cos(a) * sr * 1.25;
      const py = sy + Math.sin(a) * sr * 0.65;
      if (h === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }
    ctx.closePath();
    ctx.stroke();
  }

  ctx.fillStyle = "#D49B35";
  ctx.strokeStyle = "#2E1512";
  ctx.beginPath();
  ctx.ellipse(-188, -18, 28, 17, -0.2, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = "#FFF2B2";
  ctx.beginPath();
  ctx.arc(-198, -22, 3.6, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

export function drawMountMandara(ctx, x, y, erupt = 0, scale = 1.0) {
  ctx.save();
  ctx.translate(x, y);
  ctx.scale(scale, scale);

  const mg = ctx.createLinearGradient(-190, -470, 190, 130);
  mg.addColorStop(0, rgbaCss(mixColor(parseHexColor("#6C589C"), parseHexColor("#26584C"), erupt)));
  mg.addColorStop(0.65, rgbaCss(mixColor(parseHexColor("#3A3264"), parseHexColor("#163A34"), erupt)));
  mg.addColorStop(1, "#121830");
  ctx.fillStyle = mg;
  ctx.strokeStyle = rgbaCss(mixColor(parseHexColor("#E8B954"), parseHexColor("#42F59B"), erupt));
  ctx.lineWidth = 3.5;
  ctx.beginPath();
  ctx.moveTo(-210, 130);
  ctx.lineTo(-162, -90);
  ctx.lineTo(-132, -230);
  ctx.lineTo(-92, -335);
  ctx.lineTo(-34, -445);
  ctx.lineTo(18, -462);
  ctx.lineTo(68, -372);
  ctx.lineTo(118, -255);
  ctx.lineTo(156, -110);
  ctx.lineTo(212, 130);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = "rgba(12, 14, 34, 0.34)";
  ctx.beginPath();
  ctx.moveTo(-6, -456);
  ctx.lineTo(-34, -445);
  ctx.lineTo(-132, -230);
  ctx.lineTo(-210, 130);
  ctx.lineTo(-15, 130);
  ctx.closePath();
  ctx.fill();

  ctx.strokeStyle = "rgba(255, 255, 255, 0.32)";
  ctx.lineWidth = 4.0;
  ctx.beginPath();
  ctx.moveTo(32, -340);
  ctx.quadraticCurveTo(54, -180, 68, 45);
  ctx.stroke();
  ctx.restore();
}

export function drawVasukiSerpent(ctx, t, erupt, churnOsc, layer = "front") {
  const ink = "#180D14";
  const scaleTop = erupt > 0.4 ? "#1E926B" : "#256E5E";
  const scaleMid = erupt > 0.4 ? "#2FC28C" : "#34947D";
  const scaleHi = erupt > 0.4 ? "#8BFFCE" : "#8EEAD0";
  const bellyCream = erupt > 0.4 ? "#A8E8C0" : "#E8CA7A";

  function drawContinuousRibbon(pts, r0, r1) {
    const topSide = [];
    const botSide = [];
    let minY = 9999;
    let maxY = -9999;
    let maxR = 0;

    for (let i = 0; i < pts.length; i++) {
      const p = pts[i];
      const prev = pts[Math.max(0, i - 1)];
      const next = pts[Math.min(pts.length - 1, i + 1)];
      const dx = next[0] - prev[0];
      const dy = next[1] - prev[1];
      const len = Math.max(1, Math.hypot(dx, dy));
      let nx = -dy / len;
      let ny = dx / len;
      if (ny > 0) {
        nx = -nx;
        ny = -ny;
      }
      const r = lerp(r0, r1, i / (pts.length - 1));
      topSide.push([p[0] + nx * r, p[1] + ny * r]);
      botSide.push([p[0] - nx * r, p[1] - ny * r]);
      if (p[1] < minY) minY = p[1];
      if (p[1] > maxY) maxY = p[1];
      if (r > maxR) maxR = r;
    }

    ctx.beginPath();
    ctx.moveTo(topSide[0][0], topSide[0][1]);
    for (let i = 1; i < topSide.length; i++) ctx.lineTo(topSide[i][0], topSide[i][1]);
    for (let i = botSide.length - 1; i >= 0; i--) ctx.lineTo(botSide[i][0], botSide[i][1]);
    ctx.closePath();

    const bodyG = ctx.createLinearGradient(0, minY - maxR, 0, maxY + maxR);
    bodyG.addColorStop(0, scaleMid);
    bodyG.addColorStop(0.55, scaleTop);
    bodyG.addColorStop(1, "#12483A");
    ctx.fillStyle = bodyG;
    ctx.fill();

    ctx.save();
    ctx.clip();
    ctx.fillStyle = bellyCream;
    ctx.beginPath();
    for (let i = 0; i < pts.length; i++) {
      const mx = lerp(topSide[i][0], botSide[i][0], 0.64);
      const my = lerp(topSide[i][1], botSide[i][1], 0.64);
      if (i === 0) ctx.moveTo(mx, my);
      else ctx.lineTo(mx, my);
    }
    for (let i = botSide.length - 1; i >= 0; i--) ctx.lineTo(botSide[i][0], botSide[i][1]);
    ctx.closePath();
    ctx.fill();

    ctx.strokeStyle = "rgba(18, 42, 34, 0.44)";
    ctx.lineWidth = 1.8;
    for (let i = 1; i < pts.length - 1; i++) {
      const p = pts[i];
      const r = lerp(r0, r1, i / (pts.length - 1));
      ctx.beginPath();
      ctx.moveTo(p[0] - 10, p[1] - r);
      ctx.lineTo(p[0] + 10, p[1] + r * 0.35);
      ctx.moveTo(p[0] + 10, p[1] - r);
      ctx.lineTo(p[0] - 10, p[1] + r * 0.35);
      ctx.stroke();
      ctx.fillStyle = scaleHi;
      ctx.beginPath();
      ctx.ellipse(p[0], p[1] - r * 0.55, 5, 2.5, 0, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();

    ctx.strokeStyle = ink;
    ctx.lineWidth = 3.0;
    ctx.stroke();
  }

  function sampleQuad(x0, y0, cx, cy, x1, y1, steps = 22) {
    const out = [];
    for (let i = 0; i <= steps; i++) {
      const s = i / steps;
      const is = 1 - s;
      out.push([is * is * x0 + 2 * is * s * cx + s * s * x1, is * is * y0 + 2 * is * s * cy + s * s * y1]);
    }
    return out;
  }

  const coilSpec = [
    { ry: -260, rw: 148 },
    { ry: -160, rw: 170 },
    { ry: -60, rw: 194 },
  ];

  if (layer === "back" || layer === "both") {
    for (const { ry, rw } of coilSpec) {
      drawContinuousRibbon(sampleQuad(-rw, ry - 4, 0, ry - 42, rw, ry - 4, 18), 18, 18);
    }
    if (layer === "back") return;
  }

  for (const ring of [0, 2]) {
    const { ry, rw } = coilSpec[ring];
    drawContinuousRibbon(sampleQuad(-rw, ry - 6, 0, ry + 36, rw, ry - 6, 20), 20, 20);
  }

  const tailIn = sampleQuad(495, -132 + churnOsc * 0.5, 420, -92, 335, -96 - churnOsc * 0.45, 16);
  const rightSpan = sampleQuad(335, -96 - churnOsc * 0.45, 224, -102, 168, -162, 16);
  const frontCenter = sampleQuad(168, -162, 0, -112, -168, -162, 22);
  const leftSpan = sampleQuad(-168, -162, -220, -100, -325, -98 + churnOsc * 0.45, 16);
  const hoodUp = sampleQuad(-325, -98 + churnOsc * 0.45, -432, -102, -412, -276 - churnOsc * 0.4, 16);
  drawContinuousRibbon(
    [...tailIn, ...rightSpan.slice(1), ...frontCenter.slice(1), ...leftSpan.slice(1), ...hoodUp.slice(1)],
    7,
    25
  );

  ctx.save();
  ctx.translate(-412, -276 - churnOsc * 0.4);
  for (let sm = 0; sm < 5; sm++) {
    const sx = -45 - sm * 16;
    const sy = -45 + Math.sin(t * 5 + sm) * 16;
    drawGlow(ctx, sx, sy, 6, 56, erupt > 0.35 ? "rgba(42, 245, 162, 0.50)" : "rgba(255, 126, 48, 0.44)");
  }
  for (let h = -2; h <= 2; h++) {
    ctx.save();
    ctx.rotate(h * 0.25 - 0.16 + Math.sin(t * 3.5 + h) * 0.05);
    const hy = -72 + Math.abs(h) * 15;
    const hx = h * 20;
    const hg = ctx.createLinearGradient(hx - 26, hy - 38, hx + 26, hy + 20);
    hg.addColorStop(0, scaleHi);
    hg.addColorStop(0.45, scaleTop);
    hg.addColorStop(1, "#0B2C25");
    ctx.fillStyle = hg;
    ctx.strokeStyle = ink;
    ctx.lineWidth = 2.6;
    ctx.beginPath();
    ctx.moveTo(0, 14);
    ctx.bezierCurveTo(hx - 36, hy + 12, hx - 34, hy - 34, hx, hy - 48);
    ctx.bezierCurveTo(hx + 34, hy - 34, hx + 36, hy + 12, 0, 14);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    ctx.strokeStyle = bellyCream;
    ctx.lineWidth = 2.2;
    for (const gy of [-18, -8, 2]) {
      ctx.beginPath();
      ctx.moveTo(hx - 13, hy + gy);
      ctx.quadraticCurveTo(hx, hy + gy + 5, hx + 13, hy + gy);
      ctx.stroke();
    }

    ctx.fillStyle = "#FFD452";
    ctx.beginPath();
    ctx.arc(hx, hy - 38, 3.6, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = scaleTop;
    ctx.strokeStyle = ink;
    ctx.beginPath();
    ctx.ellipse(hx - 5, hy - 26, 16, 11, -0.35, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = erupt > 0.4 ? "#5EF7BA" : "#FF9F1C";
    ctx.beginPath();
    ctx.arc(hx - 9, hy - 30, 3.2, 0, Math.PI * 2);
    ctx.fill();

    if (h === 0 || Math.abs(h) === 1) {
      ctx.fillStyle = "#FFFFFF";
      ctx.beginPath();
      ctx.moveTo(hx - 15, hy - 22);
      ctx.lineTo(hx - 19, hy - 14);
      ctx.lineTo(hx - 11, hy - 18);
      ctx.fill();
      ctx.strokeStyle = "#FF3B4E";
      ctx.lineWidth = 2.2;
      ctx.beginPath();
      ctx.moveTo(hx - 18, hy - 22);
      ctx.lineTo(hx - 30, hy - 18);
      ctx.lineTo(hx - 36, hy - 23);
      ctx.moveTo(hx - 30, hy - 18);
      ctx.lineTo(hx - 37, hy - 13);
      ctx.stroke();
    }
    ctx.restore();
  }
  ctx.restore();
}

export function drawOceanWaves(
  ctx,
  t,
  erupt = 0,
  baseStartY = 1042,
  drawMidBackHook = null,
  width = CANVAS_WIDTH,
  height = CANVAS_HEIGHT,
  waveColorsOverride = null
) {
  const waveCols =
    Array.isArray(waveColorsOverride) && waveColorsOverride.length >= 4
      ? waveColorsOverride
      : erupt > 0.5
        ? ["#124B44", "#0E3D3A", "#092B34", "#061624"]
        : ["#265E94", "#1B4678", "#112D54", "#081430"];
  for (let w = 0; w < 4; w++) {
    if (w === 1 && typeof drawMidBackHook === "function") {
      drawMidBackHook();
    }
    const baseY = baseStartY + w * 46;
    ctx.fillStyle = waveCols[w];
    ctx.beginPath();
    ctx.moveTo(-100, height + 100);
    for (let x = -100; x <= width + 100; x += 24) {
      const wy = baseY + Math.sin(x * 0.016 + t * (2.6 + w * 0.7) + w * 1.6) * (20 + w * 6);
      ctx.lineTo(x, wy);
    }
    ctx.lineTo(width + 100, height + 100);
    ctx.closePath();
    ctx.fill();
    ctx.strokeStyle = erupt > 0.4 ? "rgba(110, 255, 198, 0.46)" : "rgba(220, 244, 255, 0.40)";
    ctx.lineWidth = 3.2;
    ctx.stroke();
  }
}

export function drawAmritaKalash(ctx, x, floorY, scale = 1.0) {
  ctx.save();
  ctx.translate(x, floorY);
  ctx.scale(scale, scale);

  ctx.fillStyle = "rgba(8, 5, 16, 0.42)";
  ctx.beginPath();
  ctx.ellipse(0, 2, 68, 12, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#483452";
  ctx.strokeStyle = "#F6C453";
  ctx.lineWidth = 2.8;
  ctx.beginPath();
  ctx.roundRect(-50, -56, 100, 56, 8);
  ctx.fill();
  ctx.stroke();
  ctx.beginPath();
  ctx.roundRect(-58, -68, 116, 14, 5);
  ctx.fill();
  ctx.stroke();

  ctx.translate(0, -104);
  drawGlow(ctx, 0, -14, 6, 125, "rgba(255, 226, 120, 0.78)");
  const kg = ctx.createLinearGradient(-42, -62, 42, 34);
  kg.addColorStop(0, "#FFF6B8");
  kg.addColorStop(0.5, "#F6C453");
  kg.addColorStop(1, "#9E5E12");
  ctx.fillStyle = kg;
  ctx.strokeStyle = "#482210";
  ctx.lineWidth = 2.8;
  ctx.beginPath();
  ctx.ellipse(0, 0, 38, 32, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  ctx.beginPath();
  ctx.roundRect(-22, -44, 44, 20, 6);
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = "#2E8B57";
  for (const lx of [-18, 0, 18]) {
    ctx.beginPath();
    ctx.ellipse(lx, -52, 13, 5.5, lx * 0.03, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.fillStyle = "#FFF0A8";
  ctx.beginPath();
  ctx.arc(0, -56, 11, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

export function drawBrassClock(ctx, cx, cy, R, angSlow, angFast, smearAmt = 0.3, handCol = "#C83728") {
  ctx.save();
  ctx.translate(cx, cy);
  if (smearAmt > 0.05) {
    for (let k = 1; k <= 5; k++) {
      const a = angFast - Math.PI / 2 - k * 0.14 * smearAmt;
      ctx.strokeStyle = `rgba(255, 214, 98, ${(0.28 - k * 0.045).toFixed(3)})`;
      ctx.lineWidth = 7 - k;
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.lineTo(Math.cos(a) * R * 0.78, Math.sin(a) * R * 0.78);
      ctx.stroke();
    }
  }

  ctx.fillStyle = "#D49B35";
  ctx.beginPath();
  ctx.arc(0, 0, safeR(R), 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#FFF7E2";
  ctx.beginPath();
  ctx.arc(0, 0, safeR(R * 0.88), 0, Math.PI * 2);
  ctx.fill();

  for (let i = 0; i < 12; i++) {
    const a = (i / 12) * Math.PI * 2;
    ctx.strokeStyle = "#3B2610";
    ctx.lineWidth = i % 3 === 0 ? 5 : 2.5;
    ctx.beginPath();
    ctx.moveTo(Math.cos(a) * R * 0.72, Math.sin(a) * R * 0.72);
    ctx.lineTo(Math.cos(a) * R * 0.83, Math.sin(a) * R * 0.83);
    ctx.stroke();
  }

  ctx.strokeStyle = "#2A180D";
  ctx.lineWidth = 8;
  ctx.lineCap = "round";
  ctx.beginPath();
  ctx.moveTo(0, 0);
  ctx.lineTo(Math.cos(angSlow - Math.PI / 2) * R * 0.48, Math.sin(angSlow - Math.PI / 2) * R * 0.48);
  ctx.stroke();

  ctx.strokeStyle = handCol;
  ctx.lineWidth = 5;
  ctx.beginPath();
  ctx.moveTo(0, 0);
  ctx.lineTo(Math.cos(angFast - Math.PI / 2) * R * 0.76, Math.sin(angFast - Math.PI / 2) * R * 0.76);
  ctx.stroke();

  ctx.fillStyle = "#B87A1E";
  ctx.beginPath();
  ctx.arc(0, 0, 11, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

export function drawGroundedHourglassStand(ctx, x, floorY, t = 0) {
  ctx.save();
  ctx.translate(x, floorY);
  ctx.fillStyle = "rgba(6, 5, 14, 0.48)";
  ctx.beginPath();
  ctx.ellipse(0, 2, 52, 13, 0, 0, Math.PI * 2);
  ctx.fill();

  const sg = ctx.createLinearGradient(-24, 0, 24, 0);
  sg.addColorStop(0, "#B87E22");
  sg.addColorStop(0.5, "#FFE07D");
  sg.addColorStop(1, "#8A5614");
  ctx.fillStyle = sg;
  ctx.strokeStyle = "#3A1F0B";
  ctx.lineWidth = 2.4;
  ctx.beginPath();
  ctx.roundRect(-42, -16, 84, 16, 4);
  ctx.roundRect(-28, -32, 56, 16, 4);
  ctx.roundRect(-11, -198, 22, 166, 4);
  ctx.roundRect(-44, -214, 88, 16, 6);
  ctx.fill();
  ctx.stroke();

  ctx.save();
  ctx.translate(0, -280);
  ctx.fillStyle = "#D49B35";
  ctx.fillRect(-42, -68, 84, 12);
  ctx.fillRect(-42, 54, 84, 12);
  ctx.fillStyle = "rgba(180, 232, 255, 0.36)";
  ctx.strokeStyle = "#F6C453";
  ctx.lineWidth = 2.8;
  ctx.beginPath();
  ctx.moveTo(-32, -56);
  ctx.lineTo(32, -56);
  ctx.lineTo(4, -2);
  ctx.lineTo(32, 54);
  ctx.lineTo(-32, 54);
  ctx.lineTo(-4, -2);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = "#FFD365";
  const sandP = (t * 0.25) % 1;
  ctx.beginPath();
  ctx.moveTo(-22, -40 + sandP * 14);
  ctx.lineTo(22, -40 + sandP * 14);
  ctx.lineTo(2, -4);
  ctx.closePath();
  ctx.fill();
  ctx.beginPath();
  ctx.moveTo(0, -4);
  ctx.lineTo(0, 52);
  ctx.strokeStyle = "#FFD365";
  ctx.lineWidth = 2.5;
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(-26, 54);
  ctx.quadraticCurveTo(0, 34 - sandP * 10, 26, 54);
  ctx.closePath();
  ctx.fill();
  ctx.restore();
  ctx.restore();
}

export function drawVectorEarthGlobe(ctx, cx, cy, R, rotPhase = 0, glowCol = "rgba(86, 186, 255, 0.36)") {
  ctx.save();
  drawGlow(ctx, cx, cy, R * 0.7, R * 1.45, glowCol);
  ctx.beginPath();
  ctx.arc(cx, cy, safeR(R), 0, Math.PI * 2);
  const ocean = ctx.createRadialGradient(cx - R * 0.3, cy - R * 0.3, R * 0.1, cx, cy, safeR(R));
  ocean.addColorStop(0, "#4CB6FF");
  ocean.addColorStop(0.65, "#1E6AB5");
  ocean.addColorStop(1, "#0D2A58");
  ctx.fillStyle = ocean;
  ctx.fill();

  ctx.save();
  ctx.clip();
  ctx.fillStyle = "#5CC26F";
  const shift = (rotPhase * R * 1.4) % (R * 3);
  for (let k = -1; k <= 1; k++) {
    const lx = cx - shift + k * R * 2.2;
    ctx.beginPath();
    ctx.ellipse(lx - R * 0.2, cy - R * 0.18, R * 0.42, R * 0.28, 0.3, 0, Math.PI * 2);
    ctx.ellipse(lx + R * 0.35, cy + R * 0.25, R * 0.34, R * 0.22, -0.2, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();

  ctx.strokeStyle = "rgba(255, 255, 255, 0.45)";
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.arc(cx, cy, safeR(R), 0, Math.PI * 2);
  ctx.stroke();
  ctx.restore();
}

export function drawMeruRouteScroll(ctx, localT = 1.5, fromLabel = "DWARAKA", toLabel = "BRAHMALOKA", width = CANVAS_WIDTH, height = CANVAS_HEIGHT) {
  const unfurl = easeOutCubic(localT / 0.85);
  const desk = ctx.createLinearGradient(0, 0, 0, height);
  desk.addColorStop(0, "#1E1418");
  desk.addColorStop(0.5, "#331D1A");
  desk.addColorStop(1, "#180F12");
  ctx.fillStyle = desk;
  ctx.fillRect(0, 0, width, height);
  ctx.strokeStyle = "rgba(246, 196, 83, 0.14)";
  ctx.lineWidth = 2;
  ctx.strokeRect(48, 48, width - 96, height - 96);

  const sw = lerp(140, 800, unfurl);
  const sx = 540 - sw * 0.5;
  const sy = 445;
  const sh = 670;

  ctx.fillStyle = "rgba(0,0,0,0.45)";
  ctx.beginPath();
  ctx.roundRect(sx + 12, sy + 16, sw, sh, 12);
  ctx.fill();

  ctx.fillStyle = "#F5E2B8";
  ctx.strokeStyle = "#B87E2A";
  ctx.lineWidth = 5;
  ctx.beginPath();
  ctx.roundRect(sx, sy, sw, sh, 12);
  ctx.fill();
  ctx.stroke();

  if (sw > 260) {
    ctx.strokeStyle = "rgba(152, 102, 34, 0.45)";
    ctx.lineWidth = 2;
    ctx.strokeRect(sx + 18, sy + 18, sw - 36, sh - 36);
  }

  for (const rx of [sx - 12, sx + sw - 12]) {
    ctx.fillStyle = "#7D481A";
    ctx.beginPath();
    ctx.roundRect(rx, sy - 22, 24, sh + 44, 12);
    ctx.fill();
    ctx.fillStyle = "#F6C453";
    ctx.beginPath();
    ctx.arc(rx + 12, sy - 22, 16, 0, Math.PI * 2);
    ctx.arc(rx + 12, sy + sh + 22, 16, 0, Math.PI * 2);
    ctx.fill();
  }

  if (unfurl > 0.55) {
    ctx.save();
    ctx.globalAlpha = clamp((unfurl - 0.55) / 0.35, 0, 1);
    ctx.fillStyle = "#C68B45";
    ctx.beginPath();
    ctx.moveTo(215, 1045);
    ctx.lineTo(355, 830);
    ctx.lineTo(485, 955);
    ctx.lineTo(630, 795);
    ctx.lineTo(790, 1045);
    ctx.closePath();
    ctx.fill();

    ctx.strokeStyle = "#3E98E8";
    ctx.lineWidth = 10;
    ctx.beginPath();
    ctx.moveTo(225, 1070);
    ctx.bezierCurveTo(370, 965, 620, 845, 815, 550);
    ctx.stroke();

    const flightP = smooth((localT - 0.8) / 3.2);
    ctx.strokeStyle = "#C42E2E";
    ctx.lineWidth = 4.5;
    ctx.setLineDash([12, 10]);
    ctx.beginPath();
    ctx.moveTo(240, 1025);
    ctx.quadraticCurveTo(465, 735, 800, 545);
    ctx.stroke();
    ctx.setLineDash([]);

    const mx = (1 - flightP) * (1 - flightP) * 240 + 2 * (1 - flightP) * flightP * 465 + flightP * flightP * 800;
    const my = (1 - flightP) * (1 - flightP) * 1025 + 2 * (1 - flightP) * flightP * 735 + flightP * flightP * 545;
    drawGlow(ctx, 800, 545, 8, 56, "rgba(255, 206, 86, 0.92)");
    ctx.fillStyle = "#192044";
    ctx.strokeStyle = "#F6C453";
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.arc(mx, my, 32, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = "#FFF4D4";
    ctx.font = '800 22px "Cinzel", serif';
    ctx.textAlign = "center";
    ctx.fillText("★", mx, my + 8);

    for (const tag of [{ x: 270, y: 1068, txt: fromLabel }, { x: 750, y: 500, txt: toLabel }]) {
      ctx.fillStyle = "#2E190C";
      ctx.beginPath();
      ctx.roundRect(tag.x - 95, tag.y - 20, 190, 36, 18);
      ctx.fill();
      ctx.fillStyle = "#FFE088";
      ctx.font = '800 20px "Cinzel", serif';
      ctx.fillText(tag.txt, tag.x, tag.y + 5);
    }
    ctx.restore();
  }
}

export function drawMagnifyingSectorLens(ctx, x, y, lR = 192, sectors = 27, progress = 1.0, pop = 1.0) {
  if (pop <= 0.02) return;
  const lScale = easeOutBack(clamp(pop, 0, 1));
  ctx.save();
  ctx.translate(x, y);
  ctx.scale(lScale, lScale);

  ctx.strokeStyle = "#8C5418";
  ctx.lineWidth = 24;
  ctx.lineCap = "round";
  ctx.beginPath();
  ctx.moveTo(lR * 0.72, lR * 0.72);
  ctx.lineTo(lR * 1.12, lR * 1.12);
  ctx.stroke();

  ctx.fillStyle = "#101938";
  ctx.beginPath();
  ctx.arc(0, 0, lR, 0, Math.PI * 2);
  ctx.fill();

  const litN = Math.floor(clamp(progress, 0, 1) * sectors);
  for (let i = 0; i < sectors; i++) {
    const a0 = (i / sectors) * Math.PI * 2 - Math.PI / 2;
    const a1 = a0 + (Math.PI * 2) / sectors - 0.04;
    ctx.fillStyle = i < litN ? "#FFD454" : "rgba(255, 224, 150, 0.16)";
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.arc(0, 0, lR * 0.86, a0, a1);
    ctx.closePath();
    ctx.fill();
  }
  ctx.fillStyle = "#101938";
  ctx.beginPath();
  ctx.arc(0, 0, lR * 0.44, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#FFD86B";
  ctx.font = '800 54px "Cinzel", serif';
  ctx.textAlign = "center";
  ctx.fillText(String(litN), 0, 18);

  ctx.strokeStyle = "#F6C453";
  ctx.lineWidth = 14;
  ctx.beginPath();
  ctx.arc(0, 0, lR, 0, Math.PI * 2);
  ctx.stroke();
  ctx.restore();
}

export function drawSpacetimeComparator(ctx, t, leftTitle = "RELATIVITY", rightTitle = "SURYA SIDDHANTA") {
  const cards = [
    { x: 90, title: leftTitle, sub: "CURVED SPACETIME" },
    { x: 560, title: rightTitle, sub: "VEDIC ORBITS" },
  ];
  for (let i = 0; i < 2; i++) {
    const cd = cards[i];
    ctx.fillStyle = "rgba(18, 28, 58, 0.92)";
    ctx.strokeStyle = i === 0 ? "#59D1FF" : "#F6C453";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.roundRect(cd.x, 455, 430, 560, 22);
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = i === 0 ? "#8EE4FF" : "#FFD978";
    ctx.font = '800 26px "Cinzel", serif';
    ctx.textAlign = "center";
    ctx.fillText(cd.title, cd.x + 215, 514);
    ctx.fillStyle = "rgba(240, 245, 255, 0.78)";
    ctx.font = '700 20px "Inter", sans-serif';
    ctx.fillText(cd.sub, cd.x + 215, 548);
  }

  ctx.save();
  ctx.translate(305, 770);
  for (let r = 0; r < 5; r++) {
    const rx = 50 + r * 30;
    ctx.strokeStyle = "rgba(89, 209, 255, 0.56)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.ellipse(0, r * 24, rx, 22, 0, 0, Math.PI * 2);
    ctx.stroke();
  }
  drawGlow(ctx, 0, -10, 8, 52, "rgba(255, 222, 118, 0.96)");
  ctx.strokeStyle = "#FFE17D";
  ctx.lineWidth = 2.8;
  for (const side of [-1, 1]) {
    ctx.beginPath();
    ctx.moveTo(-165, -24 + side * 52);
    ctx.quadraticCurveTo(0, -24 + side * 10, 165, -24 + side * 58);
    ctx.stroke();
  }
  ctx.restore();

  ctx.save();
  ctx.translate(775, 785);
  for (let k = 0; k < 3; k++) {
    ctx.save();
    ctx.rotate(t * (k % 2 === 0 ? 0.5 : -0.7) + k * 0.8);
    ctx.strokeStyle = "#F6C453";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.ellipse(0, 0, 128 - k * 14, 50, 0, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  }
  ctx.fillStyle = "#7CE4FF";
  ctx.beginPath();
  ctx.arc(0, 0, 14, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();

  ctx.fillStyle = "#F6C453";
  ctx.beginPath();
  ctx.arc(540, 735, 28, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#0D152E";
  ctx.font = '800 32px "Inter", sans-serif';
  ctx.textAlign = "center";
  ctx.fillText("=", 540, 746);
}

export function drawWeddingMandap(ctx, floorY = 1230, t = 0) {
  for (const mx of [175, 905]) {
    ctx.fillStyle = "rgba(8, 6, 14, 0.38)";
    ctx.beginPath();
    ctx.ellipse(mx, floorY + 4, 48, 12, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#D49B35";
    ctx.strokeStyle = "#482210";
    ctx.lineWidth = 2.6;
    ctx.fillRect(mx - 18, 345, 36, floorY - 370);
    ctx.strokeRect(mx - 18, 345, 36, floorY - 370);
    ctx.fillRect(mx - 34, floorY - 25, 68, 28);
    ctx.strokeRect(mx - 34, floorY - 25, 68, 28);
  }

  ctx.fillStyle = "#B87A1E";
  ctx.strokeStyle = "#FFE088";
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.roundRect(145, 315, 790, 42, 12);
  ctx.fill();
  ctx.stroke();

  for (let g = 0; g < 16; g++) {
    const f = g / 15;
    const gx = lerp(175, 905, f);
    const gy = 365 + Math.sin(f * Math.PI) * 145 + Math.sin(t * 2 + g) * 5;
    ctx.fillStyle = g % 2 === 0 ? "#FF9F1C" : "#FFE066";
    ctx.beginPath();
    ctx.arc(gx, gy, 18, 0, Math.PI * 2);
    ctx.fill();
  }

  // Grounded Agni Wedding Kalash Urn
  ctx.save();
  ctx.translate(540, floorY + 6);
  ctx.fillStyle = "rgba(8, 6, 14, 0.42)";
  ctx.beginPath();
  ctx.ellipse(0, 2, 34, 8, 0, 0, Math.PI * 2);
  ctx.fill();
  drawGlow(ctx, 0, -34, 4, 40, "rgba(255, 200, 96, 0.65)");
  ctx.fillStyle = "#D48828";
  ctx.strokeStyle = "#3B1E12";
  ctx.lineWidth = 2.4;
  ctx.beginPath();
  ctx.ellipse(0, -14, 22, 14, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = "#FFDF70";
  ctx.beginPath();
  ctx.ellipse(0, -34, 7, 13, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

export function drawKalachakra(ctx, cx, cy, r, t, speed = 1, opacity = 1, tint = parseHexColor("#FFD480")) {
  if (opacity <= 0.01) return;
  ctx.save();
  ctx.translate(cx, cy);
  ctx.globalCompositeOperation = "lighter";

  const rg = ctx.createRadialGradient(0, 0, r * 0.4, 0, 0, r * 1.45);
  rg.addColorStop(0, rgbaCss(tint, 0.14 * opacity));
  rg.addColorStop(0.7, rgbaCss(tint, 0.05 * opacity));
  rg.addColorStop(1, rgbaCss(tint, 0));
  ctx.fillStyle = rg;
  ctx.beginPath();
  ctx.arc(0, 0, r * 1.45, 0, Math.PI * 2);
  ctx.fill();

  for (const [rf, lw, al] of [[1.0, 2.2, 0.42], [0.87, 1.4, 0.28], [0.71, 2.0, 0.36], [0.46, 1.5, 0.32]]) {
    ctx.strokeStyle = rgbaCss(tint, al * opacity);
    ctx.lineWidth = lw;
    ctx.beginPath();
    ctx.arc(0, 0, r * rf, 0, Math.PI * 2);
    ctx.stroke();
  }

  ctx.save();
  ctx.rotate(t * 0.14 * speed);
  ctx.strokeStyle = rgbaCss(tint, 0.34 * opacity);
  ctx.lineWidth = 1.6;
  ctx.setLineDash([10, 14]);
  ctx.beginPath();
  ctx.arc(0, 0, r * 0.935, 0, Math.PI * 2);
  ctx.stroke();
  ctx.setLineDash([]);

  for (let i = 0; i < 12; i++) {
    const ang = (i * Math.PI) / 6;
    ctx.strokeStyle = rgbaCss(tint, 0.24 * opacity);
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.moveTo(Math.cos(ang) * r * 0.46, Math.sin(ang) * r * 0.46);
    ctx.lineTo(Math.cos(ang) * r * 0.87, Math.sin(ang) * r * 0.87);
    ctx.stroke();
    ctx.fillStyle = rgbaCss(tint, 0.72 * opacity);
    ctx.beginPath();
    ctx.arc(Math.cos(ang) * r, Math.sin(ang) * r, i % 3 === 0 ? 5.5 : 3.0, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();

  ctx.save();
  ctx.rotate(-t * 0.24 * speed);
  ctx.strokeStyle = rgbaCss(tint, 0.36 * opacity);
  ctx.lineWidth = 1.5;
  for (let i = 0; i < 8; i++) {
    ctx.rotate(Math.PI / 4);
    ctx.beginPath();
    ctx.moveTo(0, -r * 0.16);
    ctx.quadraticCurveTo(r * 0.18, -r * 0.32, 0, -r * 0.45);
    ctx.quadraticCurveTo(-r * 0.18, -r * 0.32, 0, -r * 0.16);
    ctx.stroke();
  }
  ctx.restore();

  ctx.save();
  ctx.rotate(t * 0.85 * speed);
  ctx.strokeStyle = rgbaCss(parseHexColor("#FFF4D6"), 0.82 * opacity);
  ctx.lineWidth = 3;
  ctx.lineCap = "round";
  ctx.beginPath();
  ctx.moveTo(0, 0);
  ctx.lineTo(0, -r * 0.80);
  ctx.stroke();
  ctx.restore();

  ctx.fillStyle = rgbaCss(parseHexColor("#FFF4DA"), 0.88 * opacity);
  ctx.beginPath();
  ctx.arc(0, 0, 7.5, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

export function drawIronPillar(ctx, x, floorY, height = 560) {
  ctx.save();
  ctx.translate(x, floorY);
  ctx.fillStyle = "rgba(8, 6, 14, 0.48)";
  ctx.beginPath();
  ctx.ellipse(0, 2, 92, 16, 0, 0, Math.PI * 2);
  ctx.fill();

  // Sandstone plinth
  ctx.fillStyle = "#7D5438";
  ctx.strokeStyle = "#2A160E";
  ctx.lineWidth = 2.6;
  ctx.beginPath();
  ctx.roundRect(-74, -36, 148, 36, 6);
  ctx.roundRect(-58, -62, 116, 26, 6);
  ctx.fill();
  ctx.stroke();

  // Tapered rustless forge-welded iron shaft
  const ig = ctx.createLinearGradient(-28, 0, 28, 0);
  ig.addColorStop(0, "#242834");
  ig.addColorStop(0.45, "#5A6274");
  ig.addColorStop(1, "#181C26");
  ctx.fillStyle = ig;
  ctx.strokeStyle = "#0E1018";
  ctx.beginPath();
  ctx.moveTo(-28, -62);
  ctx.lineTo(-19, -height);
  ctx.lineTo(19, -height);
  ctx.lineTo(28, -62);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();

  // Bell capital & chakra base
  ctx.fillStyle = "#D49B35";
  ctx.beginPath();
  ctx.roundRect(-30, -height - 34, 60, 34, 8);
  ctx.fill();
  ctx.stroke();
  ctx.beginPath();
  ctx.ellipse(0, -height - 46, 22, 12, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  ctx.restore();
}

const KALACHAKRA_DEFAULT_TINT = parseHexColor("#FFD480");
const SHANI_MANDALA_TINT = parseHexColor("#7EB8FF");

export function drawShaniDrishtiMandala(
  ctx,
  cx,
  cy,
  r = 220,
  t = 0,
  speed = 1.0,
  opacity = 0.92,
  tint = SHANI_MANDALA_TINT
) {
  if (opacity <= 0.01) return;
  drawKalachakra(ctx, cx, cy, r, t, speed, opacity, tint);

  // Overlay Shani's 3rd, 7th, and 10th house Vedic Drishti karmic aspect rays + Saturn ring hub
  ctx.save();
  ctx.translate(cx, cy);
  ctx.globalCompositeOperation = "lighter";
  for (const houseOffset of [2, 6, 9]) {
    const ang = (houseOffset / 12) * Math.PI * 2 + t * 0.14 * speed - Math.PI * 0.5;
    ctx.strokeStyle = `rgba(255, 118, 86, ${(0.55 * opacity).toFixed(3)})`;
    ctx.lineWidth = 2.6;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(Math.cos(ang) * r * 0.94, Math.sin(ang) * r * 0.94);
    ctx.stroke();

    ctx.fillStyle = `rgba(255, 198, 102, ${(0.82 * opacity).toFixed(3)})`;
    ctx.beginPath();
    ctx.arc(Math.cos(ang) * r * 0.94, Math.sin(ang) * r * 0.94, 7.5, 0, Math.PI * 2);
    ctx.fill();
  }

  ctx.strokeStyle = `rgba(180, 218, 255, ${(0.85 * opacity).toFixed(3)})`;
  ctx.lineWidth = 2.8;
  ctx.beginPath();
  ctx.ellipse(0, 0, r * 0.24, r * 0.085, -0.32, 0, Math.PI * 2);
  ctx.stroke();
  ctx.restore();
}

export function drawSamudraManthanEnsemble(ctx, p = {}, t = 0) {
  const px = Number(p.x ?? 540);
  const py = Number(p.y ?? 980);
  const sc = Number(p.scale ?? 1.0);
  const erupt = Number(p.erupt ?? 0.45);
  const churnOsc = p.churnOsc ?? Math.sin(t * 3.8) * 18;
  const shiftX = px + churnOsc * 0.25;

  ctx.save();
  ctx.translate(shiftX, py);
  if (sc !== 1.0) ctx.scale(sc, sc);
  drawVasukiSerpent(ctx, t, erupt, churnOsc, "back");
  drawMountMandara(ctx, 0, 0, erupt, 1.0);
  drawVasukiSerpent(ctx, t, erupt, churnOsc, "front");
  ctx.restore();

  const kurmaY = Number(p.kurmaY ?? py + 132 * sc);
  const waveStartY = Number(p.baseStartY ?? py + 62 * sc);
  drawOceanWaves(
    ctx,
    t,
    erupt,
    waveStartY,
    () => drawKurmaAvatar(ctx, shiftX, kurmaY, sc),
    CANVAS_WIDTH,
    CANVAS_HEIGHT,
    p.waveColors ?? null
  );

  drawHalahalaOrb(
    ctx,
    px,
    py - 240 * sc,
    Number(p.orbRadius ?? 42) * sc,
    t,
    clamp(0.45 + erupt * 0.55, 0.45, 1.0),
    p.halahalaColor ?? "emerald"
  );
}

const drawKalachakraProp = (c, p, t) =>
  drawKalachakra(
    c,
    p.x ?? 540,
    p.y ?? 820,
    p.r ?? 220,
    p.t ?? t,
    p.speed ?? 1.0,
    p.opacity ?? 0.9,
    p.tint ? parseHexColor(p.tint) : KALACHAKRA_DEFAULT_TINT
  );

const drawIronPillarProp = (c, p) => drawIronPillar(c, p.x ?? 540, p.y ?? 1142, p.height ?? 560);

/**
 * Shared declarative prop dispatch table used by both video scenes and cover thumbnails.
 * Covers all 17 canonical IDs in assets/manifest.yaml plus runtime scene aliases.
 */
export const PROP_DRAWERS = {
  trishul: (c, p) => {
    const sc = Number(p.scale ?? 1.0);
    if (sc === 1.0) {
      drawGroundedTrishul(c, p.x ?? 180, p.y ?? 1445, Number(p.h ?? 430));
      return;
    }
    c.save();
    c.translate(p.x ?? 195, p.y ?? 1585);
    c.scale(sc, sc);
    drawGroundedTrishul(c, 0, 0, Number(p.h ?? 452));
    c.restore();
  },
  kurma_avatar: (c, p) => drawKurmaAvatar(c, p.x ?? 540, p.y ?? 1112, p.scale ?? 1.0),
  mount_mandara: (c, p) => drawMountMandara(c, p.x ?? 540, p.y ?? 980, p.erupt ?? 0.1, p.scale ?? 1.0),
  vasuki_serpent: (c, p, t) => {
    const sc = Number(p.scale ?? 1.0);
    c.save();
    c.translate(p.x ?? 540, p.y ?? 980);
    if (sc !== 1.0) c.scale(sc, sc);
    drawVasukiSerpent(c, t, p.erupt ?? 0.25, p.churnOsc ?? Math.sin(t * 2.2), p.layer ?? "both");
    c.restore();
  },
  cosmic_ocean: (c, p, t) =>
    drawOceanWaves(
      c,
      t,
      p.erupt ?? 0.2,
      p.baseStartY ?? 1042,
      p.drawMidBackHook ?? null,
      CANVAS_WIDTH,
      CANVAS_HEIGHT,
      p.waveColors ?? null
    ),
  samudra_manthan_halahala: (c, p, t) => drawSamudraManthanEnsemble(c, p, t),
  halahala_orb: (c, p, t) =>
    drawHalahalaOrb(c, p.x ?? 540, p.y ?? 860, p.r ?? 44, t, p.alpha ?? 1.0, p.color ?? "emerald"),
  amrita_kalash: (c, p) => drawAmritaKalash(c, p.x ?? 540, p.y ?? 1142, p.scale ?? 1.0),
  brass_clock: (c, p, t) =>
    drawBrassClock(
      c,
      p.x ?? 540,
      p.y ?? 700,
      p.r ?? 138,
      p.slowAng ?? t * (p.slowRate ?? 0.2),
      p.fastAng ?? t * (p.fastRate ?? 1.4),
      p.smearAmt ?? 0.3,
      p.handCol ?? "#C83728"
    ),
  hourglass_stand: (c, p, t) => drawGroundedHourglassStand(c, p.x ?? 540, p.y ?? 1240, p.t ?? t),
  earth_globe: (c, p, t) =>
    drawVectorEarthGlobe(
      c,
      p.x ?? 540,
      p.y ?? 920,
      p.r ?? 150,
      p.rotPhase ?? t * (p.rotSpeed ?? 0.4),
      p.glowCol ?? "rgba(86, 186, 255, 0.36)"
    ),
  meru_route_scroll: (c, p, _t, localT) =>
    drawMeruRouteScroll(c, p.localT ?? localT, p.fromLabel ?? "DWARAKA", p.toLabel ?? "BRAHMALOKA"),
  magnifying_sector_lens: (c, p) =>
    drawMagnifyingSectorLens(c, p.x ?? 620, p.y ?? 780, p.r ?? 192, p.sectors ?? 27, p.progress ?? 1.0, p.pop ?? 1.0),
  spacetime_comparator: (c, p, t) =>
    drawSpacetimeComparator(c, p.t ?? t, p.leftTitle ?? "RELATIVITY", p.rightTitle ?? "SURYA SIDDHANTA"),
  wedding_mandap: (c, p, t) => drawWeddingMandap(c, p.floorY ?? 1230, p.t ?? t),
  kalachakra: drawKalachakraProp,
  brahmaloka_time_chakra: drawKalachakraProp,
  shani_drishti_mandala: (c, p, t) =>
    drawShaniDrishtiMandala(
      c,
      p.x ?? 540,
      p.y ?? 760,
      p.r ?? 220,
      p.t ?? t,
      p.speed ?? 1.0,
      p.opacity ?? 0.92,
      p.tint ? parseHexColor(p.tint) : SHANI_MANDALA_TINT
    ),
  iron_pillar: drawIronPillarProp,
  mehrauli_iron_pillar: drawIronPillarProp,
};

function resolvePropKey(prop) {
  if (!prop) return null;
  if (prop.id && PROP_DRAWERS[prop.id]) return prop.id;
  if (prop.kind && PROP_DRAWERS[prop.kind]) return prop.kind;
  return null;
}

export function drawRegisteredProp(ctx, prop, t = 0, localT = 0) {
  const key = resolvePropKey(prop);
  if (key) PROP_DRAWERS[key](ctx, prop, t, localT);
}

/**
 * Declarative scene prop list renderer handling Kurma-in-ocean wave interleaving
 * and Vasuki-around-Mandara back/front wrapping automatically.
 */
export function drawPropList(ctx, props = [], t = 0, localT = 0) {
  if (!Array.isArray(props) || props.length === 0) return;

  const keyed = props.map((p) => ({ prop: p, key: resolvePropKey(p) }));
  const kurmaProps = keyed.filter((item) => item.key === "kurma_avatar").map((item) => item.prop);
  const hasOcean = keyed.some((item) => item.key === "cosmic_ocean");
  const hasMandara = keyed.some((item) => item.key === "mount_mandara");
  const vasukiProps = keyed.filter((item) => item.key === "vasuki_serpent").map((item) => item.prop);
  const hasExplicitVasukiBack = vasukiProps.some((v) => v.layer === "back");

  const deferredVasuki = [];
  let backVasukiDrawn = false;

  for (const { prop, key } of keyed) {
    if (!key) continue;

    if (hasOcean && key === "kurma_avatar") {
      // Drawn via cosmic_ocean mid-back wave hook so Kurma emerges cleanly between wave planes
      continue;
    }

    if (key === "cosmic_ocean") {
      const hook =
        kurmaProps.length > 0
          ? () => {
              for (const kp of kurmaProps) {
                PROP_DRAWERS.kurma_avatar(ctx, kp, t, localT);
              }
            }
          : prop.drawMidBackHook ?? null;
      PROP_DRAWERS.cosmic_ocean(ctx, { ...prop, drawMidBackHook: hook }, t, localT);
      continue;
    }

    if (hasMandara && vasukiProps.length > 0 && !hasExplicitVasukiBack) {
      if (key === "vasuki_serpent") {
        deferredVasuki.push(prop);
        continue;
      }
      if (key === "mount_mandara") {
        if (!backVasukiDrawn) {
          for (const vp of vasukiProps) {
            PROP_DRAWERS.vasuki_serpent(ctx, { ...vp, layer: "back" }, t, localT);
          }
          backVasukiDrawn = true;
        }
        PROP_DRAWERS.mount_mandara(ctx, prop, t, localT);
        for (const vp of deferredVasuki) {
          PROP_DRAWERS.vasuki_serpent(ctx, { ...vp, layer: "front" }, t, localT);
        }
        deferredVasuki.length = 0;
        continue;
      }
    }

    PROP_DRAWERS[key](ctx, prop, t, localT);
  }

  for (const vp of deferredVasuki) {
    PROP_DRAWERS.vasuki_serpent(ctx, { ...vp, layer: "front" }, t, localT);
  }
}
