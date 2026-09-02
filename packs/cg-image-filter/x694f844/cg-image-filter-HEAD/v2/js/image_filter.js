import { comfy } from '/comfy/api/v2.js';

const VERSION = '1.9';
const INTERACTION_ROUTE = '/secure-nodes/interactions/respond';
const FILTER_TYPES = ['Image Filter', 'Text Image Filter', 'Mask Image Filter'];
const AUDIO = Object.freeze({
  'beep.mp3': new URL('./audio/beep.mp3', import.meta.url).href,
  'ding.mp3': new URL('./audio/ding.mp3', import.meta.url).href,
  'honk.mp3': new URL('./audio/honk.mp3', import.meta.url).href,
});

const SETTING = Object.freeze({
  playSound: 'Image Filter.UI.Play Sound',
  soundTimeout: 'Image Filter.UI.Sound Timeout',
  enlarge: 'Image Filter.UI.Enlarge Small Images',
  multiple: 'Image Filter.Actions.Multiple Selection',
  autosend: 'Image Filter.Actions.Autosend Identical',
  startZoomed: 'Image Filter.UI.Start Zoomed',
  smallWindow: 'Image Filter.UI.Small Window',
  logging: 'Image Filter.Z.Detailed Logging',
  fps: 'Image Filter.Video.FPS',
});

function declareSettings() {
  const definitions = [
    { id: SETTING.playSound, name: 'Play sound when activating', type: 'boolean', defaultValue: true },
    { id: SETTING.soundTimeout, name: 'Reminder sound every x seconds', type: 'number', defaultValue: 30, attrs: { min: 0, max: 600, step: 1 } },
    { id: SETTING.enlarge, name: 'Enlarge small images in grid', type: 'boolean', defaultValue: true },
    {
      id: SETTING.multiple,
      name: 'Allow multiple images to be selected',
      type: 'combo',
      options: [
        { value: 0, label: 'Yes' },
        { value: 1, label: 'No - selecting sends image' },
        { value: 2, label: 'No - selecting unselects previous' },
      ],
      defaultValue: 0,
    },
    { id: SETTING.autosend, name: 'If all images are identical, autosend one', type: 'boolean', defaultValue: false },
    {
      id: SETTING.startZoomed,
      name: 'Enter the Image Filter node with an image zoomed',
      type: 'combo',
      options: [
        { value: 0, label: 'No' },
        { value: 1, label: 'First' },
        { value: -1, label: 'Last' },
      ],
      defaultValue: 0,
    },
    { id: SETTING.smallWindow, name: 'Start with a compact activation view', type: 'boolean', defaultValue: false },
    { id: SETTING.logging, name: 'Turn on detailed logging', type: 'boolean', defaultValue: false },
    { id: SETTING.fps, name: 'Video frames per second', type: 'number', defaultValue: 5, attrs: { min: 0, max: 120, step: 1 } },
  ];
  for (const definition of definitions) comfy.settings.declare(definition);
}

declareSettings();

function log(...values) {
  if (comfy.settings.get(SETTING.logging) === true) {
    console.log('[cg-image-filter]', ...values);
  }
}

function element(tag, properties = {}, style = '') {
  const value = document.createElement(tag);
  for (const [key, item] of Object.entries(properties)) value[key] = item;
  if (style) value.style.cssText = style;
  return value;
}

function button(label, onClick, style = '') {
  const value = element('button', { textContent: label }, [
    'padding:7px 12px', 'border:1px solid #666', 'border-radius:5px',
    'background:#333', 'color:#eee', 'cursor:pointer', style,
  ].filter(Boolean).join(';'));
  value.addEventListener('click', onClick);
  return value;
}

function imageUrl(identity) {
  const query = new URLSearchParams({
    filename: identity?.filename || identity?.name || '',
    type: identity?.type || 'temp',
    subfolder: identity?.subfolder || '',
  });
  return comfy.backend.url(`/view?${query.toString()}`);
}

function extrasRow(record) {
  const row = element('div', {}, 'display:flex;gap:6px;flex-wrap:wrap');
  record.extras.forEach((value, index) => {
    const input = element('input', {
      type: 'text', value, placeholder: `extra${index + 1}`,
    }, 'flex:1;min-width:120px;padding:5px;background:#181818;color:#eee;border:1px solid #666;border-radius:4px');
    input.addEventListener('input', (event) => {
      record.extras[index] = String(event?.value ?? input.value ?? '');
    });
    row.append(input);
  });
  return row;
}

