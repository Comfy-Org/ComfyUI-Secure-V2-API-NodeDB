import { comfy } from "/comfy/api/v2.js";


const MIN_AXES = 3;
const MAX_AXES = 10;
const DEFAULT_WEIGHT = 1;
const MIN_WEIGHT = 0;
const MAX_WEIGHT = 2;
const MAX_SYNC_CHARS = 256;
const CANVAS_SIZE = 500;
const RADAR_RADIUS = 230;
const POINT_RADIUS = 8;
const HIT_RADIUS = 18;
const NODE_WIDTH = 540;
const NODE_HEIGHT = 570;
const PORT_CENTER = { x: NODE_WIDTH / 2, y: 305 };
const PORT_RADIUS = 245;

const states = new WeakMap();


export function clampAxes(value) {
  const number = Math.trunc(Number(value));
  if (!Number.isFinite(number)) return 5;
  return Math.max(MIN_AXES, Math.min(MAX_AXES, number));
}


function clampWeight(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return DEFAULT_WEIGHT;
  return Math.max(MIN_WEIGHT, Math.min(MAX_WEIGHT, number));
}


export function parseWeights(value, count) {
  const size = clampAxes(count);
  const text = typeof value === "string" ? value : "";
  if (text.length > MAX_SYNC_CHARS) return Array(size).fill(DEFAULT_WEIGHT);
  const values = text.split(",").filter((item) => item.trim() !== "").map(Number);
  if (
    values.length === 0 ||
    values.some((item) => !Number.isFinite(item) || item < MIN_WEIGHT || item > MAX_WEIGHT)
  ) {
    return Array(size).fill(DEFAULT_WEIGHT);
  }
  return Array.from({ length: size }, (_, index) =>
    index < values.length ? values[index] : DEFAULT_WEIGHT,
  );
}


export function formatWeights(values) {
  return values.map((value) => clampWeight(value).toFixed(2)).join(",");
}


export function resizeWeights(values, remembered, count) {
  values.forEach((value, index) => remembered.set(index, value));
  return Array.from({ length: clampAxes(count) }, (_, index) => {
    if (index < values.length) return values[index];
    return remembered.has(index) ? remembered.get(index) : DEFAULT_WEIGHT;
  });
}


export function projectedWeight(index, count, x, y) {
  const angle = Math.PI * 2 * index / count - Math.PI / 2;
  const dx = x - CANVAS_SIZE / 2;
  const dy = y - CANVAS_SIZE / 2;
  const projected = dx * Math.cos(angle) + dy * Math.sin(angle);
  return clampWeight(projected / RADAR_RADIUS * MAX_WEIGHT);
}


export function outputPosition(index, count) {
  const angle = Math.PI * 2 * index / count - Math.PI / 2;
  return {
    x: PORT_CENTER.x + PORT_RADIUS * Math.cos(angle),
    y: PORT_CENTER.y + PORT_RADIUS * Math.sin(angle),
  };
}


export function syncOutputs(node, count) {
  const size = clampAxes(count);
  while (node.outputs.length > size) {
    node.outputs.remove({ index: node.outputs.length - 1 });
  }
  while (node.outputs.length < size) {
    node.outputs.add(String(node.outputs.length + 1), "FLOAT");
  }
  node.outputs.all().forEach((slot, index) => {
    slot.modify({
      name: String(index + 1),
      label: String(index + 1),
      position: outputPosition(index, size),
      direction: "center",
    });
  });
}


function pointFor(weight, index, count) {
  const angle = Math.PI * 2 * index / count - Math.PI / 2;
  const radius = RADAR_RADIUS * clampWeight(weight) / MAX_WEIGHT;
  return {
    x: CANVAS_SIZE / 2 + radius * Math.cos(angle),
    y: CANVAS_SIZE / 2 + radius * Math.sin(angle),
  };
}


