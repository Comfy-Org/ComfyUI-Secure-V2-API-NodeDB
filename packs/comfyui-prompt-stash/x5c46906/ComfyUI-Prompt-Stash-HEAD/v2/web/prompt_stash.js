import { comfy } from '/comfy/api/v2.js';


const SAVER = 'PromptStashSaver';
const PASSTHROUGH = 'PromptStashPassthrough';
const MANAGER = 'PromptStashManager';
const NONE = 'None';
const DEFAULT_LIST = 'default';
const STORAGE_KEY = 'phazei.PromptStash/library-v1.json';
const INTERACTION_VARIANT = 'prompt-stash-passthrough-v1';
const RESPONSE_ROUTE = '/secure-nodes/interactions/respond';
const MAX_IMPORT_BYTES = 4 * 1024 * 1024;
const MAX_LISTS = 256;
const MAX_PROMPTS = 8192;
const MAX_NAME = 256;
const MAX_PROMPT_TEXT = 1_000_000;

const DEFAULT_LIBRARY = {
  version: '1.0',
  lists: {
    default: {
      Instructions: "📝 Quick Tips:\n\n• 'Use Input' takes text from input node\n• 'Use Prompt' uses text from prompt box (input node won't run)\n\n• Prompt saves only if 'Save Name' is filled\n• Saving to an existing name overwrites it\n\n• Use 'List' dropdown to select prompt lists\n• Manage lists with the Prompt Stash Manager node\n\n• For real-time editing, use Prompt Stash Passthrough node with 'Pause to Edit'\n• If workflow closes while paused, use 'Clear Paused' in Manager node\n\n• Saved prompts persist between sessions\n• All nodes share the same prompt library",
      ManageLists: "📂 Managing Prompt Lists:\n\n• Use the Prompt Stash Manager node to add or delete prompt lists\n• 'Add' creates a new list named in 'New List Name'\n• 'Delete' removes the selected list from 'Existing Lists'\n• Cannot delete the last remaining list\n• 'Clear Paused' resets any stuck pause states\n\n• Organize prompts into categories using lists\n• Switch between lists in the Prompt Stash Saver node using the 'List' dropdown",
      positive_demo: 'masterpiece, best quality, highly detailed',
      negative_demo: 'worst quality, bad anatomy, text, error, jpeg artifacts, blurry',
    },
    characters: {
      wizard: 'elderly wizard with long white beard, wearing blue robes with stars',
      warrior: 'strong warrior wearing plate armor, battle-scarred, determined expression',
    },
    backgrounds: {
      forest: 'dense forest, tall trees, dappled sunlight, misty atmosphere',
      sea: 'vast ocean depths',
    },
  },
};

const states = new Map();
const pending = new Map();
let libraryPromise;
let mutation = Promise.resolve();


function notify(severity, summary, detail) {
  comfy.commands.notify({ severity, summary, detail: String(detail) });
}


function cleanName(value) {
  const name = typeof value === 'string' ? value.trim() : '';
  return name && name.length <= MAX_NAME ? name : undefined;
}


function normalizeLists(value, { requirePrompt = false } = {}) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new TypeError("Prompt Stash 'lists' must be an object");
  }
  const lists = Object.create(null);
  let promptCount = 0;
  for (const [rawListName, rawPrompts] of Object.entries(value)) {
    const listName = cleanName(rawListName);
    if (!listName || !rawPrompts || typeof rawPrompts !== 'object' ||
        Array.isArray(rawPrompts)) continue;
    const prompts = Object.create(null);
    for (const [rawKey, rawText] of Object.entries(rawPrompts)) {
      const key = cleanName(rawKey);
      if (!key || typeof rawText !== 'string' || rawText.length > MAX_PROMPT_TEXT) {
        continue;
      }
      prompts[key] = rawText;
      promptCount += 1;
      if (promptCount > MAX_PROMPTS) {
        throw new RangeError('Prompt Stash import has too many prompts');
      }
    }
    if (!requirePrompt || Object.keys(prompts).length) lists[listName] = prompts;
    if (Object.keys(lists).length > MAX_LISTS) {
      throw new RangeError('Prompt Stash import has too many lists');
    }
  }
  if (!Object.keys(lists).length) {
    throw new TypeError('No valid prompt lists were found');
  }
  return lists;
}


