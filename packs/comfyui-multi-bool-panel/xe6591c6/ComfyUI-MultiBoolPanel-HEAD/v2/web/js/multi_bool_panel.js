import { comfy } from "/comfy/api/v2.js";

const PANEL_TYPE = "SolidlimeMultiBoolPanel";
const ROW_HEIGHT = 23;
const MAX_ITEMS = 20;
const REFRESH_MS = 120;
const states = new Map();
let pollTimer;
let stopNodeChanges;
let stopWorkflowLoads;

function stateKey(node) {
  return `${node.graphId ?? "visible"}:${node.id}`;
}

function modeOf(node) {
  const value = String(node.widgets.get("mode")?.getValue() ?? "widgets");
  return value === "bypass" || value === "mute" ? value : "widgets";
}

function titleOf(entity) {
  return String(entity.getTitle?.() ?? "");
}

function isBooleanWidget(widget) {
  const type = String(widget.widgetType ?? "").toLowerCase();
  return type === "boolean" || type === "toggle"
    || widget.getOptions()?.type === "boolean";
}

function booleanWidget(node) {
  return node.widgets.all().find(isBooleanWidget);
}

function graphFor(state) {
  const graph = comfy.graph;
  if (state.node.graphId !== undefined && state.node.graphId !== graph.id) return undefined;
  return graph;
}

function resolveTargets(state) {
  const graph = graphFor(state);
  const prefix = titleOf(state.node);
  if (!graph || !prefix) return [];
  const needle = `${prefix}:`;
  const targets = [];

  for (const node of graph.nodes()) {
    if (comfy.sameEntity(node, state.node)) continue;
    const title = titleOf(node);
    if (!title.startsWith(needle)) continue;
    const name = title.slice(needle.length).trim();
    if (name) targets.push({ kind: "node", ref: node, name });
  }

  if (modeOf(state.node) !== "widgets") {
    for (const group of graph.groups()) {
      const title = titleOf(group);
      if (!title.startsWith(needle)) continue;
      const name = title.slice(needle.length).trim();
      if (name) targets.push({ kind: "group", ref: group, name });
    }
  }

  targets.sort((left, right) => {
    const byName = left.name.localeCompare(right.name, undefined, { sensitivity: "base" });
    if (byName !== 0) return byName;
    return String(left.ref.id).localeCompare(String(right.ref.id));
  });
  return targets;
}

function hasMembers(target) {
  return target.kind !== "group" || target.ref.nodes().length > 0;
}

function canToggle(target, mode) {
  if (target.kind === "group") return hasMembers(target);
  return mode !== "widgets" || Boolean(booleanWidget(target.ref));
}

function currentValue(target, mode) {
  if (target.kind === "group") {
    const members = target.ref.nodes();
    return members.length > 0 && members.every((node) => node.getMode() === "always");
  }
  if (mode !== "widgets") return target.ref.getMode() === "always";
  return Boolean(booleanWidget(target.ref)?.getValue());
}

function applyValue(target, mode, value) {
  if (target.kind === "group") {
    const next = value ? "always" : (mode === "bypass" ? "bypass" : "never");
    for (const node of target.ref.nodes()) node.setMode(next);
    return;
  }
  if (mode === "widgets") {
    booleanWidget(target.ref)?.setValue(Boolean(value));
  } else {
    target.ref.setMode(value ? "always" : (mode === "bypass" ? "bypass" : "never"));
  }
}

function cleanSwitches(value) {
  const result = Object.create(null);
  if (!value || typeof value !== "object" || Array.isArray(value)) return result;
  let count = 0;
  for (const [key, enabled] of Object.entries(value)) {
    if (count >= 256) break;
    if (key.includes(":v3:") && key.length <= 1024 && typeof enabled === "boolean") {
      result[key] = enabled;
      count += 1;
    }
  }
  return result;
}

function readSwitches(state) {
  return cleanSwitches(state.node.getProperty("switches"));
}

function writeSwitch(state, key, value) {
  const switches = readSwitches(state);
  switches[key] = Boolean(value);
  state.node.setProperty("switches", { ...switches });
}

function fingerprint(state) {
  const graph = graphFor(state);
  if (!graph) return "inactive";
  const mode = modeOf(state.node);
  const targets = resolveTargets(state).map((target) => [
    target.kind,
    target.ref.id,
    target.name,
    canToggle(target, mode),
    currentValue(target, mode),
  ]);
  return JSON.stringify([
    graph.id,
    graph.version,
    titleOf(state.node),
    mode,
    state.node.getProperty("switches"),
    targets,
  ]);
}

function style(element, values) {
  Object.assign(element.style, values);
  return element;
}

function makeToggle(doc, enabled, disabled) {
  const button = style(doc.createElement("button"), {
    width: "32px",
    height: "16px",
    border: "0",
    borderRadius: "8px",
    position: "relative",
    cursor: disabled ? "not-allowed" : "pointer",
    background: enabled ? "#4a7a4a" : "#3a3a3a",
    flexShrink: "0",
    marginLeft: "8px",
    padding: "0",
    opacity: disabled ? "0.55" : "1",
  });
  button.type = "button";
  button.disabled = disabled;
  button.setAttribute("aria-pressed", String(enabled));
  const knob = style(doc.createElement("span"), {
    width: "12px",
    height: "12px",
    borderRadius: "50%",
    background: enabled ? "#8f8" : "#888",
    position: "absolute",
    top: "2px",
    left: enabled ? "18px" : "2px",
  });
  button.append(knob);
  return button;
}