function drawRadar(context, values, hoverIndex) {
  const center = CANVAS_SIZE / 2;
  context.clearRect(0, 0, CANVAS_SIZE, CANVAS_SIZE);
  context.fillStyle = "#171717";
  context.fillRect(0, 0, CANVAS_SIZE, CANVAS_SIZE);

  context.textAlign = "center";
  context.textBaseline = "middle";
  context.font = "12px sans-serif";
  for (const reference of [0.5, 1, 1.5, 2]) {
    const radius = RADAR_RADIUS * reference / MAX_WEIGHT;
    context.beginPath();
    context.arc(center, center, radius, 0, Math.PI * 2);
    context.setLineDash([4, 4]);
    context.lineWidth = 1;
    context.strokeStyle = reference === 2 ? "#bf1f1f" : "#686868";
    context.stroke();
    context.fillStyle = "#aaa";
    context.fillText(reference.toFixed(1), center + radius - 16, center);
  }
  context.setLineDash([]);

  values.forEach((_value, index) => {
    const angle = Math.PI * 2 * index / values.length - Math.PI / 2;
    context.beginPath();
    context.moveTo(center, center);
    context.lineTo(
      center + RADAR_RADIUS * Math.cos(angle),
      center + RADAR_RADIUS * Math.sin(angle),
    );
    context.strokeStyle = "#555";
    context.stroke();
  });

  const points = values.map((value, index) => pointFor(value, index, values.length));
  context.beginPath();
  points.forEach((point, index) => {
    if (index === 0) context.moveTo(point.x, point.y);
    else context.lineTo(point.x, point.y);
  });
  context.closePath();
  context.lineWidth = 3;
  context.strokeStyle = "#008cba";
  context.fillStyle = "rgba(0, 140, 186, 0.3)";
  context.stroke();
  context.fill();

  points.forEach((point, index) => {
    context.beginPath();
    context.arc(point.x, point.y, index === hoverIndex ? 10 : POINT_RADIUS, 0, Math.PI * 2);
    context.fillStyle = index === hoverIndex ? "#00bfff" : "#008cba";
    context.fill();
    context.fillStyle = "#ddd";
    context.fillText(String(index + 1), point.x, point.y - 18);
  });
}


function pointerCoordinates(canvas, event) {
  const rect = canvas.getBoundingClientRect();
  return {
    x: (event.clientX - rect.left) * CANVAS_SIZE / rect.width,
    y: (event.clientY - rect.top) * CANVAS_SIZE / rect.height,
  };
}


function nearestPoint(values, x, y) {
  let result = -1;
  let distance = HIT_RADIUS * HIT_RADIUS;
  values.forEach((value, index) => {
    const point = pointFor(value, index, values.length);
    const candidate = (point.x - x) ** 2 + (point.y - y) ** 2;
    if (candidate <= distance) {
      result = index;
      distance = candidate;
    }
  });
  return result;
}


