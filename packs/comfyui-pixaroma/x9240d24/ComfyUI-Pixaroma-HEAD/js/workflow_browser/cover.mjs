// ╔═══════════════════════════════════════════════════════════════╗
// ║  Pixaroma Workflows - what a card shows instead of a filename  ║
// ╚═══════════════════════════════════════════════════════════════╝
//
// Three sources, best first:
//   1. a picture the user chose by hand,
//   2. the last image that workflow actually produced,
//   3. a small map of the graph, drawn from the node positions already in the
//      file.
//
// (3) matters most: it means all 144 workflows have a recognisable cover the
// first time the panel is ever opened, with nothing to generate and nothing to
// go stale. (2) then fills in on its own as the user works.
//
// A picture of the CANVAS is deliberately not attempted - it cannot be captured
// without a screen-share permission prompt, so it is not on the table.

import { api } from "../../../scripts/api.js";
import { pixApiUrl } from "../shared/api_url.mjs";
import { runWorkflow } from "../shared/run_tab.mjs";
import * as A from "./api.mjs";

// ── colour ──────────────────────────────────────────────────────────────────
//
// The map carries each node's REAL colour. Drawing it literally does not work:
// ComfyUI node colours are title tints meant to sit on a dark canvas, so they
// are near-black (#1d1d1d, #342339, #0c2f36) and a cover made of them is an
// unreadable smudge.
//
// So the HUE is kept and the lightness is forced to something legible at 120px.
// An orange node still looks orange and a green group still looks green - the
// cover reflects the actual workflow - but it can be read at thumbnail size.
// The earlier version hashed the colour into a fixed palette, which meant a
// green node could come out brown: it looked arbitrary because it was.

// A GREY has no hue. Asking for one returns 0, which is red - so an earlier
// version that forced a saturation floor onto everything turned every plain
// #1d1d1d node into dusty pink (196,110,110) and the covers came out salmon,
// while the genuinely orange nodes had been fine all along. Anything below this
// much saturation is treated as colourless and only has its lightness lifted.
const ACHROMATIC = 0.06;

const LIFT_L = 0.62;    // target lightness for a node that HAS a colour
const GREY_L = 0.42;    // plain nodes: visible, clearly neutral, not competing
const LIFT_S = 0.45;    // saturation floor, applied only to real hues
const NO_COLOUR = "#57534f";

const _liftCache = new Map();

function lift(hex) {
  // Colours come from workflow files, which are downloaded from the internet.
  // A number or an object here used to throw on .slice.
  if (!hex || typeof hex !== "string") return NO_COLOUR;
  const hit = _liftCache.get(hex);
  if (hit) return hit;

  let h = hex.slice(1);
  if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
  if (h.length !== 6) return NO_COLOUR;
  const r = parseInt(h.slice(0, 2), 16) / 255;
  const g = parseInt(h.slice(2, 4), 16) / 255;
  const b = parseInt(h.slice(4, 6), 16) / 255;

  const mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn;
  let hue = 0, sat = 0;
  const l0 = (mx + mn) / 2;
  if (d) {
    sat = l0 > 0.5 ? d / (2 - mx - mn) : d / (mx + mn);
    hue = mx === r ? ((g - b) / d + (g < b ? 6 : 0))
        : mx === g ? ((b - r) / d + 2)
        : ((r - g) / d + 4);
    hue /= 6;
  }
  // Grey in, grey out. Only a colour that actually has a hue gets saturated up.
  const grey = sat < ACHROMATIC;
  const s = grey ? 0 : Math.max(sat, LIFT_S);
  const l = grey ? GREY_L : LIFT_L;
  const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
  const p = 2 * l - q;
  const ch = (t) => {
    t = (t + 1) % 1;
    if (t < 1 / 6) return p + (q - p) * 6 * t;
    if (t < 0.5) return q;
    if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
    return p;
  };
  const to = (v) => Math.round(v * 255).toString(16).padStart(2, "0");
  const out = "#" + to(ch(hue + 1 / 3)) + to(ch(hue)) + to(ch(hue - 1 / 3));
  // 143 workflows x up to 60 nodes is a lot of conversions per render, and the
  // same handful of colours repeats throughout.
  _liftCache.set(hex, out);
  return out;
}

/** Paint the graph map. Sized to the element's real box at device pixels, or
 *  covers look soft on a high-DPI screen and blocky when the node is zoomed. */
export function drawMap(canvas, map) {
  const w = canvas.clientWidth || 120;
  const h = canvas.clientHeight || 64;
  const dpr = Math.min(window.devicePixelRatio || 1, 3);
  if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
  }
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);

  ctx.fillStyle = "#141414";
  ctx.fillRect(0, 0, w, h);

  if (!Array.isArray(map) || !map.length) {
    // An unreadable or empty workflow still gets something honest to look at
    // rather than a blank hole in the grid.
    ctx.strokeStyle = "#2e2e2e";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(w * 0.3, h * 0.5); ctx.lineTo(w * 0.7, h * 0.5);
    ctx.stroke();
    return;
  }

  // Entries come from an untrusted file. A null or short one used to throw on
  // e[0] inside a requestAnimationFrame, where nothing catches it, and the card
  // was left with a blank cover and a console error.
  const boxes = map.filter((e) => Array.isArray(e) && e.length >= 4
    && Number.isFinite(+e[0]) && Number.isFinite(+e[1])
    && Number.isFinite(+e[2]) && Number.isFinite(+e[3]));
  if (!boxes.length) return;

  // Inset so boxes at the extremes are not clipped flush against the edge.
  const pad = 6;
  const iw = Math.max(1, w - pad * 2);
  const ih = Math.max(1, h - pad * 2);

  // Wires first, so boxes sit on top. Approximated as a line between box
  // centres in reading order: the real link list is not carried in the map, and
  // at 120x64 the impression of a graph is all that reads anyway.
  ctx.strokeStyle = "rgba(120,150,180,.35)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  for (let i = 1; i < boxes.length; i++) {
    const a = boxes[i - 1], b = boxes[i];
    ctx.moveTo(pad + (a[0] + a[2] / 2) * iw, pad + (a[1] + a[3] / 2) * ih);
    ctx.lineTo(pad + (b[0] + b[2] / 2) * iw, pad + (b[1] + b[3] / 2) * ih);
  }
  ctx.stroke();

  for (const e of boxes) {
    const x = pad + e[0] * iw;
    const y = pad + e[1] * ih;
    const bw = Math.max(2, e[2] * iw);
    const bh = Math.max(2, e[3] * ih);
    const col = e[4];
    ctx.fillStyle = lift(col);
    ctx.globalAlpha = col ? 0.95 : 0.5;
    const r = Math.min(2, bw / 2, bh / 2);
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(x, y, bw, bh, r);
    else ctx.rect(x, y, bw, bh);
    ctx.fill();
  }
  ctx.globalAlpha = 1;
}

