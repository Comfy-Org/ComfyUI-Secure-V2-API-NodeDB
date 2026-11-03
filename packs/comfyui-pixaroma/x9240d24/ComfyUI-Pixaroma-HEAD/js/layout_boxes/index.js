// Layout Boxes Pixaroma - wiring.
//
// Draw where things go in a picture: boxes on a canvas the shape of your
// latent, a number and a description per box, and out come FLUX.3 layout
// `elements` exactly like ComfyUI's own Create Bounding Boxes node sends them,
// in the Classic AND the Nodes 2.0 look (core's canvas is Nodes 2.0 only).
//
// core.mjs state (pure) | actions.mjs every change + undo | input.mjs draw,
// move, resize | draw.mjs the canvas | source.mjs the canvas shape + the
// background picture | controls.mjs shared controls | ui.mjs the node face |
// big.mjs the big view | css.mjs | help.mjs

import { app } from "../../../scripts/app.js";
import { isGraphLoading } from "../shared/graph_loading.mjs";
import { registerNodeHelp } from "../shared/help.mjs";
import { isLiveNode } from "../shared/live_node.mjs";
import { closeNodeSettingsFor, registerNodeAccent } from "../shared/node_settings.mjs";
import { isVueNodes } from "../shared/nodes2.mjs";
import { onRendererChange } from "../shared/renderer_switch.mjs";
import { onRouterChanged } from "../shared/router_changed.mjs";
import { runTab, eachRestoredOutput } from "../shared/run_tab.mjs";
import { CLASS, HIDDEN_INPUT, injectedState } from "./core.mjs";
import { closeBig, openBig } from "./big.mjs";
import { LAYOUT_BOXES_HELP } from "./help.mjs";
import { canvasDims, loadPicture, pictureWired, runSource, upstreamPicture } from "./source.mjs";
import { MIN_W, buildFace, contentMin, destroyFace, paintFace, renderFace } from "./ui.mjs";

const DEFAULT_W = 440;
const DEFAULT_H = 600;
const POLL_MS = 700;

registerNodeHelp(CLASS, LAYOUT_BOXES_HELP);
registerNodeAccent(CLASS, { title: "Layout Boxes" });

// ── the background picture and the canvas shape ────────────────────────────
function repaintAll(node) {
  paintFace(node);
  node._pixLybBig?.paint?.();
}

function onPicture(node) {
  const pic = node._pixLybPic;
  // A run's copy that will not load (the temp folder was cleared) is dropped,
  // and the node falls back to the upstream picture.
  if (pic?.failed && pic.kind === "run" && node._pixLybRun && node._pixLybRun.key === pic.key) {
    node._pixLybRun.failed = true;
    refreshSource(node);
    return;
  }
  repaintAll(node);
}

function refreshSource(node) {
  if (!node?._pixLybFace) return;
  let want = null;
  if (pictureWired(node)) {
    const up = upstreamPicture(node);
    const run = node._pixLybRun;
    // The run's copy is the exact picture that came in: trust it for as long
    // as the upstream is the one that produced it.
    if (run && !run.failed && run.forKey === (up ? up.key : null)) want = run;
    else if (up) want = { ...up, kind: "upstream" };
  }
  loadPicture(node, want, () => onPicture(node));
  // The shape follows width / height and whatever is wired into them; LiteGraph
  // fires nothing when an upstream number changes, so compare and repaint.
  const d = canvasDims(node);
  const sig = `${d.w}x${d.h}:${d.from}:${node._pixLybPic?.ok ? 1 : 0}`;
  if (sig !== node._pixLybSig) {
    node._pixLybSig = sig;
    repaintAll(node);
  }
}

function applyRun(node, message) {
  const entry = message?.pixaroma_layout_boxes?.[0];
  if (!entry) return;
  // Runtime only, never serialized: the temp copy does not outlive the server,
  // and the size is only a fallback for a wired size the page can't read.
  const dims = entry.dims;
  node._pixLybRunDims = Array.isArray(dims) && dims[0] > 0 && dims[1] > 0 ? [dims[0], dims[1]] : null;
  node._pixLybRun = entry.picture ? runSource(entry.picture, upstreamPicture(node)?.key ?? null) : null;
  refreshSource(node);
  repaintAll(node);
}

// ── Classic sizing ─────────────────────────────────────────────────────────
// The node height LiteGraph needs around our body: everything above it
// (widget.y: slots and the width / height rows) plus the DOM widget's margin
// above AND below. COMPUTED, never measured inside onResize (sketch.md #9).
function chromeH(node) {
  const w = node._pixLybFace?.widget;
  const y = w && w.y > 0 ? w.y : 110;
  const m = w && Number.isFinite(w.margin) ? w.margin : 10;
  return y + 2 * m;
}

