import { comfy } from "/comfy/api/v2.js";

const NODE_TYPES = ["VisualAreaPrompt", "VisualAreaPromptAdvanced"];
const PREFIX = "area_conditioning_";
const DEFAULT_AREA = Object.freeze([0, 0, 1, 1, 1]);
const MAX_AREAS = 64;
const stateByNode = new Map();

function cloneDefault() {
  return [...DEFAULT_AREA];
}

function validArea(value) {
  return Array.isArray(value) && value.length === 5 && value.every((item, index) =>
    typeof item === "number" && Number.isFinite(item) && item >= 0 &&
    item <= (index === 4 ? 10 : 1));
}

function stateFor(node) {
  let state = stateByNode.get(node.id);
  if (!state) {
    state = { selected: 0, controls: [], stops: [], surface: null, updating: false };
    stateByNode.set(node.id, state);
  }
  return state;
}

function areasFor(node, minimum = 1) {
  const raw = node.getProperty("area_values");
  const values = Array.isArray(raw)
    ? raw.filter(validArea).slice(0, MAX_AREAS).map((area) => [...area])
    : [];
  while (values.length < minimum) values.push(cloneDefault());
  return values;
}

function storeAreas(node, values) {
  node.setProperty("area_values", values.map((area) => [...area]));
  stateFor(node).surface?.redraw();
}

function dynamicSlots(node) {
  return node.inputs.all().filter((slot) => slot.name.startsWith(PREFIX));
}

function syncControls(node) {
  const state = stateFor(node);
  const values = areasFor(node);
  state.selected = Math.max(0, Math.min(state.selected, values.length - 1));
  const selected = values[state.selected] ?? cloneDefault();
  const indexWidget = node.widgets.get("area_id");
  indexWidget?.setOption("max", Math.max(0, values.length - 1));
  if (indexWidget?.getValue() !== state.selected) indexWidget?.setValue(state.selected);
  for (let index = 0; index < state.controls.length; index += 1) {
    const widget = state.controls[index];
    if (widget.getValue() !== selected[index]) widget.setValue(selected[index]);
  }
  state.surface?.redraw();
}

function reconcileInputs(node) {
  const state = stateFor(node);
  if (state.updating) return;
  state.updating = true;
  try {
    const slots = dynamicSlots(node);
    const connected = slots.filter((slot) => slot.isConnected).slice(0, MAX_AREAS);
    for (const slot of slots) {
      if (!slot.isConnected || !connected.includes(slot)) node.inputs.remove(slot.id);
    }
    connected.forEach((slot, index) => {
      slot.modify({ name: `${PREFIX}${index}`, type: "CONDITIONING" });
    });
    const wanted = Math.max(1, connected.length);
    const values = areasFor(node, wanted).slice(0, wanted);
    storeAreas(node, values);
    state.selected = Math.min(state.selected, wanted - 1);
    node.inputs.add(PREFIX, "CONDITIONING", { shape: "optional" });
    syncControls(node);
  } finally {
    state.updating = false;
  }
}

function updateSelected(node, coordinate, value) {
  const state = stateFor(node);
  const values = areasFor(node);
  if (!values[state.selected]) values[state.selected] = cloneDefault();
  const ceiling = coordinate === 4 ? 10 : 1;
  const numeric = Number(value);
  values[state.selected][coordinate] = Number.isFinite(numeric)
    ? Math.max(0, Math.min(ceiling, numeric))
    : DEFAULT_AREA[coordinate];
  storeAreas(node, values);
}

