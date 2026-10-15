// Owned loader mount. Existing catalogue math stays byte-identical.
import { createCatalogueSelection, normalizeRows } from './catalogue_selection.js';

// Literal pinned widget commit semantics; admitted row bounds stay in the helper.
export function commitStrengthText(value) {
  let parsedValue = parseFloat(value);
  if (isNaN(parsedValue)) parsedValue = 1.0;
  return parsedValue.toFixed(2);
}

export function registerRowEditor(comfy, { type, prefix, lifecycle }) {
  const instances = new Map();
  let registrationAlive = true;
  const keyOf = node => JSON.stringify([node.graphId, node.id]);
  const off = comfy.defs.extend(type, definition => {
    definition.onCreated(node => {
      if (!registrationAlive || node.isDeleted) return;
      const key = keyOf(node);
      instances.get(key)?.dispose();
      const previous = node.widgets.get('loras');
      const initial = normalizeRows(previous?.getValue());
      const extra = lifecycle(node, initial);
      if (previous) node.widgets.remove('loras');
      let alive = true, root = null, cell = null, widget = null;
      let controller = null, unsubscribeCell = null, unsubscribeController = null;
      let loading = false, error = null, query = '', refreshGeneration = 0;
      const listeners = [];
      const releaseListeners = () => listeners.splice(0).forEach(off => off());
      const read = () => widget ? widget.getValue() : cell ? cell.get() : initial;
      const write = value => {
        if (!alive || node.isDeleted) throw new Error('LoRA editor is disposed');
        if (widget) widget.setValue(value);
        else if (cell) cell.set(value);
        else throw new Error('LoRA widget is not mounted');
        extra.rowsChanged(value);
      };
      function perform(action) {
        if (!alive || node.isDeleted) return;
        try { error = null; action(); }
        catch (failure) { error = String(failure.message ?? failure); }
        render();
      }
      function indexOf(name) {
        const index = controller.snapshot().findIndex(row => row.name === name);
        if (index < 0) throw new Error('LoRA row no longer exists');
        return index;
      }
      async function refresh() {
        if (!alive || !controller) return false;
        const ticket = ++refreshGeneration;
        loading = true; error = null; render();
        try { return await controller.refresh(); }
        catch (failure) { if (alive && ticket === refreshGeneration) error = String(failure.message ?? failure); return false; }
        finally { if (alive && ticket === refreshGeneration) { loading = false; render(); } }
      }
      function render() {
        if (!alive || !root || !controller || node.isDeleted) return;
        releaseListeners(); root.replaceChildren();
        const doc = root.ownerDocument;
        function listen(element, event, callback) {
          element.addEventListener(event, callback);
          listeners.push(() => element.removeEventListener(event, callback));
        }
        function text(parent, tag, value) {
          const element = doc.createElement(tag); element.textContent = value; parent.append(element); return element;
        }
        function button(parent, label, name, action) {
          const element = text(parent, 'button', label); element.type = 'button';
          element.setAttribute('aria-label', name);
          listen(element, 'click', () => perform(action)); return element;
        }
        text(root, 'strong', 'LoRAs');
        let rows;
        try { rows = controller.snapshot(); }
        catch (failure) {
          error = String(failure.message ?? failure);
          text(root, 'p', error).setAttribute('role', 'status');
          return;
        }
        const search = doc.createElement('input'); search.type = 'search';
        search.setAttribute('aria-label', prefix + '.search'); search.setAttribute('value', query); root.append(search);
        const choices = doc.createElement('div'); root.append(choices);
        let choiceListeners = [];
        function searchChoices() {
          choiceListeners.splice(0).forEach(off => off()); choices.replaceChildren();
          try {
            for (const name of controller.search(query).slice(0, 128)) {
              const element = text(choices, 'button', name); element.type = 'button';
              element.setAttribute('aria-label', prefix + '.add.' + name);
              const clicked = () => perform(() => controller.add(name));
              element.addEventListener('click', clicked);
              choiceListeners.push(() => element.removeEventListener('click', clicked));
            }
          } catch (failure) { error = String(failure.message ?? failure); }
        }
        listeners.push(() => choiceListeners.splice(0).forEach(off => off()));
        listen(search, 'input', () => { query = search.value; searchChoices(); });
        button(root, 'Refresh catalogue', prefix + '.refresh', () => { void refresh(); }).disabled = loading;
        for (const row of rows) {
          const line = doc.createElement('div'); root.append(line);
          const choose = button(line, row.name, prefix + '.select.' + row.name, () => controller.select(row.name));
          choose.setAttribute('aria-pressed', String(Boolean(row.selected)));
          const active = button(line, row.active ? 'Active' : 'Inactive', prefix + '.active.' + row.name,
            () => controller.update(indexOf(row.name), { active: !controller.snapshot()[indexOf(row.name)].active }));
          active.setAttribute('role', 'switch'); active.setAttribute('aria-checked', String(Boolean(row.active)));
          function strength(field, label) {
            const input = doc.createElement('input'); input.type = 'text';
            input.setAttribute('aria-label', label + '.' + row.name);
            input.setAttribute('value', Number(row[field]).toFixed(2)); line.append(input);
            listen(input, 'change', () => perform(() => {
              const value = commitStrengthText(input.value);
              controller.update(indexOf(row.name), { [field]: value });
            }));
          }
          strength('strength', prefix + '.strength');
          const expanded = button(line, row.expanded ? 'Collapse CLIP' : 'Expand CLIP', prefix + '.expand.' + row.name,
            () => controller.update(indexOf(row.name), { expanded: !controller.snapshot()[indexOf(row.name)].expanded }));
          expanded.setAttribute('aria-expanded', String(Boolean(row.expanded)));
          if (row.expanded) strength('clipStrength', prefix + '.clipStrength');
          const move = direction => {
            const from = indexOf(row.name), to = from + direction;
            if (to >= 0 && to < controller.snapshot().length) controller.move(from, to);
          };
          button(line, 'Move up', prefix + '.up.' + row.name, () => move(-1)).disabled = rows[0].name === row.name;
          button(line, 'Move down', prefix + '.down.' + row.name, () => move(1)).disabled = rows[rows.length - 1].name === row.name;
          button(line, 'Remove', prefix + '.remove.' + row.name, () => controller.remove(indexOf(row.name)));
        }
        const status = text(root, 'p', error ?? ''); status.setAttribute('role', 'status');
        searchChoices();
      }
      function restore() {
        if (!alive || !controller) return;
        // Validate authoritative workflow restoration; never replace with defaults on corruption.
        try { controller.snapshot(); error = null; }
        catch (failure) { error = String(failure.message ?? failure); }
        render();
      }
      function dispose() {
        if (!alive) return;
        alive = false; ++refreshGeneration;
        extra.dispose();
        releaseListeners(); unsubscribeCell?.(); unsubscribeController?.();
        unsubscribeCell = unsubscribeController = null;
        controller?.dispose(); root?.replaceChildren(); root = cell = null;
        if (instances.get(key)?.dispose === dispose) instances.delete(key);
      }
      widget = node.widgets.mount({ name: 'loras', height: 420, defaultValue: initial,
        serialize: true, sendToPrompt: true,
        render(container, value) {
          if (!alive || node.isDeleted) return;
          root = container;
          if (cell !== value) {
            unsubscribeCell?.(); cell = value;
            unsubscribeCell = cell.onChange(restore);
          }
          if (!controller) {
            controller = createCatalogueSelection(comfy, { read, write });
            unsubscribeController = controller.onChange(render);
            void refresh();
          }
          restore();
        }, destroy: dispose });
      extra.attach(widget, dispose);
      instances.set(key, { node, restore() { extra.restore(); restore(); }, dispose });
    });
    definition.onConfigured(node => { instances.get(keyOf(node))?.restore(); });
    definition.onRemoved(node => {
      const instance = instances.get(keyOf(node));
      if (instance && (instance.node === node || instance.node.isDeleted)) instance.dispose();
    });
  });
  return () => {
    if (!registrationAlive) return;
    registrationAlive = false; off(); [...instances.values()].forEach(instance => instance.dispose());
  };
}
