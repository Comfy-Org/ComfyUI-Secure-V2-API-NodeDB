import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { pathToFileURL } from "node:url";


const entry = path.resolve(process.argv[2]);
const source = fs.readFileSync(entry, "utf8");
for (const forbidden of [
  /\/scripts\/app\.js|\/scripts\/api\.js/,
  /LiteGraph|app\.graph|app\.queuePrompt/,
  /(?:^|[^A-Za-z])document\s*\./m,
  /(?:^|[^A-Za-z])window\s*\./m,
  /localStorage|indexedDB|fetch\s*\(|comfy\.backend|innerHTML/,
]) assert.doesNotMatch(source, forbidden);


class FakeWidget {
  constructor(value) { this.value = value; this.writes = []; }
  getValue() { return this.value; }
  setValue(value) { this.value = value; this.writes.push(value); }
}


class FakeNode {
  constructor(value = "stale", includeWidget = true) {
    this.widget = includeWidget ? new FakeWidget(value) : undefined;
    this.widgets = {
      get: (name) => name === "workflow_name" ? this.widget : undefined,
    };
  }
}


let documentName = "My: Workflow.json";
const rootNode = new FakeNode();
const subgraphNode = new FakeNode();
const incompleteNode = new FakeNode("stale", false);
const queries = [];
const beforeRun = new Set();
const comfy = {
  workflow: {
    current: () => documentName === undefined ? undefined : { name: documentName },
  },
  graph: {
    queryNodes(query) {
      queries.push(query);
      return [rootNode, subgraphNode, incompleteNode];
    },
  },
  queue: {
    onBeforeRun(listener) {
      beforeRun.add(listener);
      return () => beforeRun.delete(listener);
    },
  },
};


const context = vm.createContext({ console, Promise, Math, Number, Object, String, Array, Set });
const module = new vm.SourceTextModule(source, {
  context,
  identifier: pathToFileURL(entry).href,
});
await module.link(async (specifier) => {
  assert.equal(specifier, "/comfy/api/v2.js");
  const stub = new vm.SyntheticModule(["comfy"], function () {
    this.setExport("comfy", comfy);
  }, { context });
  await stub.link(() => {});
  return stub;
});
await module.evaluate();


const sanitize = module.namespace.sanitizeWorkflowName;
assert.equal(sanitize("folder/My: Flow.json"), "My_ Flow");
assert.equal(sanitize("C:\\bad<name>.json"), "C__bad_name");
assert.equal(sanitize(" ...__ "), "NO_WORKFLOW_NAME");
assert.equal(sanitize("name.JSON"), "name.JSON");
assert.equal(sanitize("bad\u0001name.json"), "bad_name");
assert.equal(sanitize("x".repeat(513)), "NO_WORKFLOW_NAME");
assert.equal(sanitize(undefined), "NO_WORKFLOW_NAME");

assert.equal(beforeRun.size, 1, "one typed pre-run listener replaces queuePrompt monkey-patching");
for (const listener of beforeRun) listener();
assert.equal(rootNode.widget.value, "My_ Workflow");
assert.equal(subgraphNode.widget.value, "My_ Workflow");
assert.deepEqual(
  { type: queries[0].type, scope: queries[0].scope },
  { type: "WorkflowName", scope: "root-and-subgraphs" },
  "the first run updates root and subgraph definitions before prompt construction",
);

documentName = "second/workflow.json";
for (const listener of beforeRun) listener();
assert.equal(rootNode.widget.value, "workflow");
assert.equal(subgraphNode.widget.value, "workflow");
assert.deepEqual(rootNode.widget.writes, ["My_ Workflow", "workflow"]);

documentName = undefined;
for (const listener of beforeRun) listener();
assert.equal(rootNode.widget.value, "NO_WORKFLOW_NAME");
assert.equal(subgraphNode.widget.value, "NO_WORKFLOW_NAME");

const isolatedListeners = new Set();
const isolatedNode = new FakeNode();
const isolatedApi = {
  workflow: { current: () => ({ name: "isolated.json" }) },
  graph: { queryNodes: () => [isolatedNode] },
  queue: {
    onBeforeRun(listener) {
      isolatedListeners.add(listener);
      return () => isolatedListeners.delete(listener);
    },
  },
};
const unsubscribe = module.namespace.installWorkflowName(isolatedApi);
assert.equal(isolatedListeners.size, 1);
for (const listener of isolatedListeners) listener();
assert.equal(isolatedNode.widget.value, "isolated");
unsubscribe();
assert.equal(isolatedListeners.size, 0, "the typed listener has explicit teardown");

console.log("PASS: secure WorkflowName sanitization, first-run sync, subgraphs, and teardown");
