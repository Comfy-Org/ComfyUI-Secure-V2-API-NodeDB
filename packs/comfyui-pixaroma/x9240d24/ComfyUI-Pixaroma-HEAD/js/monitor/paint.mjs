// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  Monitor Pixaroma - the classic renderer's face, painted on the canvas   ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// WHY canvas and not a DOM widget: this node is TITLE-LESS, and a DOM element
// sitting on top of the LiteGraph canvas cannot behave like a node. Made
// click-through it hands its clicks to the BROWSER (you get the back/forward
// context menu, not the node menu), and left clickable it eats the drag. So in
// the classic renderer the face is painted straight onto the node and LiteGraph
// keeps its drag and its right-click for free. This is the Label / Run Timer
// recipe (.claude/patterns/run-timer.md #4c).
//
// The buttons are hit-tested against the SAME rects this file paints, cached on
// a runtime field, which is the Compare / Preview pattern for canvas controls.

import { app } from "../../../scripts/app.js";
import { accentOf } from "../shared/node_settings.mjs";
import { pixAsset } from "../shared/api_url.mjs";
import { M, faceBlocks, barColor, barRows, scalarItems, labelUnitWidth } from "./core.mjs";

// ── the bundled gear, drawn on a canvas ─────────────────────────────────────
// Nodes 2.0 gets this icon for free as a CSS mask (house rule #28, the same one
// Dropdown and LoRA Loader use). A canvas has no masks, so here the SVG is
// loaded once as an image and TINTED into a small cached bitmap per size and
// colour: draw the artwork, then composite "source-in" with the fill, which
// keeps the shape's alpha and replaces its colour.
//
// It loads asynchronously, so the first frames have no bitmap and fall back to
// the button's text label. That is deliberate: an icon that has not arrived must
// never leave an empty button. The load is same-origin (our own asset route), so
// drawing it does not taint the canvas.
const GEAR_SRC = pixAsset("icons/note/gear.svg");
let _gearImg = null;
let _gearState = "idle"; // idle | loading | ready | failed
const _gearCache = new Map();

function ensureGear() {
  if (_gearState !== "idle") return;
  _gearState = "loading";
  try {
    const img = new Image();
    img.onload = () => {
      _gearImg = img;
      _gearState = "ready";
      // repaint now rather than waiting up to a second for the next sample
      try {
        app.canvas?.setDirty?.(true, true);
      } catch (_e) {}
    };
    img.onerror = () => {
      _gearState = "failed";
    };
    img.src = GEAR_SRC;
  } catch (_e) {
    _gearState = "failed";
  }
}

// ⚠️ RASTERISE AT THE DEVICE SCALE, NOT IN NODE PIXELS ("the gear is blurred",
// reported 2026-08-24). The node canvas carries a transform of canvas-zoom x
// devicePixelRatio, so a bitmap made at its node-space size gets MAGNIFIED by
// that transform on screen - a 20px gear stretched to 70px at high zoom is
// visibly soft, while the text beside it stays sharp because text is drawn
// vectorially under the same transform every frame. Same family as
// canvasBackingScale in shared/nodes2.mjs: back a raster by the effective
// on-screen pixels, then draw it DOWN at the logical size so the transform
// lands it 1:1. Quantised to quarter steps so a smooth zoom does not mint a
// bitmap per frame, capped so the cache stays tiny.
function deviceScale() {
  let zoom = 1;
  try {
    zoom = app.canvas?.ds?.scale || 1;
  } catch (_e) {}
  const dpr = (typeof window !== "undefined" && window.devicePixelRatio) || 1;
  return Math.min(6, Math.max(1, Math.ceil(zoom * dpr * 4) / 4));
}

function gearBitmap(px, color, eff) {
  ensureGear();
  if (_gearState !== "ready" || !_gearImg) return null;
  const raster = Math.max(6, Math.round(px * (eff || 1)));
  const key = raster + "|" + color;
  const hit = _gearCache.get(key);
  if (hit) return hit;
  try {
    const cv = document.createElement("canvas");
    cv.width = raster;
    cv.height = raster;
    const c = cv.getContext("2d");
    // drawImage renders the SVG vectorially at the DESTINATION size, so the
    // raster is sharp at exactly this many pixels - the blur only ever comes
    // from scaling the finished bitmap afterwards.
    c.drawImage(_gearImg, 0, 0, raster, raster);
    c.globalCompositeOperation = "source-in";
    c.fillStyle = color;
    c.fillRect(0, 0, raster, raster);
    // Keep the cache small: two colours (idle and hover) across a handful of
    // sizes is all a face ever asks for, but a slider drag or a zoom can walk
    // through many.
    if (_gearCache.size > 24) _gearCache.clear();
    _gearCache.set(key, cv);
    return cv;
  } catch (_e) {
    _gearState = "failed";
    return null;
  }
}

