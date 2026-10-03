import { comfy } from "/comfy/api/v2.js";

const BASE_ARROW_KEY_NAV_SETTINGS = 'codecringebinge.Arrow Key Canvas Navigation';
const PAN_SPEED_SETTING = `${BASE_ARROW_KEY_NAV_SETTINGS}.Pan Speed`;
const SHIFT_MULTIPLIER_SETTING = `${BASE_ARROW_KEY_NAV_SETTINGS}.Shift Multiplier`;
const MANUAL_OVERLAY_SELECTORS_SETTING = `${BASE_ARROW_KEY_NAV_SETTINGS}.Manual Overlay CSS Selectors (to Disable Panning)`;
const DEFAULT_PAN_SPEED = 60;
const DEFAULT_SHIFT_MULTIPLIER = 3;

for (const setting of [
  {
    id: MANUAL_OVERLAY_SELECTORS_SETTING,
    name: "Manual Overlay CSS Selectors (to Disable Panning)",
    type: "text",
    defaultValue: "",
    tooltip:
      "Retained for profile compatibility. Secure V2 automatically withholds canvas shortcuts while inputs, dialogs, modals, and interactive overlays own focus.",
  },
  {
    id: SHIFT_MULTIPLIER_SETTING,
    name: "Pan Speed Multiplier (Shift + Arrow Key)",
    type: "number",
    defaultValue: DEFAULT_SHIFT_MULTIPLIER,
    tooltip: "Multiplies pan speed while holding Shift.",
  },
  {
    id: PAN_SPEED_SETTING,
    name: "Pan Speed",
    type: "number",
    defaultValue: DEFAULT_PAN_SPEED,
    tooltip: "Sets pan speed in viewport pixels per step.",
  },
]) {
  comfy.settings.declare(setting);
}

function numberSetting(id, fallback) {
  const value = Number(comfy.settings.get(id));
  return Number.isFinite(value) ? value : fallback;
}

function hasImageCarousel(node) {
  if (!node) return false;
  if (node.getOutputImages().length > 1) return true;
  return node.widgets.all().filter((widget) => widget.name === "image").length > 1;
}

function selectedCarouselOwnsHorizontalArrows() {
  return comfy.graph.selection().some(hasImageCarousel);
}

function pan(xDirection, yDirection, shifted) {
  if (xDirection !== 0 && selectedCarouselOwnsHorizontalArrows()) return;

  const base = numberSetting(PAN_SPEED_SETTING, DEFAULT_PAN_SPEED);
  const multiplier = shifted
    ? numberSetting(SHIFT_MULTIPLIER_SETTING, DEFAULT_SHIFT_MULTIPLIER)
    : 1;
  const delta = base * multiplier;
  comfy.graph.panBy({ x: xDirection * delta, y: yDirection * delta });
}

const directions = [
  ["up", "ArrowUp", 0, 1],
  ["down", "ArrowDown", 0, -1],
  ["left", "ArrowLeft", 1, 0],
  ["right", "ArrowRight", -1, 0],
];

for (const [name, key, x, y] of directions) {
  comfy.commands.register({
    id: `codecringebinge.arrow.key.canvas.navigation.${name}`,
    label: `Pan canvas ${name}`,
    keybinding: { key },
    scope: "canvas",
    run: () => pan(x, y, false),
  });
  comfy.commands.register({
    id: `codecringebinge.arrow.key.canvas.navigation.${name}.fast`,
    label: `Pan canvas ${name} faster`,
    keybinding: { key, shift: true },
    scope: "canvas",
    run: () => pan(x, y, true),
  });
}
