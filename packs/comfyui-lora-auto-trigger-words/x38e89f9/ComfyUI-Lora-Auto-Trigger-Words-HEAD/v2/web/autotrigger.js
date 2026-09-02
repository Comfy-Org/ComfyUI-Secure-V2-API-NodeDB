import { comfy } from "/comfy/api/v2.js";


export const FRONTEND_INTENTS = Object.freeze([
  "combo-display-mode-setting",
  "hierarchical-subfolder-pickers",
  "managed-lora-preview",
  "live-preview-inventory-after-definition-refresh",
  "object-valued-combo-normalization",
  "save-output-as-lora-preview",
]);

const TARGETS = Object.freeze([
  "LoraLoaderAdvanced",
  "LoraLoaderStackedAdvanced",
]);
const DISPLAY_MODE = "autotrigger.Combo++.Submenu";


function numericMode(value) {
  if (value === true) return 1;
  const parsed = Number(value);
  return parsed === 2 ? 2 : parsed === 0 ? 0 : 1;
}


function applyDisplayMode(node) {
  const widget = node.widgets.get("lora_name");
  if (!widget) return;
  const mode = numericMode(comfy.settings.get(DISPLAY_MODE));
  widget.setOption("useGrouping", mode === 1);
  widget.setOption("showThumbnails", mode === 2);
  widget.setOption("showItemNavigators", mode !== 0);
}


function applyDisplayModeToOpenNodes() {
  for (const type of TARGETS) {
    for (const node of comfy.graph.nodesOfType(type)) applyDisplayMode(node);
  }
}


comfy.settings.declare({
  id: DISPLAY_MODE,
  name: "🐍 LoRA loader display mode",
  type: "combo",
  defaultValue: 1,
  options: [
    { value: 0, label: "List (normal)" },
    { value: 1, label: "Tree (subfolders)" },
    { value: 2, label: "Thumbnails (grid)" },
  ],
  category: ["LoRA Auto Trigger Words", "Models", "Display mode"],
  tooltip: "Choose the host-rendered LoRA catalogue picker presentation.",
  onChange: applyDisplayModeToOpenNodes,
});


// The host resolves adjacent previews from the model catalogue at hover time;
// there is no pack-owned image inventory to become stale when definitions are
// refreshed or a preview is assigned.
comfy.widgets.registerComboPreview({
  id: "autotrigger.loraPreviews",
  modelCategories: ["loras"],
  extensions: ["safetensors", "sft", "pt", "ckpt", "gguf"],
  candidatePolicy: "adjacent-model-preview-v1",
  media: ["image/png", "image/webp", "image/jpeg", "video/mp4", "video/webm"],
});


comfy.defs.extend(TARGETS, (builder) => {
  builder.onCreated((node) => {
    const widget = node.widgets.get("lora_name");
    if (!widget) return;
    const normalize = (value) => {
      if (
        value !== null
        && typeof value === "object"
        && typeof value.content === "string"
      ) {
        widget.setValue(value.content);
      }
    };
    widget.on("change", normalize);
    normalize(widget.getValue());
    applyDisplayMode(node);
  });
});


function loaderChoices() {
  const choices = [];
  for (const type of TARGETS) {
    for (const loader of comfy.graph.nodesOfType(type)) {
      const value = loader.widgets.get("lora_name")?.getValue();
      if (typeof value === "string" && value.length > 0) {
        choices.push({ loader, value });
      }
    }
  }
  return choices;
}


// User intent is "make the image currently under the pointer this LoRA's
// preview".  The pack passes only graph/model identities; the host resolves
// the managed /view descriptor and performs the confined atomic write.
comfy.defs.extend(/./, (builder) => {
  builder.addMenuItem({
    label: "Save as LoRA Preview",
    when: (node) => {
      const imageIndex = node.getDisplayedImageIndex();
      return Number.isSafeInteger(imageIndex)
        && imageIndex >= 0
        && imageIndex < node.getOutputImages().length
        && loaderChoices().length > 0;
    },
    items: () => loaderChoices().map(({ loader, value }) => ({
      label: value,
      run: (sourceNode) => {
        const imageIndex = sourceNode.getDisplayedImageIndex();
        const modelValue = loader.widgets.get("lora_name")?.getValue();
        if (
          !Number.isSafeInteger(imageIndex)
          || imageIndex < 0
          || typeof modelValue !== "string"
          || modelValue.length === 0
        ) return;
        void comfy.widgets.assignComboPreview({
          category: "loras",
          modelValue,
          sourceNodeId: String(sourceNode.id),
          imageIndex,
          policy: "adjacent-model-preview-v1",
        }).catch((error) => {
          console.error("[LoRA Auto Trigger] preview assignment failed", error);
        });
      },
    })),
  });
});


applyDisplayModeToOpenNodes();
