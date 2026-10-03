import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import vm from "node:vm";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

class MemoryStorage {
    constructor() { this.values = new Map(); }
    async list(namespace) { return [...this.values.keys()].filter((key) => key.startsWith(namespace)); }
    async get(key) { return this.values.get(key); }
    async set(key, value) { this.values.set(key, value); }
    async remove(key) { this.values.delete(key); }
    async usage(namespace) {
        const values = [...this.values.entries()].filter(([key]) => key.startsWith(namespace));
        return { usedBytes: values.reduce((sum, [, value]) => sum + new TextEncoder().encode(value).byteLength, 0), entryCount: values.length, quotaBytes: 16 * 1024 * 1024 };
    }
}

class FakeElement {
    constructor(ownerDocument, tagName) {
        this.ownerDocument = ownerDocument; this.tagName = tagName.toUpperCase(); this.children = [];
        this.listeners = new Map(); this.dataset = {}; this.style = {}; this.textContent = ""; this.value = "";
    }
    appendChild(child) { this.children.push(child); return child; }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this.children = children; }
    setAttribute(name, value) { this[name] = value; }
    addEventListener(type, listener) { this.listeners.set(type, [...(this.listeners.get(type) || []), listener]); }
    dispatch(type, event = {}) { for (const listener of this.listeners.get(type) || []) listener({ stopPropagation() {}, ...event }); }
}
class FakeDocument { createElement(tagName) { return new FakeElement(this, tagName); } }

function graph(name = "Current") { return { nodes: [{ id: 1, type: "Example", title: name }], links: [], groups: [] }; }

async function loadFrontend() {
    const storage = new MemoryStorage(); const sidebars = []; const buttons = []; const commands = [];
    const dialogs = []; const notifications = []; const opened = []; const downloads = [];
    let picked; let pickedMany = []; let currentGraph = graph();
    const comfy = {
        storage,
        ui: {
            addSidebarTab(definition) { sidebars.push(definition); return () => {}; },
            addActionBarButton(definition) { buttons.push(definition); return { update() {}, remove() {} }; },
            showDialog(definition) { dialogs.push(definition); return { close() { definition.destroy?.(); } }; },
            async prompt() { return undefined; },
        },
        commands: {
            register(definition) { commands.push(definition); },
            notify(message) { notifications.push(message); },
        },
        workflow: {
            current() { return { id: "doc-1", name: "Current Workflow", path: "workflows/current.json" }; },
            async snapshot() { return structuredClone(currentGraph); },
            async open(data, options) { opened.push({ data: structuredClone(data), options: structuredClone(options) }); },
        },
        files: {
            async pick() { return picked; },
            async pickMany() { return pickedMany; },
            async download(value) { downloads.push(value); },
        },
    };
    const context = vm.createContext({ console, TextEncoder, TextDecoder, Uint8Array, Date, Math, Promise, structuredClone, atob, btoa });
    const cache = new Map();
    const comfyModule = new vm.SyntheticModule(["comfy"], function init() { this.setExport("comfy", comfy); }, { context, identifier: "/comfy/api/v2.js" });
    async function load(identifier) {
        if (identifier === "/comfy/api/v2.js") return comfyModule;
        const absolute = identifier.startsWith("file:") ? fileURLToPath(identifier) : identifier;
        if (cache.has(absolute)) return cache.get(absolute);
        const source = await fs.readFile(absolute, "utf8");
        const module = new vm.SourceTextModule(source, { context, identifier: pathToFileURL(absolute).href });
        cache.set(absolute, module);
        await module.link(async (specifier, referencing) => specifier === "/comfy/api/v2.js" ? comfyModule : load(path.resolve(path.dirname(fileURLToPath(referencing.identifier)), specifier)));
        return module;
    }
    const entry = await load(path.join(root, "web", "workflow_vault.js")); await entry.evaluate();
    return {
        vault: entry.namespace.workflowVault, comfy, storage, sidebars, buttons, commands, dialogs,
        notifications, opened, downloads,
        setPicked(value) { picked = value; }, setPickedMany(value) { pickedMany = value; }, setGraph(value) { currentGraph = value; },
    };
}

