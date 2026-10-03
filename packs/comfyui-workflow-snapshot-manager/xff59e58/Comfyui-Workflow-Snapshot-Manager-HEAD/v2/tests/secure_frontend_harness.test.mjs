import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import vm from "node:vm";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

class MemoryStorage {
    constructor() {
        this.values = new Map();
    }

    async list(namespace) {
        return [...this.values.keys()].filter((key) => key === namespace || key.startsWith(`${namespace}/`));
    }

    async get(key) {
        return this.values.get(key);
    }

    async set(key, value) {
        this.values.set(key, value);
    }

    async remove(key) {
        this.values.delete(key);
    }

    async usage(namespace) {
        const entries = [...this.values.entries()].filter(([key]) => key.startsWith(namespace));
        return {
            usedBytes: entries.reduce((sum, [, value]) => sum + new TextEncoder().encode(value).byteLength, 0),
            entryCount: entries.length,
            quotaBytes: 8 * 1024 * 1024,
        };
    }
}

class FakeElement {
    constructor(ownerDocument, tagName) {
        this.ownerDocument = ownerDocument;
        this.tagName = tagName.toUpperCase();
        this.style = {};
        this.children = [];
        this.listeners = new Map();
        this.textContent = "";
        this.value = "";
        this.selected = false;
    }

    appendChild(child) {
        this.children.push(child);
        return child;
    }

    replaceChildren(...children) {
        this.children = children;
    }

    addEventListener(type, listener) {
        const listeners = this.listeners.get(type) || [];
        listeners.push(listener);
        this.listeners.set(type, listeners);
    }
}

class FakeDocument {
    createElement(tagName) {
        return new FakeElement(this, tagName);
    }
}

function graph(name, value = 1) {
    return {
        nodes: [{ id: 1, type: "Example", title: name, widgets_values: [value] }],
        links: [],
        groups: [],
    };
}

async function loadFrontend() {
    const commands = [];
    const notifications = [];
    const sidebars = [];
    const actionButtons = [];
    const dialogs = [];
    const settings = [];
    const workflowLoaded = [];
    const documentActivated = [];
    const nodeHooks = [];
    const opened = [];
    const intervals = [];
    const timeouts = [];
    const downloads = [];
    let picked;
    let currentGraph = graph("Initial");
    const storage = new MemoryStorage();
    const comfy = {
        storage,
        settings: {
            get() { return undefined; },
            declare(definition) { settings.push(definition); },
        },
        commands: {
            register(definition) { commands.push(definition); },
            notify(message) { notifications.push(message); },
        },
        ui: {
            addSidebarTab(definition) { sidebars.push(definition); return () => {}; },
            addActionBarButton(definition) { actionButtons.push(definition); return () => {}; },
            showDialog(definition) { dialogs.push(definition); return { close() {} }; },
            async prompt() { return undefined; },
        },
        defs: {
            extend(nodeId, build) {
                const builder = { onExecuted(callback) { nodeHooks.push({ nodeId, callback }); } };
                build(builder);
                return () => {};
            },
        },
        workflow: {
            current() { return { id: "doc-1", name: "Test", path: "workflows/test.json" }; },
            async snapshot() { return structuredClone(currentGraph); },
            async open(data, options) {
                opened.push({ data: structuredClone(data), options: structuredClone(options) });
                currentGraph = structuredClone(data);
            },
        },
        graph: { version: 1 },
        files: {
            async pick() { return picked; },
            async download(payload) { downloads.push(payload); },
        },
        onWorkflowLoaded(callback) { workflowLoaded.push(callback); return () => {}; },
        onDocumentActivated(callback) { documentActivated.push(callback); return () => {}; },
    };

    const context = vm.createContext({
        console,
        TextEncoder,
        TextDecoder,
        structuredClone,
        Date,
        Math,
        Promise,
        setInterval(callback, milliseconds) {
            intervals.push({ callback, milliseconds });
            return intervals.length;
        },
        clearInterval() {},
        setTimeout(callback, milliseconds) {
            timeouts.push({ callback, milliseconds, cleared: false });
            return timeouts.length;
        },
        clearTimeout(handle) {
            if (timeouts[handle - 1]) timeouts[handle - 1].cleared = true;
        },
    });
    const moduleCache = new Map();
    const comfyModule = new vm.SyntheticModule(["comfy"], function initialize() {
        this.setExport("comfy", comfy);
    }, { context, identifier: "/comfy/api/v2.js" });

    async function loadModule(identifier) {
        if (identifier === "/comfy/api/v2.js") return comfyModule;
        const absolute = identifier.startsWith("file:") ? fileURLToPath(identifier) : identifier;
        if (moduleCache.has(absolute)) return moduleCache.get(absolute);
        const source = await fs.readFile(absolute, "utf8");
        const module = new vm.SourceTextModule(source, {
            context,
            identifier: pathToFileURL(absolute).href,
            initializeImportMeta(meta) { meta.url = pathToFileURL(absolute).href; },
        });
        moduleCache.set(absolute, module);
        await module.link(async (specifier, referencingModule) => {
            if (specifier === "/comfy/api/v2.js") return comfyModule;
            const parentPath = path.dirname(fileURLToPath(referencingModule.identifier));
            return loadModule(path.resolve(parentPath, specifier));
        });
        return module;
    }

    const entry = await loadModule(path.join(root, "js", "snapshot_manager.js"));
    await entry.evaluate();
    return {
        manager: entry.namespace.snapshotManager,
        comfy,
        commands,
        notifications,
        dialogs,
        sidebars,
        actionButtons,
        settings,
        workflowLoaded,
        documentActivated,
        nodeHooks,
        opened,
        intervals,
        timeouts,
        downloads,
        storage,
        setGraph(value) { currentGraph = structuredClone(value); },
        setPicked(value) { picked = value; },
    };
}

