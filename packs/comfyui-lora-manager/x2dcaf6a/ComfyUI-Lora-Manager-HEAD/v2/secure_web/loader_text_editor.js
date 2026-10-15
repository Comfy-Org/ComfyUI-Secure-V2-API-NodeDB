// Pack-owned mounted Loader candidate. Graph-dependent trigger propagation
// is an explicit remaining family gate; this module never guesses GraphScope.
import { registerRowEditor } from './row_editor.js';
import { normalizeRows } from './catalogue_selection.js';
import { mergeLoras } from './stacker_merge.js';
import { applyLoraValuesToText, debounce } from './stacker_syntax.js';
import { createAutoFormatPreference, formatAutocompleteTextOnBlur } from './autocomplete_blur.js';
import { attachLocalAutocomplete } from './autocomplete_local.js';

const TYPE = 'Lora Loader (LoraManager)';
const encoder = new TextEncoder();
// Same encoded ownership ceiling as the retained catalogue row helper.
// Workloads outside this admitted profile visibly refuse, never truncate.
const MAX_TEXT_BYTES = 262144;

function textValue(value) {
  if (typeof value !== 'string' || encoder.encode(value).length > MAX_TEXT_BYTES) {
    throw new Error('Loader text requires a string within the 262144-byte owned profile');
  }
  return value;
}

