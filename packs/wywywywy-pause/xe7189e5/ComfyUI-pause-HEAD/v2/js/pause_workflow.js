import { comfy } from '/comfy/api/v2.js';

const TARGETS = ['PauseWorkflowNode', 'PauseWorkflowNodeWithSound'];
const VARIANT = 'wywywywy-workflow-pause-v1';
const RESPONSE_ROUTE = '/secure-nodes/interactions/respond';
const PAUSED_COLOR = '#8b6914';
const SOUND_URL = new URL('./notification.mp3', import.meta.url).href;

const nodeStates = new Map();
const pending = new Map();

function setPaused(node, state, paused) {
  state.continueButton.setDisabled(!paused);
  state.cancelButton.setDisabled(!paused);
  if (paused) {
    if (!state.hasSavedColor) {
      state.savedColor = node.getBgColor();
      state.hasSavedColor = true;
    }
    node.setBgColor(PAUSED_COLOR);
  } else if (state.hasSavedColor) {
    node.setBgColor(state.savedColor);
    state.savedColor = undefined;
    state.hasSavedColor = false;
  }
}

function syncNode(nodeId, paused) {
  const node = comfy.graph.node(String(nodeId));
  const state = nodeStates.get(String(nodeId));
  if (node && state) setPaused(node, state, paused);
}

async function postResponse(requestId, action) {
  const response = await comfy.backend.fetch(RESPONSE_ROUTE, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ request_id: String(requestId), response: { action } }),
  });
  if (!response.ok) {
    throw new Error(`pause response failed (${response.status})`);
  }
}

async function finish(record, action) {
  if (!record || record.finished || record.sending) return;
  record.sending = true;
  try {
    await postResponse(record.detail.request_id, action);
    record.finished = true;
    if (pending.get(record.nodeId) === record) {
      pending.delete(record.nodeId);
      syncNode(record.nodeId, false);
    }
    record.dialog?.close();
  } catch (error) {
    record.sending = false;
    comfy.commands.notify({
      severity: 'error',
      summary: 'Pause Workflow',
      detail: String(error),
    });
  }
}

function playNotification() {
  try {
    const audio = new Audio(SOUND_URL);
    void audio.play().catch(() => {});
  } catch (_error) {
    // Audio can be unavailable in a headless or autoplay-restricted client.
  }
}

function showPause(detail) {
  if (detail?.kind !== 'prompt-await') return;
  if (detail?.payload?.variant !== VARIANT) return;
  if (typeof detail.request_id !== 'string') return;

  const nodeId = String(detail.node_id);
  const previous = pending.get(nodeId);
  if (previous && !previous.finished) void finish(previous, 'cancel');

  const record = {
    detail,
    nodeId,
    finished: false,
    sending: false,
    dialog: undefined,
  };
  pending.set(nodeId, record);
  syncNode(nodeId, true);
  if (detail.payload.sound === true) playNotification();

  let continueButton;
  let cancelButton;
  record.dialog = comfy.ui.showDialog({
    key: `wywywywy.pause.${nodeId}`,
    title: String(detail.payload.title || 'Pause Workflow'),
    render(container) {
      const doc = container.ownerDocument;
      const message = doc.createElement('p');
      message.textContent = 'Workflow paused. Continue to pass both inputs through, or cancel this run.';
      const controls = doc.createElement('div');
      controls.style.cssText = 'display:flex;justify-content:flex-end;gap:8px';
      cancelButton = doc.createElement('button');
      cancelButton.textContent = 'Cancel run';
      continueButton = doc.createElement('button');
      continueButton.textContent = 'Continue';
      cancelButton.addEventListener('click', () => { void finish(record, 'cancel'); });
      continueButton.addEventListener('click', () => { void finish(record, 'continue'); });
      controls.append(cancelButton, continueButton);
      container.append(message, controls);
      continueButton.focus();
    },
    destroy() {
      if (!record.finished && !record.sending) void finish(record, 'cancel');
    },
  });
}

comfy.defs.extend(TARGETS, (builder) => {
  builder.onCreated((node) => {
    const continueButton = node.widgets.add({
      type: 'button', name: '✔️ Continue', value: null,
      disabled: true, serialize: false,
    });
    const cancelButton = node.widgets.add({
      type: 'button', name: '⛔ Cancel', value: null,
      disabled: true, serialize: false,
    });
    const state = {
      continueButton,
      cancelButton,
      savedColor: undefined,
      hasSavedColor: false,
    };
    nodeStates.set(String(node.id), state);
    continueButton.on('activate', () => {
      void finish(pending.get(String(node.id)), 'continue');
    });
    cancelButton.on('activate', () => {
      void finish(pending.get(String(node.id)), 'cancel');
    });
    if (pending.has(String(node.id))) setPaused(node, state, true);
  });
  builder.onRemoved((node) => nodeStates.delete(String(node.id)));
});

comfy.backend.on('secure-node-interaction', showPause);
comfy.queue.onInterrupted(() => {
  for (const record of [...pending.values()]) void finish(record, 'cancel');
});
