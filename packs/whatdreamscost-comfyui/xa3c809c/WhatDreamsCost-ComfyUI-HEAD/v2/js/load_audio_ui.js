import { comfy } from '/comfy/api/v2.js';

const TARGET = 'LoadAudioUI';
const states = new Map();
const keyFor = (node) => `${node.graphId ?? ''}:${node.id}`;

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
    const query = new URLSearchParams({ filename, subfolder, type: 'input' });
    return comfy.backend.assetUrl(`/view?${query.toString()}`);
}

async function upload(file) {
    const result = await comfy.files.upload(file, { subfolder: 'whatdreamscost' });
    return result.path;
}

function setRange(state, start, end) {
    const duration = Math.max(0, state.duration);
    let first = Math.max(0, Math.min(duration, Number(start) || 0));
    let last = Math.max(first, Math.min(duration, Number(end) || duration));
    state.startWidget.setValue(Number(first.toFixed(3)));
    state.endWidget.setValue(Number(last.toFixed(3)));
    state.durationWidget.setValue(Number((last - first).toFixed(3)));
    if (state.startRange) {
        state.startRange.max = String(duration || 1);
        state.endRange.max = String(duration || 1);
        state.startRange.value = String(first);
        state.endRange.value = String(last);
        state.readout.textContent = `Trimmed: ${(last - first).toFixed(2)}s`;
    }
}

function loadPreview(state, reset = false) {
    const value = state.audioWidget.getValue();
    if (!value || value === 'none') {
        state.audio.removeAttribute('src');
        state.duration = 0;
        setRange(state, 0, 0);
        return;
    }
    state.resetOnLoad = reset;
    state.title.textContent = logicalPath(value).split('/').pop() || 'Audio';
    state.audio.src = assetUrl(value);
    state.audio.load();
}

function mount(state, container) {
    const doc = container.ownerDocument;
    const root = doc.createElement('div');
    root.style.cssText = 'display:flex;flex-direction:column;gap:8px;padding:8px;background:#222;color:#eee';
    const header = doc.createElement('div');
    header.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:8px';
    state.title = doc.createElement('strong');
    state.title.textContent = 'Audio';
    const choose = doc.createElement('button');
    choose.textContent = 'Upload Audio';
    choose.style.cssText = 'padding:5px 9px;background:#3a3f4b;border:1px solid #666;border-radius:4px;color:#eee;cursor:pointer';
    const input = doc.createElement('input');
    input.type = 'file';
    input.accept = 'audio/*,video/*';
    input.hidden = true;
    header.append(state.title, choose, input);
    root.appendChild(header);

    state.audio = doc.createElement('audio');
    state.audio.controls = true;
    state.audio.style.width = '100%';
    root.appendChild(state.audio);
    state.readout = doc.createElement('small');
    state.readout.textContent = 'Trimmed: 0.00s';
    root.appendChild(state.readout);
    const ranges = doc.createElement('div');
    ranges.style.cssText = 'display:grid;grid-template-columns:1fr;gap:3px';
    state.startRange = doc.createElement('input');
    state.endRange = doc.createElement('input');
    for (const range of [state.startRange, state.endRange]) {
        range.type = 'range';
        range.min = '0';
        range.max = '1';
        range.step = '0.01';
        ranges.appendChild(range);
    }
    root.appendChild(ranges);

    state.audio.addEventListener('loadedmetadata', () => {
        state.duration = Number.isFinite(state.audio.duration) ? state.audio.duration : 0;
        if (state.resetOnLoad) setRange(state, 0, state.duration);
        else setRange(state, state.startWidget.getValue(), state.endWidget.getValue() || state.duration);
        state.resetOnLoad = false;
    });
    state.audio.addEventListener('timeupdate', () => {
        const end = Number(state.endWidget.getValue()) || state.duration;
        if (state.audio.currentTime >= end) {
            state.audio.pause();
            state.audio.currentTime = Number(state.startWidget.getValue()) || 0;
        }
    });
    state.startRange.addEventListener('input', () => setRange(state, state.startRange.value, state.endRange.value));
    state.endRange.addEventListener('input', () => setRange(state, state.startRange.value, state.endRange.value));
    choose.addEventListener('click', () => input.click());
    input.addEventListener('change', async () => {
        const file = input.files?.[0];
        if (!file) return;
        choose.disabled = true;
        choose.textContent = 'Uploading…';
        try {
            state.audioWidget.setValue(await upload(file));
            loadPreview(state, true);
        } catch (error) {
            comfy.commands.notify({ severity: 'error', summary: 'Audio upload failed', detail: String(error) });
        } finally {
            choose.disabled = false;
            choose.textContent = 'Upload Audio';
            input.value = '';
        }
    });
    container.appendChild(root);
    loadPreview(state, false);
}

comfy.defs.extend(TARGET, (builder) => {
    builder.hideWidget('audioUI');
    builder.onCreated((node) => {
        const state = {
            node,
            audioWidget: node.widgets.get('audio'),
            startWidget: node.widgets.get('start_time'),
            endWidget: node.widgets.get('end_time'),
            durationWidget: node.widgets.get('duration'),
            duration: 0,
            resetOnLoad: false,
            unsubscribers: [],
        };
        if (!state.audioWidget || !state.startWidget || !state.endWidget || !state.durationWidget) return;
        node.widgets.get('audioUI')?.setHidden(true);
        states.set(keyFor(node), state);
        state.unsubscribers.push(state.audioWidget.on('change', () => loadPreview(state, true)));
        node.widgets.mount({
            name: 'whatdreamscost_audio_player',
            hideOnZoom: false,
            render: (container) => mount(state, container),
            destroy() { state.audio?.pause(); },
        });
        node.setSizeConstraints({ minWidth: 440, autoHeight: true });
    });
    builder.onConfigured((node) => {
        const state = states.get(keyFor(node));
        if (state?.audio) loadPreview(state, false);
    });
    builder.onRemoved((node) => {
        const state = states.get(keyFor(node));
        state?.audio?.pause();
        for (const unsubscribe of state?.unsubscribers || []) unsubscribe();
        states.delete(keyFor(node));
    });
});
