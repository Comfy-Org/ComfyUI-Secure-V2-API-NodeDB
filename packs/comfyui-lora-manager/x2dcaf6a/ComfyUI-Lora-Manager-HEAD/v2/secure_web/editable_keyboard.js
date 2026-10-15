// MIKE 40de94c compatibility only. The worker never cancels a DOM event.
const utf8 = new TextEncoder();
const controlled = new Set(['ArrowDown', 'ArrowUp', 'Enter', 'Tab', 'Escape']);

export function keysForMode(mode) {
  return ['ArrowDown', 'ArrowUp', 'Escape',
    ...(mode === 'tab_only' ? ['Tab'] : mode === 'enter_only' ? ['Enter'] : ['Tab', 'Enter'])];
}

export function validOwnedSnapshot(snapshot) {
  return snapshot && typeof snapshot.value === 'string' &&
    Number.isInteger(snapshot.start) && Number.isInteger(snapshot.end) &&
    snapshot.start >= 0 && snapshot.end >= snapshot.start && snapshot.end <= snapshot.value.length;
}

export function attachEditableKeyboard({ editor, element, selection, preferences, resolve, commit, paint, close, report }) {
  let alive = true, composing = false, ready = null, generation = 0, busyToken = null;
  function clear() {
    generation++; ready = null; busyToken = null;
    editor.removeAttribute('data-editable-keys');
  }
  function open(snapshot, plans, mode, appendComma) {
    clear();
    if (!alive || composing || busyToken !== null || !validOwnedSnapshot(snapshot) || !selection.items.length ||
        !(plans instanceof Map) || selection.items.some(item => !plans.has(item) ||
          typeof plans.get(item) !== 'string' || !plans.get(item))) return false;
    ready = { snapshot: { ...snapshot }, plans, mode, appendComma, generation };
    editor.setAttribute('data-editable-keys', keysForMode(mode).join(' '));
    return true;
  }
  function same(a, b) { return a.value === b.value && a.start === b.start && a.end === b.end; }
  async function read() {
    const before = await element.get('value');
    const start = await element.get('selectionStart');
    const end = await element.get('selectionEnd');
    const value = await element.get('value');
    const snapshot = { value, start, end };
    if (before !== value || editor.value !== value || !validOwnedSnapshot(snapshot)) {
      throw new Error('Owned text/caret changed during observation');
    }
    return snapshot;
  }
  async function apply(item, observed, state) {
    const token = ++generation;
    busyToken = token; ready = null; editor.removeAttribute('data-editable-keys');
    const previousAccepted = selection.lastAccepted;
    let wrote = false, plannedMarker = null, errorOwner = token;
    try {
      // Read actual usage again at acceptance, as native insertSelection does.
      // Prefetched readiness alone is not a guarantee about a later authored edit.
      const insertText = await resolve(item, state.appendComma,
        () => alive && !composing && token === generation);
      const current = await read();
      if (!alive || composing || token !== generation || !same(current, observed)) {
        throw new Error('Stale autocomplete acceptance refused before text write');
      }
      if (typeof insertText !== 'string' || !insertText) throw new Error('Actual insertion data is not ready');
      const plan = selection.resolvedInsertion(current.value, current.start, insertText, state.appendComma);
      plannedMarker = selection.lastAccepted;
      if (!plan || utf8.encode(plan.value).length > 262144) throw new Error('Result exceeds Loader text ownership');
      // Readback guards are observational, not an atomic host compare-and-write.
      const final = await read();
      if (!alive || composing || token !== generation || !same(final, observed)) {
        throw new Error('Text changed before autocomplete write');
      }
      // Publish through the SAME mounted widget callback. No inert dispatchEvent,
      // host editor access, forged input event or alternate lifecycle owner.
      editor.value = plan.value;
      editor.textContent = plan.value;
      commit(); wrote = true;
      close();
      errorOwner = generation;
      const after = await element.get('value');
      if (!alive || errorOwner !== generation) return;
      if (!alive || editor.value !== plan.value || after !== plan.value) {
        throw new Error('Insertion caret restoration refused after changed text');
      }
      await element.invoke('setSelectionRange', plan.caret, plan.caret);
      // A failure here leaves the committed draft visible; never roll back over
      // a concurrent edit. Genuine queued typing/caret races remain test gates.
    } catch (error) {
      if (!wrote && plannedMarker !== null && selection.lastAccepted === plannedMarker) {
        selection.lastAccepted = previousAccepted;
      }
      // A late failed read cannot close a newer menu, resurrect a restored
      // continuation marker, or report an error on a removed mount.
      if (!alive || errorOwner !== generation) return;
      clear(); close(); report(String(error.message ?? error));
    } finally { if (busyToken === token) busyToken = null; }
  }
  async function keyed(event) {
    if (!alive || !controlled.has(event.key)) return;
    const state = ready;
    if (!state) return; // Includes already-queued keys after a cleared declaration.
    const observed = { value: event.value, start: event.selectionStart, end: event.selectionEnd };
    const prefs = preferences();
    if (composing || event.isComposing === true || event.keyCode === 229 ||
        event.ctrlKey || event.altKey || event.metaKey || event.shiftKey) return;
    if (event.target !== editor || event.currentTarget !== editor || event.trustedGesture !== true ||
        event.editableTarget !== true || event.defaultPrevented !== true ||
        !keysForMode(state.mode).includes(event.key) ||
        prefs.mode !== state.mode || prefs.appendComma !== state.appendComma ||
        !validOwnedSnapshot(observed) || !same(observed, state.snapshot) || editor.value !== observed.value) {
      clear(); close(); report('Unclaimed or stale keyboard acceptance refused'); return;
    }
    const term = selection.range(observed.value, observed.start, state.appendComma).text;
    const intent = selection.keyIntent(event.key, term, state.mode);
    if (intent.kind === 'hide') { clear(); close(); return; }
    if (intent.kind === 'select') { paint(); open(state.snapshot, state.plans, state.mode, state.appendComma); return; }
    if (intent.kind === 'accept') await apply(intent.item, observed, state);
  }
  async function pointer(index) {
    const state = ready;
    if (!alive || !state || busyToken !== null || composing || index < 0 || index >= selection.items.length) return;
    const prefs = preferences();
    if (prefs.mode !== state.mode || prefs.appendComma !== state.appendComma) { clear(); close(); return; }
    selection.select(index, true); paint();
    await apply(selection.items[index], state.snapshot, state);
  }
  const startComposition = () => { composing = true; clear(); close(); };
  const endComposition = () => { composing = false; clear(); };
  const blurred = () => clear(); // Pointer grace is menu-owned; keys stop immediately.
  editor.addEventListener('keydown', keyed);
  editor.addEventListener('compositionstart', startComposition);
  editor.addEventListener('compositionend', endComposition);
  editor.addEventListener('blur', blurred);
  return {
    open, clear, read, pointer,
    dispose() {
      if (!alive) return;
      alive = false; clear();
      editor.removeEventListener('keydown', keyed);
      editor.removeEventListener('compositionstart', startComposition);
      editor.removeEventListener('compositionend', endComposition);
      editor.removeEventListener('blur', blurred);
    }
  };
}
