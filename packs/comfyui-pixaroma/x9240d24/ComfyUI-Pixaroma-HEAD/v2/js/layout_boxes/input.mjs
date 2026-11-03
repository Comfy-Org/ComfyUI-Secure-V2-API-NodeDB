// Layout Boxes Pixaroma - drawing, moving and resizing boxes with the mouse.
//
// Shared by the node face and the big view: each passes its own area and a
// getRect() that says where the canvas sits inside it.
//
//   drag on an empty spot      draws a new box
//   drag a box                 moves it (it stays inside the canvas)
//   drag a handle              resizes the selected box (the 8 squares)
//   click a box                selects it and puts the caret in its row
//
// The drag follows convention #20 to the letter: pointer capture on the area
// AND "no button held -> finish", because a lost release otherwise leaves a box
// glued to the cursor. Nothing is saved until the release: one drag is ONE
// change and one Undo step.

import { readState } from "./core.mjs";
import { HANDLE, HANDLE_CURSOR, boxPx, handlesOf } from "./draw.mjs";
import { addBox, refresh, select, setRect, uiState } from "./actions.mjs";

const MIN_BOX_PX = 6;          // smaller than this on screen is a click, not a box
const DEAD_PX = 3;             // a press on a box moves it only after this much travel
const GRAB = HANDLE / 2 + 3;   // how close to a handle counts as on it, CSS px

const clamp01 = (v) => Math.min(1, Math.max(0, v));

/** What is under the pointer: a handle of the selected box, a box (topmost
 *  first), or nothing. `px` in area CSS px. */
function hitTest(node, rect, px) {
  const boxes = readState(node).boxes;
  const sel = uiState(node).sel;
  if (sel >= 0 && boxes[sel]) {
    for (const [id, hx, hy] of handlesOf(boxPx(boxes[sel], rect))) {
      if (Math.abs(px[0] - hx) <= GRAB && Math.abs(px[1] - hy) <= GRAB) return { kind: "handle", index: sel, handle: id };
    }
  }
  for (let i = boxes.length - 1; i >= 0; i--) {
    const p = boxPx(boxes[i], rect);
    if (px[0] >= p.x && px[0] <= p.x + p.w && px[1] >= p.y && px[1] <= p.y + p.h) return { kind: "box", index: i };
  }
  return { kind: "none" };
}

/**
 * getRect() -> the canvas box in the area's CSS px, or null when nothing is laid out.
 * onDraft(draft|null) repaints with the box being drawn or dragged.
 * onPick(index, isNew) runs after a box was drawn (isNew) or clicked, on THIS surface.
 */
