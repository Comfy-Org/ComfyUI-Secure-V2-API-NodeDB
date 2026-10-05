import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const sourcePath = process.argv[2];
if (!sourcePath) throw new Error("frontend source path is required");

class FakeElement {
  constructor(tagName, ownerDocument) {
    this.tagName = tagName.toUpperCase();
    this.ownerDocument = ownerDocument;
    this.style = {};
    this.children = [];
    this.parent = undefined;
    this.listeners = new Map();
    this.attributes = new Map();
    this.dataset = {};
    this.textContent = "";
    this.type = "";
    this.value = "";
    this.checked = false;
    this.src = "";
  }
  append(...children) {
    for (const child of children) {
      child.parent = this;
      this.children.push(child);
    }
  }
  replaceChildren(...children) {
    for (const child of this.children) child.parent = undefined;
    this.children = [];
    this.append(...children);
  }
  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) ?? new Set();
    listeners.add(listener);
    this.listeners.set(type, listeners);
  }
  removeEventListener(type, listener) {
    this.listeners.get(type)?.delete(listener);
  }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  dispatch(type) {
    const event = {
      type,
      target: this,
      defaultPrevented: false,
      propagationStopped: false,
      preventDefault() { this.defaultPrevented = true; },
      stopPropagation() { this.propagationStopped = true; },
    };
    for (const listener of [...(this.listeners.get(type) ?? [])]) listener(event);
    return event;
  }
}

class FakeDocument {
  constructor() { this.created = []; }
  createElement(tagName) {
    const element = new FakeElement(tagName, this);
    this.created.push(element);
    return element;
  }
}

function subscribe(map, name, listener) {
  const listeners = map.get(name) ?? new Set();
  listeners.add(listener);
  map.set(name, listeners);
  return () => listeners.delete(listener);
}

function emit(map, name, value) {
  for (const listener of [...(map.get(name) ?? [])]) listener(value);
}

const backendListeners = new Map();
const queueListeners = new Map();
const executingListeners = new Set();
const readyListeners = new Set();
const panels = [];
const dialogs = [];
const notifications = [];
const storageWrites = [];
let pending = 1;
let failNextWrite = false;
let stored = JSON.stringify({
  gifHeight: 999,
  selectedGif: "../escape.gif",
  barStyle: "not-a-style",
  gradientColor1: "javascript:red",
  fadeInOut: false,
});

const comfy = {
  onReady(listener) {
    readyListeners.add(listener);
    return () => readyListeners.delete(listener);
  },
  onExecutingNodeChanged(listener) {
    executingListeners.add(listener);
    return () => executingListeners.delete(listener);
  },
  backend: {
    on(name, listener) { return subscribe(backendListeners, name, listener); },
  },
  queue: {
    pending() { return pending; },
    onInterrupted(listener) { return subscribe(queueListeners, "interrupted", listener); },
    onRejected(listener) { return subscribe(queueListeners, "rejected", listener); },
    onPendingChanged(listener) { return subscribe(queueListeners, "pending", listener); },
  },
  storage: {
    async get(name) {
      assert.equal(name, "animate-progress/settings.json");
      return stored;
    },
    async set(name, value) {
      assert.equal(name, "animate-progress/settings.json");
      storageWrites.push(value);
      if (failNextWrite) {
        failNextWrite = false;
        throw new Error("quota reached");
      }
      stored = value;
    },
  },
  commands: {
    notify(notification) { notifications.push(notification); },
  },
  ui: {
    mountViewportPanel(definition) {
      const document = new FakeDocument();
      const container = document.createElement("div");
      const record = { definition, document, container, removed: false };
      definition.render(container);
      const handle = {
        remove() { record.removed = true; },
      };
      record.handle = handle;
      panels.push(record);
      return handle;
    },
    showDialog(definition) {
      const document = new FakeDocument();
      const container = document.createElement("div");
      const record = { definition, document, container, closed: false };
      definition.render(container);
      const handle = {
        close() {
          if (record.closed) return;
          record.closed = true;
          definition.destroy?.();
        },
      };
      record.handle = handle;
      dialogs.push(record);
      return handle;
    },
  },
};

let nextFrame = 1;
const frames = new Map();
const cancelledFrames = [];
function requestAnimationFrame(callback) {
  const id = nextFrame++;
  frames.set(id, callback);
  return id;
}
function cancelAnimationFrame(id) {
  cancelledFrames.push(id);
  frames.delete(id);
}
function flushFrames() {
  const current = [...frames.values()];
  frames.clear();
  for (const callback of current) callback();
}

