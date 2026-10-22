import { comfy } from '/comfy/api/v2.js';
import { NodeTypesString } from './constants.js';
import { LABEL_DEFAULTS, layoutLabel, drawLabel } from './label_drawing.js';
import { changedNode } from './base_node.js';
// Imported for their registrations, which every node type must receive before this
// pack's `define` calls run (extendEveryNodeType in base_node.js).
import './menu_queue_node.js';
import './feature_import_individual_nodes.js';

// Label owns its text, typography, sizing and rotation. The host only supplies
// a bounded drawing surface and declarative node presentation.
const TYPE = NodeTypesString.LABEL;
const records = new Map();
const keyFor = (node) => JSON.stringify([node.graphId, node.id]);
const measurement = new OffscreenCanvas(1, 1).getContext('2d');

// `title`: the new title when a change event carries it; otherwise the node's own.
function refresh(node, title = node.getTitle()) {
  const key = keyFor(node);
  let record = records.get(key);
  if (!record) {
    record = { properties: undefined, layout: undefined, surface: undefined };
    records.set(key, record);
  }
  const properties = { ...LABEL_DEFAULTS, ...node.getProperties() };
  const layout = layoutLabel(title, properties, measurement);
  record.properties = properties;
  record.layout = layout;
  if (!record.surface) {
    record.surface = node.canvas({
      bounds: layout.bounds,
      draw(context) { drawLabel(context, record.layout, record.properties); },
    });
  } else {
    record.surface.setBounds(layout.bounds);
  }
  const previous = node.getSize();
  if (previous.width !== layout.width || previous.height !== layout.height) {
    node.setSize({ width: layout.width, height: layout.height });
  }
}

function initialize(node) {
  for (const [name, value] of Object.entries(LABEL_DEFAULTS)) {
    if (node.getProperty(name) === undefined) node.setProperty(name, value);
  }
  node.setCollapsed(false);
  refresh(node);
}

function remove(node) {
  const key = keyFor(node);
  const record = records.get(key);
  record?.dialog?.close();
  record?.surface?.remove();
  records.delete(key);
}

function showProperties(node) {
  const record = records.get(keyFor(node));
  if (!record) return;
  record.dialog?.close();
  record.dialog = comfy.ui.showDialog({
    key: `rgthree.label.${node.graphId}.${node.id}`,
    title: 'Label properties',
    render(container) {
      const addField = (name, value, kind, apply) => {
        const row = document.createElement('label');
        const caption = document.createElement('span');
        caption.textContent = name;
        const input = document.createElement(kind === 'multiline' ? 'textarea' : kind === 'align' ? 'select' : 'input');
        if (kind === 'align') {
          for (const alignment of ['left', 'center', 'right']) {
            const option = document.createElement('option');
            option.value = alignment;
            option.textContent = alignment;
            input.appendChild(option);
          }
        } else if (kind !== 'multiline') input.type = kind;
        input.value = String(value ?? '');
        input.addEventListener('change', () => {
          const next = kind === 'number' ? Number(input.value) : input.value;
          if (kind === 'number' && !Number.isFinite(next)) return;
          apply(next);
          refresh(node);
        });
        row.appendChild(caption);
        row.appendChild(input);
        container.appendChild(row);
      };
      addField('Title', node.getTitle(), 'multiline', (value) => node.setTitle(value));
      const properties = { ...LABEL_DEFAULTS, ...node.getProperties() };
      for (const [name, defaultValue] of Object.entries(LABEL_DEFAULTS)) {
        const kind = name === 'textAlign' ? 'align' : typeof defaultValue === 'number' ? 'number' : 'text';
        addField(name, properties[name], kind, (value) => node.setProperty(name, value));
      }
    },
  });
}

// Extensions must be registered before defining the type so their edit hooks
// are installed on the generated node class.
comfy.defs.extend(TYPE, (builder) => {
  builder.onDoubleClick(showProperties);
  builder.addMenuItem({ label: 'Edit label', run: showProperties });
});
comfy.defs.define({
  type: TYPE,
  title: TYPE,
  category: 'rgthree',
  description: 'Floating text annotation. Double-click to edit its title and properties.',
  execution: 'frontend',
  presentation: { chrome: 'none', resizable: false, collapsible: false, pinnedInteraction: 'pass-through' },
  onCreated(node, event) {
    // Graph loading adds nodes before configuring their saved state. The
    // worker receives that earlier snapshot asynchronously; writing defaults
    // here would overwrite the properties already restored on the host.
    if (!event?.loading) initialize(node);
  },
  onConfigured: initialize,
  onPropertyChanged(node) { if (records.has(keyFor(node))) refresh(node); },
  onRemoved: remove,
});
// `refresh` reads the node through its handle (getProperties, getSize, canvas).
// `changedNode` hands back that handle even where the event carries a plain copy of the
// node (host stack r3), where revisions 4 and 5 threw `getProperties is not a function`.
// The new title comes from the event: sandbox guest c6b97a15 does not update its copy of
// the node for a change made in the host, so `getTitle()` there still reads the old one.
comfy.onNodeChanged((event) => {
  if (event.property !== 'title' || event.node?.type !== TYPE) return;
  const node = changedNode(event);
  if (node) refresh(node, typeof event.to === 'string' ? event.to : node.getTitle());
}, { scope: 'document' });