function tipBlock(record, onTag) {
  if (!record.payload.tip) return undefined;
  const block = element('div', {}, 'white-space:pre-wrap;padding:7px;background:#222;border-radius:4px');
  const text = String(record.payload.tip);
  const pattern = /\{\{(.*?)\}\}/g;
  let offset = 0;
  for (let match = pattern.exec(text); match; match = pattern.exec(text)) {
    if (match.index > offset) block.append(document.createTextNode(text.slice(offset, match.index)));
    const tag = button(match[1], () => onTag?.(match[1]), 'padding:2px 6px;margin:1px;background:#4a405f');
    block.append(tag);
    offset = match.index + match[0].length;
  }
  if (offset < text.length) block.append(document.createTextNode(text.slice(offset)));
  return block;
}

function countdownLabel(record) {
  if (!Number.isFinite(record.deadline)) return '';
  const remaining = Math.max(0, Math.ceil((record.deadline - Date.now()) / 1000));
  return `${remaining}s`;
}

function commonButtons(record, send, { hide = true } = {}) {
  const row = element('div', {}, 'display:flex;gap:8px;justify-content:flex-end;flex-wrap:wrap');
  const countdown = element('span', {
    textContent: countdownLabel(record),
  }, 'margin-right:auto;align-self:center;font-variant-numeric:tabular-nums');
  record.countdown = countdown;
  row.append(
    countdown,
    button('Reset timer', () => respond(record, { reset: true })),
    ...(hide ? [button('Hide', () => {
      record.compact = true;
      record.draw(record);
    })] : []),
    button('Cancel', () => cancel(record), 'background:#612f35'),
    button('Send', send, 'background:#275d3a'),
  );
  return row;
}

async function postInteraction(requestId, response) {
  const result = await comfy.backend.fetch(INTERACTION_ROUTE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ request_id: requestId, response }),
  });
  if (!result.ok) throw new Error(`interaction response failed (${result.status})`);
}

let active;
let lastTextSent;

async function respond(record, response) {
  if (!record || record.responded || record.sending) return;
  record.sending = true;
  try {
    await postInteraction(record.detail.request_id, response);
    record.responded = true;
    if (response?.cancelled === false && typeof response.text === 'string') {
      lastTextSent = response.text;
    }
    log('response', response);
    if (record.dialog) record.dialog.close();
    else stopRecord(record);
  } catch (error) {
    record.sending = false;
    comfy.commands.notify({
      severity: 'error', summary: 'Image Filter', detail: String(error),
    });
  }
}

function cancel(record) {
  return respond(record, { cancelled: true });
}

function stopRecord(record) {
  if (record.frameTimer) clearInterval(record.frameTimer);
  if (record.soundTimer) clearInterval(record.soundTimer);
  if (record.countdownTimer) clearInterval(record.countdownTimer);
  if (active === record) active = undefined;
}

async function playReminder(record) {
  if (comfy.settings.get(SETTING.playSound) !== true || record.responded) return;
  const source = AUDIO[record.payload.sound] || AUDIO['ding.mp3'];
  try {
    await comfy.commands.playSound({ src: source, volume: 1 });
  } catch (error) {
    log('sound unavailable', error);
  }
}

function startReminders(record) {
  void playReminder(record);
  const seconds = Number(comfy.settings.get(SETTING.soundTimeout) ?? 30);
  if (Number.isFinite(seconds) && seconds > 0) {
    record.soundTimer = setInterval(() => void playReminder(record), seconds * 1000);
  }
  if (Number.isFinite(record.deadline)) {
    record.countdownTimer = setInterval(() => {
      if (record.countdown) record.countdown.textContent = countdownLabel(record);
    }, 250);
  }
}

function groupFrames(payload) {
  const count = Math.max(1, Number(payload.video_frames) || 1);
  const groups = [];
  for (let index = 0; index < payload.images.length; index += count) {
    groups.push(payload.images.slice(index, index + count));
  }
  return groups;
}

