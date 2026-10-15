// Save Image frontend source; browser/serialization/backend closure is pending.
const TYPE = 'Save Image (LoraManager)';
const keyOf = node => JSON.stringify([node.graphId, node.id]);

export function formatDate(text, date) {
  const pad = (n, len) => n.toString().padStart(len, '0');
  return text
    .replace(/yyyy/g, () => date.getFullYear().toString())
    .replace(/yy/g, () => pad(date.getFullYear() % 100, 2))
    .replace(/MM/g, () => pad(date.getMonth() + 1, 2))
    .replace(/M/g, () => (date.getMonth() + 1).toString())
    .replace(/dd/g, () => pad(date.getDate(), 2))
    .replace(/d/g, () => date.getDate().toString())
    .replace(/hh/g, () => pad(date.getHours(), 2))
    .replace(/h/g, () => date.getHours().toString())
    .replace(/mm/g, () => pad(date.getMinutes(), 2))
    .replace(/m/g, () => date.getMinutes().toString())
    .replace(/ss/g, () => pad(date.getSeconds(), 2))
    .replace(/s/g, () => date.getSeconds().toString());
}

/**
 * Synchronous like the public beforeSerialize contract and native replacement.
 * Native coercion/sanitation, alias priority and first-match behavior retained.
 * @param {*} value
 * @param {{alias: unknown, title: string, graphId?: string, id: string}[]} rows
 * @param {(row: object, name: string) => {found: boolean, value?: unknown}} readValue
 */
export function resolveFilename(value, rows, readValue, now = () => new Date()) {
  if (!value || typeof value !== 'string' || !value.includes('%')) return value;
  return value.replace(/%([^%]+)%/g, (match, text) => {
    const split = text.split('.');
    if (split.length !== 2) {
      if (split[0].startsWith('date:')) return formatDate(split[0].substring(5), now());
      if (text !== 'width' && text !== 'height')
        console.warn('[Save Image (LoraManager)] Unknown placeholder: %' + text + '%');
      return match;
    }
    let nodes = rows.filter(row => row.alias === split[0]);
    if (!nodes.length) nodes = rows.filter(row => row.title === split[0]);
    if (!nodes.length) {
      console.warn('[Save Image (LoraManager)] Node not found: ' + split[0]);
      return match;
    }
    if (nodes.length > 1)
      console.warn("[Save Image (LoraManager)] Multiple nodes matched '" + split[0] + "', using first match");
    const found = readValue(nodes[0], split[1]);
    if (!found.found) {
      console.warn("[Save Image (LoraManager)] Widget '" + split[1] + "' not found on node " + split[0]);
      return match;
    }
    return ((found.value ?? '') + '').replaceAll(/[/?<>\\:*|"\x00-\x1F\x7F]/g, '_');
  });
}

/** @param {Comfy} comfy */
function graphRows(comfy) {
  const root = comfy.graph.root();
  if (!root) return [];
  const nodes = [];
  const visited = new Set();
  for (const scope of [root, ...comfy.graph.subgraphs()]) {
    if (visited.has(scope.id)) continue;
    visited.add(scope.id);
    for (const node of scope.nodes()) nodes.push(node);
  }
  return nodes.filter(node => !node.isDeleted).map(node => ({
    graphId: node.graphId, id: node.id, alias: node.getProperty('Node name for S&R'),
    title: node.getTitle(), node,
  }));
}

/** @param {Comfy} comfy */
export function registerSaveImageExtraOutput(comfy) {
  const instances = new Map();
  let stopped = false;
  const offDefinition = comfy.defs.extend(TYPE, builder => {
    builder.onCreated(node => {
      if (stopped || node.isDeleted) return;
      const key = keyOf(node);
      instances.get(key)?.dispose();
      const filename = node.widgets.get('filename_prefix');
      if (!filename) {
        console.warn('[Save Image (LoraManager)] filename_prefix widget not found');
        return;
      }
      let alive = true;
      const subscriptions = [];
      const valid = () => alive && !stopped && !node.isDeleted;
      const dispose = () => {
        if (!alive) return;
        alive = false;
        for (const unsubscribe of subscriptions.splice(0)) unsubscribe();
        if (instances.get(key)?.dispose === dispose) instances.delete(key);
      };
      const format = node.widgets.get('file_format');
      const updateFormat = () => {
        if (!valid()) return;
        const value = format?.getValue();
        for (const [name, wanted] of [['webp_method', 'webp'], ['jpeg_subsampling', 'jpeg']]) {
          const widget = node.widgets.get(name);
          if (widget) {
            widget.setDisabled(value !== wanted);
            widget.setHidden(value !== wanted);
          }
        }
      };
      try {
        subscriptions.push(filename.on('beforeSerialize', event => {
          if (!valid()) return;
          // Native serializeValue reads the widget's live value directly.
          const value = filename.getValue();
          if (!value || typeof value !== 'string' || !value.includes('%')) {
            event.setSerializedValue(value);
            return;
          }
          const rows = graphRows(comfy);
          const projection = resolveFilename(value, rows, (row, name) => {
            const widget = row.node.widgets.get(name);
            return widget ? { found: true, value: widget.getValue() } : { found: false };
          });
          if (valid()) event.setSerializedValue(projection);
        }));
        if (format) subscriptions.push(format.on('change', updateFormat));
        subscriptions.push(filename.on('removed', dispose));
        if (format) subscriptions.push(format.on('removed', dispose));
        instances.set(key, { node, dispose });
        updateFormat();
      } catch (error) {
        dispose();
        throw error;
      }
    });
    builder.onRemoved(() => {
      // Only isDeleted is guaranteed readable once an entity is gone.
      for (const instance of [...instances.values()])
        if (instance.node.isDeleted) instance.dispose();
    });
  });
  return () => {
    if (stopped) return;
    stopped = true;
    offDefinition();
    for (const instance of [...instances.values()]) instance.dispose();
  };
}
