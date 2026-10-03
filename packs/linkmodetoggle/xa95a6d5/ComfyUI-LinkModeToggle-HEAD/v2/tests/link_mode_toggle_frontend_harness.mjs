import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { pathToFileURL } from "node:url";

const entry = path.resolve(process.argv[2]);
const source = fs.readFileSync(entry, "utf8");
assert.match(source, /from ["']\/comfy\/api\/v2\.js["']/);
for (const forbidden of [
  /\bwindow\b/, /\bdocument\b/, /\blocalStorage\b/, /\bsessionStorage\b/,
  /MutationObserver/, /app\.registerExtension/, /links_render_mode/,
  /setLinkRenderMode/, /render_curved_links/, /\bfetch\s*\(/,
]) assert.doesNotMatch(source, forbidden);

const SETTING_ID = "Comfy.LinkRenderMode";
let settingValue = 1;
let cachedSetting;
let cacheRequested = false;
let failNextWrite = false;
const settingListeners = new Set();
const setCalls = [];
const commands = [];
const notifications = [];
const readyListeners = new Set();
const buttons = [];

const comfy = {
  settings: {
    get(id) {
      assert.equal(id, SETTING_ID);
      if (!cacheRequested) {
        cacheRequested = true;
        setTimeout(() => { cachedSetting = settingValue; }, 0);
        return undefined;
      }
      return cachedSetting;
    },
    async set(id, value) {
      assert.equal(id, SETTING_ID);
      setCalls.push(value);
      cachedSetting = value;
      if (failNextWrite) {
        failNextWrite = false;
        throw new Error("write rejected");
      }
      const previous = settingValue;
      settingValue = value;
      for (const listener of [...settingListeners]) listener(value, previous);
    },
    onChange(id, listener) {
      assert.equal(id, SETTING_ID);
      settingListeners.add(listener);
      return () => settingListeners.delete(listener);
    },
  },
  commands: {
    register(definition) {
      assert.ok(!commands.some((item) => item.id === definition.id));
      commands.push(definition);
    },
    notify(definition) { notifications.push(definition); },
  },
  ui: {
    addActionBarButton(definition) {
      const handle = {
        definition,
        removed: false,
        updates: [],
        update(changes) {
          assert.equal(this.removed, false);
          this.updates.push(changes);
          Object.assign(this.definition, changes);
        },
        remove() { this.removed = true; },
      };
      buttons.push(handle);
      return handle;
    },
  },
  onReady(listener) {
    readyListeners.add(listener);
    return () => readyListeners.delete(listener);
  },
};

const context = vm.createContext({ console, Error, Promise, String, setTimeout });
const comfyModule = new vm.SyntheticModule(["comfy"], function () {
  this.setExport("comfy", comfy);
}, { context, identifier: "secure:comfy-api-v2" });
const module = new vm.SourceTextModule(source, {
  context,
  identifier: pathToFileURL(entry).href,
});
await comfyModule.link(() => {});
await comfyModule.evaluate();
await module.link(async (specifier) => {
  assert.equal(specifier, "/comfy/api/v2.js");
  return comfyModule;
});
await module.evaluate();

assert.equal(commands.length, 2);
const f8 = commands.find((command) => command.id.endsWith(".f8"));
const ctrlK = commands.find((command) => command.id.endsWith(".ctrl-k"));
assert.deepEqual(JSON.parse(JSON.stringify(f8.keybinding)), { key: "F8" });
assert.deepEqual(JSON.parse(JSON.stringify(ctrlK.keybinding)), { key: "k", ctrl: true });
assert.equal(f8.scope, "canvas");
assert.equal(ctrlK.scope, "canvas");
assert.equal(readyListeners.size, 1);

const ready = [...readyListeners][0];
await ready();
assert.equal(buttons.length, 1);
assert.equal(settingListeners.size, 1);
assert.equal(buttons[0].definition.label, "L");
assert.match(buttons[0].definition.tooltip, /LINEAR/);

// Host key dispatch withholds canvas-scoped commands from text entry.
async function dispatch(command, target) {
  if (command.scope === "canvas" && target === "text") return false;
  await command.run();
  return true;
}
assert.equal(await dispatch(f8, "text"), false);
assert.equal(await dispatch(ctrlK, "text"), false);
assert.deepEqual(setCalls, []);

// Both shortcuts and the button preserve the exact order and wrap.
assert.equal(await dispatch(f8, "canvas"), true);
assert.equal(settingValue, 0);
assert.match(buttons[0].definition.tooltip, /STRAIGHT/);
await dispatch(ctrlK, "canvas");
assert.equal(settingValue, 2);
assert.match(buttons[0].definition.tooltip, /SPLINE/);
buttons[0].definition.run({});
await new Promise((resolve) => setTimeout(resolve, 0));
assert.equal(settingValue, 1);
assert.match(buttons[0].definition.tooltip, /LINEAR/);
assert.deepEqual(setCalls, [0, 2, 1]);

// A settings-panel change updates the live action button.
const previous = settingValue;
settingValue = 0;
cachedSetting = 0;
for (const listener of [...settingListeners]) listener(settingValue, previous);
assert.equal(buttons[0].definition.label, "S");
assert.match(buttons[0].definition.tooltip, /STRAIGHT/);

// Failed writes report the failure and stay synchronized with host state.
failNextWrite = true;
await f8.run();
assert.equal(settingValue, 0);
assert.equal(cachedSetting, 2, "the real guest cache is optimistic on rejection");
assert.equal(buttons[0].definition.label, "S");
assert.match(buttons[0].definition.tooltip, /STRAIGHT/);
assert.equal(notifications.length, 1);
assert.equal(notifications[0].severity, "warn");

// Re-running setup removes old resources before installing replacements.
const firstButton = buttons[0];
const firstUpdateCount = firstButton.updates.length;
// Emulate the host correcting the optimistic cache before a later remount.
cachedSetting = settingValue;
await ready();
assert.equal(commands.length, 2, "ready remount must not register more commands");
assert.equal(buttons.length, 2);
assert.equal(firstButton.removed, true);
assert.equal(settingListeners.size, 1);
assert.match(buttons[1].definition.tooltip, /STRAIGHT/);
settingValue = 1;
cachedSetting = 1;
for (const listener of [...settingListeners]) listener(1, 0);
assert.equal(firstButton.updates.length, firstUpdateCount);
assert.match(buttons[1].definition.tooltip, /LINEAR/);

console.log("PASS: LinkModeToggle typed setting, commands, button, and teardown");
