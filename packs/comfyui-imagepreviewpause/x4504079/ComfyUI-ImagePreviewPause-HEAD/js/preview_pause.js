import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const postContinue = (nodeId) => fetch("/image_preview_pause/continue/" + nodeId, { method: "POST" });
const postCancel = () => fetch("/image_preview_pause/cancel", { method: "POST" });

app.registerExtension({
  name: "image-preview-pause",
  nodeCreated(node) {
    if (node.comfyClass === "ImagePreviewPause") {
      const continueBtn = node.addWidget("button", "✔️ Continue", "CONTINUE", () => {
        postContinue(node.id);
      });

      const cancelBtn = node.addWidget("button", "⛔ Cancel", "CANCEL", () => {
        postCancel();
      });
    }
  },
  setup() {
    const original_api_interrupt = api.interrupt;
    api.interrupt = function () {
      postCancel();
      original_api_interrupt.apply(this, arguments);
    }
  },
});
