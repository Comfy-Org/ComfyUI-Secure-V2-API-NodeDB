import { comfy } from '/comfy/api/v2.js';

const NODE_TYPE = 'WanMultiImageLoader';
const MAX_IMAGES = 50;
const MAX_IMAGE_BYTES = 16 * 1024 * 1024;
const MAX_TOTAL_BYTES = 256 * 1024 * 1024;
const IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp'];
const IMAGE_MIME_TYPES = [
    'image/png', 'image/jpeg', 'image/webp', 'image/gif', 'image/bmp',
];
const states = new Map();
let uploadSequence = 0;

function stateKey(node) {
    return `${node.graphId ?? ''}:${node.id}`;
}

function parseImages(value) {
    if (typeof value !== 'string' || !value.trim()) return [];
    try {
        const parsed = JSON.parse(value);
        if (!Array.isArray(parsed)) return [];
        return parsed.slice(0, MAX_IMAGES).flatMap((item) => {
            if (!item || typeof item !== 'object') return [];
            const name = typeof item.name === 'string' ? item.name : '';
            const type = ['input', 'temp', 'output'].includes(item.type)
                ? item.type : 'input';
            const subfolder = typeof item.subfolder === 'string'
                ? item.subfolder : '';
            if (!name || /[\\/\0-\x1f\x7f]/.test(name)) return [];
            if (subfolder.split(/[\\/]/).some((part) => part === '..')) return [];
            return [{ name, type, subfolder }];
        });
    } catch {
        return [];
    }
}

function slim(images) {
    return images.map(({ name, type = 'input', subfolder = '' }) => ({
        name, type, subfolder,
    }));
}

function sync(state) {
    state.dataWidget.setValue(JSON.stringify(slim(state.images)));
}

function previewUrl(item) {
    const query = new URLSearchParams({
        filename: item.name,
        subfolder: item.subfolder || '',
        type: item.type || 'input',
    });
    return comfy.backend.assetUrl(`/view?${query.toString()}`);
}

function concatBytes(...parts) {
    const length = parts.reduce((total, part) => total + part.byteLength, 0);
    const result = new Uint8Array(length);
    let offset = 0;
    for (const part of parts) {
        result.set(part, offset);
        offset += part.byteLength;
    }
    return result;
}

async function uploadImage(file) {
    uploadSequence += 1;
    const boundary = `----secure-wan22fmlf-${uploadSequence}`;
    const encoder = new TextEncoder();
    const mimeType = file.type || 'application/octet-stream';
    const uploadName = file.name.replaceAll('"', '_');
    const header = encoder.encode(
        `--${boundary}\r\n` +
        `Content-Disposition: form-data; name="image"; filename="${uploadName}"\r\n` +
        `Content-Type: ${mimeType}\r\n\r\n`,
    );
    const footer = encoder.encode(`\r\n--${boundary}--\r\n`);
    const response = await comfy.backend.fetch('/upload/image', {
        method: 'POST',
        headers: { 'Content-Type': `multipart/form-data; boundary=${boundary}` },
        body: concatBytes(header, file.bytes, footer),
    });
    if (!response.ok) throw new Error(`image upload failed (${response.status})`);
    const value = await response.json();
    if (!value || typeof value !== 'object' ||
        typeof value.name !== 'string' || !value.name ||
        /[\\/\0-\x1f\x7f]/.test(value.name)) {
        throw new Error('image upload returned an invalid identity');
    }
    const type = ['input', 'temp', 'output'].includes(value.type)
        ? value.type : 'input';
    const subfolder = typeof value.subfolder === 'string'
        ? value.subfolder : '';
    if (subfolder.split(/[\\/]/).some((part) => part === '..')) {
        throw new Error('image upload returned an escaping subfolder');
    }
    return { name: value.name, type, subfolder };
}