function rr(ctx, x, y, w, h, r) {
  const rad = Math.max(0, Math.min(r, w / 2, h / 2));
  ctx.beginPath();
  if (typeof ctx.roundRect === "function") {
    ctx.roundRect(x, y, w, h, rad);
    return;
  }
  ctx.moveTo(x + rad, y);
  ctx.arcTo(x + w, y, x + w, y + h, rad);
  ctx.arcTo(x + w, y + h, x, y + h, rad);
  ctx.arcTo(x, y + h, x, y, rad);
  ctx.arcTo(x, y, x + w, y, rad);
  ctx.closePath();
}

// Centre text on its ACTUAL glyph box. A digits-only string sits visibly high
// with textBaseline "middle", because that baseline is computed from the font's
// full em box including descenders no digit has (the same trap Run Timer's
// fillTextVC exists for). Called once per whole string, NEVER per character.
function textVC(ctx, text, x, yMid, align) {
  ctx.textAlign = align || "left";
  const m = ctx.measureText(text);
  if (m && m.actualBoundingBoxAscent != null && m.actualBoundingBoxDescent != null) {
    ctx.textBaseline = "alphabetic";
    ctx.fillText(text, x, yMid + (m.actualBoundingBoxAscent - m.actualBoundingBoxDescent) / 2);
  } else {
    ctx.textBaseline = "middle";
    ctx.fillText(text, x, yMid);
  }
}

const MONO = 'ui-monospace, "Cascadia Mono", Consolas, monospace';

export function paintFace(node, ctx, st, sample, peak) {
  const s = node._pmScale || 1;
  const W = node.size[0];
  const H = node.size[1];
  const acc = accentOf(node);
  const blocks = faceBlocks(node, st, sample, peak);

  // ⚠️ CLIP TO THE NODE. A canvas painter has no overflow rule, so a line that
  // is wider than the node simply keeps drawing over the graph behind it - which
  // is what a narrow, tall node did: the temp / power / peak strip ran straight
  // out past the right edge and over the canvas. The DOM face has always clipped
  // (overflow:hidden on the screen), so without this the two faces disagree
  // about what happens when something does not fit.
  ctx.save();
  ctx.beginPath();
  ctx.rect(0, 0, W, H);
  ctx.clip();
  try {
    paintBlocks(node, ctx, st, sample, peak, blocks, s, W, H, acc);
  } finally {
    ctx.restore();
  }
}

function paintBlocks(node, ctx, st, sample, peak, blocks, s, W, H, acc) {

  // The node BODY is already painted as the dark screen by the drawNode wrap in
  // index.js (matching bgcolor + radius + no shadow), so there is no panel to
  // draw here - only the contents.
  const x0 = M.padX * s;
  const x1 = W - M.padX * s;
  const avail = x1 - x0;
  const rects = [];
  // the label column fits the longest enabled label (core.mjs labelUnitWidth)
  const lwPx = labelUnitWidth(blocks.filter((b) => b.kind === "bar").map((b) => b.row)) * s;

  let y = M.padY * s;
  blocks.forEach((b, i) => {
    if (i) y += M.gap * s;
    const h = b.h * s;
    if (y + h > H - M.padY * s + 0.5) {
      // Out of room: stop rather than spilling past the frame. Only reachable
      // for a frame or two while a row is being switched on, since the node is
      // resized to fit right after.
      y += h;
      return;
    }
    switch (b.kind) {
      case "title": paintTitle(ctx, node, b, x0, x1, y, h, s, acc); break;
      case "bar": paintBar(ctx, b.row, st, peak, x0, avail, y, h, s, acc, lwPx); break;
      case "strip": paintStrip(ctx, b.items, x0, x1, y, h, s); break;
      case "strip1": paintStrip1(ctx, node, st, sample, peak, x0, avail, y, h, s, acc); break;
      case "buttons": paintButtons(ctx, node, b.items, x0, avail, y, h, s, acc, rects); break;
      default: break;
    }
    y += h;
  });

  node._pmBtnRects = rects;
}

function paintTitle(ctx, node, b, x0, x1, y, h, s, acc) {
  const mid = y + h / 2;
  const r = 2.5 * s;
  ctx.fillStyle = node._pmRunning ? acc : (node._pmOffline ? "#5a5a60" : "#3ec371");
  ctx.beginPath();
  ctx.arc(x0 + r, mid, r, 0, Math.PI * 2);
  ctx.fill();
  ctx.font = `${Math.round(M.titleFont * s)}px ${MONO}`;
  ctx.fillStyle = "#6b6b72";
  const text = (b.text || (node._pmOffline ? "Connecting" : "System")).toUpperCase();
  textVC(ctx, fit(ctx, text, x1 - (x0 + r * 2 + 5 * s)), x0 + r * 2 + 5 * s, mid, "left");
}

