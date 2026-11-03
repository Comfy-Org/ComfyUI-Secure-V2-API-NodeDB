// Sketch Pixaroma - every change to the marks goes through here.
//
// Why one place: each change must (1) write the saved state, (2) be recorded
// for Undo / Redo, (3) tell ComfyUI's change tracker - a drawn mark ends on
// pointerup, which the pack-wide change net never sees, so without the explicit
// notifyGraphChanged() the workflow would not look modified and a mark could
// be lost on close (convention #31/#32) - and (4) repaint the face and the big
// view.
//
// Undo stores OPERATIONS, not snapshots of the whole list: a snapshot taken
// before "add mark 2" would, when restored, also wipe a note typed on mark 1
// after it. An operation only touches the mark it is about.

import { notifyGraphChanged } from "../shared/graph_changed.mjs";
import { nodeSetting } from "../shared/node_settings.mjs";
import { MAX_MARKS, SETTING_AUTO, nextAutoColor, readState, writeState } from "./core.mjs";

const HISTORY_CAP = 60;

export const autoColor = () => nodeSetting(SETTING_AUTO, true) !== false;

/** Runtime-only picks: tool, colour, line width, the hovered row, history. */
export function uiState(node) {
  if (!node._pixSkUi) {
    const marks = readState(node).marks;
    node._pixSkUi = {
      tool: "box",
      color: autoColor() ? nextAutoColor(marks) : "red",
      width: "M",
      hover: -1,
      undo: [],
      redo: [],
    };
  }
  return node._pixSkUi;
}

/** Repaint the face (and the big view when open). `structural` rebuilds the list. */
export function refresh(node, structural) {
  try { node._pixSkRefresh?.(!!structural); } catch (e) { console.warn("[Sketch] repaint failed", e); }
}

const copyMark = (m) => ({ ...m, pts: m.pts.map((p) => [p[0], p[1]]) });

function apply(node, op, marks) {
  // Returns the operation that UNDOES `op`.
  if (op.kind === "add") {
    marks.push(copyMark(op.mark));
    return { kind: "remove", index: marks.length - 1 };
  }
  if (op.kind === "remove") {
    const [gone] = marks.splice(op.index, 1);
    return gone ? { kind: "insert", index: op.index, mark: copyMark(gone) } : null;
  }
  if (op.kind === "insert") {
    marks.splice(Math.min(op.index, marks.length), 0, copyMark(op.mark));
    return { kind: "remove", index: Math.min(op.index, marks.length - 1) };
  }
  if (op.kind === "clear") {
    const all = marks.splice(0, marks.length).map(copyMark);
    return { kind: "restore", marks: all };
  }
  if (op.kind === "restore") {
    marks.splice(0, marks.length, ...op.marks.map(copyMark));
    return { kind: "clear" };
  }
  return null;
}

function run(node, op, { record = true, clearRedo = true, patch = null } = {}) {
  const st = readState(node);
  const marks = st.marks.map(copyMark);
  const inverse = apply(node, op, marks);
  if (!inverse) return null;
  writeState(node, { marks, ...(patch || {}) });
  const ui = uiState(node);
  if (record) {
    ui.undo.push(inverse);
    if (ui.undo.length > HISTORY_CAP) ui.undo.shift();
  }
  if (clearRedo) ui.redo = [];
  notifyGraphChanged();
  return inverse;
}

// With auto colour on, the next colour follows the LAST mark, so every change
// that alters which mark is last re-picks it: without this, undoing a blue mark
// left the next one green instead of blue again.
function repickColor(node) {
  if (autoColor()) uiState(node).color = nextAutoColor(readState(node).marks);
}

export function commitMark(node, mark, picAspect) {
  if (readState(node).marks.length >= MAX_MARKS) return false;
  const done = run(node, { kind: "add", mark }, { patch: picAspect ? { picAspect } : null });
  if (!done) return false;
  repickColor(node);
  refresh(node, true);
  return true;
}

export function deleteMark(node, index) {
  const ui = uiState(node);
  if (run(node, { kind: "remove", index })) {
    ui.hover = -1;
    repickColor(node);
    refresh(node, true);
  }
}

export function clearMarks(node) {
  if (!readState(node).marks.length) return;
  if (run(node, { kind: "clear" })) {
    uiState(node).hover = -1;
    repickColor(node);
    refresh(node, true);
  }
}

export function undo(node) {
  const ui = uiState(node);
  const op = ui.undo.pop();
  if (!op) return false;
  const inverse = run(node, op, { record: false, clearRedo: false });
  if (inverse) ui.redo.push(inverse);
  ui.hover = -1;
  repickColor(node);
  refresh(node, true);
  return true;
}

export function redo(node) {
  const ui = uiState(node);
  const op = ui.redo.pop();
  if (!op) return false;
  const inverse = run(node, op, { record: false, clearRedo: false });
  if (inverse) ui.undo.push(inverse);
  ui.hover = -1;
  repickColor(node);
  refresh(node, true);
  return true;
}

/** A note as typed. No history entry (it would be one per keystroke) and no
 *  list rebuild, so the box keeps its focus and caret. */
export function setNote(node, index, text) {
  const st = readState(node);
  if (!st.marks[index]) return;
  st.marks[index].note = String(text ?? "");
  writeState(node, { marks: st.marks });
  refresh(node, false);
}

export function setRemoveMarks(node, on) {
  writeState(node, { removeMarks: !!on });
  notifyGraphChanged();
  refresh(node, false);
}
