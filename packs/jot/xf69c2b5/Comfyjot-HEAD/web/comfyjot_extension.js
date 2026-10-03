import { app } from "/scripts/app.js";

import { COMMANDS, DEFAULT_BRUSH_SIZE, EXTENSION_NAME, SETTINGS, SIDEBAR_TAB_ID } from "./jot/constants.js";
import { ComfyJotOverlay } from "./jot/overlay.js";
import { ensureStyles } from "./jot/styles.js";

const SIDEBAR_ICON_STYLE_ID = "comfyjot-sidebar-icon-style";
const DOODLE_ICON_URL = new URL("./icons/doodle.svg", import.meta.url).href;

let overlay = null;

function ensureSidebarIconStyles() {
  if (document.getElementById(SIDEBAR_ICON_STYLE_ID)) {
    return;
  }

  const style = document.createElement("style");
  style.id = SIDEBAR_ICON_STYLE_ID;
  style.textContent = `
    .${SIDEBAR_TAB_ID}-tab-button .side-bar-button-icon {
      width: 1.1em;
      height: 1.1em;
      min-width: 1.1em;
      min-height: 1.1em;
      display: inline-block;
      flex: 0 0 auto;
      font-size: 0;
      line-height: 0;
      background-color: currentColor;
      -webkit-mask-image: url("${DOODLE_ICON_URL}");
      mask-image: url("${DOODLE_ICON_URL}");
      -webkit-mask-repeat: no-repeat;
      mask-repeat: no-repeat;
      -webkit-mask-position: center;
      mask-position: center;
      -webkit-mask-size: contain;
      mask-size: contain;
    }
  `;
  document.head.appendChild(style);
}

function getSettingValue(settingId) {
  return app.ui?.settings?.getSettingValue?.(settingId);
}

function getOverlay() {
  if (!overlay) {
    overlay = new ComfyJotOverlay({
      getSettingValue,
      toast: app.extensionManager?.toast,
    });
  }
  return overlay;
}

function ensureOverlayVisible() {
  const instance = getOverlay();
  if (!instance.isVisible()) {
    instance.setVisible(true);
  }
  return instance;
}

function toggleOverlay() {
  const instance = getOverlay();
  if (instance.isVisible()) {
    return instance.setVisible(false);
  }
  instance.setVisible(true);
  return instance.toggleEditMode(false);
}

function toggleInkMode() {
  const instance = ensureOverlayVisible();
  return instance.toggleEditMode();
}

function closeSidebarTabIfOpen() {
  const toggleSidebarTab = app.extensionManager?.sidebarTab?.toggleSidebarTab;
  if (typeof toggleSidebarTab !== "function") {
    return false;
  }

  try {
    toggleSidebarTab(SIDEBAR_TAB_ID);
    return true;
  } catch {
    return false;
  }
}

function renderSidebarLauncher(element) {
  ensureStyles();
  element.replaceChildren();

  const container = document.createElement("div");
  container.className = "comfyjot-sidebar-launcher";

  const infoCard = document.createElement("div");
  infoCard.className = "comfyjot-sidebar-launcher__card";
  infoCard.innerHTML = `
    <strong>Comfy Jot</strong>
    <div>Canvas notes live above the graph so you can sketch arrows, write reminders, and keep workflow context visible.</div>
  `;

  const button = document.createElement("button");
  button.type = "button";
  button.className = "comfyjot-pill";
  button.textContent = "Open Jot Overlay";
  button.addEventListener("click", () => {
    const overlayInstance = ensureOverlayVisible();
    overlayInstance.toggleEditMode(false);
  });
  infoCard.appendChild(button);

  container.appendChild(infoCard);
  element.appendChild(container);

  queueMicrotask(() => {
    closeSidebarTabIfOpen();
    toggleOverlay();
  });
}

function registerSidebarTab() {
  const register = app.extensionManager?.registerSidebarTab;
  if (typeof register !== "function") {
    console.warn("[ComfyJot] registerSidebarTab is unavailable on this frontend build.");
    return;
  }

  ensureSidebarIconStyles();
  register({
    id: SIDEBAR_TAB_ID,
    title: "Comfy Jot",
    tooltip: "Toggle Comfy Jot canvas notes",
    label: "Jot",
    type: "custom",
    icon: "",
    render: renderSidebarLauncher,
  });
}

app.registerExtension({
  name: EXTENSION_NAME,

  settings: [
    {
      id: SETTINGS.DEFAULT_BRUSH_SIZE,
      name: "Default brush size",
      type: "slider",
      attrs: { min: 1, max: 48, step: 1 },
      defaultValue: DEFAULT_BRUSH_SIZE,
      category: ["Comfy Jot", "Canvas"],
    },
    {
      id: SETTINGS.SHOW_EXISTING_ON_LOAD,
      name: "Auto-show saved notes on workflow load",
      type: "boolean",
      defaultValue: true,
      category: ["Comfy Jot", "Canvas"],
    },
  ],

  commands: [
    {
      id: COMMANDS.TOGGLE_OVERLAY,
      label: "Comfy Jot: Toggle Overlay",
      icon: "pi pi-pencil",
      function: () => toggleOverlay(),
    },
    {
      id: COMMANDS.TOGGLE_INK,
      label: "Comfy Jot: Toggle Ink Mode",
      icon: "pi pi-file-edit",
      function: () => toggleInkMode(),
    },
    {
      id: COMMANDS.UNDO,
      label: "Comfy Jot: Undo Stroke",
      icon: "pi pi-undo",
      function: () => getOverlay().undo(),
    },
    {
      id: COMMANDS.REDO,
      label: "Comfy Jot: Redo Stroke",
      icon: "pi pi-redo",
      function: () => getOverlay().redo(),
    },
    {
      id: COMMANDS.CLEAR,
      label: "Comfy Jot: Clear Notes",
      icon: "pi pi-trash",
      function: () => getOverlay().clear(),
    },
  ],

  keybindings: [
    {
      combo: { key: "j", ctrl: true, shift: true },
      commandId: COMMANDS.TOGGLE_OVERLAY,
    },
  ],

  menuCommands: [
    {
      path: ["Extensions", "Comfy Jot"],
      commands: [
        COMMANDS.TOGGLE_OVERLAY,
        COMMANDS.TOGGLE_INK,
        COMMANDS.UNDO,
        COMMANDS.REDO,
        COMMANDS.CLEAR,
      ],
    },
  ],

  async setup() {
    ensureStyles();
    getOverlay().loadFromGraph();
    registerSidebarTab();
  },

  async afterConfigureGraph() {
    getOverlay().loadFromGraph();
  },
});
