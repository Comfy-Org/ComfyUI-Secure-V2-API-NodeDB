import { comfy } from '/comfy/api/v2.js';

const MAX_UPLOAD = 16 * 1024 * 1024;
// Explicit approved managed-picker profile, not universal native image/*.
const IMAGE_MIMES = ['image/png', 'image/jpeg', 'image/webp', 'image/gif', 'image/bmp', 'image/tiff'];
const controllers = new WeakMap();
function checkedPath(value) {
    if (typeof value !== 'string' || value.length > 1024 || value.includes('\\') || value.includes(':') || value.startsWith('/') ||
        value.includes('\0') || value.split('/').some(part => part === '.' || part === '..'))
        throw new TypeError('image selection must be a managed input label');
    return value;
}
export function imagePreview(facade, value) {
    const label = checkedPath(value);
    const cut = label.lastIndexOf('/'), name = label.slice(cut + 1), folder = cut < 0 ? '' : label.slice(0, cut);
    return facade.backend.url('/view?filename=' + encodeURIComponent(name) + '&type=input&subfolder=' + encodeURIComponent(folder));
}
export function createImageGrid(node, facade, prompts) {
    let alive = true;
    const slots = [], disposers = [];
    const listen = (el, type, fn) => { el.addEventListener(type, fn); disposers.push(() => el.removeEventListener(type, fn)); };
    function refresh(slot) {
        const label = checkedPath(slot.image.getValue() || '');
        slot.thumb.src = label ? imagePreview(facade, label) : '';
        slot.thumb.style.display = label ? 'block' : 'none';
        slot.placeholder.style.display = label ? 'none' : 'flex';
        if (slot.textarea) slot.textarea.value = slot.prompt.getValue() || '';
    }
    function select(slot, label) {
        const value = checkedPath(label);
        const values = slot.image.getOptions()?.values;
        if (Array.isArray(values) && value && !values.includes(value)) slot.image.setOption('values', [...values, value]);
        slot.image.setValue(value); refresh(slot);
    }
    function clear() {
        if (!alive) return;
        for (const slot of slots) {
            slot.epoch++; select(slot, '');
            slot.status.textContent = '';
            slot.prompt?.setValue(''); refresh(slot);
        }
    }
    async function upload(slot, selected) {
        if (!alive || !selected) return;
        const epoch = ++slot.epoch;
        let file;
        if (selected instanceof File) {
            if (!Number.isSafeInteger(selected.size) || selected.size > MAX_UPLOAD) throw new RangeError('image upload exceeds bound');
            file = selected;
        } else {
            if (!(selected.bytes instanceof Uint8Array) || selected.bytes.byteLength > MAX_UPLOAD)
                throw new RangeError('image upload exceeds bound');
            file = new File([selected.bytes], selected.name, { type: selected.type });
        }
        if (!IMAGE_MIMES.includes(file.type)) throw new TypeError('image upload MIME profile refused');
        // Explicit normalization: managed publication, not arbitrary overwrite=true.
        const result = await facade.files.upload(file);
        if (alive && epoch === slot.epoch) select(slot, result.path);
    }
    const rows = 4, columns = prompts ? 1 : 3;
    for (let row = 0; row < rows; row++) {
        node.widgets.mount({
            name: 'row_' + (prompts ? row + 1 : row), height: 162, serialize: false, sendToPrompt: false,
            render(container) {
                const doc = container.ownerDocument;
                container.style.cssText = 'display:flex;gap:6px;width:100%;align-items:stretch;box-sizing:border-box;padding:3px 0';
                for (let column = 0; column < columns; column++) {
                    const index = row * columns + column + 1;
                    const image = node.widgets.get('image_' + index), prompt = prompts ? node.widgets.get('prompt_' + index) : undefined;
                    if (!image || (prompts && !prompt)) continue;
                    image.setHidden(true); if (prompt) prompt.setHidden(true);
                    const block = doc.createElement('div');
                    block.style.cssText = 'display:flex;flex-direction:column;align-items:center;gap:4px;background:#2a2a2a;border:1px solid #444;border-radius:4px;padding:5px;width:136px;flex-shrink:0;box-sizing:border-box';
                    const thumb = doc.createElement('img');
                    thumb.style.cssText = 'width:124px;height:124px;object-fit:contain;border-radius:3px;background:#1a1a1a';
                    const placeholder = doc.createElement('div'); placeholder.textContent = '#' + index;
                    placeholder.style.cssText = 'width:124px;height:124px;align-items:center;justify-content:center;color:#666;font-size:13px;background:#1a1a1a;border-radius:3px';
                    const browse = doc.createElement('button'); browse.textContent = 'browse';
                    const status = doc.createElement('span');
                    const slot = { image, prompt, thumb, placeholder, status, epoch: 0 };
                    slots.push(slot);
                    const guardedUpload = async selected => {
                        const attempt = slot.epoch + 1;
                        try { await upload(slot, selected); }
                        catch (error) { if (alive && slot.epoch === attempt) status.textContent = String(error); }
                    };
                    listen(browse, 'click', async () => {
                        const epoch = slot.epoch;
                        try {
                            status.textContent = '';
                            const selected = await facade.files.pick({ mimeTypes: IMAGE_MIMES, maxBytes: MAX_UPLOAD });
                            if (alive && epoch === slot.epoch) await guardedUpload(selected);
                        } catch (error) {
                            if (alive && epoch === slot.epoch) status.textContent = String(error);
                        }
                    });
                    listen(block, 'dragover', event => { event.preventDefault(); event.stopPropagation(); block.style.borderColor = '#888'; });
                    listen(block, 'dragleave', event => { event.preventDefault(); event.stopPropagation(); block.style.borderColor = '#444'; });
                    listen(block, 'drop', async event => {
                        event.preventDefault(); event.stopPropagation(); block.style.borderColor = '#444';
                        const selected = event.dataTransfer?.files?.[0];
                        if (selected?.type?.startsWith('image/')) await guardedUpload(selected);
                    });
                    block.append(thumb, placeholder, browse, status); container.append(block);
                    disposers.push(image.on('change', () => { if (alive) refresh(slot); }));
                    if (prompt) {
                        const textarea = doc.createElement('textarea');
                        textarea.placeholder = 'prompt_' + index;
                        textarea.style.cssText = 'flex:1;min-width:0;min-height:150px;resize:vertical;background:#2a2a2a;border:1px solid #444;border-radius:4px;color:#fff;font-size:11px;padding:4px 6px;box-sizing:border-box;outline:none';
                        slot.textarea = textarea;
                        listen(textarea, 'input', () => {
                            if (!alive) return;
                            if (new TextEncoder().encode(textarea.value).length > 65536) throw new RangeError('prompt text exceeds bound');
                            prompt.setValue(textarea.value);
                        });
                        disposers.push(prompt.on('change', () => { if (alive) refresh(slot); }));
                        container.append(textarea);
                    }
                    refresh(slot);
                }
            },
            destroy() { dispose(); },
        });
    }
    node.widgets.mount({
        name: 'clear_button', height: 44, serialize: false, sendToPrompt: false,
        render(container) {
            const button = container.ownerDocument.createElement('button'); button.textContent = 'Clear All';
            listen(button, 'click', clear); container.append(button);
        },
        destroy() { dispose(); },
    });
    node.setSizeConstraints({ minWidth: prompts ? 560 : 450, minHeight: rows * 162 + (prompts ? 40 : 70), autoHeight: true });
    function dispose() {
        if (!alive) return; alive = false;
        for (const slot of slots) slot.epoch++;
        for (const off of disposers.splice(0)) off();
    }
    return { clear, dispose, configured() { if (alive) for (const slot of slots) refresh(slot); } };
}
export function registerImageGrid(kind, prompts) {
    comfy.defs.extend(kind, builder => {
        builder.onCreated(node => { controllers.set(node, createImageGrid(node, comfy, prompts)); });
        builder.onConfigured(node => { controllers.get(node)?.configured(); });
        builder.onRemoved(node => { controllers.get(node)?.dispose(); controllers.delete(node); });
        // Claim node-wide drop without recovering node.imgs or host objects.
        builder.onDragDrop?.(() => true);
    });
}
// Active confined frontend graph; archival diagnostics are outside WEB_DIRECTORY.
