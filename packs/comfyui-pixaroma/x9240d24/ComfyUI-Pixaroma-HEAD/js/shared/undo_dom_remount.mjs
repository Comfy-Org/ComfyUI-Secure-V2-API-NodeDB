// After Ctrl+Z / Ctrl+Y in Nodes 2.0, put every Pixaroma node's DOM widget back
// on the page (measured 2026-10-02 on frontend 1.53.6; CLAUDE.md Vue Compat #26).
//
// WHY: undo and redo are `app.loadGraphData(previousState)`, which rebuilds
// EVERY node as a NEW object with the SAME id. Vue keeps each node's component
// (same key), and core's WidgetDOM.vue mounts `widget.element` only in
// onMounted, so the new node's element never reaches the page: the page keeps
// the OLD element, wired to the dead node object. Measured on a workflow with
// all 85 Pixaroma node types: 70 of 81 visible controls were stale after one
// Ctrl+Z, and text typed into a Prompt afterwards went to the dead node, so a
// Save or a Run used the old text. A workflow TAB switch is not affected (all
// controls came back live), and Classic is not affected (its DomWidgets.vue
// keys on widget.id, which changes).
//
// WHAT IT DOES: just before any loadGraphData, note the WidgetDOM host div of
// every Pixaroma DOM widget on the page (node id + widget name + the element in
// it). After the load, for each note, mount the LIVE node's widget element into
// that host - the same `replaceChildren` WidgetDOM's own mountWidgetElement does,
// for the same node (canvas.graph.getNodeById) and the same widget name. Only
// when ALL hold:
//   - the host is still on the page, inside .lg-node[data-node-id=<that id>];
//   - the live node there is a Pixaroma node with a widget of that name, whose
//     element is NOT on the page yet (so a fixed frontend, or a node that
//     remounted itself, is left alone);
//   - the host holds nothing, or exactly the OLD element it held before the
//     load (never anything else).
// DOM only: nothing serialized is written, so it cannot dirty a workflow.
// Other packs' nodes are never touched.

import { app } from "../../../scripts/app.js";
import { isVueNodes } from "./nodes2.mjs";

const RETRY_MS = [0, 50, 150, 400, 1000];

// Ours by name OR by category: two classes are named the other way round
// (NotifyPixaroma, KreaLoraConvertPixaroma), CLAUDE.md Vue Compat #24.
function isOurs(node) {
  if (!node) return false;
  const t = String(node.type || node.comfyClass || "");
  if (t.includes("Pixaroma")) return true;
  return String(node.constructor?.category || "").startsWith("👑 Pixaroma");
}

// The Nodes 2.0 per-widget host: the element's parent inside the node element.
// In Classic the parent is ComfyUI's .dom-widget wrapper, which is not ours to
// manage (and never stale).
function hostOf(el) {
  const h = el?.parentElement;
  if (!h || h.classList.contains("dom-widget") || !h.closest(".lg-node")) return null;
  return h;
}

function snapshot() {
  const out = [];
  const g = app.canvas?.graph;
  if (!g || !isVueNodes()) return out;
  for (const n of g._nodes || []) {
    if (!isOurs(n)) continue;
    for (const w of n.widgets || []) {
      const el = w?.element;
      if (!(el instanceof HTMLElement) || !el.isConnected || !w.name) continue;
      const host = hostOf(el);
      if (host) out.push({ id: String(n.id), name: w.name, host, oldEl: el, done: false });
    }
  }
  return out;
}

// One pass. Returns true while some note could still resolve on a later pass.
function remount(notes) {
  const g = app.canvas?.graph;
  if (!g || !isVueNodes()) return false;
  let waiting = false;
  for (const s of notes) {
    if (s.done) continue;
    // Vue re-rendered this node itself (a different node type, a tab switch):
    // its new host mounted the right element on its own.
    if (!s.host.isConnected) { s.done = true; continue; }
    const nodeEl = s.host.closest(".lg-node");
    if (!nodeEl || nodeEl.getAttribute("data-node-id") !== s.id) { s.done = true; continue; }
    const n = g.getNodeById(s.id);
    if (!n) { waiting = true; continue; }
    if (!isOurs(n)) { s.done = true; continue; }
    const w = (n.widgets || []).find((x) => x && x.name === s.name);
    const el = w?.element;
    // A node may build its DOM widget a moment after creation: look again.
    if (!(el instanceof HTMLElement)) { waiting = true; continue; }
    if (el.isConnected) { s.done = true; continue; }
    const first = s.host.firstElementChild;
    if (first && first !== s.oldEl) { s.done = true; continue; }
    try { s.host.replaceChildren(el); } catch (_e) {}
    s.done = true;
  }
  return waiting;
}

function schedule(notes, i) {
  setTimeout(() => {
    let again = false;
    try { again = remount(notes); } catch (_e) { again = false; }
    if (again && i + 1 < RETRY_MS.length) schedule(notes, i + 1);
  }, RETRY_MS[i]);
}

export function installUndoDomRemount() {
  if (!app || typeof app.loadGraphData !== "function" || app._pixUndoRemountWrapped) return;
  app._pixUndoRemountWrapped = true;
  const orig = app.loadGraphData;
  app.loadGraphData = function (...args) {
    let notes = [];
    try { notes = snapshot(); } catch (_e) { notes = []; }
    const r = orig.apply(this || app, args);
    if (notes.length) Promise.resolve(r).finally(() => schedule(notes, 0));
    return r;
  };
}
