/**
 * Sutradhar v2 Anatomical Character Engine.
 * Fuses Episode 4's tapered traceCapsule limbs, 5-finger drawSculptedHand poses,
 * 2.5D head turn parallax, high-arched hairlines clear of tilak, and phoneme mouthOpen
 * interpolation with hero, royal, sage, and musician presets.
 */

import { clamp, drawGlow, drawHalahalaOrb, lerp } from "../core/seek_runtime.js";

export const CHARACTER_PRESETS = {
  shiva: {
    skin: "#DCE6F4", skinDark: "#94A8C8", dhotiA: "#D97A28", dhotiB: "#7C3914",
    sash: "#233C70", trim: "#F6C453", hair: "#201522", lip: "#7D4450", iris: "#26334D",
    role: "shiva", upperW: 16.5, elbowW: 12.0, wristW: 8.2, defaultScale: 0.9,
    headgear: "jatamukuta_chandrama", tilak: "tripundra_trinetra",
    adornment: "rudraksha_serpent", garment: "tiger_dhoti", tigerSeatDefault: true,
  },
  devi: {
    skin: "#F5C298", skinDark: "#CC865A", dhotiA: "#C92448", dhotiB: "#7A1028",
    sash: "#FFB248", trim: "#FFE282", hair: "#1B1018", lip: "#B83546", iris: "#3E2216",
    role: "devi", upperW: 13.0, elbowW: 10.0, wristW: 7.2, defaultScale: 0.86,
    headgear: "karanda_mukuta_odhani", tilak: "kumkum_bindi",
    adornment: "gold_temple_necklace", garment: "zari_saree", tigerSeatDefault: false,
  },
  brahma: {
    skin: "#F4C294", skinDark: "#D69464", dhotiA: "#F5C453", dhotiB: "#C27C1E",
    sash: "#FCE8C8", trim: "#FFD365", hair: "#ECE6DF", lip: "#8F423B", iris: "#3E2216",
    role: "brahma", upperW: 16.0, elbowW: 11.8, wristW: 8.0, defaultScale: 0.8,
    beard: true, extraArms: true, threeHeads: true,
    headgear: "chaturmukha_kirita", tilak: "urdhva_pundra",
    adornment: "gold_kanthihara", garment: "royal_dhoti", tigerSeatDefault: false,
  },
  vishnu: {
    skin: "#7EB8F0", skinDark: "#4A82C4", dhotiA: "#F6C453", dhotiB: "#C47D18",
    sash: "#D62839", trim: "#FFE680", hair: "#1A1220", lip: "#743E4E", iris: "#26334D",
    role: "deva", upperW: 16.5, elbowW: 12.0, wristW: 8.2, defaultScale: 0.88,
    extraArms: true,
    headgear: "kirita_mukuta", tilak: "urdhva_pundra",
    adornment: "kaustubha_vaijayanti", garment: "royal_dhoti", tigerSeatDefault: false,
  },
  shani_dev: {
    skin: "#56638A", skinDark: "#303956", dhotiA: "#263159", dhotiB: "#131830",
    sash: "#D49B35", trim: "#F6C453", hair: "#140D18", lip: "#4C3240", iris: "#1D2640",
    role: "deva", upperW: 16.5, elbowW: 12.2, wristW: 8.4, defaultScale: 0.88,
    headgear: "kirita_mukuta", tilak: "tripundra_gold",
    adornment: "iron_gold_kanthihara", garment: "royal_dhoti", tigerSeatDefault: false,
  },
  surya_dev: {
    skin: "#F6B97A", skinDark: "#CE8444", dhotiA: "#E88224", dhotiB: "#A83E10",
    sash: "#C41E3A", trim: "#FFE875", hair: "#201214", lip: "#984438", iris: "#3E2216",
    role: "deva", upperW: 16.5, elbowW: 12.0, wristW: 8.2, defaultScale: 0.88,
    headgear: "kirita_mukuta_solar", tilak: "surya_tilak",
    adornment: "solar_prabhavali", garment: "royal_dhoti", tigerSeatDefault: false,
  },
  ravana: {
    skin: "#B87C64", skinDark: "#7D4838", dhotiA: "#681930", dhotiB: "#360A18",
    sash: "#B83B28", trim: "#D49B35", hair: "#180D14", lip: "#78302E", iris: "#6E1D1A",
    role: "asura", upperW: 17.5, elbowW: 13.0, wristW: 8.8, defaultScale: 0.92,
    headgear: "asura_horned_kirita", tilak: "asura_flame_mark",
    adornment: "gold_kanthihara", garment: "royal_dhoti", tigerSeatDefault: false,
  },
  kakudmi: {
    skin: "#E8B186", skinDark: "#C88A62", dhotiA: "#E88B2C", dhotiB: "#B5481A",
    sash: "#A61D33", trim: "#FFD365", hair: "#1E1218", lip: "#8F423B", iris: "#3E2216",
    role: "king", upperW: 16.5, elbowW: 12.2, wristW: 8.4, defaultScale: 0.86,
    headgear: "winged_royal_crown", tilak: "urdhva_pundra",
    adornment: "emerald_kanthihara", garment: "royal_dhoti", tigerSeatDefault: false,
  },
  balarama: {
    skin: "#6EB3F5", skinDark: "#4584C4", dhotiA: "#F4C23D", dhotiB: "#BA7A14",
    sash: "#2766B8", trim: "#FFE57F", hair: "#1E1218", lip: "#6E4B68", iris: "#26334D",
    role: "king", upperW: 17.5, elbowW: 12.8, wristW: 8.6, defaultScale: 0.94,
    headgear: "winged_royal_crown", tilak: "urdhva_pundra",
    adornment: "gold_kanthihara", garment: "royal_dhoti", tigerSeatDefault: false,
  },
  revati: {
    skin: "#F0BC92", skinDark: "#C88860", dhotiA: "#E95A7E", dhotiB: "#A22449",
    sash: "#FFCC92", trim: "#FFE282", hair: "#1B1018", lip: "#B83546", iris: "#3E2216",
    role: "princess", upperW: 13.0, elbowW: 10.0, wristW: 7.2, defaultScale: 0.83,
    headgear: "gajara_bun_tiara", tilak: "kumkum_bindi",
    adornment: "gold_kanthihara", garment: "pleated_lehenga", tigerSeatDefault: false,
  },
  sutradhar_narrator: {
    skin: "#E6AF84", skinDark: "#BE8058", dhotiA: "#D97B2A", dhotiB: "#8C3D12",
    sash: "#FAF0DC", trim: "#F6C453", hair: "#2A1E24", lip: "#8C463E", iris: "#3E2216",
    role: "sage", upperW: 15.5, elbowW: 11.5, wristW: 8.0, defaultScale: 0.85,
    beard: true,
    headgear: "sage_jataknot", tilak: "tripundra_chandan",
    adornment: "rudraksha_mala", garment: "sage_dhoti", tigerSeatDefault: false,
  },
  ancient_scholar: {
    skin: "#E2AA7E", skinDark: "#B67950", dhotiA: "#B65428", dhotiB: "#6E2B14",
    sash: "#F2DFC0", trim: "#E6B245", hair: "#E4DDD4", lip: "#8A463C", iris: "#3E2216",
    role: "scholar", upperW: 15.2, elbowW: 11.2, wristW: 7.8, defaultScale: 0.84,
    beard: true,
    headgear: "sage_jataknot", tilak: "chandan_bindu",
    adornment: "rudraksha_mala", garment: "sage_dhoti", tigerSeatDefault: false,
  },
  deva: {
    skin: "#EFC396", skinDark: "#C48858", dhotiA: "#E89B2D", dhotiB: "#984216",
    sash: "#9C1C34", trim: "#FFD464", hair: "#1E1218", lip: "#8F423B", iris: "#3E2216",
    role: "deva", upperW: 16.5, elbowW: 12.0, wristW: 8.2, defaultScale: 0.9,
    headgear: "kirita_mukuta", tilak: "urdhva_pundra",
    adornment: "gold_kanthihara", garment: "royal_dhoti", tigerSeatDefault: false,
  },
  asura: {
    skin: "#B87C64", skinDark: "#7D4838", dhotiA: "#681930", dhotiB: "#360A18",
    sash: "#B83B28", trim: "#D49B35", hair: "#180D14", lip: "#78302E", iris: "#6E1D1A",
    role: "asura", upperW: 16.5, elbowW: 12.2, wristW: 8.4, defaultScale: 0.9,
    headgear: "asura_horned_kirita", tilak: "asura_flame_mark",
    adornment: "gold_kanthihara", garment: "royal_dhoti", tigerSeatDefault: false,
  },
  gandharva: {
    skin: "#F0B98C", skinDark: "#C88A62", dhotiA: "#45C4B0", dhotiB: "#187E74",
    sash: "#E68A2E", trim: "#FFD365", hair: "#1E1218", lip: "#8F423B", iris: "#3E2216",
    role: "deva", upperW: 15.5, elbowW: 11.5, wristW: 8.0, defaultScale: 0.85,
    headgear: "winged_royal_crown", tilak: "chandan_bindu",
    adornment: "gold_kanthihara", garment: "royal_dhoti", tigerSeatDefault: false,
  },
};

