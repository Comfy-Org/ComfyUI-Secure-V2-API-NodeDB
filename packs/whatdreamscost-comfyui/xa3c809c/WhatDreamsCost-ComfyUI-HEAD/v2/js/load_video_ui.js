import { comfy } from '/comfy/api/v2.js';

const TARGET = 'LoadVideoUI';
const states = new Map();
const keyFor = (node) => `${node.graphId ?? ''}:${node.id}`;
const clamp = (value, low, high) => Math.max(low, Math.min(high, value));

function logicalPath(value) {
    let path = String(value || '').trim().replace(/\s*\[input\]\s*$/, '').replaceAll('\\', '/');
    if (path.startsWith('input/')) path = path.slice(6);
    return path;
}

function assetUrl(value) {
    const path = logicalPath(value);
    const slash = path.lastIndexOf('/');
    const filename = slash < 0 ? path : path.slice(slash + 1);
    const subfolder = slash < 0 ? '' : path.slice(0, slash);
    return comfy.backend.assetUrl(`/view?${new URLSearchParams({ filename, subfolder, type: 'input' })}`);
}

async function upload(file) {
    const result = await comfy.files.upload(file, { subfolder: 'whatdreamscost' });
    return result.path;
}

function number(state, name, fallback = 0) {
    const value = Number(state.node.widgets.get(name)?.getValue());
    return Number.isFinite(value) ? value : fallback;
}

function setNumber(state, name, value, digits = 3) {
    const widget = state.node.widgets.get(name);
    if (!widget) return;
    const next = digits === 0 ? Math.round(value) : Number(value.toFixed(digits));
    if (Number(widget.getValue()) !== next) widget.setValue(next);
}

function syncBounds(state, source = 'time') {
    const rate = Math.max(1, number(state, 'frame_rate', 24));
    if (source === 'frames') {
        const start = Math.max(0, number(state, 'start_frame'));
        const end = Math.max(start, number(state, 'end_frame'));
        setNumber(state, 'start_time', start / rate);
        setNumber(state, 'end_time', end / rate);
        setNumber(state, 'duration', (end - start) / rate);
        setNumber(state, 'duration_frames', end - start, 0);
    } else {
        const start = Math.max(0, number(state, 'start_time'));
        const end = Math.max(start, number(state, 'end_time'));
        setNumber(state, 'start_frame', start * rate, 0);
        setNumber(state, 'end_frame', end * rate, 0);
        setNumber(state, 'duration', end - start);
        setNumber(state, 'duration_frames', (end - start) * rate, 0);
    }
    renderBounds(state);
}

function setMode(state, mode) {
    state.node.widgets.get('display_mode')?.setValue(mode);
    const frames = mode === 'frames';
    for (const name of ['start_frame', 'end_frame', 'duration_frames']) state.node.widgets.get(name)?.setHidden(!frames);
    for (const name of ['start_time', 'end_time', 'duration']) state.node.widgets.get(name)?.setHidden(frames);
    state.node.widgets.get('display_mode')?.setHidden(true);
    if (state.secondsButton) {
        state.secondsButton.dataset.active = String(!frames);
        state.framesButton.dataset.active = String(frames);
        state.secondsButton.style.background = frames ? '#252525' : '#4a4f5b';
        state.framesButton.style.background = frames ? '#4a4f5b' : '#252525';
    }
    renderBounds(state);
}

function renderBounds(state) {
    if (!state.startRange) return;
    const mode = String(state.node.widgets.get('display_mode')?.getValue() || 'seconds');
    const duration = state.mediaDuration || 0;
    const rate = Math.max(1, number(state, 'frame_rate', 24));
    const maximum = mode === 'frames' ? Math.max(1, Math.round(duration * rate)) : Math.max(0.01, duration);
    const start = mode === 'frames' ? number(state, 'start_frame') : number(state, 'start_time');
    const endRaw = mode === 'frames' ? number(state, 'end_frame') : number(state, 'end_time');
    const end = endRaw > start ? endRaw : maximum;
    state.startRange.max = state.endRange.max = String(maximum);
    state.startRange.step = state.endRange.step = mode === 'frames' ? '1' : '0.01';
    state.startRange.value = String(clamp(start, 0, maximum));
    state.endRange.value = String(clamp(end, start, maximum));
    const delta = Math.max(0, end - start);
    state.trimReadout.textContent = mode === 'frames'
        ? `Trimmed: ${Math.round(delta)} frames`
        : `Trimmed: ${delta.toFixed(2)}s`;
}

