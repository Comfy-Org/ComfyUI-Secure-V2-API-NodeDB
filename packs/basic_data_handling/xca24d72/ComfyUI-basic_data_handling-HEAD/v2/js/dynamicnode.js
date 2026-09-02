import { comfy } from "/comfy/api/v2.js";
import { DYNAMIC_NODES } from "./dynamic-config.js";


const stateByNode = new Map();


function stateFor(node) {
  let state = stateByNode.get(node.id);
  if (!state) {
    state = { processing: false, restoring: false, listeners: new Map() };
    stateByNode.set(node.id, state);
  }
  return state;
}


function suffixFor(name, template) {
  if (!name.startsWith(template.base)) return undefined;
  const suffix = name.slice(template.base.length);
  if (template.dynamic === "number") {
    return /^\d+$/.test(suffix) ? suffix : undefined;
  }
  return /^[a-zA-Z]$/.test(suffix) ? suffix : undefined;
}


function nameFor(template, index) {
  if (template.dynamic === "letter") {
    return `${template.base}${String.fromCharCode(97 + index)}`;
  }
  return `${template.base}${index}`;
}


function templateFor(name, templates) {
  for (const template of templates) {
    const suffix = suffixFor(name, template);
    if (suffix !== undefined) return { template, suffix };
  }
  return undefined;
}


function defaultValue(template) {
  if (template.options.default !== undefined) return template.options.default;
  if (template.widget === "number") return 0;
  if (template.widget === "toggle") return false;
  return "";
}


function widgetDefinition(template, name, value = defaultValue(template)) {
  const options = { ...template.options };
  if (template.widget === "combo" && !Array.isArray(options.values)) {
    options.values = [value];
  }
  return { type: template.widget, name, value, options };
}


function clearListener(node, name) {
  const state = stateFor(node);
  state.listeners.get(name)?.();
  state.listeners.delete(name);
}


function watchWidget(node, name, templates) {
  const state = stateFor(node);
  if (state.listeners.has(name)) return;
  const widget = node.widgets.get(name);
  if (!widget) return;
  const release = widget.on("change", () => reconcile(node, templates));
  state.listeners.set(name, release);
}


function addTemplateSlot(node, template, name) {
  if (template.widget && !node.widgets.get(name)) {
    node.widgets.add(widgetDefinition(template, name));
  }
  const config = template.widget
    ? { widget: name, widgetConfig: { type: template.type, options: template.options } }
    : {};
  node.inputs.add(name, template.type, config);
}


function removeSlot(node, slot, template) {
  if (template.widget) {
    clearListener(node, slot.name);
    node.widgets.remove(slot.name);
  }
  node.inputs.remove(slot.id);
}


function itemMap(node, templates) {
  const result = new Map();
  for (const slot of node.inputs.all()) {
    const match = templateFor(slot.name, templates);
    if (!match) continue;
    let item = result.get(match.suffix);
    if (!item) {
      item = { suffix: match.suffix, slots: [], active: false };
      result.set(match.suffix, item);
    }
    const widget = match.template.widget ? node.widgets.get(slot.name) : undefined;
    const value = widget?.getValue();
    const activeWidget = match.template.widget
      && (value ?? defaultValue(match.template)) !== defaultValue(match.template);
    item.slots.push({ slot, template: match.template });
    item.active ||= Boolean(slot.isConnected || activeWidget);
  }
  return result;
}


function sortedItems(items, dynamic) {
  return [...items.values()].sort((left, right) => {
    if (dynamic === "number") return Number(left.suffix) - Number(right.suffix);
    return left.suffix.localeCompare(right.suffix);
  });
}


function removeExtraEmptyItems(node, templates) {
  const items = sortedItems(itemMap(node, templates), templates[0].dynamic);
  const empty = items.filter((item) => !item.active);
  if (empty.length <= 1) return false;
  const activeCount = items.length - empty.length;
  const keep = activeCount === 0 ? empty[0] : empty.at(-1);
  for (const item of empty) {
    if (item === keep) continue;
    for (const { slot, template } of item.slots) removeSlot(node, slot, template);
  }
  return true;
}


function renameWidget(node, template, oldName, newName) {
  const widget = node.widgets.get(oldName);
  const value = widget?.getValue() ?? defaultValue(template);
  clearListener(node, oldName);
  if (widget) node.widgets.remove(oldName);
  node.widgets.add(widgetDefinition(template, newName, value));
}


function renumber(node, templates) {
  const items = sortedItems(itemMap(node, templates), templates[0].dynamic);
  items.forEach((item, index) => {
    for (const { slot, template } of item.slots) {
      const next = nameFor(template, index);
      if (slot.name === next) continue;
      if (template.widget) renameWidget(node, template, slot.name, next);
      slot.modify({
        name: next,
        ...(template.widget
          ? { widget: next, widgetConfig: { type: template.type, options: template.options } }
          : {}),
      });
    }
  });
}


function addTrailingItem(node, templates) {
  const items = sortedItems(itemMap(node, templates), templates[0].dynamic);
  if (items.some((item) => !item.active)) return;
  if (templates[0].dynamic === "letter" && items.length >= 26) return;

  const previousNames = node.inputs.names();
  const dynamicNames = new Set(
    previousNames.filter((name) => templateFor(name, templates)),
  );
  let insertion = -1;
  previousNames.forEach((name, index) => {
    if (dynamicNames.has(name)) insertion = index;
  });
  const added = [];
  for (const template of templates) {
    const name = nameFor(template, items.length);
    addTemplateSlot(node, template, name);
    added.push(name);
  }
  const order = node.inputs.names().filter((name) => !added.includes(name));
  order.splice(insertion + 1, 0, ...added);
  node.inputs.reorder(order);
}


function attachWidgetListeners(node, templates) {
  for (const slot of node.inputs.all()) {
    const match = templateFor(slot.name, templates);
    if (!match?.template.widget) continue;
    if (!node.widgets.get(slot.name)) {
      node.widgets.add(widgetDefinition(match.template, slot.name));
      slot.modify({
        widget: slot.name,
        widgetConfig: {
          type: match.template.type,
          options: match.template.options,
        },
      });
    }
    watchWidget(node, slot.name, templates);
  }
}


function reconcile(node, templates) {
  const state = stateFor(node);
  if (state.processing || state.restoring) return;
  state.processing = true;
  try {
    attachWidgetListeners(node, templates);
    removeExtraEmptyItems(node, templates);
    renumber(node, templates);
    addTrailingItem(node, templates);
    attachWidgetListeners(node, templates);
  } finally {
    state.processing = false;
  }
}


for (const [nodeType, templates] of Object.entries(DYNAMIC_NODES)) {
  comfy.defs.extend(nodeType, (builder) => {
    builder.onCreated((node, event) => {
      const state = stateFor(node);
      state.restoring = Boolean(event.restored || event.loading);
      if (!state.restoring) reconcile(node, templates);
    });
    builder.onConfigured((node) => {
      const state = stateFor(node);
      state.restoring = false;
      reconcile(node, templates);
    });
    builder.onConnectionsChanged((node, event) => {
      if (event.side === "input") reconcile(node, templates);
    });
    builder.onRemoved((node) => {
      const state = stateByNode.get(node.id);
      for (const release of state?.listeners.values() ?? []) release();
      stateByNode.delete(node.id);
    });
  });
}
