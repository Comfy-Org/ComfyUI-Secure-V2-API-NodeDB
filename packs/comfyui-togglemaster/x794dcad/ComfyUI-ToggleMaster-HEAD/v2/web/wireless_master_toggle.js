import { comfy } from "/comfy/api/v2.js";

const NODE_TYPE = "Wireless Master Toggle";
const REFRESH_DELAY_MS = 100;
const DEFAULTS = Object.freeze({
  matchColors: "",
  matchTitle: "",
  showNav: true,
  showAllGraphs: true,
  sort: "position",
  customSortAlphabet: "",
  toggleRestriction: "default",
  autoRefresh: true,
  userWidth: 0,
});
const states = new Map();

function keyOf(node) {
  return `${node.graphId ?? "visible"}:${node.id}`;
}

function stringProperty(node, name, fallback = "") {
  const value = node.getProperty(name);
  return typeof value === "string" ? value : fallback;
}

function booleanProperty(node, name, fallback) {
  const value = node.getProperty(name);
  return typeof value === "boolean" ? value : fallback;
}

function initializeProperties(node) {
  for (const [name, value] of Object.entries(DEFAULTS)) {
    if (node.getProperty(name) === undefined) node.setProperty(name, value);
  }
}

function colorTokens(node) {
  return stringProperty(node, "matchColors")
    .split(",")
    .map((value) => value.trim().toLowerCase())
    .filter(Boolean);
}

function titleExpression(node) {
  const source = stringProperty(node, "matchTitle");
  if (!source) return undefined;
  try {
    return new RegExp(source, "i");
  } catch (error) {
    console.error("Invalid Regex", error);
    return undefined;
  }
}

function comparePosition(left, right) {
  const leftId = Number(left.id);
  const rightId = Number(right.id);
  if (Number.isFinite(leftId) && Number.isFinite(rightId) && leftId !== rightId) {
    return leftId - rightId;
  }
  const byId = String(left.id).localeCompare(String(right.id), undefined, { numeric: true });
  if (byId !== 0) return byId;
  return String(left.graphId ?? "").localeCompare(String(right.graphId ?? ""));
}

function targetsFor(state) {
  const { node } = state;
  const regex = titleExpression(node);
  const colors = colorTokens(node);
  if (!regex && colors.length === 0) return [];

  const scope = booleanProperty(node, "showAllGraphs", true)
    ? "root-and-subgraphs"
    : "visible";
  const targets = comfy.graph.queryNodes({ scope }).filter((candidate) => {
    if (comfy.sameEntity(candidate, node)) return false;

    let titleMatches = true;
    if (regex) {
      regex.lastIndex = 0;
      titleMatches = regex.test(candidate.getTitle());
    }

    let colorMatches = true;
    if (colors.length > 0) {
      const foreground = String(candidate.getColor() ?? "").toLowerCase();
      const background = String(candidate.getBgColor() ?? "").toLowerCase();
      colorMatches = colors.some((color) => (
        foreground.includes(color) || background.includes(color)
      ));
    }
    return titleMatches && colorMatches;
  });

  if (stringProperty(node, "sort", "position") === "alphanumeric") {
    targets.sort((left, right) => {
      const byTitle = left.getTitle().localeCompare(
        right.getTitle(), undefined, { sensitivity: "base", numeric: true },
      );
      return byTitle || comparePosition(left, right);
    });
  } else {
    targets.sort(comparePosition);
  }
  return targets;
}

function enabled(target) {
  return target.getMode() !== "never";
}

function restrictionOf(node) {
  const value = stringProperty(node, "toggleRestriction", "default");
  return value === "max one" || value === "always one" ? value : "default";
}

function enforceRestriction(state, targets) {
  if (state.enforcing || targets.length === 0) return;
  const restriction = restrictionOf(state.node);
  if (restriction === "default") return;
  const active = targets.filter(enabled);
  if (active.length <= 1 && (active.length === 1 || restriction !== "always one")) return;

  const keep = active[0] ?? targets[0];
  state.enforcing = true;
  try {
    comfy.graph.batch(() => {
      for (const target of targets) {
        const next = comfy.sameEntity(target, keep) ? "always" : "never";
        if (target.getMode() !== next) target.setMode(next);
      }
    });
  } finally {
    state.enforcing = false;
  }
}

function applyToggle(state, target, nextEnabled) {
  const targets = targetsFor(state);
  const restriction = restrictionOf(state.node);
  if (!nextEnabled && restriction === "always one") {
    const active = targets.filter(enabled);
    if (active.length <= 1 && active.some((item) => comfy.sameEntity(item, target))) {
      render(state);
      return;
    }
  }

  comfy.graph.batch(() => {
    if (nextEnabled && restriction !== "default") {
      for (const candidate of targets) {
        candidate.setMode(comfy.sameEntity(candidate, target) ? "always" : "never");
      }
    } else {
      target.setMode(nextEnabled ? "always" : "never");
    }
  });
  render(state);
}

