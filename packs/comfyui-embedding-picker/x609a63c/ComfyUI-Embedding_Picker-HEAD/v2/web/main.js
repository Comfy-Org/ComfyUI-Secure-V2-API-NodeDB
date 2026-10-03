import { comfy } from "/comfy/api/v2.js";


const PICKER_TYPE = "EmbeddingPicker";
const TARGET_TYPES = [PICKER_TYPE, "CLIPTextEncode"];
let embeddingNamesPromise;


export function listEmbeddingNames() {
  if (!embeddingNamesPromise) {
    embeddingNamesPromise = comfy.models.list("embeddings").catch(() => {
      embeddingNamesPromise = undefined;
      return [];
    });
  }
  return embeddingNamesPromise;
}


export async function populateEmbeddingWidget(node) {
  const widget = node.widgets.get("embedding");
  if (!widget) return;
  const names = await listEmbeddingNames();
  const current = widget.getValue();
  const choices = typeof current === "string" && current && !names.includes(current)
    ? [current, ...names]
    : names;
  widget.setOption("values", choices);
  if ((!current || typeof current !== "string") && choices.length) {
    widget.setValue(choices[0]);
  }
}


function ensureTextInput(node) {
  const existing = node.inputs.byName("text");
  if (existing) return { input: existing, created: false, widget: undefined };
  const widget = node.widgets.get("text");
  if (!widget) return undefined;
  const options = widget.getOptions() ?? { multiline: true };
  widget.setHidden(true);
  return {
    input: node.inputs.add("text", "STRING", {
      widget: "text",
      widgetConfig: { type: "STRING", options },
    }),
    created: true,
    widget,
  };
}


export function prependEmbeddingPicker(target) {
  const position = target.getPosition();
  const size = target.getSize();
  const shiftY = target.comfyClass === "CLIPTextEncode" ? 20 : 0;
  const picker = comfy.graph.add(PICKER_TYPE, {
    position: { x: position.x - 330, y: position.y + shiftY },
  });
  picker.setSize({ width: 300, height: 200 });
  picker.setColor(target.getColor());
  picker.setBgColor(target.getBgColor());

  const sourceText = target.widgets.get("text")?.getValue();
  if (typeof sourceText === "string") {
    picker.widgets.get("text")?.setValue(sourceText);
  }

  const targetInput = ensureTextInput(target);
  const pickerOutput = picker.outputs.byName("text");
  if (!targetInput || !pickerOutput || !pickerOutput.connectTo(target.id, "text")) {
    if (targetInput?.created) {
      target.inputs.remove("text");
      targetInput.widget.setHidden(false);
    }
    picker.remove();
    return undefined;
  }

  if (size.height > 120) {
    target.setSize({ width: size.width, height: 120 });
  }
  comfy.graph.select([picker]);
  return picker;
}


comfy.defs.extend(PICKER_TYPE, (builder) => {
  builder.onCreated((node) => {
    void populateEmbeddingWidget(node);
  });
});

comfy.defs.extend(TARGET_TYPES, (builder) => {
  builder.addMenuItem({
    label: "Prepend Embedding Picker",
    order: -100,
    run(node) {
      prependEmbeddingPicker(node);
    },
  });
});
