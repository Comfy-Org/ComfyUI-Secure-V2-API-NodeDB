// Layout Boxes Pixaroma - the node face.
//
// ONE DOM widget in both renderers (the fill recipe of nodes2-preview-fill.md,
// the same structure as Sketch's face): the root fills its row, all layout
// lives on an inner absolute layer, and the canvas area is the one part that
// grows with the node. The canvas shows a still picture of itself while idle
// (convention #41) and repaints at graph-zoom resolution so it stays sharp.
//
// Height: getMinHeight is a CONSTANT (convention #39 E - a content-derived one
// grows a saved node on load). The node grows by one row when YOU add a box,
// so the canvas you are drawing on never shrinks under the mouse, and the
// resize floor is measured live only while a resize handle is dragged.

import { attachCanvasSnapshot } from "../shared/canvas_snapshot.mjs";
import { installCanvasZoomPassthrough } from "../shared/canvas_zoom.mjs";
import { isGraphLoading } from "../shared/graph_loading.mjs";
import { installNativeTextMenu } from "../shared/native_text_menu.mjs";
import { installNodeAccent, openNodeSettings } from "../shared/node_settings.mjs";
import { applyAdaptiveCanvasOnly, canvasBackingScale, installZoomRepaint, isVueNodes } from "../shared/nodes2.mjs";
import { installResizeFloor } from "../shared/resize_floor.mjs";
import { readState } from "./core.mjs";
import { injectCSS } from "./css.mjs";
import { renderStage } from "./draw.mjs";
import { attachBoxes } from "./input.mjs";
import { uiState } from "./actions.mjs";
import { buildActions, buildFooter, buildShapeChip, focusRow, renderList, syncListSelection } from "./controls.mjs";
import { canvasDims } from "./source.mjs";

export const WIDGET_NAME = "layout_boxes_ui";
export const WIDGET_TYPE = "pixaroma_layout_boxes";   // unique: a registered Vue type would swallow the DOM
export const STAGE_MIN = 120;
export const FLOOR = 220;                       // the body with the canvas at STAGE_MIN and one list row
export const MIN_W = 320;                       // the toolbar and a text-box row still fit

const el = (tag, cls) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  return e;
};

export function buildFace(node, { onExpand }) {
  injectCSS();
  const root = el("div", "pix-lyb-root");
  const inner = el("div", "pix-lyb-inner");
  const bar = el("div", "pix-lyb-bar");
  const stage = el("div", "pix-lyb-stage");
  const canvas = el("canvas", "pix-lyb-cv");
  // INLINE absolute on purpose: the snapshot helper's FILL mode reads it.
  canvas.style.cssText = "position:absolute;inset:0;width:100%;height:100%;display:block;";
  stage.appendChild(canvas);
  const list = el("div", "pix-lyb-list");
  inner.append(bar, stage, list);
  buildFooter(inner);
  root.appendChild(inner);

  const syncChip = buildShapeChip(bar);
  bar.appendChild(el("span", "pix-lyb-grow"));
  const syncActions = buildActions(node, bar, { onExpand, onGear: () => openNodeSettings(node) });

  const widget = node.addDOMWidget(WIDGET_NAME, WIDGET_TYPE, root, {
    serialize: false,
    getMinHeight: () => FLOOR,
  });
  // BOTH flags: options.serialize keeps it out of the PROMPT, widget.serialize
  // (top level) keeps it out of the saved WORKFLOW's widgets_values.
  widget.serialize = false;
  // An 'auto' (growing) row in Nodes 2.0, and the floor LiteGraph's
  // computeSize reads in Classic. No getMaxHeight: the body must fill.
  widget.computeLayoutSize = () => ({ minHeight: FLOOR, minWidth: 1 });
  applyAdaptiveCanvasOnly(widget);
  installCanvasZoomPassthrough(root);
  installNativeTextMenu(root);
  installNodeAccent(node, root);

  const face = { root, inner, stage, canvas, list, widget, rect: null, draft: null, syncChip, syncActions };
  node._pixLybFace = face;
  face.floorOff = installResizeFloor(root, () => contentMin(node));
  face.widthOff = installWidthFloor(root);
  face.snap = attachCanvasSnapshot(canvas);
  face.ro = new ResizeObserver(() => paintFace(node));
  face.ro.observe(stage);
  face.zoomOff = installZoomRepaint(node, null, () => paintFace(node), "_pixLybZoomRaf");
  face.input = attachBoxes(node, stage, () => face.rect, (d) => {
    face.draft = d;
    paintFace(node);
  }, (i) => focusRow(list, i));
  return widget;
}

