import { comfy } from "/comfy/api/v2.js";

import {
  HEADER_HEIGHT,
  RESIZE_SIZE,
  clampGeometry,
  defaultGeometry,
  dragGeometry,
  panelRegions,
  resizeGeometry,
  sanitizeStoredGeometry,
} from "./geometry.js";

const STORAGE_KEY = "live-preview/geometry.json";
const MAX_STORAGE_BYTES = 4096;
const MAX_FRAME_BYTES = 32 * 1024 * 1024;
const MAX_FRAME_DIMENSION = 8192;
const MAX_FRAME_PIXELS = 64 * 1024 * 1024;
const ACCEPTED_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

function pointInClose(point, geometry) {
  const dx = point.x - (geometry.x + geometry.width - 17);
  const dy = point.y - (geometry.y + HEADER_HEIGHT / 2);
  return dx * dx + dy * dy <= 12 * 12;
}

function pointInResize(point, geometry) {
  return point.x >= geometry.x + geometry.width - RESIZE_SIZE &&
    point.y >= geometry.y + geometry.height - RESIZE_SIZE;
}

function hasLivePreviewNode(api) {
  return api.graph.queryNodes({
    type: "LivePreview",
    scope: "root-and-subgraphs",
  }).length > 0;
}

function safeQueueRemaining(detail) {
  const value = detail?.exec_info?.queue_remaining;
  return Number.isSafeInteger(value) && value >= 0 ? value : undefined;
}

function drawRoundedPanel(context, geometry) {
  context.save();
  context.fillStyle = "#0d0d18";
  context.strokeStyle = "#7c6aff";
  context.lineWidth = 2;
  context.beginPath();
  context.roundRect(geometry.x, geometry.y, geometry.width, geometry.height, 10);
  context.fill();
  context.stroke();
  context.restore();
}

function drawHeader(context, state) {
  const geometry = state.geometry;
  context.save();
  context.beginPath();
  context.roundRect(geometry.x + 1, geometry.y + 1, geometry.width - 2, HEADER_HEIGHT, [9, 9, 0, 0]);
  context.fillStyle = "#16213e";
  context.fill();
  context.fillStyle = state.status === "active"
    ? "#00d4aa"
    : state.status === "error" ? "#ff5555" : state.status === "idle" ? "#7c6aff" : "#444444";
  context.beginPath();
  context.arc(geometry.x + 14, geometry.y + HEADER_HEIGHT / 2, 4, 0, Math.PI * 2);
  context.fill();
  context.font = "700 12px sans-serif";
  context.textBaseline = "middle";
  context.fillStyle = "#7c6aff";
  context.fillText("⚡ Live Preview", geometry.x + 26, geometry.y + HEADER_HEIGHT / 2);
  context.font = "10px monospace";
  context.textAlign = "right";
  if (state.previewCount > 0) {
    context.fillStyle = "#00d4aa";
    context.fillText(`step ${state.previewCount}`, geometry.x + geometry.width - 98, geometry.y + HEADER_HEIGHT / 2);
  }
  if (state.fps > 0 && state.status === "active") {
    context.fillStyle = "#777790";
    context.fillText(`${state.fps} fps`, geometry.x + geometry.width - 42, geometry.y + HEADER_HEIGHT / 2);
  }
  context.font = "14px sans-serif";
  context.fillStyle = "#777790";
  context.fillText("×", geometry.x + geometry.width - 12, geometry.y + HEADER_HEIGHT / 2);
  context.restore();
}

function drawFrame(context, state) {
  const geometry = state.geometry;
  const x = geometry.x + 2;
  const y = geometry.y + HEADER_HEIGHT + 1;
  const width = geometry.width - 4;
  const height = geometry.height - HEADER_HEIGHT - 3;
  context.save();
  context.beginPath();
  context.rect(x, y, width, height);
  context.clip();
  context.fillStyle = "#080810";
  context.fillRect(x, y, width, height);
  if (state.bitmap) {
    const scale = Math.min(width / state.bitmap.width, height / state.bitmap.height);
    const drawWidth = state.bitmap.width * scale;
    const drawHeight = state.bitmap.height * scale;
    context.drawImage(
      state.bitmap,
      x + (width - drawWidth) / 2,
      y + (height - drawHeight) / 2,
      drawWidth,
      drawHeight,
    );
  }
  context.restore();
  context.save();
  context.fillStyle = "#7c6aff80";
  context.beginPath();
  context.moveTo(geometry.x + geometry.width, geometry.y + geometry.height - RESIZE_SIZE);
  context.lineTo(geometry.x + geometry.width, geometry.y + geometry.height);
  context.lineTo(geometry.x + geometry.width - RESIZE_SIZE, geometry.y + geometry.height);
  context.closePath();
  context.fill();
  context.restore();
}

