import { comfy } from "/comfy/api/v2.js";

import {
  DEFAULT_OPTIONS,
  LocalUndo,
  PRETTIFIER_NODE_TYPE,
  alignNodes,
  equalizeSpacing,
  runPrettify,
  selectedWorkflowNodes,
} from "./layout.js";

const COMMAND = "workflow-prettier";
const installations = new WeakMap();

const LAYOUT_HINTS = Object.freeze({
  "Layered (Vertical Stacks)": "DAG columns grouped by depth and stacked vertically. Best for branching pipelines.",
  Linear: "A single row in topological execution order. Best for simple pipelines.",
  "Compact (Tight Rectangle)": "Packs nodes into a tight rectangle without using connections.",
  "Sort by Type": "Groups identical node types into columns ordered by pipeline depth.",
});

const DIRECTION_HINTS = Object.freeze({
  "Left to Right": "Standard left-to-right data flow.",
  "Top to Bottom": "Vertical flow for tall displays.",
  "Right to Left": "Reversed right-to-left data flow.",
});

const GROUP_HINTS = Object.freeze({
  "Auto (Respect Groups)": "Arranges nodes inside groups, then positions groups as blocks.",
  "Respect Groups": "Arranges nodes inside groups, then positions groups as blocks.",
  "Ignore Groups": "Treats all nodes as one flat graph.",
});

function documentId(api) {
  return api.workflow.documentId();
}

export function readOptions(node) {
  const value = (name, fallback) => node.widgets.get(name)?.getValue() ?? fallback;
  return Object.freeze({
    layout: value("layout", DEFAULT_OPTIONS.layout),
    direction: value("direction", DEFAULT_OPTIONS.direction),
    groupHandling: value("group_handling", DEFAULT_OPTIONS.groupHandling),
    horizontalSpacing: Number(value("horizontal_spacing", DEFAULT_OPTIONS.horizontalSpacing)),
    verticalSpacing: Number(value("vertical_spacing", DEFAULT_OPTIONS.verticalSpacing)),
    groupPadding: Number(value("group_padding", DEFAULT_OPTIONS.groupPadding)),
  });
}

function withSnapshot(api, undo, action) {
  const graph = api.graph;
  undo.push(documentId(api), graph);
  graph.batch(() => action(graph));
}

function undoCurrent(api, undo) {
  return undo.pop(documentId(api), api.graph);
}

function element(document, tag, text, styles = {}) {
  const item = document.createElement(tag);
  if (text !== undefined) item.textContent = text;
  Object.assign(item.style, styles);
  return item;
}

function button(document, label, run) {
  const item = element(document, "button", label, {
    border: "1px solid var(--border-color, #555)",
    borderRadius: "4px",
    background: "var(--comfy-input-bg, #242b30)",
    color: "var(--input-text, #ddd)",
    cursor: "pointer",
    padding: "5px 8px",
  });
  item.type = "button";
  item.addEventListener("click", run);
  return item;
}

function installNodePanel(api, undo, node, states) {
  const key = `${node.graphId ?? api.graph.id}:${node.id}`;
  states.get(key)?.dispose();
  const state = {
    container: undefined,
    detailsOpen: false,
    subscriptions: [],
    disposed: false,
    dispose() {
      for (const stop of state.subscriptions.splice(0)) stop();
      state.container = undefined;
      if (states.get(key) === state) states.delete(key);
    },
  };
  states.set(key, state);

  node.setColor("#2a363b");
  node.setBgColor("#1a252a");
  const currentSize = node.getSize();
  if (currentSize.width < 340) node.setSize({ width: 340, height: currentSize.height });

  node.widgets.mount({
    name: "workflow_prettier_controls",
    serialize: false,
    sendToPrompt: false,
    render(container) {
      state.dispose();
      state.disposed = false;
      states.set(key, state);
      state.container = container;
      const document = container.ownerDocument;
      Object.assign(container.style, {
        boxSizing: "border-box",
        color: "var(--input-text, #ddd)",
        display: "grid",
        fontFamily: "sans-serif",
        fontSize: "11px",
        gap: "6px",
        padding: "6px",
      });

      const actions = element(document, "div", undefined, {
        display: "grid",
        gap: "5px",
        gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
      });
      actions.append(
        button(document, "Prettify!", () => withSnapshot(api, undo,
          (graph) => runPrettify(graph, readOptions(node)))),
        button(document, "Equalize Spacing", () => withSnapshot(api, undo,
          (graph) => equalizeSpacing(graph, readOptions(node)))),
        button(document, "Undo", () => undoCurrent(api, undo)),
      );

      const details = element(document, "section", undefined, {
        background: "rgba(0, 0, 0, 0.22)",
        borderRadius: "4px",
        display: state.detailsOpen ? "grid" : "none",
        gap: "5px",
        padding: "7px",
      });
      const detailsButton = button(document, state.detailsOpen ? "Hide Details" : "Details", () => {
        state.detailsOpen = !state.detailsOpen;
        details.style.display = state.detailsOpen ? "grid" : "none";
        detailsButton.textContent = state.detailsOpen ? "Hide Details" : "Details";
      });
      actions.append(detailsButton);
      container.replaceChildren(actions, details);

      const renderDetails = () => {
        const options = readOptions(node);
        const section = (title, body) => {
          const row = element(document, "div");
          row.append(
            element(document, "strong", title, { color: "#9bc3dc", display: "block" }),
            element(document, "span", body),
          );
          return row;
        };
        details.replaceChildren(
          section("Layout", LAYOUT_HINTS[options.layout] ?? ""),
          section("Direction", DIRECTION_HINTS[options.direction] ?? ""),
          section("Groups", GROUP_HINTS[options.groupHandling] ?? ""),
          element(document, "span", `Local undo: ${undo.depth(documentId(api), api.graph)}/10`, {
            color: "var(--descrip-text, #999)",
          }),
        );
      };
      renderDetails();
      for (const name of ["layout", "direction", "group_handling"]) {
        const widget = node.widgets.get(name);
        if (widget) state.subscriptions.push(widget.on("change", renderDetails));
      }
    },
    destroy() {
      state.dispose();
    },
  });
  return state;
}