function normalizeLibrary(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new TypeError('Prompt Stash data must be an object');
  }
  return { version: '1.0', lists: normalizeLists(value.lists) };
}


async function loadLibrary() {
  if (!libraryPromise) {
    libraryPromise = (async () => {
      try {
        const stored = await comfy.storage.get(STORAGE_KEY);
        if (stored) return normalizeLibrary(JSON.parse(stored));
      } catch (error) {
        console.error('[Prompt Stash] Could not read stored library:', error);
      }
      const initial = structuredClone(DEFAULT_LIBRARY);
      await comfy.storage.set(STORAGE_KEY, JSON.stringify(initial));
      return initial;
    })();
  }
  return libraryPromise;
}


function changeLibrary(update) {
  mutation = mutation.then(async () => {
    const current = structuredClone(await loadLibrary());
    const result = update(current);
    const next = normalizeLibrary(current);
    await comfy.storage.set(STORAGE_KEY, JSON.stringify(next, null, 2));
    libraryPromise = Promise.resolve(next);
    await refreshAll(next);
    return result;
  });
  return mutation;
}


function widget(node, name) {
  const result = node.widgets.get(name);
  if (!result) throw new Error(`${node.comfyClass} is missing widget '${name}'`);
  return result;
}


function updateCombo(node, name, values, fallback) {
  const target = widget(node, name);
  target.setOption('values', values);
  if (!values.includes(target.getValue())) target.setValue(fallback);
  const slot = node.inputs.byName(name);
  slot?.modify({
    widget: name,
    widgetConfig: { type: [...values], options: { default: fallback } },
  });
  const source = slot?.source();
  if (source) {
    const upstream = comfy.graph.node(source.nodeId);
    if (upstream?.comfyClass === 'PrimitiveNode') {
      const primitive = upstream.widgets.at(0);
      primitive?.setOption('values', values);
      if (!values.includes(primitive?.getValue())) primitive?.setValue(fallback);
    }
  }
  return target;
}


function setButton(button, disabled) {
  button?.setDisabled(Boolean(disabled));
}


async function refreshSaver(state, data = undefined) {
  const library = data || await loadLibrary();
  const listNames = Object.keys(library.lists);
  updateCombo(state.node, 'prompt_lists', listNames, listNames[0] || DEFAULT_LIST);
  const selectedList = String(state.list.getValue());
  const prompts = library.lists[selectedList] || Object.create(null);
  updateCombo(state.node, 'load_saved', [NONE, ...Object.keys(prompts)], NONE);
  const saveName = String(state.saveName.getValue() ?? '').trim();
  const text = String(state.prompt.getValue() ?? '').trim();
  setButton(state.saveButton, !(saveName && text));
  setButton(state.deleteButton, state.saved.getValue() === NONE);
}


async function refreshManager(state, data = undefined) {
  const library = data || await loadLibrary();
  const names = Object.keys(library.lists);
  state.existing.setOption('values', names);
  if (!names.includes(state.existing.getValue())) {
    state.existing.setValue(names[0] || DEFAULT_LIST);
  }
  setButton(state.addButton, !cleanName(state.newName.getValue()));
  setButton(state.deleteButton, names.length <= 1 || !state.existing.getValue());
}


async function refreshAll(data = undefined) {
  const library = data || await loadLibrary();
  await Promise.all([...states.values()].map((state) => {
    if (state.kind === 'saver') return refreshSaver(state, library);
    if (state.kind === 'manager') return refreshManager(state, library);
    return undefined;
  }));
}


function savedPrompt(state, data) {
  const list = data.lists[String(state.list.getValue())] || Object.create(null);
  return list[String(state.saved.getValue())];
}


