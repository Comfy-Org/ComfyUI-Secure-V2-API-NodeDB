import { comfy } from '/comfy/api/v2.js';
import { BONE_SPECS, CANVAS_SIZE, PoseHistory, PoseModel, UV_MAP, frameRect } from './pose_model.js';

const DISPLAY = 384;
const MAX_FILE_BYTES = 16 * 1024 * 1024;
const IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/webp'];
const mountedEditors = new WeakMap();

function el(doc, tag, props = {}) {
  const node = doc.createElement(tag);
  Object.assign(node, props);
  return node;
}

function button(doc, label, title, action) {
  const result = el(doc, 'button', { type: 'button', textContent: label, title });
  result.style.cssText = 'padding:3px 7px;background:#4b5563;color:white;border:0;border-radius:4px;cursor:pointer;font:600 11px sans-serif';
  result.addEventListener('click', action);
  return result;
}

function row(doc) {
  const result = el(doc, 'div');
  result.style.cssText = 'display:flex;gap:4px;align-items:center;flex-wrap:wrap';
  return result;
}

function setWidget(node, name, value) {
  const widget = node.widgets.get(name);
  if (widget) widget.setValue(value);
}

export async function pickBitmap() {
  const picked = await comfy.files.pick({ extensions: ['.png', '.jpg', '.jpeg', '.webp'], mimeTypes: IMAGE_TYPES, maxBytes: MAX_FILE_BYTES });
  if (!picked) return undefined;
  const bitmap = await createImageBitmap(new Blob([picked.bytes], { type: picked.type }));
  if (bitmap.width <= 0 || bitmap.height <= 0 || bitmap.width * bitmap.height > 4096 * 4096) {
    bitmap.close?.();
    throw new Error('Image dimensions exceed the 4096×4096 resource limit');
  }
  return { bitmap, name: picked.name };
}

export function drawPose(ctx, model, texture, background, backgroundColor, showRig = true) {
  ctx.clearRect(0, 0, CANVAS_SIZE, CANVAS_SIZE);
  if (backgroundColor) { ctx.fillStyle = backgroundColor; ctx.fillRect(0, 0, CANVAS_SIZE, CANVAS_SIZE); }
  if (background) {
    const aspect = background.width / background.height;
    const width = aspect >= 1 ? CANVAS_SIZE : Math.round(CANVAS_SIZE * aspect);
    const height = aspect >= 1 ? Math.round(CANVAS_SIZE / aspect) : CANVAS_SIZE;
    ctx.drawImage(background, (CANVAS_SIZE - width) / 2, (CANVAS_SIZE - height) / 2, width, height);
  }
  ctx.save();
  ctx.translate(CANVAS_SIZE / 2, CANVAS_SIZE / 2);
  ctx.scale(model.camera.zoom, model.camera.zoom);
  ctx.translate(-CANVAS_SIZE / 2 + model.camera.x, -CANVAS_SIZE / 2 + model.camera.y);
  for (const bone of model.bones) {
    if (bone.name.includes('Eye') && !bone.name.includes('Base')) {
      if (model.variants.headBack) continue;
      ctx.beginPath(); ctx.arc(bone.endX, bone.endY, 5, 0, Math.PI * 2); ctx.fillStyle = '#222'; ctx.fill();
      continue;
    }
    if (!bone.uv) continue;
    const radius = bone.width / 2;
    ctx.save();
    ctx.translate(bone.gx, bone.gy); ctx.rotate(bone.gAngle - Math.PI / 2);
    ctx.beginPath(); ctx.roundRect?.(-radius, 0, bone.width, bone.length, radius); ctx.clip();
    if (texture) {
      const [x, y, width, height] = UV_MAP[bone.uv];
      ctx.drawImage(texture, x * texture.width / 1024, y * texture.height / 1024,
        width * texture.width / 1024, height * texture.height / 1024,
        -radius, 0, bone.width, bone.length);
    } else {
      ctx.fillStyle = bone.name.includes('Hand') || bone.name === 'Head' ? '#f5c8a0' : '#70b8b8';
      ctx.fillRect(-radius, 0, bone.width, bone.length);
    }
    if (showRig) { ctx.strokeStyle = '#555'; ctx.lineWidth = 1.5 / model.camera.zoom; ctx.stroke(); }
    ctx.restore();
  }
  if (showRig) {
    for (const bone of model.bones) {
      if (bone.name === 'Root' || bone.name.includes('Base')) continue;
      ctx.beginPath(); ctx.moveTo(bone.gx, bone.gy); ctx.lineTo(bone.endX, bone.endY);
      ctx.strokeStyle = bone.slide ? '#ef6464' : 'rgba(255,255,255,.55)'; ctx.lineWidth = 2 / model.camera.zoom; ctx.stroke();
      ctx.beginPath(); ctx.arc(bone.endX, bone.endY, 4 / model.camera.zoom, 0, Math.PI * 2); ctx.fillStyle = '#fff'; ctx.fill();
    }
  }
  ctx.restore();
}

