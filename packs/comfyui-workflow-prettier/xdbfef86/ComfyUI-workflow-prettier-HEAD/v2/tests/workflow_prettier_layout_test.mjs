import assert from "node:assert/strict";

import {
  LocalUndo,
  alignNodes,
  equalizeSpacing,
  layoutCompact,
  layoutLayered,
  layoutLinear,
  layoutSortByType,
  partitionByGroup,
  runPrettify,
} from "../web/layout.js";

class Node {
  constructor(id, type, x, y, width = 100, height = 60) {
    this.id = String(id);
    this.type = type;
    this.pos = { x, y };
    this.size = { width, height };
  }
  getPosition() { return { ...this.pos }; }
  setPosition(value) { this.pos = { ...value }; }
  getSize() { return { ...this.size }; }
}

class Group {
  constructor(id, bounds) { this.id = String(id); this.bounds = { ...bounds }; }
  getBounds() { return { ...this.bounds }; }
  setBounds(value) { this.bounds = { ...value }; }
}

class Graph {
  constructor(id, nodes, links = [], groups = []) {
    this.id = id;
    this._nodes = nodes;
    this._links = links.map(([sourceNodeId, targetNodeId], index) => ({
      id: String(index + 1), sourceNodeId: String(sourceNodeId), targetNodeId: String(targetNodeId),
    }));
    this._groups = groups;
    this._selection = [];
    this.batchCount = 0;
  }
  nodes() { return [...this._nodes]; }
  node(id) { return this._nodes.find((node) => node.id === String(id)); }
  links() { return [...this._links]; }
  groups() { return [...this._groups]; }
  selection() { return [...this._selection]; }
  batch(run) { this.batchCount += 1; return run(); }
}

function noOverlap(nodes) {
  for (let left = 0; left < nodes.length; left += 1) {
    for (let right = left + 1; right < nodes.length; right += 1) {
      const a = nodes[left];
      const b = nodes[right];
      const separated = a.pos.x + a.size.width <= b.pos.x || b.pos.x + b.size.width <= a.pos.x ||
        a.pos.y + a.size.height <= b.pos.y || b.pos.y + b.size.height <= a.pos.y;
      assert.equal(separated, true, `${a.id} overlaps ${b.id}`);
    }
  }
}

const prettier = new Node("prettier", "WorkflowPrettifier", 999, 999);
const a = new Node("a", "Load", 10, 0, 80, 50);
const b = new Node("b", "Process", 20, 80, 120, 70);
const c = new Node("c", "Process", 15, 170, 90, 65);
const d = new Node("d", "Save", 30, 260, 100, 60);
const graph = new Graph("root", [prettier, a, b, c, d], [["a", "b"], ["a", "c"], ["b", "d"], ["c", "d"]]);

layoutLayered(graph, [a, b, c, d], 100, 100, { horizontalSpacing: 40, verticalSpacing: 30 });
assert.equal(a.pos.x, 100);
assert.equal(b.pos.x, c.pos.x);
assert.ok(d.pos.x > b.pos.x);
assert.notEqual(b.pos.y, c.pos.y);
assert.deepEqual(prettier.pos, { x: 999, y: 999 });

layoutLinear(graph, [a, b, c, d], 5, 7, { horizontalSpacing: 20 });
assert.deepEqual(a.pos, { x: 5, y: 7 });
assert.equal(b.pos.x, 105);
assert.equal(c.pos.y, 7);
assert.ok(d.pos.x > c.pos.x);

layoutCompact(graph, [a, b, c, d], 0, 0, { horizontalSpacing: 10, verticalSpacing: 10 });
noOverlap([a, b, c, d]);

layoutSortByType(graph, [a, b, c, d], 0, 0, { horizontalSpacing: 20, verticalSpacing: 10 });
assert.equal(b.pos.x, c.pos.x);
assert.notEqual(a.pos.x, b.pos.x);

// A cycle must remain present and converge without an infinite traversal.
const cycleA = new Node("ca", "Cycle", 0, 0);
const cycleB = new Node("cb", "Cycle", 20, 20);
const cycleGraph = new Graph("cycle", [cycleA, cycleB], [["ca", "cb"], ["cb", "ca"]]);
runPrettify(cycleGraph, { layout: "Layered (Vertical Stacks)" });
assert.ok(Number.isFinite(cycleA.pos.x) && Number.isFinite(cycleB.pos.y));

