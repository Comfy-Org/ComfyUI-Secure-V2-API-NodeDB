import { comfy } from '/comfy/api/v2.js';
import { SERVICE as PROMPT_SERVICE } from './prompt_service.js';

// The public chrome owns its presentation. A text badge and jump action retain
// actual queue/node/step information without inserting a custom DOM bar into
// the host's top/bottom layout. No percentage is invented for an unknown total.
export function progressText({ queue, prompt }) {
    const pieces = [];
    if (prompt?.errorDetails) pieces.push(String(prompt.errorDetails.exception_type ?? 'Execution error'));
    if (prompt) {
        const count = prompt.executedNodeIds.length;
        pieces.push(prompt.totalNodes == null ? `${count} nodes completed` : `${count}/${prompt.totalNodes} nodes`);
        const current = prompt.currentlyExecuting;
        if (current) {
            if (current.nodeLabel) pieces.push(current.nodeLabel);
            if (current.step != null && current.maxSteps > 0) pieces.push(`${current.step}/${current.maxSteps} steps`);
            if (current.pass > 1) pieces.push(`pass ${current.pass}`);
        }
    }
    pieces.push(`Queue: ${queue}`);
    return pieces.join(' · ');
}

export function installProgress(CONFIG_SERVICE) {
let badge, jump, last = { queue: comfy.queue.pending(), prompt: null };
function reconcile() {
    if (!CONFIG_SERVICE.getFeatureValue('progress_bar.enabled', true)) {
        badge?.remove(); jump?.remove(); badge = jump = undefined; return;
    }
    const value = { text: progressText(last), variant: last.prompt?.errorDetails ? 'error' : 'info' };
    if (badge) badge.update(value);
    else badge = comfy.ui.addTopBarBadge({ id: 'rgthree.progress', ...value });
    if (!jump) jump = comfy.ui.addActionBarButton({ id: 'rgthree.progress.jump', icon: 'pi-crosshairs', tooltip: 'Show executing node',
        run() { const node = comfy.executingNode(); if (node) comfy.graph.centerOn(node); } });
}
comfy.onReady(() => {
    PROMPT_SERVICE.addEventListener('progress-update', (event) => { last = event.detail; reconcile(); });
    CONFIG_SERVICE.addEventListener('config-change', (event) => {
        if (event.detail.key === 'features.progress_bar.enabled') reconcile();
    });
    reconcile();
});
}
