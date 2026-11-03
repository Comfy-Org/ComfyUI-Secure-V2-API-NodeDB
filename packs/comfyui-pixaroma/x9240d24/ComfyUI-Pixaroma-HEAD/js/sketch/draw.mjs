// Sketch Pixaroma - drawing the marks on a canvas.
//
// Marks are drawn in the PICTURE's own pixel space (a transform maps it onto
// the screen), with the SAME geometry as nodes/_sketch_helpers.py: line width
// from the picture's long side, the midpoint-quadratic freehand curve, the
// arrow head, the text size and its baseline. So what the node shows is what
// the edit model will get.

import { pixAsset } from "../shared/api_url.mjs";
import {
  COLORS, HEAD_HALF, HEAD_MIN, HEAD_SCALE, MIN_LINE_PX, TEXT_BASELINE, TEXT_SCALE, WIDTHS, rgbOf,
} from "./core.mjs";

export const FONT_FAMILY = "PixSketchInter";
let _font = null;

/** The bundled Inter, the same file Python draws text with. Loaded once. */
export function ensureSketchFont(onReady) {
  if (!_font) {
    _font = (async () => {
      const face = new FontFace(FONT_FAMILY, `url("${pixAsset("fonts/Inter-Variable.ttf")}")`, { weight: "100 900" });
      await face.load();
      document.fonts.add(face);
      return true;
    })().catch((e) => {
      console.warn("[Sketch] could not load the text font, using the system one", e);
      return false;
    });
  }
  _font.then(() => onReady?.());
  return _font;
}

export const halfUp = (x) => Math.floor(x + 0.5);

export function linePx(wKey, longSide) {
  return Math.max(MIN_LINE_PX, (WIDTHS[wKey] || WIDTHS.M) * longSide);
}

export function textSizePx(lw) {
  return Math.max(8, halfUp(lw * TEXT_SCALE));
}

export function textOutlinePx(size) {
  return Math.max(1, halfUp(Math.max(2, size / 7) / 2));
}

/** The picture fitted inside a box, centred (object-fit: contain). */
export function fitRect(iw, ih, cw, ch) {
  if (!(iw > 0 && ih > 0 && cw > 0 && ch > 0)) return { x: 0, y: 0, w: 0, h: 0 };
  const s = Math.min(cw / iw, ch / ih);
  const w = iw * s;
  const h = ih * s;
  return { x: (cw - w) / 2, y: (ch - h) / 2, w, h };
}

/** Mirror of _sketch_helpers.arrow_geometry. */
export function arrowGeometry(p0, p1, lw) {
  const dx = p1[0] - p0[0];
  const dy = p1[1] - p0[1];
  const length = Math.hypot(dx, dy);
  const ang = Math.atan2(dy, dx);
  let hl = Math.max(lw * HEAD_SCALE, HEAD_MIN);
  if (length > 0) hl = Math.min(hl, length / 1.5);
  const tip = p1;
  const c1 = [tip[0] - hl * Math.cos(ang - HEAD_HALF), tip[1] - hl * Math.sin(ang - HEAD_HALF)];
  const c2 = [tip[0] - hl * Math.cos(ang + HEAD_HALF), tip[1] - hl * Math.sin(ang + HEAD_HALF)];
  const back = hl * Math.cos(HEAD_HALF);
  const base = [tip[0] - back * Math.cos(ang), tip[1] - back * Math.sin(ang)];
  return { base, head: [tip, c1, c2] };
}

/** Is a freehand stroke a loop drawn AROUND something? Decided once, here, and
 *  stored on the mark, so Python never judges the same stroke differently.
 *  `P` in picture pixels. */
export function isClosedLoop(P, lw) {
  if (P.length < 3) return false;
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const [x, y] of P) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }
  const diag = Math.hypot(x1 - x0, y1 - y0);
  if (diag < lw * 4) return false;
  const a = P[0];
  const b = P[P.length - 1];
  return Math.hypot(b[0] - a[0], b[1] - a[1]) <= Math.max(0.15 * diag, 2.5 * lw);
}

function tracePen(ctx, P) {
  ctx.beginPath();
  ctx.moveTo(P[0][0], P[0][1]);
  if (P.length < 3) {
    ctx.lineTo(P[P.length - 1][0], P[P.length - 1][1]);
    return;
  }
  for (let i = 1; i < P.length - 1; i++) {
    const mx = (P[i][0] + P[i + 1][0]) / 2;
    const my = (P[i][1] + P[i + 1][1]) / 2;
    ctx.quadraticCurveTo(P[i][0], P[i][1], mx, my);
  }
  const L = P[P.length - 1];
  ctx.lineTo(L[0], L[1]);
}

function outlineRgba(color) {
  return color === "white" || color === "yellow" ? "rgba(0,0,0,0.749)" : "rgba(255,255,255,0.851)";
}