function drawImageChoice(record) {
  const root = record.container;
  root.replaceChildren();
  const shell = element('section', {}, [
    'display:flex', 'flex-direction:column', 'gap:10px',
    'width:min(88vw,1100px)', 'max-height:82vh', 'overflow:auto',
    'padding:8px', 'box-sizing:border-box', 'color:#eee',
  ].join(';'));
  const groups = record.groups;

  if (record.compact) {
    const preview = element('img', {
      src: imageUrl(groups.at(-1)[0]), alt: 'Image Filter preview',
    }, 'max-width:260px;max-height:220px;object-fit:contain;cursor:pointer;align-self:center');
    preview.addEventListener('click', () => {
      record.compact = false;
      drawImageChoice(record);
    });
    shell.append(preview, button('Open Image Filter', () => {
      record.compact = false;
      drawImageChoice(record);
    }), button('Cancel', () => cancel(record), 'background:#612f35'));
    root.append(shell);
    return;
  }

  const tip = tipBlock(record);
  if (tip) shell.append(tip);

  if (record.zoomIndex !== undefined) {
    const zoom = element('div', {}, 'display:flex;align-items:center;gap:8px;justify-content:center');
    const index = record.zoomIndex;
    const zoomImage = element('img', {
      src: imageUrl(groups[index][0]), alt: `Image ${index + 1}`,
    }, 'max-width:72vw;max-height:48vh;object-fit:contain;border:3px solid #888');
    zoomImage.addEventListener('click', () => toggleSelection(record, index));
    zoom.append(
      button('Previous', () => { record.zoomIndex = (index - 1 + groups.length) % groups.length; drawImageChoice(record); }),
      zoomImage,
      button('Next', () => { record.zoomIndex = (index + 1) % groups.length; drawImageChoice(record); }),
    );
    shell.append(zoom);
  }

  const grid = element('div', {}, 'display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:9px');
  const animated = [];
  groups.forEach((frames, index) => {
    const chosen = record.selected.has(index);
    const image = element('img', {
      src: imageUrl(frames[0]), alt: `Image ${index + 1}`,
    }, [
      'width:100%', 'max-height:260px', 'object-fit:contain', 'cursor:pointer',
      `border:4px solid ${chosen ? '#42c96b' : '#555'}`, 'border-radius:5px',
      comfy.settings.get(SETTING.enlarge) === false ? 'image-rendering:auto' : '',
    ].filter(Boolean).join(';'));
    image.addEventListener('click', () => toggleSelection(record, index));
    image.addEventListener('dblclick', () => { record.zoomIndex = index; drawImageChoice(record); });
    image.addEventListener('mouseenter', () => { record.hoverIndex = index; });
    image.addEventListener('mouseleave', () => {
      if (record.hoverIndex === index) record.hoverIndex = undefined;
    });
    grid.append(image);
    if (frames.length > 1) animated.push({ image, frames });
  });
  shell.append(grid, extrasRow(record));
  const controls = commonButtons(record, record.send);
  controls.prepend(button(
    record.selected.size > groups.length / 2 ? 'Select none' : 'Select all',
    () => {
      if (record.selected.size > groups.length / 2) record.selected.clear();
      else record.selected = new Set(groups.map((_value, index) => index));
      drawImageChoice(record);
    },
  ));
  shell.append(controls);
  root.append(shell);

  if (record.frameTimer) clearInterval(record.frameTimer);
  if (animated.length) {
    let frame = 0;
    const fps = Number(comfy.settings.get(SETTING.fps) ?? 5);
    record.frameTimer = setInterval(() => {
      frame += 1;
      for (const item of animated) {
        item.image.src = imageUrl(item.frames[frame % item.frames.length]);
      }
    }, fps > 0 ? Math.max(16, 1000 / fps) : 1000);
  }
}

function toggleSelection(record, index) {
  const mode = Number(comfy.settings.get(SETTING.multiple) ?? 0);
  if (mode === 1) {
    record.selected = new Set([index]);
    void respond(record, {
      cancelled: false, selected: [index], extras: [...record.extras],
    });
    return;
  }
  if (mode === 2) {
    record.selected = new Set([index]);
  } else if (record.selected.has(index)) {
    record.selected.delete(index);
  } else {
    record.selected.add(index);
  }
  drawImageChoice(record);
}

