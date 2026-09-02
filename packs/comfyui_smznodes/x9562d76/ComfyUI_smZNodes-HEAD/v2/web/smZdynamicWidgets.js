import { comfy } from "/comfy/api/v2.js";


const ENCODE_WIDGETS = [
  "mean_normalization",
  "multi_conditioning",
  "use_old_emphasis_implementation",
  "with_SDXL",
];
const SDXL_WIDGETS = [
  "ascore", "width", "height", "crop_w", "crop_h",
  "target_width", "target_height", "text_g", "text_l",
];


function widget(node, name) {
  return node.widgets.get(name);
}


function hide(node, name, hidden) {
  widget(node, name)?.setHidden(Boolean(hidden));
}


export function applyEncodeVisibility(node) {
  const parser = String(widget(node, "parser")?.getValue() ?? "comfy");
  const withSdxl = Boolean(widget(node, "with_SDXL")?.getValue());
  const oldEmphasis = Boolean(
    widget(node, "use_old_emphasis_implementation")?.getValue()
  );
  hide(node, "mean_normalization", parser === "comfy");
  hide(
    node,
    "use_old_emphasis_implementation",
    parser === "comfy" || !oldEmphasis && parser.includes("comfy"),
  );
  hide(node, "text", withSdxl);
  hide(node, "multi_conditioning", withSdxl);
  for (const name of SDXL_WIDGETS) hide(node, name, !withSdxl);
  // Upstream hid this optional socket in its dynamic frontend. The backend
  // keeps it linkable/serializable and the V2 widget API hides only its widget.
  hide(node, "smZ_steps", true);
}


export function applySettingsVisibility(node) {
  let extra = {};
  try {
    extra = JSON.parse(String(widget(node, "extra")?.getValue() ?? "{}"));
  } catch (_error) {
    extra = {};
  }
  hide(node, "extra", true);
  for (const item of node.widgets.all()) {
    if (item.name === "extra") continue;
    if (item.name.startsWith("info_")) {
      item.setHidden(extra.show_descriptions !== true);
      item.setDisabled(true);
    } else if (item.name.startsWith("ㅤ")) {
      item.setHidden(extra.show_headings === false);
      item.setDisabled(true);
    }
  }
}


// One pinned frontend registration: the source extension named
// ``Comfy.smZ.dynamicWidgets`` handled both node types. ``defs.extend`` accepts
// the same selector set without touching prototypes or renderer internals.
comfy.defs.extend(["smZ CLIPTextEncode", "smZ Settings"], (builder) => {
  builder.onCreated((node) => {
    if (node.type === "smZ CLIPTextEncode" || node.comfyClass === "smZ CLIPTextEncode") {
      applyEncodeVisibility(node);
      widget(node, "parser")?.on("change", () => applyEncodeVisibility(node));
      widget(node, "with_SDXL")?.on("change", () => applyEncodeVisibility(node));
      widget(node, "use_old_emphasis_implementation")?.on(
        "change", () => applyEncodeVisibility(node),
      );
    } else {
      applySettingsVisibility(node);
      widget(node, "extra")?.on("change", () => applySettingsVisibility(node));
    }
  });

  for (const name of ENCODE_WIDGETS) {
    builder.addMenuItem({
      label: `Toggle ${name} visibility`,
      when: (node) => Boolean(widget(node, name)),
      run: (node) => {
        const item = widget(node, name);
        if (item) item.setHidden(!item.isHidden());
      },
    });
  }
});