// A track this short says nothing, so below it the bar is dropped rather than
// squeezed. In scale-1 pixels.
const MIN_TRACK = 18;

function paintBar(ctx, row, st, peak, x0, avail, y, h, s, acc, lwPx) {
  const mid = y + h / 2;
  const g = 7 * s;
  let lw = lwPx != null ? lwPx : M.labelW * s;
  let vw = M.valueW * s;
  // WHAT GOES FIRST WHEN THERE IS NOT ENOUGH ROOM: the BAR, then the LABEL, and
  // the NUMBER survives to the end.
  //
  // The order matters and the first version had it wrong: it dropped the label
  // before the bar, so a node dragged narrow showed a column of bare numbers
  // with nothing to say which was VRAM and which was RAM - reported with a
  // screenshot. The bar is the decoration; the label is what makes the number
  // mean anything. This is also the order the DOM face has always used (the
  // track is `flex:1 1 0` so it gives way first, the label `flex:0 1 auto`
  // second, the value `flex:0 0 auto` never), and the two must agree.
  let tw = avail - lw - vw - g * 2;
  if (tw < MIN_TRACK * s) { tw = 0; }                        // drop the bar first
  if (lw + vw + g > avail) { lw = 0; }                       // then the label

  let x = x0;
  ctx.font = `${Math.round(M.font * s)}px ${MONO}`;
  if (lw > 0) {
    ctx.fillStyle = "#8a8a8a";
    textVC(ctx, fit(ctx, row.label, lw), x, mid, "left");
    x += lw + g;
  }

  if (tw > 0) {
    const bh = M.barH * s;
    const by = mid - bh / 2;
    ctx.fillStyle = "rgba(255,255,255,0.055)";
    rr(ctx, x, by, tw, bh, M.barR * s);
    ctx.fill();
    if (row.pct != null && row.pct > 0) {
      ctx.fillStyle = barColor(row.pct, acc, st.warn);
      rr(ctx, x, by, Math.max(2 * s, (tw * row.pct) / 100), bh, M.barR * s);
      ctx.fill();
    }
    if (row.key === "vram" && st.show.peak && peak && peak.pct > 0) {
      const pxPos = x + (tw * Math.min(99.4, peak.pct)) / 100;
      ctx.fillStyle = "#ffd9cd";
      ctx.fillRect(pxPos, by - s, Math.max(1, 2 * s), bh + s * 2);
    }
    x += tw;
  }

  if (vw > 0) {
    x += g;
    // The unit is drawn dimmer and a shade smaller, so the NUMBER is what the
    // eye lands on. Right-aligned, so the digits line up down the column.
    const tail = row.tail ?? "";
    const main = row.main ?? "";
    ctx.font = `${Math.round(M.font * s * 0.86)}px ${MONO}`;
    const tailW = ctx.measureText(tail).width;
    ctx.fillStyle = "#6b6b72";
    textVC(ctx, tail, x0 + avail, mid, "right");
    ctx.font = `${Math.round(M.font * s)}px ${MONO}`;
    ctx.fillStyle = "#e0e0e0";
    textVC(ctx, main, x0 + avail - tailW, mid, "right");
  }
}

function paintStrip(ctx, items, x0, x1, y, h, s) {
  const mid = y + h / 2;
  let x = x0;
  for (const it of items) {
    if (x >= x1) return;   // out of room: stop rather than run off the node
    ctx.font = `${Math.round(M.stripFont * s)}px ${MONO}`;
    ctx.fillStyle = "#8a8a8a";
    const lab = it.label + " ";
    textVC(ctx, lab, x, mid, "left");
    x += ctx.measureText(lab).width;
    ctx.fillStyle = it.hot ? "#e8a33d" : "#e0e0e0";
    textVC(ctx, it.text, x, mid, "left");
    x += ctx.measureText(it.text).width + 9 * s;
  }
}

