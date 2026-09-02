import { comfy } from '/comfy/api/v2.js';

const NODE = 'vsLinx_LoadLastGeneratedImage';
const states = new Map();
const keyFor = (node) => `${node.graphId ?? ''}:${node.id}`;

function cleanName(value) {
  return String(value ?? '').replace(/\s+\[(input|output|temp)\]\s*$/i, '').trim();
}

function viewUrl(name, type = 'output') {
  const normalized = cleanName(name).replaceAll('\\', '/');
  const slash = normalized.lastIndexOf('/');
  const query = new URLSearchParams({
    filename: slash < 0 ? normalized : normalized.slice(slash + 1),
    subfolder: slash < 0 ? '' : normalized.slice(0, slash),
    type,
  });
  return comfy.backend.url(`/view?${query}`);
}

function select(state, name) {
  const value = name === '[none]' || name === '(None)' ? '' : cleanName(name);
  state.node.widgets.get('image')?.setValue(value ? `${value} [output]` : '');
  state.combo?.setValue(value || '(None)');
  if (state.image) {
    state.image.hidden = !value;
    if (value) state.image.src = viewUrl(value);
    else state.image.removeAttribute('src');
  }
}

async function listOutput(node) {
  const response = await comfy.backend.fetch('/secure-nodes/assets/output?kind=image');
  if (!response.ok) return [];
  const value = await response.json();
  let names = Array.isArray(value) ? value.map(String).filter((item) => item !== '[none]') : [];
  if (node.getProperty('include_subfolders') === false) {
    names = names.filter((name) => !name.includes('/'));
  }
  return names.slice(0, 4096);
}

async function refresh(state, chooseLatest = false) {
  const names = await listOutput(state.node);
  state.combo?.setOption('values', names.length ? names : ['(None)']);
  const saved = cleanName(state.node.widgets.get('image')?.getValue());
  const selected = chooseLatest || !names.includes(saved) ? (names[0] ?? '') : saved;
  select(state, selected);
}

async function upload(state) {
  const file = await comfy.files.pick({ mimeTypes: ['image/*'], maxBytes: 16 * 1024 * 1024 });
  if (!file) return;
  const form = new FormData();
  form.append('image', new Blob([file.bytes], { type: file.type || 'application/octet-stream' }), file.name);
  form.append('type', 'output');
  const response = await comfy.backend.fetch('/upload/image', { method: 'POST', body: form });
  if (!response.ok) throw new Error(`upload failed (${response.status})`);
  const result = await response.json();
  const name = result.subfolder ? `${result.subfolder}/${result.name}` : String(result.name ?? file.name);
  await refresh(state, false);
  select(state, name);
}

comfy.defs.extend(NODE, (builder) => {
  builder.onCreated((node) => {
    if (node.getProperty('include_subfolders') === undefined) {
      node.setProperty('include_subfolders', true);
    }
    node.widgets.get('image')?.setHidden(true);
    const combo = node.widgets.add({
      type: 'combo', name: 'select_image', value: '(None)',
      options: { values: ['(None)'] }, serialize: false,
    });
    combo.setLabel('image');
    node.widgets.move('select_image', 0);
    const state = { node, combo, image: undefined, wasExecuting: false };
    states.set(keyFor(node), state);
    combo.on('change', (value) => select(state, String(value ?? '')));

    const refreshButton = node.widgets.add({ type: 'button', name: 'Refresh', serialize: false });
    refreshButton.on('activate', () => { void refresh(state, true); });
    const uploadButton = node.widgets.add({ type: 'button', name: 'Choose file to upload', serialize: false });
    uploadButton.on('activate', () => { void upload(state).catch((error) => console.error('[vsLinx] upload failed', error)); });

    node.widgets.mount({
      name: 'output_preview', height: 190, serialize: false, sendToPrompt: false,
      render(container) {
        const image = container.ownerDocument.createElement('img');
        Object.assign(image.style, {
          display: 'block', width: '100%', height: '180px', objectFit: 'contain', borderRadius: '6px',
        });
        image.hidden = true;
        container.append(image);
        state.image = image;
      },
    });
    node.setSizeConstraints({ autoHeight: true });

    state.stopExecution = comfy.onExecutingNodeChanged((executing) => {
      if (executing) state.wasExecuting = true;
      else if (state.wasExecuting) {
        state.wasExecuting = false;
        if (node.widgets.get('auto_refresh')?.getValue() === true) void refresh(state, true);
      }
    });
    void refresh(state, !cleanName(node.widgets.get('image')?.getValue()));
  });

  builder.onConfigured((node) => {
    const state = states.get(keyFor(node));
    if (state) void refresh(state, false);
  });

  builder.onPropertyChanged((node, event) => {
    if (event.name === 'include_subfolders') {
      const state = states.get(keyFor(node));
      if (state) void refresh(state, true);
    }
  });

  builder.onRemoved((node) => {
    const state = states.get(keyFor(node));
    state?.stopExecution?.();
    states.delete(keyFor(node));
  });
});