/** One mark, in picture pixels (W x H is the picture's real size). */
export function drawMark(ctx, m, W, H) {
  const lw = linePx(m.w, Math.max(W, H));
  const P = m.pts.map(([x, y]) => [x * W, y * H]);
  const col = rgbOf(m.color);
  ctx.save();
  ctx.strokeStyle = col;
  ctx.fillStyle = col;
  ctx.lineWidth = lw;
  if (m.type === "box") {
    const [a, b] = P;
    ctx.lineJoin = "miter";
    ctx.strokeRect(Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.abs(b[0] - a[0]), Math.abs(b[1] - a[1]));
  } else if (m.type === "ellipse") {
    const [a, b] = P;
    ctx.beginPath();
    ctx.ellipse((a[0] + b[0]) / 2, (a[1] + b[1]) / 2,
      Math.max(0.5, Math.abs(b[0] - a[0]) / 2), Math.max(0.5, Math.abs(b[1] - a[1]) / 2), 0, 0, Math.PI * 2);
    ctx.stroke();
  } else if (m.type === "pen") {
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    tracePen(ctx, P);
    ctx.stroke();
  } else if (m.type === "arrow") {
    const { base, head } = arrowGeometry(P[0], P[1], lw);
    ctx.lineCap = "round";
    ctx.beginPath();
    ctx.moveTo(P[0][0], P[0][1]);
    ctx.lineTo(base[0], base[1]);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(head[0][0], head[0][1]);
    ctx.lineTo(head[1][0], head[1][1]);
    ctx.lineTo(head[2][0], head[2][1]);
    ctx.closePath();
    ctx.fill();
  } else if (m.type === "text") {
    const size = textSizePx(lw);
    const sw = textOutlinePx(size);
    ctx.font = `700 ${size}px "${FONT_FAMILY}", "Inter", "Segoe UI", sans-serif`;
    ctx.textAlign = "left";
    ctx.textBaseline = "alphabetic";
    const x = P[0][0];
    const y = P[0][1] + size * TEXT_BASELINE;
    ctx.lineJoin = "round";
    ctx.lineWidth = sw * 2;          // a canvas stroke is centred: 2x reaches sw outside
    ctx.strokeStyle = outlineRgba(m.color);
    ctx.strokeText(m.text, x, y);
    ctx.fillText(m.text, x, y);
  }
  ctx.restore();
}

/** Where a mark's number badge sits, in picture fractions. */
export function badgeAnchor(m) {
  const [a, b] = m.pts;
  if (m.type === "box") return [Math.min(a[0], b[0]), Math.min(a[1], b[1])];
  if (m.type === "ellipse") {
    // ON the oval, upper left: the corner of its bounding box floats off it.
    const rx = Math.abs(b[0] - a[0]) / 2;
    const ry = Math.abs(b[1] - a[1]) / 2;
    return [(a[0] + b[0]) / 2 - rx * Math.SQRT1_2, (a[1] + b[1]) / 2 - ry * Math.SQRT1_2];
  }
  return m.pts[0];
}

/**
 * The whole picture area: fitted picture, the marks, the number badges.
 * Everything is in CSS pixels of the box; `scale` is the backing-store factor.
 * Returns the picture's rectangle in the box, which pointer input maps through.
 */
export function renderStage(canvas, cssW, cssH, scale, pic, marks, opts = {}) {
  const bw = Math.max(1, Math.round(cssW * scale));
  const bh = Math.max(1, Math.round(cssH * scale));
  if (canvas.width !== bw || canvas.height !== bh) { canvas.width = bw; canvas.height = bh; }
  const ctx = canvas.getContext("2d");
  ctx.setTransform(scale, 0, 0, scale, 0, 0);
  ctx.clearRect(0, 0, cssW, cssH);
  if (!pic || !pic.ok) return null;

  const rect = fitRect(pic.w, pic.h, cssW, cssH);
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(pic.img, rect.x, rect.y, rect.w, rect.h);

  const W = pic.realW || pic.w;
  const H = pic.realH || pic.h;
  const k = rect.w / W;
  ctx.save();
  ctx.beginPath();
  ctx.rect(rect.x, rect.y, rect.w, rect.h);
  ctx.clip();                                  // a mark never paints past the picture
  ctx.translate(rect.x, rect.y);
  ctx.scale(k, k);
  marks.forEach((m, i) => {
    if (i === opts.hover) {
      ctx.save();
      ctx.shadowColor = "rgba(255,255,255,0.95)";
      ctx.shadowBlur = 10 * scale;
      drawMark(ctx, m, W, H);
      ctx.restore();
    }
    drawMark(ctx, m, W, H);
  });
  if (opts.draft) drawMark(ctx, opts.draft, W, H);
  ctx.restore();

  if (opts.badges !== false) {
    const r = opts.badgeR || 9;
    marks.forEach((m, i) => {
      const [bx, by] = badgeAnchor(m);
      let ax = rect.x + bx * rect.w;
      let ay = rect.y + by * rect.h;
      if (m.type === "text") {
        // The click is where the word STARTS, so a badge centred there covers
        // its first letter: sit just left of the word, or above it at the edge.
        if (ax - 2 * r - 3 >= rect.x) ax -= r + 3;
        else ay -= (textSizePx(linePx(m.w, Math.max(W, H))) * k) / 2 + r + 2;
      }
      const x = Math.min(rect.x + rect.w - r, Math.max(rect.x + r, ax));
      const y = Math.min(rect.y + rect.h - r, Math.max(rect.y + r, ay));
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fillStyle = rgbOf(m.color);
      ctx.fill();
      ctx.lineWidth = 1.5;
      ctx.strokeStyle = "rgba(0,0,0,0.55)";
      ctx.stroke();
      const c = COLORS[m.color] || COLORS.red;
      const light = c[0] * 0.299 + c[1] * 0.587 + c[2] * 0.114 > 170;
      ctx.fillStyle = light ? "#111" : "#fff";
      ctx.font = `700 ${Math.round(r * 1.15)}px "Segoe UI", system-ui, sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(String(i + 1), x, y + 0.5);
    });
  }
  return rect;
}