function drawFrame(ctx, mode, width, height, backgroundAspect) {
  ctx.clearRect(0, 0, DISPLAY, DISPLAY);
  const frame = frameRect(mode, width, height, backgroundAspect, DISPLAY);
  if (frame.w === DISPLAY && frame.h === DISPLAY) return;
  ctx.fillStyle = 'rgba(0,0,0,.72)';
  ctx.fillRect(0, 0, DISPLAY, frame.y); ctx.fillRect(0, frame.y + frame.h, DISPLAY, DISPLAY - frame.y - frame.h);
  ctx.fillRect(0, frame.y, frame.x, frame.h); ctx.fillRect(frame.x + frame.w, frame.y, DISPLAY - frame.x - frame.w, frame.h);
  ctx.strokeStyle = 'rgba(255,255,255,.5)'; ctx.strokeRect(frame.x + .5, frame.y + .5, frame.w - 1, frame.h - 1);
}

export function mountPoseEditor(container, node) {
  const doc = container.ownerDocument;
  const model = new PoseModel();
  const history = new PoseHistory();
  let texture; let background; let inputImage;
  let backgroundColor = '#e0e0e0'; let showRig = true; let imageMode = false;
  let sizeMode = String(node.widgets.get('output_size_mode')?.getValue() ?? 'Standard');
  let customWidth = Number(node.widgets.get('custom_width')?.getValue() ?? 600);
  let customHeight = Number(node.widgets.get('custom_height')?.getValue() ?? 600);
  let dragName; let panning = false; let lastX = 0; let lastY = 0; let dragSnapshot;

  container.tabIndex = 0;
  container.style.cssText = 'display:flex;flex-direction:column;gap:4px;background:#2c2c2c;padding:6px;box-sizing:border-box;color:#ddd;font:11px sans-serif;outline:none';
  const toolbar = row(doc); const variants = row(doc); const sizing = row(doc);
  const wrapper = el(doc, 'div'); wrapper.style.cssText = `position:relative;width:${DISPLAY}px;height:${DISPLAY}px`;
  const canvas = el(doc, 'canvas', { width: CANVAS_SIZE, height: CANVAS_SIZE });
  canvas.style.cssText = `width:${DISPLAY}px;height:${DISPLAY}px;background:#e0e0e0;border-radius:6px;display:block;cursor:grab`;
  const overlay = el(doc, 'canvas', { width: DISPLAY, height: DISPLAY });
  overlay.style.cssText = `position:absolute;inset:0;width:${DISPLAY}px;height:${DISPLAY}px;pointer-events:none`;
  wrapper.append(canvas, overlay);
  const ctx = canvas.getContext('2d'); const overlayCtx = overlay.getContext('2d');
  if (!ctx || !overlayCtx) throw new Error('2D canvas is unavailable');

  const refresh = () => {
    if (imageMode && inputImage) {
      ctx.clearRect(0, 0, CANVAS_SIZE, CANVAS_SIZE);
      const aspect = inputImage.width / inputImage.height;
      const width = aspect >= 1 ? CANVAS_SIZE : Math.round(CANVAS_SIZE * aspect);
      const height = aspect >= 1 ? Math.round(CANVAS_SIZE / aspect) : CANVAS_SIZE;
      ctx.drawImage(inputImage, (CANVAS_SIZE - width) / 2, (CANVAS_SIZE - height) / 2, width, height);
      overlayCtx.clearRect(0, 0, DISPLAY, DISPLAY);
    } else {
      drawPose(ctx, model, texture, background, backgroundColor, showRig);
      drawFrame(overlayCtx, sizeMode, customWidth, customHeight, background ? background.width / background.height : undefined);
    }
  };
  const remember = () => history.remember(model.snapshot());
  const restore = (snapshot) => { if (snapshot) { model.restore(snapshot); refresh(); } };
  const undo = () => restore(history.undo(model.snapshot()));
  const redo = () => restore(history.redo(model.snapshot()));

  const poseButton = button(doc, 'P', 'Pose editor', () => { imageMode = false; refresh(); });
  const imageButton = button(doc, 'I', 'Image input', () => {
    if (!node.inputs.byName('background_image')?.isConnected) { imageMode = true; refresh(); }
  });
  toolbar.append(poseButton, imageButton,
    button(doc, '📸', 'Capture pose', () => {
      if (imageMode && inputImage) {
        const staging = el(doc, 'canvas', { width: inputImage.width, height: inputImage.height });
        staging.getContext('2d')?.drawImage(inputImage, 0, 0);
        setWidget(node, 'image_data', staging.toDataURL('image/png'));
      } else {
        const previous = showRig; showRig = false; refresh();
        const frame = frameRect(sizeMode, customWidth, customHeight, background ? background.width / background.height : undefined, DISPLAY);
        if (frame.w === DISPLAY && frame.h === DISPLAY) setWidget(node, 'image_data', canvas.toDataURL('image/png'));
        else {
          const outWidth = sizeMode === 'Custom' ? customWidth : frame.w;
          const outHeight = sizeMode === 'Custom' ? customHeight : frame.h;
          const staging = el(doc, 'canvas', { width: outWidth, height: outHeight });
          staging.getContext('2d')?.drawImage(canvas, frame.x * CANVAS_SIZE / DISPLAY, frame.y * CANVAS_SIZE / DISPLAY,
            frame.w * CANVAS_SIZE / DISPLAY, frame.h * CANVAS_SIZE / DISPLAY, 0, 0, outWidth, outHeight);
          setWidget(node, 'image_data', staging.toDataURL('image/png'));
        }
        showRig = previous; refresh();
      }
    }),
    button(doc, '↶', 'Undo pose edit', undo), button(doc, '↷', 'Redo pose edit', redo),
    button(doc, 'RP', 'Reset pose', () => { remember(); model.reset(); refresh(); }),
    button(doc, 'RC', 'Reset camera', () => { remember(); model.camera = { x: 0, y: 0, zoom: 1 }; refresh(); }),
    button(doc, '🦴', 'Show/hide rig', () => { showRig = !showRig; refresh(); }));

  for (const [part, front, back] of [['headBack', '👤F', '👤B'], ['bodyBack', '👕F', '👕B'], ['leftOpen', 'L✊', 'L🖐'], ['rightOpen', 'R✊', 'R🖐']]) {
    const control = button(doc, front, `Toggle ${part}`, () => { remember(); control.textContent = model.toggle(part) ? back : front; refresh(); });
    variants.append(control);
  }

  async function choose(kind) {
    const picked = await pickBitmap(); if (!picked) return;
    if (kind === 'texture') { texture?.close?.(); texture = picked.bitmap; }
    if (kind === 'background') { background?.close?.(); background = picked.bitmap; }
    if (kind === 'input') { inputImage?.close?.(); inputImage = picked.bitmap; imageMode = true; }
    refresh();
  }
  variants.append(
    button(doc, '🖼 Tex', 'Load texture atlas', () => void choose('texture')),
    button(doc, '📂 BG', 'Load editor background', () => void choose('background')),
    button(doc, '✕ BG', 'Clear editor background', () => { background?.close?.(); background = undefined; refresh(); }),
    button(doc, '📂 Image', 'Load direct image', () => void choose('input')));
  const color = el(doc, 'input', { type: 'color', value: backgroundColor, title: 'Background color' });
  color.addEventListener('input', () => { backgroundColor = color.value; refresh(); }); variants.append(color);
  variants.append(button(doc, '✕ Color', 'Clear background color', () => { backgroundColor = undefined; refresh(); }));

  const widthInput = el(doc, 'input', { type: 'number', min: '64', max: '4096', step: '8', value: String(customWidth) });
  const heightInput = el(doc, 'input', { type: 'number', min: '64', max: '4096', step: '8', value: String(customHeight) });
  for (const input of [widthInput, heightInput]) input.style.cssText = 'width:60px;background:#444;color:white;border:1px solid #666';
  const applySize = () => {
    customWidth = Math.max(64, Math.min(4096, Number(widthInput.value) || 600));
    customHeight = Math.max(64, Math.min(4096, Number(heightInput.value) || 600));
    setWidget(node, 'custom_width', customWidth); setWidget(node, 'custom_height', customHeight); refresh();
  };
  widthInput.addEventListener('change', applySize); heightInput.addEventListener('change', applySize);
  sizing.append(el(doc, 'span', { textContent: 'Size:' }));
  for (const mode of ['Standard', 'Background', 'Custom']) sizing.append(button(doc, mode === 'Standard' ? 'Std' : mode === 'Background' ? 'BG' : 'Custom', mode, () => {
    sizeMode = mode; setWidget(node, 'output_size_mode', mode); refresh();
  }));
  sizing.append(widthInput, el(doc, 'span', { textContent: '×' }), heightInput);

  const coords = (event) => {
    const rect = canvas.getBoundingClientRect();
    return { x: (event.clientX - rect.left) * CANVAS_SIZE / rect.width, y: (event.clientY - rect.top) * CANVAS_SIZE / rect.height };
  };
  canvas.addEventListener('pointerdown', (event) => {
    container.focus(); const point = coords(event); const world = model.screenToWorld(point.x, point.y);
    dragName = model.nearest(world.x, world.y)?.name; panning = !dragName; lastX = point.x; lastY = point.y; dragSnapshot = model.snapshot();
    canvas.setPointerCapture?.(event.pointerId);
  });
  canvas.addEventListener('pointermove', (event) => {
    if (!dragName && !panning) return; const point = coords(event);
    if (panning) model.pan(point.x - lastX, point.y - lastY);
    else { const world = model.screenToWorld(point.x, point.y); model.drag(dragName, world.x, world.y); }
    lastX = point.x; lastY = point.y; refresh();
  });
  const endPointer = () => { if (dragSnapshot) history.remember(dragSnapshot); dragSnapshot = undefined; dragName = undefined; panning = false; };
  canvas.addEventListener('pointerup', endPointer); canvas.addEventListener('pointercancel', endPointer);
  canvas.addEventListener('wheel', (event) => { event.preventDefault(); remember(); model.zoom(event.deltaY); refresh(); }, { passive: false });
  container.addEventListener('keydown', (event) => {
    if (!(event.ctrlKey || event.metaKey)) return;
    if (event.key.toLowerCase() === 'z') { event.preventDefault(); event.shiftKey ? redo() : undo(); }
    else if (event.key.toLowerCase() === 'y') { event.preventDefault(); redo(); }
  });

  container.append(toolbar, sizing, variants, wrapper);
  refresh();
  return {
    forcePoseMode() { imageMode = false; refresh(); },
    dispose() { texture?.close?.(); background?.close?.(); inputImage?.close?.(); container.replaceChildren(); },
  };
}

comfy.defs.extend('PoseEditor2D', (builder) => {
  builder.onCreated((node) => {
    for (const name of ['image_data', 'output_size_mode', 'custom_width', 'custom_height']) node.widgets.get(name)?.setHidden(true);
    const imageData = node.widgets.get('image_data');
    imageData?.on('beforeSerialize', (event) => {
      if (event.context !== 'prompt') event.setSerializedValue('');
    });
    node.setSizeConstraints({ minWidth: 430, maxWidth: 430, minHeight: 520 });
    let controller;
    node.widgets.mount({
      name: 'pose_editor_widget', height: 470, hideOnZoom: false, serialize: false, sendToPrompt: false,
      render(container) {
        controller?.dispose();
        controller = mountPoseEditor(container, node);
        mountedEditors.set(node, controller);
      },
      destroy() { controller?.dispose(); mountedEditors.delete(node); },
    });
  });
  builder.onConnectionsChanged((node) => {
    if (node.inputs.byName('background_image')?.isConnected) mountedEditors.get(node)?.forcePoseMode();
  });
});

export { BONE_SPECS, PoseHistory, PoseModel, frameRect };
