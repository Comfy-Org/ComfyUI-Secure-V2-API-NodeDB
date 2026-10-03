import { app } from "../../../scripts/app.js";

const PANEL_TYPE = "SolidlimeMultiBoolPanel";
const ROW_HEIGHT = 23;
const HEADER_PAD = 6;
const MAX_ITEMS = 20;
const DEBOUNCE_MS = 120;

// ── helpers ──────────────────────────────────────────────

function getModeWidget(node) {
  return (node.widgets || []).find((w) => w.name === "mode");
}

function getPanelMode(node) {
  return getModeWidget(node)?.value ?? "widgets";
}

/** Resolve target nodes/groups whose title starts with "<panelTitle>:" and item part is non-empty. */
function resolveTargets(panelNode) {
  const prefix = panelNode.title;
  if (!prefix) return [];
  const needle = prefix + ":";
  const mode = getPanelMode(panelNode);
  const targets = [];
  // Nodes
  (app.graph._nodes || []).forEach((n) => {
    if (n.id === panelNode.id) return;
    if (!n.title || !n.title.startsWith(needle)) return;
    const name = n.title.slice(needle.length).trim();
    if (name.length > 0) targets.push({ kind: "node", ref: n, name });
  });
  // Groups — only relevant in bypass/mute modes (widgets mode targets boolean widgets)
  if (mode !== "widgets") {
    (app.graph._groups || []).forEach((g) => {
      if (!g.title || !g.title.startsWith(needle)) return;
      const name = g.title.slice(needle.length).trim();
      if (name.length > 0) targets.push({ kind: "group", ref: g, name });
    });
  }
  return targets;
}

/** Get current real state of a target (node or group) for a given panel mode. */
function currentRealValue(target, mode) {
  if (target.kind === "group") {
    const g = target.ref;
    if (typeof g.recomputeInsideNodes === "function") g.recomputeInsideNodes();
    const members = g._nodes || [];
    if (members.length === 0) return false;
    // ON = node runs normally (mode 0); OFF = bypassed/muted
    return members.every((n) => n.mode === 0);
  }
  const targetNode = target.ref;
  if (mode === "bypass") return targetNode.mode === 0;
  if (mode === "mute") return targetNode.mode === 0;
  // widgets: first boolean widget value
  const bw = (targetNode.widgets || []).find(
    (w) => w.type === "BOOLEAN" || w.type === "toggle" || (w.options && w.options.type === "boolean")
  );
  return bw ? !!bw.value : false;
}

/** Check if target node has a boolean widget. */
function hasBooleanWidget(targetNode) {
  return (targetNode.widgets || []).some(
    (w) => w.type === "BOOLEAN" || w.type === "toggle" || (w.options && w.options.type === "boolean")
  );
}

/** Apply a toggle value to a target (node or group). */
function applyValue(target, mode, value) {
  if (target.kind === "group") {
    if (mode === "widgets") return; // groups are never included in widgets mode
    const g = target.ref;
    if (typeof g.recomputeInsideNodes === "function") g.recomputeInsideNodes();
    const m = value ? 0 : (mode === "bypass" ? 4 : 2);
    (g._nodes || []).forEach((n) => { n.mode = m; });
    app.graph.setDirtyCanvas(true, true);
    return;
  }
  const targetNode = target.ref;
  if (mode === "bypass") {
    targetNode.mode = value ? 0 : 4;
  } else if (mode === "mute") {
    targetNode.mode = value ? 0 : 2;
  } else {
    // widgets
    const bw = (targetNode.widgets || []).find(
      (w) => w.type === "BOOLEAN" || w.type === "toggle" || (w.options && w.options.type === "boolean")
    );
    if (bw) {
      bw.value = value;
      if (typeof bw.callback === "function") {
        try { bw.callback(value); } catch (_) { /* ignore */ }
      }
    }
  }
  app.graph.setDirtyCanvas(true, true);
}

// ── canvas.setDirty hook (rename detection) ──────────────
// The new frontend renames nodes by assigning node.title directly and only
// calls canvas.setDirty — neither graph.change() nor onPropertyChanged fire.
// Wrapping canvas.setDirty (installed once) is the only observable signal
// for label changes; panels then re-render only when their own relevant key
// actually changed. Add/remove are already covered by graph hooks.
const panels = new Set();
let panelsCheckTimer = null;
const PANELS_CHECK_MS = 150;

