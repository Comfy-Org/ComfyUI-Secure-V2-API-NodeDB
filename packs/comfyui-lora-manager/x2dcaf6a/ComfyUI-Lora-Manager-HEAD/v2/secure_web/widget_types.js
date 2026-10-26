// LoRA Manager rev 10: the pack's own input widget types, registered through comfy.defs.defineWidgetType (platform request
// #11, host-stack r4a). LORAS, AUTOCOMPLETE_TEXT_LORAS and AUTOCOMPLETE_TEXT_PROMPT are input types this pack's nodes declare
// in secure-nodes.json. While no type is registered the host renders those inputs as sockets and drops their values from
// widgets_values (comfy-api.d.ts, DefRegistry.defineWidgetType).
//
// The live guest (c6b97a15) does not bridge defineWidgetType: the call falls through to the generic rpc, which cannot clone
// the render function. Only a synchronous Unsubscribe counts as registered, so nothing changes on live and the widgets appear
// once r4a lands.
//
// Held (platform list): autocomplete, caret insertion and the keyboard producer need G3 (a textarea element handle), G4 (the
// settings call through the declared backend API on the pack's own route) and G5 (ui.editable-keyboard). The two text types
// are plain multiline editors holding the same string value. The live sanitizer strips aria-pressed, aria-checked,
// aria-expanded and role (G7), so row state is also shown with inline styles.
import { createCatalogueSelection } from './catalogue_selection.js';
import { commitStrengthText } from './row_editor.js';

export const LORA_WIDGET_TYPES = Object.freeze(['LORAS', 'AUTOCOMPLETE_TEXT_LORAS', 'AUTOCOMPLETE_TEXT_PROMPT']);
const encoder = new TextEncoder();
// The owned text profile of the retained Loader/Stacker editors: refuse visibly, never truncate.
const MAX_TEXT_BYTES = 262144;
const MAX_CHOICES = 128;

/** @param {unknown} value */
function textOf(value) {
  if (value === null || value === undefined) return '';
  if (typeof value !== 'string' || encoder.encode(value).length > MAX_TEXT_BYTES)
    throw new Error('LoRA text requires a string within the 262144-byte owned profile');
  return value;
}

/** @param {any} context */
function optionsOf(context) {
  try { const options = context?.getOptions?.(); return options && typeof options === 'object' ? options : {}; }
  catch { return {}; }
}

/** Plain multiline editor bound to the value cell (both AUTOCOMPLETE_TEXT_* types). */
export function renderText(container, value, name, context) {
  const doc = container.ownerDocument;
  const options = optionsOf(context);
  const textarea = doc.createElement('textarea');
  textarea.setAttribute('aria-label', String(name));
  if (typeof options.placeholder === 'string') textarea.setAttribute('placeholder', options.placeholder);
  textarea.style.cssText = 'width:100%;min-height:56px;box-sizing:border-box;resize:vertical;font-family:inherit';
  const status = doc.createElement('p');
  status.style.cssText = 'margin:2px 0 0;font-size:11px;color:#e57373';
  container.replaceChildren(textarea, status);
  const show = () => {
    let text;
    try { text = textOf(value.get()); status.textContent = ''; }
    catch (error) { status.textContent = String(error?.message ?? error); return; }
    if (textarea.value !== text) textarea.value = text;
    // The opaque textarea renderer needs literal content as well as the value property.
    if (textarea.textContent !== text) textarea.textContent = text;
  };
  const onInput = () => {
    try {
      const next = textOf(textarea.value);
      if (next !== value.get()) value.set(next);
      status.textContent = '';
    } catch (error) { status.textContent = String(error?.message ?? error); }
  };
  textarea.addEventListener('input', onInput);
  const offChange = value.onChange(show);
  show();
  return () => {
    offChange();
    textarea.removeEventListener('input', onInput);
    container.replaceChildren();
  };
}

