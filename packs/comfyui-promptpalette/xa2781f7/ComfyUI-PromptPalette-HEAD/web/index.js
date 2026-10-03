import { app } from "../../scripts/app.js";
import { setupCanvasUI } from "./canvas_ui.js";
import { setupDomUI } from "./dom_ui.js";

app.registerExtension({
  name: "PromptPalette",

  async beforeRegisterNodeDef(nodeType, nodeData, app) {
    if (nodeData.name === "PromptPalette") {
      if (isVueNodesMode()) {
        setupDomUI(nodeType, app);
      } else {
        setupCanvasUI(nodeType, app);
      }
    }
  },
});

function isVueNodesMode() {
  if (typeof window === "undefined") {
    return false;
  }
  return !!(window.LiteGraph && window.LiteGraph.vueNodesMode);
}