export function mountRadar(container, state) {
  const doc = container.ownerDocument;
  const canvas = doc.createElement("canvas");
  canvas.width = CANVAS_SIZE;
  canvas.height = CANVAS_SIZE;
  canvas.style.cssText = "display:block;width:500px;height:500px;max-width:100%;background:#171717;border-radius:8px;touch-action:none";
  container.style.cssText = "display:flex;justify-content:center;align-items:center;overflow:hidden;padding:4px;box-sizing:border-box";
  container.append(canvas);
  const context = canvas.getContext("2d");
  if (!context) throw new Error("Radar Weights requires a 2D canvas");

  let hoverIndex = -1;
  let dragIndex = -1;
  let destroyed = false;
  const redraw = () => {
    if (!destroyed) drawRadar(context, state.weights, hoverIndex);
  };
  const move = (event) => {
    const point = pointerCoordinates(canvas, event);
    if (dragIndex < 0) {
      const next = nearestPoint(state.weights, point.x, point.y);
      if (next !== hoverIndex) {
        hoverIndex = next;
        canvas.style.cursor = next < 0 ? "default" : "grab";
        redraw();
      }
      return;
    }
    state.setWeight(dragIndex, projectedWeight(
      dragIndex, state.weights.length, point.x, point.y,
    ));
    redraw();
  };
  const down = (event) => {
    const point = pointerCoordinates(canvas, event);
    dragIndex = nearestPoint(state.weights, point.x, point.y);
    if (dragIndex >= 0) {
      canvas.setPointerCapture?.(event.pointerId);
      canvas.style.cursor = "grabbing";
      event.preventDefault?.();
    }
  };
  const end = (event) => {
    if (dragIndex >= 0) canvas.releasePointerCapture?.(event.pointerId);
    dragIndex = -1;
    canvas.style.cursor = hoverIndex < 0 ? "default" : "grab";
  };
  const leave = (event) => {
    end(event);
    hoverIndex = -1;
    redraw();
  };

  const listeners = [
    ["pointerdown", down], ["pointermove", move], ["pointerup", end],
    ["pointercancel", end], ["pointerleave", leave],
  ];
  listeners.forEach(([name, listener]) => canvas.addEventListener(name, listener));
  redraw();
  return {
    canvas,
    redraw,
    destroy() {
      if (destroyed) return;
      destroyed = true;
      listeners.forEach(([name, listener]) => canvas.removeEventListener(name, listener));
      container.replaceChildren();
    },
  };
}


function commitState(state) {
  state.sync.setValue(formatWeights(state.weights));
  state.controller?.redraw();
}


function setCount(state, count) {
  const nextCount = clampAxes(count);
  state.weights = resizeWeights(state.weights, state.remembered, nextCount);
  syncOutputs(state.node, nextCount);
  commitState(state);
}


function removeRadar(node) {
  const state = states.get(node);
  if (!state) return;
  state.unsubscribeAxes();
  state.controller?.destroy();
  states.delete(node);
}


export function installRadar(node) {
  removeRadar(node);
  const axes = node.widgets.get("axes_count");
  const sync = node.widgets.get("_weights_sync");
  if (!axes || !sync) throw new Error("Radar Weights is missing its state widgets");

  const count = clampAxes(axes.getValue());
  const state = {
    node,
    axes,
    sync,
    remembered: new Map(),
    weights: parseWeights(sync.getValue(), count),
    controller: undefined,
    unsubscribeAxes: () => {},
    setWeight(index, value) {
      if (index < 0 || index >= state.weights.length) return;
      state.weights[index] = clampWeight(value);
      state.remembered.set(index, state.weights[index]);
      commitState(state);
    },
  };
  state.weights.forEach((value, index) => state.remembered.set(index, value));
  states.set(node, state);
  syncOutputs(node, count);
  commitState(state);
  state.unsubscribeAxes = axes.on("change", (value) => setCount(state, value));

  node.setSizeConstraints({
    minWidth: NODE_WIDTH, maxWidth: NODE_WIDTH,
    minHeight: NODE_HEIGHT, maxHeight: NODE_HEIGHT,
  });
  node.setSize({ width: NODE_WIDTH, height: NODE_HEIGHT });
  node.widgets.mount({
    name: "radar_weights_display",
    height: CANVAS_SIZE,
    hideOnZoom: false,
    serialize: false,
    sendToPrompt: false,
    render(container) {
      state.controller?.destroy();
      state.controller = mountRadar(container, state);
    },
    destroy() {
      state.controller?.destroy();
      state.controller = undefined;
    },
  });
}


function restoreRadar(node) {
  const state = states.get(node);
  if (!state) return;
  const count = clampAxes(state.axes.getValue());
  state.weights = parseWeights(state.sync.getValue(), count);
  state.weights.forEach((value, index) => state.remembered.set(index, value));
  syncOutputs(node, count);
  commitState(state);
}


comfy.defs.extend("RadarWeightsNode", (builder) => {
  builder.hideWidget("_weights_sync");
  builder.onCreated((node) => installRadar(node));
  builder.onConfigured((node) => restoreRadar(node));
  builder.onRemoved((node) => removeRadar(node));
});
