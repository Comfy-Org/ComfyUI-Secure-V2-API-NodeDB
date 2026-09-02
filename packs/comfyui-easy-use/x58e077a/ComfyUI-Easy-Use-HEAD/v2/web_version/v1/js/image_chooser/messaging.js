import { comfy } from '/comfy/api/v2.js';
import { FlowState } from "./state.js";

const pendingRequests = new Map();

function begin_request(id, requestId) {
    pendingRequests.set(String(id), String(requestId));
}

async function respond_interaction(requestId, response) {
    const result = await comfy.backend.fetch('/secure-nodes/interactions/respond', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ request_id: String(requestId), response }),
    });
    return result.ok;
}

function send_message_from_pausing_node(message) {
    const id = comfy.executingNode()?.id;
    send_message(id, message);
}

function send_message(id, message) {
    if (String(id) === '-1') {
        const replies = [...pendingRequests.values()].map((requestId) =>
            respond_interaction(requestId, { cancelled: true }));
        pendingRequests.clear();
        return Promise.all(replies).then(() => true);
    }
    const key = String(id);
    const requestId = pendingRequests.get(key);
    if (!requestId) return Promise.resolve(false);
    const separator = Array.isArray(message) ? message.indexOf(-1) : -1;
    const candidates = Array.isArray(message)
        ? message.slice(0, separator < 0 ? message.length : separator)
        : [];
    const selected = candidates.filter((value) => Number.isInteger(value) && value >= 0);
    pendingRequests.delete(key);
    return respond_interaction(requestId, { selected }).then(() => true);
}

function send_cancel() {
    send_message(-1,'__cancel__');
    // Set here and cleared by chooser.js's onInterrupted listener. The old code
    // wrapped api.interrupt, so its re-entry check ran synchronously inside this
    // call and could clear the flag on the next line. The published signal is
    // the backend's interrupt event, which arrives later — clearing it here
    // would let our own interrupt come back round as another cancel, forever.
    FlowState.cancelling = true;
    comfy.queue.interrupt();
}

// skip_next_restart_message() went with restart_from_here (see chooser.js): the
// only '__start__' worth suppressing was the one our own re-queue provoked.
function send_onstart() {
    send_message(-1,'__start__');
    return true;
}

export {
    begin_request, respond_interaction, send_message_from_pausing_node,
    send_cancel, send_message, send_onstart,
}
