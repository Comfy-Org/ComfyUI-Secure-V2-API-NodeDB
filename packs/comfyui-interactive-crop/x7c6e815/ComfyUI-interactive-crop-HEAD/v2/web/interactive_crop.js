import { comfy } from '/comfy/api/v2.js';

const NODE_TYPE = 'InteractiveCrop';
const VARIANT = 'interactive-crop.inline-v1';
const RESPONSE_ROUTE = '/secure-nodes/interactions/respond';
const CANVAS_NAME = 'interactive_crop_preview';
const HANDLE_RADIUS = 6;
const MIN_SELECTION = 2;

const states = new Map();
const records = new Map();

function clamp(value, low, high) {
  return Math.max(low, Math.min(high, value));
}

function normalizeRect(rect) {
  const x0 = Math.min(rect.x, rect.x + rect.w);
  const y0 = Math.min(rect.y, rect.y + rect.h);
  const x1 = Math.max(rect.x, rect.x + rect.w);
  const y1 = Math.max(rect.y, rect.y + rect.h);
  return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
}

function clampRect(rect, width, height) {
  const value = normalizeRect(rect);
  value.w = clamp(value.w, MIN_SELECTION, width);
  value.h = clamp(value.h, MIN_SELECTION, height);
  value.x = clamp(value.x, 0, Math.max(0, width - value.w));
  value.y = clamp(value.y, 0, Math.max(0, height - value.h));
  return value;
}

function aspectEndpoint(anchorX, anchorY, pointerX, pointerY, ratio, width, height) {
  const dx = pointerX - anchorX;
  const dy = pointerY - anchorY;
  const signX = dx >= 0 ? 1 : -1;
  const signY = dy >= 0 ? 1 : -1;
  let spanX = Math.abs(dx);
  let spanY = Math.abs(dy);
  if (spanX / Math.max(spanY, 0.0001) > ratio) spanY = spanX / ratio;
  else spanX = spanY * ratio;
  const maximumX = signX > 0 ? width - anchorX : anchorX;
  const maximumY = signY > 0 ? height - anchorY : anchorY;
  const factor = Math.min(1, maximumX / Math.max(spanX, 0.0001), maximumY / Math.max(spanY, 0.0001));
  return {
    x: anchorX + signX * spanX * factor,
    y: anchorY + signY * spanY * factor,
  };
}

function handles(rect) {
  const middleX = rect.x + rect.w / 2;
  const middleY = rect.y + rect.h / 2;
  return [
    { key: 'nw', x: rect.x, y: rect.y },
    { key: 'n', x: middleX, y: rect.y },
    { key: 'ne', x: rect.x + rect.w, y: rect.y },
    { key: 'e', x: rect.x + rect.w, y: middleY },
    { key: 'se', x: rect.x + rect.w, y: rect.y + rect.h },
    { key: 's', x: middleX, y: rect.y + rect.h },
    { key: 'sw', x: rect.x, y: rect.y + rect.h },
    { key: 'w', x: rect.x, y: middleY },
  ];
}

function hitHandle(state, x, y) {
  if (!state.rect || !state.drawBox) return undefined;
  const projected = projectRect(state, state.rect);
  return handles(projected).find((item) => (
    Math.abs(item.x - x) <= HANDLE_RADIUS && Math.abs(item.y - y) <= HANDLE_RADIUS
  ))?.key;
}

function projectRect(state, rect) {
  const box = state.drawBox;
  return {
    x: box.x + rect.x * box.w / state.imageWidth,
    y: box.y + rect.y * box.h / state.imageHeight,
    w: rect.w * box.w / state.imageWidth,
    h: rect.h * box.h / state.imageHeight,
  };
}

function imagePoint(state, event) {
  const box = state.drawBox;
  return {
    x: clamp((event.x - box.x) * state.imageWidth / box.w, 0, state.imageWidth),
    y: clamp((event.y - box.y) * state.imageHeight / box.h, 0, state.imageHeight),
  };
}

function inside(rect, x, y) {
  return x >= rect.x && y >= rect.y && x <= rect.x + rect.w && y <= rect.y + rect.h;
}

function ratioEnabled(state) {
  return state.ratioWidget?.getValue() === true;
}

