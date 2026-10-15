import { comfy } from '/comfy/api/v2.js';

// The host publishes accepted prompt ids and exact executable-node counts.
// Progress events describe execution; the built prompt is never intercepted.
export class PromptExecution {
    constructor(id) {
        this.id = id; this.totalNodes = null; this.executedNodeIds = [];
        this.currentlyExecuting = null; this.errorDetails = null; this.finished = false;
    }
    completed(nodeId) {
        if (nodeId != null && !this.executedNodeIds.includes(String(nodeId))) this.executedNodeIds.push(String(nodeId));
    }
    executing(nodeId, step, maxSteps) {
        if (nodeId == null) {
            if (this.currentlyExecuting && !this.errorDetails) this.completed(this.currentlyExecuting.nodeId);
            this.currentlyExecuting = null; this.finished = true; return;
        }
        nodeId = String(nodeId);
        if (this.currentlyExecuting?.nodeId !== nodeId) {
            if (this.currentlyExecuting) this.completed(this.currentlyExecuting.nodeId);
            const node = comfy.executionNode(nodeId);
            this.currentlyExecuting = { nodeId, nodeLabel: node?.getTitle() ?? node?.type, pass: 0 };
        }
        if (Number.isFinite(step) && Number.isFinite(maxSteps) && maxSteps > 0) {
            if (this.currentlyExecuting.step == null || step < this.currentlyExecuting.step) this.currentlyExecuting.pass++;
            this.currentlyExecuting.step = step; this.currentlyExecuting.maxSteps = maxSteps;
        }
    }
    error(details) { this.errorDetails = details; }
}

export class PromptService extends EventTarget {
    constructor() {
        super(); this.promptsMap = new Map(); this.currentExecution = null;
        this.lastQueueRemaining = comfy.queue.pending(); this.unsubscribers = [];
        const listen = (name, callback) => this.unsubscribers.push(comfy.backend.on(name, callback));
        this.unsubscribers.push(comfy.queue.onAfterRun((event) => {
            for (const submission of event.submissions ?? []) {
                const prompt = this.getOrMakePrompt(submission.promptId);
                prompt.totalNodes = submission.nodeCount;
                this.dispatchEvent(new CustomEvent('queue-prompt', { detail: { prompt } }));
            }
            this.dispatchProgressUpdate();
        }));
        this.unsubscribers.push(comfy.queue.onPendingChanged((value) => { this.lastQueueRemaining = value; this.dispatchProgressUpdate(); }));
        listen('execution_start', (event) => {
            this.currentExecution = this.getOrMakePrompt(event.prompt_id);
            this.currentExecution.finished = false; this.dispatchProgressUpdate();
        });
        listen('executing', (event) => {
            const nodeId = event && typeof event === 'object' ? event.node : event;
            const id = event && typeof event === 'object' ? event.prompt_id : undefined;
            const prompt = this.forEvent(id); prompt.executing(nodeId); this.dispatchProgressUpdate();
            if (nodeId == null && this.currentExecution === prompt) this.currentExecution = null;
        });
        listen('progress', (event) => {
            this.forEvent(event.prompt_id).executing(event.node, event.value, event.max); this.dispatchProgressUpdate();
        });
        listen('execution_cached', (event) => {
            const prompt = this.forEvent(event.prompt_id);
            for (const id of event.nodes ?? []) prompt.completed(id);
            this.dispatchProgressUpdate();
        });
        listen('executed', (event) => {
            this.forEvent(event.prompt_id).completed(event.node); this.dispatchProgressUpdate();
        });
        listen('execution_error', (event) => {
            this.forEvent(event.prompt_id).error(event); this.dispatchProgressUpdate();
        });
        this.unsubscribers.push(comfy.queue.onInterrupted(() => {
            if (this.currentExecution) {
                this.currentExecution.error({ exception_type: 'Interrupted' });
                this.currentExecution.finished = true;
            }
            this.dispatchProgressUpdate(); this.currentExecution = null;
        }));
    }
    forEvent(id) {
        if (id != null) {
            const prompt = this.getOrMakePrompt(id);
            // A delayed event for an older prompt may update its history but
            // must not replace the active execution selected by execution_start.
            if (!this.currentExecution && !prompt.finished) this.currentExecution = prompt;
            return prompt;
        }
        return this.currentExecution ?? (this.currentExecution = this.getOrMakePrompt('unknown'));
    }
    getOrMakePrompt(id) {
        id = String(id ?? 'unknown');
        let prompt = this.promptsMap.get(id);
        if (!prompt) {
            prompt = new PromptExecution(id); this.promptsMap.set(id, prompt);
            // History is bounded. A later event for an evicted prompt stays
            // usable with an explicitly unknown total, never a guessed zero.
            while (this.promptsMap.size > 256) this.promptsMap.delete(this.promptsMap.keys().next().value);
        }
        return prompt;
    }
    dispatchProgressUpdate() {
        this.dispatchEvent(new CustomEvent('progress-update', { detail: { queue: this.lastQueueRemaining, prompt: this.currentExecution } }));
    }
    dispose() { for (const unsubscribe of this.unsubscribers) unsubscribe(); this.unsubscribers.length = 0; }
}

export const SERVICE = new PromptService();
