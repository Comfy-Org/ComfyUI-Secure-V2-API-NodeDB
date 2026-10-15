// Render-local pool controls. Dialogs/listeners never touch parent DOM/canvas.
import { createPoolEditorState } from './pool_editor_state.js';
import { createPoolApi } from './pool_api.js';
import { createPreviewPreferencesEditor, createPreviewPreferencesTransport } from './preview_preferences.js';

export function mountPoolEditor(node, comfy, { api = null, preferences = null, now = Date.now } = {}) {
  let alive = true, root = null, cell = null, widget = null, timer = null, loading = false, error = null;
  let modal = null, query = '', displayed = 200, expanded = new Set();
  const drafts = { include: '', exclude: '' }, listeners = [], subs = [];
  const prefs = createPreviewPreferencesEditor(preferences ?? createPreviewPreferencesTransport(comfy.backend));
  const state = createPoolEditorState({ api: api ?? createPoolApi(comfy.backend, { onError: failure => {
    if (alive) error = String(failure.message ?? failure);
  } }), now, write(value) { if (alive) { if (widget) widget.setValue(value); else cell?.set(value); } } });
  function listen(element, name, callback) {
    element.addEventListener(name, callback); listeners.push(() => element.removeEventListener(name, callback));
  }
  function releaseListeners() { listeners.splice(0).forEach(off => off()); }
  async function refresh() {
    if (!alive) return false;
    loading = true; error = null; render();
    try { await state.refresh(); return true; }
    catch (failure) { if (alive) error = String(failure.message ?? failure); return false; }
    finally { if (alive) { loading = false; render(); } }
  }
  function changed(filters) {
    if (!alive) return;
    const current = state.snapshot();
    state.restore({ filters, preview: { matchCount: current.matchCount } });
    if (timer !== null) clearTimeout(timer);
    timer = setTimeout(() => { timer = null; if (alive) void refresh(); }, 300);
    render();
  }
  function toggle(section, kind, value) {
    const filters = state.snapshot().filters;
    const selected = section === 'baseModels' ? filters.baseModels : filters[section][kind];
    const next = selected.includes(value) ? selected.filter(item => item !== value) : [...selected, value];
    if (section === 'baseModels') filters.baseModels = next; else filters[section][kind] = next;
    changed(filters);
  }
  function open(kind) { modal = kind; query = ''; displayed = 200; expanded = new Set(); render(); }
  function close() { modal = null; render(); }
  function render() {
    if (!alive || !root) return;
    releaseListeners(); root.replaceChildren();
    const doc = root.ownerDocument, current = state.snapshot();
    function text(parent, tag, value) { const element = doc.createElement(tag); element.textContent = value; parent.append(element); return element; }
    function button(parent, label, name, callback) {
      const element = text(parent, 'button', label); element.type = 'button'; element.setAttribute('aria-label', name);
      listen(element, 'click', callback); return element;
    }
    text(root, 'strong', 'LoRA Pool');
    text(root, 'p', 'Matching LoRAs: ' + current.matchCount.toLocaleString());
    const refreshButton = button(root, 'Refresh', 'refresh', () => { void refresh(); }); refreshButton.disabled = loading;
    for (const [label, key] of [['Base Models', 'baseModels'], ['Include Tags', 'tags.include'], ['Exclude Tags', 'tags.exclude'],
      ['Include Folders', 'folders.include'], ['Exclude Folders', 'folders.exclude']])
      button(root, label, key, () => open(key));
    for (const [label, key] of [['No Credit Required', 'noCreditRequired'], ['Allow Selling', 'allowSelling']]) {
      const control = button(root, label, key, () => { const filters = state.snapshot().filters;
        filters.license[key] = !filters.license[key]; changed(filters); });
      control.setAttribute('role', 'switch'); control.setAttribute('aria-checked', String(current.filters.license[key]));
    }
    for (const kind of ['include', 'exclude']) {
      const input = doc.createElement('input'); input.type = 'text'; input.setAttribute('aria-label', kind + ' name pattern');
      input.setAttribute('value', drafts[kind]); listen(input, 'input', () => { drafts[kind] = input.value; }); root.append(input);
      button(root, 'Add ' + kind + ' pattern', 'pattern.' + kind, () => {
        const pattern = drafts[kind].trim(), filters = state.snapshot().filters;
        if (pattern && !filters.namePatterns[kind].includes(pattern)) {
          filters.namePatterns[kind].push(pattern); drafts[kind] = ''; changed(filters);
        }
      });
      for (const pattern of current.filters.namePatterns[kind])
        button(root, 'Remove ' + pattern, 'remove.' + kind, () => { const filters = state.snapshot().filters;
          filters.namePatterns[kind] = filters.namePatterns[kind].filter(value => value !== pattern); changed(filters); });
    }
    const regex = button(root, 'Use Regex', 'regex', () => { const filters = state.snapshot().filters;
      filters.namePatterns.useRegex = !filters.namePatterns.useRegex; changed(filters); });
    regex.setAttribute('role', 'switch'); regex.setAttribute('aria-checked', String(current.filters.namePatterns.useRegex));
    const preview = doc.createElement('ul'); preview.setAttribute('aria-label', 'pool-preview-items'); root.append(preview);
    for (const item of current.items.slice(0, 5)) text(preview, 'li', item.model_name || item.file_name);
    if (current.matchCount > 5) text(preview, 'li', '+' + (current.matchCount - 5) + ' more');
    if (!current.items.length && !loading) text(preview, 'li', 'No matching LoRAs');
    text(root, 'span', error ?? '');
    const preferenceState = prefs.snapshot();
    if (preferenceState.loaded) {
      const values = preferenceState.draft;
      const sfw = button(root, 'Show Only SFW', 'prefs.sfw', () => {
        prefs.edit({ ...prefs.snapshot().draft, show_only_sfw: !prefs.snapshot().draft.show_only_sfw }); render(); });
      sfw.setAttribute('role', 'switch'); sfw.setAttribute('aria-checked', String(values.show_only_sfw));
      button(root, 'Display: ' + values.model_name_display, 'prefs.name', () => {
        prefs.edit({ ...prefs.snapshot().draft, model_name_display: values.model_name_display === 'model_name' ? 'file_name' : 'model_name' }); render(); });
      const save = button(root, 'Save Preview Preferences', 'prefs.save', () => {
        const pending = prefs.save(); render(); void pending.then(updated => { if (alive) { render(); if (updated) void refresh(); } })
          .catch(() => { if (alive) render(); }); }); save.disabled = preferenceState.busy;
    }
    text(root, 'p', preferenceState.conflict ? 'Preferences conflict; draft retained. Reload explicitly.' : preferenceState.error ?? '');
    button(root, 'Reload Preview Preferences', 'prefs.reload', () => {
      void prefs.load().then(() => { if (alive) render(); }).catch(() => { if (alive) render(); }); });
    if (!modal) return;
    const dialog = doc.createElement('div'); dialog.setAttribute('role', 'dialog'); dialog.setAttribute('aria-label', modal);
    // Owned subtree only: no Teleport-to-body, body overflow or global escape listener.
    root.append(dialog); text(dialog, 'h3', modal); button(dialog, 'Close', 'close', close);
    listen(dialog, 'keydown', event => { if (event.key === 'Escape') close(); });
    const input = doc.createElement('input'); input.type = 'text'; input.setAttribute('aria-label', 'Search ' + modal);
    input.setAttribute('value', query); dialog.append(input);
    listen(input, 'input', () => { query = input.value; render(); });
    const [section, kind] = modal.split('.'), selected = section === 'baseModels' ? current.filters.baseModels : current.filters[section][kind];
    function choice(parent, label, key, count = null) {
      const control = button(parent, label + (count === null ? '' : ' (' + count + ')'), 'choose.' + key,
        () => toggle(section, kind, key));
      control.setAttribute('role', 'checkbox'); control.setAttribute('aria-checked', String(selected.includes(key)));
    }
    const lower = query.toLowerCase();
    if (section === 'baseModels') {
      for (const option of current.baseModels.filter(value => !query || value.name.toLowerCase().includes(lower)))
        choice(dialog, option.name, option.name, option.count);
    } else if (section === 'tags') {
      const filtered = current.tags.filter(value => !query || value.tag.toLowerCase().includes(lower));
      for (const option of query ? filtered : filtered.slice(0, displayed)) choice(dialog, option.tag, option.tag, option.count);
      // Source tag paging is finite200 increments. Owned scroll supplies the same boundary.
      listen(dialog, 'scroll', () => { if (!query && displayed < current.tags.length &&
        dialog.scrollHeight - dialog.scrollTop - dialog.clientHeight < 100) { displayed = Math.min(displayed + 200, current.tags.length); render(); } });
    } else {
      function filterTree(nodes) {
        if (!query) return nodes;
        const result = [];
        for (const item of nodes) {
          const children = item.children ? filterTree(item.children) : [];
          if (item.key.toLowerCase().includes(lower) || item.label.toLowerCase().includes(lower) || children.length) {
            result.push({ ...item, children: children.length ? children : item.children });
            if (children.length) expanded.add(item.key);
          }
        }
        return result;
      }
      function tree(parent, nodes) { for (const item of nodes) {
        const branch = doc.createElement('div'); parent.append(branch); choice(branch, item.label, item.key);
        if (item.children?.length) {
          button(branch, expanded.has(item.key) ? 'Collapse' : 'Expand', 'expand.' + item.key,
            () => { if (expanded.has(item.key)) expanded.delete(item.key); else expanded.add(item.key); render(); });
          if (expanded.has(item.key)) tree(branch, item.children);
        }
      } }
      tree(dialog, filterTree(current.folders));
    }
  }
  function dispose() {
    if (!alive) return; alive = false;
    if (timer !== null) clearTimeout(timer); timer = null;
    releaseListeners(); subs.splice(0).forEach(off => off()); state.dispose(); prefs.dispose();
    root?.replaceChildren(); root = cell = null;
  }
  widget = node.widgets.mount({ name: 'pool_config', height: 520, defaultValue: {
    version: 2, filters: state.snapshot().filters }, serialize: true, sendToPrompt: true,
    render(container, value) { root = container; cell = value; render(); }, destroy: dispose });
  const initialize = async value => {
    state.restore(value); render();
    await Promise.all([state.fetchOptions(), prefs.load()]);
    if (alive) { render(); await refresh(); }
  };
  const started = initialize(widget.getValue()).catch(failure => { if (alive) { error = String(failure.message ?? failure); render(); } });
  return Object.freeze({ ready: started, snapshot: () => state.snapshot(), preferences: () => prefs.snapshot(),
    refresh, restore: initialize, dispose });
}
