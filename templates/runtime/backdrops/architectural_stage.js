/**
 * Sutradhar v2 Architectural Stage Engine (Ref-1 HORIZON_Y Grounding Law).
 * Provides unified palace walls, dado wainscoting, fluted pilasters, 1-point perspective
 * floorboards, optional velvet curtains (Beat-1 opt-in), clock niches, and dais pedestals.
 */

import {
  CANVAS_HEIGHT,
  CANVAS_WIDTH,
  DEFAULT_HORIZON_Y,
  drawGlow,
  lerp,
} from "../core/seek_runtime.js";

export function drawPalaceInterior(ctx, opts = {}) {
  const {
    wallTop = "#3B162C",
    wallBot = "#5E233A",
    dadoTop = "#3D1824",
    floorColA = "#7C4C30",
    floorColB = "#4A2B1C",
    curtainCol = null,
    carpetCol = null,
    panOffsetX = 0,
    t = 0,
    hasDiyas = true,
    horizonY = DEFAULT_HORIZON_Y,
    width = CANVAS_WIDTH,
    height = CANVAS_HEIGHT,
  } = opts;

  const sky = ctx.createLinearGradient(0, 0, 0, horizonY);
  sky.addColorStop(0, wallTop);
  sky.addColorStop(1, wallBot);
  ctx.fillStyle = sky;
  ctx.fillRect(-120, -120, width + 240, horizonY + 120);

  // Rear wall dado wainscoting & fluted sandstone pilasters resting on horizonY
  ctx.save();
  ctx.translate(panOffsetX * 0.45, 0);
  const dadoY = horizonY - 250;
  ctx.fillStyle = dadoTop;
  ctx.fillRect(-500, dadoY, width + 1600, horizonY - dadoY);
  ctx.strokeStyle = "rgba(246, 196, 83, 0.36)";
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.moveTo(-500, dadoY);
  ctx.lineTo(width + 1100, dadoY);
  ctx.stroke();

  for (let x = -440; x < width + 1100; x += 220) {
    ctx.strokeStyle = "rgba(246, 196, 83, 0.22)";
    ctx.lineWidth = 2;
    ctx.strokeRect(x + 22, dadoY + 24, 176, 198);
    ctx.strokeRect(x + 34, dadoY + 36, 152, 174);
  }

  for (let px = -120; px <= width + 980; px += 460) {
    const pg = ctx.createLinearGradient(px, 0, px + 68, 0);
    pg.addColorStop(0, "rgba(255, 212, 128, 0.22)");
    pg.addColorStop(0.5, "rgba(255, 232, 176, 0.34)");
    pg.addColorStop(1, "rgba(70, 42, 22, 0.40)");
    ctx.fillStyle = pg;
    ctx.fillRect(px, 120, 68, horizonY - 120);

    ctx.fillStyle = "rgba(246, 196, 83, 0.56)";
    ctx.fillRect(px - 10, horizonY - 26, 88, 26);
    ctx.fillStyle = "rgba(246, 196, 83, 0.32)";
    ctx.fillRect(px - 16, horizonY, 100, 12);
  }

  if (hasDiyas) {
    for (let dx = -180; dx <= width + 860; dx += 145) {
      const dy = dadoY - 6;
      const fl = 0.82 + Math.sin(t * 9.2 + dx) * 0.16;
      drawGlow(ctx, dx, dy - 16, 4, 46 * fl, "rgba(255, 220, 120, 0.70)");
      ctx.fillStyle = "#B64A26";
      ctx.beginPath();
      ctx.ellipse(dx, dy, 20, 8, 0, 0, Math.PI);
      ctx.fill();
      ctx.fillStyle = "#FFE67E";
      ctx.beginPath();
      ctx.ellipse(dx, dy - 14 * fl, 6, 11 * fl, 0, 0, Math.PI * 2);
      ctx.fill();
    }
  }
  ctx.restore();

  // 1-Point Perspective Floorboards from horizonY -> height
  const fg = ctx.createLinearGradient(0, horizonY, 0, height);
  fg.addColorStop(0, floorColA);
  fg.addColorStop(0.28, floorColB);
  fg.addColorStop(1, "#140B09");
  ctx.fillStyle = fg;
  ctx.fillRect(-120, horizonY, width + 240, height - horizonY + 120);

  const seamShad = ctx.createLinearGradient(0, horizonY, 0, horizonY + 48);
  seamShad.addColorStop(0, "rgba(0, 0, 0, 0.42)");
  seamShad.addColorStop(1, "rgba(0, 0, 0, 0)");
  ctx.fillStyle = seamShad;
  ctx.fillRect(-120, horizonY, width + 240, 48);

  ctx.fillStyle = "#E6B245";
  ctx.fillRect(-120, horizonY - 5, width + 240, 8);

  ctx.save();
  ctx.strokeStyle = "rgba(0, 0, 0, 0.28)";
  ctx.lineWidth = 2.2;
  for (let i = -9; i <= 9; i++) {
    const topX = width * 0.5 + i * 54 + panOffsetX * 0.45;
    const botX = width * 0.5 + i * 205 + panOffsetX * 0.90;
    ctx.beginPath();
    ctx.moveTo(topX, horizonY + 3);
    ctx.lineTo(botX, height);
    ctx.stroke();
  }
  ctx.strokeStyle = "rgba(255, 224, 150, 0.11)";
  ctx.lineWidth = 1.6;
  for (let k = 1; k <= 8; k++) {
    const f = Math.pow(k / 8, 1.48);
    const hy = horizonY + f * (height - horizonY);
    ctx.beginPath();
    ctx.moveTo(0, hy);
    ctx.lineTo(width, hy);
    ctx.stroke();
  }
  ctx.restore();

  if (carpetCol) {
    ctx.save();
    ctx.fillStyle = carpetCol;
    ctx.beginPath();
    ctx.moveTo(275, horizonY + 14);
    ctx.lineTo(805, horizonY + 14);
    ctx.lineTo(950, height);
    ctx.lineTo(130, height);
    ctx.closePath();
    ctx.fill();
    ctx.strokeStyle = "#F6C453";
    ctx.lineWidth = 6;
    ctx.beginPath();
    ctx.moveTo(275, horizonY + 14);
    ctx.lineTo(130, height);
    ctx.moveTo(805, horizonY + 14);
    ctx.lineTo(950, height);
    ctx.moveTo(275, horizonY + 14);
    ctx.lineTo(805, horizonY + 14);
    ctx.stroke();
    ctx.restore();
  }

  if (curtainCol) {
    const hemY = horizonY + 123;
    for (const side of [-1, 1]) {
      const xBase = side < 0 ? 0 : width;
      ctx.fillStyle = curtainCol;
      ctx.beginPath();
      ctx.moveTo(xBase, 0);
      ctx.lineTo(xBase - side * 124, 0);
      ctx.quadraticCurveTo(xBase - side * 86 + Math.sin(t * 1.4) * 7, hemY * 0.52, xBase - side * 116, hemY);
      ctx.lineTo(xBase, hemY);
      ctx.closePath();
      ctx.fill();
      ctx.strokeStyle = "rgba(246, 196, 83, 0.65)";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(xBase - side * 124, 0);
      ctx.quadraticCurveTo(xBase - side * 86 + Math.sin(t * 1.4) * 7, hemY * 0.52, xBase - side * 116, hemY);
      ctx.stroke();
    }
  }
}

