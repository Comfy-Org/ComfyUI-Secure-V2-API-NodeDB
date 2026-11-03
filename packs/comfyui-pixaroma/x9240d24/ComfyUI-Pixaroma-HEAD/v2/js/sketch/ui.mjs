// Sketch Pixaroma - the node face.
//
// ONE DOM widget in both renderers (the fill recipe of nodes2-preview-fill.md):
// the root fills its row, all layout lives on an inner absolute layer, and the
// picture area is the one part that grows with the node. The canvas shows a
// still picture of itself while idle (convention #41: a canvas on screen costs
// every render), and repaints at graph-zoom resolution so it stays sharp.
//
// Height: getMinHeight is a CONSTANT (convention #39 E - a content-derived one
// grows a saved node on load). The node grows by one row when YOU add a mark,
// so the picture you are drawing on never shrinks under the pen, and the
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
import { ensureSketchFont, renderStage } from "./draw.mjs";
import { attachDrawing } from "./input.mjs";
import { uiState } from "./actions.mjs";
import { buildActions, buildColors, buildPromptBox, buildTools, focusLastNote, renderList } from "./controls.mjs";
import { imageWired } from "./source.mjs";

export const WIDGET_NAME = "sketch_ui";
export const WIDGET_TYPE = "pixaroma_sketch";   // unique: a registered Vue type would swallow the DOM
export const STAGE_MIN = 140;
export const FLOOR = 330;                        // the body with the picture at STAGE_MIN, one list row
export const MIN_W = 360;                        // the widest control row still fits (both renderers)

const el = (tag, cls) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  return e;
};

export function buildFace(node, { onExpand }) {
  injectCSS();
  const root = el("div", "pix-sketch-root");
  const inner = el("div", "pix-sketch-inner");
  const row1 = el("div", "pix-sketch-row1");
  const row2 = el("div", "pix-sketch-row2");
  const stage = el("div", "pix-sketch-stage");
  const canvas = el("canvas", "pix-sketch-cv");
  // INLINE absolute on purpose: the snapshot helper's FILL mode reads it.
  canvas.style.cssText = "position:absolute;inset:0;width:100%;height:100%;display:block;";
  const empty = el("div", "pix-sketch-empty");
  const warn = el("div", "pix-sketch-warn");
  // One short line: the banner sits over the picture, on top of the very marks it asks you to check.
  warn.textContent = "The picture changed shape. Check the marks still fit.";
  warn.hidden = true;
  stage.append(canvas, empty, warn);
  const list = el("div", "pix-sketch-list");
  const prompt = el("div", "pix-sketch-prompt");
  inner.append(row1, row2, stage, list, prompt);
  root.appendChild(inner);

  const syncTools = buildTools(node, row1);
  row1.appendChild(el("span", "pix-sketch-grow"));
  const syncActions = buildActions(node, row1, { onExpand, onGear: () => openNodeSettings(node) });
  const syncColors = buildColors(node, row2);
  const syncPrompt = buildPromptBox(node, prompt);

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

  const face = {
    root, inner, stage, canvas, empty, warn, list, prompt, widget,
    rect: null, draft: null, syncTools, syncActions, syncColors, syncPrompt,
  };
  node._pixSkFace = face;
  face.floorOff = installResizeFloor(root, () => contentMin(node));
  face.widthOff = installWidthFloor(root);
  face.snap = attachCanvasSnapshot(canvas);
  face.ro = new ResizeObserver(() => paintFace(node));
  face.ro.observe(stage);
  face.zoomOff = installZoomRepaint(node, null, () => paintFace(node), "_pixSkZoomRaf");
  face.draw = attachDrawing(node, stage, () => faceView(node), (d) => {
    face.draft = d;
    paintFace(node);
  }, () => focusLastNote(list));
  ensureSketchFont(() => paintFace(node));
  return widget;
}

// Nodes 2.0 has no width floor that fits this body: dragged narrower, the gear
// and the XL button were cut off (measured at 326 wide). Its corner drag clamps
// at the node element's INLINE min-width, read on every move (useNodeResize.ts),
// so pin one only WHILE a resize handle of this node is held, exactly like the
// height floor, and it can never fight a saved size on a load. The element is
// found by CONTAINMENT at press time, never cached (Vue replaces it).
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
    const el = e.target.closest?.(".lg-node");
    if (!el || !el.contains(root)) return;
    try { el.style.setProperty("min-width", MIN_W + "px"); pinned = el; } catch {}
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

function faceView(node) {
  const f = node._pixSkFace;
  const pic = node._pixSkPic;
  if (!f?.rect || !pic?.ok) return null;
  return { rect: f.rect, W: pic.realW, H: pic.realH };
}

