// Layout Boxes Pixaroma - the canvas shape, and the background picture.
//
// THE SHAPE, in this order:
//  1. a background picture that is showing: its own shape (boxes are drawn over
//     the picture an edit model will see),
//  2. width and height: the node's own numbers, or, when they are wired, the
//     number that will arrive - read on the page for Sizes Pixaroma,
//     Resolution Pixaroma and a plain number node, through Reroutes,
//  3. a wired number that can't be read before Run: the size the last run
//     reported, else the node's own number.
// The shape is only for drawing: boxes are stored as fractions of the canvas,
// so a wrong guess shows a stretched canvas, never wrong elements.
//
// THE PICTURE (copied from js/sketch/source.mjs, itself a mirror of Inpaint
// Crop's resolveImageSource - keep them in step): before a run, the upstream
// walk to a Load Image or any node already showing a picture; when the live
// branch can't be known it shows NOTHING. After a run, the copy Python saved of
// the picture that really came in, trusted while the upstream is unchanged.

import { pixApiUrl } from "../shared/api_url.mjs";
// The Sizes Pixaroma mirror lives with Load 3D (pure, harness-checked there:
// D:/Claude Tests/_load3d_size_parity.py). One mirror, never a second copy.
import { sizesNodeOutputs } from "../load_3d/size.mjs";

export const PICTURE_INPUT = "background";
const MAX_SOURCE_HOPS = 12;
const MAX_REROUTE_HOPS = 16;

function inputByName(node, name) {
  return (node?.inputs || []).find((i) => i && i.name === name) || null;
}

function linkById(graph, id) {
  if (id == null || !graph) return null;
  let l = graph.links?.[id];
  if (!l && typeof graph.links?.get === "function") l = graph.links.get(id);
  return l || null;
}

// ── width and height ───────────────────────────────────────────────────────
const isReroute = (n) => n?.type === "Reroute" || n?.comfyClass === "Reroute";

function readWired(up, slot) {
  const cls = String(up.comfyClass || up.type || "");
  if (cls === "PixaromaSizes") {
    const [w, h] = sizesNodeOutputs(up.properties?.sizesState);
    return slot === 0 ? w : slot === 1 ? h : null;
  }
  if (cls === "PixaromaResolution") {
    try {
      const s = JSON.parse(up.properties?.resolutionState);
      const v = slot === 1 ? s.h : slot === 0 ? s.w : null;
      return Number.isFinite(v) ? Math.round(v) : null;
    } catch { return null; }
  }
  // A plain number node: only when it holds exactly ONE number (a node with
  // seed, steps and cfg would be a guess).
  const nums = (up.widgets || []).filter((x) => typeof x.value === "number");
  return nums.length === 1 && Number.isFinite(nums[0].value) ? Math.round(nums[0].value) : null;
}

/** {value, from} for one side: from "own" | "wired" | "unknown". */
function side(node, name) {
  const own = Number((node.widgets || []).find((w) => w.name === name)?.value);
  const ownVal = Number.isFinite(own) && own > 0 ? own : 1024;
  const inp = inputByName(node, name);
  if (!inp || inp.link == null) return { value: ownVal, from: "own" };
  const graph = node.graph;
  let link = linkById(graph, inp.link);
  let up = link ? graph.getNodeById(link.origin_id) : null;
  for (let hop = 0; up && isReroute(up); hop++) {
    if (hop >= MAX_REROUTE_HOPS) return { value: ownVal, from: "unknown" };
    const rin = up.inputs?.[0];
    if (!rin || rin.link == null) return { value: ownVal, from: "own" };
    link = linkById(graph, rin.link);
    up = link ? graph.getNodeById(link.origin_id) : null;
  }
  if (!up || !link) return { value: ownVal, from: "unknown" };
  const v = up.mode === 2 || up.mode === 4 ? null : readWired(up, link.origin_slot);
  return Number.isFinite(v) && v > 0 ? { value: v, from: "wired" } : { value: ownVal, from: "unknown" };
}

/**
 * The canvas shape: { w, h, from } where from is
 *   "picture" | "own" | "wired" | "run" (a wired size read from the last run).
 */
export function canvasDims(node) {
  const pic = node._pixLybPic;
  if (pic?.ok && pic.realW > 0 && pic.realH > 0) return { w: pic.realW, h: pic.realH, from: "picture" };
  const sw = side(node, "width");
  const sh = side(node, "height");
  const run = node._pixLybRunDims;
  if ((sw.from === "unknown" || sh.from === "unknown") && run) {
    return {
      w: sw.from === "unknown" ? run[0] : sw.value,
      h: sh.from === "unknown" ? run[1] : sh.value,
      from: "run",
    };
  }
  const from = sw.from === "wired" || sh.from === "wired" ? "wired"
    : sw.from === "unknown" || sh.from === "unknown" ? "unknown" : "own";
  return { w: sw.value, h: sh.value, from };
}

