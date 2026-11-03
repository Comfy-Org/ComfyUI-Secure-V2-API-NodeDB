// Layout Boxes Pixaroma - drawing the canvas and its boxes.
//
// One renderer for the node face and the big view. The canvas (the picture's
// shape) is fitted inside the area with a small margin, so the resize handles of
// a box on the edge stay grabbable. Boxes are drawn from first to last, so a
// later box sits on top, the same order the prompt lists them in.

import { colorOf, inkOn, rgbaOf } from "./core.mjs";

export const HANDLE = 7;            // handle square, CSS px
const MARGIN = 6;                   // area edge to canvas edge, CSS px

/** The canvas box inside the area (object-fit: contain, centred). */
export function fitRect(aspect, cw, ch) {
  const aw = cw - 2 * MARGIN;
  const ah = ch - 2 * MARGIN;
  if (!(aspect > 0 && aw > 0 && ah > 0)) return { x: 0, y: 0, w: 0, h: 0 };
  let w = aw;
  let h = aw / aspect;
  if (h > ah) { h = ah; w = ah * aspect; }
  return { x: (cw - w) / 2, y: (ch - h) / 2, w, h };
}

/** A box (fractions) in area CSS px. */
export function boxPx(b, rect) {
  const x0 = rect.x + Math.min(b.x, b.x + b.w) * rect.w;
  const y0 = rect.y + Math.min(b.y, b.y + b.h) * rect.h;
  return { x: x0, y: y0, w: Math.abs(b.w) * rect.w, h: Math.abs(b.h) * rect.h };
}

/** The eight handles of a box, as [id, cx, cy]. */
export function handlesOf(p) {
  const { x, y, w, h } = p;
  return [
    ["nw", x, y], ["n", x + w / 2, y], ["ne", x + w, y], ["e", x + w, y + h / 2],
    ["se", x + w, y + h], ["s", x + w / 2, y + h], ["sw", x, y + h], ["w", x, y + h / 2],
  ];
}

export const HANDLE_CURSOR = {
  nw: "nwse-resize", se: "nwse-resize", ne: "nesw-resize", sw: "nesw-resize",
  n: "ns-resize", s: "ns-resize", e: "ew-resize", w: "ew-resize",
};

// The last line of a label that does not fit ends with "…", cut to the width:
// a lone first word ("a") on a small box said nothing. Runs on EVERY paint
// (each pointermove of a drag, each keystroke), so it measures at most about a
// dozen times: a binary search, never past what one line can hold (no glyph
// at 11-13 px is narrower than 3 px). Trimming one character per measure cost
// 106 ms a paint with six 2000-character descriptions (measured).
function ellipsize(ctx, text, maxW) {
  const cap = Math.min(text.length, Math.ceil(maxW / 3) + 2);
  if (text.length <= cap && ctx.measureText(text).width <= maxW) return text;
  let lo = 1;
  let hi = cap;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (ctx.measureText(text.slice(0, mid) + "…").width <= maxW) lo = mid;
    else hi = mid - 1;
  }
  return text.slice(0, lo).trimEnd() + "…";
}

function wrapLines(ctx, text, maxW, maxLines) {
  if (maxLines <= 0) return [];
  const words = text.split(/\s+/).filter(Boolean);
  const lines = [];
  let line = "";
  for (let i = 0; i < words.length; i++) {
    const test = line ? line + " " + words[i] : words[i];
    if (line && ctx.measureText(test).width > maxW) {
      if (lines.length === maxLines - 1) return [...lines, ellipsize(ctx, words.slice(i - line.split(" ").length).join(" "), maxW)];
      lines.push(line);
      line = words[i];
    } else {
      line = test;
    }
  }
  if (line) lines.push(lines.length === maxLines - 1 ? ellipsize(ctx, line, maxW) : line);
  return lines;
}

/** What the canvas writes inside a box: the words of a text box, then the description. */
export function labelOf(b) {
  const words = b.type === "text" && b.text.trim() ? `"${b.text.trim()}"  ` : "";
  return words + (b.desc || "").trim();
}

/**
 * Paint the area. `view`:
 *   aspect   canvas width / height
 *   pic      a loaded picture ({img, ok}) or null
 *   boxes    the saved boxes
 *   sel, hover  indices or -1
 *   draft    { index, rect } while a box is drawn (index -1) or dragged
 *   big      true in the big view (bigger badges and text)
 * Returns the canvas box in CSS px (for the pointer maths).
 */
