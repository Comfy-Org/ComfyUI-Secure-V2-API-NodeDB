import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';


function check(condition, message) {
  if (!condition) throw new Error(message);
}

class FakeWidget {
  constructor(definition) {
    this.name = definition.name;
    this.value = definition.value;
    this.writes = [];
  }

  getValue() { return this.value; }
  setValue(value) {
    this.value = value;
    this.writes.push(value);
  }
}

let definition;
let movedListener;
let workflowListener;
let graphNodes = [];
let selected = [];
const commands = new Map();
const centered = [];
const selections = [];

const comfy = {
  sameEntity(left, right) {
    return Boolean(left && right && left.id === right.id && left.type === right.type);
  },
  defs: {
    define(value) { definition = value; },
    nodeColor(name) {
      const colors = {
        black: { color: '#black', bgColor: '#black-bg', groupColor: '#black-group' },
        cyan: { color: '#cyan', bgColor: '#cyan-bg', groupColor: '#cyan-group' },
        yellow: { color: '#yellow', bgColor: '#yellow-bg', groupColor: '#yellow-group' },
      };
      return colors[name];
    },
  },
  graph: {
    nodesOfType(type) { return graphNodes.filter((node) => node.type === type); },
    selection() { return selected; },
    centerOn(node) { centered.push(node.id); },
    select(nodes) {
      selected = [...nodes];
      selections.push(nodes.map((node) => node.id));
    },
  },
  commands: {
    register(value) { commands.set(value.id, value); },
  },
  onNodeMoved(listener) {
    movedListener = listener;
    return () => {};
  },
  onWorkflowLoaded(listener) {
    workflowListener = listener;
    return () => {};
  },
};

const context = vm.createContext({ console });
const facade = new vm.SyntheticModule(
  ['comfy'],
  function initialize() { this.setExport('comfy', comfy); },
  { context, identifier: '/comfy/api/v2.js' },
);
const sourcePath = path.resolve(process.env.TARGET_JS);
const source = fs.readFileSync(sourcePath, 'utf8');
const module = new vm.SourceTextModule(source, { context, identifier: sourcePath });
await module.link(async (specifier) => {
  if (specifier === '/comfy/api/v2.js') return facade;
  throw new Error(`unexpected import: ${specifier}`);
});
await module.evaluate();

check(definition?.type === '⚓ Anchor', 'wrong frontend node type');
check(definition.title === '⚓ Anchor', 'wrong frontend node title');
check(definition.category === 'utils', 'wrong frontend node category');
check(definition.execution === 'frontend', 'node is not frontend-only');
check(
  JSON.stringify(definition.widgets.map(({ type, name, value }) => ({ type, name, value }))) ===
    JSON.stringify([
      { type: 'text', name: 'waypoint', value: '' },
      { type: 'number', name: 'waypoint_x', value: 0 },
      { type: 'number', name: 'waypoint_y', value: 0 },
    ]),
  'wrong saved widget census',
);
check(definition.widgets[1].options.precision === 0, 'x is not an integer widget');
check(definition.widgets[2].options.precision === 0, 'y is not an integer widget');
check(typeof movedListener === 'function', 'movement lifecycle not registered');
check(typeof workflowListener === 'function', 'workflow lifecycle not registered');
check(commands.size === 2, 'wrong command census');

const previous = commands.get('drjkl.anchors.previous');
const next = commands.get('drjkl.anchors.next');
check(previous?.keybinding?.key === 'a', 'previous shortcut changed');
check(next?.keybinding?.key === 'd', 'next shortcut changed');
check(previous.scope === 'canvas' && next.scope === 'canvas', 'shortcuts are not canvas scoped');

function makeNode(id, type = '⚓ Anchor') {
  const widgets = new Map(
    definition.widgets.map((widget) => [widget.name, new FakeWidget(widget)]),
  );
  return {
    id,
    type,
    color: undefined,
    background: undefined,
    serializeWidgets: false,
    widgets: { get(name) { return widgets.get(name); } },
    setSerializeWidgets(value) { this.serializeWidgets = value; },
    setColor(value) { this.color = value; },
    setBgColor(value) { this.background = value; },
  };
}

const first = makeNode('1');
const second = makeNode('2');
const third = makeNode('3');
graphNodes = [first, second, third];
for (const node of graphNodes) definition.onCreated(node);
check(graphNodes.every((node) => node.serializeWidgets), 'widgets are not serialized');
check(graphNodes.every((node) => node.color === '#black'), 'default anchor color changed');
check(graphNodes.every((node) => node.background === '#yellow-bg'), 'default anchor background changed');

movedListener({ node: second, position: { x: 123.5, y: -44 } });
check(second.widgets.get('waypoint_x').getValue() === 123.5, 'x position not committed');
check(second.widgets.get('waypoint_y').getValue() === -44, 'y position not committed');
const foreign = makeNode('foreign', 'Other');
movedListener({ node: foreign, position: { x: 9, y: 8 } });
check(foreign.widgets.get('waypoint_x').writes.length === 0, 'foreign node was changed');

selected = [first];
next.run();
check(centered.at(-1) === '2', 'd did not advance to the next anchor');
check(JSON.stringify(selections.at(-1)) === JSON.stringify(['2']), 'next anchor not selected');
next.run();
check(centered.at(-1) === '3', 'second d did not advance');
previous.run();
check(centered.at(-1) === '2', 'a did not navigate backward');

selected = [foreign];
next.run();
check(centered.at(-1) === '3', 'non-anchor selection lost the active anchor');
workflowListener();
selected = [foreign];
next.run();
check(centered.at(-1) === '2', 'workflow reset did not restart from the first anchor');

graphNodes = [first];
selected = [];
next.run();
check(centered.at(-1) === '1', 'single anchor did not recenter');
const beforeEmpty = centered.length;
graphNodes = [];
previous.run();
check(centered.length === beforeEmpty, 'empty graph attempted navigation');

for (const name of ['window', 'parent', 'document', 'app', 'LiteGraph', 'fetch']) {
  check(vm.runInContext(`typeof ${name}`, context) === 'undefined', `${name} leaked`);
}

console.log('comfyui-anchors frontend harness: PASS');