export function resolveCharacterPreset(roleOrId = "deva", overrides = {}) {
  const key = typeof roleOrId === "object" && roleOrId !== null ? roleOrId.id || roleOrId.rig_role || "deva" : roleOrId;
  const base = CHARACTER_PRESETS[key] || CHARACTER_PRESETS.deva;
  const spec = typeof roleOrId === "object" && roleOrId !== null ? roleOrId : null;
  const flatSpec = spec
    ? {
        ...(spec.rig_role ? { role: spec.rig_role } : {}),
        ...(spec.palette || {}),
        ...(spec.proportions || {}),
        ...(spec.features || {}),
      }
    : {};
  return { ...base, ...flatSpec, ...overrides };
}

export function traceCapsule(ctx, x0, y0, r0, x1, y1, r1, skipStartCap = false) {
  const dx = x1 - x0;
  const dy = y1 - y0;
  const dist = Math.max(1, Math.hypot(dx, dy));
  const theta = Math.atan2(dy, dx);
  const beta = Math.asin(clamp((r0 - r1) / dist, -0.98, 0.98));
  const a0 = theta + Math.PI * 0.5 - beta;
  const a1 = theta - Math.PI * 0.5 + beta;
  ctx.beginPath();
  if (skipStartCap) {
    ctx.moveTo(x0 + Math.cos(a1) * r0, y0 + Math.sin(a1) * r0);
    ctx.arc(x1, y1, r1, a1, a0, false);
    ctx.lineTo(x0 + Math.cos(a0) * r0, y0 + Math.sin(a0) * r0);
  } else {
    ctx.arc(x0, y0, r0, a0, a1, false);
    ctx.arc(x1, y1, r1, a1, a0, false);
  }
  ctx.closePath();
  ctx.fill();
}

export function drawSculptedHand(ctx, x, y, angle, palmPose, skin, skinDark, ink) {
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(angle);
  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  ctx.strokeStyle = ink;
  ctx.lineWidth = 2.2;

  if (palmPose === "cup" || palmPose === "palm_open" || palmPose === "bless") {
    const g = ctx.createLinearGradient(0, -14, 0, 14);
    g.addColorStop(0, skin);
    g.addColorStop(1, skinDark);
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.moveTo(-4, -8);
    ctx.quadraticCurveTo(10, -12, 22, -6);
    ctx.quadraticCurveTo(32, -8, 35, -3);
    ctx.quadraticCurveTo(33, 4, 24, 6);
    ctx.quadraticCurveTo(14, 12, -2, 8);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(4, -7);
    ctx.quadraticCurveTo(12, -16, 18, -11);
    ctx.quadraticCurveTo(13, -5, 6, -4);
    ctx.fill();
    ctx.stroke();

    ctx.strokeStyle = "rgba(46,21,18,0.45)";
    ctx.lineWidth = 1.4;
    for (const fy of [-3, 0, 3]) {
      ctx.beginPath();
      ctx.moveTo(20, fy);
      ctx.lineTo(31, fy + 1);
      ctx.stroke();
    }
  } else if (palmPose === "namaskar") {
    ctx.fillStyle = skin;
    ctx.beginPath();
    ctx.moveTo(-8, 12);
    ctx.quadraticCurveTo(-11, -4, -6, -24);
    ctx.quadraticCurveTo(0, -32, 6, -24);
    ctx.quadraticCurveTo(10, -4, 7, 12);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(-5, 8);
    ctx.quadraticCurveTo(-9, -4, -4, -10);
    ctx.stroke();
  } else if (palmPose === "grip") {
    ctx.fillStyle = skin;
    ctx.beginPath();
    ctx.roundRect(-8, -12, 24, 22, 8);
    ctx.fill();
    ctx.stroke();
    ctx.strokeStyle = "rgba(46,21,18,0.6)";
    ctx.lineWidth = 1.8;
    for (const fy of [-5, 1, 7]) {
      ctx.beginPath();
      ctx.moveTo(0, fy);
      ctx.lineTo(14, fy);
      ctx.stroke();
    }
    ctx.fillStyle = skinDark;
    ctx.strokeStyle = ink;
    ctx.lineWidth = 2.0;
    ctx.beginPath();
    ctx.roundRect(-6, -13, 18, 8, 4);
    ctx.fill();
    ctx.stroke();
  } else {
    ctx.fillStyle = skin;
    ctx.beginPath();
    ctx.moveTo(-4, -9);
    ctx.quadraticCurveTo(8, -11, 20, -8);
    ctx.quadraticCurveTo(32, -9, 34, -4);
    ctx.quadraticCurveTo(35, 1, 31, 4);
    ctx.quadraticCurveTo(22, 10, 6, 10);
    ctx.quadraticCurveTo(-3, 7, -4, -9);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.strokeStyle = "rgba(46,21,18,0.48)";
    ctx.lineWidth = 1.5;
    for (let f = -4; f <= 4; f += 3.5) {
      ctx.beginPath();
      ctx.moveTo(19, f);
      ctx.lineTo(31, f + (f > 0 ? 1 : -1));
      ctx.stroke();
    }
  }
  ctx.restore();
}

export function drawAnatomicalArm(ctx, sx, sy, ex, ey, hx, hy, opts) {
  const {
    upperW = 16.5,
    elbowW = 12.0,
    wristW = 8.2,
    skin,
    skinDark,
    ink,
    armletCol,
    wristCol,
    palmPose = "relax",
    handAng = null,
  } = opts;

  const dx1 = ex - sx;
  const dy1 = ey - sy;
  const dx2 = hx - ex;
  const dy2 = hy - ey;
  const len1 = Math.max(1, Math.hypot(dx1, dy1));
  const nx1 = -dy1 / len1;
  const ny1 = dx1 / len1;

  const pad = 2.8;
  ctx.fillStyle = ink;
  traceCapsule(ctx, sx, sy, upperW + pad, ex, ey, elbowW + pad, true);
  ctx.beginPath();
  ctx.arc(ex, ey, elbowW + pad, 0, Math.PI * 2);
  ctx.fill();
  traceCapsule(ctx, ex, ey, elbowW + pad, hx, hy, wristW + pad, false);

  const ag = ctx.createLinearGradient(sx - nx1 * upperW, sy - ny1 * upperW, sx + nx1 * upperW, sy + ny1 * upperW);
  ag.addColorStop(0, skin);
  ag.addColorStop(0.68, skin);
  ag.addColorStop(1, skinDark);
  ctx.fillStyle = ag;
  traceCapsule(ctx, sx, sy, upperW, ex, ey, elbowW, false);
  ctx.beginPath();
  ctx.arc(ex, ey, elbowW, 0, Math.PI * 2);
  ctx.fill();
  traceCapsule(ctx, ex, ey, elbowW, hx, hy, wristW, false);

  ctx.fillStyle = "rgba(255, 255, 255, 0.14)";
  ctx.beginPath();
  ctx.arc(sx, sy + 4, upperW * 0.62, 0, Math.PI * 2);
  ctx.fill();

  const kx = lerp(sx, ex, 0.45);
  const ky = lerp(sy, ey, 0.45);
  const kang = Math.atan2(dy1, dx1);
  const armR = lerp(upperW, elbowW, 0.45) + 0.6;
  ctx.save();
  ctx.translate(kx, ky);
  ctx.rotate(kang);
  ctx.fillStyle = armletCol;
  ctx.strokeStyle = ink;
  ctx.lineWidth = 2.0;
  ctx.beginPath();
  ctx.roundRect(-4.5, -armR, 9, armR * 2, 3);
  ctx.fill();
  ctx.stroke();
  ctx.restore();

  const wang = Math.atan2(dy2, dx2);
  ctx.save();
  ctx.translate(hx - Math.cos(wang) * 6, hy - Math.sin(wang) * 6);
  ctx.rotate(wang);
  ctx.fillStyle = wristCol;
  ctx.strokeStyle = ink;
  ctx.lineWidth = 1.9;
  ctx.beginPath();
  ctx.roundRect(-4.5, -wristW * 1.12, 8.5, wristW * 2.24, 3);
  ctx.fill();
  ctx.stroke();
  ctx.restore();

  const finalAng = handAng !== null ? handAng : wang;
  drawSculptedHand(ctx, hx, hy, finalAng, palmPose, skin, skinDark, ink);
}

