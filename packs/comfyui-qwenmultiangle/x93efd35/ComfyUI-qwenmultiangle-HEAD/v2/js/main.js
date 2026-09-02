import { comfy } from '/comfy/api/v2.js';

const TARGET = 'QwenMultiangleCameraNode';
const WIDTH = 340;
const HEIGHT = 370;
const CENTER_Y = 178;
const instances = new Map();

const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
const wrapAngle = (value) => ((Math.round(value) % 360) + 360) % 360;
const keyFor = (node) => `${String(node.graphId ?? '')}:${String(node.id)}`;

function widgetNumber(node, name, fallback) {
    const value = Number(node.widgets.get(name)?.getValue());
    return Number.isFinite(value) ? value : fallback;
}

function promptFor(azimuth, elevation, zoom) {
    const angle = ((azimuth % 360) + 360) % 360;
    let horizontal;
    if (angle < 22.5 || angle >= 337.5) horizontal = 'front view';
    else if (angle < 67.5) horizontal = 'front-right quarter view';
    else if (angle < 112.5) horizontal = 'right side view';
    else if (angle < 157.5) horizontal = 'back-right quarter view';
    else if (angle < 202.5) horizontal = 'back view';
    else if (angle < 247.5) horizontal = 'back-left quarter view';
    else if (angle < 292.5) horizontal = 'left side view';
    else horizontal = 'front-left quarter view';

    let vertical;
    if (elevation < -15) vertical = 'low-angle shot';
    else if (elevation < 15) vertical = 'eye-level shot';
    else if (elevation < 45) vertical = 'elevated shot';
    else vertical = 'high-angle shot';

    const distance = zoom < 2
        ? 'wide shot'
        : zoom < 6 ? 'medium shot' : 'close-up';
    return `<sks> ${horizontal} ${vertical} ${distance}`;
}

function roundedRect(context, x, y, width, height, radius) {
    const r = Math.min(radius, width / 2, height / 2);
    context.beginPath();
    context.moveTo(x + r, y);
    context.lineTo(x + width - r, y);
    context.quadraticCurveTo(x + width, y, x + width, y + r);
    context.lineTo(x + width, y + height - r);
    context.quadraticCurveTo(
        x + width, y + height, x + width - r, y + height,
    );
    context.lineTo(x + r, y + height);
    context.quadraticCurveTo(x, y + height, x, y + height - r);
    context.lineTo(x, y + r);
    context.quadraticCurveTo(x, y, x + r, y);
    context.closePath();
}

function drawFittedImage(context, image, x, y, width, height) {
    const imageWidth = Number(image?.naturalWidth || image?.width || 0);
    const imageHeight = Number(image?.naturalHeight || image?.height || 0);
    if (!(imageWidth > 0 && imageHeight > 0)) return false;
    const scale = Math.min(width / imageWidth, height / imageHeight);
    const targetWidth = imageWidth * scale;
    const targetHeight = imageHeight * scale;
    context.drawImage(
        image,
        x + (width - targetWidth) / 2,
        y + (height - targetHeight) / 2,
        targetWidth,
        targetHeight,
    );
    return true;
}

function drawGrid(context) {
    context.strokeStyle = '#191925';
    context.lineWidth = 1;
    for (let row = 0; row < 8; row += 1) {
        const y = 115 + row * 18;
        const inset = row * 7;
        context.beginPath();
        context.moveTo(inset, y);
        context.lineTo(WIDTH - inset, y);
        context.stroke();
    }
    for (let column = -6; column <= 6; column += 1) {
        context.beginPath();
        context.moveTo(WIDTH / 2 + column * 14, 115);
        context.lineTo(WIDTH / 2 + column * 27, 241);
        context.stroke();
    }
}