// Nested groups assign a node to the smallest containing rectangle.
const nested = new Node("nested", "Inner", 75, 75, 20, 20);
const outer = new Group("outer", { x: 0, y: 0, width: 300, height: 300 });
const inner = new Group("inner", { x: 50, y: 50, width: 100, height: 100 });
const groupedGraph = new Graph("grouped", [nested], [], [outer, inner]);
const partition = partitionByGroup(groupedGraph);
assert.deepEqual(partition.grouped.get("outer"), []);
assert.deepEqual(partition.grouped.get("inner").map((node) => node.id), ["nested"]);

const memberA = new Node("ga", "A", 20, 40);
const memberB = new Node("gb", "B", 140, 40);
const free = new Node("free", "C", 500, 500);
const group = new Group("g", { x: 0, y: 0, width: 400, height: 200 });
const layoutGroupGraph = new Graph("group-layout", [memberA, memberB, free], [["ga", "gb"], ["gb", "free"]], [group]);
runPrettify(layoutGroupGraph, {
  layout: "Layered (Vertical Stacks)", direction: "Left to Right",
  groupHandling: "Respect Groups", horizontalSpacing: 30, verticalSpacing: 20, groupPadding: 25,
});
const bounds = group.getBounds();
for (const node of [memberA, memberB]) {
  assert.ok(node.pos.x >= bounds.x && node.pos.x + node.size.width <= bounds.x + bounds.width);
  assert.ok(node.pos.y >= bounds.y && node.pos.y + node.size.height <= bounds.y + bounds.height);
}
assert.ok(free.pos.x >= bounds.x + bounds.width);

// Direction transforms preserve finite geometry and mirror order.
runPrettify(graph, { layout: "Linear", direction: "Right to Left", groupHandling: "Ignore Groups" });
assert.ok(a.pos.x > d.pos.x);
runPrettify(graph, { layout: "Linear", direction: "Top to Bottom", groupHandling: "Ignore Groups" });
assert.ok(d.pos.y > a.pos.y);
noOverlap([a, b, c, d]);

graph._selection = [a, b, c];
a.pos = { x: 0, y: 0 }; b.pos = { x: 200, y: 50 }; c.pos = { x: 500, y: 100 };
assert.equal(alignNodes(graph, "left"), true);
assert.equal(a.pos.x, b.pos.x);
assert.equal(b.pos.x, c.pos.x);
a.pos = { x: 0, y: 0 }; b.pos = { x: 200, y: 50 }; c.pos = { x: 500, y: 100 };
assert.equal(alignNodes(graph, "distributeH"), true);
assert.ok(b.pos.x > a.pos.x && c.pos.x > b.pos.x);
graph._selection = [prettier, a];
assert.equal(alignNodes(graph, "left"), false);

a.pos = { x: 0, y: 0 }; b.pos = { x: 5, y: 200 }; c.pos = { x: 300, y: 20 }; d.pos = { x: 305, y: 300 };
assert.equal(equalizeSpacing(graph, { horizontalSpacing: 50, verticalSpacing: 25 }), true);
assert.equal(b.pos.y, a.pos.y + a.size.height + 25);
assert.equal(c.pos.x, a.pos.x + Math.max(a.size.width, b.size.width) + 50);

// Undo is local to document+graph, capped, and ignores stale entities.
const undo = new LocalUndo(2);
const otherNode = new Node("a", "Load", 700, 700);
const otherGraph = new Graph("root", [otherNode]);
undo.push("doc-one", graph);
a.setPosition({ x: 1234, y: 4321 });
undo.push("doc-one", graph);
a.setPosition({ x: 4567, y: 7654 });
undo.push("doc-one", graph);
assert.equal(undo.depth("doc-one", graph), 2);
assert.equal(undo.depth("doc-two", otherGraph), 0);
assert.equal(undo.pop("doc-two", otherGraph), false);
graph._nodes = graph._nodes.filter((node) => node !== d); // stale saved id must be ignored
assert.equal(undo.pop("doc-one", graph), true);
assert.deepEqual(a.pos, { x: 4567, y: 7654 });
assert.equal(undo.pop("doc-one", graph), true);
assert.deepEqual(a.pos, { x: 1234, y: 4321 });
assert.equal(graph.batchCount, 2);
undo.clearDocument("doc-one");
assert.equal(undo.depth("doc-one", graph), 0);

console.log("workflow prettier layout behavior: PASS");