// A node reports what it wrote through ComfyUI's standard `images` list even
// when the file is not an image: Save Mp4 puts its mp4 there so the clip shows
// up in the output panel and the Assets tab. An <img> can never render that, so
// the card showed the browser's broken-image glyph (the grid hid it behind the
// error fallback, the detail pane did not). Everything here therefore asks what
// the file IS, not merely what list it arrived in.
const PICTURE_EXTS = ["png", "jpg", "jpeg", "webp", "gif", "bmp", "avif"];

/** Can this filename be shown in an <img>? Extension only: the entry's `format`
 *  field is set by the node that wrote it and plenty of nodes omit it. */
export function isPictureName(filename) {
  const name = String(filename || "").split("?")[0];
  const dot = name.lastIndexOf(".");
  if (dot < 0) return false;
  return PICTURE_EXTS.includes(name.slice(dot + 1).toLowerCase());
}

/** Where a card's picture should come from, if anywhere. */
export function coverFor(entry, meta) {
  const hand = meta?.covers?.[entry.rel];
  if (hand && hand.kind === "file" && hand.file) {
    // The version in the query is what lets the picture be cached hard and
    // still update the instant it is replaced - the filename never changes.
    return { kind: "image", url: pixApiUrl(`/pixaroma/api/workflows/cover/${encodeURIComponent(hand.file)}?v=${hand.v || 1}`) };
  }
  // A cover saved by the first version was embedded here as base64. The server
  // moves those out to files when the sidecar is read, but a panel still
  // holding the old copy in memory should show it rather than nothing.
  if (hand && hand.kind === "file" && hand.url) return { kind: "image", url: hand.url };
  // Recorded automatically, so it may name a video from before the capture
  // learned to check. Falling back here heals those in place: no migration, no
  // write, and nothing to explain to anyone who already has them.
  if (hand && hand.kind === "output" && hand.filename && isPictureName(hand.filename)) {
    return { kind: "image", url: outputURL(hand) };
  }
  return { kind: "map" };
}

/** Does this workflow have a picture the user chose by hand? */
export function hasHandCover(entry, meta) {
  const hand = meta?.covers?.[entry.rel];
  return !!(hand && hand.kind === "file" && (hand.file || hand.url));
}

function outputURL(rec) {
  const p = new URLSearchParams({
    filename: rec.filename || "",
    subfolder: rec.subfolder || "",
    type: rec.type || "output",
  });
  // pixApiUrl adds the deployment's own /api prefix, so pass the BARE route.
  return pixApiUrl(`/view?${p.toString()}`);
}

// ── remembering what a workflow produced ────────────────────────────────────
//
// When a run finishes we already know which workflow is open, and the event
// carries the images it wrote. Recording the pair is all it takes for covers to
// appear as somebody works, with no backfill and no scanning of the output
// folder.

let installed = false;
let pending = null;
let flushTimer = null;

export function installOutputCoverCapture() {
  if (installed) return;
  installed = true;

  api.addEventListener("executed", (ev) => {
    try {
      const output = ev?.detail?.output;
      const images = output?.images;
      if (!Array.isArray(images) || !images.length) return;
      const img = images.find((i) => i && i.filename && (i.type || "output") !== "temp"
                                     && isPictureName(i.filename));
      if (!img) return;
      // The workflow that RAN, not the one open now: a run keeps going when you
      // switch tabs, and its picture became the OTHER workflow's cover (VC#30).
      // runWorkflow needs core's own listener to have filed the output first,
      // hence the microtask; when it cannot tell, the one open at the event, as before.
      const openRel = A.activePath();
      queueMicrotask(() => {
        try {
          const owner = runWorkflow(output);
          const rel = owner ? A.fromStorePath(owner.path || "") : openRel;
          if (!rel) return;                  // an unsaved workflow has no file to pin it to
          pending = pending || {};
          pending[rel] = { kind: "output", filename: img.filename, subfolder: img.subfolder || "", type: img.type || "output" };
          // Debounced: a batch fires this once per output node, and each one would
          // otherwise be its own write.
          clearTimeout(flushTimer);
          flushTimer = setTimeout(flush, 1200);
        } catch {
          // Never throw over a cover thumbnail.
        }
      });
    } catch {
      // Never throw inside ComfyUI's event loop over a cover thumbnail.
    }
  });
}

async function flush() {
  const batch = pending;
  pending = null;
  if (!batch) return;
  try { await A.saveMeta({ covers: batch }); } catch { /* a missed cover is not worth a message */ }
}
