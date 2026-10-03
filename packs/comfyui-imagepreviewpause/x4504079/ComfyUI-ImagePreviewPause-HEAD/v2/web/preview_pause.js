import { comfy } from "/comfy/api/v2.js";

const NODE_TYPE = "ImagePreviewPause";
const VARIANT = "image-preview-pause.inline-v1";
const RESPONSE_ROUTE = "/secure-nodes/interactions/respond";
const MAX_IMAGES = 256;

const states = new Map();
const records = new Map();

function managedImageRoute(identity) {
  const query = new URLSearchParams({
    filename: identity.filename,
    type: identity.type,
    subfolder: identity.subfolder || "",
  });
  return `/view?${query.toString()}`;
}

async function loadManagedImage(identity) {
  const response = await comfy.backend.fetch(managedImageRoute(identity));
  if (!response.ok) throw new Error(`preview fetch failed (${response.status})`);
  return createImageBitmap(await response.blob());
}

function validateIdentity(value) {
  if (!value || typeof value !== "object") return undefined;
  if (typeof value.filename !== "string" || !value.filename) return undefined;
  if (!new Set(["input", "temp", "output"]).has(value.type)) return undefined;
  if (typeof value.subfolder !== "string") return undefined;
  if (value.filename.includes("/") || value.filename.includes("\\")) return undefined;
  if (value.subfolder.split(/[\\/]/).includes("..")) return undefined;
  return {
    filename: value.filename,
    type: value.type,
    subfolder: value.subfolder,
  };
}

function validatePayload(payload) {
  if (!payload || payload.variant !== VARIANT || !Array.isArray(payload.images)) {
    return undefined;
  }
  if (payload.images.length < 1 || payload.images.length > MAX_IMAGES) return undefined;
  const images = payload.images.map(validateIdentity);
  if (images.some((image) => !image)) return undefined;
  if (Number(payload.count) !== images.length) return undefined;
  return { variant: VARIANT, images, count: images.length };
}

function closeImages(images) {
  for (const image of images) image?.close?.();
}

function setControls(state, enabled) {
  state.continueButton.setDisabled(!enabled);
  state.cancelButton.setDisabled(!enabled);
}

function draw(state, context, size, theme) {
  const [width, height] = size;
  context.fillStyle = "#000000";
  context.fillRect(0, 0, width, height);
  if (state.images.length === 0) {
    context.fillStyle = theme?.textColor || "#d0d0d0";
    context.font = "14px sans-serif";
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillText(state.active ? "Loading preview…" : "Waiting for execution", width / 2, height / 2);
    return;
  }

  const columns = Math.max(1, Math.ceil(Math.sqrt(state.images.length)));
  const rows = Math.ceil(state.images.length / columns);
  const gap = 4;
  const cellWidth = (width - gap * (columns + 1)) / columns;
  const cellHeight = (height - gap * (rows + 1)) / rows;
  state.images.forEach((image, index) => {
    const column = index % columns;
    const row = Math.floor(index / columns);
    const scale = Math.min(cellWidth / image.width, cellHeight / image.height);
    const drawWidth = image.width * scale;
    const drawHeight = image.height * scale;
    const x = gap + column * (cellWidth + gap) + (cellWidth - drawWidth) / 2;
    const y = gap + row * (cellHeight + gap) + (cellHeight - drawHeight) / 2;
    context.drawImage(image, x, y, drawWidth, drawHeight);
  });
}

function notifyError(error) {
  comfy.commands.notify({
    severity: "error",
    summary: "Preview Image with Pause",
    detail: String(error),
  });
}

function finishRecord(record) {
  if (!record || record.finished) return;
  record.finished = true;
  if (record.timer !== undefined) clearTimeout(record.timer);
  records.delete(record.requestId);
  const state = record.state;
  if (state.active === record) {
    state.active = undefined;
    closeImages(state.images);
    state.images = [];
    setControls(state, false);
    state.canvas.redraw();
    activateNext(state);
  } else {
    const index = state.queue.indexOf(record);
    if (index >= 0) state.queue.splice(index, 1);
  }
}