// ── the background picture ─────────────────────────────────────────────────
const PASSTHROUGH_INPUT = {
  JoinImageWithAlpha: "image",
  SplitImageWithAlpha: "image",
  PixaromaImageInfo: "image_info",
};

function routedInput(node, fromSlot) {
  const cls = node.comfyClass || node.type || "";
  if (cls === "PixaromaSwitch") {
    const idx = node.properties?.switchState?.activeIndex;
    return idx ? inputByName(node, "input_" + idx) : null;
  }
  if (cls === "PixaromaSwitchSource") {
    const bank = node.properties?.switchSourceState?.active === "B" ? "b" : "a";
    return inputByName(node, bank + "_" + ((fromSlot | 0) + 1));
  }
  const named = PASSTHROUGH_INPUT[cls];
  if (named) {
    const hit = inputByName(node, named);
    if (hit) return hit;
  }
  const wired = (node.inputs || []).filter((i) => i.link != null);
  return wired.length === 1 ? wired[0] : null;
}

function parseAnnotatedImageValue(value) {
  let v = String(value || "");
  let type = "input";
  const m = v.match(/\s*\[(input|output|temp)\]\s*$/i);
  if (m) { type = m[1].toLowerCase(); v = v.slice(0, m.index); }
  v = v.replace(/\\/g, "/").trim();
  const i = v.lastIndexOf("/");
  return { filename: i >= 0 ? v.slice(i + 1) : v, subfolder: i >= 0 ? v.slice(0, i) : "", type };
}

function viewUrl(part) {
  return pixApiUrl(`/view?filename=${encodeURIComponent(part.filename)}` +
    `&subfolder=${encodeURIComponent(part.subfolder || "")}` +
    `&type=${encodeURIComponent(part.type || "input")}`);
}

function heldPicture(src, slot) {
  if (!src) return null;
  if (src.comfyClass === "LoadImage" || src.type === "LoadImage") {
    const w = (src.widgets || []).find((x) => x.name === "image");
    if (w && w.value) return { key: "load:" + w.value, url: viewUrl(parseAnnotatedImageValue(w.value)) };
  }
  if (src.imgs && src.imgs.length > 0) {
    const img = src.imgs[slot] || src.imgs[0];
    const url = typeof img === "string" ? img : img?.src;
    if (url) return { key: "imgs:" + url, url };
  }
  return null;
}

/** Walk back to the picture that will arrive on `background`, or null. */
export function upstreamPicture(node) {
  const graph = node?.graph;
  if (!graph) return null;
  let input = inputByName(node, PICTURE_INPUT);
  const seen = new Set();
  for (let hop = 0; hop < MAX_SOURCE_HOPS; hop++) {
    if (!input || input.link == null) return null;
    const link = linkById(graph, input.link);
    const src = link && graph.getNodeById(link.origin_id);
    if (!src || seen.has(src.id)) return null;
    seen.add(src.id);
    const held = heldPicture(src, link.origin_slot);
    if (held) return held;
    input = routedInput(src, link.origin_slot);
  }
  return null;
}

export function pictureWired(node) {
  return inputByName(node, PICTURE_INPUT)?.link != null;
}

/** The picture entry a run sent back -> a picture source. */
export function runSource(entry, forKey) {
  if (!entry || typeof entry !== "object" || !entry.filename) return null;
  const url = pixApiUrl(`/view?filename=${encodeURIComponent(entry.filename)}` +
    `&subfolder=${encodeURIComponent(entry.subfolder || "")}&type=${encodeURIComponent(entry.type || "temp")}`);
  return {
    key: "run:" + entry.filename,
    url,
    kind: "run",
    realW: Number(entry.width) || 0,
    realH: Number(entry.height) || 0,
    forKey: forKey ?? null,
  };
}

/** Load a picture into the node unless it is already the one showing.
 *  `onReady` runs after it loads OR fails, so the face repaints either way. */
export function loadPicture(node, src, onReady) {
  if (!src) {
    if (node._pixLybPic) { node._pixLybPic = null; onReady?.(); }
    return;
  }
  if (node._pixLybPic?.key === src.key) return;
  const img = new Image();
  img.decoding = "async";
  const pic = {
    key: src.key, url: src.url, kind: src.kind || "upstream", img,
    realW: src.realW || 0, realH: src.realH || 0, ok: false, failed: false,
  };
  node._pixLybPic = pic;
  img.onload = () => {
    if (node._pixLybPic !== pic) return;
    if (!pic.realW || !pic.realH) { pic.realW = img.naturalWidth; pic.realH = img.naturalHeight; }
    pic.ok = true;
    onReady?.();
  };
  img.onerror = () => {
    if (node._pixLybPic !== pic) return;
    pic.failed = true;
    onReady?.();
  };
  img.src = src.url;
}
