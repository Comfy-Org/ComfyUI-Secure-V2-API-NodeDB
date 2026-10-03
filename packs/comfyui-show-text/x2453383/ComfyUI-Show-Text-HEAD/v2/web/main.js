import { comfy } from "/comfy/api/v2.js";


const NODE_TYPE = "ShowText";
const DISPLAY_NAME = "show_text_display";
const STATE_VERSION = 1;
const MAX_DISPLAY_ITEMS = 1024;
const MAX_DISPLAY_CHARS = 4_194_304;
const MIN_HEIGHT = 48;
const MAX_HEIGHT = 480;
const ROW_BASE_HEIGHT = 34;
const LINE_HEIGHT = 18;
const views = new WeakMap();


function normalizeTexts(value) {
  if (!value || typeof value !== "object" || value.version !== STATE_VERSION ||
      !Array.isArray(value.texts) || value.texts.length > MAX_DISPLAY_ITEMS) {
    return [];
  }
  let characters = 0;
  const texts = [];
  for (const item of value.texts) {
    if (typeof item !== "string") return [];
    characters += item.length;
    if (characters > MAX_DISPLAY_CHARS) return [];
    texts.push(item);
  }
  return texts;
}


function normalizeExecutionText(value) {
  if (typeof value === "string") return [value];
  if (!Array.isArray(value) || value.length > MAX_DISPLAY_ITEMS) return [];
  let characters = 0;
  const texts = [];
  for (const item of value) {
    if (typeof item !== "string") return [];
    characters += item.length;
    if (characters > MAX_DISPLAY_CHARS) return [];
    texts.push(item);
  }
  return texts;
}


function visibleTexts(texts) {
  const visible = [...texts];
  if (!visible[0]) visible.shift();
  return visible;
}


function displayHeight(texts) {
  const visible = visibleTexts(texts);
  if (!visible.length) return MIN_HEIGHT;
  let height = 12;
  for (const text of visible) {
    const lines = Math.max(1, text.split("\n").length);
    height += Math.max(ROW_BASE_HEIGHT, 16 + lines * LINE_HEIGHT);
  }
  return Math.max(MIN_HEIGHT, Math.min(MAX_HEIGHT, height));
}


class ShowTextView {
  constructor(container, mountedValue, requestHeight) {
    this.container = container;
    this.mountedValue = mountedValue;
    this.requestHeight = requestHeight;
    this.texts = normalizeTexts(mountedValue.get());
    this.destroyed = false;
    this.unsubscribe = mountedValue.onChange((value) => {
      if (this.destroyed) return;
      const texts = normalizeTexts(value);
      if (JSON.stringify(texts) !== JSON.stringify(this.texts)) {
        this.texts = texts;
        this.render();
      }
    });
    this.render();
  }

  render() {
    if (this.destroyed) return;
    this.container.replaceChildren();
    const ownerDoc = this.container.ownerDocument;
    for (const text of visibleTexts(this.texts)) {
      const field = ownerDoc.createElement("textarea");
      field.value = text;
      field.readOnly = true;
      field.setAttribute("aria-label", "Show Text output");
      field.style.boxSizing = "border-box";
      field.style.display = "block";
      field.style.width = "100%";
      field.style.minHeight = "34px";
      field.style.margin = "0 0 6px";
      field.style.opacity = "0.7";
      field.style.resize = "none";
      this.container.append(field);
    }
    this.requestHeight(displayHeight(this.texts));
  }

  setTexts(texts) {
    if (this.destroyed) return;
    const normalized = normalizeExecutionText(texts);
    if (JSON.stringify(normalized) === JSON.stringify(this.texts)) return;
    this.texts = normalized;
    this.mountedValue.set({ version: STATE_VERSION, texts: normalized });
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
    node.setSizeConstraints({ minWidth: 280, minHeight: 80, autoHeight: true });
    let widget;
    let pendingHeight;
    let lastHeight;
    widget = node.widgets.mount(DISPLAY_NAME, {
      defaultValue: { version: STATE_VERSION, texts: [] },
      serialize: true,
      sendToPrompt: false,
      hideOnZoom: false,
      render(container, mountedValue) {
        destroyView(node);
        const view = new ShowTextView(container, mountedValue, (height) => {
          if (height === lastHeight) return;
          lastHeight = height;
          if (widget) widget.setHeight(height);
          else pendingHeight = height;
        });
        views.set(node, view);
        return () => {
          if (views.get(node) === view) views.delete(node);
          view.destroy();
        };
      },
    });
    if (pendingHeight !== undefined) widget.setHeight(pendingHeight);
  });

  builder.onExecuted((node, result) => {
    views.get(node)?.setTexts(result.raw?.text);
  });

  builder.onRemoved((node) => {
    destroyView(node);
  });
});


export { displayHeight, normalizeExecutionText, normalizeTexts, visibleTexts };