export function renderStage(canvas, cssW, cssH, scale, view) {
  const pw = Math.max(1, Math.round(cssW * scale));
  const ph = Math.max(1, Math.round(cssH * scale));
  if (canvas.width !== pw) canvas.width = pw;
  if (canvas.height !== ph) canvas.height = ph;
  const ctx = canvas.getContext("2d");
  ctx.setTransform(scale, 0, 0, scale, 0, 0);
  ctx.clearRect(0, 0, cssW, cssH);

  const rect = fitRect(view.aspect, cssW, cssH);
  if (!rect.w || !rect.h) return rect;

  // the canvas: the picture, or a plain dark field with rule-of-thirds guides
  if (view.pic?.ok) {
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(view.pic.img, rect.x, rect.y, rect.w, rect.h);
    ctx.fillStyle = "rgba(0,0,0,0.18)";
    ctx.fillRect(rect.x, rect.y, rect.w, rect.h);
  } else {
    ctx.fillStyle = "#2a2a2a";
    ctx.fillRect(rect.x, rect.y, rect.w, rect.h);
    ctx.strokeStyle = "rgba(255,255,255,0.07)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (const f of [1 / 3, 2 / 3]) {
      const gx = Math.round(rect.x + rect.w * f) + 0.5;
      const gy = Math.round(rect.y + rect.h * f) + 0.5;
      ctx.moveTo(gx, rect.y); ctx.lineTo(gx, rect.y + rect.h);
      ctx.moveTo(rect.x, gy); ctx.lineTo(rect.x + rect.w, gy);
    }
    ctx.stroke();
  }
  ctx.strokeStyle = "rgba(255,255,255,0.22)";
  ctx.lineWidth = 1;
  ctx.strokeRect(Math.round(rect.x) + 0.5, Math.round(rect.y) + 0.5, Math.round(rect.w) - 1, Math.round(rect.h) - 1);

  const big = !!view.big;
  const badgeR = big ? 12 : 9;
  const font = big ? 13 : 11;
  const boxes = view.boxes.map((b) => ({ ...b }));
  const d = view.draft;
  if (d && d.index >= 0 && boxes[d.index]) Object.assign(boxes[d.index], d.rect);

  ctx.save();
  ctx.beginPath();
  ctx.rect(rect.x, rect.y, rect.w, rect.h);
  ctx.clip();
  boxes.forEach((b, i) => {
    const p = boxPx(b, rect);
    const hot = i === view.sel || i === view.hover;
    ctx.fillStyle = rgbaOf(i, hot ? 0.26 : 0.16);
    ctx.fillRect(p.x, p.y, p.w, p.h);
    ctx.strokeStyle = rgbaOf(i);
    ctx.lineWidth = i === view.sel ? 2.5 : 2;
    ctx.strokeRect(p.x + 1, p.y + 1, Math.max(0, p.w - 2), Math.max(0, p.h - 2));

    // the label, under the badge, as many lines as fit
    const label = labelOf(b);
    if (label && p.w > badgeR * 4 && p.h > badgeR * 2 + font + 6) {
      ctx.save();
      ctx.beginPath();
      ctx.rect(p.x + 2, p.y + 2, p.w - 4, p.h - 4);
      ctx.clip();
      ctx.font = `600 ${font}px "Segoe UI", system-ui, sans-serif`;
      ctx.textBaseline = "top";
      const lineH = font + 3;
      const top = p.y + badgeR * 2 + 8;
      const maxLines = Math.max(0, Math.floor((p.y + p.h - 4 - top) / lineH));
      const lines = wrapLines(ctx, label, p.w - 12, maxLines);
      ctx.lineWidth = 3;
      ctx.strokeStyle = "rgba(0,0,0,0.7)";
      ctx.fillStyle = "#fff";
      lines.forEach((ln, k) => {
        ctx.strokeText(ln, p.x + 6, top + k * lineH);
        ctx.fillText(ln, p.x + 6, top + k * lineH);
      });
      ctx.restore();
    }

    // the number, which is the N of <obj_N> in the prompt
    const cx = p.x + badgeR + 4;
    const cy = p.y + badgeR + 4;
    ctx.beginPath();
    ctx.arc(cx, cy, badgeR, 0, Math.PI * 2);
    ctx.fillStyle = rgbaOf(i);
    ctx.fill();
    ctx.fillStyle = inkOn(i);
    ctx.font = `700 ${big ? 13 : 11}px "Segoe UI", system-ui, sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(String(i + 1), cx, cy + 0.5);
    ctx.textAlign = "start";
  });

  // the box being drawn
  if (d && d.index < 0 && d.rect) {
    const p = boxPx(d.rect, rect);
    const i = boxes.length;
    ctx.fillStyle = rgbaOf(i, 0.14);
    ctx.fillRect(p.x, p.y, p.w, p.h);
    ctx.setLineDash([6, 4]);
    ctx.strokeStyle = rgbaOf(i);
    ctx.lineWidth = 2;
    ctx.strokeRect(p.x + 1, p.y + 1, Math.max(0, p.w - 2), Math.max(0, p.h - 2));
    ctx.setLineDash([]);
  }
  ctx.restore();

  // the selected box's handles, drawn last so they sit over every other box
  const s = view.sel;
  if (s >= 0 && boxes[s] && !(d && d.index < 0)) {
    const p = boxPx(boxes[s], rect);
    const c = colorOf(s);
    ctx.lineWidth = 1.5;
    for (const [, hx, hy] of handlesOf(p)) {
      ctx.fillStyle = "#fff";
      ctx.fillRect(hx - HANDLE / 2, hy - HANDLE / 2, HANDLE, HANDLE);
      ctx.strokeStyle = `rgb(${c[0]},${c[1]},${c[2]})`;
      ctx.strokeRect(hx - HANDLE / 2, hy - HANDLE / 2, HANDLE, HANDLE);
    }
  }
  return rect;
}