export function attachBoxes(node, area, getRect, onDraft, onPick) {
  let drag = null;   // { mode, index, handle, start, startRect, rect, pointerId }

  // Pointer -> area CSS px. getBoundingClientRect is in SCREEN pixels (the
  // graph zoom scales the node body); the canvas box is in the area's layout
  // pixels, so convert through the area's own ratio.
  const toArea = (e) => {
    const r = area.getBoundingClientRect();
    const k = r.width > 0 ? area.clientWidth / r.width : 1;
    return [(e.clientX - r.left) * k, (e.clientY - r.top) * k];
  };
  const toCanvas = (px, rect) => [(px[0] - rect.x) / rect.w, (px[1] - rect.y) / rect.h];

  const finish = (keep) => {
    if (!drag) return;
    const d = drag;
    drag = null;
    if (d.pointerId != null) { try { area.releasePointerCapture(d.pointerId); } catch {} }
    onDraft(null);
    if (!keep) return;
    const rect = getRect();
    if (d.mode === "draw") {
      if (!rect || !d.rect) return;
      if (d.rect.w * rect.w < MIN_BOX_PX || d.rect.h * rect.h < MIN_BOX_PX) return;   // a click on empty canvas
      const i = addBox(node, d.rect);
      if (i >= 0) onPick?.(i, true);
      return;
    }
    if (d.moved) setRect(node, d.index, d.rect);
    else onPick?.(d.index, false);
  };

  area.addEventListener("pointerdown", (e) => {
    if (e.button !== 0 || drag) return;
    const rect = getRect();
    if (!rect || !rect.w || !rect.h) return;
    e.stopPropagation();
    e.preventDefault();
    const px = toArea(e);
    const p = toCanvas(px, rect);
    const hit = hitTest(node, rect, px);
    if (hit.kind === "none" && (p[0] < 0 || p[0] > 1 || p[1] < 0 || p[1] > 1)) {
      select(node, -1);                                       // the margin around the canvas
      return;
    }
    try { area.setPointerCapture(e.pointerId); } catch {}
    if (hit.kind === "none") {
      select(node, -1);
      drag = { mode: "draw", index: -1, start: p, rect: { x: p[0], y: p[1], w: 0, h: 0 }, pointerId: e.pointerId };
    } else {
      const b = readState(node).boxes[hit.index];
      select(node, hit.index);
      drag = {
        mode: hit.kind === "handle" ? "resize" : "move",
        index: hit.index, handle: hit.handle, start: p, startPx: px,
        startRect: { x: b.x, y: b.y, w: b.w, h: b.h }, rect: { x: b.x, y: b.y, w: b.w, h: b.h },
        moved: false, pointerId: e.pointerId,
      };
    }
    onDraft({ index: drag.index, rect: drag.rect });
  });

  area.addEventListener("pointermove", (e) => {
    const rect = getRect();
    if (!drag) {
      // hover: the cursor says what a press would do
      if (!rect || !rect.w) return;
      const hit = hitTest(node, rect, toArea(e));
      area.style.cursor = hit.kind === "handle" ? HANDLE_CURSOR[hit.handle] : hit.kind === "box" ? "move" : "crosshair";
      const ui = uiState(node);
      const hv = hit.kind === "none" ? -1 : hit.index;
      if (ui.hover !== hv) { ui.hover = hv; refresh(node, false); }
      return;
    }
    if (e.pointerId !== drag.pointerId) return;
    if (!(e.buttons & 1)) { finish(true); return; }
    if (!rect || !rect.w) return;
    const px = toArea(e);
    // A press on a box is a CLICK until the pointer travels DEAD_PX: a tap with
    // a pixel of jitter used to nudge the box, add an Undo step and skip the
    // caret jump to its row (reproduced: x 0.4 -> 0.4031 on a 1 px wobble).
    if (drag.mode !== "draw" && !drag.moved) {
      if (Math.hypot(px[0] - drag.startPx[0], px[1] - drag.startPx[1]) < DEAD_PX) return;
      drag.moved = true;
    }
    const p = toCanvas(px, rect);
    const s = drag.startRect;
    if (drag.mode === "draw") {
      const a = drag.start;
      const bx = clamp01(p[0]);
      const by = clamp01(p[1]);
      drag.rect = { x: Math.min(a[0], bx), y: Math.min(a[1], by), w: Math.abs(bx - a[0]), h: Math.abs(by - a[1]) };
    } else if (drag.mode === "move") {
      const dx = p[0] - drag.start[0];
      const dy = p[1] - drag.start[1];
      drag.rect = {
        x: Math.min(1 - s.w, Math.max(0, s.x + dx)),
        y: Math.min(1 - s.h, Math.max(0, s.y + dy)),
        w: s.w, h: s.h,
      };
    } else {
      let x0 = s.x, y0 = s.y, x1 = s.x + s.w, y1 = s.y + s.h;
      const hd = drag.handle;
      if (hd.includes("w")) x0 = clamp01(p[0]);
      if (hd.includes("e")) x1 = clamp01(p[0]);
      if (hd.includes("n")) y0 = clamp01(p[1]);
      if (hd.includes("s")) y1 = clamp01(p[1]);
      drag.rect = { x: Math.min(x0, x1), y: Math.min(y0, y1), w: Math.abs(x1 - x0), h: Math.abs(y1 - y0) };
    }
    onDraft({ index: drag.index, rect: drag.rect });
  });

  area.addEventListener("pointerleave", () => {
    if (drag) return;
    const ui = uiState(node);
    if (ui.hover !== -1) { ui.hover = -1; refresh(node, false); }
  });
  area.addEventListener("pointerup", (e) => { if (drag && e.pointerId === drag.pointerId) finish(true); });
  area.addEventListener("pointercancel", () => finish(false));
  area.addEventListener("lostpointercapture", () => finish(true));

  return { cancel: () => finish(false), dragging: () => !!drag };
}
