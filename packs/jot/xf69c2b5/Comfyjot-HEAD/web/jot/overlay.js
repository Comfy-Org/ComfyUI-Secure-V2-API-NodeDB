import { app } from "/scripts/app.js";

import {
  BRUSH_SIZE_MAX,
  BRUSH_SIZE_MIN,
  DEFAULT_BRUSH_SIZE,
  DEFAULT_COLOR,
  DEFAULT_SWATCHES,
  SETTINGS,
  TOOLS,
  TOOL_LABELS,
} from "./constants.js";
import { cloneDocument, createEmptyDocument, readDocumentFromGraph, writeDocumentToGraph } from "./graph-store.js";
import { ensureStyles } from "./styles.js";

const SNAPSHOT_MAX_EDGE = 1600;
const SNAPSHOT_MIME_TYPE = "image/png";

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function lerp(start, end, amount) {
  return start + (end - start) * amount;
}

function makeStrokeId() {
  return `jot-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

function getDistance(a, b) {
  const dx = a[0] - b[0];
  const dy = a[1] - b[1];
  return Math.hypot(dx, dy);
}

function getSettingValue(getSetting, settingId, fallback) {
  const value = getSetting?.(settingId);
  return value ?? fallback;
}

function getBooleanSetting(getSetting, settingId, fallback) {
  return Boolean(getSettingValue(getSetting, settingId, fallback));
}

function getNumberSetting(getSetting, settingId, fallback, min, max) {
  const value = Number(getSettingValue(getSetting, settingId, fallback));
  if (!Number.isFinite(value)) {
    return fallback;
  }
  return clamp(value, min, max);
}

function getCanvasTransform() {
  const ds = app.canvas?.ds || app.canvas?.dragAndScale;
  const scale = Number(ds?.scale) || 1;
  const offset = Array.isArray(ds?.offset) ? ds.offset : [0, 0];
  return {
    scale,
    offsetX: Number(offset[0]) || 0,
    offsetY: Number(offset[1]) || 0,
  };
}

function graphToViewportPoint(point) {
  const canvas = app.canvas;
  if (canvas?.convertOffsetToCanvas) {
    return canvas.convertOffsetToCanvas(point);
  }

  const { scale, offsetX, offsetY } = getCanvasTransform();
  return [(point[0] + offsetX) * scale, (point[1] + offsetY) * scale];
}

function pointerEventToGraphPoint(event) {
  const canvas = app.canvas;
  if (canvas?.convertEventToCanvasOffset) {
    return canvas.convertEventToCanvasOffset(event);
  }

  const rect = canvas?.canvas?.getBoundingClientRect?.();
  if (!rect) {
    return null;
  }

  const { scale, offsetX, offsetY } = getCanvasTransform();
  const localX = event.clientX - rect.left;
  const localY = event.clientY - rect.top;
  return [localX / scale - offsetX, localY / scale - offsetY];
}

function forwardWheelEventToCanvas(event) {
  const target = app.canvas?.canvas || app.canvasEl || null;
  if (!(target instanceof EventTarget) || target === event.currentTarget) {
    return false;
  }

  const forwardedEvent = new WheelEvent("wheel", {
    bubbles: true,
    cancelable: true,
    composed: true,
    view: window,
    clientX: event.clientX,
    clientY: event.clientY,
    screenX: event.screenX,
    screenY: event.screenY,
    deltaX: event.deltaX,
    deltaY: event.deltaY,
    deltaZ: event.deltaZ,
    deltaMode: event.deltaMode,
    altKey: event.altKey,
    ctrlKey: event.ctrlKey,
    metaKey: event.metaKey,
    shiftKey: event.shiftKey,
  });

  return target.dispatchEvent(forwardedEvent);
}

function unionBounds(currentBounds, nextBounds) {
  if (!nextBounds) {
    return currentBounds;
  }
  if (!currentBounds) {
    return { ...nextBounds };
  }

  return {
    minX: Math.min(currentBounds.minX, nextBounds.minX),
    minY: Math.min(currentBounds.minY, nextBounds.minY),
    maxX: Math.max(currentBounds.maxX, nextBounds.maxX),
    maxY: Math.max(currentBounds.maxY, nextBounds.maxY),
  };
}

function getStrokeBounds(stroke) {
  if (!stroke?.points?.length) {
    return null;
  }

  const padding = Math.max((Number(stroke.size) || 0) * 0.5, 8);
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;

  for (const point of stroke.points) {
    minX = Math.min(minX, point[0]);
    minY = Math.min(minY, point[1]);
    maxX = Math.max(maxX, point[0]);
    maxY = Math.max(maxY, point[1]);
  }

  if (![minX, minY, maxX, maxY].every(Number.isFinite)) {
    return null;
  }

  return {
    minX: minX - padding,
    minY: minY - padding,
    maxX: maxX + padding,
    maxY: maxY + padding,
  };
}

export class ComfyJotOverlay {
  constructor({ getSettingValue: getSettingValueFn, toast }) {
    this.getSettingValue = getSettingValueFn;
    this.toast = toast;

    this.documentData = createEmptyDocument();
    this.history = [];
    this.future = [];

    this.visible = false;
    this.editMode = false;
    this.notesVisible = true;
    this.activeTool = TOOLS.BRUSH;
    this.brushSize = getNumberSetting(
      this.getSettingValue,
      SETTINGS.DEFAULT_BRUSH_SIZE,
      DEFAULT_BRUSH_SIZE,
      BRUSH_SIZE_MIN,
      BRUSH_SIZE_MAX,
    );
    this.color = DEFAULT_COLOR;

    this.rootEl = null;
    this.canvasEl = null;
    this.canvasCtx = null;
    this.railEl = null;
    this.resizeObserver = null;
    this.hostEl = null;

    this.buttons = {};
    this.sizeLabelEl = null;
    this.sizePreviewEl = null;
    this.sizeDotEl = null;
    this.sizeInputEl = null;
    this.colorInputEl = null;
    this.swatchEls = [];

    this.lastRenderSignature = "";
    this.needsRender = true;
    this.rafId = null;

    this.activeStroke = null;
    this.activePointerId = null;
    this.boundPointerDown = (event) => this.onPointerDown(event);
    this.boundPointerMove = (event) => this.onPointerMove(event);
    this.boundPointerUp = (event) => this.onPointerUp(event);
    this.boundPointerCancel = (event) => this.onPointerCancel(event);
    this.boundWheel = (event) => this.onWheel(event);
  }

  isVisible() {
    return this.visible;
  }

  ensureMounted() {
    ensureStyles();

    const nextHost =
      document.getElementById("graph-canvas-container") ||
      document.querySelector(".graph-canvas-container") ||
      app.canvasEl?.parentElement ||
      null;

    if (!nextHost) {
      return false;
    }

    if (!this.rootEl) {
      this.createDom();
    }

    if (this.hostEl !== nextHost || !this.rootEl.isConnected) {
      this.hostEl = nextHost;
      this.hostEl.appendChild(this.rootEl);
      this.observeHost();
      this.needsRender = true;
    }

    return true;
  }

  createDom() {
    this.rootEl = document.createElement("div");
    this.rootEl.className = "comfyjot-root";
    this.rootEl.hidden = true;

    this.canvasEl = document.createElement("canvas");
    this.canvasEl.className = "comfyjot-surface";
    this.canvasEl.addEventListener("pointerdown", this.boundPointerDown);
    this.canvasEl.addEventListener("pointermove", this.boundPointerMove);
    this.canvasEl.addEventListener("pointerup", this.boundPointerUp);
    this.canvasEl.addEventListener("pointercancel", this.boundPointerCancel);
    this.canvasEl.addEventListener("wheel", this.boundWheel, { passive: false });
    this.canvasCtx = this.canvasEl.getContext("2d");

    this.railEl = document.createElement("div");
    this.railEl.className = "comfyjot-rail";

    const brandStack = document.createElement("div");
    brandStack.className = "comfyjot-brand";
    const brandLabel = document.createElement("div");
    brandLabel.className = "comfyjot-brand__label";
    brandLabel.textContent = "Comfy Jot";
    const inkButton = this.makePillButton("Ink", () => this.toggleEditMode());
    inkButton.classList.add("comfyjot-pill--ink");
    brandStack.append(brandLabel, inkButton);

    const toolGrid = document.createElement("div");
    toolGrid.className = "comfyjot-grid comfyjot-grid--tools comfyjot-cluster";
    const brushButton = this.makeIconButton("pi pi-pencil", TOOL_LABELS[TOOLS.BRUSH], () =>
      this.setTool(TOOLS.BRUSH),
    );
    const eraserButton = this.makeIconButton("pi pi-eraser", TOOL_LABELS[TOOLS.ERASER], () =>
      this.setTool(TOOLS.ERASER),
    );
    toolGrid.append(brushButton, eraserButton);

    const sizeSection = document.createElement("div");
    sizeSection.className = "comfyjot-size comfyjot-cluster";
    const sizeLabel = document.createElement("div");
    sizeLabel.className = "comfyjot-size__label";
    const sizeTitle = document.createElement("span");
    sizeTitle.textContent = "Brush";
    this.sizeLabelEl = document.createElement("strong");
    sizeLabel.append(sizeTitle, this.sizeLabelEl);

    const sizeSlider = document.createElement("div");
    sizeSlider.className = "comfyjot-size__slider";
    this.sizePreviewEl = sizeSlider;
    this.sizeDotEl = document.createElement("div");
    this.sizeDotEl.className = "comfyjot-size__dot";

    this.sizeInputEl = document.createElement("input");
    this.sizeInputEl.className = "comfyjot-size__input";
    this.sizeInputEl.type = "range";
    this.sizeInputEl.min = String(BRUSH_SIZE_MIN);
    this.sizeInputEl.max = String(BRUSH_SIZE_MAX);
    this.sizeInputEl.step = "1";
    this.sizeInputEl.setAttribute("aria-label", "Brush size");
    this.sizeInputEl.addEventListener("input", (event) => {
      this.setBrushSize(Number(event.currentTarget?.value));
    });
    sizeSlider.append(this.sizeDotEl, this.sizeInputEl);
    sizeSection.append(sizeLabel, sizeSlider);

    const colorSection = document.createElement("div");
    colorSection.className = "comfyjot-color comfyjot-cluster";
    this.colorInputEl = document.createElement("input");
    this.colorInputEl.className = "comfyjot-color__picker";
    this.colorInputEl.type = "color";
    this.colorInputEl.addEventListener("input", (event) => {
      this.setColor(event.currentTarget?.value || DEFAULT_COLOR);
    });
    colorSection.appendChild(this.colorInputEl);

    const swatchGrid = document.createElement("div");
    swatchGrid.className = "comfyjot-swatch-grid";
    this.swatchEls = DEFAULT_SWATCHES.map((swatch) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "comfyjot-swatch";
      button.style.background = swatch;
      button.title = swatch;
      button.addEventListener("click", () => this.setColor(swatch));
      swatchGrid.appendChild(button);
      return button;
    });
    colorSection.appendChild(swatchGrid);

    const divider = document.createElement("div");
    divider.className = "comfyjot-divider";

    const actionGrid = document.createElement("div");
    actionGrid.className = "comfyjot-grid comfyjot-grid--actions comfyjot-cluster";
    const undoButton = this.makeIconButton("pi pi-undo", "Undo stroke", () => this.undo());
    const redoButton = this.makeIconButton("pi pi-undo", "Redo stroke", () => this.redo());
    redoButton.classList.add("comfyjot-icon-button--redo");
    const clearButton = this.makeIconButton("pi pi-trash", "Clear all notes", () => this.clear());
    const visibilityButton = this.makeIconButton("pi pi-eye", "Hide notes", () => this.toggleNotesVisibility());
    actionGrid.append(undoButton, redoButton, clearButton, visibilityButton);

    this.buttons = {
      ink: inkButton,
      brush: brushButton,
      eraser: eraserButton,
      undo: undoButton,
      redo: redoButton,
      clear: clearButton,
      visibility: visibilityButton,
    };

    this.railEl.append(brandStack, toolGrid, sizeSection, colorSection, divider, actionGrid);
    this.rootEl.append(this.canvasEl, this.railEl);

    this.syncControls();
  }

  observeHost() {
    this.resizeObserver?.disconnect();
    if (!this.hostEl || typeof ResizeObserver !== "function") {
      return;
    }

    this.resizeObserver = new ResizeObserver(() => {
      this.needsRender = true;
    });
    this.resizeObserver.observe(this.hostEl);
  }

  makePillButton(label, onClick) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "comfyjot-pill";
    button.textContent = label;
    button.addEventListener("click", onClick);
    return button;
  }

  makeIconButton(iconClass, title, onClick) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "comfyjot-icon-button";
    button.title = title;
    button.innerHTML = `<i class="${iconClass}"></i>`;
    button.addEventListener("click", onClick);
    return button;
  }

  syncControls() {
    if (!this.rootEl) {
      return;
    }

    this.rootEl.hidden = !this.visible;
    this.canvasEl.classList.toggle("is-editing", this.visible && this.editMode);

    this.buttons.ink?.classList.toggle("is-active", this.editMode);
    this.buttons.ink && (this.buttons.ink.textContent = this.editMode ? "Ink On" : "Ink Off");
    this.buttons.brush?.classList.toggle("is-active", this.activeTool === TOOLS.BRUSH);
    this.buttons.eraser?.classList.toggle("is-active", this.activeTool === TOOLS.ERASER);
    this.buttons.visibility?.classList.toggle("is-active", this.notesVisible);
    if (this.buttons.visibility) {
      this.buttons.visibility.title = this.notesVisible ? "Hide notes" : "Show notes";
      this.buttons.visibility.innerHTML = `<i class="pi ${this.notesVisible ? "pi-eye" : "pi-eye-slash"}"></i>`;
    }

    if (this.sizeLabelEl) {
      this.sizeLabelEl.textContent = `${Math.round(this.brushSize)}px`;
    }
    if (this.sizeDotEl) {
      const brushSpan = Math.max(1, BRUSH_SIZE_MAX - BRUSH_SIZE_MIN);
      const ratio = clamp((this.brushSize - BRUSH_SIZE_MIN) / brushSpan, 0, 1);
      const previewSize = Math.round(lerp(6, 30, ratio));
      this.sizePreviewEl?.style.setProperty("--comfyjot-brush-ratio", ratio.toFixed(3));
      this.sizePreviewEl?.style.setProperty("--comfyjot-brush-dot-size", `${previewSize}px`);
      this.sizeDotEl.style.width = `${previewSize}px`;
      this.sizeDotEl.style.height = `${previewSize}px`;
      this.sizeDotEl.style.background = this.activeTool === TOOLS.ERASER ? "transparent" : this.color;
      this.sizeDotEl.style.border =
        this.activeTool === TOOLS.ERASER ? `2px solid ${this.color}` : "none";
    }
    if (this.sizeInputEl) {
      this.sizeInputEl.value = String(this.brushSize);
    }
    if (this.colorInputEl) {
      this.colorInputEl.value = this.color;
    }

    this.swatchEls.forEach((element, index) => {
      element.classList.toggle("is-active", DEFAULT_SWATCHES[index].toLowerCase() === this.color.toLowerCase());
    });

    const hasUndo = this.history.length > 0;
    const hasRedo = this.future.length > 0;
    const hasStrokes = this.documentData.strokes.length > 0;
    this.buttons.undo && (this.buttons.undo.disabled = !hasUndo);
    this.buttons.redo && (this.buttons.redo.disabled = !hasRedo);
    this.buttons.clear && (this.buttons.clear.disabled = !hasStrokes);
  }

  setVisible(nextVisible) {
    const visible = Boolean(nextVisible);
    this.visible = visible;

    if (visible) {
      this.ensureMounted();
      this.editMode = false;
      this.cancelActiveStroke();
      this.startRenderLoop();
    } else {
      this.cancelActiveStroke();
      this.editMode = false;
      this.stopRenderLoop();
    }

    this.syncControls();
    this.needsRender = true;
    if (visible) {
      this.renderIfNeeded(true);
    }
    return this.visible;
  }

  toggleVisible(force) {
    return this.setVisible(force ?? !this.visible);
  }

  toggleEditMode(force) {
    if (!this.visible) {
      this.visible = true;
      this.ensureMounted();
      this.startRenderLoop();
    }

    this.editMode = typeof force === "boolean" ? force : !this.editMode;
    if (this.editMode) {
      this.notesVisible = true;
    } else {
      this.cancelActiveStroke();
    }
    this.syncControls();
    return this.editMode;
  }

  toggleNotesVisibility(force) {
    this.notesVisible = typeof force === "boolean" ? force : !this.notesVisible;
    if (!this.notesVisible && this.editMode) {
      this.editMode = false;
      this.cancelActiveStroke();
    }
    this.syncControls();
    this.needsRender = true;
    this.renderIfNeeded(true);
    return this.notesVisible;
  }

  setTool(tool) {
    this.activeTool = tool === TOOLS.ERASER ? TOOLS.ERASER : TOOLS.BRUSH;
    this.syncControls();
    this.needsRender = true;
  }

  setBrushSize(value) {
    const numeric = clamp(Number(value) || DEFAULT_BRUSH_SIZE, BRUSH_SIZE_MIN, BRUSH_SIZE_MAX);
    this.brushSize = numeric;
    this.syncControls();
    this.needsRender = true;
  }

  setColor(value) {
    this.color = typeof value === "string" && value ? value : DEFAULT_COLOR;
    this.syncControls();
    this.needsRender = true;
  }

  loadFromGraph() {
    this.documentData = readDocumentFromGraph(app.graph);
    this.history = [];
    this.future = [];
    this.editMode = false;
    this.cancelActiveStroke();

    if (
      this.documentData.strokes.length > 0 &&
      getBooleanSetting(this.getSettingValue, SETTINGS.SHOW_EXISTING_ON_LOAD, true)
    ) {
      this.visible = true;
      this.startRenderLoop();
    }

    this.syncControls();
    this.needsRender = true;
    this.renderIfNeeded(true);
  }

  pushHistorySnapshot() {
    this.history.push(cloneDocument(this.documentData));
    if (this.history.length > 60) {
      this.history.shift();
    }
    this.future = [];
  }

  persistDocument() {
    this.documentData = {
      ...this.documentData,
      snapshot: this.buildDocumentSnapshot(),
    };
    writeDocumentToGraph(app.graph, this.documentData);
    this.syncControls();
    this.needsRender = true;
    this.renderIfNeeded(true);
  }

  undo() {
    if (!this.history.length) {
      return;
    }

    this.future.push(cloneDocument(this.documentData));
    this.documentData = this.history.pop() || createEmptyDocument();
    this.persistDocument();
  }

  redo() {
    if (!this.future.length) {
      return;
    }

    this.history.push(cloneDocument(this.documentData));
    this.documentData = this.future.pop() || createEmptyDocument();
    this.persistDocument();
  }

  clear() {
    if (!this.documentData.strokes.length) {
      return;
    }

    this.pushHistorySnapshot();
    this.documentData = createEmptyDocument();
    this.persistDocument();
    this.toast?.add?.({
      severity: "secondary",
      summary: "Comfy Jot",
      detail: "Canvas notes cleared.",
      life: 1600,
    });
  }

  onPointerDown(event) {
    if (!this.visible || !this.editMode) {
      return;
    }
    if (event.button !== 0 && event.pointerType !== "touch" && event.pointerType !== "pen") {
      return;
    }

    const point = pointerEventToGraphPoint(event);
    if (!point) {
      return;
    }

    this.activePointerId = event.pointerId;
    this.activeStroke = {
      id: makeStrokeId(),
      tool: this.activeTool,
      color: this.color,
      size: this.brushSize,
      points: [point],
    };

    this.canvasEl.setPointerCapture?.(event.pointerId);
    this.needsRender = true;
    event.preventDefault();
    event.stopPropagation();
  }

  onPointerMove(event) {
    if (!this.activeStroke || this.activePointerId !== event.pointerId) {
      return;
    }

    const point = pointerEventToGraphPoint(event);
    if (!point) {
      return;
    }

    const previousPoint = this.activeStroke.points[this.activeStroke.points.length - 1];
    const minDistance = 0.6 / Math.max(getCanvasTransform().scale, 0.0001);
    if (getDistance(previousPoint, point) < minDistance) {
      return;
    }

    this.activeStroke.points.push(point);
    this.needsRender = true;
    event.preventDefault();
    event.stopPropagation();
  }

  onPointerUp(event) {
    if (!this.activeStroke || this.activePointerId !== event.pointerId) {
      return;
    }

    this.finishActiveStroke();
    this.canvasEl.releasePointerCapture?.(event.pointerId);
    event.preventDefault();
    event.stopPropagation();
  }

  onPointerCancel(event) {
    if (this.activePointerId === event.pointerId) {
      this.cancelActiveStroke();
    }
  }

  onWheel(event) {
    if (!this.visible || !this.editMode) {
      return;
    }

    const forwarded = forwardWheelEventToCanvas(event);
    if (!forwarded || event.cancelable) {
      event.preventDefault();
    }
    event.stopPropagation();
  }

  finishActiveStroke() {
    if (!this.activeStroke) {
      return;
    }

    this.pushHistorySnapshot();
    this.documentData = {
      ...this.documentData,
      strokes: [...this.documentData.strokes, this.activeStroke],
    };
    this.activeStroke = null;
    this.activePointerId = null;
    this.persistDocument();
  }

  cancelActiveStroke() {
    this.activeStroke = null;
    this.activePointerId = null;
    this.needsRender = true;
  }

  resizeCanvasIfNeeded() {
    if (!this.canvasEl || !this.hostEl) {
      return false;
    }

    const rect = this.hostEl.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const width = Math.max(1, Math.round(rect.width * dpr));
    const height = Math.max(1, Math.round(rect.height * dpr));

    if (this.canvasEl.width === width && this.canvasEl.height === height) {
      return false;
    }

    this.canvasEl.width = width;
    this.canvasEl.height = height;
    this.canvasEl.style.width = `${rect.width}px`;
    this.canvasEl.style.height = `${rect.height}px`;
    this.needsRender = true;
    return true;
  }

  getDocumentBounds() {
    return this.documentData.strokes.reduce(
      (bounds, stroke) => unionBounds(bounds, getStrokeBounds(stroke)),
      null,
    );
  }

  renderStrokeSnapshot(ctx, stroke, { originX, originY, scale }) {
    if (!stroke.points.length) {
      return;
    }

    const width = Math.max(1.2, stroke.size * scale);
    const projectPoint = (point) => [
      (point[0] - originX) * scale,
      (point[1] - originY) * scale,
    ];

    ctx.save();
    ctx.globalCompositeOperation = stroke.tool === TOOLS.ERASER ? "destination-out" : "source-over";
    ctx.strokeStyle = stroke.color;
    ctx.fillStyle = stroke.color;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.lineWidth = width;

    const [startX, startY] = projectPoint(stroke.points[0]);
    if (stroke.points.length === 1) {
      ctx.beginPath();
      ctx.arc(startX, startY, width / 2, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
      return;
    }

    ctx.beginPath();
    ctx.moveTo(startX, startY);
    for (let index = 1; index < stroke.points.length; index += 1) {
      const [x, y] = projectPoint(stroke.points[index]);
      ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.restore();
  }

  buildDocumentSnapshot() {
    if (!this.documentData.strokes.length) {
      return null;
    }

    const bounds = this.getDocumentBounds();
    if (!bounds) {
      return null;
    }

    const graphWidth = Math.max(1, bounds.maxX - bounds.minX);
    const graphHeight = Math.max(1, bounds.maxY - bounds.minY);
    const longestEdge = Math.max(graphWidth, graphHeight);
    const scale = longestEdge > SNAPSHOT_MAX_EDGE ? SNAPSHOT_MAX_EDGE / longestEdge : 1;
    const width = Math.max(1, Math.ceil(graphWidth * scale));
    const height = Math.max(1, Math.ceil(graphHeight * scale));

    const snapshotCanvas = document.createElement("canvas");
    snapshotCanvas.width = width;
    snapshotCanvas.height = height;

    const ctx = snapshotCanvas.getContext("2d");
    if (!ctx) {
      return null;
    }

    ctx.clearRect(0, 0, width, height);
    for (const stroke of this.documentData.strokes) {
      this.renderStrokeSnapshot(ctx, stroke, {
        originX: bounds.minX,
        originY: bounds.minY,
        scale,
      });
    }

    return {
      mimeType: SNAPSHOT_MIME_TYPE,
      image: snapshotCanvas.toDataURL(SNAPSHOT_MIME_TYPE),
      width,
      height,
      bounds: [bounds.minX, bounds.minY, graphWidth, graphHeight],
    };
  }

  getRenderSignature() {
    const rect = this.hostEl?.getBoundingClientRect();
    const { scale, offsetX, offsetY } = getCanvasTransform();
    const width = rect ? Math.round(rect.width) : 0;
    const height = rect ? Math.round(rect.height) : 0;
    return [
      width,
      height,
      scale,
      offsetX,
      offsetY,
      this.documentData.strokes.length,
      this.activeStroke?.points.length || 0,
      this.brushSize,
      this.color,
      this.activeTool,
      this.editMode,
      this.notesVisible,
      this.visible,
    ].join("|");
  }

  renderStroke(ctx, stroke) {
    if (!stroke.points.length) {
      return;
    }

    const width = Math.max(1.2, stroke.size * getCanvasTransform().scale);
    ctx.save();
    ctx.globalCompositeOperation = stroke.tool === TOOLS.ERASER ? "destination-out" : "source-over";
    ctx.strokeStyle = stroke.color;
    ctx.fillStyle = stroke.color;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.lineWidth = width;

    const [startX, startY] = graphToViewportPoint(stroke.points[0]);

    if (stroke.points.length === 1) {
      ctx.beginPath();
      ctx.arc(startX, startY, width / 2, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
      return;
    }

    ctx.beginPath();
    ctx.moveTo(startX, startY);
    for (let index = 1; index < stroke.points.length; index += 1) {
      const [x, y] = graphToViewportPoint(stroke.points[index]);
      ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.restore();
  }

  renderIfNeeded(force = false) {
    if (!this.visible) {
      return;
    }

    if (!this.ensureMounted()) {
      return;
    }

    this.resizeCanvasIfNeeded();
    const signature = this.getRenderSignature();
    if (!force && !this.needsRender && signature === this.lastRenderSignature) {
      return;
    }

    const ctx = this.canvasCtx;
    if (!ctx) {
      return;
    }

    const dpr = window.devicePixelRatio || 1;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, this.canvasEl.width / dpr, this.canvasEl.height / dpr);

    if (this.notesVisible) {
      this.documentData.strokes.forEach((stroke) => this.renderStroke(ctx, stroke));
    }
    if (this.notesVisible && this.activeStroke) {
      this.renderStroke(ctx, this.activeStroke);
    }

    this.needsRender = false;
    this.lastRenderSignature = signature;
  }

  startRenderLoop() {
    if (this.rafId) {
      return;
    }

    const tick = () => {
      this.rafId = window.requestAnimationFrame(tick);
      this.renderIfNeeded();
    };
    tick();
  }

  stopRenderLoop() {
    if (!this.rafId) {
      return;
    }

    window.cancelAnimationFrame(this.rafId);
    this.rafId = null;
  }
}
