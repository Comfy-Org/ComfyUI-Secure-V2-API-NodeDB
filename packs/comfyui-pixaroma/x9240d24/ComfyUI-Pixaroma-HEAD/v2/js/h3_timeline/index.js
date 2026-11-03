// H3 Timeline Pixaroma - wiring.
//
// One long MiniMax H3 video told as scenes: each scene its own length, words
// and (when it needs one) picture. The scenes live on node.properties.h3Timeline
// and reach Python through the hidden TimelineState input (graphToPrompt hook
// below); nodes/node_h3_timeline.py builds each scene's conditioning and the
// windows that follow the scenes.
//
// core.mjs state | pictures.mjs input-folder pictures + the picker | crop.mjs
// the crop view | ui.mjs the face + sizing | css.mjs | help.mjs

import { app } from "../../../scripts/app.js";
import { capComputeSizeInNodes2 } from "../shared/core_min_size.mjs";
import { isGraphLoading } from "../shared/graph_loading.mjs";
import { registerNodeHelp } from "../shared/help.mjs";
import { isVueNodes } from "../shared/nodes2.mjs";
import { runTab, eachRestoredOutput } from "../shared/run_tab.mjs";
import { CLASS, HIDDEN_INPUT, injectedState } from "./core.mjs";
import { closeCrop } from "./crop.mjs";
import { H3_TIMELINE_HELP } from "./help.mjs";
import { MIN_W, buildFace, contentMin, destroyFace, renderFace } from "./ui.mjs";

const DEFAULT_W = 580;
const DEFAULT_H = 760;

registerNodeHelp(CLASS, H3_TIMELINE_HELP);

// Classic: the node height LiteGraph needs around our body, COMPUTED (sketch.md #9).
function chromeH(node) {
  const w = node._pixH3tFace?.widget;
  const y = w && w.y > 0 ? w.y : 200;
  const m = w && Number.isFinite(w.margin) ? w.margin : 10;
  return y + 2 * m;
}

function applyRun(node, message) {
  const entry = message?.h3_timeline?.[0];
  if (!entry) return;
  // Runtime only: the readout belongs to this session's run, never to the file.
  node._pixH3tRun = { audio: String(entry.audio || ""), seconds: entry.seconds, mode: entry.mode,
    keep: String(entry.keep || "") };
  renderFace(node, false, false);
}

app.registerExtension({
  name: "Pixaroma.H3Timeline",

  // A Run that ended while another workflow tab was open (js/shared/run_tab.mjs).
  onNodeOutputsUpdated(nodeOutputs) {
    eachRestoredOutput(nodeOutputs, CLASS, (node, output) => applyRun(node, output));
  },

  beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData?.name !== CLASS) return;
    if (nodeType.prototype._pixH3tPatched) return;
    nodeType.prototype._pixH3tPatched = true;
    capComputeSizeInNodes2(nodeType);

    const _created = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      _created?.apply(this, arguments);
      const node = this;
      buildFace(node);
      // The video size and the mode change what the face shows (the cut, the
      // sound lane), never the saved scenes: a repaint, no write.
      for (const name of ["width", "height", "mode"]) {
        const w = node.widgets?.find((x) => x.name === name);
        if (!w) continue;
        const cb = w.callback;
        w.callback = function () {
          const r = cb?.apply(this, arguments);
          queueMicrotask(() => renderFace(node, false, false));
          return r;
        };
      }
      // Fresh size, SYNCHRONOUSLY: configure() restores a saved size right after
      // this, so a deferred write would clobber it on every reload (convention #9).
      // DEFAULT_H is about one scene; the exact fit comes once the body is laid
      // out (ui.mjs fitFresh), only for a node no configure() ran on.
      if (!Array.isArray(node.size)) node.size = [DEFAULT_W, DEFAULT_H];
      node.size[0] = DEFAULT_W;
      node.size[1] = DEFAULT_H;
      node._pixH3tFresh = !isGraphLoading();
      // configure() fills node.properties after this; render once it has (Vue Compat #8).
      queueMicrotask(() => renderFace(node, true, false));
    };

    const _configure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
      const r = _configure?.apply(this, arguments);
      // DOM only: nothing here may write node.size, properties or slots (Vue Compat #18).
      this._pixH3tSel = -1;
      this._pixH3tFresh = false;          // opened, pasted or cloned: keeps its saved size
      renderFace(this, true, false);
      return r;
    };

    const _executed = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (message) {
      _executed?.apply(this, arguments);
      queueMicrotask(() => {
        if (runTab(message) === "other") return;
        applyRun(this, message);
      });
    };

    // Classic-only clamps, never during a load (convention #7 + Vue Compat #18).
    const _resize = nodeType.prototype.onResize;
    nodeType.prototype.onResize = function (size) {
      if (!isVueNodes() && !isGraphLoading() && this._pixH3tFace) {
        if (size[0] < MIN_W) size[0] = MIN_W;
        const floor = contentMin(this) + chromeH(this);
        if (size[1] < floor) size[1] = floor;
      }
      return _resize?.apply(this, arguments);
    };

    const _draw = nodeType.prototype.onDrawForeground;
    nodeType.prototype.onDrawForeground = function () {
      if (!isVueNodes() && !isGraphLoading() && this.size[0] < MIN_W) this.size[0] = MIN_W;
      return _draw?.apply(this, arguments);
    };

    const _removed = nodeType.prototype.onRemoved;
    nodeType.prototype.onRemoved = function () {
      closeCrop();
      destroyFace(this);
      return _removed?.apply(this, arguments);
    };
  },
});

// ── graphToPrompt: put the scenes into the hidden input ────────────────────
// Inject only - never prune: Export (API) serialises this same output.
function buildIndex() {
  const index = new Map();
  const seen = new Set();
  const visit = (graph) => {
    if (!graph || seen.has(graph)) return;
    seen.add(graph);
    for (const n of graph._nodes || graph.nodes || []) {
      if (!n) continue;
      if (n.comfyClass === CLASS || n.type === CLASS) index.set(String(n.id), n);
      const inner = n.subgraph || n._graph;
      if (inner && inner !== graph) visit(inner);
    }
  };
  visit(app.graph);
  for (const sg of app.graph?.subgraphs?.values?.() || []) visit(sg);
  return index;
}

function findNode(index, id) {
  const s = String(id);
  if (index.has(s)) return index.get(s);
  const tail = s.includes(":") ? s.slice(s.lastIndexOf(":") + 1) : null;
  return tail && index.has(tail) ? index.get(tail) : null;
}

const _origGraphToPrompt = app.graphToPrompt;
app.graphToPrompt = async function (...args) {
  const result = await _origGraphToPrompt.apply(this, args);
  try {
    const out = result?.output;
    if (out) {
      let index = null;
      for (const id in out) {
        const entry = out[id];
        if (!entry || entry.class_type !== CLASS) continue;
        if (!index) index = buildIndex();
        const node = findNode(index, id);
        if (!node) continue;
        entry.inputs = entry.inputs || {};
        entry.inputs[HIDDEN_INPUT] = JSON.stringify(injectedState(node));
      }
    }
  } catch (e) {
    console.error("[Pixaroma.H3Timeline] could not add the scenes to the prompt", e);
  }
  return result;
};
