import { comfy } from '/comfy/api/v2.js';

const NODES = ['vsLinx_LoadSelectedImagesList', 'vsLinx_LoadSelectedImagesBatch'];
const MAX_FILES = 256;
const states = new Map();
const keyFor = (node) => `${node.graphId ?? ''}:${node.id}`;

function parse(value) {
  try {
    const result = JSON.parse(String(value ?? ''));
    return Array.isArray(result) ? result.map(String) : [];
  } catch (_error) {
    return String(value ?? '').split('\n').map((item) => item.trim()).filter(Boolean);
  }
}

function dedupe(values) {
  return [...new Set(values.map((value) => String(value).replaceAll('\\', '/')))];
}

function limitFor(node) {
  const requested = Math.floor(Number(node.getProperty('max_images')) || 0);
  return Math.max(1, Math.min(MAX_FILES, requested > 0 ? requested : MAX_FILES));
}

function imageUrl(name) {
  const slash = name.lastIndexOf('/');
  const query = new URLSearchParams({
    filename: slash < 0 ? name : name.slice(slash + 1),
    subfolder: slash < 0 ? '' : name.slice(0, slash),
    type: 'input',
  });
  return comfy.backend.url(`/view?${query}`);
}

function render(state) {
  if (!state.grid) return;
  state.grid.replaceChildren();
  for (const name of state.names) {
    const image = state.grid.ownerDocument.createElement('img');
    image.src = imageUrl(name);
    image.alt = name;
    image.title = name;
    Object.assign(image.style, {
      width: '72px', height: '72px', objectFit: 'cover', borderRadius: '5px',
    });
    state.grid.append(image);
  }
  state.status.textContent = state.names.length
    ? `${state.names.length} image${state.names.length === 1 ? '' : 's'} selected`
    : 'No images selected';
}

function commit(state, names) {
  state.names = dedupe(names).slice(0, limitFor(state.node));
  const encoded = JSON.stringify(state.names);
  state.node.widgets.get('selected_paths')?.setValue(encoded);
  state.node.setProperty('selected_paths', encoded);
  render(state);
}

async function uploadFiles(state, files) {
  const selected = Array.from(files ?? []).slice(0, limitFor(state.node));
  const names = [];
  for (const file of selected) {
    if (!String(file.type ?? '').startsWith('image/') || file.size > 16 * 1024 * 1024) continue;
    const form = new FormData();
    form.append('image', file, file.name);
    form.append('type', 'input');
    const response = await comfy.backend.fetch('/upload/image', { method: 'POST', body: form });
    if (!response.ok) continue;
    const result = await response.json();
    names.push(result.subfolder ? `${result.subfolder}/${result.name}` : String(result.name));
  }
  commit(state, names);
}

for (const nodeType of NODES) {
  comfy.defs.extend(nodeType, (builder) => {
    builder.onBeforeConnect((node, event) => {
      if (event.side === 'input' && node.inputs.at(event.index)?.name === 'selected_paths') return false;
    });

    builder.onCreated((node) => {
      if (node.getProperty('max_images') === undefined) node.setProperty('max_images', 0);
      if (node.getProperty('fail_if_empty') === undefined) node.setProperty('fail_if_empty', true);
      if (node.getProperty('filename_handling') === undefined) {
        node.setProperty('filename_handling', 'full filename');
      }
      for (const name of ['selected_paths', 'fail_if_empty', 'filename_handling']) {
        node.widgets.get(name)?.setHidden(true);
      }
      node.widgets.get('fail_if_empty')?.setValue(node.getProperty('fail_if_empty') !== false);
      node.widgets.get('filename_handling')?.setValue(String(node.getProperty('filename_handling')));

      const state = {
        node,
        names: parse(node.getProperty('selected_paths') || node.widgets.get('selected_paths')?.getValue()),
        grid: undefined,
        status: undefined,
      };
      states.set(keyFor(node), state);
      node.widgets.mount({
        name: 'image_picker', height: 180, serialize: false, sendToPrompt: false,
        render(container) {
          const doc = container.ownerDocument;
          const button = doc.createElement('button');
          button.textContent = 'Select images';
          const input = doc.createElement('input');
          input.type = 'file';
          input.multiple = true;
          input.accept = 'image/*';
          input.hidden = true;
          const status = doc.createElement('div');
          status.style.margin = '6px 0';
          const grid = doc.createElement('div');
          Object.assign(grid.style, {
            display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(72px, 1fr))',
            gap: '5px', maxHeight: '130px', overflow: 'auto',
          });
          button.addEventListener('click', () => input.click());
          input.addEventListener('change', () => {
            void uploadFiles(state, input.files).catch((error) => {
              console.error('[vsLinx] image selection upload failed', error);
            });
          });
          container.append(button, input, status, grid);
          state.grid = grid;
          state.status = status;
          render(state);
        },
      });
      node.setSizeConstraints({ autoHeight: true });
      commit(state, state.names);
    });

    builder.onConfigured((node) => {
      const state = states.get(keyFor(node));
      if (state) commit(state, parse(node.getProperty('selected_paths') || node.widgets.get('selected_paths')?.getValue()));
    });

    builder.onPropertyChanged((node, event) => {
      const state = states.get(keyFor(node));
      if (!state) return;
      if (event.name === 'max_images') commit(state, state.names);
      if (event.name === 'fail_if_empty') node.widgets.get('fail_if_empty')?.setValue(Boolean(event.value));
      if (event.name === 'filename_handling') {
        const value = event.value === 'deduped filename' ? event.value : 'full filename';
        node.widgets.get('filename_handling')?.setValue(value);
      }
    });

    builder.onRemoved((node) => states.delete(keyFor(node)));
  });
}