export function registerLoaderTextEditor(comfy, keyboardOptions) {
  const getAutoFormatPreference = createAutoFormatPreference(comfy);
  return registerRowEditor(comfy, { type: TYPE, prefix: 'loader', lifecycle(node) {
    // Validate both original optional sockets before adding either. Never
    // drop existing links or replace a mismatching reconstructed socket.
    const slots = node.inputs.all();
    for (const [name, type] of [['clip', 'CLIP'], ['lora_stack', 'LORA_STACK']]) {
      const matching = slots.filter(slot => slot.name === name);
      if (matching.length > 1 || (matching.length === 1 && matching[0].type !== type)) {
        throw new Error('Existing Loader ' + name + ' socket is ambiguous/incompatible');
      }
    }
    const previous = node.widgets.get('text');
    const initialText = textValue(previous ? previous.getValue() : '');
    // Complete initial row/text/socket preflight before the first mutation.
    node.setSerializeWidgets(true);
    if (!node.inputs.byName('clip')) node.inputs.add('clip', 'CLIP', { shape: 'optional' });
    if (!node.inputs.byName('lora_stack')) node.inputs.add('lora_stack', 'LORA_STACK', { shape: 'optional' });
    if (previous) node.widgets.remove('text');
    let alive = true, restoring = false, rowWidget = null, textWidget = null;
    let cell = null, textarea = null, status = null, root = null, failure = null;
    let offCell = null, offText = null, offRows = null, offInput = null;
    let observedRows = null;
    let disposeEditor = null, autocomplete = null;

    const currentText = () => textValue(textWidget ? textWidget.getValue() : cell ? cell.get() : initialText);
    const currentRows = () => normalizeRows(rowWidget?.getValue());
    function show() {
      if (!alive || node.isDeleted || !textarea) return;
      try {
        const value = currentText();
        if (textarea.value !== value) {
          autocomplete?.reset(); // External widget edits invalidate key readiness.
          textarea.value = value;
        }
        // The element facade materializes incoming value properties separately
        // from markup. Keep literal textarea content current after direct commits.
        if (textarea.textContent !== value) textarea.textContent = value;
      } catch (error) { failure = String(error.message ?? error); }
      if (status) status.textContent = failure ?? '';
    }
    function perform(action) {
      if (!alive || node.isDeleted) return;
      try { failure = null; action(); }
      catch (error) { failure = String(error.message ?? error); }
      show();
    }
    function setText(value) {
      const next = textValue(value);
      if (next === currentText()) return;
      if (textWidget) textWidget.setValue(next);
      else if (cell) cell.set(next);
      else throw new Error('Loader text is not mounted');
    }
    function mergeCurrentText() {
      if (!rowWidget) return;
      // Literal pinned merge: existing matching rows keep their authored
      // strengths and order, regardless of changed strengths in the text.
      const current = currentRows();
      const merged = normalizeRows(mergeLoras(currentText(), current));
      const signature = JSON.stringify(merged);
      if (signature !== JSON.stringify(current)) rowWidget.setValue(merged);
      // Published worker change delivery is asynchronous. A reply to our own
      // text merge must not re-enter the row-edit callback and clean the text.
      observedRows = signature;
    }
    const inputSync = debounce(value => perform(() => {
      if (!rowWidget || restoring) return;
      setText(applyLoraValuesToText(currentText(), value));
    })); // Pinned native DEFAULT_DEBOUNCE_MS = 80, not a queue hook substitute.

    textWidget = node.widgets.mount({ name: 'text', height: 120,
      defaultValue: initialText, serialize: true, sendToPrompt: true,
      render(container, value) {
        if (!alive || node.isDeleted) return;
        root = container;
        if (cell !== value) {
          offCell?.(); cell = value;
          offCell = cell.onChange(show);
        }
        offInput?.(); autocomplete?.dispose(); autocomplete = null; root.replaceChildren();
        const doc = root.ownerDocument;
        textarea = doc.createElement('textarea');
        textarea.setAttribute('aria-label', 'loader.text');
        textarea.setAttribute('data-name', 'loader.autocomplete.text');
        textarea.setAttribute('placeholder', 'Search LoRAs; use <lora:name:strength>');
        textarea.textContent = currentText();
        root.append(textarea);
        status = doc.createElement('p'); status.setAttribute('role', 'status'); root.append(status);
        const editor = textarea;
        const inputChanged = () => perform(() => {
          inputSync.cancel();
          setText(editor.value);
          // The worker's widget write is optimistic; merge from its actual
          // published value rather than holding a separate authored draft.
          mergeCurrentText();
        });
        const blurChanged = () => perform(() => {
          if (!getAutoFormatPreference()) return;
          const current = editor.value;
          const formatted = textValue(formatAutocompleteTextOnBlur(current));
          if (formatted === current) return;
          // Native blur dispatches input after formatting. The selected opaque
          // facade's dispatchEvent is a no-op, so call this same input callback:
          // cancel pending row->text work, commit widget text and merge rows.
          editor.value = formatted;
          inputChanged();
        });
        editor.addEventListener('input', inputChanged);
        editor.addEventListener('blur', blurChanged);
        offInput = () => {
          editor.removeEventListener('input', inputChanged);
          editor.removeEventListener('blur', blurChanged);
        };
        autocomplete = attachLocalAutocomplete(comfy, node, editor, root, message => {
          failure = message; show();
        }, { ...keyboardOptions, commit: inputChanged });
        show();
      },
      destroy() { dispose(); }
    });

    function dispose() {
      if (!alive) return;
      alive = false; inputSync.cancel(); autocomplete?.dispose(); autocomplete = null;
      offCell?.(); offText?.(); offRows?.(); offInput?.();
      offCell = offText = offRows = offInput = null;
      root?.replaceChildren(); root = textarea = status = cell = null;
      rowWidget = textWidget = null;
      disposeEditor?.(); disposeEditor = null;
    }
    return {
      rowsChanged(value) {
        if (alive && !restoring && !node.isDeleted) {
          const rows = normalizeRows(value);
          observedRows = JSON.stringify(rows);
          inputSync(rows);
        }
      },
      attach(widget, disposeOwner) {
        rowWidget = widget;
        disposeEditor = disposeOwner;
        observedRows = JSON.stringify(currentRows());
        offText = textWidget.on('change', () => perform(() => {
          inputSync.cancel(); mergeCurrentText();
        }));
        offRows = rowWidget.on('change', value => {
          if (!alive || node.isDeleted) return;
          perform(() => {
            const rows = normalizeRows(value), signature = JSON.stringify(rows);
            if (signature === observedRows) return;
            observedRows = signature;
            if (!restoring) inputSync(rows);
          });
        });
      },
      restore() {
        if (!alive || node.isDeleted) return;
        inputSync.cancel(); autocomplete?.reset(); restoring = true;
        try { mergeCurrentText(); failure = null; }
        catch (error) { failure = String(error.message ?? error); throw error; }
        finally { restoring = false; show(); }
      },
      dispose
    };
  } });
}