function button(doc, label, color) {
    const element = doc.createElement('button');
    element.textContent = label;
    element.style.cssText = [
        'flex:1', 'padding:6px 8px', `background:${color}`,
        'border:1px solid #666', 'border-radius:4px', 'color:#eee',
        'font-size:12px', 'cursor:pointer',
    ].join(';');
    return element;
}

function render(state) {
    const { container, doc } = state;
    container.replaceChildren();
    const root = doc.createElement('div');
    root.style.cssText = 'display:flex;flex-direction:column;gap:6px;padding:4px';

    const controls = doc.createElement('div');
    controls.style.cssText = 'display:flex;gap:4px';
    const replaceButton = button(doc, '📁 Select', '#2f2f2f');
    const addButton = button(doc, '➕ Add', '#244a24');
    const sortButton = button(doc, '🔃 Sort', '#222a4a');
    const clearButton = button(
        doc, state.confirmClear ? 'Confirm clear' : '🗑️ Clear', '#4a2222',
    );
    controls.appendChild(replaceButton);
    controls.appendChild(addButton);
    controls.appendChild(sortButton);
    controls.appendChild(clearButton);
    root.appendChild(controls);

    const status = doc.createElement('small');
    status.textContent = state.status || `${state.images.length}/${MAX_IMAGES} images`;
    status.style.cssText = 'color:#bbb;min-height:14px';
    root.appendChild(status);

    const grid = doc.createElement('div');
    grid.style.cssText = [
        'display:grid', 'grid-template-columns:repeat(auto-fill,minmax(90px,1fr))',
        'gap:6px', 'max-height:280px', 'overflow-y:auto',
        'background:#1f1f1f', 'border-radius:4px', 'padding:4px',
    ].join(';');
    root.appendChild(grid);

    state.orderValues = new Map();
    state.images.forEach((item, index) => {
        const wrapper = doc.createElement('div');
        wrapper.style.cssText = 'display:flex;flex-direction:column;gap:3px';
        const thumb = doc.createElement('button');
        thumb.style.cssText = [
            'position:relative', 'padding:0', 'aspect-ratio:1',
            'border-radius:4px', 'overflow:hidden', 'cursor:pointer',
            `border:2px solid ${index === state.currentIndex ? '#0f0' : 'transparent'}`,
            'background:#000',
        ].join(';');
        const image = doc.createElement('img');
        image.src = previewUrl(item);
        image.alt = item.name;
        image.style.cssText = 'width:100%;height:100%;object-fit:cover';
        const label = doc.createElement('span');
        label.textContent = `#${index}`;
        label.style.cssText = [
            'position:absolute', 'left:2px', 'top:2px', 'padding:1px 3px',
            'font-size:10px', 'background:rgba(0,0,0,.7)', 'color:#fff',
        ].join(';');
        const remove = doc.createElement('button');
        remove.textContent = '×';
        remove.style.cssText = [
            'position:absolute', 'right:2px', 'top:2px', 'width:20px',
            'height:20px', 'border:0', 'background:rgba(255,0,0,.75)',
            'color:#fff', 'cursor:pointer',
        ].join(';');
        remove.addEventListener('click', (event) => {
            event.stopPropagation();
            state.images.splice(index, 1);
            state.currentIndex = Math.min(
                state.currentIndex, Math.max(0, state.images.length - 1),
            );
            state.indexWidget.setValue(state.currentIndex);
            state.status = '';
            sync(state);
            render(state);
        });
        thumb.addEventListener('click', () => {
            state.currentIndex = index;
            state.indexWidget.setValue(index);
            render(state);
        });
        thumb.appendChild(image);
        thumb.appendChild(label);
        thumb.appendChild(remove);

        const order = doc.createElement('input');
        order.type = 'number';
        order.placeholder = String(index);
        order.style.cssText = [
            'width:100%', 'box-sizing:border-box', 'background:#222',
            'border:1px solid #444', 'border-radius:3px', 'color:#eee',
            'font-size:10px', 'text-align:center',
        ].join(';');
        order.addEventListener('input', (event) => {
            state.orderValues.set(index, event.target.value);
        });
        wrapper.appendChild(thumb);
        wrapper.appendChild(order);
        grid.appendChild(wrapper);
    });

    const choose = async (replace) => {
        const remaining = replace ? MAX_IMAGES : MAX_IMAGES - state.images.length;
        if (remaining <= 0) {
            state.status = `Maximum ${MAX_IMAGES} images reached`;
            render(state);
            return;
        }
        state.status = 'Selecting images…';
        render(state);
        try {
            const files = await comfy.files.pickMany({
                extensions: IMAGE_EXTENSIONS,
                mimeTypes: IMAGE_MIME_TYPES,
                maxBytes: MAX_IMAGE_BYTES,
                maxFiles: remaining,
                maxTotalBytes: MAX_TOTAL_BYTES,
            });
            if (!files.length) {
                state.status = '';
                render(state);
                return;
            }
            const uploaded = [];
            for (const file of files) {
                state.status = `Uploading ${uploaded.length + 1}/${files.length}…`;
                render(state);
                uploaded.push(await uploadImage(file));
            }
            state.images = replace
                ? uploaded : [...state.images, ...uploaded].slice(0, MAX_IMAGES);
            state.currentIndex = Math.min(
                state.currentIndex, Math.max(0, state.images.length - 1),
            );
            state.status = '';
            sync(state);
        } catch (error) {
            state.status = `Image selection failed: ${String(error)}`;
        }
        render(state);
    };

    replaceButton.addEventListener('click', () => void choose(true));
    addButton.addEventListener('click', () => void choose(false));
    sortButton.addEventListener('click', () => {
        state.images = state.images
            .map((image, index) => {
                const raw = Number(state.orderValues.get(index));
                return { image, index, order: Number.isFinite(raw) ? raw : index };
            })
            .sort((a, b) => a.order - b.order || a.index - b.index)
            .map((entry) => entry.image);
        state.status = '';
        sync(state);
        render(state);
    });
    clearButton.addEventListener('click', () => {
        if (!state.confirmClear) {
            state.confirmClear = true;
        } else {
            state.images = [];
            state.currentIndex = 0;
            state.indexWidget.setValue(0);
            state.confirmClear = false;
            state.status = '';
            sync(state);
        }
        render(state);
    });

    container.appendChild(root);
}

