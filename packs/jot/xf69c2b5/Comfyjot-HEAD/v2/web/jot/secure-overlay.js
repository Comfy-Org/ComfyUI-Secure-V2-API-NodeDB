import { comfy } from "/comfy/api/v2.js";

const DATA_KEY = "comfyjot";
const DATA_VERSION = 2;
const MAX_HISTORY = 60;
const MAX_SNAPSHOT_EDGE = 1600;
const DEFAULT_COLOR = "#ffb347";
const SWATCHES = [
  "#ffb347", "#ff6b6b", "#ffd166", "#7bdff2",
  "#7ae582", "#c4b5fd", "#f8fafc", "#111827",
];

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function emptyDocument() {
  return { version: DATA_VERSION, strokes: [], snapshot: null };
}

function cloneDocument(documentData) {
  return structuredClone(documentData);
}

function normalizeDocument(value) {
  if (!value || typeof value !== "object" || !Array.isArray(value.strokes)) {
    return emptyDocument();
  }
  const strokes = value.strokes.flatMap((stroke, index) => {
    if (!stroke || typeof stroke !== "object" || !Array.isArray(stroke.points)) return [];
    const points = stroke.points.flatMap((point) => {
      if (!Array.isArray(point) || point.length < 2) return [];
      const x = Number(point[0]);
      const y = Number(point[1]);
      return Number.isFinite(x) && Number.isFinite(y) ? [[x, y]] : [];
    });
    if (!points.length) return [];
    return [{
      id: typeof stroke.id === "string" ? stroke.id : `stroke-${index}`,
      tool: stroke.tool === "eraser" ? "eraser" : "brush",
      color: typeof stroke.color === "string" ? stroke.color : DEFAULT_COLOR,
      size: clamp(Number(stroke.size) || 10, 1, 256),
      points,
    }];
  });
  return {
    version: DATA_VERSION,
    strokes,
    snapshot: value.snapshot && typeof value.snapshot === "object"
      ? value.snapshot
      : null,
  };
}

function strokeBounds(stroke) {
  const padding = Math.max(stroke.size / 2, 8);
  const xs = stroke.points.map(([x]) => x);
  const ys = stroke.points.map(([, y]) => y);
  return {
    minX: Math.min(...xs) - padding,
    minY: Math.min(...ys) - padding,
    maxX: Math.max(...xs) + padding,
    maxY: Math.max(...ys) + padding,
  };
}

function documentBounds(strokes) {
  if (!strokes.length) return null;
  return strokes.map(strokeBounds).reduce((all, bounds) => ({
    minX: Math.min(all.minX, bounds.minX),
    minY: Math.min(all.minY, bounds.minY),
    maxX: Math.max(all.maxX, bounds.maxX),
    maxY: Math.max(all.maxY, bounds.maxY),
  }));
}

function drawStroke(context, stroke, project, widthScale = 1) {
  if (!stroke.points.length) return;
  const width = Math.max(1.2, stroke.size * widthScale);
  context.save();
  context.globalCompositeOperation = stroke.tool === "eraser"
    ? "destination-out"
    : "source-over";
  context.strokeStyle = stroke.color;
  context.fillStyle = stroke.color;
  context.lineCap = "round";
  context.lineJoin = "round";
  context.lineWidth = width;
  const start = project(stroke.points[0]);
  if (stroke.points.length === 1) {
    context.beginPath();
    context.arc(start.x, start.y, width / 2, 0, Math.PI * 2);
    context.fill();
  } else {
    context.beginPath();
    context.moveTo(start.x, start.y);
    for (const point of stroke.points.slice(1)) {
      const next = project(point);
      context.lineTo(next.x, next.y);
    }
    context.stroke();
  }
  context.restore();
}

function bytesToBase64(bytes) {
  let binary = "";
  for (let offset = 0; offset < bytes.length; offset += 32768) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 32768));
  }
  return btoa(binary);
}

function style(element, values) {
  Object.assign(element.style, values);
  return element;
}

function button(label, run) {
  const element = document.createElement("button");
  element.type = "button";
  element.textContent = label;
  element.addEventListener("click", run);
  return style(element, {
    border: "1px solid #64748b",
    borderRadius: "8px",
    background: "#1e293b",
    color: "#f8fafc",
    padding: "7px 10px",
    cursor: "pointer",
  });
}

export class ComfyJot {
  constructor() {
    this.documentData = emptyDocument();
    this.history = [];
    this.future = [];
    this.visible = false;
    this.editMode = false;
    this.notesVisible = true;
    this.tool = "brush";
    this.color = DEFAULT_COLOR;
    this.brushSize = 10;
    this.activeStroke = null;
    this.activePointerId = null;
    this.viewport = null;
    this.controls = {};
  }

