import { comfy } from '/comfy/api/v2.js';


const NODE_TYPE = 'PromptSaverNode';
const NEW_PROMPT = '[New Prompt]';
const STORAGE_NAMESPACE = 'ComfyUI.PromptSaver';
const INDEX_KEY = `${STORAGE_NAMESPACE}/index.json`;
const SAVE_DELAY_MS = 60_000;
const states = new Map();


function nodeKey(node) {
  return `${node.graphId ?? 'root'}:${node.id}`;
}


function sanitizeFilename(name) {
  return String(name).replace(/[\\/*?:"<>|]/g, '').trim();
}


function normalizeIndex(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return Object.create(null);
  }
  const normalized = Object.create(null);
  for (const [safeName, title] of Object.entries(value)) {
    if (typeof safeName !== 'string' || typeof title !== 'string') continue;
    if (!title || title === NEW_PROMPT) continue;
    normalized[safeName] = title;
  }
  return normalized;
}


async function loadIndex() {
  try {
    const stored = await comfy.storage.get(INDEX_KEY);
    return normalizeIndex(stored ? JSON.parse(stored) : {});
  } catch (error) {
    console.error('[PromptSaver] Error loading index:', error);
    return Object.create(null);
  }
}


function keyForTitle(title, index) {
  for (const [safeName, existingTitle] of Object.entries(index)) {
    if (existingTitle === title) return safeName;
  }
  return undefined;
}


function allocateKey(title, index) {
  const base = sanitizeFilename(title);
  let candidate = base;
  let counter = 1;
  while (Object.hasOwn(index, candidate)) {
    candidate = `${base}_${counter}`;
    counter += 1;
  }
  return candidate;
}


function promptKey(safeName) {
  return `${STORAGE_NAMESPACE}/prompts/${encodeURIComponent(safeName)}.txt`;
}


async function storePrompt(title, text) {
  const index = await loadIndex();
  let safeName = keyForTitle(title, index);
  if (safeName === undefined) safeName = allocateKey(title, index);
  await comfy.storage.set(promptKey(safeName), text);
  index[safeName] = title;
  await comfy.storage.set(INDEX_KEY, JSON.stringify(index, null, 2));
  return title;
}


async function loadPrompt(title) {
  const index = await loadIndex();
  const safeName = keyForTitle(title, index);
  if (safeName === undefined) return '';
  try {
    return (await comfy.storage.get(promptKey(safeName))) ?? '';
  } catch (error) {
    console.error('[PromptSaver] Error reading prompt:', error);
    return '';
  }
}


async function availableAutoTitle(baseTitle) {
  const titles = new Set(Object.values(await loadIndex()));
  if (!titles.has(baseTitle)) return baseTitle;
  let index = 1;
  while (titles.has(`${baseTitle}_auto_${index}`)) index += 1;
  return `${baseTitle}_auto_${index}`;
}


function defaultTitle() {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
  const workflowName = comfy.workflow.current()?.name;
  const prefix = workflowName ? workflowName.replace(/\s+/g, '_') : 'Prompt';
  return `${timestamp}_${prefix}`;
}


function setSelection(state, value) {
  state.suppressSelection = true;
  try {
    state.selectedTitle.setValue(value);
  } finally {
    state.suppressSelection = false;
  }
}


async function refreshTitles(state) {
  const titles = [NEW_PROMPT, ...Object.values(await loadIndex())];
  state.selectedTitle.setOption('values', titles);
  if (!titles.includes(state.selectedTitle.getValue())) {
    setSelection(state, NEW_PROMPT);
  }
  return titles;
}


function resetNewPrompt(state) {
  state.loading = true;
  clearTimeout(state.autoSaveTimer);
  state.autoSaveTimer = undefined;
  state.hasChanges = false;
  try {
    state.promptText.setValue('');
    state.titleName.setValue(defaultTitle());
  } finally {
    state.loading = false;
  }
}


async function selectPrompt(state, title) {
  if (state.suppressSelection) return;
  if (title === NEW_PROMPT) {
    resetNewPrompt(state);
    return;
  }
  if (typeof title !== 'string') return;

  state.loading = true;
  clearTimeout(state.autoSaveTimer);
  state.autoSaveTimer = undefined;
  state.hasChanges = false;
  try {
    const text = await loadPrompt(title);
    state.promptText.setValue(text);
    state.titleName.setValue(title);
  } finally {
    state.loading = false;
  }
}


async function save(state, title, isAuto) {
  if (!title || title === NEW_PROMPT) return false;
  try {
    const storedTitle = await storePrompt(title, String(state.promptText.getValue() ?? ''));
    await refreshTitles(state);
    setSelection(state, storedTitle);
    console.log(`[PromptSaver] ${isAuto ? 'Auto-saved' : 'Saved'}: ${storedTitle}`);
    return true;
  } catch (error) {
    console.error('[PromptSaver] Save error:', error);
    comfy.commands.notify({
      severity: 'error',
      summary: 'Prompt Saver',
      detail: 'The prompt could not be saved.',
    });
    return false;
  }
}


async function performAutoSave(state) {
  const title = String(state.titleName.getValue() ?? '').trim();
  if (!title || title === NEW_PROMPT) return;
  const available = await availableAutoTitle(title);
  if (await save(state, available, true)) state.hasChanges = false;
}


function scheduleAutoSave(state) {
  if (state.loading || state.autoSave.getValue() !== true) return;
  state.hasChanges = true;
  clearTimeout(state.autoSaveTimer);
  state.autoSaveTimer = setTimeout(() => {
    state.autoSaveTimer = undefined;
    if (state.hasChanges) void performAutoSave(state);
  }, SAVE_DELAY_MS);
}


comfy.defs.extend(NODE_TYPE, (builder) => {
  builder.onCreated((node) => {
    const state = {
      selectedTitle: node.widgets.get('selected_title'),
      autoSave: node.widgets.get('auto_save'),
      titleName: node.widgets.get('title_name'),
      promptText: node.widgets.get('prompt_text'),
      autoSaveTimer: undefined,
      refreshTimer: undefined,
      hasChanges: false,
      loading: false,
      suppressSelection: false,
    };
    if (!state.selectedTitle || !state.autoSave || !state.titleName || !state.promptText) {
      throw new Error('PromptSaverNode is missing a required widget');
    }
    states.set(nodeKey(node), state);

    if (!state.titleName.getValue()) state.titleName.setValue(defaultTitle());
    state.selectedTitle.on('change', (value) => void selectPrompt(state, value));
    // The stored title list is frontend-owned. Queue the schema's stable
    // sentinel so core combo validation never depends on private user state;
    // workflow and embedded serialization keep the user's visible selection.
    state.selectedTitle.on('beforeSerialize', (event) => {
      if (event.context === 'prompt') event.setSerializedValue(NEW_PROMPT);
    });
    state.titleName.on('change', () => scheduleAutoSave(state));
    state.promptText.on('change', () => scheduleAutoSave(state));
    state.autoSave.on('change', (value) => {
      if (value === true) return;
      clearTimeout(state.autoSaveTimer);
      state.autoSaveTimer = undefined;
      state.hasChanges = false;
    });

    const button = node.widgets.add({
      type: 'button',
      name: '💾 Save Prompt',
      value: null,
      serialize: false,
    });
    button.on('activate', () => {
      clearTimeout(state.autoSaveTimer);
      state.autoSaveTimer = undefined;
      state.hasChanges = false;
      const title = String(state.titleName.getValue() ?? '').trim();
      if (title && title !== NEW_PROMPT) void save(state, title, false);
    });

    void refreshTitles(state);
    state.refreshTimer = setInterval(() => void refreshTitles(state), SAVE_DELAY_MS);
  });

  builder.onRemoved((node) => {
    const key = nodeKey(node);
    const state = states.get(key);
    if (!state) return;
    clearTimeout(state.autoSaveTimer);
    clearInterval(state.refreshTimer);
    states.delete(key);
  });
});