async function loadSelected(state) {
  const selected = String(state.saved.getValue());
  if (selected === NONE) {
    state.prompt.setValue('');
    state.saveName.setValue('');
    await refreshSaver(state);
    return;
  }
  const data = await loadLibrary();
  const value = savedPrompt(state, data);
  if (typeof value !== 'string') return;
  state.loading = true;
  try {
    state.prompt.setValue(value);
    state.saveName.setValue(selected);
  } finally {
    state.loading = false;
  }
  await refreshSaver(state, data);
}


function addButton(node, name, run) {
  const button = node.widgets.add({
    type: 'button', name, value: null, disabled: false, serialize: false,
  });
  button.on('activate', () => {
    Promise.resolve(run()).catch((error) => {
      console.error(`[Prompt Stash] ${name} failed:`, error);
      notify('error', 'Prompt Stash', error);
    });
  });
  return button;
}


function deepMerge(existing, imported) {
  const summary = {
    lists_added: [], lists_merged: [], prompts_added: 0, prompts_renamed: [],
  };
  for (const [listName, importedPrompts] of Object.entries(imported)) {
    if (!Object.hasOwn(existing, listName)) {
      existing[listName] = { ...importedPrompts };
      summary.lists_added.push(listName);
      summary.prompts_added += Object.keys(importedPrompts).length;
      continue;
    }
    summary.lists_merged.push(listName);
    const target = existing[listName];
    for (const [key, text] of Object.entries(importedPrompts)) {
      let destination = key;
      if (Object.hasOwn(target, destination)) {
        let counter = 2;
        while (Object.hasOwn(target, `${key} (${counter})`)) counter += 1;
        destination = `${key} (${counter})`;
        summary.prompts_renamed.push({ original: key, renamed: destination, list: listName });
      }
      target[destination] = text;
      summary.prompts_added += 1;
    }
  }
  return summary;
}


async function exportLibrary() {
  const data = await loadLibrary();
  const stamp = new Date().toISOString().slice(0, 16).replace('T', '_').replace(':', '-');
  await comfy.files.download({
    name: `prompt_stash_export_${stamp}.json`,
    mimeType: 'application/json',
    bytes: new TextEncoder().encode(JSON.stringify(data, null, 2)),
  });
}


async function importLibrary() {
  const file = await comfy.files.pick({
    extensions: ['json'], mimeTypes: ['application/json'], maxBytes: MAX_IMPORT_BYTES,
  });
  if (!file) return;
  if (!file.name.toLowerCase().endsWith('.json')) {
    throw new TypeError('Please select a JSON file');
  }
  const decoded = new TextDecoder('utf-8', { fatal: true }).decode(file.bytes);
  const parsed = JSON.parse(decoded);
  const imported = normalizeLists(parsed?.lists, { requirePrompt: true });
  const summary = await changeLibrary((current) => deepMerge(current.lists, imported));
  const parts = [
    `Added ${summary.prompts_added} prompts`,
    `${summary.lists_added.length} new lists`,
    `${summary.lists_merged.length} merged lists`,
  ];
  if (summary.prompts_renamed.length) {
    parts.push(`${summary.prompts_renamed.length} renamed conflicts`);
  }
  notify('success', 'Prompt Stash import complete', parts.join(', '));
}


function promptProjection(node) {
  return {
    omitInputs: widget(node, 'use_input_text').getValue() === true ? [] : ['text'],
  };
}


function appliedOutput(result) {
  const value = result?.raw?.prompt_stash;
  return value && typeof value === 'object' ? value : undefined;
}