  async mount() {
    this.brushSize = clamp(Number(
      comfy.settings.get("ComfyJot.Settings.DefaultBrushSize") ?? 10,
    ), 1, 48);
    this.overlay = comfy.ui.mountGraphOverlay({
      id: "ComfyJot.notes",
      ariaLabel: "Comfy Jot canvas notes",
      visible: false,
      interactive: false,
      draw: (context, size, viewport) => this.draw(context, size, viewport),
      onPointerDown: (event) => this.pointerDown(event),
      onPointerMove: (event) => this.pointerMove(event),
      onPointerUp: (event) => this.pointerUp(event),
      onPointerCancel: (event) => this.pointerCancel(event),
      onKeyDown: (event) => this.keyDown(event),
    });
    this.panel = comfy.ui.mountViewportPanel({
      id: "ComfyJot.tools",
      anchor: "bottom-center",
      offsetY: 16,
      width: 720,
      maxHeight: 180,
      ariaLabel: "Comfy Jot tools",
      render: (container) => this.renderTools(container),
    });
    await this.loadFromWorkflow();
  }

  renderTools(container) {
    const root = style(document.createElement("section"), {
      display: "flex", flexWrap: "wrap", alignItems: "center", gap: "8px",
      padding: "10px", background: "#0f172a", color: "#f8fafc",
      borderRadius: "12px", fontFamily: "sans-serif",
    });
    const ink = button("Ink Off", () => this.toggleEditMode());
    const brush = button("Brush", () => this.setTool("brush"));
    const eraser = button("Eraser", () => this.setTool("eraser"));
    const undo = button("Undo", () => this.undo());
    const redo = button("Redo", () => this.redo());
    const clear = button("Clear", () => this.clear());
    const notes = button("Hide Notes", () => this.toggleNotes());
    const size = document.createElement("input");
    size.type = "range";
    size.min = "1";
    size.max = "48";
    size.step = "1";
    size.value = String(this.brushSize);
    size.title = "Brush size";
    size.addEventListener("input", () => this.setBrushSize(size.value));
    const color = document.createElement("input");
    color.type = "color";
    color.value = this.color;
    color.title = "Brush color";
    color.addEventListener("input", () => {
      this.color = color.value || DEFAULT_COLOR;
      this.syncControls();
    });
    const swatches = SWATCHES.map((value) => {
      const swatch = button("", () => {
        this.color = value;
        color.value = value;
        this.syncControls();
      });
      swatch.title = value;
      style(swatch, { background: value, width: "26px", height: "26px", padding: "0" });
      return swatch;
    });
    root.append(ink, brush, eraser, size, color, ...swatches, undo, redo, clear, notes);
    container.append(root);
    this.controls = { root, ink, brush, eraser, undo, redo, clear, notes, size, color };
    this.syncControls();
  }

  syncControls() {
    const { root, ink, brush, eraser, undo, redo, clear, notes, size, color } = this.controls;
    if (!root) return;
    root.hidden = !this.visible;
    ink.textContent = this.editMode ? "Ink On" : "Ink Off";
    brush.disabled = this.tool === "brush";
    eraser.disabled = this.tool === "eraser";
    undo.disabled = !this.history.length;
    redo.disabled = !this.future.length;
    clear.disabled = !this.documentData.strokes.length;
    notes.textContent = this.notesVisible ? "Hide Notes" : "Show Notes";
    size.value = String(this.brushSize);
    color.value = this.color;
  }

  setVisible(value) {
    this.visible = Boolean(value);
    if (!this.visible) this.editMode = false;
    this.overlay.setVisible(this.visible);
    this.overlay.setInteractive(this.visible && this.editMode);
    this.syncControls();
    this.overlay.redraw();
  }

  toggleVisible() {
    this.setVisible(!this.visible);
  }

  toggleEditMode() {
    if (!this.visible) this.visible = true;
    this.editMode = !this.editMode;
    if (this.editMode) this.notesVisible = true;
    else this.cancelStroke();
    this.overlay.setVisible(true);
    this.overlay.setInteractive(this.editMode);
    this.syncControls();
    this.overlay.redraw();
  }

  toggleNotes() {
    this.notesVisible = !this.notesVisible;
    if (!this.notesVisible) {
      this.editMode = false;
      this.cancelStroke();
      this.overlay.setInteractive(false);
    }
    this.syncControls();
    this.overlay.redraw();
  }

  setTool(tool) {
    this.tool = tool === "eraser" ? "eraser" : "brush";
    this.syncControls();
  }

  setBrushSize(value) {
    this.brushSize = clamp(Number(value) || 10, 1, 48);
    this.syncControls();
  }

