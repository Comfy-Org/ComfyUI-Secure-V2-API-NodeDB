// Sketch Pixaroma - the big view, for careful marking.
//
// A full-screen overlay with the same tools, a large picture and the notes on
// the right. It edits the SAME saved marks as the node, live, so there is no
// Save step and nothing to lose: Done (or Esc, or clicking outside) just
// closes it.
//
// While it is open, ComfyUI's graph Ctrl+Z is blocked through the ONE shared
// guard (Vue Compat #6 - never hand-roll this), and Ctrl+Z / Ctrl+Y undo and
// redo marks instead. Keys are stopped at the overlay so ComfyUI's own
// shortcuts (Delete removes the selected node!) cannot fire behind it.

import { installGraphUndoGuard } from "../shared/graph_undo_guard.mjs";
import { applyAccent } from "../shared/node_settings.mjs";
import { isComfyTextShortcut } from "../shared/text_shortcuts.mjs";
import { readState } from "./core.mjs";
import { injectCSS } from "./css.mjs";
import { renderStage } from "./draw.mjs";
import { attachDrawing } from "./input.mjs";
import { redo, uiState, undo } from "./actions.mjs";
import { TOOLS, buildActions, buildColors, buildPromptBox, buildTools, focusLastNote, renderList } from "./controls.mjs";

const el = (tag, cls, text) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
};

export function isBigOpen(node) {
  const b = node?._pixSkBig;
  if (b && !b.ov.isConnected) node._pixSkBig = null;   // torn down without us (Vue Compat #2)
  return !!node?._pixSkBig;
}

export function openBig(node, title = "Sketch Pixaroma") {
  if (isBigOpen(node)) return;
  injectCSS();
  const ov = el("div", "pix-sketch-big");
  ov.tabIndex = -1;
  applyAccent(ov, node);                   // a body-level overlay does not inherit the node's colour

  const panel = el("div", "pix-sketch-bpanel");
  const head = el("div", "pix-sketch-bhead");
  const done = el("button", "pix-sketch-done", "Done");
  done.type = "button";
  done.title = "Back to the workflow. Your marks are already saved on the node.";
  head.append(
    el("span", "pix-sketch-btitle", title),
    el("span", "pix-sketch-bhint", "Drag on the picture, type the change, press Enter.  B C P A T pick a tool.  Ctrl+Z undo, Ctrl+Y redo, Esc closes."),
    el("span", "pix-sketch-grow"),
    done,
  );

  const main = el("div", "pix-sketch-bmain");
  const rail = el("div", "pix-sketch-brail");
  const center = el("div", "pix-sketch-bcenter");
  const stage = el("div", "pix-sketch-stage");
  const canvas = el("canvas", "pix-sketch-cv");
  canvas.style.cssText = "position:absolute;inset:0;width:100%;height:100%;display:block;";
  stage.appendChild(canvas);
  center.appendChild(stage);
  const side = el("div", "pix-sketch-bside");
  const colors = el("div", "pix-sketch-bcolors");
  const list = el("div", "pix-sketch-list");
  const prompt = el("div", "pix-sketch-prompt");
  side.append(el("h4", null, "Color and line"), colors, el("h4", null, "Marks and what to change"), list, prompt);
  main.append(rail, center, side);
  panel.append(head, main);
  ov.appendChild(panel);

  const syncTools = buildTools(node, rail, { vertical: true });
  const syncActions = buildActions(node, rail, { vertical: true });
  const syncColors = buildColors(node, colors);
  const syncPrompt = buildPromptBox(node, prompt);

  const big = { ov, stage, canvas, list, rect: null, draft: null };
  node._pixSkBig = big;

  const paint = () => {
    if (!ov.isConnected) return;
    const w = stage.clientWidth;
    const h = stage.clientHeight;
    if (!w || !h) return;
    big.rect = renderStage(canvas, w, h, window.devicePixelRatio || 1, node._pixSkPic,
      readState(node).marks, { draft: big.draft, hover: uiState(node).hover, badgeR: 11 });
  };
  big.refresh = (structural) => {
    if (structural) renderList(node, list);
    syncTools();
    syncActions();
    syncColors();
    syncPrompt();
    paint();
  };
  big.paint = paint;

  const ro = new ResizeObserver(paint);
  ro.observe(stage);
  const drawing = attachDrawing(node, stage, () => {
    const pic = node._pixSkPic;
    return big.rect && pic?.ok ? { rect: big.rect, W: pic.realW, H: pic.realH } : null;
  }, (d) => { big.draft = d; paint(); }, () => focusLastNote(list));

  const undoGuardOff = installGraphUndoGuard(() => ov.isConnected);

  const close = () => {
    if (big.closed) return;
    big.closed = true;
    try { drawing.cancel(); } catch {}
    try { ro.disconnect(); } catch {}
    try { undoGuardOff?.(); } catch {}
    ov.remove();
    if (node._pixSkBig === big) node._pixSkBig = null;
    // REBUILD the node's rows, not just repaint: a note typed here updates the
    // saved marks without rebuilding the face's list (a rebuild mid-typing would
    // steal the caret), so its note boxes still held the OLD text, and the next
    // keystroke in one of them wrote that old text back over the new note
    // (measured: "golden crown" typed here became "make the hat red!").
    try { node._pixSkRepaint?.(true); } catch {}
  };
  big.close = close;

  done.addEventListener("click", (e) => { e.stopPropagation(); close(); });
  // Clicking the dim backdrop closes; a drag that merely ENDS there does not.
  let downOnBackdrop = false;
  ov.addEventListener("pointerdown", (e) => { downOnBackdrop = e.target === ov; });
  ov.addEventListener("click", (e) => { if (e.target === ov && downOnBackdrop) close(); });

  // Enter or Esc in a note leaves it with NOTHING focused, and a key on the
  // page body never reaches this overlay, so the tool keys and Ctrl+Z went
  // dead until the next click. Take the focus back.
  ov.addEventListener("focusout", (e) => {
    if (e.relatedTarget) return;
    setTimeout(() => {
      const a = document.activeElement;
      if (ov.isConnected && (!a || a === document.body)) { try { ov.focus({ preventScroll: true }); } catch {} }
    }, 0);
  });

  ov.addEventListener("keydown", (e) => {
    const typing = e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement;
    if (isComfyTextShortcut(e)) return;            // Ctrl+Enter still runs the workflow
    e.stopPropagation();
    if (e.key === "Escape") { e.preventDefault(); if (typing) e.target.blur(); else close(); return; }
    if (typing) return;
    const k = e.key.toLowerCase();
    if ((e.ctrlKey || e.metaKey) && k === "z" && !e.shiftKey) { e.preventDefault(); undo(node); return; }
    if ((e.ctrlKey || e.metaKey) && (k === "y" || (k === "z" && e.shiftKey))) { e.preventDefault(); redo(node); return; }
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    const tool = TOOLS.find((t) => t.key.toLowerCase() === k);
    if (tool) { e.preventDefault(); uiState(node).tool = tool.id; big.refresh(false); try { node._pixSkRepaint?.(); } catch {} }
  });

  document.body.appendChild(ov);
  big.refresh(true);
  setTimeout(() => { try { ov.focus(); } catch {} }, 0);
}

export function closeBig(node) {
  try { node?._pixSkBig?.close?.(); } catch {}
}