function drawOrbitScene(context, state) {
    drawGrid(context);
    const azimuth = state.azimuth * Math.PI / 180;
    const elevationOffset = state.elevation * 0.62;
    const radiusX = 116;
    const radiusY = 49;
    const cameraX = WIDTH / 2 + Math.sin(azimuth) * radiusX;
    const cameraY = CENTER_Y + Math.cos(azimuth) * radiusY - elevationOffset;

    context.save();
    context.strokeStyle = 'rgba(233, 61, 130, 0.65)';
    context.lineWidth = 2;
    context.beginPath();
    context.ellipse(WIDTH / 2, CENTER_Y, radiusX, radiusY, 0, 0, Math.PI * 2);
    context.stroke();

    const planeX = WIDTH / 2 - 47;
    const planeY = CENTER_Y - 55;
    context.fillStyle = '#242432';
    context.fillRect(planeX, planeY, 94, 110);
    if (state.imageReady) {
        context.save();
        context.beginPath();
        context.rect(planeX + 3, planeY + 3, 88, 104);
        context.clip();
        drawFittedImage(context, state.image, planeX + 3, planeY + 3, 88, 104);
        context.restore();
    } else {
        context.strokeStyle = '#3a3a4a';
        context.lineWidth = 1;
        for (let i = 1; i < 5; i += 1) {
            context.beginPath();
            context.moveTo(planeX, planeY + i * 22);
            context.lineTo(planeX + 94, planeY + i * 22);
            context.stroke();
        }
    }
    context.strokeStyle = '#e93d82';
    context.lineWidth = 3;
    context.strokeRect(planeX, planeY, 94, 110);

    context.strokeStyle = 'rgba(255, 184, 0, 0.75)';
    context.lineWidth = 2;
    context.beginPath();
    context.moveTo(WIDTH / 2, CENTER_Y);
    context.lineTo(cameraX, cameraY);
    context.stroke();

    const heading = Math.atan2(CENTER_Y - cameraY, WIDTH / 2 - cameraX);
    context.translate(cameraX, cameraY);
    context.rotate(heading + Math.PI / 2);
    context.fillStyle = '#e93d82';
    context.beginPath();
    context.moveTo(0, -12);
    context.lineTo(9, 10);
    context.lineTo(-9, 10);
    context.closePath();
    context.fill();
    context.restore();

    context.fillStyle = '#00ffd0';
    context.beginPath();
    context.arc(35, CENTER_Y - elevationOffset, 5, 0, Math.PI * 2);
    context.fill();
    context.strokeStyle = 'rgba(0, 255, 208, 0.55)';
    context.beginPath();
    context.moveTo(35, CENTER_Y + 19);
    context.lineTo(35, CENTER_Y - 42);
    context.stroke();
}

function drawCameraView(context, state) {
    context.fillStyle = '#12121a';
    context.fillRect(9, 51, WIDTH - 18, 213);
    const drawn = state.imageReady && drawFittedImage(
        context, state.image, 12, 54, WIDTH - 24, 207,
    );
    if (!drawn) {
        const gradient = context.createLinearGradient(12, 54, 12, 261);
        gradient.addColorStop(0, '#29293a');
        gradient.addColorStop(1, '#111119');
        context.fillStyle = gradient;
        context.fillRect(12, 54, WIDTH - 24, 207);
    }
    context.strokeStyle = '#e93d82';
    context.lineWidth = 2;
    context.strokeRect(9, 51, WIDTH - 18, 213);
    context.strokeStyle = 'rgba(0, 255, 208, 0.75)';
    context.beginPath();
    context.moveTo(WIDTH / 2 - 18, 157);
    context.lineTo(WIDTH / 2 + 18, 157);
    context.moveTo(WIDTH / 2, 139);
    context.lineTo(WIDTH / 2, 175);
    context.stroke();
    context.fillStyle = 'rgba(10, 10, 15, 0.82)';
    roundedRect(context, 20, 226, 118, 24, 5);
    context.fill();
    context.fillStyle = '#00ffd0';
    context.font = '11px system-ui, sans-serif';
    context.fillText('CAMERA VIEW', 31, 242);
}