function relevantKey(panel) {
  const mode = getPanelMode(panel);
  const names = resolveTargets(panel)
    .map((t) => t.name.toLowerCase())
    .sort();
  return (panel.title || "") + "\u0000" + mode + "\u0000" + names.join("\u0000");
}

function checkPanels() {
  panels.forEach((p) => {
    if (typeof p.__scheduleRefresh !== "function") return;
    const k = relevantKey(p);
    if (k !== p.__mbpLastKey) {
      p.__mbpLastKey = k;
      p.__scheduleRefresh();
    }
  });
}

function schedulePanelsCheck() {
  if (panelsCheckTimer) clearTimeout(panelsCheckTimer);
  panelsCheckTimer = setTimeout(() => {
    panelsCheckTimer = null;
    checkPanels();
  }, PANELS_CHECK_MS);
}

function mbpSetDirtyWrapper(fg, bg) {
  const r = this.__mbpPrevSetDirty.call(this, fg, bg);
  schedulePanelsCheck();
  return r;
}

function installCanvasHook(canvas) {
  if (!canvas || canvas.__mbpHooked) return;
  canvas.__mbpPrevSetDirty = canvas.setDirty;
  canvas.setDirty = mbpSetDirtyWrapper;
  canvas.__mbpHooked = true;
}

function uninstallCanvasHook() {
  if (panels.size > 0) return;
  const canvas = app.canvas;
  if (canvas && canvas.__mbpHooked && canvas.setDirty === mbpSetDirtyWrapper) {
    canvas.setDirty = canvas.__mbpPrevSetDirty;
    canvas.__mbpPrevSetDirty = null;
    canvas.__mbpHooked = false;
  }
}

// ── panel widget builder ─────────────────────────────────

