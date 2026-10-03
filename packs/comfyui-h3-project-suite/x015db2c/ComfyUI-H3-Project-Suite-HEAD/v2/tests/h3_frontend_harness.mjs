import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

class Element {
  constructor(tag, ownerDocument) {
    this.tagName = tag.toUpperCase();
    this.ownerDocument = ownerDocument;
    this.children = [];
    this.listeners = new Map();
    this.value = "";
    this.textContent = "";
    this.className = "";
  }
  append(...children) { for (const child of children) this.appendChild(child); }
  appendChild(child) {
    this.children.push(child);
    if (this.tagName === "SELECT" && !this.value && child.value) this.value = child.value;
    return child;
  }
  replaceChildren(...children) { this.children = []; this.append(...children); }
  addEventListener(name, listener) { this.listeners.set(name, listener); }
  setAttribute(name, value) { this[name] = value; }
  remove() { this.removed = true; }
  fire(name, event = {}) { return this.listeners.get(name)?.(event); }
}

class Document {
  createElement(tag) { return new Element(tag, this); }
}

const projects = new Map();
const calls = [];
let sidebar;

function response(status, value) {
  return { ok: status >= 200 && status < 300, status, json: async () => value };
}

const comfy = {
  backend: {
    async ownFetch(path, init) {
      calls.push([path, init?.method || "GET"]);
      const body = init?.body ? JSON.parse(init.body) : {};
      if (path === "/projects") return response(200, { projects: [...projects.keys()] });
      if (path === "/create") {
        projects.set(body.name, {
          name: body.name, width: 0, height: 0,
          approved: [], pending: null, takes: [], auto_approve: false,
        });
        return response(200, projects.get(body.name));
      }
      if (path.startsWith("/state?name=")) {
        const name = decodeURIComponent(path.split("=")[1]);
        return projects.has(name)
          ? response(200, projects.get(name))
          : response(404, { error: "missing" });
      }
      if (path === "/approve") {
        const state = projects.get(body.name);
        state.approved.push(state.pending);
        state.pending = null;
        return response(200, { ok: true, state });
      }
      return response(200, { ok: true });
    },
  },
  commands: {
    notify(value) { throw new Error(`unexpected notification: ${JSON.stringify(value)}`); },
    register(value) { assert.equal(value.id, "H3ProjectSuite.Refresh"); },
  },
  ui: {
    addSidebarTab(value) { sidebar = value; },
  },
};

globalThis.__comfy = comfy;
let source = await readFile(new URL("../web/h3_project_panel.js", import.meta.url), "utf8");
source = source
  .replace('import { comfy } from "/comfy/api/v2.js";', "const comfy = globalThis.__comfy;")
  .replace('new URL("./h3_project_panel.css", import.meta.url).href', '"h3_project_panel.css"');
await import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);

assert.equal(sidebar.id, "h3-project-suite.projects");
const doc = new Document();
const container = new Element("div", doc);
sidebar.render(container);
await new Promise((resolve) => setTimeout(resolve, 0));

const root = container.children[1];
assert.equal(root.children[3].textContent, "Create a project to begin.");
const creator = root.children[2];
creator.children[0].value = "Film One";
creator.children[1].fire("click");
await new Promise((resolve) => setTimeout(resolve, 0));
await new Promise((resolve) => setTimeout(resolve, 0));

assert(projects.has("Film One"));
assert.equal(root.children[3].textContent, "0 approved");
assert.deepEqual(calls.slice(0, 4), [
  ["/projects", "GET"],
  ["/create", "POST"],
  ["/projects", "GET"],
  ["/state?name=Film%20One", "GET"],
]);

const state = projects.get("Film One");
state.takes.push({ index: 1, take: 1, basename: "clip_001_take1" });
state.pending = state.takes[0];
await comfy.backend.ownFetch("/approve", {
  method: "POST", body: JSON.stringify({ name: "Film One" }),
});
assert.equal(state.approved.length, 1);
assert.equal(state.pending, null);

sidebar.destroy();
assert.equal(root.removed, true);
console.log("H3 secure frontend harness passed");
