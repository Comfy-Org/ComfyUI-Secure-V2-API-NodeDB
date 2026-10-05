import { comfy } from "/comfy/api/v2.js";

/** @type {Map<string, import('../comfy-api').NodeMode>} */
const TAG_TYPES = new Map([
  ["OrchestratorNodeToogle", "bypass"],
  ["OrchestratorNodeMuter", "never"],
]);
/** @type {Map<string, import('../comfy-api').NodeMode>} */
const GROUP_TYPES = new Map([
  ["OrchestratorNodeGroupBypasser", "bypass"],
  ["OrchestratorNodeGroupMuter", "never"],
]);
const states = new Map();
/** @type {ReturnType<typeof setInterval> | undefined} */
let refreshTimer;
/** @type {(() => void) | undefined} */
let stopNodeChanges;
/** @type {(() => void) | undefined} */
let stopWorkflowLoaded;

/** @param {import('../comfy-api').NodeHandle} node */
function keyOf(node) {
  return `${node.graphId ?? "visible"}:${node.id}`;
}

/** @param {import('../comfy-api').NodeHandle} node @param {string} name @param {string} fallback */
function stringProperty(node, name, fallback) {
  const value = node.getProperty(name);
  return typeof value === "string" ? value : fallback;
}

/** @param {import('../comfy-api').NodeHandle} node @param {string} name @param {boolean} fallback */
function booleanProperty(node, name, fallback) {
  const value = node.getProperty(name);
  return typeof value === "boolean" ? value : fallback;
}

/** @param {import('../comfy-api').NodeHandle} node */
function initializeTagProperties(node) {
  if (node.getProperty("workflow_id") === undefined) {
    node.setProperty("workflow_id", "default_workflow");
  }
  if (node.getProperty("group_id") === undefined) {
    node.setProperty("group_id", "DEFAULT");
  }
  if (node.getProperty("show_settings") === undefined) {
    node.setProperty("show_settings", true);
  }
  if (node.getProperty("node_mode") === undefined) {
    node.setProperty("node_mode", true);
  }
}

/** @param {string} title */
function titleTags(title) {
  const matches = [];
  const expression = /\[\[(.*?):(.*?)\]\]/g;
  for (const match of title.matchAll(expression)) {
    matches.push({ group: match[1], tag: match[2] });
  }
  return matches;
}

/** @param {import('../comfy-api').NodeHandle} controller */
function documentNodes(controller) {
  return comfy.graph.queryNodes({ scope: "root-and-subgraphs" }).filter(
    (candidate) => !comfy.sameEntity(candidate, controller),
  );
}

/** @param {import('../comfy-api').NodeHandle} controller */
function tagTargets(controller) {
  const groupId = stringProperty(controller, "group_id", "DEFAULT");
  const targets = [];
  const tags = new Set();
  for (const candidate of documentNodes(controller)) {
    const match = titleTags(candidate.getTitle()).find((item) => item.group === groupId);
    if (!match) continue;
    tags.add(match.tag);
    targets.push({ node: candidate, tag: match.tag });
  }
  return { targets, tags: [...tags].sort((a, b) => a.localeCompare(b)) };
}

/** @param {import('../comfy-api').NodeHandle} controller @param {Set<string>} selected @param {import('../comfy-api').NodeMode} inactive */
function applyTagSelection(controller, selected, inactive) {
  const { targets } = tagTargets(controller);
  comfy.graph.batch(() => {
    for (const target of targets) {
      target.node.setMode(selected.has(target.tag) ? "always" : inactive);
    }
  });
}

/** @param {import('../comfy-api').NodeHandle} controller */
function activeTags(controller) {
  const { targets } = tagTargets(controller);
  const active = new Set();
  for (const target of targets) {
    if (target.node.getMode() === "always") active.add(target.tag);
  }
  return active;
}

/** @param {import('../comfy-api').NodeHandle} controller @param {import('../comfy-api').NodeMode} inactive */
function groupSelection(controller, inactive) {
  const groups = [...comfy.graph.groups()];
  const stored = stringProperty(controller, "selected_group", "");
  let selected = groups.find((group) => group.id === stored || group.getTitle() === stored);
  if (!selected) {
    selected = groups.find((group) => {
      const nodes = group.nodes();
      return nodes.length > 0 && nodes[0].getMode() !== inactive;
    }) ?? groups[0];
  }
  return { groups, selected };
}

