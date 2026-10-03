import { comfy } from "/comfy/api/v2.js";
import { CompareViewer } from "./compare_viewer.js";


const viewers = new WeakMap();

comfy.defs.extend("ImageCompareNode", (builder) => {
  builder.onCreated((node) => {
    if (node.widgets.get("image_compare")) return;
    node.setSizeConstraints({ minWidth: 360, minHeight: 400 });
    let viewer;
    node.widgets.mount({
      name: "image_compare",
      height: 330,
      hideOnZoom: false,
      serialize: false,
      sendToPrompt: false,
      render(container) {
        viewer = new CompareViewer(container);
        viewers.set(node, viewer);
      },
      destroy() {
        viewer?.destroy();
        viewers.delete(node);
      },
    });
  });

  builder.onExecuted((node) => {
    viewers.get(node)?.setImages(node.getOutputImages().slice(0, 2));
  });
  builder.onResized((node) => viewers.get(node)?.resize());
  builder.onRemoved((node) => {
    viewers.get(node)?.destroy();
    viewers.delete(node);
  });
});