function render(state) {
  if (state.disposed || !state.list || !graphFor(state)) return;
  const mode = modeOf(state.node);
  const switches = readSwitches(state);
  const allTargets = resolveTargets(state);
  const overflow = Math.max(0, allTargets.length - MAX_ITEMS);
  const targets = allTargets.slice(0, MAX_ITEMS);
  const doc = state.list.ownerDocument;
  const children = [];

  if (targets.length === 0) {
    const hint = style(doc.createElement("div"), {
      padding: "6px 4px",
      color: "#888",
      fontSize: "11px",
      lineHeight: "1.4",
      textAlign: "center",
    });
    hint.textContent = "Name this panel A to control nodes titled A:name";
    children.push(hint);
  }

  for (const target of targets) {
    const disabled = !canToggle(target, mode);
    const stateName = `${mode}:v3:${target.name}`;
    const enabled = Object.hasOwn(switches, stateName)
      ? switches[stateName]
      : currentValue(target, mode);
    const row = style(doc.createElement("div"), {
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      padding: "2px 6px",
      borderBottom: "1px solid #2a2a2a",
      height: `${ROW_HEIGHT}px`,
      boxSizing: "border-box",
    });
    const label = style(doc.createElement("span"), {
      flex: "1",
      overflow: "hidden",
      textOverflow: "ellipsis",
      whiteSpace: "nowrap",
      fontSize: "12px",
      color: disabled ? "#555" : "#ccc",
    });
    label.textContent = target.name;
    if (disabled) {
      label.title = target.kind === "group"
        ? "The group contains no nodes"
        : "The node has no boolean widget";
    }
    const toggle = makeToggle(doc, enabled, disabled);
    toggle.setAttribute("aria-label", target.name);
    toggle.addEventListener("click", () => {
      if (disabled) return;
      const next = toggle.getAttribute("aria-pressed") !== "true";
      writeSwitch(state, stateName, next);
      applyValue(target, mode, next);
      render(state);
    });
    row.append(label, toggle);
    children.push(row);
  }

  if (overflow > 0) {
    const note = style(doc.createElement("div"), {
      padding: "3px 6px",
      color: "#666",
      fontSize: "11px",
      textAlign: "center",
      borderTop: "1px solid #333",
    });
    note.textContent = `${overflow} more`;
    children.push(note);
  }

  state.list.replaceChildren(...children);
  state.mount?.setHeight(Math.max(60, children.length * ROW_HEIGHT + 12));
  state.lastFingerprint = fingerprint(state);
}

function refresh(state, force = false) {
  if (state.disposed || !graphFor(state)) return;
  const next = fingerprint(state);
  if (force || next !== state.lastFingerprint) render(state);
}

function scheduleRefresh(state) {
  if (!state || state.disposed || state.refreshTimer !== undefined) return;
  state.refreshTimer = setTimeout(() => {
    state.refreshTimer = undefined;
    refresh(state);
  }, 0);
}

function scheduleAll() {
  for (const state of states.values()) scheduleRefresh(state);
}

function ensureSharedObservers() {
  if (!stopNodeChanges) stopNodeChanges = comfy.onNodeChanged(scheduleAll);
  if (!stopWorkflowLoads) stopWorkflowLoads = comfy.onWorkflowLoaded(scheduleAll);
  if (pollTimer === undefined) {
    pollTimer = setInterval(() => {
      for (const state of states.values()) refresh(state);
    }, REFRESH_MS);
  }
}

function releaseSharedObservers() {
  if (states.size > 0) return;
  if (pollTimer !== undefined) clearInterval(pollTimer);
  pollTimer = undefined;
  stopNodeChanges?.();
  stopWorkflowLoads?.();
  stopNodeChanges = undefined;
  stopWorkflowLoads = undefined;
}

function dispose(state) {
  if (!state || state.disposed) return;
  state.disposed = true;
  if (state.refreshTimer !== undefined) clearTimeout(state.refreshTimer);
  for (const unsubscribe of state.unsubscribers.splice(0)) unsubscribe();
  if (states.get(state.key) === state) states.delete(state.key);
  releaseSharedObservers();
  state.container = undefined;
  state.list = undefined;
}

comfy.defs.extend(PANEL_TYPE, (builder) => {
  builder.onCreated((node) => {
    const key = stateKey(node);
    dispose(states.get(key));
    const state = {
      key,
      node,
      mount: undefined,
      container: undefined,
      list: undefined,
      lastFingerprint: "",
      refreshTimer: undefined,
      unsubscribers: [],
      disposed: false,
    };
    states.set(key, state);
    ensureSharedObservers();

    const switches = cleanSwitches(node.getProperty("switches"));
    node.setProperty("switches", { ...switches });
    node.setSizeConstraints({ minWidth: 150, autoHeight: true });

    state.mount = node.widgets.mount({
      name: "multi_bool_panel",
      height: 60,
      serialize: false,
      sendToPrompt: false,
      render(container) {
        state.container = container;
        style(container, {
          fontFamily: "monospace",
          fontSize: "12px",
          color: "#ccc",
          overflowY: "auto",
          userSelect: "none",
        });
        state.list = container.ownerDocument.createElement("div");
        container.replaceChildren(state.list);
        render(state);
      },
      destroy() {
        dispose(state);
      },
    });

    const mode = node.widgets.get("mode");
    if (mode) state.unsubscribers.push(mode.on("change", () => scheduleRefresh(state)));
  });

  builder.onConfigured((node) => scheduleRefresh(states.get(stateKey(node))));
  builder.onRemoved((node) => dispose(states.get(stateKey(node))));
});