function resizeRect(state, point) {
  const base = state.dragStartRect;
  const key = state.handle;
  let left = base.x;
  let top = base.y;
  let right = base.x + base.w;
  let bottom = base.y + base.h;

  if (ratioEnabled(state) && ['nw', 'ne', 'se', 'sw'].includes(key)) {
    const anchorX = key.includes('w') ? right : left;
    const anchorY = key.includes('n') ? bottom : top;
    const endpoint = aspectEndpoint(
      anchorX, anchorY, point.x, point.y,
      state.imageWidth / state.imageHeight,
      state.imageWidth, state.imageHeight,
    );
    return clampRect({
      x: Math.min(anchorX, endpoint.x),
      y: Math.min(anchorY, endpoint.y),
      w: Math.abs(endpoint.x - anchorX),
      h: Math.abs(endpoint.y - anchorY),
    }, state.imageWidth, state.imageHeight);
  }

  if (key.includes('w')) left = point.x;
  if (key.includes('e')) right = point.x;
  if (key.includes('n')) top = point.y;
  if (key.includes('s')) bottom = point.y;
  return clampRect({ x: left, y: top, w: right - left, h: bottom - top }, state.imageWidth, state.imageHeight);
}

function setControls(state, enabled) {
  state.applyButton.setDisabled(!enabled);
  state.cancelButton.setDisabled(!enabled);
}

function managedImageRoute(identity) {
  const query = new URLSearchParams({
    filename: identity.filename,
    type: identity.type,
    subfolder: identity.subfolder || '',
  });
  return `/view?${query.toString()}`;
}

async function loadManagedImage(identity) {
  const response = await comfy.backend.fetch(managedImageRoute(identity));
  if (!response.ok) throw new Error(`preview fetch failed (${response.status})`);
  return createImageBitmap(await response.blob());
}

function notifyError(error) {
  comfy.commands.notify({
    severity: 'error',
    summary: 'Interactive Crop',
    detail: String(error),
  });
}

async function sendResponse(record, response) {
  if (!record || record.finished || record.sending) return false;
  record.sending = true;
  try {
    const result = await comfy.backend.fetch(RESPONSE_ROUTE, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ request_id: record.requestId, response }),
    });
    if (!result.ok) {
      if (result.status === 404) {
        finishRecord(record);
        return false;
      }
      throw new Error(`interaction response failed (${result.status})`);
    }
    finishRecord(record);
    return true;
  } catch (error) {
    record.sending = false;
    notifyError(error);
    return false;
  }
}