function drawPanel(context, state) {
    const prompt = promptFor(state.azimuth, state.elevation, state.zoom);
    context.fillStyle = 'rgba(10, 10, 15, 0.92)';
    roundedRect(context, 8, 8, WIDTH - 16, 34, 6);
    context.fill();
    context.strokeStyle = 'rgba(233, 61, 130, 0.45)';
    context.stroke();
    context.fillStyle = '#e93d82';
    context.font = '11px ui-monospace, SFMono-Regular, monospace';
    context.fillText(prompt, 16, 29, WIDTH - 32);

    context.fillStyle = 'rgba(10, 10, 15, 0.94)';
    roundedRect(context, 8, 276, WIDTH - 16, 84, 6);
    context.fill();
    context.strokeStyle = 'rgba(233, 61, 130, 0.35)';
    context.stroke();

    const labels = [
        ['HORIZONTAL', `${Math.round(state.azimuth)}°`, '#e93d82', 63],
        ['VERTICAL', `${Math.round(state.elevation)}°`, '#00ffd0', 170],
        ['ZOOM', state.zoom.toFixed(1), '#ffb800', 267],
    ];
    context.textAlign = 'center';
    for (const [label, value, color, x] of labels) {
        context.fillStyle = '#777786';
        context.font = '9px system-ui, sans-serif';
        context.fillText(label, x, 301);
        context.fillStyle = color;
        context.font = '600 15px system-ui, sans-serif';
        context.fillText(value, x, 323);
    }
    context.fillStyle = '#6f6f7d';
    context.font = '9px system-ui, sans-serif';
    context.fillText('drag scene • wheel zoom • bottom-right resets', WIDTH / 2, 348);
    context.textAlign = 'start';

    context.fillStyle = 'rgba(233, 61, 130, 0.16)';
    roundedRect(context, WIDTH - 35, 331, 22, 20, 4);
    context.fill();
    context.strokeStyle = '#e93d82';
    context.stroke();
    context.fillStyle = '#e93d82';
    context.font = '16px system-ui, sans-serif';
    context.fillText('↻', WIDTH - 32, 347);
    return prompt;
}

function draw(instance) {
    if (!instance.active) return;
    const { context, state, canvas } = instance;
    context.clearRect(0, 0, WIDTH, HEIGHT);
    context.fillStyle = '#0a0a0f';
    context.fillRect(0, 0, WIDTH, HEIGHT);
    if (state.cameraView) drawCameraView(context, state);
    else drawOrbitScene(context, state);
    const prompt = drawPanel(context, state);
    canvas.setAttribute('title', prompt);
}

function syncFromWidgets(instance) {
    const { node, state } = instance;
    state.azimuth = clamp(widgetNumber(node, 'horizontal_angle', 0), 0, 360);
    state.elevation = clamp(widgetNumber(node, 'vertical_angle', 0), -30, 60);
    state.zoom = clamp(widgetNumber(node, 'zoom', 5), 0, 10);
    state.cameraView = Boolean(node.widgets.get('camera_view')?.getValue());
    draw(instance);
}

function writeState(instance, azimuth, elevation, zoom) {
    const values = {
        horizontal_angle: clamp(wrapAngle(azimuth), 0, 360),
        vertical_angle: clamp(Math.round(elevation), -30, 60),
        zoom: Math.round(clamp(zoom, 0, 10) * 10) / 10,
    };
    instance.state.azimuth = values.horizontal_angle;
    instance.state.elevation = values.vertical_angle;
    instance.state.zoom = values.zoom;
    for (const [name, value] of Object.entries(values)) {
        instance.node.widgets.get(name)?.setValue(value);
    }
    draw(instance);
}

function reset(instance) {
    writeState(instance, 0, 0, 5);
}

function previewUrl(item) {
    if (!item || typeof item !== 'object') return null;
    if (typeof item.filename !== 'string' || !item.filename) return null;
    const query = new URLSearchParams({
        filename: item.filename,
        subfolder: typeof item.subfolder === 'string' ? item.subfolder : '',
        type: typeof item.type === 'string' ? item.type : 'temp',
    });
    return comfy.backend.url(`/view?${query.toString()}`);
}

function updateImage(instance, descriptor) {
    instance.state.image = null;
    instance.state.imageReady = false;
    const url = previewUrl(descriptor);
    if (!url) {
        draw(instance);
        return;
    }
    const image = new Image();
    instance.state.image = image;
    image.onload = () => {
        if (!instance.active || instance.state.image !== image) return;
        instance.state.imageReady = true;
        draw(instance);
    };
    image.onerror = () => {
        if (!instance.active || instance.state.image !== image) return;
        instance.state.imageReady = false;
        draw(instance);
    };
    image.src = url;
}

function destroy(instance) {
    if (!instance?.active) return;
    instance.active = false;
    for (const unsubscribe of instance.unsubscribers.splice(0)) unsubscribe();
    instance.state.image = null;
    instance.container?.replaceChildren();
    instances.delete(instance.key);
}