test("frontend installs only typed mounted UI and canvas-scoped commands", async () => {
    const harness = await loadFrontend();
    assert.equal(harness.sidebars.length, 1);
    assert.equal(harness.sidebars[0].id, "Comfy.WorkflowVault");
    assert.equal(harness.buttons.length, 1);
    assert.deepEqual(harness.commands.map((item) => item.scope), ["canvas", "canvas"]);
    assert.deepEqual(harness.commands.map((item) => ({ ...item.keybinding })), [
        { key: "v", ctrl: true, shift: true }, { key: "s", ctrl: true, alt: true },
    ]);
    const container = new FakeDocument().createElement("aside");
    harness.sidebars[0].render(container); await harness.vault.renderSidebar();
    assert.ok(container.children.length >= 3);
});

test("save, browse, search and exact new/replace workflow opening work", async () => {
    const harness = await loadFrontend();
    const entry = await harness.vault.store.createEntry({ name: "Portrait Cleanup", description: "Skin detail", tags: ["portrait"], workflow: graph("Stored") });
    harness.vault.query = "skin";
    assert.deepEqual([...(await harness.vault.matchingEntries()).map((item) => item.id)], [entry.id]);
    await harness.vault.openEntry(entry.id, "new");
    await harness.vault.openEntry(entry.id, "replace");
    assert.deepEqual(harness.opened, [
        { data: graph("Stored"), options: { mode: "new", name: "Portrait Cleanup" } },
        { data: graph("Stored"), options: { mode: "replace" } },
    ]);
    harness.vault.showVaultDialog();
    const definition = harness.dialogs.at(-1); const container = new FakeDocument().createElement("main");
    definition.render(container); await new Promise((resolve) => setImmediate(resolve));
    assert.ok(container.children.length >= 4);
    definition.onKeyDown({ key: "s", editableTarget: false });
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(harness.dialogs.at(-1).key, "Comfy.WorkflowVault.saveDialog");
});

test("archive import/export uses bounded file broker and rejects malformed input", async () => {
    const harness = await loadFrontend();
    await harness.vault.store.createEntry({ name: "Portable", workflow: graph("Portable") });
    await harness.vault.exportArchive();
    assert.equal(harness.downloads.length, 1);
    assert.equal(harness.downloads[0].name, "workflow-vault-secure.json");
    assert.equal(harness.downloads[0].mimeType, "application/json");
    const raw = harness.downloads[0].bytes;

    const second = await loadFrontend();
    second.setPicked({ name: "vault.json", type: "application/json", bytes: raw });
    await second.vault.importArchive();
    assert.equal((await second.vault.store.state()).entries.length, 1);
    second.setPicked({ name: "bad.json", type: "application/json", bytes: new TextEncoder().encode("{}") });
    await assert.rejects(() => second.vault.importArchive(), /Invalid vault import/);
});

test("media picker and downloader remain bounded", async () => {
    const harness = await loadFrontend();
    const entry = await harness.vault.store.createEntry({ name: "Media", workflow: graph() });
    harness.setPickedMany([{ name: "example.png", type: "image/png", bytes: new Uint8Array([1, 2, 3]) }]);
    await harness.vault.addExamples(entry.id);
    const saved = await harness.vault.store.getEntry(entry.id);
    assert.equal(saved.examples.length, 1);
    assert.equal(saved.examples[0].bytes, 3);
});

test("dialog keys are scoped to host dialog callbacks and ignore editable targets", async () => {
    const harness = await loadFrontend();
    harness.vault.showVaultDialog();
    const definition = harness.dialogs.at(-1);
    const before = harness.dialogs.length;
    definition.onKeyDown({ key: "s", editableTarget: true });
    assert.equal(harness.dialogs.length, before);
    definition.onKeyDown({ key: "s", editableTarget: false });
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(harness.dialogs.length, before + 1);
});

test("frontend source contains no ambient DOM, network, browser storage or backend escape", async () => {
    const source = (await Promise.all(["workflow_vault.js", "vault_store.js"].map((name) => fs.readFile(path.join(root, "web", name), "utf8")))).join("\n");
    for (const forbidden of ["document.", "window.", "localStorage", "indexedDB", "fetch(", "comfy.backend", "innerHTML", "eval("]) {
        assert.equal(source.includes(forbidden), false, forbidden);
    }
    assert.match(source, /from "\/comfy\/api\/v2\.js"/);
    assert.match(source, /scope: "canvas"/);
    assert.match(source, /mode: "new"/);
    assert.match(source, /mode: "replace"/);
});