async function sendResponse(record, response) {
  if (!record || record.finished || record.sending) return false;
  record.sending = true;
  try {
    const result = await comfy.backend.fetch(RESPONSE_ROUTE, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ request_id: record.requestId, response }),
    });
    if (!result.ok && result.status !== 404) {
      throw new Error(`interaction response failed (${result.status})`);
    }
    finishRecord(record);
    return result.ok;
  } catch (error) {
    record.sending = false;
    notifyError(error);
    return false;
  }
}

function expireRecord(record) {
  if (!record || record.finished) return;
  finishRecord(record);
}

function activateNext(state) {
  if (state.disposed || state.active || state.queue.length === 0) return;
  const record = state.queue.shift();
  if (!record || record.finished) {
    activateNext(state);
    return;
  }
  state.active = record;
  closeImages(state.images);
  state.images = [];
  setControls(state, false);
  state.canvas.redraw();
  void Promise.all(record.payload.images.map(loadManagedImage)).then((images) => {
    if (state.disposed || record.finished || state.active !== record) {
      closeImages(images);
      return;
    }
    state.images = images;
    setControls(state, true);
    state.canvas.redraw();
  }).catch((error) => {
    if (record.finished || state.active !== record) return;
    notifyError(error);
    void sendResponse(record, { action: "cancel" });
  });
}

function receiveInteraction(detail) {
  if (detail?.kind !== "image-choice" || typeof detail.request_id !== "string") return;
  const payload = validatePayload(detail.payload);
  if (!payload) return;
  const state = states.get(String(detail.node_id));
  if (!state || state.disposed || records.has(detail.request_id)) return;
  const record = {
    requestId: detail.request_id,
    state,
    payload,
    sending: false,
    finished: false,
    timer: undefined,
  };
  const timeout = Number(detail.timeout_seconds);
  if (Number.isFinite(timeout) && timeout > 0) {
    record.timer = setTimeout(() => expireRecord(record), timeout * 1000 + 250);
  }
  records.set(record.requestId, record);
  state.queue.push(record);
  activateNext(state);
}

function addButton(node, name, activate) {
  const button = node.widgets.add({
    type: "button",
    name,
    value: null,
    disabled: true,
    serialize: false,
  });
  button.on("activate", activate);
  return button;
}

function disposeState(state) {
  if (!state || state.disposed) return;
  state.disposed = true;
  states.delete(String(state.node.id));
  const pending = [state.active, ...state.queue].filter(Boolean);
  state.active = undefined;
  state.queue = [];
  closeImages(state.images);
  state.images = [];
  setControls(state, false);
  for (const record of pending) {
    if (record.timer !== undefined) clearTimeout(record.timer);
    void sendResponse(record, { action: "cancel" }).finally(() => finishRecord(record));
  }
  state.canvas.redraw();
}

comfy.defs.extend(NODE_TYPE, (builder) => {
  builder.onCreated((node) => {
    const previous = states.get(String(node.id));
    if (previous) disposeState(previous);
    const state = {
      node,
      queue: [],
      active: undefined,
      disposed: false,
      images: [],
      canvas: undefined,
      continueButton: undefined,
      cancelButton: undefined,
    };
    state.canvas = node.widgets.canvas({
      name: "image_preview_pause",
      height: 300,
      draw: (context, size, theme) => draw(state, context, size, theme),
      serialize: false,
      sendToPrompt: false,
    });
    state.continueButton = addButton(node, "✔️ Continue", () => {
      void sendResponse(state.active, { action: "continue" });
    });
    state.cancelButton = addButton(node, "⛔ Cancel", () => {
      void sendResponse(state.active, { action: "cancel" });
    });
    node.setSizeConstraints({ minWidth: 320, minHeight: 390 });
    states.set(String(node.id), state);
  });
  builder.onRemoved((node) => disposeState(states.get(String(node.id))));
});

comfy.backend.on("secure-node-interaction", receiveInteraction);
comfy.queue.onInterrupted(() => {
  for (const record of [...records.values()]) expireRecord(record);
});