function createCameraWidget(node) {
    const key = keyFor(node);
    destroy(instances.get(key));
    const state = {
        azimuth: 0,
        elevation: 0,
        zoom: 5,
        cameraView: false,
        image: null,
        imageReady: false,
    };
    const instance = {
        key,
        node,
        state,
        active: true,
        dragging: false,
        dragStart: null,
        canvas: null,
        context: null,
        container: null,
        unsubscribers: [],
    };
    instances.set(key, instance);

    node.widgets.mount({
        name: 'camera_preview',
        height: HEIGHT,
        hideOnZoom: false,
        serialize: false,
        sendToPrompt: false,
        render(container) {
            instance.container = container;
            container.style.width = '100%';
            container.style.height = `${HEIGHT}px`;
            const canvas = container.ownerDocument.createElement('canvas');
            canvas.width = WIDTH;
            canvas.height = HEIGHT;
            canvas.style.width = '100%';
            canvas.style.height = `${HEIGHT}px`;
            canvas.style.display = 'block';
            canvas.style.cursor = 'grab';
            canvas.style.touchAction = 'none';
            container.appendChild(canvas);
            instance.canvas = canvas;
            instance.context = canvas.getContext('2d');
            if (!instance.context) throw new Error('2D canvas is unavailable');

            canvas.addEventListener('pointerdown', (event) => {
                if (Number(event.offsetY) >= 326 && Number(event.offsetX) >= WIDTH - 45) {
                    reset(instance);
                    return;
                }
                instance.dragging = true;
                instance.dragStart = {
                    x: Number(event.offsetX),
                    y: Number(event.offsetY),
                    azimuth: state.azimuth,
                    elevation: state.elevation,
                };
                canvas.style.cursor = 'grabbing';
            });
            canvas.addEventListener('pointermove', (event) => {
                if (!instance.dragging || !instance.dragStart) return;
                const dx = Number(event.offsetX) - instance.dragStart.x;
                const dy = Number(event.offsetY) - instance.dragStart.y;
                writeState(
                    instance,
                    instance.dragStart.azimuth + dx * 1.2,
                    instance.dragStart.elevation - dy * 0.5,
                    state.zoom,
                );
            });
            const stopDrag = () => {
                instance.dragging = false;
                instance.dragStart = null;
                canvas.style.cursor = 'grab';
            };
            canvas.addEventListener('pointerup', stopDrag);
            canvas.addEventListener('pointercancel', stopDrag);
            canvas.addEventListener('dblclick', () => reset(instance));
            canvas.addEventListener('wheel', (event) => {
                const direction = Number(event.deltaY) > 0 ? -0.4 : 0.4;
                writeState(
                    instance, state.azimuth, state.elevation,
                    state.zoom + direction,
                );
            });
            syncFromWidgets(instance);
        },
        destroy() {
            destroy(instance);
        },
    });

    for (const name of [
        'horizontal_angle', 'vertical_angle', 'zoom', 'camera_view',
    ]) {
        const unsubscribe = node.widgets.get(name)?.on(
            'change', () => syncFromWidgets(instance),
        );
        if (typeof unsubscribe === 'function') {
            instance.unsubscribers.push(unsubscribe);
        }
    }
    syncFromWidgets(instance);
    return instance;
}

comfy.defs.extend(TARGET, (builder) => {
    builder.onCreated((node) => {
        const size = node.getSize();
        node.setSize({
            width: Math.max(Number(size.width), 350),
            height: Math.max(Number(size.height), 520),
        });
        node.setSizeConstraints({ minWidth: 350, minHeight: 520 });
        createCameraWidget(node);
    });
    builder.onConfigured((node) => {
        const instance = instances.get(keyFor(node));
        if (instance) syncFromWidgets(instance);
    });
    builder.onConnectionsChanged((node, event) => {
        if (event.side !== 'input' || event.index !== 0 || event.connected) return;
        const instance = instances.get(keyFor(node));
        if (instance) updateImage(instance, null);
    });
    builder.onExecuted((node, result) => {
        const instance = instances.get(keyFor(node));
        if (!instance) return;
        const images = result.raw?.preview_images;
        updateImage(instance, Array.isArray(images) ? images[0] : null);
    });
    builder.onRemoved((node) => destroy(instances.get(keyFor(node))));
});
