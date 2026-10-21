/**
 * Lora Info (LoraManager) on the published sandbox API, using only members the live guest (c6b97a15) implements.
 *
 * Original (ComfyUI-Lora-Manager 2dcaf6a):
 * - web/comfyui/lora_info.js: a wire-only `lora_source` input (`*`, shape 7); LoRA list widgets push their selection
 *   to the Lora Info nodes wired directly to them; a request id drops stale answers; removing the last `lora_source`
 *   wire clears the display.
 * - vue-widgets/src/components/LoraInfoWidget.vue: a Notes tab (filename, editable notes, Save -> toast), a Description
 *   tab (version and model descriptions), "No LoRA selected" when empty; value {name, notes, filePath, activeTab}.
 *
 * Platform replacements (recorded as deliberate differences):
 * - the pack's own routes, reached by relative path through comfy.backend.fetch (the host adds the pack's base);
 * - Save writes a pack-owned record: packs never write host model files;
 * - descriptions are shown as plain text: third-party HTML is never rendered in the host page;
 * - the saved node keeps the logical file name under the pack-owned key `lora_info`, never a host path. An original
 *   workflow's widgets_values[0] {name, notes, filePath, activeTab} is read when the host hands it to onConfigured;
 *   its absolute filePath is dropped and the logical file is looked up by name when the description or a save needs it;
 * - Save stays enabled while idle (Save on unchanged notes is a no-op, as in the original): re-rendering the button
 *   while the user types would rebuild the textarea and drop the caret.
 */
const LORA_INFO_CLASS = 'Lora Info (LoraManager)';
const SOURCE_INPUT = 'lora_source';
const PANEL = 'lora_info_display';
const SAVED_KEY = 'lora_info';
const ROUTE = Object.freeze({ notes: 'lm/loras/get-notes', metadata: 'lm/loras/metadata', save: 'lm/loras/save-metadata' });
const NAME_MAX = 4096;
const NOTES_MAX = 1024 * 1024;

const views = new Map(); // `${graphId}\0${id}` -> view

const api = () => globalThis.comfy;
const keyOf = (node) => `${node?.graphId ?? ''}\0${node?.id}`;

function blankDescription() {
  return { loading: false, loaded: false, error: false, version: '', model: '' };
}

function viewFor(node) {
  const key = keyOf(node);
  let view = views.get(key);
  if (!view) {
    view = { name: '', notes: '', originalNotes: '', file: '', activeTab: 'notes', saving: false,
             description: blankDescription(), reqId: 0, container: null, nodeId: String(node.id) };
    views.set(key, view);
  }
  return view;
}

