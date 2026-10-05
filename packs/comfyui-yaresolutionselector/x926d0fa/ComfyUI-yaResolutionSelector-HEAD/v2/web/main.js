import { comfy } from "/comfy/api/v2.js";


const YARS_TYPES = ["YARS", "YARSAdv"];
const TARGET_TYPES = ["EmptyLatentImage", "ImageScale", "LatentUpscale"];
const READOUT = "resolution_printout";


function formatReadout(result) {
  const raw = result?.raw ?? result;
  const widthValue = Array.isArray(raw?.width) ? raw.width[0] : raw?.width;
  const heightValue = Array.isArray(raw?.height) ? raw.height[0] : raw?.height;
  const ratioValue = Array.isArray(raw?.ratio) ? raw.ratio[0] : raw?.ratio;
  const width = Number(widthValue);
  const height = Number(heightValue);
  const ratio = Number(ratioValue);
  if (!Number.isFinite(width) || !Number.isFinite(height) || !Number.isFinite(ratio)) return "";
  const megapixels = ((width * height) / 1048576).toFixed(2);
  return `resolution: ${width}x${height} (~${megapixels} Mpx)\nratio: ~${ratio.toFixed(2)}`;
}


function mountReadout(node) {
  node.setSizeConstraints({ minWidth: 260, minHeight: 120, autoHeight: true });
  node.widgets.mount(READOUT, {
    defaultValue: "",
    serialize: true,
    sendToPrompt: false,
    hideOnZoom: false,
    render(container, mountedValue) {
      const field = container.ownerDocument.createElement("textarea");
      field.readOnly = true;
      field.setAttribute("aria-label", "Calculated resolution");
      field.style.boxSizing = "border-box";
      field.style.width = "100%";
      field.style.height = "58px";
      field.style.opacity = "0.8";
      field.style.resize = "none";
      const update = (value) => {
        field.value = typeof value === "string" ? value : "";
      };
      update(mountedValue.get());
      const unsubscribe = mountedValue.onChange(update);
      container.replaceChildren(field);
      return () => {
        unsubscribe();
        container.replaceChildren();
      };
    },
  }).setHeight(68);
}


function ensureIntegerInput(node, name) {
  const existing = node.inputs.byName(name);
  if (existing) return { input: existing, created: false };
  const widget = node.widgets.get(name);
  if (!widget) return undefined;
  widget.setHidden(true);
  const input = node.inputs.add(name, "INT", {
    widget: name,
    widgetConfig: { type: "INT", options: widget.getOptions() ?? {} },
  });
  return { input, created: true, widget };
}


function rollbackInput(node, name, state) {
  if (!state?.created) return;
  node.inputs.remove(name);
  state.widget.setHidden(false);
}


export function prependSelector(target, selectorType = "YARS") {
  const position = target.getPosition();
  const selector = comfy.graph.add(selectorType, {
    position: { x: position.x - 290, y: position.y },
  });
  selector.setSize({ width: 260, height: 180 });

  const widthInput = ensureIntegerInput(target, "width");
  const heightInput = ensureIntegerInput(target, "height");
  const widthOutput = selector.outputs.byName("width");
  const heightOutput = selector.outputs.byName("height");
  const widthLink = widthInput && widthOutput?.connectTo(target.id, "width");
  const heightLink = heightInput && heightOutput?.connectTo(target.id, "height");
  if (!widthLink || !heightLink) {
    widthOutput?.disconnect(target.id);
    heightOutput?.disconnect(target.id);
    rollbackInput(target, "width", widthInput);
    rollbackInput(target, "height", heightInput);
    selector.remove();
    return undefined;
  }
  comfy.graph.select([selector]);
  return selector;
}


comfy.defs.extend(YARS_TYPES, (builder) => {
  builder.onCreated((node) => mountReadout(node));
  builder.onExecuted((node, result) => {
    const text = formatReadout(result);
    if (text) node.widgets.get(READOUT)?.setValue(text);
  });
});


comfy.defs.extend(TARGET_TYPES, (builder) => {
  builder.addMenuItem({
    label: "Prepend yaResolution Selector",
    order: -100,
    run(node) {
      prependSelector(node, "YARS");
    },
  });
  builder.addMenuItem({
    label: "Prepend Advanced yaResolution Selector",
    order: -99,
    run(node) {
      prependSelector(node, "YARSAdv");
    },
  });
});


export { formatReadout };