app.registerExtension({
  name: "Pixaroma.LayoutBoxes",

  // A Run that ended while another workflow tab was open (js/shared/run_tab.mjs).
  onNodeOutputsUpdated(nodeOutputs) {
    eachRestoredOutput(nodeOutputs, CLASS, (node, output) => applyRun(node, output));
  },

  beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData?.name !== CLASS) return;
    if (nodeType.prototype._pixLybPatched) return;
    nodeType.prototype._pixLybPatched = true;

    const _created = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      _created?.apply(this, arguments);
      const node = this;
      buildFace(node, { onExpand: () => openBig(node) });
      node._pixLybRefresh = (structural) => {
        renderFace(node, structural, true);
        node._pixLybBig?.refresh?.(structural);
      };
      // `structural` rebuilds the rows too. Never a resize: userAction false.
      node._pixLybRepaint = (structural = false) => { renderFace(node, structural, false); };

      // Typing a new width or height repaints at once (the poll would too).
      for (const name of ["width", "height"]) {
        const w = (node.widgets || []).find((x) => x.name === name);
        if (!w) continue;
        const cb = w.callback;
        w.callback = function () {
          const r = cb?.apply(this, arguments);
          queueMicrotask(() => refreshSource(node));
          return r;
        };
      }

      // Fresh size, SYNCHRONOUSLY: configure() runs next and restores a saved
      // size, so a deferred write would clobber it on every reload (convention #9).
      if (!Array.isArray(node.size)) node.size = [DEFAULT_W, DEFAULT_H];
      node.size[0] = DEFAULT_W;
      node.size[1] = DEFAULT_H;

      // configure() fills node.properties after this; render once it has.
      queueMicrotask(() => {
        renderFace(node, true, false);
        refreshSource(node);
      });

      // Polls for "the Load Image now holds a different picture" and "Sizes
      // Pixaroma now sends another size": LiteGraph fires nothing for either.
      // Stops by itself for a copy that never joins a graph (Ctrl+C, clone -
      // Vue Compat #8), and does nothing for a node left in a closed subgraph.
      node._pixLybIdle = 0;
      node._pixLybPoll = setInterval(() => {
        if (!node.graph) {
          if (++node._pixLybIdle > 6) { clearInterval(node._pixLybPoll); node._pixLybPoll = null; }
          return;
        }
        node._pixLybIdle = 0;
        if (!isLiveNode(node)) return;
        refreshSource(node);
      }, POLL_MS);

      // A Switch Pixaroma flipping its branch moves no wire, so ask again.
      node._pixLybRouterOff = onRouterChanged(() => { if (isLiveNode(node)) refreshSource(node); });
      // Same face in both renderers; only a repaint is needed after a flip.
      node._pixLybRendererOff = onRendererChange(() => repaintAll(node));
    };

    const _configure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
      const r = _configure?.apply(this, arguments);
      // DOM only: nothing here may write node.size, properties or slots, or a
      // clean workflow opens flagged "modified" (Vue Compat #18).
      delete this._pixLybUi;          // selection / history belong to the node that was open
      renderFace(this, true, false);
      queueMicrotask(() => refreshSource(this));
      return r;
    };

    const _conn = nodeType.prototype.onConnectionsChange;
    nodeType.prototype.onConnectionsChange = function () {
      const r = _conn?.apply(this, arguments);
      queueMicrotask(() => refreshSource(this));
      return r;
    };

    const _executed = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (message) {
      _executed?.apply(this, arguments);
      // A Run that ended while another workflow tab is open belongs to that tab
      // (decided once the message's listeners ran); core hands it back when
      // that tab opens again: onNodeOutputsUpdated above.
      queueMicrotask(() => {
        if (runTab(message) === "other") return;
        applyRun(this, message);
      });
    };

    // Classic-only clamps, never during a load (convention #7 + Vue Compat #18).
    // In Nodes 2.0 the rendered size lives in the layout store: the drag floor
    // there is installResizeFloor, set up in ui.mjs.
    const _resize = nodeType.prototype.onResize;
    nodeType.prototype.onResize = function (size) {
      if (!isVueNodes() && !isGraphLoading() && this._pixLybFace) {
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
      if (this._pixLybPoll) { clearInterval(this._pixLybPoll); this._pixLybPoll = null; }
      try { this._pixLybRouterOff?.(); } catch {}
      try { this._pixLybRendererOff?.(); } catch {}
      this._pixLybRouterOff = this._pixLybRendererOff = null;
      closeBig(this);
      try { closeNodeSettingsFor(this); } catch {}
      destroyFace(this);
      return _removed?.apply(this, arguments);
    };
  },
});

// ── graphToPrompt: put the boxes into the hidden input ─────────────────────
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
    console.error("[Pixaroma.LayoutBoxes] could not add the boxes to the prompt", e);
  }
  return result;
};