/** Plain text from a description that may hold HTML; the result is only ever written as text. */
export function plainText(html) {
  if (typeof html !== 'string') return '';
  return html
    .replace(/<\s*br\s*\/?\s*>/gi, '\n')
    .replace(/<\/\s*(p|div|li|h[1-6]|tr)\s*>/gi, '\n')
    .replace(/<[^>]*>/g, '')
    .replace(/&nbsp;/g, ' ').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

/** The value restored from a saved node: this port's own key first, then an original workflow's widget value. */
export function restoredValue(data) {
  const text = (value, max) => typeof value === 'string' && value.length <= max;
  const tab = (value) => (value === 'description' ? 'description' : 'notes');
  const own = data && typeof data === 'object' ? data[SAVED_KEY] : undefined;
  if (own && typeof own === 'object' && text(own.name, NAME_MAX) && text(own.notes, NOTES_MAX) &&
      text(own.file ?? '', NAME_MAX)) {
    return { name: own.name, notes: own.notes, file: own.file ?? '', activeTab: tab(own.activeTab), legacy: false };
  }
  const values = data && typeof data === 'object' ? data.widgets_values : undefined;
  const legacy = Array.isArray(values) ? values[0] : undefined;
  if (legacy && typeof legacy === 'object' && !Array.isArray(legacy) && text(legacy.name ?? '', NAME_MAX) &&
      text(legacy.notes ?? '', NOTES_MAX)) {
    // An original workflow: keep the name, notes and tab; never keep its absolute host filePath.
    return { name: legacy.name ?? '', notes: legacy.notes ?? '', file: '', activeTab: tab(legacy.activeTab), legacy: true };
  }
  return null;
}

async function request(path, init) {
  const response = await api().backend.fetch(path, init);
  if (!response.ok) return { ok: false, status: response.status, text: await response.text() };
  return { ok: true, status: response.status, data: await response.json() };
}

function notify(severity, summary, detail, life) {
  try {
    // comfy.commands.notify crosses as an RPC: it answers with a promise, so its failure is caught there.
    Promise.resolve(api().commands.notify({ severity, summary, detail, life }))
      .catch((error) => console.error('[LoraInfo] notify failed:', error));
  } catch (error) {
    console.error('[LoraInfo] notify failed:', error);
  }
}

/** Looks the logical file up by name (an original workflow's value carries only a host path). */
async function resolveFile(view) {
  if (view.file || !view.name) return view.file;
  try {
    const answer = await request(`${ROUTE.notes}?name=${encodeURIComponent(view.name)}`, { method: 'GET' });
    if (answer.ok && typeof answer.data?.file === 'string') view.file = answer.data.file;
  } catch (error) {
    console.error('[LoraInfo] file lookup failed:', error);
  }
  return view.file;
}

async function fetchDescription(view) {
  if (view.description.loading || !view.name) return;
  if (!(await resolveFile(view))) return;
  view.description = { ...blankDescription(), loading: true };
  paint(view);
  try {
    const answer = await request(`${ROUTE.metadata}?file=${encodeURIComponent(view.file)}`, { method: 'GET' });
    if (!answer.ok) throw new Error(`Failed to fetch metadata: HTTP ${answer.status}`);
    const metadata = answer.data?.success ? answer.data.metadata : null;
    view.description = { ...blankDescription(), loaded: true,
      version: metadata ? plainText(metadata.description || '') : '',
      model: metadata ? plainText(metadata.model?.description || '') : '' };
  } catch (error) {
    console.error('[LoraInfo] Failed to fetch description:', error);
    view.description = { ...blankDescription(), error: true }; // not loaded: the next tab switch retries
  }
  paint(view);
}

function setInfo(view, data) {
  if (!data) {
    Object.assign(view, { name: '', notes: '', originalNotes: '', file: '' });
  } else {
    Object.assign(view, { name: data.name, notes: data.notes, originalNotes: data.notes, file: data.file || '' });
  }
  view.description = blankDescription();
  paint(view);
  if (data && view.activeTab === 'description') void fetchDescription(view);
}

async function save(view) {
  if (view.notes === view.originalNotes || view.saving) return;
  if (!(await resolveFile(view))) return;
  view.saving = true;
  paint(view);
  const notes = view.notes;
  try {
    const answer = await request(ROUTE.save, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file: view.file, notes }),
    });
    if (answer.ok && answer.data?.success) {
      notify('success', 'Saved', 'Notes updated successfully', 2000);
      view.originalNotes = notes;
    } else {
      notify('error', 'Error', answer.data?.message || answer.data?.error || answer.text || 'Failed to save notes', 3000);
    }
  } catch (error) {
    console.error('[LoraInfo] Failed to save notes:', error);
    notify('error', 'Error', error?.message || 'Failed to save notes', 3000);
  } finally {
    view.saving = false;
    paint(view);
  }
}

// Remote-DOM ships these as element properties (guest serializeStub); everything else goes as an attribute.
const STUB_PROPS = new Set(['value', 'placeholder', 'type', 'checked', 'disabled']);

function element(doc, tag, props = {}, text) {
  const el = doc.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (STUB_PROPS.has(key)) el[key] = value;
    else el.setAttribute(key, String(value));
  }
  if (text !== undefined) el.textContent = text;
  return el;
}