/** Everything the body needs at its smallest: the rows, the picture at its
 *  minimum, the list as it is now, the prompt. Measured, for the DRAG floor. */
export function contentMin(node) {
  const f = node._pixSkFace;
  if (!f) return FLOOR;
  const cs = getComputedStyle(f.inner);
  const gap = parseFloat(cs.rowGap) || 6;
  const pad = (parseFloat(cs.paddingTop) || 0) + (parseFloat(cs.paddingBottom) || 0);
  const kids = [...f.inner.children];
  let h = pad + gap * Math.max(0, kids.length - 1);
  // The picture at its minimum, the list at the height it WANTS (it may be
  // squeezed right now, and a squeezed height would lower its own floor), and
  // every other part at its content height (flex 0 0 auto).
  for (const c of kids) h += c === f.stage ? STAGE_MIN : c === f.list ? listWant(f) : c.offsetHeight;
  return Math.max(FLOOR, Math.ceil(h));
}

/** The list's height with every row showing, up to its four-row cap. */
function listWant(f) {
  const cap = parseFloat(getComputedStyle(f.list).maxHeight);
  return Math.min(Number.isFinite(cap) ? cap : Infinity, f.list.scrollHeight);
}

/** Grow (or shrink) the node when a USER action changed the list's height, so
 *  the picture keeps its size. Never on a load. */
function growBy(node, dy) {
  if (!dy || isGraphLoading() || !node?.size) return;
  const w = node.size[0];
  const h = node.size[1] + dy;
  node.setSize?.([w, h]);
  node.setDirtyCanvas?.(true, true);
  settle(node);
}

// A mark added or removed moves the picture box TWICE in one frame: the list
// changes height (the box shrinks or grows), then the node follows and the box
// is back where it was. A ResizeObserver only reports a size that differs from
// the last one it REPORTED, so it stays silent, while the paint made in between
// used the in-between size and the picture shows stretched (measured: box
// 403x377, canvas painted for 403x349). Look again once the frame has landed,
// and a few times after, since the node's DOM follows on a later frame.
function settle(node) {
  const check = () => {
    const f = node._pixSkFace;
    if (!f) return;
    if (f.stage.clientWidth !== f.paintedW || f.stage.clientHeight !== f.paintedH) paintFace(node);
  };
  requestAnimationFrame(check);
  for (const ms of [50, 150, 400]) setTimeout(check, ms);
}

/** Re-sync every control; rebuild the list on a structural change. `userAction`
 *  is what allows the node to change size - the load path never passes it. */
export function renderFace(node, structural = true, userAction = false) {
  const f = node._pixSkFace;
  if (!f) return;
  const before = listWant(f);
  if (structural) renderList(node, f.list);
  f.syncTools();
  f.syncActions();
  f.syncColors();
  f.syncPrompt();
  if (structural && userAction) {
    const after = listWant(f);
    if (before > 0 && after !== before) growBy(node, after - before);
  }
  paintFace(node);
}

export function paintFace(node) {
  const f = node._pixSkFace;
  if (!f) return;
  const pic = node._pixSkPic;
  const st = readState(node);
  let msg = "";
  if (!pic) msg = imageWired(node) ? "Run once to show the picture here." : "Wire a picture into the image input.";
  else if (pic.failed) msg = "Could not load the picture. Run once to show it here.";
  else if (!pic.ok) msg = "Loading the picture…";
  f.empty.textContent = msg;
  f.empty.hidden = !msg;
  f.stage.classList.toggle("nopic", !pic?.ok);
  const aspect = pic?.ok ? pic.realW / pic.realH : null;
  f.warn.hidden = !(aspect && st.marks.length && st.picAspect
    && Math.abs(aspect - st.picAspect) / st.picAspect > 0.02);

  const cssW = f.stage.clientWidth;
  const cssH = f.stage.clientHeight;
  if (!cssW || !cssH) return;              // not laid out (collapsed, zoomed out, hidden tab)
  f.paintedW = cssW;
  f.paintedH = cssH;
  f.rect = renderStage(f.canvas, cssW, cssH, canvasBackingScale(cssW, cssH), pic, st.marks, {
    draft: f.draft,
    hover: uiState(node).hover,
  });
  f.snap?.changed();
}

export function destroyFace(node) {
  const f = node._pixSkFace;
  if (!f) return;
  try { f.draw?.cancel(); } catch {}
  try { f.ro?.disconnect(); } catch {}
  try { f.zoomOff?.(); } catch {}
  try { f.snap?.dispose(); } catch {}
  try { f.floorOff?.(); } catch {}
  try { f.widthOff?.(); } catch {}
  node._pixSkFace = null;
}

