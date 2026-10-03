import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";

function check(condition, message) {
  if (!condition) throw new Error(message);
}

const settings = new Map();
const settingDefs = new Map();
const commands = new Map();
const pans = [];
let selected = [];

const comfy = {
  settings: {
    declare(definition) {
      settingDefs.set(definition.id, definition);
      if (!settings.has(definition.id)) {
        settings.set(definition.id, definition.defaultValue);
      }
    },
    get(id) {
      return settings.get(id);
    },
  },
  commands: {
    register(definition) {
      commands.set(definition.id, definition);
    },
  },
  graph: {
    selection() {
      return selected;
    },
    panBy(delta) {
      pans.push({ ...delta });
    },
  },
};

const context = vm.createContext({ console });
const facade = new vm.SyntheticModule(
  ["comfy"],
  function initialize() {
    this.setExport("comfy", comfy);
  },
  { context, identifier: "/comfy/api/v2.js" },
);
const sourcePath = path.resolve(process.env.TARGET_JS);
const source = fs.readFileSync(sourcePath, "utf8");
const module = new vm.SourceTextModule(source, {
  context,
  identifier: sourcePath,
});
await module.link(async (specifier) => {
  if (specifier === "/comfy/api/v2.js") return facade;
  throw new Error(`unexpected import: ${specifier}`);
});
await module.evaluate();

const base = "codecringebinge.Arrow Key Canvas Navigation";
const panSpeed = `${base}.Pan Speed`;
const shiftMultiplier = `${base}.Shift Multiplier`;
const manualSelectors = `${base}.Manual Overlay CSS Selectors (to Disable Panning)`;

check(settingDefs.size === 3, "wrong setting census");
check(settingDefs.get(panSpeed)?.type === "number", "pan speed type changed");
check(settingDefs.get(panSpeed)?.defaultValue === 60, "pan speed default changed");
check(
  settingDefs.get(shiftMultiplier)?.defaultValue === 3,
  "shift multiplier default changed",
);
check(
  settingDefs.get(manualSelectors)?.type === "text" &&
    settingDefs.get(manualSelectors)?.defaultValue === "",
  "compatibility selector setting changed",
);

check(commands.size === 8, "four regular and four Shift bindings are required");
for (const command of commands.values()) {
  check(command.scope === "canvas", `${command.id} is not canvas scoped`);
}

const command = (name, fast = false) =>
  commands.get(
    `codecringebinge.arrow.key.canvas.navigation.${name}${fast ? ".fast" : ""}`,
  );

check(command("up")?.keybinding?.key === "ArrowUp", "up key changed");
check(command("up")?.keybinding?.shift === undefined, "plain up requires Shift");
check(command("up", true)?.keybinding?.shift === true, "fast up lost Shift");

command("up").run();
command("down").run();
command("left").run();
command("right").run();
check(
  JSON.stringify(pans) ===
    JSON.stringify([
      { x: 0, y: 60 },
      { x: 0, y: -60 },
      { x: 60, y: 0 },
      { x: -60, y: 0 },
    ]),
  "default direction or distance changed",
);

settings.set(panSpeed, 25);
settings.set(shiftMultiplier, 4);
command("up", true).run();
check(
  JSON.stringify(pans.at(-1)) === JSON.stringify({ x: 0, y: 100 }),
  "Shift multiplier was not applied",
);

function makeNode({ images = 0, imageWidgets = 0 } = {}) {
  const widgets = Array.from({ length: imageWidgets }, () => ({ name: "image" }));
  widgets.push({ name: "seed" });
  return {
    getOutputImages() {
      return Array.from({ length: images }, (_, index) => `image-${index}.png`);
    },
    widgets: {
      all() {
        return widgets;
      },
    },
  };
}

selected = [makeNode({ images: 2 })];
const beforeOutputCarousel = pans.length;
command("left").run();
check(pans.length === beforeOutputCarousel, "output carousel lost Left ownership");
command("up").run();
check(pans.length === beforeOutputCarousel + 1, "carousel incorrectly blocked vertical pan");

selected = [makeNode({ imageWidgets: 2 })];
const beforeWidgetCarousel = pans.length;
command("right", true).run();
check(pans.length === beforeWidgetCarousel, "widget carousel lost Right ownership");

selected = [makeNode({ images: 1, imageWidgets: 1 })];
command("right").run();
check(
  JSON.stringify(pans.at(-1)) === JSON.stringify({ x: -25, y: 0 }),
  "single image incorrectly blocked panning",
);

for (const name of ["window", "parent", "document", "app", "LiteGraph", "fetch"]) {
  check(vm.runInContext(`typeof ${name}`, context) === "undefined", `${name} leaked`);
}

console.log("arrow key canvas navigation frontend harness: PASS");