function drawCompactEditor(record, source, label) {
  const root = record.container;
  root.replaceChildren();
  const shell = element('section', {}, 'display:flex;flex-direction:column;gap:8px;width:260px;padding:8px;color:#eee');
  const preview = element('img', {
    src: source, alt: `${label} compact preview`,
  }, 'max-width:240px;max-height:180px;object-fit:contain;cursor:pointer;align-self:center');
  const open = () => {
    record.compact = false;
    record.draw(record);
  };
  preview.addEventListener('click', open);
  shell.append(
    preview,
    button(`Open ${label}`, open),
    button('Cancel', () => cancel(record), 'background:#612f35'),
  );
  root.append(shell);
}

function drawTextEdit(record) {
  if (record.compact) {
    drawCompactEditor(
      record, imageUrl(record.payload.images[0]), 'Text Image Filter',
    );
    return;
  }
  const root = record.container;
  root.replaceChildren();
  const shell = element('section', {}, 'display:flex;flex-direction:column;gap:10px;width:min(86vw,900px);max-height:82vh;overflow:auto;padding:8px;color:#eee');
  const preview = element('div', {}, 'display:grid;place-items:center;max-height:45vh;overflow:hidden');
  const image = element('img', {
    src: imageUrl(record.payload.images[0]), alt: 'Text Image Filter preview',
  }, 'grid-area:1/1;max-width:80vw;max-height:45vh;object-fit:contain');
  preview.append(image);
  if (record.payload.mask_images?.[0]) {
    preview.append(element('img', {
      src: imageUrl(record.payload.mask_images[0]), alt: 'Mask overlay',
    }, 'grid-area:1/1;max-width:80vw;max-height:45vh;object-fit:contain;opacity:.42;mix-blend-mode:screen'));
  }
  const textarea = element('textarea', {
    value: record.text,
    rows: 5,
  }, `width:100%;box-sizing:border-box;min-height:${record.payload.textareaheight || 150}px;padding:8px;background:#181818;color:#eee;border:1px solid #666`);
  textarea.addEventListener('input', (event) => {
    record.text = String(event?.value ?? textarea.value ?? '');
  });
  textarea.addEventListener('click', () => {
    const now = Date.now();
    record.textClicks = (record.textClicks || []).filter((time) => now - time < 650);
    record.textClicks.push(now);
    if (record.textClicks.length >= 3 && lastTextSent !== undefined) {
      record.textClicks = [];
      record.text = lastTextSent;
      textarea.value = lastTextSent;
    }
  });
  const tip = tipBlock(record, (tag) => {
    record.text += `${tag} `;
    drawTextEdit(record);
  });
  shell.append(preview);
  if (tip) shell.append(tip);
  shell.append(textarea, extrasRow(record), commonButtons(record, record.send));
  root.append(shell);
}

function concatBytes(...parts) {
  const length = parts.reduce((total, part) => total + part.byteLength, 0);
  const output = new Uint8Array(length);
  let offset = 0;
  for (const part of parts) {
    output.set(part, offset);
    offset += part.byteLength;
  }
  return output;
}

async function uploadMask(blob) {
  if (!(blob instanceof Blob) || blob.size > 16 * 1024 * 1024) {
    throw new Error('edited mask exceeds the 16 MiB upload bound');
  }
  const bytes = new Uint8Array(await blob.arrayBuffer());
  const boundary = `----secure-cg-image-filter-${Date.now()}`;
  const encoder = new TextEncoder();
  const name = `cg-mask-${Date.now()}.png`;
  const header = encoder.encode(
    `--${boundary}\r\n` +
    `Content-Disposition: form-data; name="image"; filename="${name}"\r\n` +
    `Content-Type: image/png\r\n\r\n`,
  );
  const typePart = encoder.encode(
    `\r\n--${boundary}\r\n` +
    'Content-Disposition: form-data; name="type"\r\n\r\n' +
    'temp\r\n',
  );
  const footer = encoder.encode(`--${boundary}--\r\n`);
  const result = await comfy.backend.fetch('/upload/image', {
    method: 'POST',
    headers: { 'Content-Type': `multipart/form-data; boundary=${boundary}` },
    body: concatBytes(header, bytes, typePart, footer),
  });
  if (!result.ok) throw new Error(`mask upload failed (${result.status})`);
  const value = await result.json();
  if (!value || typeof value !== 'object' || typeof value.name !== 'string' ||
      !value.name || /[\\/\0-\x1f\x7f]/.test(value.name) || value.type !== 'temp' ||
      typeof value.subfolder !== 'string' ||
      value.subfolder.split(/[\\/]/).some((part) => part === '..')) {
    throw new Error('mask upload returned an invalid temp identity');
  }
  return { name: value.name, type: 'temp', subfolder: value.subfolder };
}