/** @param {import('../comfy-api').NodeHandle} controller @param {import('../comfy-api').GroupHandle} selected @param {import('../comfy-api').NodeMode} inactive */
function applyGroupSelection(controller, selected, inactive) {
  controller.setProperty("selected_group", selected.id);
  comfy.graph.batch(() => {
    for (const group of comfy.graph.groups()) {
      const mode = group.id === selected.id ? "always" : inactive;
      for (const node of group.nodes()) node.setMode(mode);
    }
  });
}

/** @template {HTMLElement} T @param {T} element @param {Record<string, string>} values @returns {T} */
function style(element, values) {
  Object.assign(element.style, values);
  return element;
}

/** @param {Document} doc @param {string} label @param {boolean} active */
function button(doc, label, active = false) {
  const element = style(doc.createElement("button"), {
    border: "1px solid #4b4b4b",
    borderRadius: "4px",
    background: active ? "#3d7448" : "#303030",
    color: "#eee",
    cursor: "pointer",
    minHeight: "25px",
    overflow: "hidden",
    padding: "3px 7px",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  });
  element.type = "button";
  element.textContent = label;
  element.setAttribute("aria-pressed", String(active));
  return element;
}

/** @param {Document} doc @param {string} label @param {HTMLInputElement} input */
function labeled(doc, label, input) {
  const row = style(doc.createElement("label"), {
    alignItems: "center", display: "grid", gap: "5px",
    gridTemplateColumns: "88px 1fr", padding: "2px 4px",
  });
  const text = doc.createElement("span");
  text.textContent = label;
  row.append(text, input);
  return row;
}

/** @param {Document} doc @param {string} value */
function textInput(doc, value) {
  const input = style(doc.createElement("input"), {
    background: "#222", border: "1px solid #555", color: "#eee",
    minWidth: "0", padding: "3px",
  });
  input.type = "text";
  input.value = value;
  return input;
}

/** @param {any} state */
function renderTag(state) {
  if (state.disposed || !state.container) return;
  const { node, inactive } = state;
  const doc = state.container.ownerDocument;
  const exclusive = booleanProperty(node, "node_mode", true);
  const showing = booleanProperty(node, "show_settings", true);
  const { tags } = tagTargets(node);
  const selected = activeTags(node);
  const children = [];

  const settingsToggle = button(doc, showing ? "Hide Settings" : "Show Settings", showing);
  settingsToggle.addEventListener("click", () => {
    node.setProperty("show_settings", !showing);
    renderTag(state);
  });
  children.push(settingsToggle);

  if (showing) {
    const workflow = textInput(doc, stringProperty(node, "workflow_id", "default_workflow"));
    workflow.addEventListener("change", () => node.setProperty("workflow_id", workflow.value.slice(0, 128)));
    children.push(labeled(doc, "Workflow ID", workflow));

    const group = textInput(doc, stringProperty(node, "group_id", "DEFAULT"));
    group.addEventListener("change", () => {
      node.setProperty("group_id", group.value.slice(0, 128));
      renderTag(state);
    });
    children.push(labeled(doc, "Group ID", group));

    const mode = doc.createElement("input");
    mode.type = "checkbox";
    mode.checked = exclusive;
    mode.addEventListener("change", () => {
      node.setProperty("node_mode", mode.checked);
      if (mode.checked) applyTagSelection(node, new Set(), inactive);
      renderTag(state);
    });
    children.push(labeled(doc, "Exclusive", mode));
  }

  if (!exclusive && tags.length > 1) {
    const allActive = tags.every((tag) => selected.has(tag));
    const all = button(doc, "Active All", allActive);
    all.addEventListener("click", () => {
      applyTagSelection(node, allActive ? new Set() : new Set(tags), inactive);
      renderTag(state);
    });
    children.push(all);
  }

  for (const tag of tags) {
    const active = selected.has(tag);
    const control = button(doc, tag, active);
    control.addEventListener("click", () => {
      if (exclusive) {
        applyTagSelection(node, active ? new Set() : new Set([tag]), inactive);
      } else {
        const next = new Set(selected);
        if (active) next.delete(tag); else next.add(tag);
        applyTagSelection(node, next, inactive);
      }
      renderTag(state);
    });
    children.push(control);
  }
  if (tags.length === 0) {
    const empty = doc.createElement("span");
    empty.textContent = "No matching [[group:tag]] titles";
    children.push(empty);
  }
  state.container.replaceChildren(...children);
  state.mount?.setHeight(Math.max(44, 31 * children.length + 8));
}