function paintStrip1(ctx, node, st, sample, peak, x0, avail, y, h, s, acc) {
  const mid = y + h / 2;
  const segs = [];
  for (const r of barRows(node, st, sample)) {
    segs.push({
      label: r.label,
      pct: r.pct,
      text: (r.main ?? "") + (r.key === "gpu" || r.key === "cpu" ? "%" : ""),
    });
  }
  for (const it of scalarItems(st, sample, peak)) segs.push({ label: null, text: it.text, hot: it.hot });
  if (!segs.length) {
    ctx.font = `${Math.round(M.font * s)}px ${MONO}`;
    ctx.fillStyle = "#6b6b72";
    textVC(ctx, sample ? "Nothing to show" : "Connecting", x0, mid, "left");
    return;
  }

  ctx.font = `${Math.round(M.font * s)}px ${MONO}`;
  let x = x0;
  const limit = x0 + avail;
  segs.forEach((sg, i) => {
    if (x >= limit) return;
    if (i) {
      ctx.fillStyle = "#3a3a3a";
      textVC(ctx, " · ", x, mid, "left");
      x += ctx.measureText(" · ").width;
    }
    if (sg.label) {
      ctx.fillStyle = "#8a8a8a";
      const lab = sg.label + " ";
      textVC(ctx, lab, x, mid, "left");
      x += ctx.measureText(lab).width;
      if (sg.pct != null) {
        const mw = 30 * s;
        const mh = 5 * s;
        ctx.fillStyle = "rgba(255,255,255,0.06)";
        rr(ctx, x, mid - mh / 2, mw, mh, 2 * s);
        ctx.fill();
        ctx.fillStyle = barColor(sg.pct, acc, st.warn);
        rr(ctx, x, mid - mh / 2, Math.max(2 * s, (mw * sg.pct) / 100), mh, 2 * s);
        ctx.fill();
        x += mw + 5 * s;
      }
    }
    ctx.fillStyle = sg.hot ? "#e8a33d" : "#e0e0e0";
    textVC(ctx, sg.text, x, mid, "left");
    x += ctx.measureText(sg.text).width;
  });
}

function paintButtons(ctx, node, items, x0, avail, y, h, s, acc, rects) {
  const g = 5 * s;
  const n = items.length;
  // A compact button (the gear) is a square at its natural size; the rest share
  // whatever is left, so the wording on the text buttons gets the room.
  const compact = items.filter((b) => b.compact).length;
  const compactW = h;
  const flexN = n - compact;
  const flexW = flexN > 0 ? (avail - g * (n - 1) - compact * compactW) / flexN : 0;
  if (flexN > 0 && flexW < 24 * s) return;  // no room: the panel still has the actions
  const hoverKey = node._pmHoverBtn;
  let x = x0;
  items.forEach((b, i) => {
    const w = b.compact ? compactW : flexW;
    if (i) x += g;
    const hot = hoverKey === b.key;
    rr(ctx, x, y, w, h, 4 * s);
    ctx.fillStyle = hot ? acc : "rgba(255,255,255,0.045)";
    ctx.fill();
    ctx.lineWidth = Math.max(1, s * 0.8);
    ctx.strokeStyle = hot ? acc : "rgba(255,255,255,0.13)";
    ctx.stroke();
    ctx.font = `${Math.round(M.btnFont * s)}px ${MONO}`;
    let fg = hot ? "#ffffff" : "rgba(255,255,255,0.72)";
    const flash = node._pmFlash && node._pmFlash.key === b.key ? node._pmFlash.label : null;
    if (flash) {
      rr(ctx, x, y, w, h, 4 * s);
      ctx.fillStyle = "#3ec371";
      ctx.fill();
      fg = "#ffffff";
    }
    ctx.fillStyle = fg;

    const iconPx = Math.round(14 * s);
    const icon = !flash && b.icon === "gear" ? gearBitmap(iconPx, fg, deviceScale()) : null;
    if (icon) {
      // Draw DOWN to the logical size: the raster is deviceScale() times
      // bigger, and the canvas transform magnifies it back to exactly 1:1
      // screen pixels. Centring uses iconPx, never icon.width - the raster
      // size changes with the zoom.
      ctx.drawImage(icon, Math.round(x + (w - iconPx) / 2), Math.round(y + (h - iconPx) / 2), iconPx, iconPx);
    } else {
      // no icon (yet, or not an icon button): the label, never an empty box
      textVC(ctx, fit(ctx, flash || b.label, w - 8 * s), x + w / 2, y + h / 2, "center");
    }
    rects.push({ key: b.key, x, y, w, h });
    x += w;
  });
}

/** Trim a string with an ellipsis until it fits, so nothing ever overflows. */
function fit(ctx, text, max) {
  let t = String(text ?? "");
  if (max <= 0) return "";
  if (ctx.measureText(t).width <= max) return t;
  while (t.length > 1 && ctx.measureText(t + "…").width > max) t = t.slice(0, -1);
  return t + "…";
}

/** The button under a node-local point, or null. */
export function hitButton(node, lx, ly) {
  for (const r of node._pmBtnRects || []) {
    if (lx >= r.x && lx <= r.x + r.w && ly >= r.y && ly <= r.y + r.h) return r.key;
  }
  return null;
}

/** Node-local cursor position from the canvas, for the free per-frame hover. */
export function localMouse(node) {
  try {
    const gm = node.graph?.list_of_graphcanvas?.[0]?.graph_mouse
      || window.app?.canvas?.graph_mouse;
    if (!gm) return null;
    return [gm[0] - node.pos[0], gm[1] - node.pos[1]];
  } catch (_e) {
    return null;
  }
}