function loadWorkerImage(url) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = (error) => reject(error || new Error('image load failed'));
    image.src = url;
  });
}

function drawStroke(record, from, to) {
  const radius = record.brush;
  const paint = (context, color, composite = 'source-over') => {
    context.save();
    context.globalCompositeOperation = composite;
    context.strokeStyle = color;
    context.fillStyle = color;
    context.lineWidth = radius * 2;
    context.lineCap = 'round';
    context.lineJoin = 'round';
    context.beginPath();
    context.moveTo(from.x, from.y);
    context.lineTo(to.x, to.y);
    context.stroke();
    context.beginPath();
    context.arc(to.x, to.y, radius, 0, Math.PI * 2);
    context.fill();
    context.restore();
  };
  paint(record.maskContext, record.erase ? 'black' : 'white');
  paint(record.visibleContext, 'rgba(255,40,40,.68)', record.erase ? 'destination-out' : 'source-over');
  record.canvas.title = `mask-update-${Date.now()}`;
}

function pointerPoint(record, detail) {
  const rect = record.canvas.getBoundingClientRect();
  const displayWidth = rect.width || record.width;
  const displayHeight = rect.height || record.height;
  return {
    x: Math.max(0, Math.min(record.width, Number(detail.offsetX || 0) * record.width / displayWidth)),
    y: Math.max(0, Math.min(record.height, Number(detail.offsetY || 0) * record.height / displayHeight)),
  };
}

async function prepareMaskCanvas(record) {
  const source = await loadWorkerImage(imageUrl(record.payload.image));
  const width = Number(source.naturalWidth || source.width);
  const height = Number(source.naturalHeight || source.height);
  if (!Number.isSafeInteger(width) || !Number.isSafeInteger(height) ||
      width < 1 || height < 1 || width > 16384 || height > 16384 ||
      width * height > 67_108_864) {
    throw new Error('mask editor image dimensions exceed the safe bound');
  }
  record.width = width;
  record.height = height;
  record.canvas.width = width;
  record.canvas.height = height;
  record.visibleContext = record.canvas.getContext('2d');
  record.maskSurface = new OffscreenCanvas(width, height);
  record.maskContext = record.maskSurface.getContext('2d');
  record.maskContext.fillStyle = 'black';
  record.maskContext.fillRect(0, 0, width, height);
  record.visibleContext.clearRect(0, 0, width, height);

  if (record.payload.initial_mask) {
    const initial = await loadWorkerImage(imageUrl(record.payload.initial_mask));
    record.visibleContext.drawImage(initial, 0, 0, width, height);
    const pixels = record.visibleContext.getImageData(0, 0, width, height);
    const maskPixels = new ImageData(width, height);
    for (let index = 0; index < pixels.data.length; index += 4) {
      const level = Math.max(pixels.data[index], pixels.data[index + 1], pixels.data[index + 2]);
      maskPixels.data[index] = level;
      maskPixels.data[index + 1] = level;
      maskPixels.data[index + 2] = level;
      maskPixels.data[index + 3] = 255;
      pixels.data[index] = 255;
      pixels.data[index + 1] = 40;
      pixels.data[index + 2] = 40;
      pixels.data[index + 3] = Math.round(level * 0.68);
    }
    record.maskContext.putImageData(maskPixels, 0, 0);
    record.visibleContext.putImageData(pixels, 0, 0);
  }
  record.canvas.title = 'mask-ready';
}