function commitRanges(state) {
    const mode = String(state.node.widgets.get('display_mode')?.getValue() || 'seconds');
    const start = Number(state.startRange.value);
    const end = Math.max(start, Number(state.endRange.value));
    if (mode === 'frames') {
        setNumber(state, 'start_frame', start, 0);
        setNumber(state, 'end_frame', end, 0);
        syncBounds(state, 'frames');
    } else {
        setNumber(state, 'start_time', start);
        setNumber(state, 'end_time', end);
        syncBounds(state, 'time');
    }
}

function updateCrop(state) {
    if (!state.cropBox) return;
    const x = clamp(number(state, 'crop_x'), 0, 1);
    const y = clamp(number(state, 'crop_y'), 0, 1);
    const width = clamp(number(state, 'crop_w', 1), 0.001, 1 - x);
    const height = clamp(number(state, 'crop_h', 1), 0.001, 1 - y);
    state.cropBox.style.left = `${x * 100}%`;
    state.cropBox.style.top = `${y * 100}%`;
    state.cropBox.style.width = `${width * 100}%`;
    state.cropBox.style.height = `${height * 100}%`;
    state.cropReadout.textContent = `${Math.round(width * state.video.videoWidth || 0)}×${Math.round(height * state.video.videoHeight || 0)}`;
}

function installCropGesture(state) {
    let gesture = null;
    state.cropBox.addEventListener('pointerdown', (event) => {
        event.preventDefault();
        state.cropBox.setPointerCapture(event.pointerId);
        gesture = {
            x: event.clientX,
            y: event.clientY,
            cropX: number(state, 'crop_x'),
            cropY: number(state, 'crop_y'),
            cropW: number(state, 'crop_w', 1),
            cropH: number(state, 'crop_h', 1),
            resize: event.target === state.cropHandle,
        };
    });
    state.cropBox.addEventListener('pointermove', (event) => {
        if (!gesture) return;
        const bounds = state.videoWrap.getBoundingClientRect();
        const dx = (event.clientX - gesture.x) / Math.max(1, bounds.width);
        const dy = (event.clientY - gesture.y) / Math.max(1, bounds.height);
        if (gesture.resize) {
            setNumber(state, 'crop_w', clamp(gesture.cropW + dx, 0.02, 1 - gesture.cropX));
            setNumber(state, 'crop_h', clamp(gesture.cropH + dy, 0.02, 1 - gesture.cropY));
        } else {
            setNumber(state, 'crop_x', clamp(gesture.cropX + dx, 0, 1 - gesture.cropW));
            setNumber(state, 'crop_y', clamp(gesture.cropY + dy, 0, 1 - gesture.cropH));
        }
        updateCrop(state);
    });
    state.cropBox.addEventListener('pointerup', () => { gesture = null; });
    state.cropBox.addEventListener('pointercancel', () => { gesture = null; });
}

function loadPreview(state, reset = false) {
    const value = state.node.widgets.get('video')?.getValue();
    if (!value || value === 'none') {
        state.video.removeAttribute('src');
        state.mediaDuration = 0;
        renderBounds(state);
        return;
    }
    state.resetOnLoad = reset;
    state.filename.textContent = logicalPath(value).split('/').pop() || 'Video';
    state.video.src = assetUrl(value);
    state.video.load();
}