function registerCommands(api, undo) {
  const runLayout = (layout) => withSnapshot(api, undo,
    (graph) => runPrettify(graph, { ...DEFAULT_OPTIONS, layout }));
  const definitions = [
    ["layered", "Prettify: Layered", () => runLayout("Layered (Vertical Stacks)")],
    ["linear", "Prettify: Linear", () => runLayout("Linear")],
    ["compact", "Prettify: Compact", () => runLayout("Compact (Tight Rectangle)")],
    ["sortByType", "Prettify: Sort by Type", () => runLayout("Sort by Type")],
    ["equalize", "Prettify: Equalize Spacing", () => withSnapshot(api, undo,
      (graph) => equalizeSpacing(graph, DEFAULT_OPTIONS))],
    ["undo", "Prettify: Undo Last Layout", () => undoCurrent(api, undo)],
    ["addNode", "Prettify: Add Prettifier Node", () => {
      const graph = api.graph;
      const position = graph.pointerPosition() ?? { x: 100, y: 100 };
      const node = graph.batch(() => graph.add(PRETTIFIER_NODE_TYPE, { position }));
      graph.select([node]);
    }],
  ];
  const alignment = [
    ["alignLeft", "Align Selected: Left", "left"],
    ["alignRight", "Align Selected: Right", "right"],
    ["alignTop", "Align Selected: Top", "top"],
    ["alignBottom", "Align Selected: Bottom", "bottom"],
    ["centerHorizontal", "Align Selected: Center Horizontally", "centerH"],
    ["centerVertical", "Align Selected: Center Vertically", "centerV"],
    ["distributeHorizontal", "Distribute Selected: Horizontally", "distributeH"],
    ["distributeVertical", "Distribute Selected: Vertically", "distributeV"],
  ];
  for (const [id, label, run] of definitions) {
    api.commands.register({ id: `${COMMAND}.${id}`, label, run });
  }
  for (const [id, label, mode] of alignment) {
    api.commands.register({
      id: `${COMMAND}.${id}`,
      label,
      run: () => {
        if (selectedWorkflowNodes(api.graph).length < 2) return;
        withSnapshot(api, undo, (graph) => alignNodes(graph, mode));
      },
    });
  }
}

export function installWorkflowPrettier(api = comfy) {
  const existing = installations.get(api);
  if (existing) return existing;
  const undo = new LocalUndo();
  const states = new Map();
  const stops = [];
  registerCommands(api, undo);

  const action = api.ui.addActionBarButton({
    id: "workflow-prettier.prettify",
    icon: "icon-[lucide--wand-sparkles]",
    label: "Prettify",
    tooltip: "Arrange the current workflow with a layered layout",
    run: () => withSnapshot(api, undo,
      (graph) => runPrettify(graph, DEFAULT_OPTIONS)),
  });

  stops.push(api.defs.extend(PRETTIFIER_NODE_TYPE, (builder) => {
    builder.onCreated((node) => installNodePanel(api, undo, node, states));
    builder.onRemoved((node) => states.get(`${node.graphId ?? api.graph.id}:${node.id}`)?.dispose());
  }));

  stops.push(api.defs.extend(() => true, (builder) => {
    builder.addMenuItem({
      label: "Align / Distribute",
      when: () => selectedWorkflowNodes(api.graph).length >= 2,
      items: [
        { label: "Align Left", run: () => withSnapshot(api, undo, (graph) => alignNodes(graph, "left")) },
        { label: "Align Right", run: () => withSnapshot(api, undo, (graph) => alignNodes(graph, "right")) },
        { label: "Align Top", run: () => withSnapshot(api, undo, (graph) => alignNodes(graph, "top")) },
        { label: "Align Bottom", run: () => withSnapshot(api, undo, (graph) => alignNodes(graph, "bottom")) },
        { label: "Center Horizontally", run: () => withSnapshot(api, undo, (graph) => alignNodes(graph, "centerH")) },
        { label: "Center Vertically", run: () => withSnapshot(api, undo, (graph) => alignNodes(graph, "centerV")) },
        { label: "Distribute Horizontally", run: () => withSnapshot(api, undo, (graph) => alignNodes(graph, "distributeH")) },
        { label: "Distribute Vertically", run: () => withSnapshot(api, undo, (graph) => alignNodes(graph, "distributeV")) },
      ],
      order: 80,
    });
  }));

  stops.push(api.onDocumentClosed((document) => undo.clearDocument(document.id)));
  const installation = Object.freeze({
    undo,
    action,
    remove() {
      for (const state of [...states.values()]) state.dispose();
      for (const stop of stops.splice(0)) stop();
      action.remove();
      installations.delete(api);
    },
  });
  installations.set(api, installation);
  return installation;
}

export const workflowPrettier = installWorkflowPrettier(comfy);
