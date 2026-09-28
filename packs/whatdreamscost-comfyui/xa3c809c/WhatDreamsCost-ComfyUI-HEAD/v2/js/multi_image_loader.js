import { comfy } from '/comfy/api/v2.js';

const TARGET = 'MultiImageLoader';
const MAX_IMAGES = 50;
const MAX_IMAGE_BYTES = 32 * 1024 * 1024;
const MAX_TOTAL_BYTES = 256 * 1024 * 1024;
const IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp'];
const IMAGE_MIME_TYPES = ['image/png', 'image/jpeg', 'image/webp', 'image/gif', 'image/bmp'];
const states = new Map();

function stateKey(node) {
    return `${node.graphId ?? ''}:${node.id}`;
}

function parsePaths(value) {
    if (typeof value !== 'string') return [];
    return value.split('\n').map((item) => item.trim()).filter(Boolean).slice(0, MAX_IMAGES);
}

function safePath(value) {
    if (!value || /[\0-\x1f\x7f]/.test(value)) throw new Error('upload returned an invalid path');
    const parts = value.split(/[\\/]/);
    if (parts.some((part) => part === '..')) throw new Error('upload path escapes input storage');
    return value;
}

function splitPath(path) {
    const normalized = path.replaceAll('\\', '/');
    const slash = normalized.lastIndexOf('/');
    return slash < 0
        ? { filename: normalized, subfolder: '' }
        : { filename: normalized.slice(slash + 1), subfolder: normalized.slice(0, slash) };
}

function previewUrl(path) {
    const { filename, subfolder } = splitPath(path);
    const query = new URLSearchParams({ filename, subfolder, type: 'input' });
    return comfy.backend.assetUrl(`/view?${query.toString()}`);
}

async function uploadImage(file) {
    const selected = new File([file.bytes], file.name, {
        type: file.type || 'application/octet-stream',
    });
    return safePath((await comfy.files.upload(selected, {
        subfolder: 'whatdreamscost',
    })).path);
}

function commit(state) {
    state.pathsWidget.setValue(state.paths.join('\n'));
}

function makeButton(doc, label, color) {
    const button = doc.createElement('button');
    button.textContent = label;
    button.style.cssText = `padding:5px 9px;background:${color};border:1px solid #555;border-radius:4px;color:#eee;cursor:pointer`;
    return button;
}

function render(state) {
    const { container, doc } = state;
    container.replaceChildren();
    const root = doc.createElement('div');
    root.style.cssText = 'display:flex;flex-direction:column;gap:7px;padding:6px;background:#222;color:#eee';
    const controls = doc.createElement('div');
    controls.style.cssText = 'display:flex;gap:6px;flex-wrap:wrap';
    const upload = makeButton(doc, 'Upload Images', '#3a3f4b');
    const clear = makeButton(doc, state.confirmClear ? 'Confirm Remove All' : 'Remove All', '#9d2424');
    controls.append(upload, clear);
    root.appendChild(controls);

    const status = doc.createElement('small');
    status.textContent = state.status || `${state.paths.length}/${MAX_IMAGES} images`;
    status.style.color = '#bbb';
    root.appendChild(status);

    const grid = doc.createElement('div');
    grid.style.cssText = 'display:grid;grid-template-columns:repeat(auto-fill,minmax(105px,1fr));gap:7px;max-height:420px;overflow:auto';
    let dragged = -1;
    state.paths.forEach((path, index) => {
        const item = doc.createElement('div');
        item.draggable = true;
        item.style.cssText = 'position:relative;aspect-ratio:1;background:#111;border:1px solid #444;border-radius:4px;overflow:hidden;cursor:grab';
        const image = doc.createElement('img');
        image.src = previewUrl(path);
        image.alt = path;
        image.draggable = false;
        image.style.cssText = 'width:100%;height:100%;object-fit:contain';
        const label = doc.createElement('span');
        label.textContent = `${index + 1}`;
        label.title = path;
        label.style.cssText = 'position:absolute;left:3px;bottom:3px;padding:1px 4px;background:#000b;border-radius:3px;font-size:10px';
        const remove = makeButton(doc, '×', '#b22');
        remove.style.cssText += ';position:absolute;right:2px;top:2px;padding:0;width:22px;height:22px';
        remove.addEventListener('click', () => {
            state.paths.splice(index, 1);
            commit(state);
            render(state);
        });
        item.addEventListener('dragstart', () => { dragged = index; });
        item.addEventListener('dragover', (event) => event.preventDefault());
        item.addEventListener('drop', (event) => {
            event.preventDefault();
            if (dragged < 0 || dragged === index) return;
            const [moved] = state.paths.splice(dragged, 1);
            state.paths.splice(index, 0, moved);
            dragged = -1;
            commit(state);
            render(state);
        });
        item.append(image, label, remove);
        grid.appendChild(item);
    });
    root.appendChild(grid);

    upload.addEventListener('click', async () => {
        try {
            const remaining = MAX_IMAGES - state.paths.length;
            if (remaining <= 0) throw new Error(`maximum ${MAX_IMAGES} images reached`);
            const files = await comfy.files.pickMany({
                extensions: IMAGE_EXTENSIONS,
                mimeTypes: IMAGE_MIME_TYPES,
                maxBytes: MAX_IMAGE_BYTES,
                maxFiles: remaining,
                maxTotalBytes: MAX_TOTAL_BYTES,
            });
            for (let index = 0; index < files.length; index += 1) {
                state.status = `Uploading ${index + 1}/${files.length}…`;
                render(state);
                state.paths.push(await uploadImage(files[index]));
                commit(state);
            }
            state.status = '';
        } catch (error) {
            state.status = String(error);
        }
        render(state);
    });
    clear.addEventListener('click', () => {
        if (!state.confirmClear) state.confirmClear = true;
        else {
            state.paths = [];
            state.confirmClear = false;
            commit(state);
        }
        render(state);
    });
    container.appendChild(root);
}

comfy.defs.extend(TARGET, (builder) => {
    builder.hideWidget('image_paths');
    builder.onCreated((node) => {
        const pathsWidget = node.widgets.get('image_paths');
        if (!pathsWidget) return;
        pathsWidget.setHidden(true);
        const state = {
            node,
            pathsWidget,
            paths: parsePaths(pathsWidget.getValue()),
            status: '',
            confirmClear: false,
            container: null,
            doc: null,
        };
        states.set(stateKey(node), state);
        node.widgets.mount({
            name: 'whatdreamscost_image_gallery',
            hideOnZoom: false,
            render(container) {
                state.container = container;
                state.doc = container.ownerDocument;
                render(state);
            },
            destroy() {
                state.container?.replaceChildren();
                state.container = null;
            },
        });
        node.setSizeConstraints({ minWidth: 420, autoHeight: true });
        const size = node.getSize();
        if (size.width < 420) node.setSize({ width: 420, height: size.height });
    });
    builder.onConfigured((node) => {
        const state = states.get(stateKey(node));
        if (!state) return;
        state.paths = parsePaths(state.pathsWidget.getValue());
        state.status = '';
        state.confirmClear = false;
        if (state.container) render(state);
    });
    builder.onRemoved((node) => {
        const state = states.get(stateKey(node));
        state?.container?.replaceChildren();
        states.delete(stateKey(node));
    });
});