comfy.defs.extend(NODE_TYPE, (builder) => {
    builder.hideWidget('images_data');

    builder.onCreated((node) => {
        const key = stateKey(node);
        if (states.has(key)) return;
        const dataWidget = node.widgets.get('images_data');
        const indexWidget = node.widgets.get('index');
        if (!dataWidget || !indexWidget) return;
        dataWidget.setHidden(true);
        const state = {
            node,
            dataWidget,
            indexWidget,
            images: parseImages(dataWidget.getValue()),
            currentIndex: Number(indexWidget.getValue()) || 0,
            status: '',
            confirmClear: false,
            orderValues: new Map(),
            unsubscribers: [],
            container: null,
            doc: null,
        };
        states.set(key, state);
        state.unsubscribers.push(indexWidget.on('change', (value) => {
            state.currentIndex = Math.max(0, Number(value) || 0);
            if (state.container) render(state);
        }));
        state.unsubscribers.push(dataWidget.on('beforeSerialize', (event) => {
            event.setSerializedValue(JSON.stringify(slim(state.images)));
        }));
        node.widgets.mount({
            name: 'wan_multi_image_gallery',
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
        state.images = parseImages(state.dataWidget.getValue());
        state.currentIndex = Math.max(0, Number(state.indexWidget.getValue()) || 0);
        state.status = '';
        state.confirmClear = false;
        if (state.container) render(state);
    });

    builder.onRemoved((node) => {
        const key = stateKey(node);
        const state = states.get(key);
        if (!state) return;
        for (const unsubscribe of state.unsubscribers) unsubscribe();
        state.container?.replaceChildren();
        states.delete(key);
    });
});
