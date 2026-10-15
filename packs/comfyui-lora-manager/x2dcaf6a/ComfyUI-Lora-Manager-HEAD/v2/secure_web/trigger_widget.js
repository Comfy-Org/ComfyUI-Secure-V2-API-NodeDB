import { applyHighlightTags, collectHighlightTokens, formatStrengthValue, readSavedTriggerWidgets, reconcileTags, serializeTags } from './trigger_logic.js';

import { createManagerPreferences } from './manager_settings.js';

const TYPE = 'TriggerWord Toggle (LoraManager)';
const keyOf = node => JSON.stringify([node.graphId, node.id]);
const cloneTags = tags => tags.map(tag => ({ ...tag,
  ...(Array.isArray(tag.items) ? { items: tag.items.map(item => ({ ...item })) } : {}) }));

// Partial frontend adapter. Public backend delivery is scoped by graph/node;
// browser restoration, original group editor and chain highlight remain held.
export function registerTriggerWords(comfy) {
  const instances = new Map();
  const preferences = createManagerPreferences(comfy);
  let sequence = 0;
  let removed = false;
  const disposeRemoved = () => {
    for (const state of [...instances.values()]) if (state.node.isDeleted) state.dispose();
  };
  const offDefinition = comfy.defs.extend(TYPE, builder => {
    builder.onCreated(node => {
      if (removed || node.isDeleted) return;
      instances.get(keyOf(node))?.dispose();
      const key = keyOf(node);
      node.setSerializeWidgets(true);
      // Native adds a hollow optional circle using shape7. Public onCreated
      // runs after restoration, so retain an existing restored socket.
      if (!node.inputs.byName('trigger_words'))
        node.inputs.add('trigger_words', 'string', { shape: 'optional' });
      const wheelSensitivity = preferences.getWheelSensitivity();
      const controls = ['group_mode', 'default_active', 'allow_strength_adjustment']
        .map(name => node.widgets.get(name));
      if (controls.some(widget => !widget)) throw new Error('Trigger controls are missing');
      // Existing converted value cells may be present after reconfiguration.
      const previous = node.widgets.get('toggle_trigger_words');
      const restoredTags = previous?.getValue();
      if (previous) node.widgets.remove('toggle_trigger_words');
      let original = node.widgets.get('orinalMessage');
      if (!original) original = node.widgets.add({ name: 'orinalMessage', type: 'text',
        value: '', hidden: true, serialize: true });
      let highlightedWords = new Set();
      let alive = true;
      let root = null;
      let value = null;
      let widget = null;
      let dialog = null;
      let dialogGeneration = 0;
      let unrender = () => {};
      const subscriptions = [];
      const current = () => widget ? widget.getValue() : value?.get() ?? [];
      const closeEditor = () => { ++dialogGeneration; dialog?.close(); dialog = null; };
      const commit = next => {
        if (!alive || node.isDeleted) return;
        if (widget) widget.setValue(next); else value?.set(next);
      };
      const change = action => { const next = cloneTags(current()); action(next); commit(next); };
      const listen = (element, event, fn, options) => {
        element.addEventListener(event, fn, options);
        return () => element.removeEventListener(event, fn, options);
      };
      const strengthAllowed = () => Boolean(controls[2].getValue());
      const drawButton = (parent, tag, run) => {
        const button = parent.ownerDocument.createElement('button');
        button.type = 'button';
        const display = strengthAllowed() ? formatStrengthValue(tag.strength ?? 1) : null;
        button.textContent = tag.text + (display !== null ? ` (${display})` : '');
        button.setAttribute('aria-pressed', String(Boolean(tag.active)));
        button.setAttribute('data-highlighted', String(Boolean(tag.highlighted)));
        parent.appendChild(button);
        const off = listen(button, 'click', event => {
          event.preventDefault(); event.stopPropagation();
          if (alive && !node.isDeleted) run();
        });
        return { button, off };
      };
      const openEditor = index => {
        closeEditor();
        const generation = dialogGeneration;
        const identity = current()[index]?.text;
        dialog = comfy.ui.showDialog({ key: `loramanager.trigger-group-${++sequence}`, title: 'Trigger group',
          render(container) {
            if (!alive || node.isDeleted || generation !== dialogGeneration) return;
            const offs = [];
            const group = current()[index];
            if (!group || !Array.isArray(group.items)) return;
            for (let child = 0; child < group.items.length; child++) {
              const { button, off } = drawButton(container, group.items[child], () => {
                if (generation !== dialogGeneration || current()[index]?.text !== identity) return;
                change(next => { next[index].items[child].active = !next[index].items[child].active; });
                button.setAttribute('aria-pressed', String(Boolean(current()[index].items[child].active)));
              });
              offs.push(off);
            }
            dialogCleanup = () => offs.splice(0).forEach(off => off());
          },
          onKeyDown(event) { if (event.key === 'Escape') closeEditor(); },
          destroy() {
            if (dialogGeneration === generation) ++dialogGeneration;
            dialogCleanup(); dialogCleanup = () => {};
          },
        });
      };
      let dialogCleanup = () => {};
      const render = () => {
        if (!alive || !root) return;
        unrender();
        root.replaceChildren();
        const offs = [];
        try {
          const tags = current();
          tags.forEach((tag, index) => {
            const { button, off } = drawButton(root, tag, () => change(next => { next[index].active = !next[index].active; }));
            offs.push(off);
            if (strengthAllowed()) offs.push(listen(button, 'wheel', event => {
              if (!alive || node.isDeleted) return;
              event.preventDefault(); event.stopPropagation();
              const step = wheelSensitivity;
              change(next => { next[index].strength = Math.max(0,
                (next[index].strength ?? 1) + (event.deltaY < 0 ? step : -step)); });
            }, { passive: false }));
            if (Array.isArray(tag.items)) {
              const edit = root.ownerDocument.createElement('button');
              edit.type = 'button'; edit.textContent = 'Edit group';
              root.appendChild(edit);
              offs.push(listen(edit, 'click', () => { if (alive) openEditor(index); }));
            }
          });
        } catch (error) {
          const warning = root.ownerDocument.createElement('span');
          warning.textContent = String(error.message); root.appendChild(warning);
        }
        unrender = () => offs.splice(0).forEach(off => off());
      };
      const dispose = () => {
        if (!alive) return;
        alive = false;
        closeEditor(); dialogCleanup(); dialogCleanup = () => {};
        unrender();
        subscriptions.splice(0).forEach(off => off());
        root?.replaceChildren(); root = null; value = null;
        if (instances.get(key)?.dispose === dispose) instances.delete(key);
      };
      widget = node.widgets.mount({ name: 'toggle_trigger_words', height: 100,
        defaultValue: Array.isArray(restoredTags) ? restoredTags : [], serialize: true, sendToPrompt: true,
        render(container, cell) {
          if (!alive || node.isDeleted) return;
          root = container; value = cell;
          subscriptions.push(cell.onChange(() => { if (alive) render(); }));
          render();
        }, destroy: dispose,
      });
      const names = node.widgets.names();
      const originalIndex = names.indexOf('orinalMessage');
      const tagIndex = names.indexOf('toggle_trigger_words');
      if (tagIndex > originalIndex && originalIndex >= 0)
        node.widgets.move('toggle_trigger_words', originalIndex);
      subscriptions.push(widget.on('beforeSerialize', event => {
        if (alive) event.setSerializedValue(serializeTags(current()));
      }));
      const rebuild = () => {
        closeEditor();
        const source = original.getValue();
        commit(applyHighlightTags(reconcileTags(current(), source, Boolean(controls[0].getValue()),
          controls[1].getValue(), strengthAllowed()), highlightedWords));
      };
      subscriptions.push(controls[0].on('change', () => {
        closeEditor();
        if (original.getValue()) rebuild();
      }), controls[2].on('change', rebuild));
      subscriptions.push(controls[1].on('change', active => {
        closeEditor();
        if (!current()) return;
        change(next => next.forEach(tag => {
          tag.active = active;
          if (!Boolean(controls[0].getValue()) && Array.isArray(tag.items))
            tag.items.forEach(item => { item.active = active; });
        }));
        commit(applyHighlightTags(current(), highlightedWords));
      }));
      instances.set(key, { node, dispose, restore(widgetsValues) {
        if (!alive || node.isDeleted) return false;
        const names = node.widgets.names();
        const projection = readSavedTriggerWidgets(widgetsValues,
          names.indexOf('toggle_trigger_words'), names.indexOf('orinalMessage'));
        if (projection.restoreTags) commit(projection.tags);
        if (projection.restoreMessage) original.setValue(projection.message);
        commit(applyHighlightTags(current(), highlightedWords));
        return projection.restoreTags || projection.restoreMessage;
      }, update(message) {
        if (!alive || node.isDeleted) return false;
        // Native stores the original message before attempting reconciliation.
        original.setValue(message);
        closeEditor();
        const next = reconcileTags(current(), message, Boolean(controls[0].getValue()),
          controls[1].getValue(), strengthAllowed());
        commit(applyHighlightTags(next, highlightedWords));
        return true;
      }, highlight(words) {
        if (!alive || node.isDeleted) return false;
        const wordsArray = Array.isArray(words) ? words : words ? [words] : [];
        highlightedWords = collectHighlightTokens(wordsArray);
        commit(applyHighlightTags(current(), highlightedWords));
        return true;
      } });
      render();
    });
    builder.onRemoved(disposeRemoved);
  });
  let offDelivery;
  try {
    offDelivery = comfy.backend.on('trigger_word_update', detail => {
    if (removed) return;
    const { id, graph_id: graphId, message } = detail;
    const root = comfy.graph.root();
    const scope = [root, ...comfy.graph.subgraphs()].find(graph => graph?.id === graphId) ?? root;
    const numericId = typeof id === 'string' ? Number(id) : id;
    const node = scope?.node(String(Number.isNaN(numericId) ? id : numericId));
    if (!node || node.isDeleted || node.comfyClass !== TYPE) {
      console.warn('Node not found or not a TriggerWordToggle:', id);
      return;
    }
    instances.get(keyOf(node))?.update(message);
    });
  } catch (error) {
    removed = true;
    offDefinition();
    [...instances.values()].forEach(state => state.dispose());
    throw error;
  }
  return {
    // Caller must provide the saved values for this exact addressable node.
    // No speculative onConfigure/id queue or mutation of another node.
    restore(node, widgetsValues) {
      return !removed && !node.isDeleted && instances.get(keyOf(node))?.restore(widgetsValues) || false;
    },
    update(node, message) { return !removed && !node.isDeleted && instances.get(keyOf(node))?.update(message) || false; },
    highlight(node, words) { return !removed && !node.isDeleted && instances.get(keyOf(node))?.highlight(words) || false; },
    dispose() { if (removed) return; removed = true; offDelivery(); offDefinition(); [...instances.values()].forEach(state => state.dispose()); },
  };
}
