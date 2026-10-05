import assert from "node:assert/strict";
import fs from "node:fs";

const sourcePath = new URL("../js/connection_helper.js", import.meta.url);
let source = fs.readFileSync(sourcePath, "utf8");
source = source.replace(
  'import { comfy } from "/comfy/api/v2.js";',
  "const comfy = globalThis.__connectionHelperComfy;",
);

let nextLink = 1;

class Collection {
  constructor(items = []) { this.items = items; }
  all() { return [...this.items]; }
  byName(name) { return this.items.find((item) => item.name === name); }
  byId(id) { return this.items.find((item) => item.id === id); }
  at(index) { return this.items[index]; }
  add(name, type, options = {}) {
    const item = new InputSlot(name, type, options);
    this.items.push(item);
    return item;
  }
}

class InputSlot {
  constructor(name, type, options = {}) {
    this.id = `input:${name}:${Math.random()}`;
    this.name = name;
    this.type = type;
    this.isWidgetInput = Boolean(options.widget);
    this._widgetConfig = options.widgetConfig;
    this._link = options.link;
  }
  get isConnected() { return Boolean(this._link); }
  link() { return this._link; }
  widgetConfig() { return this._widgetConfig; }
}

class OutputSlot {
  constructor(owner, name, type) {
    this.owner = owner;
    this.id = `output:${owner.id}:${name}`;
    this.name = name;
    this.type = type;
    this._links = [];
  }
  get isConnected() { return this._links.length > 0; }
  links() { return [...this._links]; }
  connectTo(targetNodeId, inputRef) {
    const target = this.owner.graph.node(targetNodeId);
    const input = target?.inputs.byId(inputRef) ?? target?.inputs.byName(inputRef);
    if (!input) return undefined;
    const link = {
      id: `link:${nextLink++}`,
      sourceNodeId: this.owner.id,
      sourceSlotId: this.id,
      sourceIndex: this.owner.outputs.all().indexOf(this),
      targetNodeId,
      targetSlotId: input.id,
      targetIndex: target.inputs.all().indexOf(input),
      type: this.type,
    };
    input._link = link;
    this._links.push(link);
    return link;
  }
}

class Node {
  constructor(id, x, y, width = 100, height = 100) {
    this.id = id;
    this.type = `type:${id}`;
    this.graphId = "graph";
    this.position = { x, y };
    this.size = { width, height };
    this.inputs = new Collection();
    this.outputs = new Collection();
    const widgets = [];
    this.widgets = {
      add(name) { const item = { name }; widgets.push(item); return item; },
      get(name) { return widgets.find((item) => item.name === name); },
    };
  }
  getPosition() { return { ...this.position }; }
  getSize() { return { ...this.size }; }
  addInput(name, type, options = {}) {
    const input = new InputSlot(name, type, options);
    this.inputs.items.push(input);
    return input;
  }
  addOutput(name, type) {
    const output = new OutputSlot(this, name, type);
    this.outputs.items.push(output);
    return output;
  }
}

class Graph {
  constructor(nodes) {
    this._nodes = nodes;
    this.batchCount = 0;
    for (const node of nodes) node.graph = this;
  }
  nodes() { return [...this._nodes]; }
  node(id) { return this._nodes.find((node) => node.id === id); }
  batch(callback) { this.batchCount += 1; return callback(); }
}

let menu;
let stopped = 0;
const comfy = {
  graph: undefined,
  defs: {
    extend(predicate, configure) {
      assert.equal(predicate({}), true);
      configure({ addMenuItem(item) { menu = item; } });
      return () => { stopped += 1; };
    },
  },
};
globalThis.__connectionHelperComfy = comfy;

const encoded = Buffer.from(`${source}\n//# sourceURL=connection-helper-v2.mjs`).toString("base64");
const mod = await import(`data:text/javascript;base64,${encoded}`);

{
  const target = new Node("target", 500, 0);
  const nearest = new Node("nearest", 300, 0);
  const far = new Node("far", -1000, 0);
  const graph = new Graph([target, nearest, far]);
  assert.equal(mod.nearestNode(graph, target), nearest);
  nearest.position.x = 2000;
  assert.equal(mod.nearestNode(graph, target), undefined);
}

