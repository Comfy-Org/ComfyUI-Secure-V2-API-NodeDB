import { comfy } from '/comfy/api/v2.js';
import { CATALOG, DEFAULT_CATEGORIES } from './catalog.js';


const NODE_TYPE = 'CreaPrompt_0';
const STORAGE_INDEX = 'ComfyUI.CreaPrompt/presets/index.json';
const RANDOM = '🎲random';
const DISABLED = 'disabled';
const states = new Map();


function keyFor(node) {
  return `${node.graphId ?? 'root'}:${node.id}`;
}


function parseDynamic(raw) {
  try {
    const parsed = JSON.parse(typeof raw === 'string' ? raw : '{}');
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {};
    const safe = {};
    for (const [name, value] of Object.entries(parsed)) {
      if (!Object.hasOwn(CATALOG, name) || typeof value !== 'string') continue;
      safe[name] = value;
    }
    return safe;
  } catch (_error) {
    return {};
  }
}


function commit(state) {
  state.json.setValue(JSON.stringify(state.values));
}


function addCategory(state, name, selected = DISABLED) {
  if (!Object.hasOwn(CATALOG, name) || Object.hasOwn(state.values, name)) return;
  const options = [DISABLED, RANDOM, ...CATALOG[name]];
  const value = options.includes(selected) ? selected : String(selected);
  const widget = state.node.widgets.add({
    type: 'combo',
    name,
    value,
    options: { values: options },
    serialize: false,
  });
  state.values[name] = value;
  state.dynamic.add(name);
  widget.on('change', (next) => {
    if (typeof next !== 'string') return;
    state.values[name] = next;
    commit(state);
  });
}


function removeCategory(state, name) {
  if (!state.dynamic.has(name)) return;
  state.node.widgets.remove(name);
  state.dynamic.delete(name);
  delete state.values[name];
  commit(state);
}


function replaceCategories(state, values) {
  for (const name of [...state.dynamic]) state.node.widgets.remove(name);
  state.dynamic.clear();
  state.values = {};
  for (const [name, value] of Object.entries(values)) addCategory(state, name, value);
  commit(state);
}


async function loadPresetIndex() {
  try {
    const raw = await comfy.storage.get(STORAGE_INDEX);
    const parsed = JSON.parse(raw ?? '{}');
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {};
    const clean = {};
    for (const [name, value] of Object.entries(parsed)) {
      if (typeof name === 'string' && typeof value === 'string') clean[name] = value;
    }
    return clean;
  } catch (_error) {
    return {};
  }
}


async function savePresetIndex(index) {
  await comfy.storage.set(STORAGE_INDEX, JSON.stringify(index));
}


function presetKey(id) {
  return `ComfyUI.CreaPrompt/presets/${encodeURIComponent(id)}.json`;
}


async function savePreset(state) {
  const requested = await comfy.ui.prompt({ label: 'Preset name', value: '' });
  const name = String(requested ?? '').trim();
  if (name.length < 2) return;
  const index = await loadPresetIndex();
  const id = Object.entries(index).find(([, label]) => label === name)?.[0]
    ?? `p${Date.now().toString(36)}`;
  await comfy.storage.set(presetKey(id), JSON.stringify(state.values, null, 2));
  index[id] = name;
  await savePresetIndex(index);
}


async function showLoadMenu(state, event) {
  const index = await loadPresetIndex();
  comfy.ui.showMenu({
    title: '📂 Load',
    event,
    items: Object.entries(index).map(([id, label]) => ({
      label,
      async run() {
        const raw = await comfy.storage.get(presetKey(id));
        replaceCategories(state, parseDynamic(raw));
      },
    })),
  });
}


async function showDeleteMenu(_state, event) {
  const index = await loadPresetIndex();
  comfy.ui.showMenu({
    title: '🗑️ Delete',
    event,
    items: Object.entries(index).map(([id, label]) => ({
      label,
      async run() {
        await comfy.storage.remove(presetKey(id));
        delete index[id];
        await savePresetIndex(index);
      },
    })),
  });
}


function showCategoryMenu(state, event) {
  comfy.ui.showMenu({
    title: '➕ Add category',
    event,
    items: Object.keys(CATALOG)
      .filter((name) => !state.dynamic.has(name))
      .sort()
      .map((name) => ({
        label: name,
        run() {
          addCategory(state, name);
          commit(state);
        },
      })),
  });
}


function showRemoveMenu(state, event) {
  comfy.ui.showMenu({
    title: '➖ Remove category',
    event,
    items: [...state.dynamic].map((name) => ({
      label: name,
      run() { removeCategory(state, name); },
    })),
  });
}


function addButton(node, name, run) {
  const widget = node.widgets.add({
    type: 'button', name, value: null, serialize: false,
  });
  widget.on('activate', (event) => void run(event));
}


comfy.defs.extend(NODE_TYPE, (builder) => {
  builder.onCreated((node, event) => {
    const jsonWidget = node.widgets.get('__csv_json');
    if (!jsonWidget) throw new Error('CreaPrompt_0 is missing __csv_json');
    jsonWidget.setHidden(true);
    const state = {
      node,
      json: jsonWidget,
      values: {},
      dynamic: new Set(),
      restoring: Boolean(event.restored || event.loading),
    };
    states.set(keyFor(node), state);

    addButton(node, '💾 Save Categories Preset', () => savePreset(state));
    addButton(node, '📂 Load Categories Preset', (menuEvent) => {
      if (menuEvent) return showLoadMenu(state, menuEvent);
    });
    addButton(node, '🗑️ Delete Categories Preset', (menuEvent) => {
      if (menuEvent) return showDeleteMenu(state, menuEvent);
    });
    addButton(node, '➖ Remove Category', (menuEvent) => {
      if (menuEvent) showRemoveMenu(state, menuEvent);
    });
    addButton(node, '🧹 Remove All', (menuEvent) => {
      if (!menuEvent) return;
      comfy.ui.showMenu({
        title: 'Remove every category?',
        event: menuEvent,
        items: [{ label: 'Remove all', run: () => replaceCategories(state, {}) }],
      });
    });
    addButton(node, '➕ Add Category', (menuEvent) => {
      if (menuEvent) showCategoryMenu(state, menuEvent);
    });

    if (!state.restoring) {
      replaceCategories(
        state,
        Object.fromEntries(DEFAULT_CATEGORIES.map((name) => [name, DISABLED])),
      );
    }
  });

  builder.onConfigured((node) => {
    const state = states.get(keyFor(node));
    if (!state) return;
    state.restoring = false;
    const stored = parseDynamic(state.json.getValue());
    replaceCategories(
      state,
      Object.keys(stored).length > 0
        ? stored
        : Object.fromEntries(DEFAULT_CATEGORIES.map((name) => [name, DISABLED])),
    );
  });

  builder.onRemoved((node) => states.delete(keyFor(node)));
});
