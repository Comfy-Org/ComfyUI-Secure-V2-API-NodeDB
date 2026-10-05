import { comfy } from "/comfy/api/v2.js";
import { PRESETS } from "./presets.js";


const NODE_TYPE = "JOJR_RandomSize";
const STATE_VERSION = 1;
const MIN_HEIGHT = 120;
const MAX_HEIGHT = 360;
const LINE_HEIGHT = 17;
const views = new WeakMap();


function validPreset(value) {
  return typeof value === "string" && Object.hasOwn(PRESETS, value)
    ? value : "Preset";
}


function normalizeState(value) {
  const preset = validPreset(value?.preset);
  const selected = typeof value?.selected === "string" &&
      PRESETS[preset].includes(value.selected) ? value.selected : "";
  return { version: STATE_VERSION, preset, selected };
}


function displayLines(state) {
  return PRESETS[state.preset].map((size) =>
    size === state.selected ? `*${size}*` : size);
}


function displayText(state) {
  return `Sizes in present:\n${displayLines(state).join("\n")}`;
}


function displayHeight(state) {
  return Math.max(MIN_HEIGHT, Math.min(
    MAX_HEIGHT, 28 + displayLines(state).length * LINE_HEIGHT,
  ));
}


function scalar(value) {
  return Array.isArray(value) ? value[0] : value;
}


class RandomSizeView {
  constructor(node, container, mountedValue, requestHeight) {
    this.node = node;
    this.container = container;
    this.mountedValue = mountedValue;
    this.requestHeight = requestHeight;
    this.state = normalizeState(mountedValue.get());
    this.destroyed = false;
    this.unsubscribers = [];
    this.unsubscribers.push(mountedValue.onChange((value) => {
      if (this.destroyed) return;
      this.state = normalizeState(value);
      this.render();
    }));
    const presetWidget = node.widgets.get("preset");
    if (presetWidget) {
      this.unsubscribers.push(presetWidget.on("change", (value) => {
        this.setPreset(value);
      }));
    }
    this.syncFromWidgets();
  }

  syncFromWidgets() {
    const presetWidget = this.node.widgets.get("preset");
    if (presetWidget) this.setPreset(presetWidget.getValue());
    else this.render();
  }

  setState(next) {
    if (this.destroyed) return;
    const state = normalizeState(next);
    if (state.preset === this.state.preset &&
        state.selected === this.state.selected) {
      this.render();
      return;
    }
    this.state = state;
    this.mountedValue.set(state);
  }

  setPreset(value) {
    const preset = validPreset(value);
    const selected = preset === this.state.preset ? this.state.selected : "";
    const seedWidget = this.node.widgets.get("seed");
    const max = PRESETS[preset].length - 1;
    if (seedWidget) {
      seedWidget.setOption("max", max);
      const seed = seedWidget.getValue();
      if (typeof seed === "number" && seed > max) seedWidget.setValue(max);
    }
    this.setState({ version: STATE_VERSION, preset, selected });
  }

  setExecution(raw) {
    if (this.destroyed) return;
    const preset = validPreset(scalar(raw?.preset) ?? this.state.preset);
    const selected = scalar(raw?.selected);
    this.setState({ version: STATE_VERSION, preset, selected });
  }

  render() {
    if (this.destroyed) return;
    this.container.replaceChildren();
    const output = this.container.ownerDocument.createElement("pre");
    output.textContent = displayText(this.state);
    output.setAttribute("aria-label", "Random Size preset values");
    output.style.boxSizing = "border-box";
    output.style.height = "100%";
    output.style.margin = "0";
    output.style.overflow = "auto";
    output.style.opacity = "0.7";
    output.style.whiteSpace = "pre-wrap";
    this.container.append(output);
    this.requestHeight(displayHeight(this.state));
  }

  destroy() {
    if (this.destroyed) return;
    this.destroyed = true;
    for (const unsubscribe of this.unsubscribers.splice(0)) unsubscribe();
    this.container.replaceChildren();
  }
}


function destroyView(node) {
  const view = views.get(node);
  if (!view) return;
  view.destroy();
  views.delete(node);
}


comfy.defs.extend(NODE_TYPE, (builder) => {
  builder.onCreated((node) => {
    node.setSizeConstraints({ minWidth: 220, minHeight: 220, autoHeight: true });
    let widget;
    let pendingHeight;
    let lastHeight;
    widget = node.widgets.mount({
      name: "display_sizes",
      defaultValue: { version: STATE_VERSION, preset: "Preset", selected: "" },
      serialize: true,
      sendToPrompt: false,
      hideOnZoom: false,
      render(container, mountedValue) {
        destroyView(node);
        const view = new RandomSizeView(node, container, mountedValue, (height) => {
          if (height === lastHeight) return;
          lastHeight = height;
          if (widget) widget.setHeight(height);
          else pendingHeight = height;
        });
        views.set(node, view);
      },
      destroy() { destroyView(node); },
    });
    if (pendingHeight !== undefined) widget.setHeight(pendingHeight);
  });

  builder.onConfigured((node) => {
    views.get(node)?.syncFromWidgets();
  });

  builder.onExecuted((node, result) => {
    views.get(node)?.setExecution(result.raw);
  });

  builder.onRemoved((node) => {
    destroyView(node);
  });
});


export { displayHeight, displayLines, displayText, normalizeState, validPreset };
