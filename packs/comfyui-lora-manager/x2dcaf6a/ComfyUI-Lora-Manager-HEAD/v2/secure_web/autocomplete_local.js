// Private MIKE40de keyboard compatibility successor. Authenticated catalogue
// ranking/filtering/pagination and provider publication remain separate gates.
import { LoaderAutocompleteSelection } from './autocomplete_selection.js';
import { attachEditableKeyboard } from './editable_keyboard.js';

const MAX_NAMES = 2048;
const MAX_BYTES = 262144;
const encode = new TextEncoder();

export function attachLocalAutocomplete(comfy, node, editor, root, report, keyboardOptions) {
  let alive = true, generation = 0, debounceTimer = null, blurTimer = null;
  let removals = [];
  const selection = new LoaderAutocompleteSelection();
  const doc = root.ownerDocument;
  const menu = doc.createElement('div');
  menu.setAttribute('role', 'listbox');
  menu.setAttribute('aria-label', 'loader.autocomplete');
  root.append(menu);
  const element = comfy.element('loader.autocomplete.text', {
    nodeId: String(node.id), widget: 'text'
  });
  const keyboard = attachEditableKeyboard({ editor, element, selection,
    preferences: keyboardOptions.preferences, commit: keyboardOptions.commit,
    resolve: keyboardOptions.producer.resolve,
    paint, close: hide, report });
  let offPreferences;
  try { offPreferences = keyboardOptions.observePreferences(hide); }
  catch (error) { keyboard.dispose(); menu.remove(); throw error; }
  const live = version => alive && !node.isDeleted && version === generation;
  function clearOptions() {
    for (const remove of removals) remove();
    removals = []; menu.replaceChildren();
  }
  function hide() {
    keyboard.clear(); generation++; clearTimeout(debounceTimer); clearTimeout(blurTimer);
    debounceTimer = blurTimer = null;
    selection.reset(); clearOptions();
  }
  function paint() {
    clearOptions();
    for (const [index, item] of selection.items.entries()) {
      const button = doc.createElement('button');
      button.setAttribute('type', 'button');
      button.setAttribute('role', 'option');
      button.setAttribute('aria-selected', String(index === selection.selectedIndex));
      button.setAttribute('aria-label', 'loader.autocomplete.' + item);
      // Names retain their original spaces; only the native extension stripping
      // is used for display. No HTML parsing of catalogue values.
      button.textContent = selection._getDisplayText(item);
      const choose = () => {
        if (!alive || node.isDeleted) return;
        void keyboard.pointer(index);
      };
      button.addEventListener('pointerdown', choose);
      removals.push(() => button.removeEventListener('pointerdown', choose));
      menu.append(button);
    }
  }
  async function search(version) {
    try {
      // The scoped public element broker supplies the actual live caret. The
      // Candidate key events have UTF16 snapshots; menu searches independently
      // observe the current scoped control rather than inventing a caret.
      const before = await element.get('value');
      const caret = await element.get('selectionStart');
      const end = await element.get('selectionEnd');
      const after = await element.get('value');
      if (!live(version)) return;
      if (before !== after || before !== editor.value ||
          !Number.isInteger(caret) || caret < 0 || caret > after.length ||
          !Number.isInteger(end) || end < caret || end > after.length) {
        throw new Error('Autocomplete text changed while reading its caret.');
      }
      if (encode.encode(after).length > MAX_BYTES) throw new Error('Autocomplete text exceeds its owned profile.');
      const prefs = keyboardOptions.preferences();
      const term = selection.range(after, caret, prefs.appendComma).text;
      if (!term || term.startsWith('/')) {
        // Native slash commands require the real manager active-filter state.
        // This local catalogue path does not invent that state or a producer.
        hide();
        if (term.startsWith('/')) report('Autocomplete commands are unavailable in this profile.');
        return;
      }
      const names = await comfy.models.list('loras');
      if (!live(version)) return;
      if (!Array.isArray(names) || names.length > MAX_NAMES ||
          names.some(name => typeof name !== 'string') ||
          encode.encode(JSON.stringify(names)).length > MAX_BYTES) {
        throw new Error('Autocomplete catalogue exceeds its owned profile.');
      }
      // Preserve genuine supplied catalogue order within each native query
      // variation. This is not the native HTTP relevance/folder ordering.
      const items = [], seen = new Set();
      for (const query of selection._getQueriesToExecute(term)) {
        for (const name of names) {
          if (selection._matchItem(name, query).matched && !seen.has(name.toLowerCase())) {
            seen.add(name.toLowerCase()); items.push(name);
          }
        }
      }
      // Native search maxItems=100; never silently truncate an admitted result.
      // Server pagination/virtual scrolling is a separate unresolved producer.
      if (items.length > 100) throw new Error('Autocomplete needs a selected paginated search profile.');
      selection.replace(items, term); report(''); paint();
      if (!items.length) return;
      const plans = await keyboardOptions.producer.prepare(items, prefs.appendComma, () => live(version));
      if (!plans || !live(version)) return;
      const observed = await keyboard.read();
      if (!live(version)) return;
      if (observed.value !== after || observed.start !== caret || observed.end !== end) {
        throw new Error('Menu input changed while obtaining actual insertion data');
      }
      const currentPreferences = keyboardOptions.preferences();
      if (currentPreferences.mode !== prefs.mode || currentPreferences.appendComma !== prefs.appendComma) {
        throw new Error('Menu preferences changed while obtaining actual insertion data');
      }
      keyboard.open(observed, plans, prefs.mode, prefs.appendComma);
    } catch (error) {
      if (!live(version)) return;
      hide(); report(String(error.message ?? error));
    }
  }
  function changed() {
    if (!alive || node.isDeleted) return;
    clearTimeout(debounceTimer); clearTimeout(blurTimer);
    keyboard.clear();
    const version = ++generation;
    // Immediately invalidate old options; a late result cannot select stale
    // items between the edit and the pinned 200ms search debounce.
    selection.reset(); clearOptions();
    debounceTimer = setTimeout(() => { debounceTimer = null; void search(version); }, 200);
  }
  function blurred() {
    clearTimeout(blurTimer);
    blurTimer = setTimeout(hide, 150); // pinned pointer-selection grace
  }
  editor.addEventListener('input', changed);
  editor.addEventListener('click', changed);
  editor.addEventListener('select', changed);
  editor.addEventListener('blur', blurred);
  return {
    reset() { hide(); selection.restore(); },
    dispose() {
      if (!alive) return;
      alive = false; hide();
      editor.removeEventListener('input', changed);
      editor.removeEventListener('click', changed);
      editor.removeEventListener('select', changed);
      editor.removeEventListener('blur', blurred);
      offPreferences(); keyboard.dispose();
      menu.remove();
    }
  };
}
