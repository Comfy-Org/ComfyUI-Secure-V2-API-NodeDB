// Info Pixaroma - which Info button is under the pointer, in both renderers.
// Shared by the click (index.js) and the hover peek (peek.mjs).
//
// Classic: the button is painted on the canvas, so hit-test graph coordinates
// (LiteGraph's getNodeOnPos: the topmost node wins). Nodes 2.0: the face is
// pointer-events:none (so the node can still be placed and dragged, label.md
// #2), so hit-test the visible button's rectangle.

import { app } from "../../../scripts/app.js";
import { isVueNodes } from "../shared/nodes2.mjs";
import { isInfo } from "./face.mjs";

// The event happened on the canvas itself (or, in Nodes 2.0, on a node element
// above it) - not on a panel, a menu, a dialog or our own windows.
export function canvasTarget(e) {
  const c = app.canvas?.canvas;
  if (!c) return false;
  const t = e.target;
  if (t === c) return true;
  return !!(t && t.closest && t.closest(".lg-node"));
}

export function infoAt(e) {
  if (!canvasTarget(e)) return null;
  const g = app.canvas?.graph;
  if (!g) return null;
  if (isVueNodes()) {
    const over = e.target.closest?.(".lg-node");
    let hit = null;
    for (const n of g._nodes || []) {
      if (!isInfo(n) || !n._pixInfoRoot || !n._pixInfoRoot.isConnected) continue;
      const nodeEl = n._pixInfoRoot.closest(".lg-node");
      // Another node's element on top of this point is the one being pointed at.
      if (over && nodeEl && over !== nodeEl) continue;
      const r = n._pixInfoRoot.getBoundingClientRect();
      if (e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom) hit = n;
    }
    return hit;
  }
  try {
    const p = app.canvas.convertEventToCanvasOffset(e);
    const n = g.getNodeOnPos(p[0], p[1], app.canvas.visible_nodes);
    return isInfo(n) ? n : null;
  } catch (_e) { return null; }
}