// Nodes 2.0 has no width floor that fits this body. Its corner drag clamps at
// the node element's INLINE min-width, read on every move (useNodeResize.ts),
// so pin one only WHILE a resize handle of this node is held, exactly like
// Sketch (sketch.md #11): it can never fight a saved size on a load. The
// element is found by CONTAINMENT at press time, never cached.
function installWidthFloor(root) {
  let pinned = null;
  const clear = () => {
    if (!pinned) return;
    try { pinned.style.removeProperty("min-width"); } catch {}
    pinned = null;
  };
  const onDown = (e) => {
    if (!isVueNodes() || !root.isConnected) return;
    if (e.target?.closest?.(".lg-node-widget")) return;   // a resize grip INSIDE a widget
    let cur = "";
    try { cur = getComputedStyle(e.target).cursor || ""; } catch {}
    if (!cur.includes("resize")) return;
    const node = e.target.closest?.(".lg-node");
    if (!node || !node.contains(root)) return;
    try { node.style.setProperty("min-width", MIN_W + "px"); pinned = node; } catch {}
  };
  window.addEventListener("pointerdown", onDown, true);
  window.addEventListener("pointerup", clear, true);
  window.addEventListener("pointercancel", clear, true);
  return () => {
    window.removeEventListener("pointerdown", onDown, true);
    window.removeEventListener("pointerup", clear, true);
    window.removeEventListener("pointercancel", clear, true);
    clear();
  };
}

/** Everything the body needs at its smallest: the bar, the canvas at its
 *  minimum, the list as it wants to be, the footer. Measured, for the DRAG floor. */
export function contentMin(node) {
  const f = node._pixLybFace;
  if (!f) return FLOOR;
  const cs = getComputedStyle(f.inner);
  const gap = parseFloat(cs.rowGap) || 6;
  const pad = (parseFloat(cs.paddingTop) || 0) + (parseFloat(cs.paddingBottom) || 0);
  const kids = [...f.inner.children];
  let h = pad + gap * Math.max(0, kids.length - 1);
  for (const c of kids) h += c === f.stage ? STAGE_MIN : c === f.list ? listWant(f) : c.offsetHeight;
  return Math.max(FLOOR, Math.ceil(h));
}

/** The list's height with every row showing, up to its cap (convention #39 C:
 *  never its squeezed offsetHeight). */
function listWant(f) {
  const cap = parseFloat(getComputedStyle(f.list).maxHeight);
  return Math.min(Number.isFinite(cap) ? cap : Infinity, f.list.scrollHeight);
}

/** Grow (or shrink) the node when a USER action changed the list's height, so
 *  the canvas keeps its size. Never on a load. */
function growBy(node, dy) {
  if (!dy || isGraphLoading() || !node?.size) return;
  node.setSize?.([node.size[0], node.size[1] + dy]);
  node.setDirtyCanvas?.(true, true);
  settle(node);
}

// A row added or removed moves the canvas box TWICE in one frame (the list
// changes height, then the node follows), and a ResizeObserver stays silent
// for a size equal to the last one it REPORTED, so the paint made in between
// would stay stretched (sketch.md #6). Look again after the frame lands.
function settle(node) {
  const check = () => {
    const f = node._pixLybFace;
    if (!f) return;
    if (f.stage.clientWidth !== f.paintedW || f.stage.clientHeight !== f.paintedH) paintFace(node);
  };
  requestAnimationFrame(check);
  for (const ms of [50, 150, 400]) setTimeout(check, ms);
}

/** Re-sync every control; rebuild the list on a structural change. `userAction`
 *  is what allows the node to change size - the load path never passes it. */
export function renderFace(node, structural = true, userAction = false) {
  const f = node._pixLybFace;
  if (!f) return;
  const before = listWant(f);
  if (structural) renderList(node, f.list);
  else syncListSelection(node, f.list);
  f.syncActions();
  if (structural && userAction) {
    const after = listWant(f);
    if (before > 0 && after !== before) growBy(node, after - before);
  }
  paintFace(node);
}

export function paintFace(node) {
  const f = node._pixLybFace;
  if (!f) return;
  f.syncChip(node);
  const cssW = f.stage.clientWidth;
  const cssH = f.stage.clientHeight;
  if (!cssW || !cssH) return;              // not laid out (collapsed, zoomed out, hidden tab)
  f.paintedW = cssW;
  f.paintedH = cssH;
  const d = canvasDims(node);
  const ui = uiState(node);
  f.rect = renderStage(f.canvas, cssW, cssH, canvasBackingScale(cssW, cssH), {
    aspect: d.w / d.h,
    pic: node._pixLybPic,
    boxes: readState(node).boxes,
    sel: ui.sel,
    hover: ui.hover,
    draft: f.draft,
  });
  f.snap?.changed();
}

export function destroyFace(node) {
  const f = node._pixLybFace;
  if (!f) return;
  try { f.input?.cancel(); } catch {}
  try { f.ro?.disconnect(); } catch {}
  try { f.zoomOff?.(); } catch {}
  try { f.snap?.dispose(); } catch {}
  try { f.floorOff?.(); } catch {}
  try { f.widthOff?.(); } catch {}
  node._pixLybFace = null;
}
