import { comfy } from "/comfy/api/v2.js";

const NODE_TYPES = ["Bleach Bypass", "RGB Curve"];
const views = new WeakMap();

export function normalizedTanh(value, slope, offset) {
  const start = Math.tanh(slope * -offset);
  const end = Math.tanh(slope * (1 - offset));
  return (Math.tanh(slope * (value - offset)) - start) / (end - start);
}

export class CurveView {
  constructor(container, slope, offset) {
    this.container = container;
    this.slope = slope;
    this.offset = offset;
    this.canvas = container.ownerDocument.createElement("canvas");
    this.canvas.setAttribute("aria-label", "RGB curve preview");
    this.canvas.style.boxSizing = "border-box";
    this.canvas.style.width = "100%";
    this.canvas.style.height = "220px";
    this.canvas.style.display = "block";
    this.container.replaceChildren(this.canvas);
    this.stops = [
      slope.on("change", () => this.draw()),
      offset.on("change", () => this.draw()),
    ];
    this.resize();
  }

  resize() {
    const width = Math.max(1, Math.floor(this.container.clientWidth || 300));
    const height = 220;
    if (this.canvas.width !== width) this.canvas.width = width;
    if (this.canvas.height !== height) this.canvas.height = height;
    this.draw();
  }

  draw() {
    const context = this.canvas.getContext("2d");
    if (!context) return;
    const width = this.canvas.width;
    const height = this.canvas.height;
    context.clearRect(0, 0, width, height);
    context.strokeStyle = "#777";
    context.lineWidth = 1;
    context.setLineDash([4, 4]);
    for (let part = 1; part < 5; part += 1) {
      const x = (width * part) / 5;
      const y = (height * part) / 5;
      context.beginPath();
      context.moveTo(x, 0);
      context.lineTo(x, height);
      context.stroke();
      context.beginPath();
      context.moveTo(0, y);
      context.lineTo(width, y);
      context.stroke();
    }
    context.setLineDash([]);
    context.strokeRect(0.5, 0.5, width - 1, height - 1);

    const slope = Number(this.slope.getValue());
    const offset = Number(this.offset.getValue());
    if (!Number.isFinite(slope) || !Number.isFinite(offset)) return;
    context.strokeStyle = "#e45b5b";
    context.lineWidth = 3;
    context.beginPath();
    for (let index = 0; index < 100; index += 1) {
      const value = index / 99;
      const x = value * width;
      const y = (1 - normalizedTanh(value, slope, offset)) * height;
      if (index === 0) context.moveTo(x, y);
      else context.lineTo(x, y);
    }
    context.stroke();
  }

  destroy() {
    for (const stop of this.stops.splice(0)) stop();
    this.container.replaceChildren();
  }
}

function mountCurve(node) {
  if (node.widgets.get("m3d_curve_preview")) return;
  const slope = node.widgets.get("slope");
  const offset = node.widgets.get("shadow_offset");
  if (!slope || !offset) return;
  node.setSizeConstraints({ minWidth: 280, minHeight: 350 });
  let view;
  node.widgets.mount({
    name: "m3d_curve_preview",
    height: 230,
    hideOnZoom: false,
    serialize: false,
    sendToPrompt: false,
    render(container) {
      view = new CurveView(container, slope, offset);
      views.set(node, view);
    },
    destroy() {
      view?.destroy();
      views.delete(node);
    },
  });
}

comfy.defs.extend(NODE_TYPES, (builder) => {
  builder.onCreated((node) => mountCurve(node));
  builder.onResized((node) => views.get(node)?.resize());
  builder.onRemoved((node) => {
    views.get(node)?.destroy();
    views.delete(node);
  });
});