/** LORAS rows editor over the retained catalogue controller (same row math as row_editor.js). */
export function renderLoras(comfy, container, value, name) {
  const doc = container.ownerDocument;
  const prefix = String(name);
  let alive = true, query = '', loading = false, error = null, generation = 0;
  const listeners = [];
  const release = () => listeners.splice(0).forEach(off => off());
  const controller = createCatalogueSelection(comfy, { read: () => value.get(), write: next => value.set(next) });
  const perform = action => {
    if (!alive) return;
    try { error = null; action(); } catch (failure) { error = String(failure?.message ?? failure); }
    render();
  };
  const indexOf = rowName => {
    const index = controller.snapshot().findIndex(row => row.name === rowName);
    if (index < 0) throw new Error('LoRA row no longer exists');
    return index;
  };
  async function refresh() {
    if (!alive) return false;
    const ticket = ++generation;
    loading = true; error = null; render();
    try { return await controller.refresh(); }
    catch (failure) { if (alive && ticket === generation) error = String(failure?.message ?? failure); return false; }
    finally { if (alive && ticket === generation) { loading = false; render(); } }
  }
  function render() {
    if (!alive) return;
    release(); container.replaceChildren();
    const listen = (element, type, callback) => {
      element.addEventListener(type, callback);
      listeners.push(() => element.removeEventListener(type, callback));
    };
    const text = (parent, tag, content) => {
      const element = doc.createElement(tag); element.textContent = content; parent.append(element); return element;
    };
    const button = (parent, label, ariaLabel, action) => {
      const element = text(parent, 'button', label); element.type = 'button';
      element.setAttribute('aria-label', ariaLabel);
      listen(element, 'click', () => perform(action));
      return element;
    };
    text(container, 'strong', 'LoRAs');
    let rows;
    try { rows = controller.snapshot(); }
    catch (failure) { text(container, 'p', String(failure?.message ?? failure)); return; }
    const search = doc.createElement('input'); search.type = 'search';
    search.setAttribute('aria-label', prefix + '.search'); search.setAttribute('value', query);
    container.append(search);
    const choices = doc.createElement('div'); container.append(choices);
    const choiceOffs = [];
    listeners.push(() => choiceOffs.splice(0).forEach(off => off()));
    const searchChoices = () => {
      choiceOffs.splice(0).forEach(off => off()); choices.replaceChildren();
      try {
        for (const choice of controller.search(query).slice(0, MAX_CHOICES)) {
          const element = text(choices, 'button', choice); element.type = 'button';
          element.setAttribute('aria-label', prefix + '.add.' + choice);
          const clicked = () => perform(() => controller.add(choice));
          element.addEventListener('click', clicked);
          choiceOffs.push(() => element.removeEventListener('click', clicked));
        }
      } catch (failure) { error = String(failure?.message ?? failure); }
    };
    listen(search, 'input', () => { query = search.value ?? ''; searchChoices(); });
    button(container, loading ? 'Refreshing…' : 'Refresh catalogue', prefix + '.refresh', () => { void refresh(); }).disabled = loading;
    for (const row of rows) {
      const line = doc.createElement('div'); container.append(line);
      line.style.cssText = 'display:flex;gap:4px;align-items:center;flex-wrap:wrap' + (row.active ? '' : ';opacity:0.55');
      const choose = button(line, row.name, prefix + '.select.' + row.name, () => controller.select(row.name));
      if (row.selected) choose.style.cssText = 'font-weight:bold;outline:1px solid currentColor';
      button(line, row.active ? 'Active' : 'Inactive', prefix + '.active.' + row.name,
        () => controller.update(indexOf(row.name), { active: !controller.snapshot()[indexOf(row.name)].active }));
      const strength = (field, label) => {
        const input = doc.createElement('input'); input.type = 'text';
        input.setAttribute('aria-label', label + '.' + row.name);
        input.setAttribute('value', Number(row[field]).toFixed(2));
        input.style.cssText = 'width:4.5em';
        line.append(input);
        listen(input, 'change', () => perform(() =>
          controller.update(indexOf(row.name), { [field]: commitStrengthText(input.value) })));
      };
      strength('strength', prefix + '.strength');
      button(line, row.expanded ? 'Collapse CLIP' : 'Expand CLIP', prefix + '.expand.' + row.name,
        () => controller.update(indexOf(row.name), { expanded: !controller.snapshot()[indexOf(row.name)].expanded }));
      if (row.expanded) strength('clipStrength', prefix + '.clipStrength');
      const move = direction => {
        const from = indexOf(row.name), to = from + direction;
        if (to >= 0 && to < controller.snapshot().length) controller.move(from, to);
      };
      button(line, 'Move up', prefix + '.up.' + row.name, () => move(-1)).disabled = rows[0].name === row.name;
      button(line, 'Move down', prefix + '.down.' + row.name, () => move(1)).disabled = rows[rows.length - 1].name === row.name;
      button(line, 'Remove', prefix + '.remove.' + row.name, () => controller.remove(indexOf(row.name)));
    }
    text(container, 'p', error ?? '').style.cssText = 'margin:2px 0 0;font-size:11px;color:#e57373';
    searchChoices();
  }
  const offController = controller.onChange(render);
  const offValue = value.onChange(() => {
    // A workflow load replaces the rows: validate, never substitute defaults on corruption.
    try { controller.snapshot(); error = null; } catch (failure) { error = String(failure?.message ?? failure); }
    render();
  });
  render();
  void refresh();
  return () => {
    if (!alive) return;
    alive = false; ++generation;
    release(); offController(); offValue(); controller.dispose(); container.replaceChildren();
  };
}

/**
 * @returns {{type: string, registered: boolean, reason?: string, off?: () => void}}
 */
function registerType(comfy, type, def) {
  let result;
  try { result = comfy.defs.defineWidgetType(type, def); }
  catch (error) { return { type, registered: false, reason: String(error?.name ?? 'Error') + ': ' + String(error?.message ?? error).slice(0, 160) }; }
  if (typeof result === 'function') return { type, registered: true, off: result };
  // A Promise is the generic rpc, not the bridge: let it settle without an unhandled rejection.
  if (result && typeof result.then === 'function') result.then(undefined, () => {});
  return { type, registered: false, reason: 'no widget-type bridge' };
}

/** @param {any} comfy */
export function registerLoraWidgetTypes(comfy) {
  const defs = {
    LORAS: { defaultValue: [], minHeight: 160, serialize: true,
             render: (container, value, name) => renderLoras(comfy, container, value, name) },
    AUTOCOMPLETE_TEXT_LORAS: { defaultValue: '', minHeight: 56, serialize: true, render: renderText },
    AUTOCOMPLETE_TEXT_PROMPT: { defaultValue: '', minHeight: 56, serialize: true, render: renderText },
  };
  const results = LORA_WIDGET_TYPES.map(type => registerType(comfy, type, defs[type]));
  let disposed = false;
  return {
    available: results.some(result => result.registered),
    results: results.map(({ type, registered, reason }) => (reason ? { type, registered, reason } : { type, registered })),
    dispose() {
      if (disposed) return;
      disposed = true;
      for (const result of results) {
        if (!result.off) continue;
        try { result.off(); } catch (error) { console.error('[LoRA Manager] widget type unsubscribe failed:', error); }
      }
    },
  };
}
