import { comfy } from "/comfy/api/v2.js";

const NODE_TYPE = "DropdownSwitch";
const CHOICE = "choice";
const INITIAL_INPUT = "input_1";
const stateByNode = new Map();

function stateFor(node) {
  let state = stateByNode.get(node.id);
  if (!state) {
    state = { labels: [], updating: false };
    stateByNode.set(node.id, state);
  }
  return state;
}

function dynamicSlots(node) {
  return node.inputs.all().filter((slot) => slot.name !== CHOICE);
}

function labelsFromNode(node) {
  return dynamicSlots(node).map((slot) => slot.name);
}

function nextInputLabel(labels, start = 1) {
  let index = start;
  while (labels.includes(`input_${index}`)) index += 1;
  return `input_${index}`;
}

function syncChoice(node, preferred) {
  const state = stateFor(node);
  state.labels = labelsFromNode(node);
  const labels = state.labels;
  const widget = node.widgets.get(CHOICE);
  if (!widget) return;

  widget.setOption("values", [...labels]);
  node.inputs.byName(CHOICE)?.modify({
    widget: CHOICE,
    widgetConfig: { type: [...labels], options: {} },
  });

  const current = preferred ?? widget.getValue();
  if (!labels.length) {
    widget.setValue("");
  } else if (typeof current !== "string" || !labels.includes(current)) {
    widget.setValue(labels[0]);
  } else if (widget.getValue() !== current) {
    widget.setValue(current);
  }
}

function addInput(node, requested = "") {
  const labels = labelsFromNode(node);
  let label = String(requested ?? "");
  if (!label) {
    // Pinned behavior starts at the next ordinal, then skips collisions.
    label = nextInputLabel(labels, labels.length + 1);
  } else if (labels.includes(label)) {
    let suffix = 2;
    while (labels.includes(`${label} (${suffix})`)) suffix += 1;
    label = `${label} (${suffix})`;
  }
  node.inputs.add(label, "*");
  syncChoice(node);
  return label;
}

function removeInput(node, label) {
  const labels = labelsFromNode(node);
  if (!labels.includes(label)) return;
  node.inputs.remove(label);
  syncChoice(node);
}

function moveInput(node, label, direction) {
  const labels = labelsFromNode(node);
  const from = labels.indexOf(label);
  const to = from + direction;
  if (from < 0 || to < 0 || to >= labels.length) return;
  [labels[from], labels[to]] = [labels[to], labels[from]];
  node.inputs.reorder([CHOICE, ...labels]);
  syncChoice(node, node.widgets.get(CHOICE)?.getValue());
}

function insertBefore(node, label) {
  const labels = labelsFromNode(node);
  const index = labels.indexOf(label);
  if (index < 0) return;
  const inserted = nextInputLabel(labels);
  node.inputs.add(inserted, "*");
  const reordered = [...labels];
  reordered.splice(index, 0, inserted);
  node.inputs.reorder([CHOICE, ...reordered]);
  syncChoice(node);
}

async function renameInput(node, label) {
  const labels = labelsFromNode(node);
  const index = labels.indexOf(label);
  if (index < 0) return;
  const requested = await comfy.ui.prompt({ label: "Input label", value: label });
  if (requested === undefined) return;
  // The pinned implementation permits duplicate labels on an explicit rename.
  const replacement = String(requested ?? "").trim() || `input_${index + 1}`;
  node.inputs.byName(label)?.modify({ name: replacement });
  const selected = node.widgets.get(CHOICE)?.getValue();
  syncChoice(node, selected === label ? replacement : selected);
}