function paint(view) {
  const container = view.container;
  if (!container) return;
  const doc = container.ownerDocument;
  if (!view.name) {
    container.replaceChildren(element(doc, 'div', { style: 'padding:8px;opacity:.7' }, 'No LoRA selected'));
    return;
  }
  const tabs = element(doc, 'div', { style: 'display:flex;gap:12px;margin-bottom:6px' });
  for (const [value, label] of [['notes', 'Notes'], ['description', 'Description']]) {
    const tab = element(doc, 'label', { style: 'cursor:pointer' });
    const radio = element(doc, 'input', { type: 'radio', name: `lora-info-tab-${view.nodeId}`, value,
                                          checked: view.activeTab === value });
    radio.addEventListener('change', (event) => {
      if (!event.checked) return;
      view.activeTab = value;
      paint(view);
      if (value === 'description' && !view.description.loaded) void fetchDescription(view);
    });
    tab.append(radio, element(doc, 'span', {}, ` ${label}`));
    tabs.append(tab);
  }
  const body = element(doc, 'div', {});
  if (view.activeTab === 'notes') {
    body.append(element(doc, 'div', { style: 'font-size:11px;opacity:.7' }, 'Filename'),
                element(doc, 'div', { style: 'margin-bottom:6px;word-break:break-all' }, view.name),
                element(doc, 'div', { style: 'font-size:11px;opacity:.7' }, 'Notes'));
    const notes = element(doc, 'textarea', { value: view.notes, placeholder: 'Add notes about this LoRA...', rows: 5,
                                             disabled: view.saving, style: 'width:100%;box-sizing:border-box' });
    // Typing only records the text: changing the markup here would rebuild the textarea and drop the caret.
    notes.addEventListener('input', (event) => { view.notes = typeof event.value === 'string' ? event.value : view.notes; });
    const button = element(doc, 'button', { type: 'button', disabled: view.saving }, view.saving ? 'Saving...' : 'Save');
    button.addEventListener('click', () => { void save(view); });
    body.append(notes, button);
  } else {
    const d = view.description;
    if (d.loading) body.append(element(doc, 'div', {}, 'Loading description...'));
    else if (d.error) body.append(element(doc, 'div', {}, 'Failed to load description'));
    else if (!d.version && !d.model) body.append(element(doc, 'div', { style: 'opacity:.7' }, 'No description available'));
    else {
      if (d.version) body.append(element(doc, 'div', { style: 'font-size:11px;opacity:.7' }, 'About this version'),
                                 element(doc, 'div', { style: 'white-space:pre-wrap;margin-bottom:6px' }, d.version));
      if (d.model) body.append(element(doc, 'div', { style: 'font-size:11px;opacity:.7' }, 'Model Description'),
                               element(doc, 'div', { style: 'white-space:pre-wrap' }, d.model));
    }
  }
  container.replaceChildren(tabs, body);
}

function sourceConnected(node) {
  return node.inputs.all().some((slot) => slot.name === SOURCE_INPUT && slot.isConnected);
}

/** The Lora Info nodes wired directly to a source node's outputs (no chain walk), as the original. */
function connectedInfoNodes(sourceNode) {
  const found = [];
  for (const slot of sourceNode?.outputs?.all?.() ?? []) {
    for (const target of slot.targets?.() ?? []) {
      const node = api().graph.node(target.nodeId);
      if (node && node.comfyClass === LORA_INFO_CLASS && !found.includes(node)) found.push(node);
    }
  }
  return found;
}

/**
 * Called by the LoRA list widgets when their selection changes (the original's updateConnectedLoraInfoNodes):
 * fetches the notes of `selection.name` and shows them on every directly wired Lora Info node. A null selection clears.
 */
export async function updateConnectedLoraInfoNodes(sourceNode, selection) {
  const targets = connectedInfoNodes(sourceNode).map(viewFor);
  if (!targets.length) return;
  if (!selection?.name) {
    for (const view of targets) { view.reqId += 1; setInfo(view, null); }
    return;
  }
  const snapshot = new Map(targets.map((view) => [view, (view.reqId += 1)]));
  let data;
  try {
    const answer = await request(`${ROUTE.notes}?name=${encodeURIComponent(selection.name)}`, { method: 'GET' });
    if (!answer.ok) throw new Error(`Failed to fetch notes for ${selection.name}`);
    data = { name: selection.name, notes: answer.data?.notes || '', file: answer.data?.file || '' };
  } catch (error) {
    console.error('Error fetching notes for lora info:', error);
    data = { name: selection.name, notes: '[Error loading notes]', file: '' };
  }
  for (const [view, reqId] of snapshot) {
    if (view.reqId === reqId) setInfo(view, data); // a newer request supersedes this answer
  }
}

api().defs.extend(LORA_INFO_CLASS, (b) => {
  b.onCreated((node) => {
    if (!node.inputs.names().includes(SOURCE_INPUT)) node.inputs.add(SOURCE_INPUT, '*', { shape: 'optional' });
    const view = viewFor(node);
    node.widgets.mount({ name: PANEL, render(container) { view.container = container; paint(view); } });
  });
  b.onConfigured((node, data) => {
    const view = viewFor(node);
    const value = restoredValue(data);
    if (!value) return;
    Object.assign(view, { name: value.name, notes: value.notes, originalNotes: value.notes, file: value.file,
                          activeTab: value.activeTab, description: blankDescription() });
    paint(view);
    if (view.name && view.activeTab === 'description') void fetchDescription(view);
  });
  b.onConnectionsChanged((node, event) => {
    if (event?.side !== 'input' || event.connected) return;
    if (!sourceConnected(node)) setInfo(viewFor(node), null);
  });
  b.onRemoved((node) => { views.delete(keyOf(node)); });
  b.onSerialize((node) => {
    const view = views.get(keyOf(node));
    if (!view || !view.name) return {};
    return { [SAVED_KEY]: { name: view.name, notes: view.notes, file: view.file, activeTab: view.activeTab } };
  });
});