function style(element, values) {
  Object.assign(element.style, values);
  return element;
}

function makeButton(doc, label) {
  const button = style(doc.createElement("button"), {
    border: "1px solid #4a4a4a",
    borderRadius: "4px",
    background: "#2f2f2f",
    color: "#ddd",
    cursor: "pointer",
    padding: "3px 7px",
  });
  button.type = "button";
  button.textContent = label;
  return button;
}

function makeSwitch(doc, isEnabled, label) {
  const button = makeButton(doc, isEnabled ? "On" : "Off");
  button.setAttribute("aria-label", `Toggle ${label}`);
  button.setAttribute("aria-pressed", String(isEnabled));
  button.style.minWidth = "42px";
  button.style.background = isEnabled ? "#3f7148" : "#3a3a3a";
  return button;
}

function render(state) {
  if (state.disposed || !state.container) return;
  const targets = targetsFor(state);
  enforceRestriction(state, targets);
  const doc = state.container.ownerDocument;
  const children = [];

  const header = style(doc.createElement("div"), {
    display: "flex",
    justifyContent: "flex-end",
    padding: "3px 4px",
  });
  const refresh = makeButton(doc, "Refresh");
  refresh.addEventListener("click", () => render(state));
  header.append(refresh);
  children.push(header);

  for (const target of targets) {
    const title = target.getTitle();
    const row = style(doc.createElement("div"), {
      display: "flex",
      alignItems: "center",
      gap: "6px",
      borderTop: "1px solid #333",
      padding: "3px 4px",
    });
    const label = style(doc.createElement("span"), {
      flex: "1",
      overflow: "hidden",
      textOverflow: "ellipsis",
      whiteSpace: "nowrap",
    });
    label.textContent = title;
    label.title = title;
    row.append(label);

    if (booleanProperty(state.node, "showNav", true)) {
      const navigate = makeButton(doc, "↗");
      navigate.setAttribute("aria-label", `Navigate to ${title}`);
      navigate.addEventListener("click", () => target.centerOn());
      row.append(navigate);
    }

    const toggle = makeSwitch(doc, enabled(target), title);
    toggle.addEventListener("click", () => applyToggle(state, target, !enabled(target)));
    row.append(toggle);
    children.push(row);
  }

  state.container.replaceChildren(...children);
  state.mount?.setHeight(Math.max(42, children.length * 28 + 8));
}

function schedule(state, force = false) {
  if (!state || state.disposed) return;
  if (!force && !booleanProperty(state.node, "autoRefresh", true)) return;
  if (state.timer !== undefined) clearTimeout(state.timer);
  state.timer = setTimeout(() => {
    state.timer = undefined;
    render(state);
  }, REFRESH_DELAY_MS);
}

function dispose(state) {
  if (!state || state.disposed) return;
  state.disposed = true;
  if (state.timer !== undefined) clearTimeout(state.timer);
  state.stopNodeChanges?.();
  if (states.get(state.key) === state) states.delete(state.key);
  state.container = undefined;
}

comfy.defs.define({
  type: NODE_TYPE,
  title: NODE_TYPE,
  category: "utils",
  description: "Control nodes by title and color across the current workflow.",
  execution: "frontend",
  onCreated(node) {
    const key = keyOf(node);
    dispose(states.get(key));
    initializeProperties(node);
    const width = Number(node.getProperty("userWidth"));
    node.setSerializeWidgets(false);
    node.setSizeConstraints({ minWidth: width > 0 ? width : 180, autoHeight: true });

    const state = {
      key,
      node,
      mount: undefined,
      container: undefined,
      timer: undefined,
      stopNodeChanges: undefined,
      enforcing: false,
      disposed: false,
    };
    states.set(key, state);
    state.stopNodeChanges = comfy.onNodeChanged(
      () => schedule(state),
      { scope: "document" },
    );
    state.mount = node.widgets.mount({
      name: "wireless_master_toggle",
      height: 42,
      serialize: false,
      sendToPrompt: false,
      render(container) {
        state.container = container;
        style(container, {
          fontFamily: "sans-serif",
          fontSize: "12px",
          color: "#ddd",
          overflowY: "auto",
          userSelect: "none",
        });
        render(state);
      },
      destroy() {
        dispose(state);
      },
    });
  },
  onConfigured(node) {
    schedule(states.get(keyOf(node)), true);
  },
  onPropertyChanged(node) {
    schedule(states.get(keyOf(node)), true);
  },
  onRemoved(node) {
    dispose(states.get(keyOf(node)));
  },
});

comfy.defs.extend(NODE_TYPE, (builder) => {
  builder.onResized((node, size) => {
    if (size.width > 0 && node.getProperty("userWidth") !== size.width) {
      node.setProperty("userWidth", size.width);
    }
  });
});