let nextTimer = 1;
const timers = new Map();
const clearedTimers = [];
function setTimeout(callback, delay) {
  const id = nextTimer++;
  timers.set(id, { callback, delay });
  return id;
}
function clearTimeout(id) {
  clearedTimers.push(id);
  timers.delete(id);
}
function flushTimers() {
  const current = [...timers.values()];
  timers.clear();
  for (const { callback } of current) callback();
}

const deterministicMath = Object.create(Math);
deterministicMath.random = () => 0.5;
const context = vm.createContext({
  console,
  URL,
  Math: deterministicMath,
  requestAnimationFrame,
  cancelAnimationFrame,
  setTimeout,
  clearTimeout,
});
const module = new vm.SourceTextModule(fs.readFileSync(sourcePath, "utf8"), {
  context,
  identifier: sourcePath,
  initializeImportMeta(meta) {
    meta.url = "https://host/extensions/comfyui-animate-progress/animate_progress.js";
  },
});
await module.link(async (specifier) => {
  assert.equal(specifier, "/comfy/api/v2.js");
  const api = new vm.SyntheticModule(["comfy"], function initialize() {
    this.setExport("comfy", comfy);
  }, { context });
  await api.link(() => {});
  await api.evaluate();
  return api;
});
await module.evaluate();

async function settle() {
  for (let index = 0; index < 8; index += 1) await Promise.resolve();
}

function panel(id, from = 0) {
  return panels.slice(from).find((record) => record.definition.id === id);
}

function elementByAria(record, aria) {
  return record.document.created.find(
    (element) => element.attributes.get("aria-label") === aria,
  );
}

function setting(record, key) {
  return record.document.created.find((element) => element.dataset.setting === key);
}

function listenerCount(map, name) {
  return map.get(name)?.size ?? 0;
}

assert.equal(readyListeners.size, 1);
const ready = [...readyListeners][0];
ready();
await settle();

assert.equal(panels.length, 2);
const progressPanel = panel("animate-progress.progress");
const buttonPanel = panel("animate-progress.settings-button");
assert.ok(progressPanel);
assert.ok(buttonPanel);
assert.equal(progressPanel.definition.anchor, "bottom-center");
assert.equal(buttonPanel.definition.anchor, "bottom-right");
assert.equal(listenerCount(backendListeners, "progress"), 1);
assert.equal(listenerCount(backendListeners, "execution_error"), 1);
assert.equal(listenerCount(queueListeners, "interrupted"), 1);
assert.equal(listenerCount(queueListeners, "rejected"), 1);
assert.equal(listenerCount(queueListeners, "pending"), 1);
assert.equal(executingListeners.size, 1);