export function drawColonnadePillar(ctx, x, floorY = 1236, topY = 0, width = 74) {
  ctx.save();
  ctx.fillStyle = "rgba(8, 6, 14, 0.45)";
  ctx.beginPath();
  ctx.ellipse(x, floorY, width * 0.92, 16, 0, 0, Math.PI * 2);
  ctx.fill();

  const hw = width * 0.5;
  ctx.fillStyle = "#D49B38";
  ctx.fillRect(x - hw, topY, width, floorY - 31 - topY);
  ctx.fillStyle = "#8C5818";
  ctx.fillRect(x - hw * 0.38, topY, width * 0.22, floorY - 31 - topY);

  ctx.fillStyle = "#E6B552";
  ctx.strokeStyle = "#482210";
  ctx.lineWidth = 2.6;
  ctx.fillRect(x - hw - 15, floorY - 40, width + 30, 20);
  ctx.strokeRect(x - hw - 15, floorY - 40, width + 30, 20);
  ctx.fillRect(x - hw - 25, floorY - 20, width + 50, 20);
  ctx.strokeRect(x - hw - 25, floorY - 20, width + 50, 20);
  ctx.restore();
}

export function drawSteppedDais(ctx, x, floorY, w = 390, h = 98, opts = {}) {
  const { bodyCol = "#484870", borderCol = "#F6C453", cushion = false } = opts;
  ctx.save();
  ctx.translate(x, floorY);
  ctx.fillStyle = "rgba(6, 5, 16, 0.44)";
  ctx.beginPath();
  ctx.ellipse(0, 2, w * 0.54, 22, 0, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = bodyCol;
  ctx.strokeStyle = borderCol;
  ctx.lineWidth = 3.2;
  ctx.beginPath();
  ctx.roundRect(-w * 0.5, -h * 0.42, w, h * 0.42, 10);
  ctx.roundRect(-w * 0.4, -h, w * 0.8, h * 0.6, 10);
  ctx.fill();
  ctx.stroke();

  if (cushion) {
    ctx.fillStyle = "#B83562";
    ctx.strokeStyle = borderCol;
    ctx.lineWidth = 2.8;
    ctx.beginPath();
    ctx.ellipse(0, -h - 6, w * 0.24, 18, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  }
  ctx.restore();
}

export function drawClockShrineNiche(ctx, cx, cy, dialR, horizonY = DEFAULT_HORIZON_Y, drawDialFn = null) {
  ctx.save();
  ctx.fillStyle = "rgba(22, 18, 44, 0.85)";
  ctx.strokeStyle = "rgba(246, 196, 83, 0.55)";
  ctx.lineWidth = 3.5;
  ctx.beginPath();
  ctx.moveTo(cx - dialR - 38, horizonY - 5);
  ctx.lineTo(cx - dialR - 38, cy);
  ctx.arc(cx, cy, dialR + 38, Math.PI, 0, false);
  ctx.lineTo(cx + dialR + 38, horizonY - 5);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();

  if (typeof drawDialFn === "function") {
    ctx.fillStyle = "#D49B35";
    ctx.fillRect(cx - 48, cy + dialR - 4, 96, 16);
    ctx.fillRect(cx - 22, cy + dialR + 12, 44, horizonY - (cy + dialR + 12) - 5);
    drawGlow(ctx, cx, cy, 20, dialR + 110, "rgba(255, 214, 114, 0.34)");
    drawDialFn();
  }
  ctx.restore();
}

export function drawRoyalMusicStage(ctx, x, daisBot = 1218, t = 0) {
  const daisTop = daisBot - 92;
  ctx.save();
  ctx.fillStyle = "rgba(8, 6, 16, 0.44)";
  ctx.fillRect(x - 365, daisBot - 6, 730, 22);

  ctx.fillStyle = "#6F1D3A";
  ctx.strokeStyle = "#F6C453";
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.moveTo(x - 325, 1092);
  ctx.lineTo(x + 315, 1092);
  ctx.lineTo(x + 345, daisTop + 18);
  ctx.lineTo(x - 355, daisTop + 18);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = "#C78E2E";
  ctx.fillRect(x - 355, daisTop + 18, 700, 44);
  ctx.strokeRect(x - 355, daisTop + 18, 700, 44);
  ctx.fillStyle = "#9C6B1D";
  ctx.fillRect(x - 367, daisBot - 30, 724, 30);
  ctx.strokeRect(x - 367, daisBot - 30, 724, 30);

  for (const gx of [x - 170, x + 160]) {
    const cushionY = daisTop - 2;
    ctx.fillStyle = "rgba(8, 6, 16, 0.36)";
    ctx.beginPath();
    ctx.ellipse(gx, cushionY + 8, 92, 20, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#B83562";
    ctx.beginPath();
    ctx.ellipse(gx, cushionY, 86, 22, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  }

  for (let r = 0; r < 4; r++) {
    const p = ((t * 0.65 + r * 0.25) % 1);
    ctx.strokeStyle = `rgba(255, 224, 130, ${(0.65 * (1 - p)).toFixed(3)})`;
    ctx.lineWidth = 3.2;
    ctx.beginPath();
    ctx.arc(x, 810 - p * 200, Math.max(1, 35 + p * 170), Math.PI * 1.15, Math.PI * 1.85);
    ctx.stroke();
  }
  ctx.restore();
}