comfy.defs.extend(SAVER, (builder) => {
  builder.onPromptSerialize(promptProjection);
  builder.onCreated((node) => {
    const state = {
      kind: 'saver', node,
      useInput: widget(node, 'use_input_text'),
      prompt: widget(node, 'prompt_text'),
      saveName: widget(node, 'save_as_key'),
      saved: widget(node, 'load_saved'),
      list: widget(node, 'prompt_lists'),
      saveButton: undefined,
      deleteButton: undefined,
      loading: false,
    };
    state.useInput.setLabel('Use ____');
    state.saveName.setLabel('Save Name');
    state.saved.setLabel('Load Saved');
    state.list.setLabel('List');
    state.saveButton = addButton(node, 'Save Prompt', async () => {
      const key = cleanName(state.saveName.getValue());
      const text = String(state.prompt.getValue() ?? '');
      if (!key || !text.trim() || text.length > MAX_PROMPT_TEXT) return;
      const listName = String(state.list.getValue());
      await changeLibrary((data) => {
        const target = data.lists[listName] || data.lists[DEFAULT_LIST];
        target[key] = text;
      });
      state.saved.setValue(key);
      await refreshSaver(state);
    });
    state.deleteButton = addButton(node, 'Delete Selected', async () => {
      const selected = String(state.saved.getValue());
      if (selected === NONE) return;
      const listName = String(state.list.getValue());
      const before = [...(state.saved.getOptions()?.values || [])];
      const deletedIndex = before.indexOf(selected);
      await changeLibrary((data) => { delete data.lists[listName]?.[selected]; });
      const after = [NONE, ...Object.keys((await loadLibrary()).lists[listName] || {})];
      const next = after.length > 1
        ? after[Math.min(Math.max(deletedIndex, 1), after.length - 1)]
        : NONE;
      state.saved.setValue(next);
      await loadSelected(state);
    });
    state.list.on('change', () => {
      state.saved.setValue(NONE);
      void refreshSaver(state);
    });
    state.saved.on('change', () => { if (!state.loading) void loadSelected(state); });
    state.prompt.on('change', () => {
      if (!state.loading && state.saved.getValue() !== NONE) {
        void loadLibrary().then((data) => {
          if (state.prompt.getValue() !== savedPrompt(state, data)) state.saved.setValue(NONE);
          return refreshSaver(state, data);
        });
      } else {
        void refreshSaver(state);
      }
    });
    state.saveName.on('change', () => {
      const trimmed = String(state.saveName.getValue() ?? '').trim();
      if (trimmed !== state.saveName.getValue()) state.saveName.setValue(trimmed);
      if (state.saved.getValue() !== NONE && trimmed !== state.saved.getValue()) {
        state.saved.setValue(NONE);
      }
      void refreshSaver(state);
    });
    states.set(String(node.id), state);
    void refreshSaver(state);
  });
  builder.onExecuted((node, result) => {
    const state = states.get(String(node.id));
    const output = appliedOutput(result);
    if (!state || output?.adopt_input !== true || typeof output.text !== 'string') return;
    state.loading = true;
    try {
      state.prompt.setValue(output.text);
      state.saveName.setValue('');
    } finally {
      state.loading = false;
    }
    void refreshSaver(state);
  });
  builder.onRemoved((node) => states.delete(String(node.id)));
});


async function postResponse(requestId, response) {
  const result = await comfy.backend.fetch(RESPONSE_ROUTE, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ request_id: String(requestId), response }),
  });
  if (!result.ok) throw new Error(`Prompt Stash response failed (${result.status})`);
}


function syncPending(nodeId, active) {
  const state = states.get(String(nodeId));
  if (state?.kind === 'passthrough') setButton(state.continueButton, !active);
}


async function finishPending(record) {
  if (!record || record.sending || record.finished) return;
  record.sending = true;
  try {
    const state = states.get(record.nodeId);
    const text = state?.kind === 'passthrough'
      ? String(state.prompt.getValue() ?? '')
      : String(record.text ?? '');
    await postResponse(record.requestId, { action: 'continue', text });
    record.finished = true;
    if (pending.get(record.nodeId) === record) pending.delete(record.nodeId);
    syncPending(record.nodeId, false);
  } catch (error) {
    record.sending = false;
    notify('error', 'Prompt Stash continue failed', error);
  }
}