test("secure frontend installs scoped UI and preserves capture, diff, restore, and import/export behavior", async () => {
    const harness = await loadFrontend();
    const {
        manager, comfy, commands, sidebars, actionButtons, nodeHooks, intervals, opened, downloads,
    } = harness;

    assert.equal(sidebars.length, 1);
    assert.equal(actionButtons.length, 1);
    assert.equal(intervals.length, 1);
    assert.equal(intervals[0].milliseconds, 500);
    assert.deepEqual(commands.map(({ scope }) => scope), ["canvas", "canvas"]);
    assert.deepEqual(commands.map(({ keybinding }) => ({ ...keybinding })), [
        { key: "s", ctrl: true },
        { key: "s", meta: true },
    ]);
    assert.deepEqual(nodeHooks.map(({ nodeId }) => nodeId), ["SaveSnapshot"]);

    const doc = new FakeDocument();
    const container = doc.createElement("section");
    sidebars[0].render(container);
    await manager.refreshSidebar();
    assert.ok(container.children.length > 0);

    const manualId = await manager.capture("Manual", {
        source: "manual", dedupe: false, skipCosmetic: false,
    });
    assert.ok(manualId);
    assert.equal((await manager.store.list(manager.workflowKey())).length, 1);

    harness.setGraph(graph("Changed", 2));
    comfy.graph.version += 1;
    manager.pollGraph();
    const autoTimer = harness.timeouts.at(-1);
    assert.ok(autoTimer);
    await autoTimer.callback();
    await manager.captureQueue;
    assert.equal((await manager.store.list(manager.workflowKey())).length, 2);

    const encodedThumbnail = "/9j/2Q==";
    nodeHooks[0].callback({}, { raw: { snapshot_manager_capture: [{
        label: "Node Trigger", thumbnail: encodedThumbnail,
    }] } });
    await manager.captureQueue;
    assert.equal((await manager.store.list(manager.workflowKey())).length, 3);
    const nodeRecord = (await manager.store.list(manager.workflowKey())).find((item) => item.source === "node");
    assert.equal(nodeRecord.hasThumbnail, true);
    assert.equal((await manager.store.get(manager.workflowKey(), nodeRecord.id)).thumbnail, encodedThumbnail);
    await manager.showThumbnail(manager.workflowKey(), nodeRecord.id);
    const previewDialog = harness.dialogs.at(-1);
    const previewContainer = doc.createElement("section");
    previewDialog.render(previewContainer);
    assert.equal(previewContainer.children[0].src, `data:image/jpeg;base64,${encodedThumbnail}`);

    const original = graph("Initial");
    const originalRecord = (await manager.store.list(manager.workflowKey())).find((item) => item.id === manualId);
    assert.ok(originalRecord);
    harness.setGraph(graph("Unsaved before restore", 3));
    await manager.restore(manager.workflowKey(), manualId);
    assert.deepEqual(opened.at(-1), { data: original, options: { mode: "replace" } });
    assert.ok((await manager.store.list(manager.workflowKey())).some((item) => item.source === "restore_guard"));

    await manager.showDiff(manager.workflowKey(), manualId);
    const diffDialog = harness.dialogs.at(-1);
    assert.match(diffDialog.title, /Snapshot diff/);
    const diffContainer = doc.createElement("section");
    diffDialog.render(diffContainer);
    assert.ok(diffContainer.children.some((child) => child.tagName === "PRE"));

    await manager.exportWorkflow(manager.workflowKey());
    assert.equal(downloads.length, 1);
    assert.equal(downloads[0].mimeType, "application/json");

    harness.setPicked({ bytes: new TextEncoder().encode("not-json") });
    await assert.rejects(manager.importWorkflow(), /valid UTF-8 JSON/);
    harness.setPicked({ bytes: new TextEncoder().encode(JSON.stringify({ version: 1, records: [{ bad: true }] })) });
    await assert.rejects(manager.importWorkflow(), /Invalid snapshot id/);

    const profileGraphA = graph("Profile A", 10);
    const profileGraphB = graph("Profile B", 20);
    await manager.store.put({
        id: "profile-snapshot-a", workflowKey: "path:a.json", timestamp: 10,
        label: "A", source: "manual", locked: true, graphData: profileGraphA,
    });
    await manager.store.put({
        id: "profile-snapshot-b", workflowKey: "path:b.json", timestamp: 20,
        label: "B", source: "manual", locked: true, graphData: profileGraphB,
    });
    const beforeProfile = opened.length;
    await manager.loadProfile({
        id: "profile-1", name: "Two tabs", timestamp: 30,
        activeWorkflowKey: "path:b.json",
        workflows: [
            { workflowKey: "path:b.json", displayName: "B tab", snapshotId: "profile-snapshot-b" },
            { workflowKey: "path:a.json", displayName: "../A/tab", snapshotId: "profile-snapshot-a" },
        ],
    });
    assert.deepEqual(opened.slice(beforeProfile), [
        { data: profileGraphA, options: { mode: "new", name: ".. A tab" } },
        { data: profileGraphB, options: { mode: "new", name: "B tab" } },
    ]);
});

test("the isolated realm supplies no ambient browser, persistence, or network authority", async () => {
    const harness = await loadFrontend();
    const manager = harness.manager;
    assert.equal(manager.api, harness.comfy);
    assert.equal(harness.commands.every((command) => command.scope === "canvas"), true);
    assert.equal(harness.sidebars.length, 1);
});
