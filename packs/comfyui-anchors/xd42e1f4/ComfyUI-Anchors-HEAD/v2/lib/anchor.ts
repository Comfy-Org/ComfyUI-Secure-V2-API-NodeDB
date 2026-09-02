import { comfy } from '/comfy/api/v2.js';

const ANCHOR_TYPE = '⚓ Anchor';
let activeAnchorId: string | undefined;

function anchors() {
  return comfy.graph.nodesOfType(ANCHOR_TYPE);
}

function currentAnchorIndex(items: ReturnType<typeof anchors>) {
  const selected = comfy.graph.selection().find((node) => node.type === ANCHOR_TYPE);
  const current = selected ?? items.find((node) => node.id === activeAnchorId);
  return Math.max(
    0,
    items.findIndex((node) => current && comfy.sameEntity(node, current)),
  );
}

function navigate(direction: -1 | 1) {
  const items = anchors();
  if (items.length < 1) return;
  const index = currentAnchorIndex(items);
  const target = items[(index + direction + items.length) % items.length];
  activeAnchorId = target.id;
  comfy.graph.centerOn(target);
  comfy.graph.select([target]);
}

comfy.defs.define({
  type: ANCHOR_TYPE,
  title: ANCHOR_TYPE,
  category: 'utils',
  execution: 'frontend',
  widgets: [
    { type: 'text', name: 'waypoint', value: '' },
    { type: 'number', name: 'waypoint_x', value: 0, options: { precision: 0 } },
    { type: 'number', name: 'waypoint_y', value: 0, options: { precision: 0 } },
  ],
  onCreated(node) {
    node.setSerializeWidgets(true);
    const black = comfy.defs.nodeColor('black');
    const yellow = comfy.defs.nodeColor('yellow');
    if (black) node.setColor(black.color);
    if (yellow) node.setBgColor(yellow.bgColor);
  },
  onRemoved(node) {
    if (node.id === activeAnchorId) activeAnchorId = undefined;
  },
});

comfy.onNodeMoved(({ node, position }) => {
  if (node.type !== ANCHOR_TYPE) return;
  node.widgets.get('waypoint_x')?.setValue(position.x);
  node.widgets.get('waypoint_y')?.setValue(position.y);
});

comfy.onWorkflowLoaded(() => {
  activeAnchorId = undefined;
});

comfy.commands.register({
  id: 'drjkl.anchors.previous',
  label: 'Previous anchor',
  keybinding: { key: 'a' },
  scope: 'canvas',
  run: () => navigate(-1),
});

comfy.commands.register({
  id: 'drjkl.anchors.next',
  label: 'Next anchor',
  keybinding: { key: 'd' },
  scope: 'canvas',
  run: () => navigate(1),
});
