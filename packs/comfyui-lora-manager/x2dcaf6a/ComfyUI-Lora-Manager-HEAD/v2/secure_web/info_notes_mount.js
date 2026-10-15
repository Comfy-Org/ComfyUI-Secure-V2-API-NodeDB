// Prepared mounted notes-only consumer. No descriptions/provider markup,
// automatic account binding, manifest registration or permanent storage claim.
import { createInfoNotesEditor } from './info_notes_editor.js';
import { createInfoNotesTransport } from './info_notes_transport.js';

export function mountInfoNotes(node, comfy, { transport = null } = {}) {
  const editor = createInfoNotesEditor(transport ?? createInfoNotesTransport(comfy.backend));
  let alive = true, container = null, cell = null, unrender = () => {};
  const subs = [];
  let widget;
  const render = () => {
    if (!alive || !container) return;
    unrender(); container.replaceChildren();
    const state = editor.snapshot();
    const doc = container.ownerDocument, input = doc.createElement('textarea');
    input.value = state.notes;
    // Native textarea markup takes its declared initial value from literal
    // text, not a value attribute. Remote-DOM escapes this text as data.
    input.textContent = state.notes;
    input.setAttribute('aria-label', 'LoRA notes');
    const save = doc.createElement('button'); save.type = 'button'; save.textContent = 'Save notes';
    save.disabled = state.saving || !state.dirty || state.name === null;
    const status = doc.createElement('span'); status.textContent = state.error ?? '';
    const change = () => { if (alive) editor.edit(input.value); };
    const commit = () => { if (alive) void editor.save().catch(() => {}); };
    input.addEventListener('input', change); save.addEventListener('click', commit);
    container.append(input, save, status);
    unrender = () => { input.removeEventListener('input', change); save.removeEventListener('click', commit); };
  };
  const persistDraft = () => {
    if (!alive) return;
    const { name, notes, activeTab } = editor.snapshot();
    const value = { name, notes, activeTab };
    if (widget) widget.setValue(value); else cell?.set(value);
    render();
  };
  const dispose = () => {
    if (!alive) return; alive = false;
    unrender(); subs.splice(0).forEach(off => off()); editor.dispose();
    container?.replaceChildren(); container = null; cell = null;
  };
  widget = node.widgets.mount({ name: 'ned_info_notes', height: 180,
    defaultValue: { name: null, notes: '', activeTab: 'notes' }, serialize: true, sendToPrompt: false,
    render(root, value) { container = root; cell = value; render(); }, destroy: dispose,
  });
  subs.push(editor.onChange(persistDraft));
  // Fresh configured workflow state includes a draft, not a replacement of the
  // authoritative record. Read current revision first, then restore the draft.
  const restore = async value => {
    if (!value || Object.getPrototypeOf(value) !== Object.prototype ||
        Object.keys(value).sort().join(',') !== 'activeTab,name,notes' ||
        typeof value.notes !== 'string' || !['notes', 'description'].includes(value.activeTab))
      throw new Error('Invalid notes workflow snapshot');
    const selected = await editor.select(value.name);
    if (!alive || !selected) return false;
    editor.tab(value.activeTab); editor.edit(value.notes); return true;
  };
  subs.push(widget.on('beforeSerialize', event => {
    if (alive) { const { name, notes, activeTab } = editor.snapshot(); event.setSerializedValue({ name, notes, activeTab }); }
  }));
  render();
  return Object.freeze({ select: name => editor.select(name), edit: text => editor.edit(text),
    save: () => editor.save(), tab: value => editor.tab(value), snapshot: () => editor.snapshot(),
    restore, dispose });
}
