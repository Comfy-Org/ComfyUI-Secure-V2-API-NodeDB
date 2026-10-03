import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { pathToFileURL } from "node:url";

const entry = path.resolve(process.argv[2]);
assert.ok(entry, "pass panel_drawing_dialog.js");
const webRoot = path.dirname(entry);
const previewPath = path.join(webRoot, "panel_layout_preview.js");

for (const file of [entry, previewPath]) {
    const source = fs.readFileSync(file, "utf8");
    assert.doesNotMatch(source, /\bfetch\s*\(/);
    assert.doesNotMatch(source, /\bwindow\b/);
    assert.doesNotMatch(source, /\bdocument\s*\./);
    assert.doesNotMatch(source, /addEventListener\s*\(\s*["']keydown/);
    assert.match(source, /from ["']\/comfy\/api\/v2\.js["']/);
}

const storage = new Map();
const notices = [];
const extensions = [];
let failNextWrite = false;

const comfy = {
    storage: {
        async get(name) { return storage.get(name); },
        async set(name, value) {
            if (failNextWrite) {
                failNextWrite = false;
                throw new Error("storage quota exceeded");
            }
            storage.set(name, value);
        },
    },
    commands: { notify(value) { notices.push(value); } },
    defs: {
        extend(selector, register) {
            const definition = { selector, hidden: [], created: [] };
            register({
                hideWidget(name) { definition.hidden.push(name); },
                onCreated(callback) { definition.created.push(callback); },
            });
            extensions.push(definition);
        },
    },
    ui: { showDialog() { throw new Error("dialog rendering is not used by pure harness cases"); } },
};

const context = vm.createContext({ console, TextEncoder, URL });
const cache = new Map();
const comfyModule = new vm.SyntheticModule(["comfy"], function () {
    this.setExport("comfy", comfy);
}, { context, identifier: "secure:comfy-api-v2" });

async function loadModule(url) {
    if (url === "secure:comfy-api-v2") return comfyModule;
    if (cache.has(url)) return cache.get(url);
    const filename = new URL(url);
    const source = fs.readFileSync(filename, "utf8");
    const module = new vm.SourceTextModule(source, {
        context,
        identifier: url,
        initializeImportMeta(meta) { meta.url = url; },
    });
    cache.set(url, module);
    await module.link(async (specifier, referencing) => {
        if (specifier === "/comfy/api/v2.js") return comfyModule;
        return loadModule(new URL(specifier, referencing.identifier).href);
    });
    return module;
}

await comfyModule.link(() => {});
await comfyModule.evaluate();
const drawingModule = await loadModule(pathToFileURL(entry).href);
await drawingModule.evaluate();
const previewModule = cache.get(pathToFileURL(previewPath).href);
const drawing = drawingModule.namespace;
const preview = previewModule.namespace;
const plain = (value) => JSON.parse(JSON.stringify(value));

assert.equal(extensions.length, 2, "both frontend extensions must register");
assert.ok(extensions.every((item) => item.selector === "PanelLayoutProvider"));
assert.deepEqual(extensions[0].hidden, ["layout_preset"]);
assert.ok(extensions.every((item) => item.created.length === 1));
assert.deepEqual(Object.keys(plain(preview.ASPECT_RATIO_CHOICES)), [
    "1:1 (Square)", "9:7", "4:3 (Standard)", "A4", "19:13",
    "3:2 (Classic Photo)", "7:4", "16:9 (Widescreen)",
    "21:9 (Ultrawide)", "12:5 (Cinemascope)",
]);
assert.equal(preview.parseAspectRatio("A4"), Math.SQRT2);

// Exercise the typed mounted-widget registration, lifecycle, and local resize.
class Element {
    constructor(tag, doc) {
        this.tagName = tag.toUpperCase();
        this.ownerDocument = doc;
        this.children = [];
        this.listeners = Object.create(null);
        this.style = {};
        this.value = "";
        this.textContent = "";
        this.clientWidth = 320;
        this.clientHeight = tag === "canvas" ? 180 : 230;
    }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this.children = [...children]; }
    setAttribute(name, value) { this[name] = value; }
    addEventListener(name, callback) { this.listeners[name] = callback; }
    removeEventListener(name, callback) {
        if (this.listeners[name] === callback) delete this.listeners[name];
    }
    setPointerCapture() {}
    releasePointerCapture() {}
    getBoundingClientRect() { return { width: this.clientWidth, height: this.clientHeight }; }
    get options() {
        const descend = (root) => root.children.flatMap((child) =>
            child?.tagName === "OPTION" ? [child] : child?.children ? descend(child) : []);
        return descend(this);
    }
    getContext() {
        const methods = new Set([
            "beginPath", "clearRect", "closePath", "fill", "fillRect", "fillText",
            "lineTo", "moveTo", "setLineDash", "stroke", "strokeRect", "arc",
        ]);
        return new Proxy({}, {
            get(target, property) {
                if (methods.has(property)) return () => {};
                return target[property];
            },
            set(target, property, value) { target[property] = value; return true; },
        });
    }
}
const ownerDocument = {
    createElement(tag) { return new Element(tag, ownerDocument); },
    createTextNode(text) { return { nodeType: 3, textContent: text }; },
};
const widgetValues = new Map([
    ["layout_preset", "Single / Full Page"],
    ["aspect_ratio", "A4"],
    ["page_orientation", "portrait"],
    ["canvas_rotation", "0"],
    ["reading_order", "left_to_right"],
]);
const widgetHandles = new Map([...widgetValues].map(([name, value]) => [name, {
    value,
    getValue() { return this.value; },
    setValue(next) { this.value = next; },
    on() { return () => {}; },
}]))
let mountDefinition;
const mountedHeights = [];
let drawWidget;
const node = {
    id: "panel-node-1",
    properties: { previewHeight: 362 },
    setSizeConstraints(value) { this.constraints = value; },
    getProperty(name) { return this.properties[name]; },
    setProperty(name, value) { this.properties[name] = value; },
    widgets: {
        get(name) { return widgetHandles.get(name); },
        mount(definition) {
            mountDefinition = definition;
            return { setHeight(height) { mountedHeights.push(height); } };
        },
        add(definition) {
            drawWidget = {
                definition,
                setLabel(label) { this.label = label; },
                on(name, callback) { this[name] = callback; },
            };
            return drawWidget;
        },
    },
};
extensions[0].created[0](node);
assert.deepEqual(plain(node.constraints), { minWidth: 300, minHeight: 360 });
assert.equal(mountDefinition.name, "layout_preview");
assert.equal(mountDefinition.height, 362);
assert.equal(mountDefinition.serialize, false);
assert.equal(mountDefinition.sendToPrompt, false);
const mountedContainer = new Element("div", ownerDocument);
mountDefinition.render(mountedContainer);
await new Promise((resolve) => setImmediate(resolve));
assert.equal(mountedContainer.children.length, 4);
const resizeHandle = mountedContainer.children[3];
resizeHandle.listeners.pointerdown({ clientY: 100, pointerId: 1 });
resizeHandle.listeners.pointermove({ clientY: 180, pointerId: 1 });
resizeHandle.listeners.pointerup({ pointerId: 1 });
assert.ok(mountedHeights.at(-1) > 230);
assert.equal(node.properties.previewHeight, mountedHeights.at(-1));
extensions[1].created[0](node);
assert.equal(drawWidget.definition.name, "draw_panels");
assert.equal(drawWidget.label, "Draw Panels");
assert.equal(typeof drawWidget.activate, "function");
mountDefinition.destroy();

// Built-in library parity and immutable fallback.
const initial = await preview.loadPresets();
assert.equal(Object.keys(initial).length, 45);
assert.equal(initial.single_full_page.category, "Single");
assert.equal(initial.single_full_page.panels.length, 1);

// A custom layout is stored privately and serialized into the graph input.
const panels = [
    [[0, 0], [0.5, 0], [0.5, 1], [0, 1]],
    [[0.5, 0], [1, 0], [1, 1], [0.5, 1]],
];
const saved = await preview.savePreset("Personal", "Two Pages", panels, [[0, 1]]);
assert.match(saved.choice, /^__panelcomposer_v2__:/);
assert.deepEqual(plain(preview.decodePresetChoice(await preview.loadPresets(), saved.choice).panels), panels);
assert.ok(storage.get(preview.STORAGE_NAME).includes("Two Pages"));
const preservedCase = await preview.savePreset("single", "Case Match", [panels[0]], [0]);
assert.equal(preservedCase.preset.category, "Single");
await assert.rejects(
    preview.savePreset("Personal", "Duplicate Group", panels, [[0, 0]]),
    /every panel exactly once/,
);

// Save failure is atomic: neither storage nor the observable library changes.
const beforeFailure = storage.get(preview.STORAGE_NAME);
failNextWrite = true;
await assert.rejects(
    preview.savePreset("Personal", "Should Fail", panels, [[0, 1]]),
    /storage quota exceeded/,
);
assert.equal(storage.get(preview.STORAGE_NAME), beforeFailure);
assert.equal(Object.values(await preview.loadPresets()).some((item) => item.label === "Should Fail"), false);

// Deletion is real and per-user, including a built-in removed from this user's library.
await preview.deletePreset("single_full_page");
assert.equal(Object.hasOwn(await preview.loadPresets(), "single_full_page"), false);
assert.equal(Object.hasOwn(JSON.parse(storage.get(preview.STORAGE_NAME)), "single_full_page"), false);

// The storage boundary rejects an oversized library before calling the host.
const large = {};
const densePolygon = Array.from({ length: 64 }, (_, index) => [index / 64, (index % 2) / 2]);
const densePanels = Array.from({ length: 64 }, () => densePolygon);
for (let index = 0; index < 40; index += 1) {
    large[`layout_${index}`] = {
        category: "Large",
        label: `Layout ${index}`,
        panels: densePanels,
    };
}
const beforeQuota = storage.get(preview.STORAGE_NAME);
await assert.rejects(preview.persistLibrary(large), /exceeds 512 KiB/);
assert.equal(storage.get(preview.STORAGE_NAME), beforeQuota);
const poisoned = JSON.parse(`{"__proto__":${JSON.stringify({
    category: "Bad", label: "Bad", panels: [panels[0]],
})}}`);
await assert.rejects(preview.persistLibrary(poisoned), /layout key is invalid/);

// Repair, overlap warning, and local history are deterministic and isolated.
const bowtie = [[0, 0], [1, 1], [0, 1], [1, 0]];
assert.equal(drawing.hasSelfIntersection(bowtie), true);
const repaired = drawing.autoRepairPanel(bowtie);
assert.equal(drawing.validatePanelPoints(repaired), null);
assert.equal(drawing.hasSelfIntersection(repaired), false);
assert.deepEqual([...drawing.overlapIndices([
    [[0, 0], [0.7, 0], [0.7, 1], [0, 1]],
    [[0.3, 0], [1, 0], [1, 1], [0.3, 1]],
])], [0, 1]);
assert.equal(drawing.overlapIndices([
    [[0, 0], [0.5, 0], [0.5, 1], [0, 1]],
    [[0.5, 0], [1, 0], [1, 1], [0.5, 1]],
]).size, 0);

const historyA = drawing.createHistory([[[0, 0], [1, 0], [1, 1]]]);
const historyB = drawing.createHistory([[[0, 0], [0.5, 0], [0.5, 0.5]]]);
historyA.commit(panels);
historyA.undo();
assert.equal(historyA.current().length, 1);
assert.equal(historyB.current().length, 1);
assert.notDeepEqual(historyA.current(), historyB.current());
historyA.redo();
assert.deepEqual(plain(historyA.current()), panels);

assert.equal(notices.filter((item) => item.severity === "error").length, 0);
console.log("PASS: PanelComposer private layouts, graph serialization, geometry, and local history");