const progressRoot = progressPanel.document.created.find(
  (element) => element.style.height === "5px",
);
const bar = progressPanel.document.created.find(
  (element) => element.tagName === "DIV" && element.style.width === "0%",
);
const runner = progressPanel.document.created.find((element) => element.tagName === "IMG");
assert.equal(runner.style.height, "150px");
assert.equal(progressRoot.style.transition, "none");
assert.match(bar.style.background, /#00c3ff/);

// Progress is clamped, selects one closed-catalogue random GIF per run, and
// does not spin a perpetual animation loop.
emit(backendListeners, "progress", { value: 2, max: 4 });
assert.equal(progressRoot.style.display, "block");
assert.equal(bar.style.width, "50.00%");
assert.equal(runner.style.left, "50.00%");
assert.match(runner.src, /runners\/giphy18\.gif$/);
const firstRunner = runner.src;
emit(backendListeners, "progress", { value: 12, max: 10 });
assert.equal(bar.style.width, "100.00%");
assert.equal(runner.src, firstRunner);
assert.equal(frames.size, 1);
flushFrames();
assert.equal(progressRoot.style.opacity, "1");
assert.equal(frames.size, 0);
emit(backendListeners, "progress", { value: "bad", max: 0 });
assert.equal(bar.style.width, "100.00%");

pending = 0;
emit(queueListeners, "pending", 0);
assert.equal(progressRoot.style.opacity, "0");
assert.equal(timers.size, 1);
assert.equal([...timers.values()][0].delay, 500);
flushTimers();
assert.equal(progressRoot.style.display, "none");

// The typed settings dialog exposes all 12 settings and all 34 bundled GIFs.
const settingsButton = elementByAria(buttonPanel, "Open Animate Progress settings");
assert.equal(settingsButton.listeners.get("click").size, 1);
settingsButton.dispatch("click");
assert.equal(dialogs.length, 1);
const dialog = dialogs[0];
const gifButtons = dialog.document.created.filter(
  (element) => element.tagName === "BUTTON" && element.dataset.value,
);
assert.equal(gifButtons.length, 35);
assert.equal(setting(dialog, "gifHeight").value, "150");
assert.equal(setting(dialog, "barStyle").value, "default");
assert.equal(setting(dialog, "gradientColor1").value, "#00c3ff");
assert.equal(setting(dialog, "fadeInOut").checked, false);

const expectedAnimations = {
  default: "none",
  scanner: "ap-tech-scanner 2s ease-in-out infinite",
  pulsing: "ap-pulsing-glow 2s ease-in-out infinite",
  plasma: "ap-plasma-flow 10s ease infinite",
  barber: "ap-barber-pole 1s linear infinite",
  "cosmic-weave": "ap-cosmic-weave 2s linear infinite",
  "dna-helix": "ap-dna-helix 1s linear infinite",
  "marching-ants": "ap-marching-ants 1s linear infinite",
};
const barStyle = setting(dialog, "barStyle");
for (const [name, animation] of Object.entries(expectedAnimations)) {
  barStyle.value = name;
  barStyle.dispatch("change");
  await settle();
  assert.equal(bar.style.animation, animation);
}

const giphy03 = gifButtons.find((element) => element.dataset.value === "giphy03.gif");
const preview = dialog.document.created.find((element) => element.alt === "Runner preview");
giphy03.dispatch("mouseenter");
assert.match(preview.src, /runners\/giphy03\.gif$/);
assert.equal(preview.style.display, "block");
giphy03.dispatch("click");
await settle();
assert.equal(giphy03.attributes.get("aria-pressed"), "true");

// A rejected storage write restores the last host-confirmed settings and
// reports the error instead of leaving a falsely-persisted UI value.
const shadowBlur = setting(dialog, "shadowBlur");
assert.equal(shadowBlur.value, "3");
failNextWrite = true;
shadowBlur.value = "17";
shadowBlur.dispatch("input");
assert.match(runner.style.filter, /17px/);
await settle();
assert.equal(shadowBlur.value, "3");
assert.match(runner.style.filter, /3px/);
assert.equal(notifications.at(-1).severity, "warn");
assert.match(notifications.at(-1).detail, /quota reached/);

// Explicit GIF selection is applied on the next run. Every terminal path
// fades and hides the panel.
pending = 1;
emit(backendListeners, "progress", { value: 1, max: 8 });
assert.match(runner.src, /runners\/giphy03\.gif$/);
emit(queueListeners, "rejected", {});
flushTimers();
assert.equal(progressRoot.style.display, "none");
emit(backendListeners, "progress", { value: 1, max: 8 });
emit(queueListeners, "interrupted");
flushTimers();
assert.equal(progressRoot.style.display, "none");
emit(backendListeners, "progress", { value: 1, max: 8 });
emit(backendListeners, "execution_error", {});
flushTimers();
assert.equal(progressRoot.style.display, "none");

// Disabling is persisted and suppresses new progress events.
const enabled = setting(dialog, "enabled");
enabled.checked = false;
enabled.dispatch("change");
await settle();
emit(backendListeners, "progress", { value: 5, max: 10 });
assert.equal(progressRoot.style.display, "none");

// Remount while a dialog, animation frame, and hide timeout exist: old panels,
// listeners, subscriptions, frame, timer, and modal are all released exactly
// once. The replacement has one listener per host event, not duplicates.
enabled.checked = true;
enabled.dispatch("change");
await settle();
emit(backendListeners, "progress", { value: 1, max: 2 });
const frameBeforeRemount = [...frames.keys()][0];
emit(queueListeners, "interrupted");
const timerBeforeRemount = [...timers.keys()][0];
assert.ok(frameBeforeRemount === undefined || cancelledFrames.includes(frameBeforeRemount));
assert.ok(timerBeforeRemount !== undefined);
ready();
await settle();
assert.equal(progressPanel.removed, true);
assert.equal(buttonPanel.removed, true);
assert.equal(dialog.closed, true);
assert.equal(settingsButton.listeners.get("click").size, 0);
assert.ok(clearedTimers.includes(timerBeforeRemount));
assert.equal(listenerCount(backendListeners, "progress"), 1);
assert.equal(listenerCount(backendListeners, "execution_error"), 1);
assert.equal(listenerCount(queueListeners, "interrupted"), 1);
assert.equal(listenerCount(queueListeners, "rejected"), 1);
assert.equal(listenerCount(queueListeners, "pending"), 1);
assert.equal(executingListeners.size, 1);
assert.equal(panels.length, 4);
const newButtonPanel = panel("animate-progress.settings-button", 2);
const newButton = elementByAria(newButtonPanel, "Open Animate Progress settings");
assert.equal(newButton.listeners.get("click").size, 1);
assert.ok(storageWrites.length >= 10);

console.log("PASS: Animate Progress behavior, storage, assets, and lifecycle");
