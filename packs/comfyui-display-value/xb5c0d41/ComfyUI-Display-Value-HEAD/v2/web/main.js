import { comfy } from "/comfy/api/v2.js";


const NODE_TYPE = "DisplayValue";
const DISPLAY_NAME = "preview";
const STATE_VERSION = 1;
const MAX_VALUE_CHARS = 1_048_576;
const MIN_HEIGHT = 56;
const MAX_HEIGHT = 360;
const LINE_HEIGHT = 18;
const views = new WeakMap();


function normalizeState(value) {
  if (!value || typeof value !== "object" || value.version !== STATE_VERSION ||
      typeof value.preview !== "string" || value.preview.length > MAX_VALUE_CHARS) {
    return "";
  }
  return value.preview;
}


function normalizeExecutionValue(value, previous = "") {
  let normalized = Array.isArray(value) ? value.join("\n") : value;
  if (!normalized && previous) normalized = previous;
  if (typeof normalized !== "string" || normalized.length > MAX_VALUE_CHARS) {
    return previous;
  }
  return normalized;
}


function displayHeight(value) {
  const lines = Math.max(1, value.split("\n").length);
  return Math.max(MIN_HEIGHT, Math.min(MAX_HEIGHT, 22 + lines * LINE_HEIGHT));
}


class DisplayValueView {
  constructor(container, mountedValue, requestHeight) {
    this.container = container;
    this.mountedValue = mountedValue;
    this.requestHeight = requestHeight;
    this.preview = normalizeState(mountedValue.get());
    this.destroyed = false;
    this.unsubscribe = mountedValue.onChange((value) => {
      if (this.destroyed) return;
      const preview = normalizeState(value);
      if (preview !== this.preview) {
        this.preview = preview;
        this.render();
      }
    });
    this.render();
  }

  render() {
    if (this.destroyed) return;
    this.container.replaceChildren();
    const field = this.container.ownerDocument.createElement("textarea");
    field.value = this.preview;
    field.readOnly = true;
    field.setAttribute("aria-label", "Display Value output");
    field.style.boxSizing = "border-box";
    field.style.display = "block";
    field.style.width = "100%";
    field.style.height = "100%";
    field.style.opacity = "0.6";
    field.style.resize = "none";
    this.container.append(field);
    this.requestHeight(displayHeight(this.preview));
  }

  setValue(value) {
    if (this.destroyed) return;
    const preview = normalizeExecutionValue(value, this.preview);
    if (preview === this.preview) return;
    this.preview = preview;
    this.mountedValue.set({ version: STATE_VERSION, preview });
    this.render();
  }

  destroy() {
    if (this.destroyed) return;
    this.destroyed = true;
    this.unsubscribe();
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
    node.setSizeConstraints({ minWidth: 240, minHeight: 96, autoHeight: true });
    let widget;
    let pendingHeight;
    let lastHeight;
    widget = node.widgets.mount({
      name: DISPLAY_NAME,
      defaultValue: { version: STATE_VERSION, preview: "" },
      serialize: true,
      sendToPrompt: false,
      hideOnZoom: false,
      render(container, mountedValue) {
        destroyView(node);
        const view = new DisplayValueView(container, mountedValue, (height) => {
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

  builder.onExecuted((node, result) => {
    views.get(node)?.setValue(result.raw?.value);
  });

  builder.onRemoved((node) => {
    destroyView(node);
  });
});


export { displayHeight, normalizeExecutionValue, normalizeState };
