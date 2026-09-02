import { comfy } from '/comfy/api/v2.js';
import { respond_interaction } from './image_chooser/messaging.js';

function randomSeed() {
    const words = new Uint32Array(2);
    crypto.getRandomValues(words);
    return (words[0] * 0x200000 + (words[1] & 0x1fffff));
}

comfy.backend.on('secure-node-interaction', (detail) => {
    if (detail?.kind !== 'prompt-await') return;
    const payload = detail.payload ?? {};
    const prompt = document.createElement('textarea');
    prompt.value = String(payload.prompt ?? '');
    prompt.rows = 6;
    prompt.style.width = '100%';

    const source = document.createElement('select');
    for (const [value, label] of [['now', 'Current input'], ['prev', 'Previous input']]) {
        const option = document.createElement('option');
        option.value = value;
        option.textContent = label;
        if (value === 'prev' && !payload.has_prev) option.disabled = true;
        source.append(option);
    }
    source.value = payload.select === 'prev' && payload.has_prev ? 'prev' : 'now';

    const unlock = document.createElement('input');
    unlock.type = 'checkbox';
    unlock.checked = Boolean(payload.unlock);
    const seed = document.createElement('input');
    seed.type = 'number';
    seed.value = String(unlock.checked ? randomSeed() : Number(payload.last_seed ?? 0));

    const continueButton = document.createElement('button');
    continueButton.textContent = 'Continue';
    const stopButton = document.createElement('button');
    stopButton.textContent = 'Stop';
    const controls = document.createElement('div');
    controls.append(source, unlock, seed, continueButton, stopButton);

    const dialog = comfy.ui.showDialog({
        key: `easyuse.promptAwait.${detail.node_id}`,
        title: 'Prompt Await',
        render(container) {
            const label = document.createElement('label');
            label.textContent = 'Prompt';
            container.append(label, prompt, controls);
        },
    });

    const finish = async (result) => {
        continueButton.disabled = true;
        stopButton.disabled = true;
        await respond_interaction(detail.request_id, {
            result,
            prompt: String(prompt.value ?? ''),
            select: source.value === 'prev' ? 'prev' : 'now',
            last_seed: Number(payload.last_seed ?? 0),
            seed: Number(seed.value ?? 0),
            unlock: Boolean(unlock.checked),
        });
        dialog.close();
    };
    continueButton.addEventListener('click', () => { void finish(1); });
    stopButton.addEventListener('click', () => { void finish(-1); });
    unlock.addEventListener('change', () => {
        seed.value = String(unlock.checked ? randomSeed() : Number(payload.last_seed ?? 0));
    });
});
