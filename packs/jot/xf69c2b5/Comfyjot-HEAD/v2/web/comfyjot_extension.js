import { comfy } from "/comfy/api/v2.js";

import { ComfyJot } from "./jot/secure-overlay.js";

const jot = new ComfyJot();

comfy.settings.declare({
  id: "ComfyJot.Settings.DefaultBrushSize",
  name: "Default brush size",
  type: "slider",
  attrs: { min: 1, max: 48, step: 1 },
  defaultValue: 10,
  category: ["Comfy Jot", "Canvas"],
  onChange(value) {
    jot.setBrushSize(value);
  },
});

comfy.settings.declare({
  id: "ComfyJot.Settings.ShowExistingOnLoad",
  name: "Auto-show saved notes on workflow load",
  type: "boolean",
  defaultValue: true,
  category: ["Comfy Jot", "Canvas"],
});

for (const command of [
  {
    id: "ComfyJot.ToggleOverlay",
    label: "Comfy Jot: Toggle Overlay",
    run: () => jot.toggleVisible(),
    keybinding: { key: "j", ctrl: true, shift: true },
    scope: "canvas",
  },
  {
    id: "ComfyJot.ToggleInk",
    label: "Comfy Jot: Toggle Ink Mode",
    run: () => jot.toggleEditMode(),
  },
  {
    id: "ComfyJot.Undo",
    label: "Comfy Jot: Undo Stroke",
    run: () => jot.undo(),
  },
  {
    id: "ComfyJot.Redo",
    label: "Comfy Jot: Redo Stroke",
    run: () => jot.redo(),
  },
  {
    id: "ComfyJot.Clear",
    label: "Comfy Jot: Clear Notes",
    run: () => jot.clear(),
  },
]) {
  comfy.commands.register(command);
}

comfy.ui.addActionBarButton({
  id: "ComfyJot.ToggleOverlay.button",
  label: "Jot",
  tooltip: "Toggle Comfy Jot canvas notes",
  icon: "icon-[lucide--pencil]",
  run: () => jot.toggleVisible(),
});

await jot.mount();
comfy.onWorkflowLoaded(() => jot.loadFromWorkflow());