function finishRecord(record) {
  if (!record || record.finished) return;
  record.finished = true;
  if (record.timer !== undefined) clearTimeout(record.timer);
  records.delete(record.requestId);
  const state = record.state;
  if (state.active === record) {
    state.active = undefined;
    state.ready = false;
    state.image?.close?.();
    state.image = undefined;
    state.rect = undefined;
    state.drag = undefined;
    setControls(state, false);
    state.canvas.redraw();
    activateNext(state);
  } else {
    const index = state.queue.indexOf(record);
    if (index >= 0) state.queue.splice(index, 1);
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
  state.imageWidth = record.payload.width;
  state.imageHeight = record.payload.height;
  state.rect = undefined;
  state.ready = false;
  state.drag = undefined;
  setControls(state, false);
  void loadManagedImage(record.payload.image).then((image) => {
    if (record.finished || state.active !== record || state.disposed) {
      image.close?.();
      return;
    }
    state.image = image;
    state.ready = true;
    setControls(state, true);
    state.canvas.redraw();
  }).catch(() => {
    if (record.finished || state.active !== record) return;
    notifyError('The managed preview could not be loaded; passing the image through.');
    void sendResponse(record, { action: 'passthrough' });
  });
  state.canvas.redraw();
}

function validatePayload(payload) {
  if (!payload || payload.variant !== VARIANT) return undefined;
  const width = Number(payload.width);
  const height = Number(payload.height);
  const image = payload.image;
  if (!Number.isInteger(width) || width < 1 || width > 1_000_000) return undefined;
  if (!Number.isInteger(height) || height < 1 || height > 1_000_000) return undefined;
  if (!image || typeof image.filename !== 'string' || typeof image.type !== 'string' || typeof image.subfolder !== 'string') return undefined;
  return {
    variant: VARIANT,
    image,
    width,
    height,
    force_original_ratio: payload.force_original_ratio === true,
  };
}

function receiveInteraction(detail) {
  if (detail?.kind !== 'image-choice' || typeof detail.request_id !== 'string') return;
  const payload = validatePayload(detail.payload);
  if (!payload) return;
  const state = states.get(String(detail.node_id));
  if (!state || state.disposed) return;
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

function applySelection(state) {
  const record = state.active;
  if (!record || !state.ready || record.finished) return;
  if (!state.rect || state.rect.w < MIN_SELECTION || state.rect.h < MIN_SELECTION) {
    void sendResponse(record, { action: 'passthrough' });
    return;
  }
  const rect = normalizeRect(state.rect);
  void sendResponse(record, {
    action: 'continue',
    x0: Math.round(rect.x),
    y0: Math.round(rect.y),
    x1: Math.round(rect.x + rect.w),
    y1: Math.round(rect.y + rect.h),
  });
}

function cancelSelection(state) {
  if (state.active) void sendResponse(state.active, { action: 'cancel' });
}

function draw(state, context, size, theme) {
  const width = Math.max(1, Number(size[0]));
  const height = Math.max(1, Number(size[1]));
  context.clearRect(0, 0, width, height);
  context.fillStyle = theme.surface;
  context.fillRect(0, 0, width, height);
  if (!state.active) {
    context.fillStyle = theme.textSecondary;
    context.textAlign = 'center';
    context.textBaseline = 'middle';
    context.font = '13px sans-serif';
    context.fillText('Preview appears while this node is executing', width / 2, height / 2);
    state.drawBox = undefined;
    return;
  }
  if (!state.ready || !state.image) {
    context.fillStyle = theme.textSecondary;
    context.textAlign = 'center';
    context.textBaseline = 'middle';
    context.font = '13px sans-serif';
    context.fillText('Loading crop preview…', width / 2, height / 2);
    state.drawBox = undefined;
    return;
  }

  const padding = 8;
  const availableWidth = Math.max(1, width - padding * 2);
  const availableHeight = Math.max(1, height - padding * 2 - 24);
  const scale = Math.min(
    availableWidth / state.imageWidth,
    availableHeight / state.imageHeight,
  );
  const drawWidth = state.imageWidth * scale;
  const drawHeight = state.imageHeight * scale;
  const drawX = (width - drawWidth) / 2;
  const drawY = padding;
  state.drawBox = { x: drawX, y: drawY, w: drawWidth, h: drawHeight };
  context.drawImage(state.image, drawX, drawY, drawWidth, drawHeight);

  if (state.rect) {
    const rect = projectRect(state, normalizeRect(state.rect));
    context.save();
    context.fillStyle = 'rgba(0,0,0,0.48)';
    context.fillRect(drawX, drawY, drawWidth, drawHeight);
    context.beginPath();
    context.rect(rect.x, rect.y, rect.w, rect.h);
    context.clip();
    context.drawImage(state.image, drawX, drawY, drawWidth, drawHeight);
    context.restore();
    context.strokeStyle = theme.text;
    context.lineWidth = 1;
    context.strokeRect(rect.x + 0.5, rect.y + 0.5, rect.w, rect.h);
    context.fillStyle = theme.text;
    context.strokeStyle = theme.border;
    for (const item of handles(rect)) {
      context.fillRect(item.x - 4, item.y - 4, 8, 8);
      context.strokeRect(item.x - 4, item.y - 4, 8, 8);
    }
  }

  context.fillStyle = theme.textSecondary;
  context.textAlign = 'center';
  context.textBaseline = 'bottom';
  context.font = '12px sans-serif';
  context.fillText('Drag to select; drag inside to move; drag handles to resize', width / 2, height - 3);
}

function pointerDown(state, event) {
  if (!state.active || !state.ready || !state.drawBox || state.active.sending) return;
  if (event.event.button !== 0 || !inside(state.drawBox, event.x, event.y)) return;
  event.event.preventDefault();
  const point = imagePoint(state, event);
  const handle = hitHandle(state, event.x, event.y);
  if (handle && state.rect) {
    state.drag = 'resize';
    state.handle = handle;
    state.dragStartRect = { ...normalizeRect(state.rect) };
  } else if (state.rect && inside(normalizeRect(state.rect), point.x, point.y)) {
    state.drag = 'move';
    state.dragStartRect = { ...normalizeRect(state.rect) };
    state.dragOffset = { x: point.x - state.rect.x, y: point.y - state.rect.y };
  } else {
    state.drag = 'new';
    state.anchor = point;
    state.rect = { x: point.x, y: point.y, w: 0, h: 0 };
  }
  state.canvas.redraw();
}

function pointerMove(state, event) {
  if (!state.drag || !state.active || !state.ready || !state.drawBox) return;
  if ((Number(event.event.buttons) & 1) !== 1) {
    state.drag = undefined;
    return;
  }
  event.event.preventDefault();
  const point = imagePoint(state, event);
  if (state.drag === 'move') {
    const base = state.dragStartRect;
    state.rect = {
      ...base,
      x: clamp(point.x - state.dragOffset.x, 0, state.imageWidth - base.w),
      y: clamp(point.y - state.dragOffset.y, 0, state.imageHeight - base.h),
    };
  } else if (state.drag === 'resize') {
    state.rect = resizeRect(state, point);
  } else {
    let endpoint = point;
    if (ratioEnabled(state)) {
      endpoint = aspectEndpoint(
        state.anchor.x, state.anchor.y, point.x, point.y,
        state.imageWidth / state.imageHeight,
        state.imageWidth, state.imageHeight,
      );
    }
    state.rect = {
      x: Math.min(state.anchor.x, endpoint.x),
      y: Math.min(state.anchor.y, endpoint.y),
      w: Math.abs(endpoint.x - state.anchor.x),
      h: Math.abs(endpoint.y - state.anchor.y),
    };
  }
  state.canvas.redraw();
}

function pointerUp(state, event) {
  if (!state.drag) return;
  event.event.preventDefault();
  state.drag = undefined;
  state.handle = undefined;
  state.dragStartRect = undefined;
  state.canvas.redraw();
}

function addButton(node, name, activate) {
  const button = node.widgets.add({
    type: 'button', name, value: null, disabled: true, serialize: false,
  });
  button.on('activate', activate);
  return button;
}

function disposeState(state) {
  if (!state || state.disposed) return;
  state.disposed = true;
  states.delete(String(state.node.id));
  const pending = [state.active, ...state.queue].filter(Boolean);
  state.queue = [];
  state.active = undefined;
  state.drag = undefined;
  setControls(state, false);
  for (const record of pending) {
    if (record.timer !== undefined) clearTimeout(record.timer);
    void sendResponse(record, { action: 'cancel' }).finally(() => finishRecord(record));
  }
}

comfy.defs.extend(NODE_TYPE, (builder) => {
  builder.onCreated((node) => {
    const state = {
      node,
      queue: [],
      active: undefined,
      disposed: false,
      ready: false,
      rect: undefined,
      drag: undefined,
      ratioWidget: node.widgets.get('force_original_ratio'),
      canvas: undefined,
      applyButton: undefined,
      cancelButton: undefined,
    };
    state.canvas = node.widgets.canvas({
      name: CANVAS_NAME,
      height: 360,
      draw: (context, size, theme) => draw(state, context, size, theme),
      onPointerDown: (event) => pointerDown(state, event),
      onPointerMove: (event) => pointerMove(state, event),
      onPointerUp: (event) => pointerUp(state, event),
      serialize: false,
      sendToPrompt: false,
    });
    state.applyButton = addButton(node, 'Apply Crop / Skip', () => applySelection(state));
    state.cancelButton = addButton(node, 'Cancel Run', () => cancelSelection(state));
    node.setSizeConstraints({ minWidth: 300, minHeight: 460 });
    const previous = states.get(String(node.id));
    if (previous && previous !== state) disposeState(previous);
    states.set(String(node.id), state);
  });
  builder.onRemoved((node) => disposeState(states.get(String(node.id))));
});

comfy.backend.on('secure-node-interaction', receiveInteraction);
comfy.queue.onInterrupted(() => {
  for (const record of [...records.values()]) expireRecord(record);
});
