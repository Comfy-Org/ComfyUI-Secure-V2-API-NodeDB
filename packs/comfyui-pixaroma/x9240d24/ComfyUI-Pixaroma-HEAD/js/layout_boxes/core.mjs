// Layout Boxes Pixaroma - the saved state and the shared constants.
//
// PURE (no imports), so the parity harness can load it in plain node:
// D:\Claude Tests\_layout_boxes\parity.py runs injectedState() here and feeds
// the result through the REAL Python node and core's own nodes.
//
// The boxes live on node.properties.layoutBoxes (an OBJECT, never a JSON
// string) and reach Python through the hidden LayoutState input, injected by
// the graphToPrompt hook in index.js. A box is stored as FRACTIONS of the
// canvas (x, y, w, h from 0 to 1), so changing the width and height keeps every
// box in its place. Coordinates are injected UNROUNDED: core turns them into a
// 0..1000 grid with round(), and rounding them first could move a value across
// a .5 and give a different number than core gives for the same box.
//
// Which box is selected, the hovered row and the undo history are RUNTIME only
// (actions.mjs uiState), so clicking a box can never flag a workflow modified.

export const CLASS = "PixaromaLayoutBoxes";
export const HIDDEN_INPUT = "LayoutState";
export const PROP = "layoutBoxes";

// Same rails as nodes/_layout_boxes_helpers.py.
export const MAX_BOXES = 64;
export const MAX_DESC = 2000;
export const MAX_TEXT = 500;

// Box N takes COLORS[(N - 1) % 8]. MUST match _layout_boxes_helpers.COLORS
// (the preview picture draws them too).
export const COLORS = [
  [255, 72, 72],
  [56, 132, 255],
  [34, 197, 94],
  [168, 85, 247],
  [250, 204, 21],
  [6, 182, 212],
  [236, 72, 153],
  [249, 115, 22],
];

export const colorOf = (i) => COLORS[((i % COLORS.length) + COLORS.length) % COLORS.length];

export function rgbaOf(i, a = 1) {
  const c = colorOf(i);
  return a >= 1 ? `rgb(${c[0]},${c[1]},${c[2]})` : `rgba(${c[0]},${c[1]},${c[2]},${a})`;
}

/** Black or white, whichever reads on box colour i. */
export function inkOn(i) {
  const c = colorOf(i);
  return c[0] * 0.299 + c[1] * 0.587 + c[2] * 0.114 > 150 ? "#111" : "#fff";
}

function num(v) {
  if (typeof v === "boolean" || v === null || v === undefined || v === "") return null;
  const f = Number(v);
  return Number.isFinite(f) ? f : null;
}

function cleanBox(b) {
  if (!b || typeof b !== "object") return null;
  const x = num(b.x);
  const y = num(b.y);
  const w = num(b.w);
  const h = num(b.h);
  if (x == null || y == null || w == null || h == null) return null;
  const type = b.type === "text" ? "text" : "obj";
  return {
    x, y, w, h, type,
    // RAW, as typed: the field must keep a trailing space while you type.
    // Python trims it when the run reads it.
    desc: typeof b.desc === "string" ? b.desc.slice(0, MAX_DESC) : "",
    text: typeof b.text === "string" ? b.text.slice(0, MAX_TEXT) : "",
  };
}

/** A healed COPY of the saved state. Never writes, so it is safe on the load path. */
export function readState(node) {
  let raw = node?.properties?.[PROP];
  if (typeof raw === "string") {
    try { raw = JSON.parse(raw); } catch { raw = null; }
  }
  if (!raw || typeof raw !== "object") raw = {};
  const boxes = [];
  if (Array.isArray(raw.boxes)) {
    for (const b of raw.boxes.slice(0, MAX_BOXES)) {
      const c = cleanBox(b);
      if (c) boxes.push(c);
    }
  }
  return { boxes };
}

/** The ONLY writer. Call it from user actions, never from a load path. A
 *  text box keeps its words even while switched to Object, so switching back
 *  brings them back. */
export function writeState(node, patch) {
  if (!node) return;
  const next = { ...readState(node), ...patch };
  node.properties = node.properties || {};
  node.properties[PROP] = {
    v: 1,
    boxes: next.boxes.slice(0, MAX_BOXES).map((b) => ({
      x: b.x, y: b.y, w: b.w, h: b.h, type: b.type === "text" ? "text" : "obj",
      desc: b.desc || "", text: b.text || "",
    })),
  };
}

/** Exactly what Python receives: the words of a box only while it is a Text box. */
export function injectedState(node) {
  return {
    v: 1,
    boxes: readState(node).boxes.map((b) => {
      const o = { x: b.x, y: b.y, w: b.w, h: b.h, type: b.type, desc: b.desc };
      if (b.type === "text") o.text = b.text;
      return o;
    }),
  };
}

/** A rectangle with positive size, kept inside the canvas. */
export function normRect(r) {
  let x0 = Math.min(r.x, r.x + r.w);
  let x1 = Math.max(r.x, r.x + r.w);
  let y0 = Math.min(r.y, r.y + r.h);
  let y1 = Math.max(r.y, r.y + r.h);
  x0 = Math.min(1, Math.max(0, x0));
  x1 = Math.min(1, Math.max(0, x1));
  y0 = Math.min(1, Math.max(0, y0));
  y1 = Math.min(1, Math.max(0, y1));
  return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
}

/** The tag a prompt cites the box by. */
export const objTag = (i) => `<obj_${i + 1}>`;