function drawAreaCanvas(node, context, size, theme) {
  const widthValue = Number(node.widgets.get("image_width")?.getValue()) || 1024;
  const heightValue = Number(node.widgets.get("image_height")?.getValue()) || 1024;
  const margin = 6;
  const scale = Math.min(
    Math.max(1, size[0] - margin * 2) / widthValue,
    Math.max(1, size[1] - margin * 2) / heightValue,
  );
  const width = widthValue * scale;
  const height = heightValue * scale;
  const left = (size[0] - width) / 2;
  const top = (size[1] - height) / 2;
  context.clearRect(0, 0, size[0], size[1]);
  context.fillStyle = theme.border;
  context.fillRect(left - 2, top - 2, width + 4, height + 4);
  context.fillStyle = theme.surface;
  context.fillRect(left, top, width, height);
  context.strokeStyle = theme.textSecondary;
  context.globalAlpha = 0.28;
  for (let index = 1; index < 20; index += 1) {
    const x = left + (width * index) / 20;
    const y = top + (height * index) / 20;
    context.beginPath(); context.moveTo(x, top); context.lineTo(x, top + height); context.stroke();
    context.beginPath(); context.moveTo(left, y); context.lineTo(left + width, y); context.stroke();
  }
  context.globalAlpha = 1;
  const values = areasFor(node);
  const selected = stateFor(node).selected;
  values.forEach((area, index) => {
    const [x, y, areaWidth, areaHeight] = area;
    context.fillStyle = `hsla(${Math.round(((index + 1) / values.length) * 360)}, 100%, 50%, ${index === selected ? 0.55 : 0.28})`;
    context.strokeStyle = index === selected ? theme.text : theme.border;
    context.lineWidth = index === selected ? 3 : 2;
    context.fillRect(left + x * width, top + y * height, areaWidth * width, areaHeight * height);
    context.strokeRect(left + x * width, top + y * height, areaWidth * width, areaHeight * height);
  });
}

function install(node) {
  const state = stateFor(node);
  storeAreas(node, areasFor(node));
  for (const name of ["image_width", "image_height"]) {
    const widget = node.widgets.get(name);
    if (widget) {
      node.setProperty(name, widget.getValue());
      state.stops.push(widget.on("change", (value) => {
        node.setProperty(name, Number(value));
        state.surface?.redraw();
      }));
    }
  }
  state.surface = node.widgets.canvas({
    name: "area_conditioning_canvas",
    height: 200,
    serialize: false,
    sendToPrompt: false,
    draw: (context, size, theme) => drawAreaCanvas(node, context, size, theme),
  });
  const indexWidget = node.widgets.add({
    type: "number", name: "area_id", value: 0, serialize: true,
    options: { min: 0, max: 0, step: 1, precision: 0 },
  });
  state.stops.push(indexWidget.on("change", (value) => {
    state.selected = Math.max(0, Math.min(areasFor(node).length - 1, Math.trunc(Number(value) || 0)));
    syncControls(node);
  }));
  ["x", "y", "width", "height", "conditioning_strength"].forEach((name, index) => {
    const widget = node.widgets.add({
      type: "number", name, value: DEFAULT_AREA[index], serialize: true,
      options: { min: 0, max: index === 4 ? 10 : 1, step: 0.1, precision: 2 },
    });
    state.controls.push(widget);
    state.stops.push(widget.on("change", (value) => updateSelected(node, index, value)));
  });
  reconcileInputs(node);
  node.setSizeConstraints({ minWidth: 240, minHeight: 360 });
}

function teardown(node) {
  const state = stateByNode.get(node.id);
  if (!state) return;
  for (const stop of state.stops.splice(0)) stop();
  stateByNode.delete(node.id);
}

for (const nodeType of NODE_TYPES) {
  comfy.defs.extend(nodeType, (builder) => {
    builder.onCreated((node) => install(node));
    builder.onConfigured((node) => {
      storeAreas(node, areasFor(node));
      reconcileInputs(node);
    });
    builder.onConnectionsChanged((node) => reconcileInputs(node));
    builder.onResized((node) => stateFor(node).surface?.redraw());
    builder.onRemoved((node) => teardown(node));
  });
}

export const __testing = Object.freeze({
  DEFAULT_AREA,
  validArea,
  areasFor,
  reconcileInputs,
  drawAreaCanvas,
  teardown,
});
