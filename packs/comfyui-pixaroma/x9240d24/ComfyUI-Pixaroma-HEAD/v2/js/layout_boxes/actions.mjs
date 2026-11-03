// Layout Boxes Pixaroma - every change to the boxes goes through here.
//
// Each change (1) writes the saved state, (2) is recorded for Undo / Redo,
// (3) tells ComfyUI's change tracker - a drawn or dragged box ends on
// pointerup, which the pack-wide change net never sees, so without
// notifyGraphChanged() the workflow would not look modified (convention #31) -
// and (4) repaints the face and the big view.
//
// Undo stores OPERATIONS, not snapshots of the whole list (sketch.md #3): a
// snapshot taken before "add box 2" would, restored, also wipe a description
// typed on box 1 after it. Operations name a box by its INDEX, which is safe
// because they are undone strictly in reverse order and the only unrecorded
// changes (typing a description or the words) never move a box.

import { notifyGraphChanged } from "../shared/graph_changed.mjs";
import { MAX_BOXES, normRect, readState, writeState } from "./core.mjs";

const HISTORY_CAP = 80;

/** Runtime-only: the selected box, the hovered box, the history. */
export function uiState(node) {
  if (!node._pixLybUi) node._pixLybUi = { sel: -1, hover: -1, undo: [], redo: [] };
  return node._pixLybUi;
}

/** Repaint the face (and the big view when open). `structural` rebuilds the list. */
export function refresh(node, structural) {
  try { node._pixLybRefresh?.(!!structural); } catch (e) { console.warn("[Layout Boxes] repaint failed", e); }
}

const copyBox = (b) => ({ ...b });
const rectOf = (b) => ({ x: b.x, y: b.y, w: b.w, h: b.h });

// Applies `op` to `boxes` in place and returns the operation that UNDOES it.
function apply(op, boxes) {
  switch (op.kind) {
    case "add":
      boxes.push(copyBox(op.box));
      return { kind: "remove", index: boxes.length - 1 };
    case "remove": {
      const [gone] = boxes.splice(op.index, 1);
      return gone ? { kind: "insert", index: op.index, box: copyBox(gone) } : null;
    }
    case "insert": {
      const at = Math.min(op.index, boxes.length);
      boxes.splice(at, 0, copyBox(op.box));
      return { kind: "remove", index: at };
    }
    case "clear":
      return { kind: "restore", boxes: boxes.splice(0, boxes.length).map(copyBox) };
    case "restore":
      boxes.splice(0, boxes.length, ...op.boxes.map(copyBox));
      return { kind: "clear" };
    case "rect": {
      const b = boxes[op.index];
      if (!b) return null;
      const old = rectOf(b);
      Object.assign(b, op.rect);
      return { kind: "rect", index: op.index, rect: old };
    }
    case "type": {
      const b = boxes[op.index];
      if (!b) return null;
      const old = b.type;
      b.type = op.type;
      return { kind: "type", index: op.index, type: old };
    }
    case "order": {
      if (!boxes[op.from] || op.to < 0 || op.to >= boxes.length) return null;
      const [b] = boxes.splice(op.from, 1);
      boxes.splice(op.to, 0, b);
      return { kind: "order", from: op.to, to: op.from };
    }
    default:
      return null;
  }
}

// Where the selection goes after an operation (or its undo) ran.
function selAfter(op, boxes) {
  if (op.kind === "add") return boxes.length - 1;
  if (op.kind === "insert") return Math.min(op.index, boxes.length - 1);
  if (op.kind === "rect" || op.kind === "type") return op.index;
  if (op.kind === "order") return op.to;
  return -1;
}

function run(node, op, { record = true, clearRedo = true } = {}) {
  const boxes = readState(node).boxes.map(copyBox);
  const inverse = apply(op, boxes);
  if (!inverse) return null;
  writeState(node, { boxes });
  const ui = uiState(node);
  if (record) {
    ui.undo.push(inverse);
    if (ui.undo.length > HISTORY_CAP) ui.undo.shift();
  }
  if (clearRedo) ui.redo = [];
  ui.sel = selAfter(op, boxes);
  ui.hover = -1;
  notifyGraphChanged();
  return inverse;
}

/** A new box from a rectangle of fractions. Returns its index, or -1. */
export function addBox(node, rect) {
  if (readState(node).boxes.length >= MAX_BOXES) return -1;
  const r = normRect(rect);
  if (!run(node, { kind: "add", box: { ...r, type: "obj", desc: "", text: "" } })) return -1;
  refresh(node, true);
  return uiState(node).sel;
}

export function deleteBox(node, index) {
  if (run(node, { kind: "remove", index })) refresh(node, true);
}

export function clearBoxes(node) {
  if (!readState(node).boxes.length) return;
  if (run(node, { kind: "clear" })) refresh(node, true);
}

/** A box moved or resized (one history entry per drag). */
export function setRect(node, index, rect) {
  const b = readState(node).boxes[index];
  if (!b) return;
  const r = normRect(rect);
  if (r.x === b.x && r.y === b.y && r.w === b.w && r.h === b.h) return;
  if (run(node, { kind: "rect", index, rect: r })) refresh(node, false);
}

export function setType(node, index, type) {
  const b = readState(node).boxes[index];
  if (!b || b.type === type) return;
  if (run(node, { kind: "type", index, type: type === "text" ? "text" : "obj" })) refresh(node, true);
}

/** Move box `from` to position `to` (its number changes, and so does its <obj_N>). */
export function reorderBox(node, from, to) {
  if (from === to) return;
  if (run(node, { kind: "order", from, to })) refresh(node, true);
}

/** The description or the words, as typed. No history entry (it would be one
 *  per keystroke) and no list rebuild, so the field keeps its focus and caret. */
export function setField(node, index, key, value) {
  if (key !== "desc" && key !== "text") return;
  const st = readState(node);
  if (!st.boxes[index]) return;
  st.boxes[index][key] = String(value ?? "");
  writeState(node, { boxes: st.boxes });
  refresh(node, false);
}

export function select(node, index) {
  const ui = uiState(node);
  const n = readState(node).boxes.length;
  const next = index >= 0 && index < n ? index : -1;
  if (ui.sel === next) return;
  ui.sel = next;
  refresh(node, false);
}

export function undo(node) {
  const ui = uiState(node);
  const op = ui.undo.pop();
  if (!op) return false;
  const inverse = run(node, op, { record: false, clearRedo: false });
  if (inverse) ui.redo.push(inverse);
  refresh(node, true);
  return true;
}

export function redo(node) {
  const ui = uiState(node);
  const op = ui.redo.pop();
  if (!op) return false;
  const inverse = run(node, op, { record: false, clearRedo: false });
  if (inverse) ui.undo.push(inverse);
  refresh(node, true);
  return true;
}