function traceFaceContour(ctx, shX) {
  ctx.beginPath();
  ctx.moveTo(-40 + shX * 0.2, -236);
  ctx.bezierCurveTo(-43, -274, 43, -274, 40 + shX * 0.2, -236);
  ctx.bezierCurveTo(42 + shX * 0.4, -212, 37 + shX * 0.5, -190, 22 + shX * 0.7, -174);
  ctx.quadraticCurveTo(shX, -164, -22 + shX * 0.7, -174);
  ctx.bezierCurveTo(-37 + shX * 0.5, -190, -42 + shX * 0.4, -212, -40 + shX * 0.2, -236);
  ctx.closePath();
}

export function drawMythFace(ctx, opts) {
  const {
    role = "shiva",
    turn = 0.0,
    tilt = 0.0,
    expr = "serene",
    blink = false,
    mouthOpen = 0.0,
    pal,
  } = opts;
  const ink = "#261214";
  const effectiveRole = pal.role || role;
  const isFeminine = effectiveRole === "devi" || effectiveRole === "princess";
  const hasBeard = Boolean(pal.beard);
  const threeHeads = Boolean(pal.threeHeads);
  const clampedTurn = clamp(turn, -0.35, 0.35);

  ctx.save();
  ctx.rotate(tilt);

  if (threeHeads) {
    for (const side of [-1, 1]) {
      ctx.save();
      ctx.translate(side * 50, -212);
      ctx.scale(0.76, 0.76);
      ctx.fillStyle = pal.skinDark;
      ctx.strokeStyle = ink;
      ctx.lineWidth = 2.8;
      ctx.beginPath();
      ctx.ellipse(0, 0, 38, 44, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
      if (hasBeard) {
        ctx.fillStyle = "#F5EFE6";
        ctx.strokeStyle = "#5C4033";
        ctx.lineWidth = 2.2;
        ctx.beginPath();
        ctx.moveTo(-20, 26);
        ctx.quadraticCurveTo(0, 62, 20, 26);
        ctx.quadraticCurveTo(0, 38, -20, 26);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
      }
      ctx.fillStyle = pal.trim;
      ctx.strokeStyle = "#482210";
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.moveTo(-30, -34);
      ctx.lineTo(0, -108);
      ctx.lineTo(30, -34);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
      ctx.restore();
    }
  }

  // Solar Prabhavali halo behind Surya Dev's head
  if (pal.adornment === "solar_prabhavali") {
    ctx.save();
    ctx.translate(0, -214);
    drawGlow(ctx, 0, 0, 26, 108, "rgba(255, 206, 86, 0.56)");
    ctx.strokeStyle = "rgba(255, 224, 118, 0.72)";
    ctx.lineWidth = 3.0;
    ctx.beginPath();
    ctx.arc(0, 0, 74, 0, Math.PI * 2);
    ctx.stroke();
    for (let i = 0; i < 12; i++) {
      const a = (i / 12) * Math.PI * 2;
      ctx.beginPath();
      ctx.moveTo(Math.cos(a) * 76, Math.sin(a) * 76);
      ctx.lineTo(Math.cos(a) * 94, Math.sin(a) * 94);
      ctx.stroke();
    }
    ctx.restore();
  }

  // Back long hair layer
  ctx.fillStyle = pal.hair;
  ctx.strokeStyle = "#120A12";
  ctx.lineWidth = 2.4;
  if (effectiveRole === "shiva") {
    ctx.beginPath();
    ctx.moveTo(-42, -238);
    ctx.quadraticCurveTo(-62, -195, -56, -135);
    ctx.quadraticCurveTo(-50, -108, -36, -112);
    ctx.lineTo(-28, -172);
    ctx.lineTo(28, -172);
    ctx.lineTo(38, -116);
    ctx.quadraticCurveTo(54, -122, 58, -172);
    ctx.quadraticCurveTo(56, -214, 42, -238);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.strokeStyle = "rgba(120, 145, 195, 0.28)";
    ctx.lineWidth = 2.2;
    for (const sx of [-48, -42, 46]) {
      ctx.beginPath();
      ctx.moveTo(sx, -220);
      ctx.quadraticCurveTo(sx * 1.15, -175, sx * 0.92, -132);
      ctx.stroke();
    }
  } else if (effectiveRole === "devi") {
    for (const side of [-1, 1]) {
      ctx.fillStyle = pal.dhotiB;
      ctx.strokeStyle = "#120A12";
      ctx.lineWidth = 2.4;
      ctx.beginPath();
      ctx.moveTo(side * 34, -252);
      ctx.bezierCurveTo(side * 64, -220, side * 66, -172, side * 58, -148);
      ctx.quadraticCurveTo(side * 34, -158, side * 22, -174);
      ctx.lineTo(side * 28, -238);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
    }
    ctx.fillStyle = pal.dhotiB;
    ctx.strokeStyle = "#120A12";
    ctx.beginPath();
    ctx.moveTo(-42, -238);
    ctx.quadraticCurveTo(0, -280, 42, -238);
    ctx.quadraticCurveTo(0, -256, -42, -238);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.strokeStyle = pal.trim;
    ctx.lineWidth = 4.0;
    ctx.beginPath();
    ctx.moveTo(-41, -239);
    ctx.quadraticCurveTo(0, -274, 41, -239);
    ctx.stroke();
  } else {
    for (const s of [-1, 1]) {
      ctx.fillStyle = pal.hair;
      ctx.beginPath();
      ctx.moveTo(s * 34, -242);
      ctx.quadraticCurveTo(s * 54, -198, s * 46, -158);
      ctx.lineTo(s * 30, -162);
      ctx.closePath();
      ctx.fill();
    }
  }

  // Ears & Kundala earrings with 2.5D head turn visibility
  for (const side of [-1, 1]) {
    const earVis = 1 - Math.max(0, side * clampedTurn * 1.4);
    if (earVis < 0.25) continue;
    const ex = side * (41 - side * clampedTurn * 12);
    ctx.fillStyle = pal.skinDark;
    ctx.strokeStyle = ink;
    ctx.lineWidth = 2.2;
    ctx.beginPath();
    ctx.ellipse(ex, -214, 7 * earVis, 14, side * 0.14, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.strokeStyle = effectiveRole === "shiva" ? "#E2BA5A" : pal.trim;
    ctx.lineWidth = 3.2;
    ctx.beginPath();
    ctx.arc(ex + side * 2, -198, 7.5 * earVis, 0, Math.PI * 2);
    ctx.stroke();
  }

  const shX = clampedTurn * 18;
  const faceG = ctx.createLinearGradient(-42, -264, 42, -168);
  faceG.addColorStop(0, pal.skin);
  faceG.addColorStop(0.72, pal.skin);
  faceG.addColorStop(1, pal.skinDark);

  ctx.fillStyle = faceG;
  traceFaceContour(ctx, shX);
  ctx.fill();

  ctx.save();
  ctx.clip();
  const shadowSide = clampedTurn >= 0 ? -1 : 1;
  ctx.fillStyle = "rgba(42, 24, 52, 0.14)";
  ctx.beginPath();
  ctx.ellipse(shadowSide * 32 + shX * 0.5, -214, 24, 48, shadowSide * 0.15, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = effectiveRole === "shiva" ? "rgba(255, 255, 255, 0.24)" : "rgba(255, 232, 206, 0.22)";
  ctx.beginPath();
  ctx.ellipse(shX - shadowSide * 14, -208, 12, 8, -0.2, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();

  ctx.strokeStyle = ink;
  ctx.lineWidth = 2.8;
  traceFaceContour(ctx, shX);
  ctx.stroke();

  if (hasBeard) {
    ctx.fillStyle = "#F5EFE6";
    ctx.strokeStyle = "#5C4033";
    ctx.lineWidth = 2.2;
    ctx.beginPath();
    ctx.moveTo(-24 + shX * 0.6, -184);
    ctx.quadraticCurveTo(shX * 0.8, -138, 24 + shX * 0.6, -184);
    ctx.quadraticCurveTo(shX * 0.8, -168, -24 + shX * 0.6, -184);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
  }

  // Tilak / Tripundra / Trinetra / Surya Tilak / Bindi
  const fx = shX * 0.92;
  const tilakType = pal.tilak || (effectiveRole === "shiva" ? "tripundra_trinetra" : isFeminine ? "kumkum_bindi" : "urdhva_pundra");
  if (tilakType === "tripundra_trinetra" || tilakType === "tripundra_gold" || tilakType === "tripundra_chandan") {
    ctx.strokeStyle =
      tilakType === "tripundra_gold"
        ? pal.trim
        : tilakType === "tripundra_chandan"
          ? "#F8DF9C"
          : "#FFFFFF";
    ctx.lineWidth = 2.6;
    ctx.lineCap = "round";
    for (const ty of [-248, -242.5, -237]) {
      ctx.beginPath();
      ctx.moveTo(fx - 15, ty);
      ctx.quadraticCurveTo(fx, ty - 1.5, fx + 15, ty);
      ctx.stroke();
    }
    ctx.fillStyle = tilakType === "tripundra_chandan" ? "#D63638" : "#E63946";
    ctx.strokeStyle = "#5A1216";
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    if (tilakType === "tripundra_trinetra") {
      ctx.ellipse(fx, -242.5, 3.3, 6.2, 0, 0, Math.PI * 2);
    } else {
      ctx.arc(fx, -242.5, 3.6, 0, Math.PI * 2);
    }
    ctx.fill();
    ctx.stroke();
  } else if (tilakType === "surya_tilak") {
    ctx.strokeStyle = "#FFE67E";
    ctx.lineWidth = 2.4;
    ctx.beginPath();
    ctx.moveTo(fx, -254);
    ctx.lineTo(fx, -234);
    ctx.stroke();
    ctx.fillStyle = "#FFB703";
    ctx.strokeStyle = "#8C2D0C";
    ctx.lineWidth = 1.4;
    ctx.beginPath();
    ctx.arc(fx, -242, 6.2, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = "#E63946";
    ctx.beginPath();
    ctx.arc(fx, -242, 2.8, 0, Math.PI * 2);
    ctx.fill();
  } else if (tilakType === "kumkum_bindi" || tilakType === "chandan_bindu") {
    ctx.fillStyle = tilakType === "kumkum_bindi" ? "#E62442" : "#F6C453";
    ctx.beginPath();
    ctx.arc(fx, -240, 4.4, 0, Math.PI * 2);
    ctx.fill();
    if (isFeminine) {
      ctx.fillStyle = pal.trim;
      ctx.beginPath();
      ctx.arc(fx, -252, 4.2, 0, Math.PI * 2);
      ctx.fill();
    }
  } else if (tilakType === "asura_flame_mark") {
    ctx.fillStyle = "#FF4D38";
    ctx.beginPath();
    ctx.moveTo(fx - 7, -250);
    ctx.lineTo(fx, -236);
    ctx.lineTo(fx + 7, -250);
    ctx.closePath();
    ctx.fill();
  } else {
    ctx.strokeStyle = pal.trim;
    ctx.lineWidth = 2.6;
    ctx.beginPath();
    ctx.moveTo(fx - 4, -248);
    ctx.quadraticCurveTo(fx, -235, fx + 4, -248);
    ctx.stroke();
    ctx.fillStyle = "#FF5733";
    ctx.beginPath();
    ctx.arc(fx, -241, 2.5, 0, Math.PI * 2);
    ctx.fill();
  }

  // Expressive Brows & Almond Eyes
  const eyeY = -219;
  const browShift = expr === "fear" ? -6 : expr === "determined" ? 3 : expr === "compassionate" ? -2.5 : 0;
  for (const side of [-1, 1]) {
    const ex = fx + side * 16 * (1 - Math.abs(clampedTurn) * 0.16);
    const exScaleX = side * clampedTurn < 0 ? 1 - Math.abs(clampedTurn) * 0.45 : 1.0;

    ctx.strokeStyle = effectiveRole === "shiva" ? "#1E121E" : "#221010";
    ctx.lineWidth = isFeminine ? 3.2 : 4.2;
    ctx.lineCap = "round";
    ctx.beginPath();
    if (expr === "determined" || effectiveRole === "asura") {
      ctx.moveTo(ex - side * 11 * exScaleX, eyeY - 9 + browShift);
      ctx.quadraticCurveTo(ex, eyeY - 16 + browShift, ex + side * 11 * exScaleX, eyeY - 12);
    } else {
      ctx.moveTo(ex - side * 11 * exScaleX, eyeY - 12 + browShift);
      ctx.quadraticCurveTo(ex, eyeY - 18 + browShift, ex + side * 11 * exScaleX, eyeY - 10 + browShift * 0.4);
    }
    ctx.stroke();

    if (blink) {
      ctx.strokeStyle = ink;
      ctx.lineWidth = 2.6;
      ctx.beginPath();
      ctx.moveTo(ex - 9 * exScaleX, eyeY);
      ctx.quadraticCurveTo(ex, eyeY + 5, ex + 9 * exScaleX, eyeY);
      ctx.stroke();
    } else {
      ctx.fillStyle = "#FAF8F4";
      ctx.strokeStyle = ink;
      ctx.lineWidth = 2.0;
      ctx.beginPath();
      ctx.moveTo(ex - 10.5 * exScaleX, eyeY + 0.5);
      ctx.quadraticCurveTo(ex, eyeY - 8.5, ex + 10.5 * exScaleX, eyeY + 0.5);
      ctx.quadraticCurveTo(ex, eyeY + 7.2, ex - 10.5 * exScaleX, eyeY + 0.5);
      ctx.closePath();
      ctx.fill();

      ctx.save();
      ctx.clip();
      const irisOff = clamp(clampedTurn * 6, -3.5, 3.5);
      const irisR = isFeminine ? 5.2 : 5.4;
      const irisCol = pal.iris || (effectiveRole === "shiva" ? "#26334D" : effectiveRole === "asura" ? "#6E1D1A" : "#3E2216");
      ctx.fillStyle = irisCol;
      ctx.beginPath();
      ctx.arc(ex + irisOff, eyeY, irisR, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#100B0E";
      ctx.beginPath();
      ctx.arc(ex + irisOff, eyeY, irisR * 0.52, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#FFFFFF";
      ctx.beginPath();
      ctx.arc(ex + irisOff - 1.6, eyeY - 1.8, 1.8, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();

      ctx.strokeStyle = "#1E0E14";
      ctx.lineWidth = isFeminine ? 3.2 : 2.8;
      ctx.beginPath();
      ctx.moveTo(ex - 11.5 * exScaleX, eyeY + 0.8);
      ctx.quadraticCurveTo(ex, eyeY - 8.8, ex + 12 * exScaleX, eyeY);
      ctx.stroke();
      ctx.strokeStyle = "rgba(46,21,18,0.45)";
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.moveTo(ex - 9 * exScaleX, eyeY + 2);
      ctx.quadraticCurveTo(ex, eyeY + 7, ex + 9 * exScaleX, eyeY + 1.5);
      ctx.stroke();
    }
  }

  // Nose bridge
  const nx = fx + clampedTurn * 4;
  ctx.strokeStyle = "rgba(86, 40, 28, 0.58)";
  ctx.lineWidth = 2.1;
  ctx.beginPath();
  ctx.moveTo(nx - clampedTurn * 2, -219);
  ctx.quadraticCurveTo(nx + (clampedTurn >= 0 ? 5 : -5), -203, nx + (clampedTurn >= 0 ? 4 : -4), -199);
  ctx.quadraticCurveTo(nx, -196.5, nx - (clampedTurn >= 0 ? 3.5 : -3.5), -198.5);
  ctx.stroke();
  ctx.fillStyle = "rgba(86, 40, 28, 0.24)";
  ctx.beginPath();
  ctx.ellipse(nx, -197, 5, 2.4, 0, 0, Math.PI * 2);
  ctx.fill();

  // Sculpted Lips + Phoneme Mouth Openness Interpolation
  const mx = fx + clampedTurn * 2.5;
  const my = -184;
  const openAmt = expr === "fear" ? Math.max(0.75, mouthOpen) : clamp(mouthOpen, 0, 1);
  if (openAmt > 0.08) {
    const ry = 2.5 + openAmt * 5.2;
    const rx = 7.5 + openAmt * 2.5;
    ctx.fillStyle = "#5C1B1E";
    ctx.strokeStyle = "#2E1212";
    ctx.lineWidth = 2.0;
    ctx.beginPath();
    ctx.ellipse(mx, my + 1.8, rx, ry, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  } else {
    const smileLift = expr === "smile" ? -3.2 : expr === "compassionate" ? -1.8 : 0;
    ctx.fillStyle = pal.lip || (isFeminine ? "#B83546" : effectiveRole === "shiva" ? "#7D4450" : "#8F423B");
    ctx.beginPath();
    ctx.moveTo(mx - 12, my);
    ctx.quadraticCurveTo(mx - 5, my - 4, mx, my - 2);
    ctx.quadraticCurveTo(mx + 5, my - 4, mx + 12, my + smileLift * 0.4);
    ctx.quadraticCurveTo(mx, my + 3 + smileLift * 0.2, mx - 12, my);
    ctx.closePath();
    ctx.fill();
    ctx.strokeStyle = "#4A1C20";
    ctx.lineWidth = 2.1;
    ctx.beginPath();
    ctx.moveTo(mx - 12, my + 0.5);
    ctx.quadraticCurveTo(mx, my + 2.8 - smileLift, mx + 12, my + smileLift * 0.4);
    ctx.stroke();
    ctx.strokeStyle = "rgba(74,28,32,0.45)";
    ctx.lineWidth = 1.8;
    ctx.beginPath();
    ctx.moveTo(mx - 6, my + 5);
    ctx.quadraticCurveTo(mx, my + 7.2, mx + 6, my + 5);
    ctx.stroke();
  }

  // High-arched parted hairline clear of tilak
  ctx.fillStyle = pal.hair;
  ctx.strokeStyle = "#140A12";
  ctx.lineWidth = 2.2;
  ctx.beginPath();
  ctx.moveTo(-40 + shX * 0.2, -238);
  ctx.quadraticCurveTo(-22 + fx * 0.4, -264, fx, -253);
  ctx.quadraticCurveTo(22 + fx * 0.4, -264, 40 + shX * 0.2, -238);
  ctx.arc(0, -228, 43, -0.22, Math.PI + 0.22, true);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();

  const hg = pal.headgear || (effectiveRole === "shiva" ? "jatamukuta_chandrama" : effectiveRole === "devi" ? "karanda_mukuta_odhani" : "kirita_mukuta");
  if (hg === "jatamukuta_chandrama") {
    ctx.fillStyle = "#221624";
    ctx.strokeStyle = "#100812";
    ctx.lineWidth = 2.4;
    ctx.beginPath();
    ctx.ellipse(-shX * 0.1, -279, 27, 21, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.beginPath();
    ctx.ellipse(-shX * 0.1, -304, 17, 13, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.strokeStyle = "#8C4A22";
    ctx.lineWidth = 4.2;
    ctx.beginPath();
    ctx.moveTo(-23, -270);
    ctx.quadraticCurveTo(0, -264, 23, -270);
    ctx.stroke();

    ctx.fillStyle = "#FFF9D8";
    ctx.strokeStyle = "#D49B35";
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    ctx.arc(-19, -290, 15, 0.35, Math.PI * 1.68);
    ctx.arc(-11.5, -293, 11.5, Math.PI * 1.68, 0.35, true);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    ctx.strokeStyle = "rgba(145, 228, 255, 0.85)";
    ctx.lineWidth = 2.6;
    ctx.beginPath();
    ctx.moveTo(4, -310);
    ctx.quadraticCurveTo(18, -322, 24, -304);
    ctx.stroke();
  } else if (hg === "gajara_bun_tiara") {
    ctx.fillStyle = pal.hair;
    ctx.strokeStyle = "#140A12";
    ctx.lineWidth = 2.2;
    ctx.beginPath();
    ctx.ellipse(0, -274, 24, 18, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    // Delicate jasmine gajara floral arc around top bun
    for (let g = -3; g <= 3; g++) {
      const ga = g * 0.34 - Math.PI * 0.5;
      const gx = Math.cos(ga) * 23;
      const gy = -274 + Math.sin(ga) * 18;
      ctx.fillStyle = "#FFF8E8";
      ctx.strokeStyle = "#D49B35";
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.arc(gx, gy, 4.5, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    }
    // Slender royal tiara
    const tg = ctx.createLinearGradient(0, -304, 0, -256);
    tg.addColorStop(0, "#FFF2A6");
    tg.addColorStop(1, "#C98520");
    ctx.fillStyle = tg;
    ctx.strokeStyle = "#3B1E10";
    ctx.lineWidth = 2.1;
    ctx.beginPath();
    ctx.moveTo(-25, -257);
    ctx.lineTo(-14, -278);
    ctx.lineTo(0, -296);
    ctx.lineTo(14, -278);
    ctx.lineTo(25, -257);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = "#E62442";
    ctx.beginPath();
    ctx.arc(0, -270, 4.0, 0, Math.PI * 2);
    ctx.fill();
  } else if (hg === "karanda_mukuta_odhani") {
    ctx.fillStyle = pal.hair;
    ctx.beginPath();
    ctx.moveTo(-36, -246);
    ctx.quadraticCurveTo(-40, -220, -34, -200);
    ctx.lineTo(-40, -238);
    ctx.closePath();
    ctx.fill();
    ctx.beginPath();
    ctx.moveTo(36, -246);
    ctx.quadraticCurveTo(40, -220, 34, -200);
    ctx.lineTo(40, -238);
    ctx.closePath();
    ctx.fill();
    const cg = ctx.createLinearGradient(0, -314, 0, -260);
    cg.addColorStop(0, "#FFF2A6");
    cg.addColorStop(1, "#C98520");
    ctx.fillStyle = cg;
    ctx.strokeStyle = "#3B1E10";
    ctx.lineWidth = 2.2;
    ctx.beginPath();
    ctx.moveTo(-26, -260);
    ctx.lineTo(-18, -292);
    ctx.lineTo(0, -316);
    ctx.lineTo(18, -292);
    ctx.lineTo(26, -260);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = "#D62839";
    ctx.beginPath();
    ctx.arc(0, -278, 4.5, 0, Math.PI * 2);
    ctx.fill();
  } else if (hg === "sage_jataknot") {
    ctx.fillStyle = pal.hair;
    ctx.strokeStyle = "#140A12";
    ctx.lineWidth = 2.2;
    ctx.beginPath();
    ctx.ellipse(0, -276, 22, 16, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.strokeStyle = pal.trim;
    ctx.lineWidth = 3.2;
    ctx.beginPath();
    ctx.moveTo(-20, -264);
    ctx.quadraticCurveTo(0, -258, 20, -264);
    ctx.stroke();
  } else {
    const isAsura = hg === "asura_horned_kirita" || effectiveRole === "asura";
    const isWinged = hg === "winged_royal_crown";
    const isSolar = hg === "kirita_mukuta_solar";
    const isChaturmukha = hg === "chaturmukha_kirita";
    const cg = ctx.createLinearGradient(-30, -352, 30, -256);
    cg.addColorStop(0, isAsura ? "#B87A32" : "#FFF2A2");
    cg.addColorStop(1, isAsura ? "#5A3018" : "#C47D18");
    ctx.fillStyle = cg;
    ctx.strokeStyle = "#3B1E10";
    ctx.lineWidth = 2.4;
    if (isSolar) {
      ctx.save();
      ctx.strokeStyle = "#FFE066";
      ctx.lineWidth = 2.6;
      for (let i = -3; i <= 3; i++) {
        const a = -Math.PI * 0.5 + i * 0.24;
        ctx.beginPath();
        ctx.moveTo(Math.cos(a) * 34, -278 + Math.sin(a) * 34);
        ctx.lineTo(Math.cos(a) * 62, -278 + Math.sin(a) * 62);
        ctx.stroke();
      }
      ctx.restore();
    }
    if (isWinged) {
      for (const s of [-1, 1]) {
        ctx.beginPath();
        ctx.moveTo(s * 34, -256);
        ctx.quadraticCurveTo(s * 62, -280, s * 46, -296);
        ctx.lineTo(s * 24, -276);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
      }
    }
    ctx.beginPath();
    ctx.moveTo(-37, -254);
    ctx.lineTo(-28, -290);
    ctx.lineTo(-17, -320);
    ctx.lineTo(0, isChaturmukha ? -364 : -354);
    ctx.lineTo(17, -320);
    ctx.lineTo(28, -290);
    ctx.lineTo(37, -254);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    if (isChaturmukha) {
      // Tiered Brahma lotus crown bands
      ctx.strokeStyle = "#FFF7CC";
      ctx.lineWidth = 2.2;
      ctx.beginPath();
      ctx.moveTo(-22, -296);
      ctx.lineTo(22, -296);
      ctx.stroke();
      ctx.fillStyle = "#FF9EBB";
      ctx.strokeStyle = "#3B1E10";
      ctx.lineWidth = 1.8;
      ctx.beginPath();
      ctx.ellipse(0, -365, 8, 5.5, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    }

    ctx.strokeStyle = "#FFF7CC";
    ctx.lineWidth = 2.2;
    ctx.beginPath();
    ctx.moveTo(-28, -272);
    ctx.lineTo(28, -272);
    ctx.stroke();
    ctx.fillStyle = isAsura || isSolar ? "#E63946" : "#22D3EE";
    ctx.beginPath();
    ctx.arc(0, -285, 5.2, 0, Math.PI * 2);
    ctx.fill();

    if (isAsura) {
      ctx.fillStyle = "#EDE0C8";
      ctx.strokeStyle = "#2E1512";
      ctx.lineWidth = 2.2;
      for (const s of [-1, 1]) {
        ctx.beginPath();
        ctx.moveTo(s * 24, -276);
        ctx.quadraticCurveTo(s * 58, -304, s * 44, -338);
        ctx.quadraticCurveTo(s * 42, -310, s * 20, -292);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
      }
    }
  }
  ctx.restore();
}

function drawRudrakshaBeads(ctx, ink) {
  for (let b = -6; b <= 6; b++) {
    const ang = b * 0.16 + Math.PI * 0.5;
    const bx = Math.cos(ang) * 44;
    const by = -126 + Math.sin(ang) * 40;
    ctx.fillStyle = "#7D4018";
    ctx.strokeStyle = ink;
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    ctx.arc(bx, by, 5.2, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  }
}

function drawStringedInstrument(ctx, kind, t, armCfg) {
  const isVeena = kind === "veena";
  drawAnatomicalArm(ctx, -68, -134, -104, -84, -76, -102, { ...armCfg, palmPose: "grip" });
  ctx.save();
  ctx.strokeStyle = "#4A2210";
  ctx.lineWidth = isVeena ? 11 : 10;
  ctx.beginPath();
  ctx.moveTo(46, -4);
  ctx.lineTo(-86, -112);
  ctx.stroke();
  if (isVeena) {
    // Upper Saraswati Veena resonator gourd + curved yali finial
    ctx.fillStyle = "#B86622";
    ctx.strokeStyle = "#3B1E12";
    ctx.lineWidth = 2.4;
    ctx.beginPath();
    ctx.arc(-56, -86, 14, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.strokeStyle = "#F6C453";
    ctx.lineWidth = 4.0;
    ctx.beginPath();
    ctx.moveTo(-86, -112);
    ctx.quadraticCurveTo(-102, -132, -88, -142);
    ctx.stroke();
  }
  ctx.strokeStyle = "#F6C453";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(42, -8);
  ctx.lineTo(-82, -108);
  ctx.stroke();
  ctx.fillStyle = isVeena ? "#D6822E" : "#C47528";
  ctx.strokeStyle = "#3B1E12";
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.arc(46, -4, isVeena ? 28 : 26, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  if (isVeena) {
    ctx.strokeStyle = "#FFE58F";
    ctx.lineWidth = 2.2;
    ctx.beginPath();
    ctx.arc(46, -4, 15, 0, Math.PI * 2);
    ctx.stroke();
  }
  ctx.restore();
  const st = Math.sin(t * 7.2) * 10;
  drawAnatomicalArm(ctx, 68, -134, 96, -64, 26, -24 + st, { ...armCfg, palmPose: "relax" });
}

export function drawMythCharacter(ctx, opts) {
  const {
    x,
    y,
    scale,
    dir = 1,
    t = 0,
    id = null,
    role = "shiva",
    pose = "neutral",
    expr = "serene",
    turn = 0.0,
    headTilt = 0.0,
    armLift = 0.0,
    mouthOpen = 0.0,
    seated = false,
    tigerSeat = false,
    neelakantha = 0,
    halahalaInHand = 0,
    halahalaColor = "emerald",
    instrument = null,
  } = opts;

  const pal = resolveCharacterPreset(id || role, opts.paletteOverrides || {});
  const effectiveRole = pal.role || role;
  const charScale = scale ?? pal.defaultScale ?? 0.9;
  const resolvedTigerSeat = opts.tigerSeat !== undefined ? Boolean(opts.tigerSeat) : Boolean(pal.tigerSeatDefault);
  const ink = "#261214";
  const breath = Math.sin(t * 2.1 + x * 0.01) * 2.8;
  const blink = ((t * 0.48 + x * 0.002) % 3.7) > 3.55;
  const hipY = seated ? -128 : -342;
  const isFeminine = effectiveRole === "devi" || effectiveRole === "princess";

  ctx.save();
  ctx.translate(x, y);

  // Dual-layer contact shadow grounding character firmly onto floor/terrain/dais at (0, 0)
  ctx.fillStyle = "rgba(6, 5, 16, 0.28)";
  ctx.beginPath();
  ctx.ellipse(0, 2, (seated ? 138 : 108) * charScale, (seated ? 25 : 21) * charScale, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "rgba(6, 5, 16, 0.50)";
  ctx.beginPath();
  ctx.ellipse(0, 1, (seated ? 98 : 66) * charScale, (seated ? 14 : 13) * charScale, 0, 0, Math.PI * 2);
  ctx.fill();

  ctx.scale(dir * charScale, charScale);

  if (seated && resolvedTigerSeat) {
    ctx.save();
    ctx.fillStyle = "#D47C26";
    ctx.strokeStyle = "#2E1512";
    ctx.lineWidth = 3.0;
    ctx.beginPath();
    ctx.moveTo(-148, 8);
    ctx.quadraticCurveTo(-162, -26, -124, -44);
    ctx.lineTo(124, -44);
    ctx.quadraticCurveTo(162, -24, 148, 8);
    ctx.quadraticCurveTo(80, 18, 0, 14);
    ctx.quadraticCurveTo(-80, 18, -148, 8);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.strokeStyle = "rgba(28, 12, 8, 0.72)";
    ctx.lineWidth = 4.5;
    for (const sx of [-115, -75, -35, 35, 75, 115]) {
      ctx.beginPath();
      ctx.moveTo(sx, -36);
      ctx.quadraticCurveTo(sx + 8, -16, sx - 6, 4);
      ctx.stroke();
    }
    ctx.restore();
  }

  // Lower Body
  const gSkirt = ctx.createLinearGradient(-70, hipY, 70, 0);
  gSkirt.addColorStop(0, pal.dhotiA);
  gSkirt.addColorStop(0.65, pal.dhotiA);
  gSkirt.addColorStop(1, pal.dhotiB);
  ctx.strokeStyle = ink;
  ctx.lineWidth = 3.0;

  if (seated) {
    ctx.fillStyle = effectiveRole === "shiva" ? "#D67E2B" : gSkirt;
    ctx.beginPath();
    ctx.moveTo(-64, hipY);
    ctx.bezierCurveTo(-116, -98, -138, -42, -118, -8);
    ctx.quadraticCurveTo(-40, 10, 0, 4);
    ctx.quadraticCurveTo(40, 10, 118, -8);
    ctx.bezierCurveTo(138, -42, 116, -98, 64, hipY);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    for (const side of [-1, 1]) {
      ctx.fillStyle = pal.skinDark;
      ctx.beginPath();
      ctx.ellipse(side * 56, -12, 34, 12, side * -0.15, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = pal.skin;
      ctx.beginPath();
      ctx.ellipse(side * 24, -18, 17, 10, side * 0.25, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    }

    if (effectiveRole === "shiva") {
      ctx.strokeStyle = "rgba(32, 14, 10, 0.72)";
      ctx.lineWidth = 4.2;
      for (const sx of [-78, -44, -12, 18, 48, 78]) {
        ctx.beginPath();
        ctx.moveTo(sx, -104);
        ctx.quadraticCurveTo(sx + 10, -70, sx - 6, -34);
        ctx.stroke();
      }
      ctx.fillStyle = "#9C2232";
      ctx.strokeStyle = ink;
      ctx.lineWidth = 2.6;
      ctx.beginPath();
      ctx.roundRect(-64, hipY - 8, 128, 18, 5);
      ctx.fill();
      ctx.stroke();
    } else {
      ctx.strokeStyle = pal.trim;
      ctx.lineWidth = 7;
      ctx.beginPath();
      ctx.moveTo(-112, -16);
      ctx.quadraticCurveTo(0, 2, 112, -16);
      ctx.stroke();
    }
  } else {
    for (const fx of [-36, 36]) {
      ctx.fillStyle = pal.skinDark;
      ctx.beginPath();
      ctx.ellipse(fx, -7, 23, 10, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = pal.trim;
      ctx.beginPath();
      ctx.roundRect(fx - 13, -19, 26, 7.5, 3);
      ctx.fill();
      ctx.stroke();
    }
    if (isFeminine) {
      const isLehenga = pal.garment === "pleated_lehenga";
      ctx.fillStyle = gSkirt;
      ctx.beginPath();
      ctx.moveTo(-54, hipY);
      ctx.bezierCurveTo(-96, -210, -128, -96, -134, -18);
      ctx.quadraticCurveTo(0, -3, 134, -18);
      ctx.bezierCurveTo(126, -96, 94, -210, 54, hipY);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
      ctx.strokeStyle = isLehenga ? "rgba(255, 226, 130, 0.42)" : "rgba(58, 6, 18, 0.45)";
      ctx.lineWidth = isLehenga ? 2.6 : 2.4;
      const pleatXs = isLehenga ? [-68, -42, -16, 14, 42, 68] : [-24, -8, 10, 28];
      for (const px of pleatXs) {
        ctx.beginPath();
        ctx.moveTo(px * 0.4, hipY + 12);
        ctx.quadraticCurveTo(px * 0.9, -150, px, -24);
        ctx.stroke();
      }
      ctx.strokeStyle = pal.trim;
      ctx.lineWidth = 10;
      ctx.beginPath();
      ctx.moveTo(-130, -28);
      ctx.quadraticCurveTo(0, -11, 130, -28);
      ctx.stroke();
    } else {
      ctx.fillStyle = gSkirt;
      ctx.beginPath();
      ctx.moveTo(-62, hipY);
      ctx.bezierCurveTo(-86, -200, -84, -90, -76, -18);
      ctx.quadraticCurveTo(-28, -5, -4, -24);
      ctx.lineTo(12, -24);
      ctx.quadraticCurveTo(36, -5, 82, -18);
      ctx.bezierCurveTo(86, -94, 84, -204, 62, hipY);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
      ctx.strokeStyle = "rgba(42, 14, 10, 0.36)";
      ctx.lineWidth = 2.2;
      for (const [fx0, fx1] of [[-46, -54], [46, 54]]) {
        ctx.beginPath();
        ctx.moveTo(fx0, hipY + 24);
        ctx.quadraticCurveTo(fx1 * 1.15, -180, fx1, -32);
        ctx.stroke();
      }
      ctx.fillStyle = pal.trim;
      ctx.strokeStyle = ink;
      ctx.fillRect(-64, hipY - 10, 128, 20);
      ctx.strokeRect(-64, hipY - 10, 128, 20);
      ctx.fillStyle = pal.sash;
      ctx.beginPath();
      ctx.moveTo(-22, hipY + 10);
      ctx.lineTo(22, hipY + 10);
      ctx.lineTo(30, -104);
      ctx.lineTo(0, -78);
      ctx.lineTo(-30, -104);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
    }
  }

  // Torso
  ctx.save();
  ctx.translate(0, hipY + 4 + breath * 0.7);

  if (isFeminine) {
    ctx.fillStyle = pal.dhotiB;
    ctx.strokeStyle = ink;
    ctx.lineWidth = 2.8;
    ctx.beginPath();
    ctx.moveTo(-48, 4);
    ctx.quadraticCurveTo(-60, -72, -62, -138);
    ctx.quadraticCurveTo(0, -158, 62, -138);
    ctx.quadraticCurveTo(60, -72, 48, 4);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    const pg = ctx.createLinearGradient(-40, -150, 90, 90);
    pg.addColorStop(0, pal.dhotiA);
    pg.addColorStop(1, pal.dhotiB);
    ctx.fillStyle = pg;
    ctx.beginPath();
    ctx.moveTo(-30, -150);
    ctx.quadraticCurveTo(18, -90, 62, 6);
    ctx.lineTo(-42, 6);
    ctx.quadraticCurveTo(-98, -45, -72, -132);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    ctx.strokeStyle = pal.trim;
    ctx.lineWidth = 6;
    ctx.beginPath();
    ctx.moveTo(-28, -148);
    ctx.quadraticCurveTo(20, -88, 60, 4);
    ctx.stroke();

    ctx.fillStyle = pal.skin;
    ctx.strokeStyle = ink;
    ctx.lineWidth = 2.2;
    ctx.beginPath();
    ctx.moveTo(-30, -150);
    ctx.quadraticCurveTo(0, -124, 30, -150);
    ctx.quadraticCurveTo(0, -158, -30, -150);
    ctx.closePath();
    ctx.fill();
  } else {
    const gSkin = ctx.createLinearGradient(-72, -150, 72, 10);
    gSkin.addColorStop(0, pal.skin);
    gSkin.addColorStop(0.65, pal.skin);
    gSkin.addColorStop(1, pal.skinDark);
    ctx.fillStyle = gSkin;
    ctx.strokeStyle = ink;
    ctx.lineWidth = 3.0;
    ctx.beginPath();
    ctx.moveTo(-54, 4);
    ctx.bezierCurveTo(-68, -42, -84, -96, -86, -134);
    ctx.quadraticCurveTo(-50, -158, 0, -156);
    ctx.quadraticCurveTo(50, -158, 86, -134);
    ctx.bezierCurveTo(84, -96, 68, -42, 54, 4);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    ctx.strokeStyle = "rgba(52, 24, 24, 0.36)";
    ctx.lineWidth = 2.1;
    for (const s of [-1, 1]) {
      ctx.beginPath();
      ctx.moveTo(s * 14, -142);
      ctx.quadraticCurveTo(s * 42, -138, s * 62, -128);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(s * 8, -98);
      ctx.quadraticCurveTo(s * 34, -84, s * 64, -98);
      ctx.stroke();
    }
    ctx.beginPath();
    ctx.moveTo(0, -96);
    ctx.lineTo(0, -18);
    ctx.stroke();

    if (effectiveRole === "shiva") {
      ctx.strokeStyle = "rgba(255, 255, 255, 0.72)";
      ctx.lineWidth = 2.4;
      for (const ty of [-124, -118, -112]) {
        ctx.beginPath();
        ctx.moveTo(-48, ty);
        ctx.lineTo(-18, ty);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(18, ty);
        ctx.lineTo(48, ty);
        ctx.stroke();
      }
    }

    ctx.fillStyle = effectiveRole === "shiva" ? "#C97222" : pal.sash;
    ctx.strokeStyle = effectiveRole === "shiva" ? ink : pal.trim;
    ctx.lineWidth = 2.6;
    ctx.beginPath();
    ctx.moveTo(-80, -140);
    ctx.quadraticCurveTo(-12, -80, 62, -14);
    ctx.lineTo(50, 14);
    ctx.quadraticCurveTo(-30, -52, -92, -108);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    if (effectiveRole === "shiva") {
      ctx.strokeStyle = "rgba(32, 14, 10, 0.65)";
      ctx.lineWidth = 3.2;
      ctx.beginPath();
      ctx.moveTo(-64, -112);
      ctx.lineTo(-50, -94);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(-26, -78);
      ctx.lineTo(-12, -62);
      ctx.stroke();
    }
  }

  // Necklaces, Rudraksha mala, Vaijayanti garland & Shiva shoulder serpent
  const adornment = pal.adornment || (effectiveRole === "shiva" ? "rudraksha_serpent" : "gold_kanthihara");
  if (adornment === "rudraksha_serpent") {
    ctx.strokeStyle = ink;
    ctx.lineWidth = 11;
    ctx.lineCap = "round";
    ctx.beginPath();
    ctx.moveTo(-58, -138);
    ctx.quadraticCurveTo(0, -108, 60, -142);
    ctx.stroke();
    ctx.strokeStyle = "#3B667E";
    ctx.lineWidth = 7.2;
    ctx.beginPath();
    ctx.moveTo(-58, -138);
    ctx.quadraticCurveTo(0, -108, 60, -142);
    ctx.stroke();
    ctx.fillStyle = "#3E6B84";
    ctx.strokeStyle = ink;
    ctx.lineWidth = 2.0;
    ctx.beginPath();
    ctx.ellipse(62, -148, 8.5, 13, 0.22, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = "#FFD750";
    ctx.beginPath();
    ctx.arc(64, -152, 2.0, 0, Math.PI * 2);
    ctx.fill();

    drawRudrakshaBeads(ctx, ink);
  } else if (adornment === "rudraksha_mala") {
    drawRudrakshaBeads(ctx, ink);
  } else {
    if (adornment === "kaustubha_vaijayanti") {
      // Flowing Vaijayanti garland across chest
      ctx.strokeStyle = "#FFF0A8";
      ctx.lineWidth = 7.5;
      ctx.beginPath();
      ctx.moveTo(-46, -144);
      ctx.quadraticCurveTo(0, -14, 46, -144);
      ctx.stroke();
      ctx.strokeStyle = "#D62839";
      ctx.lineWidth = 3.2;
      ctx.beginPath();
      ctx.moveTo(-40, -144);
      ctx.quadraticCurveTo(0, -26, 40, -144);
      ctx.stroke();
    }
    ctx.strokeStyle = adornment === "iron_gold_kanthihara" ? "#434E72" : pal.trim;
    ctx.lineWidth = adornment === "gold_temple_necklace" ? 8.0 : 6.5;
    ctx.beginPath();
    ctx.arc(0, -148, 42, 0.24, Math.PI - 0.24);
    ctx.stroke();
    if (adornment === "gold_temple_necklace" || adornment === "iron_gold_kanthihara") {
      ctx.strokeStyle = pal.trim;
      ctx.lineWidth = 3.0;
      ctx.beginPath();
      ctx.arc(0, -144, 52, 0.3, Math.PI - 0.3);
      ctx.stroke();
    }
    ctx.fillStyle =
      adornment === "emerald_kanthihara"
        ? "#16CE82"
        : adornment === "iron_gold_kanthihara"
          ? "#3B82F6"
          : "#D62839";
    ctx.beginPath();
    ctx.arc(0, -104, 5.5, 0, Math.PI * 2);
    ctx.fill();
  }

  // Arms & Hands
  const armCfg = {
    upperW: pal.upperW || (isFeminine ? 13 : 16.5),
    elbowW: pal.elbowW || (isFeminine ? 10 : 12.5),
    wristW: pal.wristW || (isFeminine ? 7.2 : 8.5),
    skin: pal.skin,
    skinDark: pal.skinDark,
    ink,
    armletCol: effectiveRole === "shiva" ? "#8D4D22" : pal.trim,
    wristCol: effectiveRole === "shiva" ? "#8D4D22" : isFeminine ? "#D62839" : pal.trim,
  };

  if (pal.extraArms) {
    drawAnatomicalArm(ctx, -70, -138, -132, -196, -118, -242, { ...armCfg, palmPose: "bless", handAng: -1.4 });
    drawAnatomicalArm(ctx, 70, -138, 132, -196, 118, -242, { ...armCfg, palmPose: "bless", handAng: -1.7 });
  }

  let palmGlowPos = null;
  if (instrument === "sitar" || instrument === "veena" || pose === "veena_play" || pose === "strum") {
    const instKind = instrument === "sitar" ? "sitar" : "veena";
    drawStringedInstrument(ctx, instKind, t, armCfg);
  } else if (pose === "namaskar") {
    drawAnatomicalArm(ctx, -68, -134, -84, -74, -14, -92, { ...armCfg, palmPose: "namaskar", handAng: 0.15 });
    drawAnatomicalArm(ctx, 68, -134, 84, -74, 14, -92, { ...armCfg, palmPose: "namaskar", handAng: -0.15 });
  } else if (pose === "shield" || pose === "awed") {
    const lift = Math.sin(t * 4.5) * 6 + armLift * 18;
    drawAnatomicalArm(ctx, -70, -132, -106, -74, -82, -132 - lift, { ...armCfg, palmPose: "palm_open", handAng: -0.7 });
    drawAnatomicalArm(ctx, 70, -132, 114, -72, 92, -138 - lift, { ...armCfg, palmPose: "palm_open", handAng: 0.7 });
  } else if (pose === "pull") {
    drawAnatomicalArm(ctx, -64, -130, -94, -84, -134, -64, { ...armCfg, palmPose: "grip", handAng: 0.25 });
    drawAnatomicalArm(ctx, 56, -130, 14, -88, -68, -64, { ...armCfg, palmPose: "grip", handAng: 2.90 });
  } else if (pose === "palm_cup" || pose === "drink") {
    const raise = pose === "drink" ? armLift : 0;
    const hx = lerp(132, 32, raise);
    const hy = lerp(-98, -158, raise);
    drawAnatomicalArm(ctx, -68, -134, -92, -62, -74, -16, { ...armCfg, palmPose: "relax" });
    drawAnatomicalArm(ctx, 70, -134, lerp(114, 96, raise), lerp(-68, -78, raise), hx, hy, { ...armCfg, palmPose: "cup", handAng: lerp(-0.12, -0.35, raise) });
    palmGlowPos = { x: hx + 14, y: hy - 28 };
  } else if (pose === "throat_reach") {
    drawAnatomicalArm(ctx, -56, -132, -78, -64, -62, -16, { ...armCfg, palmPose: "relax" });
    drawAnatomicalArm(ctx, 58, -132, 128, -82, 206, -68, { ...armCfg, palmPose: "palm_open", handAng: -0.05 });
  } else if (pose === "gesture" || pose === "bless" || pose === "clasp") {
    drawAnatomicalArm(ctx, -68, -134, -92, -64, -74, -16, { ...armCfg, palmPose: "relax" });
    drawAnatomicalArm(
      ctx,
      72,
      -134,
      116,
      -92,
      146,
      pose === "clasp" ? -56 : -102 - armLift * 18,
      { ...armCfg, palmPose: pose === "bless" ? "bless" : "cup", handAng: -0.2 }
    );
  } else {
    drawAnatomicalArm(ctx, -68, -134, -94, -62, -74, -12, { ...armCfg, palmPose: "relax" });
    drawAnatomicalArm(ctx, 68, -134, 94, -62, 74, -12, { ...armCfg, palmPose: "relax" });
  }

  // Halahala Orb in palm (emerald by default)
  if (palmGlowPos && halahalaInHand > 0.02) {
    drawHalahalaOrb(
      ctx,
      palmGlowPos.x,
      palmGlowPos.y,
      30 * clamp(halahalaInHand, 0.25, 1.15),
      t,
      clamp(halahalaInHand, 0, 1),
      halahalaColor
    );
  }

  // Neck & Sapphire Neelakantha glow
  ctx.fillStyle = pal.skinDark;
  ctx.strokeStyle = ink;
  ctx.lineWidth = 2.6;
  ctx.beginPath();
  ctx.moveTo(-20, -148);
  ctx.quadraticCurveTo(-15, -166, -16, -186);
  ctx.lineTo(16, -186);
  ctx.quadraticCurveTo(15, -166, 20, -148);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();

  if (neelakantha > 0.02) {
    const pulse = 0.88 + 0.12 * Math.sin(t * 4.0);
    drawGlow(ctx, 0, -166, 4, 62 * neelakantha * pulse, `rgba(42, 195, 255, ${(0.80 * neelakantha).toFixed(3)})`);
    const ng = ctx.createRadialGradient(0, -166, 2, 0, -166, 22);
    ng.addColorStop(0, `rgba(185, 246, 255, ${neelakantha})`);
    ng.addColorStop(0.55, `rgba(26, 134, 255, ${0.95 * neelakantha})`);
    ng.addColorStop(1, "rgba(10, 48, 128, 0)");
    ctx.fillStyle = ng;
    ctx.beginPath();
    ctx.ellipse(0, -166, 21, 15, 0, 0, Math.PI * 2);
    ctx.fill();
  }

  drawMythFace(ctx, { role: effectiveRole, turn, tilt: headTilt, expr, blink, mouthOpen, pal });

  ctx.restore();
  ctx.restore();
}
