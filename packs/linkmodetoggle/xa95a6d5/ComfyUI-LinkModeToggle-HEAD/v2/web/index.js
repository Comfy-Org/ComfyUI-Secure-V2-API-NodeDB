import { comfy } from "/comfy/api/v2.js";

const SETTING_ID = "Comfy.LinkRenderMode";
const MODES = [
  { value: 2, name: "SPLINE", label: "S" },
  { value: 1, name: "LINEAR", label: "L" },
  { value: 0, name: "STRAIGHT", label: "S" },
];

let button;
let stopSettingChange;
let writeQueue = Promise.resolve();
// Prime the sandbox's cache for this host-owned setting before onReady. The
// first undeclared read is intentionally asynchronous in Secure Nodes V2.
let confirmedMode = knownMode(comfy.settings.get(SETTING_ID)) ?? MODES[0];
let mountGeneration = 0;

function knownMode(value) {
  return MODES.find((mode) => mode.value === Number(value));
}

function modeFor(value) {
  return knownMode(value) ?? MODES[0];
}

function buttonFields(mode) {
  return {
    label: mode.label,
    tooltip: `Link Mode: ${mode.name} (F8 / Ctrl+K to toggle)`,
  };
}

function syncButton(mode = confirmedMode) {
  button?.update(buttonFields(mode));
}

async function cycleOnce() {
  const next = MODES[(MODES.indexOf(confirmedMode) + 1) % MODES.length];
  try {
    await comfy.settings.set(SETTING_ID, next.value);
    confirmedMode = next;
  } catch (error) {
    comfy.commands.notify({
      severity: "warn",
      summary: "Link mode was not changed",
      detail: error instanceof Error ? error.message : String(error),
    });
  } finally {
    // The guest setting cache is optimistic. A rejected write must therefore
    // restore the last host-confirmed mode rather than reread that cache.
    syncButton(confirmedMode);
  }
}

function cycle() {
  writeQueue = writeQueue.then(cycleOnce, cycleOnce);
  return writeQueue;
}

async function mountButton() {
  const generation = ++mountGeneration;
  stopSettingChange?.();
  stopSettingChange = undefined;
  button?.remove();
  button = undefined;
  stopSettingChange = comfy.settings.onChange(SETTING_ID, (value) => {
    confirmedMode = modeFor(value);
    syncButton(confirmedMode);
  });

  // Reading a core setting that this pack did not declare intentionally
  // returns undefined once while the sandbox backfills its synchronous cache.
  // Yield one task and read again before presenting state to the user.
  let initial = knownMode(comfy.settings.get(SETTING_ID));
  if (!initial) {
    await new Promise((resolve) => setTimeout(resolve, 0));
    initial = knownMode(comfy.settings.get(SETTING_ID));
  }
  if (generation !== mountGeneration) return;
  confirmedMode = initial ?? confirmedMode;
  button = comfy.ui.addActionBarButton({
    id: "link-mode-toggle.button",
    icon: "icon-[lucide--bezier-curve]",
    ...buttonFields(confirmedMode),
    run: () => { void cycle(); },
  });
}

for (const command of [
  {
    id: "link-mode-toggle.cycle.f8",
    keybinding: { key: "F8" },
  },
  {
    id: "link-mode-toggle.cycle.ctrl-k",
    keybinding: { key: "k", ctrl: true },
  },
]) {
  comfy.commands.register({
    ...command,
    label: "Cycle link render mode",
    scope: "canvas",
    run: cycle,
  });
}

comfy.onReady(mountButton);
