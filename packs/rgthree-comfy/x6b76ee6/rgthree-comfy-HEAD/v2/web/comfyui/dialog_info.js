import { comfy } from '/comfy/api/v2.js';
import { LORA_INFO_SERVICE, CHECKPOINT_INFO_SERVICE } from '../../rgthree/common/model_info_service.js';

let nextDialog = 0;
const EDITABLE = [
    ['name', 'Name'], ['strengthMin', 'Strength Min'],
    ['strengthMax', 'Strength Max'], ['userNote', 'Additional Notes'],
];

export function normalizeModelInfoEdit(field, value) {
    if (!EDITABLE.some(([key]) => key === field)) throw new Error('This model info field is not editable.');
    if (field.startsWith('strength')) {
        if (!Number.isFinite(Number(value))) throw new Error('Strength must be a finite number.');
        return (Math.round(Number(value) * 100) / 100).toFixed(2);
    }
    return String(value);
}

class RgthreeInfoDialog extends EventTarget {
    constructor(file, service) {
        super(); this.file = file; this.service = service;
        this.modifiedModelData = false; this.closed = false;
    }
    show() {
        this.handle = comfy.ui.showDialog({
            key: `rgthree.model-info.${++nextDialog}`, title: this.file,
            render: (container) => { this.container = container; void this.render(); },
            destroy: () => {
                this.closed = true; this.container = null;
                this.dispatchEvent(new CustomEvent('close', { detail: { modified: this.modifiedModelData } }));
            },
        });
        return this;
    }
    async render() {
        const container = this.container;
        if (!container || this.closed) return;
        container.textContent = 'Loading model information…';
        try {
            const info = await this.service.getInfo(this.file, false, false);
            if (this.closed || this.container !== container) return;
            this.modelInfo = info;
            container.textContent = '';
            const element = (tag, text = '') => {
                const item = document.createElement(tag); item.textContent = text; return item;
            };
            const table = element('table');
            const row = (label, value) => {
                const tr = element('tr'); tr.append(element('th', label), element('td', String(value ?? ''))); table.append(tr);
            };
            row('File', info.file);
            if (info.sha256) row('Hash (sha256)', info.sha256);
            if (info.baseModel || info.baseModelFile) row('Base Model', [info.baseModel, info.baseModelFile].filter(Boolean).join(' '));
            if (info.raw?.metadata?.ss_clip_skip && info.raw.metadata.ss_clip_skip !== 'None') row('Clip Skip', info.raw.metadata.ss_clip_skip);
            for (const [field, label] of EDITABLE) {
                const tr = element('tr'), cell = element('td');
                const input = element(field === 'userNote' ? 'textarea' : 'input');
                input.value = String(info[field] ?? (field === 'name' ? info.raw?.metadata?.ss_output_name ?? '' : ''));
                input.setAttribute('aria-label', label);
                const save = element('button', 'Save'); save.type = 'button';
                const status = element('span'); status.setAttribute('role', 'status');
                save.addEventListener('click', async () => {
                    save.disabled = true; status.textContent = '';
                    try {
                        const value = normalizeModelInfoEdit(field, input.value);
                        const saved = await this.service.savePartialInfo(this.file, { [field]: value });
                        this.modelInfo = saved; this.modifiedModelData = true; input.value = String(value); status.textContent = 'Saved';
                    } catch (error) { status.textContent = String(error?.message ?? error); }
                    finally { save.disabled = false; }
                });
                cell.append(input, save, status); tr.append(element('th', label), cell); table.append(tr);
            }
            container.append(table);
            if (Array.isArray(info.trainedWords) && info.trainedWords.length) {
                container.append(element('h3', 'Trained Words'));
                const selected = new Set(), output = element('textarea'); output.readOnly = true;
                output.setAttribute('aria-label', 'Selected trained words');
                for (const word of info.trainedWords) {
                    const text = String(word.word ?? ''), button = element('button', text); button.type = 'button';
                    button.setAttribute('aria-pressed', 'false');
                    button.addEventListener('click', () => {
                        if (selected.has(text)) selected.delete(text); else selected.add(text);
                        button.setAttribute('aria-pressed', String(selected.has(text)));
                        output.value = [...selected].join(', '); output.focus(); output.select();
                    });
                    container.append(button);
                }
                container.append(output);
            }
            // No automatic remote requests or source-file path probing. Provider
            // data already stored is displayed above; refresh is a distinct gap.
            container.append(element('p', 'Model-file metadata and Civitai refresh require an admitted metadata provider.'));
        } catch (error) {
            if (!this.closed) container.textContent = String(error?.message ?? error);
        }
    }
    close() { this.handle?.close(); }
}

export class RgthreeLoraInfoDialog extends RgthreeInfoDialog {
    constructor(file) { super(file, LORA_INFO_SERVICE); }
}
export class RgthreeCheckpointInfoDialog extends RgthreeInfoDialog {
    constructor(file) { super(file, CHECKPOINT_INFO_SERVICE); }
}
