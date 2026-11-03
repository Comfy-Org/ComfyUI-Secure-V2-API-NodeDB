// Layout Boxes Pixaroma - the big view, for careful drawing.
//
// A full-screen overlay with a large canvas and the boxes listed on the right
// (with Move up / Move down, which change a box's number). It edits the SAME
// saved boxes as the node, live, so there is no Save step and nothing to lose:
// Done (or Esc, or clicking outside) just closes it.
//
// While it is open, ComfyUI's graph Ctrl+Z is blocked through the ONE shared
// guard (Vue Compat #6 - never hand-roll this), and Ctrl+Z / Ctrl+Y undo and
// redo boxes instead. Keys are stopped at the overlay so ComfyUI's own
// shortcuts (Delete removes the selected NODE) cannot fire behind it; here
// Delete removes the selected box.

import { installGraphUndoGuard } from "../shared/graph_undo_guard.mjs";
import { applyAccent } from "../shared/node_settings.mjs";
import { isComfyTextShortcut } from "../shared/text_shortcuts.mjs";
import { readState } from "./core.mjs";
import { injectCSS } from "./css.mjs";
import { renderStage } from "./draw.mjs";
import { attachBoxes } from "./input.mjs";
import { deleteBox, redo, uiState, undo } from "./actions.mjs";
import { buildActions, buildFooter, buildShapeChip, focusRow, renderList, syncListSelection } from "./controls.mjs";
import { canvasDims } from "./source.mjs";

const el = (tag, cls, text) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
};

export function isBigOpen(node) {
  const b = node?._pixLybBig;
  if (b && !b.ov.isConnected) node._pixLybBig = null;   // torn down without us (Vue Compat #2)
  return !!node?._pixLybBig;
}

export function openBig(node) {
  if (isBigOpen(node)) return;
  injectCSS();
  const ov = el("div", "pix-lyb-big");
  ov.tabIndex = -1;
  applyAccent(ov, node);                   // a body-level overlay does not inherit the node's colour

  const panel = el("div", "pix-lyb-bpanel");
  const head = el("div", "pix-lyb-bhead");
  const done = el("button", "pix-lyb-done", "Done");
  done.type = "button";
  done.title = "Back to the workflow. Your boxes are already saved on the node.";
  const chipHost = el("span");
  head.append(
    el("span", "pix-lyb-btitle", "Layout Boxes Pixaroma"),
    chipHost,
    el("span", "pix-lyb-bhint", "Drag to draw a box, drag a box to move it, drag a corner to resize.  Delete removes the selected box.  Ctrl+Z undo, Ctrl+Y redo, Esc closes."),
    el("span", "pix-lyb-grow"),
    done,
  );
  const syncChip = buildShapeChip(chipHost);

  const main = el("div", "pix-lyb-bmain");
  const rail = el("div", "pix-lyb-brail");
  const center = el("div", "pix-lyb-bcenter");
  const stage = el("div", "pix-lyb-stage");
  const canvas = el("canvas", "pix-lyb-cv");
  canvas.style.cssText = "position:absolute;inset:0;width:100%;height:100%;display:block;";
  stage.appendChild(canvas);
  center.appendChild(stage);
  const side = el("div", "pix-lyb-bside");
  const list = el("div", "pix-lyb-list");
  side.append(el("h4", null, "Boxes and what goes in them"), list);
  buildFooter(side);
  main.append(rail, center, side);
  panel.append(head, main);
  ov.appendChild(panel);

  const syncActions = buildActions(node, rail);

  const big = { ov, stage, canvas, list, rect: null, draft: null };
  node._pixLybBig = big;

  const paint = () => {
    if (!ov.isConnected) return;
    syncChip(node);
    const w = stage.clientWidth;
    const h = stage.clientHeight;
    if (!w || !h) return;
    const d = canvasDims(node);
    const ui = uiState(node);
    big.rect = renderStage(canvas, w, h, window.devicePixelRatio || 1, {
      aspect: d.w / d.h, pic: node._pixLybPic, boxes: readState(node).boxes,
      sel: ui.sel, hover: ui.hover, draft: big.draft, big: true,
    });
  };
  big.refresh = (structural) => {
    if (structural) renderList(node, list, { big: true });
    else syncListSelection(node, list);
    syncActions();
    paint();
  };
  big.paint = paint;

  const ro = new ResizeObserver(paint);
  ro.observe(stage);
  const input = attachBoxes(node, stage, () => big.rect, (d) => { big.draft = d; paint(); }, (i) => focusRow(list, i, side));

  const undoGuardOff = installGraphUndoGuard(() => ov.isConnected);

  const close = () => {
    if (big.closed) return;
    big.closed = true;
    try { input.cancel(); } catch {}
    try { ro.disconnect(); } catch {}
    try { undoGuardOff?.(); } catch {}
    ov.remove();
    if (node._pixLybBig === big) node._pixLybBig = null;
    // REBUILD the node's rows, not just repaint (convention #42, sketch.md
    // #17c): a description typed here updates the saved boxes without
    // rebuilding the face's list, so its fields still hold the OLD text, and
    // the next keystroke in one of them would write that old text back.
    try { node._pixLybRepaint?.(true); } catch {}
  };
  big.close = close;

  done.addEventListener("click", (e) => { e.stopPropagation(); close(); });
  // Clicking the dim backdrop closes; a drag that merely ENDS there does not.
  let downOnBackdrop = false;
  ov.addEventListener("pointerdown", (e) => { downOnBackdrop = e.target === ov; });
  ov.addEventListener("click", (e) => { if (e.target === ov && downOnBackdrop) close(); });

  // Enter or Esc in a field leaves NOTHING focused, and a key on the page body
  // never reaches this overlay, so Delete and Ctrl+Z went dead until the next
  // click (sketch.md #12). Take the focus back.
  ov.addEventListener("focusout", (e) => {
    if (e.relatedTarget) return;
    setTimeout(() => {
      const a = document.activeElement;
      if (ov.isConnected && (!a || a === document.body)) { try { ov.focus({ preventScroll: true }); } catch {} }
    }, 0);
  });

  ov.addEventListener("keydown", (e) => {
    const typing = e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement;
    if (isComfyTextShortcut(e)) return;            // Ctrl+Enter still runs the workflow, Ctrl+S saves
    e.stopPropagation();
    if (e.key === "Escape") { e.preventDefault(); if (typing) e.target.blur(); else close(); return; }
    if (typing) return;
    // Mid-drag, the drag holds a box INDEX until the release: a Delete or an
    // undo now would shift the list under it, and the release would then move
    // the wrong box (reproduced: Delete while dragging box 1 moved box 2).
    if (input.dragging()) { e.preventDefault(); return; }
    const k = e.key.toLowerCase();
    if ((e.ctrlKey || e.metaKey) && k === "z" && !e.shiftKey) { e.preventDefault(); undo(node); return; }
    if ((e.ctrlKey || e.metaKey) && (k === "y" || (k === "z" && e.shiftKey))) { e.preventDefault(); redo(node); return; }
    if (e.key === "Delete" || e.key === "Backspace") {
      e.preventDefault();
      const sel = uiState(node).sel;
      if (sel >= 0) deleteBox(node, sel);
    }
  });

  document.body.appendChild(ov);
  big.refresh(true);
  setTimeout(() => { try { ov.focus(); } catch {} }, 0);
}

export function closeBig(node) {
  try { node?._pixLybBig?.close?.(); } catch {}
}