  pushHistory() {
    this.history.push(cloneDocument(this.documentData));
    if (this.history.length > MAX_HISTORY) this.history.shift();
    this.future = [];
  }

  async loadFromWorkflow() {
    this.documentData = normalizeDocument(await comfy.workflow.getExtra(DATA_KEY));
    this.history = [];
    this.future = [];
    this.editMode = false;
    this.activeStroke = null;
    const show = this.documentData.strokes.length > 0 &&
      comfy.settings.get("ComfyJot.Settings.ShowExistingOnLoad") !== false;
    this.setVisible(show);
  }

  async persist() {
    this.documentData.snapshot = await this.snapshot();
    await comfy.workflow.setExtra(
      DATA_KEY,
      this.documentData.strokes.length ? this.documentData : undefined,
    );
    this.syncControls();
    this.overlay.redraw();
  }

  async undo() {
    if (!this.history.length) return;
    this.future.push(cloneDocument(this.documentData));
    this.documentData = this.history.pop();
    await this.persist();
  }

  async redo() {
    if (!this.future.length) return;
    this.history.push(cloneDocument(this.documentData));
    this.documentData = this.future.pop();
    await this.persist();
  }

  async clear() {
    if (!this.documentData.strokes.length) return;
    this.pushHistory();
    this.documentData = emptyDocument();
    await this.persist();
  }

  pointerDown(event) {
    if (!this.editMode || (event.button !== 0 && event.pointerType !== "touch" && event.pointerType !== "pen")) return;
    this.activePointerId = event.pointerId;
    this.activeStroke = {
      id: `jot-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
      tool: this.tool, color: this.color, size: this.brushSize,
      points: [[event.graph.x, event.graph.y]],
    };
    this.overlay.redraw();
  }

  pointerMove(event) {
    if (!this.activeStroke || event.pointerId !== this.activePointerId) return;
    const point = [event.graph.x, event.graph.y];
    const previous = this.activeStroke.points.at(-1);
    const distance = Math.hypot(point[0] - previous[0], point[1] - previous[1]);
    if (distance < 0.6 / Math.max(this.viewport?.scale ?? 1, 0.0001)) return;
    this.activeStroke.points.push(point);
    this.overlay.redraw();
  }

  async pointerUp(event) {
    if (!this.activeStroke || event.pointerId !== this.activePointerId) return;
    this.pushHistory();
    this.documentData.strokes.push(this.activeStroke);
    this.cancelStroke();
    await this.persist();
  }

  pointerCancel(event) {
    if (event.pointerId === this.activePointerId) this.cancelStroke();
  }

  async keyDown(event) {
    if (!this.editMode || (!event.ctrlKey && !event.metaKey) || event.repeat) return;
    const key = event.key.toLowerCase();
    if (key === "z" && event.shiftKey) await this.redo();
    else if (key === "z") await this.undo();
    else if (key === "y") await this.redo();
  }

  cancelStroke() {
    this.activeStroke = null;
    this.activePointerId = null;
    this.overlay?.redraw();
  }

  draw(context, _size, viewport) {
    this.viewport = viewport;
    if (!this.notesVisible) return;
    const project = ([x, y]) => viewport.graphToViewport({ x, y });
    for (const stroke of this.documentData.strokes) {
      drawStroke(context, stroke, project, viewport.scale);
    }
    if (this.activeStroke) {
      drawStroke(context, this.activeStroke, project, viewport.scale);
    }
  }

  async snapshot() {
    const bounds = documentBounds(this.documentData.strokes);
    if (!bounds) return null;
    const graphWidth = Math.max(1, bounds.maxX - bounds.minX);
    const graphHeight = Math.max(1, bounds.maxY - bounds.minY);
    const scale = Math.min(1, MAX_SNAPSHOT_EDGE / Math.max(graphWidth, graphHeight));
    const width = Math.max(1, Math.ceil(graphWidth * scale));
    const height = Math.max(1, Math.ceil(graphHeight * scale));
    const canvas = new OffscreenCanvas(width, height);
    const context = canvas.getContext("2d");
    if (!context) return null;
    const project = ([x, y]) => ({
      x: (x - bounds.minX) * scale,
      y: (y - bounds.minY) * scale,
    });
    for (const stroke of this.documentData.strokes) {
      drawStroke(context, stroke, project, scale);
    }
    const blob = await canvas.convertToBlob({ type: "image/png" });
    const bytes = new Uint8Array(await blob.arrayBuffer());
    return {
      mimeType: "image/png",
      image: `data:image/png;base64,${bytesToBase64(bytes)}`,
      width, height,
      bounds: [bounds.minX, bounds.minY, graphWidth, graphHeight],
    };
  }
}