{
  const sourceFar = new Node("source-far", 0, 200);
  const sourceNear = new Node("source-near", 300, 0);
  const sourceRight = new Node("source-right", 900, 0);
  const target = new Node("target", 600, 0);
  const intFar = sourceFar.addOutput("int-far", "INT");
  const intNear = sourceNear.addOutput("int-near", "INT");
  sourceNear.addOutput("string", "STRING");
  sourceRight.addOutput("ignored", "FLOAT");
  const inputInt = target.addInput("amount", "INT");
  target.addInput("second_int", "INT");
  const inputString = target.addInput("text", "STRING");
  const graph = new Graph([sourceFar, sourceNear, sourceRight, target]);
  assert.equal(mod.connectNearestInputs(graph, target), 2);
  assert.equal(inputInt.link().sourceSlotId, intNear.id);
  assert.equal(inputString.link().sourceNodeId, sourceNear.id);
  assert.equal(target.inputs.byName("second_int").isConnected, false);
  assert.equal(intFar.isConnected, false);
  assert.equal(graph.batchCount, 1);
}

{
  const origin = new Node("origin", 0, 0);
  const source = new Node("source", 200, 0);
  const target = new Node("target", 250, 0);
  const outA = origin.addOutput("a", "INT");
  const outB = origin.addOutput("b", "FLOAT");
  const sourcePlain = source.addInput("plain", "INT");
  const sourceWidget = source.addInput("strength", "FLOAT", {
    widget: "strength",
    widgetConfig: { type: "FLOAT", options: { min: 0, max: 1 } },
  });
  target.addInput("plain", "INT");
  target.widgets.add("strength");
  const graph = new Graph([origin, source, target]);
  outA.connectTo(source.id, sourcePlain.id);
  outB.connectTo(source.id, sourceWidget.id);
  assert.equal(mod.copyNearestInputs(graph, target), 2);
  assert.equal(target.inputs.byName("plain").link().sourceNodeId, origin.id);
  const converted = target.inputs.byName("strength");
  assert.equal(converted.isWidgetInput, true);
  assert.deepEqual(converted.widgetConfig(), { type: "FLOAT", options: { min: 0, max: 1 } });
  assert.equal(graph.batchCount, 1);
}

{
  const upstream = new Node("upstream", 0, 0);
  const source = new Node("source", 200, 0);
  const target = new Node("target", 250, 0);
  const downstream = new Node("downstream", 600, 0);
  const sourceIn = source.addInput("in", "INT");
  target.addInput("in", "INT");
  const downstreamIn = downstream.addInput("sink", "INT");
  const graph = new Graph([upstream, source, target, downstream]);
  upstream.addOutput("feed", "INT").connectTo(source.id, sourceIn.id);
  source.addOutput("result", "INT").connectTo(downstream.id, downstreamIn.id);
  target.addOutput("result", "INT");
  assert.equal(mod.copyNearestConnections(graph, target), 2);
  assert.equal(target.inputs.byName("in").isConnected, true);
  assert.equal(target.outputs.byName("result").links()[0].targetNodeId, downstream.id);
  assert.equal(graph.batchCount, 1);
  assert.equal(mod.copyNearestConnections(graph, target), 0);
  assert.equal(graph.batchCount, 1);
}

assert.equal(menu.label, "Connection Helper");
const menuNode = new Node("menu", 0, 0);
const menuGraph = new Graph([menuNode]);
comfy.graph = menuGraph;
const children = menu.items(menuNode);
assert.deepEqual(children.map((item) => item.label), [
  "Connect nearest compatible inputs",
  "Copy inputs from nearest node",
  "Copy all connections from nearest node",
]);
for (const item of children) item.run();
const install = mod.installConnectionHelper(comfy);
assert.equal(mod.installConnectionHelper(comfy), install);
install.dispose();
install.dispose();
assert.equal(stopped, 1);

console.log("connection helper frontend harness: PASS");
