// =============================================================================
// Pixaroma toolbar visibility
//
// Pixaroma puts three buttons in ComfyUI's top action bar: Align, Workflows and
// Help. Not everyone wants all three, so each can be switched off in Settings.
// All three are ON by default, so nobody loses a button they already use.
//
// HIDING IS CSS, NOT UN-MOUNTING. Each button mounts on its own retry loop
// (app.menu.settingsGroup can be late on a cold start, so each one retries up
// to 20 times over 5s). Un-mounting would have to race three separate timers
// and re-run whenever one of them finally lands. A body class costs nothing,
// applies whether the button has appeared yet or not, and reverses instantly.
//
// HIDING THE BUTTON DOES NOT TURN THE FEATURE OFF:
//   - Workflows keeps Alt+W and its right-click-empty-canvas entry
//   - Help keeps Alt+H and its right-click-empty-canvas entry
//   - Align keeps snapping; its on/off lives in Settings under "Align"
// Those shortcuts are registered as ComfyUI COMMANDS, which have no connection
// to the DOM button, so they survive on their own. Nothing in this file has to
// keep them alive, and nothing here should ever try to.
// =============================================================================

import { app } from "../../../scripts/app.js";

// Each entry targets the button's GROUP wrapper, not the button itself: the
// group is the .comfyui-button-group that carries the toolbar's spacing, so
// hiding only the button would leave its gap behind.
//
// Each checkbox gets its OWN category leaf. Two settings under one shared leaf
// have been seen to render as a single row in this panel, which is why the repo
// already splits "Align" from "Align (advanced)". Three leaves beginning
// "Toolbar:" sort together, so they still read as one block.
const BUTTONS = [
  {
    id: "Pixaroma.Toolbar.ShowAlign",
    bodyClass: "pix-toolbar-hide-align",
    group: ".pixaroma-align-group",
    name: "Show the Align button in the top toolbar",
    category: ["👑 Pixaroma", "Toolbar: Align"],
    tooltip:
      "Turn this off to take the Align button out of the top toolbar. Align itself is untouched: snapping carries on, and its on/off switch stays in the Align section of these settings.",
  },
  {
    id: "Pixaroma.Toolbar.ShowWorkflows",
    bodyClass: "pix-toolbar-hide-workflows",
    group: ".pixwb-group-btn",
    name: "Show the Workflows button in the top toolbar",
    category: ["👑 Pixaroma", "Toolbar: Workflows"],
    tooltip:
      "Turn this off to take the Workflows button out of the top toolbar. The panel itself is untouched: Alt+W still opens it, and so does right-clicking empty canvas.",
  },
  {
    id: "Pixaroma.Toolbar.ShowHelp",
    bodyClass: "pix-toolbar-hide-help",
    group: ".pixhb-group-btn",
    name: "Show the Help button in the top toolbar",
    category: ["👑 Pixaroma", "Toolbar: Help"],
    tooltip:
      "Turn this off to take the Help button out of the top toolbar. Help itself is untouched: Alt+H still opens it, and so does right-clicking empty canvas.",
  },
];

const CSS_ID = "pixaroma-toolbar-visibility-css";

function injectCSS() {
  if (document.getElementById(CSS_ID)) return;
  const style = document.createElement("style");
  style.id = CSS_ID;
  // !important because the toolbar group carries its own display rule.
  style.textContent = BUTTONS.map(
    (b) => `body.${b.bodyClass} ${b.group} { display: none !important; }`
  ).join("\n");
  document.head.appendChild(style);
}

function apply(btn, visible) {
  injectCSS();
  document.body?.classList.toggle(btn.bodyClass, !visible);
}

app.registerExtension({
  name: "Pixaroma.ToolbarVisibility",

  settings: BUTTONS.map((b) => ({
    id: b.id,
    name: b.name,
    type: "boolean",
    defaultValue: true,
    category: b.category,
    tooltip: b.tooltip,
    // The new value arrives as the argument. Re-reading the store here would
    // return the PREVIOUS value: onChange fires before the write lands.
    onChange: (v) => apply(b, v !== false),
  })),

  setup() {
    // Anything that is not an explicit false counts as visible, so a setting
    // that has never been written (or cannot be read) leaves the button up.
    for (const b of BUTTONS) {
      let visible = true;
      try {
        visible = app.ui?.settings?.getSettingValue(b.id) !== false;
      } catch {
        /* unregistered or unreadable on a first run: stay visible */
      }
      apply(b, visible);
    }
  },
});