function drawMaskEdit(record) {
  const root = record.container;
  root.replaceChildren();
  const shell = element('section', {}, 'display:flex;flex-direction:column;gap:9px;width:min(88vw,1100px);max-height:84vh;overflow:auto;padding:8px;color:#eee');
  const tip = tipBlock(record);
  if (tip) shell.append(tip);
  const stage = element('div', {}, 'display:grid;place-items:center;align-self:center;max-width:82vw;max-height:66vh;overflow:auto;background:#111');
  const background = element('img', {
    src: imageUrl(record.payload.image), alt: 'Mask Image Filter source',
  }, 'grid-area:1/1;display:block;width:min(80vw,1024px);height:auto;max-height:64vh;object-fit:contain');
  const canvas = element('canvas', { title: 'mask-loading' }, 'grid-area:1/1;display:block;width:min(80vw,1024px);height:auto;max-height:64vh;touch-action:none;cursor:crosshair');
  record.canvas = canvas;
  canvas.addEventListener('pointerdown', (event) => {
    if (!record.maskContext) return;
    record.drawing = true;
    record.lastPoint = pointerPoint(record, event);
    drawStroke(record, record.lastPoint, record.lastPoint);
  });
  canvas.addEventListener('pointermove', (event) => {
    if (!record.drawing || !record.maskContext || Number(event.buttons) === 0) return;
    const next = pointerPoint(record, event);
    drawStroke(record, record.lastPoint, next);
    record.lastPoint = next;
  });
  canvas.addEventListener('pointerup', () => { record.drawing = false; });
  canvas.addEventListener('pointerleave', () => { record.drawing = false; });
  stage.append(background, canvas);

  const tools = element('div', {}, 'display:flex;gap:8px;align-items:center;flex-wrap:wrap');
  const radius = element('input', { type: 'range', min: 1, max: 256, step: 1, value: record.brush }, 'width:220px');
  radius.addEventListener('input', (event) => {
    record.brush = Math.max(1, Math.min(256, Number(event?.value ?? radius.value) || 24));
  });
  const mode = button(record.erase ? 'Mode: erase' : 'Mode: paint', () => {
    record.erase = !record.erase;
    mode.textContent = record.erase ? 'Mode: erase' : 'Mode: paint';
  });
  tools.append(element('span', { textContent: 'Brush' }), radius, mode, button('Clear mask', () => {
    if (!record.maskContext) return;
    record.maskContext.fillStyle = 'black';
    record.maskContext.fillRect(0, 0, record.width, record.height);
    record.visibleContext.clearRect(0, 0, record.width, record.height);
    record.canvas.title = `mask-clear-${Date.now()}`;
  }));

  const controls = commonButtons(record, async () => {
    if (!record.maskSurface) return;
    try {
      const blob = await record.maskSurface.convertToBlob({ type: 'image/png' });
      const identity = await uploadMask(blob);
      await respond(record, {
        cancelled: false,
        mask: identity,
        extras: [...record.extras],
      });
    } catch (error) {
      comfy.commands.notify({ severity: 'error', summary: 'Mask Image Filter', detail: String(error) });
    }
  }, { hide: false });
  shell.append(stage, tools, extrasRow(record), controls);
  root.append(shell);
  void prepareMaskCanvas(record).catch((error) => {
    comfy.commands.notify({ severity: 'error', summary: 'Mask Image Filter', detail: String(error) });
    void cancel(record);
  });
}

function handleDialogKey(record, event) {
  if (record.responded || record.sending || event?.editableTarget === true) return;
  const key = String(event?.key || '');
  if (key === 'Escape') {
    void cancel(record);
    return;
  }
  if (key === 'Enter') {
    record.send?.();
    return;
  }
  if (record.detail.kind !== 'image-choice') return;

  if (/^[0-9]$/.test(key)) {
    const index = Number(key);
    if (index < record.groups.length) toggleSelection(record, index);
    return;
  }
  if (key.toLowerCase() === 'a' && event?.ctrlKey === true) {
    if (record.selected.size > record.groups.length / 2) record.selected.clear();
    else record.selected = new Set(record.groups.map((_value, index) => index));
    drawImageChoice(record);
    return;
  }
  if (key === ' ') {
    if (record.zoomIndex !== undefined) record.zoomIndex = undefined;
    else if (record.hoverIndex !== undefined) record.zoomIndex = record.hoverIndex;
    drawImageChoice(record);
    return;
  }
  if (record.zoomIndex === undefined) return;
  if (key === 'ArrowUp') {
    toggleSelection(record, record.zoomIndex);
  } else if (key === 'ArrowRight') {
    record.zoomIndex = (record.zoomIndex + 1) % record.groups.length;
    drawImageChoice(record);
  } else if (key === 'ArrowLeft') {
    record.zoomIndex = (
      record.zoomIndex - 1 + record.groups.length
    ) % record.groups.length;
    drawImageChoice(record);
  }
}