function receivePause(detail) {
  if (detail?.kind !== 'prompt-await' ||
      detail?.payload?.variant !== INTERACTION_VARIANT ||
      typeof detail.request_id !== 'string') return;
  const nodeId = String(detail.node_id);
  const previous = pending.get(nodeId);
  if (previous && !previous.finished) void finishPending(previous);
  const record = {
    nodeId,
    requestId: detail.request_id,
    text: typeof detail.payload.text === 'string' ? detail.payload.text : '',
    sending: false,
    finished: false,
  };
  pending.set(nodeId, record);
  const state = states.get(nodeId);
  if (state?.kind === 'passthrough' && !state.prompt.getValue()) {
    state.prompt.setValue(record.text);
  }
  syncPending(nodeId, true);
}


comfy.defs.extend(PASSTHROUGH, (builder) => {
  builder.onPromptSerialize(promptProjection);
  builder.onCreated((node) => {
    const state = {
      kind: 'passthrough', node,
      useInput: widget(node, 'use_input_text'),
      prompt: widget(node, 'prompt_text'),
      pause: widget(node, 'pause_to_edit'),
      continueButton: undefined,
    };
    state.useInput.setLabel('Use ____');
    state.pause.setLabel('Pause to Edit');
    state.continueButton = addButton(node, 'Continue', () => {
      return finishPending(pending.get(String(node.id)));
    });
    states.set(String(node.id), state);
    syncPending(node.id, pending.has(String(node.id)));
  });
  builder.onExecuted((node, result) => {
    const state = states.get(String(node.id));
    const output = appliedOutput(result);
    if (!state || output?.adopt_input !== true || typeof output.text !== 'string') return;
    state.prompt.setValue(output.text);
  });
  builder.onRemoved((node) => states.delete(String(node.id)));
});


comfy.defs.extend(MANAGER, (builder) => {
  builder.onCreated((node) => {
    const state = {
      kind: 'manager', node,
      newName: widget(node, 'new_list_name'),
      existing: node.widgets.add({
        type: 'combo', name: 'existing_lists', value: DEFAULT_LIST,
        options: { values: [DEFAULT_LIST] }, serialize: true,
      }),
      addButton: undefined,
      deleteButton: undefined,
    };
    state.newName.setLabel('New List Name');
    state.existing.setLabel('Existing Lists');
    state.addButton = addButton(node, 'Add List', async () => {
      const name = cleanName(state.newName.getValue());
      if (!name) return;
      await changeLibrary((data) => {
        if (!Object.hasOwn(data.lists, name)) data.lists[name] = Object.create(null);
      });
      state.newName.setValue('');
      state.existing.setValue(name);
      await refreshManager(state);
    });
    state.deleteButton = addButton(node, 'Delete List', async () => {
      const selected = String(state.existing.getValue());
      const current = Object.keys((await loadLibrary()).lists);
      if (current.length <= 1 || !current.includes(selected)) return;
      const index = current.indexOf(selected);
      await changeLibrary((data) => { delete data.lists[selected]; });
      const remaining = Object.keys((await loadLibrary()).lists);
      state.existing.setValue(remaining[Math.min(index, remaining.length - 1)]);
      await refreshManager(state);
    });
    addButton(node, 'Export', exportLibrary);
    addButton(node, 'Import', importLibrary);
    addButton(node, 'Clear All Paused', async () => {
      await Promise.all([...pending.values()].map(finishPending));
    });
    state.newName.on('change', () => { void refreshManager(state); });
    state.existing.on('change', () => { void refreshManager(state); });
    states.set(String(node.id), state);
    void refreshManager(state);
  });
  builder.onRemoved((node) => states.delete(String(node.id)));
});


comfy.backend.on('secure-node-interaction', receivePause);
comfy.queue.onInterrupted(() => {
  for (const record of pending.values()) syncPending(record.nodeId, false);
  pending.clear();
});