/** @param {any} state */
function renderGroup(state) {
  if (state.disposed || !state.container) return;
  const { groups, selected } = groupSelection(state.node, state.inactive);
  const doc = state.container.ownerDocument;
  const children = [];
  for (const group of groups) {
    const active = selected?.id === group.id;
    const control = button(doc, group.getTitle(), active);
    control.addEventListener("click", () => {
      if (!active) applyGroupSelection(state.node, group, state.inactive);
      renderGroup(state);
    });
    children.push(control);
  }
  if (children.length === 0) {
    const empty = doc.createElement("span");
    empty.textContent = "No groups in this graph";
    children.push(empty);
  }
  state.container.replaceChildren(...children);
  state.mount?.setHeight(Math.max(44, 31 * children.length + 8));
}

/** @param {any} state */
function stateSignature(state) {
  if (state.kind === "tag") {
    const groupId = stringProperty(state.node, "group_id", "DEFAULT");
    const rows = documentNodes(state.node).map((node) => [
      node.graphId, node.id, node.getTitle(), node.getMode(),
    ]);
    rows.push([groupId, String(booleanProperty(state.node, "node_mode", true))]);
    return JSON.stringify(rows);
  }
  return JSON.stringify(comfy.graph.groups().map((group) => [
    group.id, group.getTitle(), group.nodes().map((node) => [node.id, node.getMode()]),
  ]));
}

function refreshAll() {
  for (const state of states.values()) {
    if (state.disposed) continue;
    const signature = stateSignature(state);
    if (signature === state.signature) continue;
    state.signature = signature;
    if (state.kind === "tag") renderTag(state); else renderGroup(state);
  }
}

function ensureSharedLifecycle() {
  if (refreshTimer !== undefined) return;
  refreshTimer = setInterval(refreshAll, 250);
  stopNodeChanges = comfy.onNodeChanged(refreshAll, { scope: "document" });
  stopWorkflowLoaded = comfy.onWorkflowLoaded(refreshAll);
}

function releaseSharedLifecycle() {
  if (states.size !== 0) return;
  if (refreshTimer !== undefined) clearInterval(refreshTimer);
  refreshTimer = undefined;
  stopNodeChanges?.();
  stopWorkflowLoaded?.();
  stopNodeChanges = undefined;
  stopWorkflowLoaded = undefined;
}

/** @param {any} state */
function dispose(state) {
  if (!state || state.disposed) return;
  state.disposed = true;
  if (states.get(state.key) === state) states.delete(state.key);
  state.container = undefined;
  releaseSharedLifecycle();
}

/** @param {string} type @param {'tag'|'group'} kind @param {import('../comfy-api').NodeMode} inactive */
function registerController(type, kind, inactive) {
  comfy.defs.extend(type, (builder) => {
    builder.onCreated((node) => {
      const key = keyOf(node);
      dispose(states.get(key));
      if (kind === "tag") initializeTagProperties(node);
      if (kind === "group" && node.getProperty("selected_group") === undefined) {
        node.setProperty("selected_group", "");
      }
      node.setSizeConstraints({ minWidth: 190, autoHeight: true });
      /** @type {any} */
      const state = {
        key, node, kind, inactive, disposed: false,
        container: undefined, mount: undefined, signature: "",
      };
      states.set(key, state);
      ensureSharedLifecycle();
      state.mount = node.widgets.mount({
        name: `custom_switch_${type}`,
        height: 44,
        serialize: false,
        sendToPrompt: false,
        render(container) {
          state.container = container;
          style(container, {
            color: "#eee", display: "grid", fontFamily: "sans-serif",
            fontSize: "12px", gap: "4px", overflowY: "auto", padding: "4px",
          });
          if (kind === "tag") renderTag(state); else renderGroup(state);
        },
        destroy() { dispose(state); },
      });
    });
    builder.onConfigured((node) => {
      const state = states.get(keyOf(node));
      if (state) state.signature = "";
      refreshAll();
    });
    builder.onPropertyChanged((node) => {
      const state = states.get(keyOf(node));
      if (state) state.signature = "";
      refreshAll();
    });
    builder.onRemoved((node) => dispose(states.get(keyOf(node))));
  });
}

for (const [type, inactive] of TAG_TYPES) registerController(type, "tag", inactive);
for (const [type, inactive] of GROUP_TYPES) registerController(type, "group", inactive);