function buildPanel(panelNode) {
  // Ensure properties container
  if (!panelNode.properties.switches) {
    panelNode.properties.switches = {};
  }
  // Drop stale state keys: v1 was keyed by name only (shared across modes),
  // v2 used "<mode>:<name>" with ON = bypass/mute applied semantics. Current
  // keys are "<mode>:v3:<name>" with ON = node runs normally (switch-panel
  // semantics: OFF applies bypass/mute).
  {
    const legacy = panelNode.properties.switches;
    for (const k of Object.keys(legacy)) {
      if (!k.includes(":v3:")) delete legacy[k];
    }
  }

  const container = document.createElement("div");
  container.style.cssText =
    "font-family:monospace;font-size:12px;color:#ccc;overflow-y:auto;user-select:none;";

  const listEl = document.createElement("div");
  container.appendChild(listEl);

  // addDOMWidget — the new frontend (comfyui_frontend_package) drops
  // options.computeSize, so sizing must be attached to the widget instance.
  // Provide both computeLayoutSize (new) and computeSize (legacy) paths.
  let rowsHeight = 60;
  const domWidget = panelNode.addDOMWidget("multi_bool_panel", "multi_bool_panel", container, {
    serialize: false,
  });
  domWidget.computeLayoutSize = () => ({
    minHeight: rowsHeight,
    minWidth: 150,
    maxHeight: rowsHeight,
  });
  domWidget.computeSize = (nodeWidth) => [nodeWidth, rowsHeight];

  // ── render ────────────────────────────────────────────

  let debounceTimer = null;

  function scheduleRefresh() {
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => render(), DEBOUNCE_MS);
  }

  function render() {
    const mode = getPanelMode(panelNode);
    const switches = panelNode.properties.switches;
    const targets = resolveTargets(panelNode);

    // Sort case-insensitively by item name
    targets.sort((a, b) => {
      const na = a.name.toLowerCase();
      const nb = b.name.toLowerCase();
      return na.localeCompare(nb);
    });

    // Build rows data
    let rows = targets.map((t) => ({ target: t, name: t.name }));

    // Limit
    const overflow = rows.length > MAX_ITEMS ? rows.length - MAX_ITEMS : 0;
    if (overflow > 0) rows = rows.slice(0, MAX_ITEMS);

    // Clear list
    listEl.innerHTML = "";

    // Empty state hint
    if (rows.length === 0 && overflow === 0) {
      const hint = document.createElement("div");
      hint.style.cssText =
        "padding:6px 4px;color:#888;font-size:11px;line-height:1.4;text-align:center;";
      hint.textContent =
        'このノードの名前を「A」に変えると、タイトルが「A:名前」のノードを操作対象にできる';
      listEl.appendChild(hint);
      resizeNode();
      return;
    }

    // Render rows
    rows.forEach(({ target: t, name }) => {
      const row = document.createElement("div");
      row.style.cssText =
        "display:flex;align-items:center;justify-content:space-between;" +
        "padding:2px 6px;border-bottom:1px solid #2a2a2a;cursor:default;height:" +
        ROW_HEIGHT + "px;box-sizing:border-box;";

      // Determine enabled state
      let disabled = false;
      let disabledTip = "";
      if (t.kind === "group") {
        if (typeof t.ref.recomputeInsideNodes === "function") t.ref.recomputeInsideNodes();
        if ((t.ref._nodes || []).length === 0) {
          disabled = true;
          disabledTip = "グループ内にノードがありません";
        }
      } else if (mode === "widgets" && !hasBooleanWidget(t.ref)) {
        disabled = true;
        disabledTip = "booleanウィジェットがありません";
      }

      // Label
      const label = document.createElement("span");
      label.style.cssText =
        "flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" +
        "font-size:12px;" + (disabled ? "color:#555;" : "color:#ccc;");
      label.textContent = name;
      if (disabled) {
        label.title = disabledTip;
      }
      row.appendChild(label);

      // Toggle — state is persisted per (mode, name) so bypass/mute/widgets
      // never share each other's on/off state.
      const toggle = createToggle(disabled);
      const stateKey = mode + ":v3:" + name;
      const saved = switches[stateKey];
      let isOn;
      if (saved !== undefined) {
        isOn = !!saved;
      } else {
        isOn = currentRealValue(t, mode);
      }
      if (isOn) toggle.classList.add("on");
      if (disabled) toggle.classList.add("disabled");

      toggle.addEventListener("click", (e) => {
        e.stopPropagation();
        if (disabled) return;
        const nowOn = !toggle.classList.contains("on");
        toggle.classList.toggle("on", nowOn);
        switches[stateKey] = nowOn;
        applyValue(t, mode, nowOn);
      });

      row.appendChild(toggle);

      // Hover highlight
      row.addEventListener("mouseenter", () => {
        if (!disabled) row.style.background = "#2a2a2a";
      });
      row.addEventListener("mouseleave", () => {
        row.style.background = "";
      });

      listEl.appendChild(row);
    });

    // Overflow note
    if (overflow > 0) {
      const note = document.createElement("div");
      note.style.cssText =
        "padding:3px 6px;color:#666;font-size:11px;text-align:center;border-top:1px solid #333;";
      note.textContent = "他" + overflow + "件";
      listEl.appendChild(note);
    }

    resizeNode();
  }

  function resizeNode() {
    const rows = listEl.children.length;
    const h = rows * ROW_HEIGHT + HEADER_PAD;
    rowsHeight = Math.max(h + HEADER_PAD, 60);
    // Skip resize/redraw when the height is unchanged (avoids flicker from
    // redundant setDirtyCanvas on every render pass).
    if (panelNode.size[1] !== rowsHeight) {
      panelNode.size = [panelNode.size[0], rowsHeight];
      panelNode.setDirtyCanvas(true, true);
    }
  }

  // ── toggle element factory ────────────────────────────

  function createToggle(disabled) {
    const el = document.createElement("div");
    el.className = "mbp-toggle" + (disabled ? " disabled" : "");
    el.style.cssText =
      "width:32px;height:16px;border-radius:8px;position:relative;cursor:pointer;" +
      "background:#3a3a3a;transition:background 0.15s;flex-shrink:0;margin-left:8px;";
    const knob = document.createElement("div");
    knob.style.cssText =
      "width:12px;height:12px;border-radius:50%;background:#888;position:absolute;" +
      "top:2px;left:2px;transition:left 0.15s,background 0.15s;";
    el.appendChild(knob);

    // Use a MutationObserver-like approach via class toggle handler
    const observer = new MutationObserver(() => {
      if (el.classList.contains("on")) {
        el.style.background = "#4a7a4a";
        knob.style.left = "18px";
        knob.style.background = "#8f8";
      } else {
        el.style.background = "#3a3a3a";
        knob.style.left = "2px";
        knob.style.background = el.classList.contains("disabled") ? "#555" : "#888";
      }
    });
    observer.observe(el, { attributes: true, attributeFilter: ["class"] });

    return el;
  }

  // ── event hooks ───────────────────────────────────────

  // Expose scheduleRefresh so checkPanels() (driven by the canvas.setDirty
  // hook) can trigger refreshes on this panel.
  panelNode.__scheduleRefresh = scheduleRefresh;

  // nodeCreated runs inside the ComfyNode constructor, where node.graph is
  // always null — so graph hooks must be installed in onAdded (fires with the
  // graph argument; node.graph is set by then). Add/remove both fire
  // graph.change(), so chaining graph.on_change plus onNodeAdded/onNodeRemoved
  // (belt & suspenders) covers structural changes.
  let prevChange = null;
  let prevNodeAdded = null;
  let prevNodeRemoved = null;
  const onChangeWrapper = (g) => { prevChange?.(g); schedulePanelsCheck(); };
  const onNodeAddedWrapper = (n) => { prevNodeAdded?.(n); schedulePanelsCheck(); };
  const onNodeRemovedWrapper = (n) => { prevNodeRemoved?.(n); schedulePanelsCheck(); };

  function installGraphHooks(g) {
    if (!g || panelNode.__hooksInstalled) return;
    panelNode.__hooksInstalled = true;
    prevChange = g.on_change;
    prevNodeAdded = g.onNodeAdded;
    prevNodeRemoved = g.onNodeRemoved;
    g.on_change = onChangeWrapper;
    g.onNodeAdded = onNodeAddedWrapper;
    g.onNodeRemoved = onNodeRemovedWrapper;
  }

  function uninstallGraphHooks() {
    const g = panelNode.graph;
    if (!panelNode.__hooksInstalled || !g) return;
    // Restore only when our wrapper is still the current handler.
    if (g.on_change === onChangeWrapper) g.on_change = prevChange;
    if (g.onNodeAdded === onNodeAddedWrapper) g.onNodeAdded = prevNodeAdded;
    if (g.onNodeRemoved === onNodeRemovedWrapper) g.onNodeRemoved = prevNodeRemoved;
    panelNode.__hooksInstalled = false;
    prevChange = prevNodeAdded = prevNodeRemoved = null;
  }

  const origOnAdded = panelNode.onAdded;
  panelNode.onAdded = function (graph) {
    installGraphHooks(graph || panelNode.graph);
    panels.add(panelNode);
    installCanvasHook(app.canvas);
    if (origOnAdded) origOnAdded.call(this, graph);
  };

  // Mode widget changes — re-evaluate enabled/disabled rows
  const modeW = getModeWidget(panelNode);
  if (modeW) {
    const origCB = modeW.callback;
    modeW.callback = function (v) {
      render();
      if (origCB) origCB.call(this, v);
    };
  }

  // Initial render
  render();
  // Baseline for change detection so the first relevant change re-renders.
  panelNode.__mbpLastKey = relevantKey(panelNode);

  // Cleanup on removal
  const origOnRemoved = panelNode.onRemoved;
  panelNode.onRemoved = function () {
    uninstallGraphHooks();
    panels.delete(panelNode);
    panelNode.__scheduleRefresh = null;
    panelNode.__mbpLastKey = null;
    uninstallCanvasHook();
    if (origOnRemoved) origOnRemoved.call(this);
  };
}

// ── extension registration ───────────────────────────────

app.registerExtension({
  name: "MultiBoolPanel",
  async nodeCreated(node) {
    if (node.type === PANEL_TYPE || node.constructor?.type === PANEL_TYPE) {
      buildPanel(node);
    }
  },
});