function restoreLabels(node, savedLabels) {
  const labels = Array.isArray(savedLabels)
    ? savedLabels.filter((item) => typeof item === "string" && item.length)
    : [];
  if (!labels.length) {
    syncChoice(node);
    return;
  }

  const state = stateFor(node);
  if (state.updating) return;
  state.updating = true;
  try {
    const slots = dynamicSlots(node);
    for (let index = 0; index < labels.length; index += 1) {
      const slot = slots[index];
      if (slot) slot.modify({ name: labels[index] });
      else node.inputs.add(labels[index], "*");
    }
    for (const slot of dynamicSlots(node).slice(labels.length)) {
      node.inputs.remove(slot.id);
    }
    // Existing slots were renamed in positional order and new ones append in
    // positional order. Avoid name-based reordering here because the pinned
    // format permits duplicate labels after an explicit rename.
    syncChoice(node);
  } finally {
    state.updating = false;
  }
}

function ensureTrailingInput(node) {
  const state = stateFor(node);
  if (state.updating) return;
  const slots = dynamicSlots(node);
  if (!slots.length || slots[slots.length - 1].isConnected) addInput(node);
}

// Extensions must be registered before their target definition so the host can
// apply them while it materializes the node type.
comfy.defs.extend(NODE_TYPE, (builder) => {
  builder.addMenuItem({
    label: "➕ Add Input",
    run: (node) => addInput(node),
    order: 10,
  });
  builder.addMenuItem({
    label: "📌 Insert Input Before",
    items: (node) => labelsFromNode(node).map((label) => ({
      label,
      run: () => insertBefore(node, label),
    })),
    order: 20,
  });
  builder.addMenuItem({
    label: "✏️ Rename Input",
    items: (node) => labelsFromNode(node).map((label) => ({
      label,
      run: async () => renameInput(node, label),
    })),
    order: 30,
  });
  builder.addMenuItem({
    label: "↑ Move Input Up",
    items: (node) => labelsFromNode(node).slice(1).map((label) => ({
      label,
      run: () => moveInput(node, label, -1),
    })),
    order: 40,
  });
  builder.addMenuItem({
    label: "↓ Move Input Down",
    items: (node) => labelsFromNode(node).slice(0, -1).map((label) => ({
      label,
      run: () => moveInput(node, label, 1),
    })),
    order: 50,
  });
  builder.addMenuItem({
    label: "🗑 Remove Input",
    items: (node) => labelsFromNode(node).map((label) => ({
      label,
      run: () => removeInput(node, label),
    })),
    order: 60,
  });
});

comfy.defs.define({
  type: NODE_TYPE,
  title: "Dropdown Switch",
  category: "utils",
  description: "Case/switch selector: choose one labeled input to forward.",
  execution: "frontend",
  inputs: [
    { name: CHOICE, type: "*" },
    { name: INITIAL_INPUT, type: "*" },
  ],
  outputs: [
    { name: "STRING", type: "STRING" },
    { name: "value", type: "*" },
  ],
  widgets: [
    { type: "combo", name: CHOICE, value: INITIAL_INPUT, options: { values: [INITIAL_INPUT] } },
  ],
  resolve: ({ self }) => {
    const selected = self.widgetValue(CHOICE);
    const label = typeof selected === "string" ? selected : "";
    const input = label ? self.input(label) : undefined;
    return {
      "0": { literal: label },
      "1": input ? { forwardTo: input } : { omit: true },
    };
  },
  onCreated(node) {
    stateFor(node);
    node.setSerializeWidgets(true);
    node.setSize({ width: 260, height: 80 });
    node.setColor("#2a3a2a");
    node.setBgColor("#1e2a1e");
    syncChoice(node);
    ensureTrailingInput(node);
  },
  onConfigured(node, data) {
    restoreLabels(node, data?.labels);
    const choice = node.widgets.get(CHOICE);
    choice?.setDisabled(Boolean(node.inputs.byName(CHOICE)?.isConnected));
  },
  onConnectionsChanged(node, event) {
    if (event.side !== "input") return;
    if (event.index === 0) {
      node.widgets.get(CHOICE)?.setDisabled(
        Boolean(node.inputs.byName(CHOICE)?.isConnected),
      );
    }
    ensureTrailingInput(node);
  },
  onSerialize(node) {
    return { labels: labelsFromNode(node) };
  },
  onRemoved(node) {
    stateByNode.delete(node.id);
  },
});
