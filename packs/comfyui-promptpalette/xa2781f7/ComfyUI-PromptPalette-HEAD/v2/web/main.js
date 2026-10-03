import { comfy } from "/comfy/api/v2.js";
import { normalizeConfig, PromptPaletteView } from "./palette.js";


const views = new WeakMap();

comfy.defs.extend("PromptPalette", (builder) => {
  builder.onCreated((node) => {
    if (node.widgets.get("promptpalette_ui")) return;
    const text = node.widgets.get("text");
    const delimiter = node.widgets.get("delimiter");
    const lineBreak = node.widgets.get("line_break");
    if (!text || !delimiter || !lineBreak) return;

    node.setSizeConstraints({ minWidth: 320, minHeight: 220 });
    let view;
    node.widgets.mount({
      name: "promptpalette_ui",
      height: 260,
      hideOnZoom: false,
      serialize: false,
      sendToPrompt: false,
      render(container) {
        view = new PromptPaletteView(container, text, delimiter, lineBreak);
        views.set(node, view);
      },
      destroy() {
        view?.destroy();
        views.delete(node);
      },
    });
  });

  builder.onConfigured((node) => {
    const delimiter = node.widgets.get("delimiter");
    const lineBreak = node.widgets.get("line_break");
    if (!delimiter || !lineBreak) return;
    normalizeConfig(delimiter, lineBreak);
    views.get(node)?.renderRows();
  });

  builder.onResized((node) => views.get(node)?.renderRows());
  builder.onRemoved((node) => {
    views.get(node)?.destroy();
    views.delete(node);
  });
});