export function installLivePreview(api = comfy, environment = {}) {
  const decode = environment.createImageBitmap ?? createImageBitmap;
  const now = environment.now ?? (() => Date.now());
  const scheduleInterval = environment.setInterval ?? setInterval;
  const cancelInterval = environment.clearInterval ?? clearInterval;
  const state = {
    disposed: false,
    visible: false,
    userHidden: false,
    geometry: undefined,
    viewport: undefined,
    bitmap: undefined,
    decodeRevision: 0,
    previewCount: 0,
    fpsCount: 0,
    fps: 0,
    fpsTimer: undefined,
    fpsStartedAt: 0,
    status: "off",
    gesture: undefined,
    regionSignature: "",
  };

  let overlay;
  let action;
  const subscriptions = [];

  const syncAction = () => action?.update({
    tooltip: state.visible ? "Hide Live Preview" : "Show Live Preview",
  });

  const syncRegions = () => {
    const regions = state.visible ? panelRegions(state.geometry) : [];
    const signature = JSON.stringify(regions);
    if (signature === state.regionSignature) return;
    state.regionSignature = signature;
    overlay.setHitRegions(regions);
  };

  const requestDraw = () => {
    syncRegions();
    overlay.redraw();
  };

  const persistGeometry = async () => {
    if (state.disposed || !state.geometry) return;
    const encoded = JSON.stringify(state.geometry);
    if (new TextEncoder().encode(encoded).byteLength > MAX_STORAGE_BYTES) return;
    try {
      await api.storage.set(STORAGE_KEY, encoded);
    } catch {
      // Geometry persistence is optional; the live preview itself remains usable.
    }
  };

  const show = (fromUser = false) => {
    state.visible = true;
    if (fromUser) state.userHidden = false;
    syncAction();
    requestDraw();
  };

  const hide = () => {
    state.visible = false;
    state.userHidden = true;
    state.gesture = undefined;
    syncAction();
    requestDraw();
  };

  const stopFps = () => {
    if (state.fpsTimer !== undefined) cancelInterval(state.fpsTimer);
    state.fpsTimer = undefined;
    state.fps = 0;
  };

  const startFps = () => {
    stopFps();
    state.fpsCount = 0;
    state.fpsStartedAt = now();
    state.fpsTimer = scheduleInterval(() => {
      state.fps = state.fpsCount;
      state.fpsCount = 0;
      state.fpsStartedAt = now();
      if (!state.disposed) requestDraw();
    }, 1000);
  };

  const acceptFrame = async (blob) => {
    if (!hasLivePreviewNode(api) || !(blob instanceof Blob) ||
        !ACCEPTED_TYPES.has(blob.type) || blob.size < 1 || blob.size > MAX_FRAME_BYTES) return;
    if (!state.visible && !state.userHidden) show();
    const revision = ++state.decodeRevision;
    let bitmap;
    try {
      bitmap = await decode(blob);
    } catch {
      return;
    }
    if (state.disposed || revision !== state.decodeRevision) {
      bitmap?.close?.();
      return;
    }
    if (!bitmap || !Number.isSafeInteger(bitmap.width) || !Number.isSafeInteger(bitmap.height) ||
        bitmap.width < 1 || bitmap.height < 1 ||
        bitmap.width > MAX_FRAME_DIMENSION || bitmap.height > MAX_FRAME_DIMENSION ||
        bitmap.width * bitmap.height > MAX_FRAME_PIXELS) {
      bitmap?.close?.();
      return;
    }
    state.bitmap?.close?.();
    state.bitmap = bitmap;
    state.previewCount += 1;
    state.fpsCount += 1;
    requestDraw();
  };

  overlay = api.ui.mountGraphOverlay({
    id: "live-preview.overlay",
    ariaLabel: "Live preview window",
    interactive: true,
    draw(context, size) {
      state.viewport = Object.freeze({ width: size[0], height: size[1] });
      state.geometry = state.geometry
        ? clampGeometry(state.geometry, state.viewport)
        : defaultGeometry(state.viewport);
      syncRegions();
      if (!state.visible) return;
      drawRoundedPanel(context, state.geometry);
      drawHeader(context, state);
      drawFrame(context, state);
    },
    onPointerDown(event) {
      if (!state.visible || !state.geometry || !state.viewport) return;
      const point = event.viewport;
      if (pointInClose(point, state.geometry)) {
        hide();
        return;
      }
      const mode = pointInResize(point, state.geometry) ? "resize" : "drag";
      state.gesture = Object.freeze({
        pointerId: event.pointerId,
        mode,
        x: point.x,
        y: point.y,
        geometry: state.geometry,
      });
    },
    onPointerMove(event) {
      const gesture = state.gesture;
      if (!gesture || gesture.pointerId !== event.pointerId || !state.viewport) return;
      const dx = event.viewport.x - gesture.x;
      const dy = event.viewport.y - gesture.y;
      state.geometry = gesture.mode === "resize"
        ? resizeGeometry(gesture.geometry, dx, dy, state.viewport)
        : dragGeometry(gesture.geometry, dx, dy, state.viewport);
      requestDraw();
    },
    onPointerUp(event) {
      if (state.gesture?.pointerId !== event.pointerId) return;
      state.gesture = undefined;
      void persistGeometry();
    },
    onPointerCancel(event) {
      if (state.gesture?.pointerId !== event.pointerId) return;
      state.gesture = undefined;
    },
    onKeyDown(event) {
      if (event.key === "Escape" && state.gesture) {
        state.geometry = state.gesture.geometry;
        state.gesture = undefined;
        requestDraw();
      }
    },
  });

  action = api.ui.addActionBarButton({
    id: "live-preview.toggle",
    icon: "icon-[lucide--scan-eye]",
    label: "Live Preview",
    tooltip: "Show Live Preview",
    run: () => state.visible ? hide() : show(true),
  });

  subscriptions.push(
    api.backend.on("b_preview", (detail) => { void acceptFrame(detail); }),
    api.backend.on("execution_start", () => {
      if (!hasLivePreviewNode(api)) return;
      state.previewCount = 0;
      state.fpsCount = 0;
      state.fps = 0;
      state.status = "active";
      if (!state.visible && !state.userHidden) show();
      startFps();
      requestDraw();
    }),
    api.backend.on("status", (detail) => {
      if (safeQueueRemaining(detail) !== 0) return;
      state.status = "idle";
      stopFps();
      requestDraw();
    }),
    api.backend.on("execution_error", () => {
      state.status = "error";
      stopFps();
      requestDraw();
    }),
  );

  const ready = api.storage.get(STORAGE_KEY).then((raw) => {
    if (state.disposed || raw === undefined || raw.length > MAX_STORAGE_BYTES) return;
    try {
      const stored = sanitizeStoredGeometry(JSON.parse(raw));
      if (stored) {
        state.geometry = state.viewport ? clampGeometry(stored, state.viewport) : stored;
        requestDraw();
      }
    } catch {
      // Corrupt geometry is ignored and replaced by a bounded default.
    }
  }).catch(() => undefined);

  return Object.freeze({
    state,
    ready,
    show: () => show(true),
    hide,
    remove() {
      if (state.disposed) return;
      state.disposed = true;
      state.decodeRevision += 1;
      stopFps();
      state.bitmap?.close?.();
      state.bitmap = undefined;
      state.gesture = undefined;
      for (const unsubscribe of subscriptions.splice(0)) unsubscribe();
      overlay.setHitRegions([]);
      overlay.remove();
      action.remove();
    },
  });
}

export const livePreview = installLivePreview(comfy);