function openDialog(detail) {
  const payload = detail.payload || {};
  const record = {
    detail,
    payload,
    extras: Array.isArray(payload.extras) ? payload.extras.slice(0, 3).map(String) : ['', '', ''],
    selected: new Set(),
    text: String(payload.text ?? ''),
    brush: 24,
    erase: false,
    responded: false,
    sending: false,
  };
  const timeoutSeconds = Number(detail.timeout_seconds);
  if (Number.isFinite(timeoutSeconds) && timeoutSeconds >= 1) {
    record.deadline = Date.now() + timeoutSeconds * 1000;
  }
  while (record.extras.length < 3) record.extras.push('');
  if (active && !active.responded) void cancel(active);
  active = record;

  let draw;
  let title = 'Image Filter';
  if (detail.kind === 'image-choice' && payload.variant === 'cg-image-filter.image-choice-v1') {
    record.groups = groupFrames(payload);
    if (!record.groups.length) return void cancel(record);
    if (payload.allsame && comfy.settings.get(SETTING.autosend) === true) {
      void respond(record, { cancelled: false, selected: [0], extras: [...record.extras] });
      return;
    }
    if (record.groups.length === 1) record.selected.add(0);
    record.send = () => {
      if (record.selected.size) {
        void respond(record, {
          cancelled: false,
          selected: [...record.selected],
          extras: [...record.extras],
        });
      }
    };
    const zoom = Number(comfy.settings.get(SETTING.startZoomed) ?? 0);
    if (zoom === 1) record.zoomIndex = 0;
    if (zoom === -1) record.zoomIndex = record.groups.length - 1;
    record.compact = comfy.settings.get(SETTING.smallWindow) === true;
    draw = drawImageChoice;
  } else if (detail.kind === 'prompt-await' && payload.variant === 'cg-image-filter.text-edit-v1') {
    title = 'Text Image Filter';
    record.compact = comfy.settings.get(SETTING.smallWindow) === true;
    record.send = () => void respond(record, {
      cancelled: false,
      text: record.text,
      extras: [...record.extras],
    });
    draw = drawTextEdit;
  } else if (detail.kind === 'mask-edit' && payload.variant === 'cg-image-filter.mask-edit-v1') {
    title = 'Mask Image Filter';
    draw = drawMaskEdit;
  } else {
    return;
  }
  const node = comfy.executionNode(String(detail.node_id));
  title = node?.getTitle?.() || title;
  record.draw = draw;
  record.dialog = comfy.ui.showDialog({
    key: 'cg-image-filter.interaction',
    title,
    render(container) {
      record.container = container;
      draw(record);
    },
    ...(detail.kind === 'mask-edit' ? {} : {
      onKeyDown(event) {
        handleDialogKey(record, event);
      },
    }),
    destroy() {
      stopRecord(record);
      if (!record.responded && !record.sending) {
        void postInteraction(record.detail.request_id, { cancelled: true });
      }
    },
  });
  startReminders(record);
}

comfy.backend.on('secure-node-interaction', (detail) => {
  log('interaction', detail);
  openDialog(detail);
});

comfy.backend.on('execution_interrupted', () => {
  if (active && !active.responded) void cancel(active);
});

function expireActive() {
  if (active) {
    active.responded = true;
    active.dialog?.close();
  }
}

comfy.onExecutingNodeChanged((node) => {
  if (active && String(node?.id ?? '') !== String(active.detail.node_id)) {
    expireActive();
  }
});

for (const type of FILTER_TYPES) {
  comfy.defs.extend(type, (builder) => {
    builder.hideWidget('graph_id');
    const syncGraph = (node) => {
      node.widgets.get('graph_id')?.setValue(String(node.graphId || ''));
      if (type === 'Mask Image Filter') {
        node.widgets.get('$$canvas-image-preview')?.setHidden(true);
      }
    };
    builder.onCreated(syncGraph);
    builder.onConfigured(syncGraph);
  });
}

comfy.defs.extend('Pick from List', (builder) => {
  builder.onConnectionsChanged((node, event) => {
    if (event.side !== 'input' || event.index !== 0) return;
    const input = node.inputs.at(0);
    const output = node.outputs.at(0);
    const type = event.connected ? (input?.connectedType || '*') : '*';
    input?.modify({ type });
    output?.modify({ type });
  });
});

log(`loaded v${VERSION}`);