function mount(state, container) {
    const doc = container.ownerDocument;
    const root = doc.createElement('div');
    root.style.cssText = 'display:flex;flex-direction:column;gap:7px;padding:8px;background:#222;color:#eee';
    const top = doc.createElement('div');
    top.style.cssText = 'display:flex;gap:6px;align-items:center;flex-wrap:wrap';
    state.filename = doc.createElement('strong');
    state.filename.style.cssText = 'flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap';
    state.secondsButton = doc.createElement('button');
    state.framesButton = doc.createElement('button');
    state.secondsButton.textContent = 'Seconds';
    state.framesButton.textContent = 'Frames';
    const uploadButton = doc.createElement('button');
    uploadButton.textContent = 'Upload Video';
    for (const button of [state.secondsButton, state.framesButton, uploadButton]) {
        button.style.cssText = 'padding:5px 8px;border:1px solid #666;border-radius:4px;color:#eee;background:#333;cursor:pointer';
        top.appendChild(button);
    }
    const input = doc.createElement('input');
    input.type = 'file';
    input.accept = 'video/*';
    input.hidden = true;
    top.appendChild(input);
    root.appendChild(top);

    state.videoWrap = doc.createElement('div');
    state.videoWrap.style.cssText = 'position:relative;width:100%;min-height:220px;background:#111;overflow:hidden';
    state.video = doc.createElement('video');
    state.video.controls = true;
    state.video.style.cssText = 'display:block;width:100%;max-height:480px;object-fit:contain';
    state.cropBox = doc.createElement('div');
    state.cropBox.style.cssText = 'position:absolute;border:2px solid #62d2ff;box-shadow:0 0 0 9999px #0007;box-sizing:border-box;cursor:move;pointer-events:auto';
    state.cropHandle = doc.createElement('span');
    state.cropHandle.style.cssText = 'position:absolute;right:-6px;bottom:-6px;width:12px;height:12px;background:#62d2ff;cursor:nwse-resize';
    state.cropReadout = doc.createElement('span');
    state.cropReadout.style.cssText = 'position:absolute;left:3px;top:3px;padding:2px 4px;background:#000b;font-size:11px';
    state.cropBox.append(state.cropHandle, state.cropReadout);
    state.videoWrap.append(state.video, state.cropBox);
    root.appendChild(state.videoWrap);
    installCropGesture(state);

    state.trimReadout = doc.createElement('small');
    root.appendChild(state.trimReadout);
    state.startRange = doc.createElement('input');
    state.endRange = doc.createElement('input');
    for (const range of [state.startRange, state.endRange]) {
        range.type = 'range';
        range.min = '0';
        range.max = '1';
        root.appendChild(range);
        range.addEventListener('input', () => { commitRanges(state); });
    }

    state.secondsButton.addEventListener('click', () => setMode(state, 'seconds'));
    state.framesButton.addEventListener('click', () => setMode(state, 'frames'));
    uploadButton.addEventListener('click', () => input.click());
    input.addEventListener('change', async () => {
        const file = input.files?.[0];
        if (!file) return;
        uploadButton.disabled = true;
        uploadButton.textContent = 'Uploading…';
        try {
            state.node.widgets.get('video')?.setValue(await upload(file));
            loadPreview(state, true);
        } catch (error) {
            comfy.commands.notify({ severity: 'error', summary: 'Video upload failed', detail: String(error) });
        } finally {
            uploadButton.disabled = false;
            uploadButton.textContent = 'Upload Video';
            input.value = '';
        }
    });
    state.video.addEventListener('loadedmetadata', () => {
        state.mediaDuration = Number.isFinite(state.video.duration) ? state.video.duration : 0;
        if (state.resetOnLoad) {
            setNumber(state, 'start_time', 0);
            setNumber(state, 'end_time', state.mediaDuration);
            syncBounds(state, 'time');
        }
        state.resetOnLoad = false;
        updateCrop(state);
        renderBounds(state);
    });
    state.video.addEventListener('timeupdate', () => {
        const mode = String(state.node.widgets.get('display_mode')?.getValue() || 'seconds');
        const rate = Math.max(1, number(state, 'frame_rate', 24));
        const start = mode === 'frames' ? number(state, 'start_frame') / rate : number(state, 'start_time');
        const end = mode === 'frames' ? number(state, 'end_frame') / rate : number(state, 'end_time');
        if (end > start && state.video.currentTime >= end) {
            state.video.pause();
            state.video.currentTime = start;
        }
    });
    container.appendChild(root);
    setMode(state, String(state.node.widgets.get('display_mode')?.getValue() || 'seconds'));
    loadPreview(state, false);
    updateCrop(state);
}

comfy.defs.extend(TARGET, (builder) => {
    for (const name of ['display_mode', 'crop_x', 'crop_y', 'crop_w', 'crop_h']) builder.hideWidget(name);
    builder.onCreated((node) => {
        const state = { node, mediaDuration: 0, resetOnLoad: false, unsubscribers: [] };
        states.set(keyFor(node), state);
        for (const name of ['display_mode', 'crop_x', 'crop_y', 'crop_w', 'crop_h']) node.widgets.get(name)?.setHidden(true);
        state.unsubscribers.push(node.widgets.get('video')?.on('change', () => state.video && loadPreview(state, true)));
        for (const name of ['crop_x', 'crop_y', 'crop_w', 'crop_h']) {
            const unsubscribe = node.widgets.get(name)?.on('change', () => updateCrop(state));
            if (unsubscribe) state.unsubscribers.push(unsubscribe);
        }
        node.widgets.mount({
            name: 'whatdreamscost_video_player',
            hideOnZoom: false,
            render: (container) => mount(state, container),
            destroy() { state.video?.pause(); },
        });
        node.setSizeConstraints({ minWidth: 520, autoHeight: true });
    });
    builder.onConfigured((node) => {
        const state = states.get(keyFor(node));
        if (!state?.video) return;
        setMode(state, String(node.widgets.get('display_mode')?.getValue() || 'seconds'));
        loadPreview(state, false);
        updateCrop(state);
    });
    builder.onRemoved((node) => {
        const state = states.get(keyFor(node));
        state?.video?.pause();
        for (const unsubscribe of state?.unsubscribers || []) unsubscribe?.();
        states.delete(keyFor(node));
    });
});
