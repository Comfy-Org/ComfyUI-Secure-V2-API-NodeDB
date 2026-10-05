import { comfy } from "/comfy/api/v2.js";


const NODE_TYPE = "MultiScenePrompt";
const SCENES_WIDGET = "scenes_json";
const MAX_SCENES = 32;
const MAX_SCENE_CHARS = 16_384;
const states = new WeakMap();
const installed = new WeakSet();


function normalizeScenes(value) {
  let parsed = value;
  if (typeof parsed === "string") {
    try {
      parsed = JSON.parse(parsed);
    } catch {
      parsed = [""];
    }
  }
  if (!Array.isArray(parsed) || parsed.length === 0) return [""];
  return parsed
    .slice(0, MAX_SCENES)
    .map((scene) => String(scene ?? "").slice(0, MAX_SCENE_CHARS));
}


function style(element, declarations) {
  Object.assign(element.style, declarations);
  return element;
}


class MultiSceneView {
  constructor(container, mountedValue) {
    this.container = container;
    this.doc = container.ownerDocument;
    this.mountedValue = mountedValue;
    this.scenes = normalizeScenes(mountedValue.get());
    this.active = 0;
    this.disposed = false;
    this.scrollTimer = undefined;

    this.root = style(this.doc.createElement("div"), {
      display: "flex",
      flexDirection: "column",
      width: "100%",
      height: "100%",
      overflow: "hidden",
      boxSizing: "border-box",
      fontFamily: "sans-serif",
    });
    this.tabRow = style(this.doc.createElement("div"), {
      display: "flex",
      alignItems: "center",
      gap: "6px",
      padding: "4px 6px",
      minHeight: "28px",
      borderRadius: "6px 6px 0 0",
      background: "var(--comfy-input-bg, #222)",
      boxSizing: "border-box",
    });
    this.tabs = style(this.doc.createElement("div"), {
      display: "flex",
      alignItems: "center",
      gap: "2px",
      flex: "1 1 auto",
      overflowX: "auto",
      overflowY: "hidden",
      whiteSpace: "nowrap",
      scrollbarWidth: "none",
    });
    this.onWheel = (event) => {
      if (Math.abs(event.deltaY) === 0) return;
      event.preventDefault();
      this.tabs.scrollLeft += event.deltaY;
    };
    this.tabs.addEventListener("wheel", this.onWheel, { passive: false });

    this.addButton = style(this.doc.createElement("button"), {
      flex: "0 0 auto",
      width: "24px",
      height: "24px",
      padding: "0",
      border: "1px solid var(--border-color, #555)",
      borderRadius: "4px",
      background: "var(--comfy-input-bg, #333)",
      color: "var(--input-text, #ddd)",
      cursor: "pointer",
      fontWeight: "bold",
    });
    this.addButton.type = "button";
    this.addButton.textContent = "+";
    this.addButton.title = "添加场景";
    this.onAdd = () => this.addScene();
    this.addButton.addEventListener("click", this.onAdd);
    this.tabRow.append(this.tabs, this.addButton);

    this.textarea = style(this.doc.createElement("textarea"), {
      width: "100%",
      minHeight: "100px",
      flex: "1 1 auto",
      resize: "none",
      boxSizing: "border-box",
      padding: "8px 10px",
      border: "1px solid var(--border-color, #444)",
      borderTop: "none",
      borderRadius: "0 0 6px 6px",
      outline: "none",
      background: "var(--comfy-input-bg, #1a1a1a)",
      color: "var(--input-text, #ddd)",
      font: "12px/1.4 sans-serif",
    });
    this.textarea.placeholder = "场景提示词";
    this.textarea.maxLength = MAX_SCENE_CHARS;
    this.onInput = () => {
      if (this.disposed) return;
      this.scenes[this.active] = this.textarea.value;
      this.commit();
    };
    this.textarea.addEventListener("input", this.onInput);
    this.root.append(this.tabRow, this.textarea);
    container.replaceChildren(this.root);

    this.stopWatching = mountedValue.onChange((value) => {
      if (this.disposed) return;
      this.scenes = normalizeScenes(value);
      if (this.active >= this.scenes.length) this.active = 0;
      this.render();
    });
    this.render();
    this.commit();
  }

  commit() {
    const serialized = JSON.stringify(this.scenes);
    if (this.mountedValue.get() !== serialized) this.mountedValue.set(serialized);
  }

  addScene() {
    if (this.scenes.length >= MAX_SCENES) return;
    this.scenes.push("");
    this.active = this.scenes.length - 1;
    this.commit();
    this.render(true);
  }

  selectScene(index) {
    if (index < 0 || index >= this.scenes.length) return;
    this.active = index;
    this.render();
  }

  removeScene(index) {
    if (this.scenes.length <= 1 || index < 0 || index >= this.scenes.length) return;
    this.scenes.splice(index, 1);
    if (this.active >= this.scenes.length) this.active = this.scenes.length - 1;
    this.commit();
    this.render();
  }

  render(scrollToEnd = false) {
    if (this.disposed) return;
    this.tabs.replaceChildren();
    this.scenes.forEach((_scene, index) => {
      const selected = index === this.active;
      const tab = style(this.doc.createElement("div"), {
        display: "inline-flex",
        alignItems: "center",
        gap: "3px",
        padding: "3px 7px",
        borderRadius: "4px",
        flexShrink: "0",
        background: selected ? "var(--comfy-menu-bg, #4a4a4a)" : "transparent",
        color: selected ? "var(--input-text, #fff)" : "var(--descrip-text, #999)",
      });
      const select = style(this.doc.createElement("button"), {
        border: "0",
        padding: "0",
        background: "transparent",
        color: "inherit",
        cursor: "pointer",
        font: "11px sans-serif",
      });
      select.type = "button";
      select.textContent = `场景${index + 1}`;
      select.setAttribute("aria-pressed", String(selected));
      select.addEventListener("click", () => this.selectScene(index));
      tab.appendChild(select);

      if (this.scenes.length > 1) {
        const remove = style(this.doc.createElement("button"), {
          border: "0",
          padding: "0 2px",
          background: "transparent",
          color: "inherit",
          cursor: "pointer",
          font: "13px sans-serif",
        });
        remove.type = "button";
        remove.textContent = "×";
        remove.title = `删除场景${index + 1}`;
        remove.addEventListener("click", () => this.removeScene(index));
        tab.appendChild(remove);
      }
      this.tabs.appendChild(tab);
    });
    this.textarea.value = this.scenes[this.active] ?? "";
    this.addButton.disabled = this.scenes.length >= MAX_SCENES;

    if (this.scrollTimer !== undefined) clearTimeout(this.scrollTimer);
    this.scrollTimer = setTimeout(() => {
      this.scrollTimer = undefined;
      if (this.disposed) return;
      const target = scrollToEnd
        ? this.tabs.lastElementChild
        : this.tabs.children[this.active];
      target?.scrollIntoView({ block: "nearest", inline: "nearest" });
    }, 0);
  }

  destroy() {
    if (this.disposed) return;
    this.disposed = true;
    if (this.scrollTimer !== undefined) clearTimeout(this.scrollTimer);
    this.stopWatching?.();
    this.tabs.removeEventListener("wheel", this.onWheel);
    this.addButton.removeEventListener("click", this.onAdd);
    this.textarea.removeEventListener("input", this.onInput);
    this.container.replaceChildren();
  }
}


function install(node) {
  if (installed.has(node)) return;
  installed.add(node);
  const original = node.widgets.get(SCENES_WIDGET);
  const initial = original?.getValue() ?? '[""]';
  node.widgets.remove(SCENES_WIDGET);
  let view;
  const widget = node.widgets.mount({
    name: SCENES_WIDGET,
    height: 148,
    hideOnZoom: false,
    defaultValue: JSON.stringify(normalizeScenes(initial)),
    serialize: true,
    sendToPrompt: true,
    render(container, value) {
      view = new MultiSceneView(container, value);
      states.set(node, view);
    },
    destroy() {
      view?.destroy();
      if (states.get(node) === view) states.delete(node);
      view = undefined;
    },
  });
  node.widgets.move(SCENES_WIDGET, 1);
  widget.setHeight(148);
  node.setSizeConstraints({ minWidth: 400, minHeight: 230, autoHeight: true });
}


comfy.defs.extend(NODE_TYPE, (builder) => {
  builder.onCreated((node) => install(node));
  builder.onRemoved((node) => {
    states.get(node)?.destroy();
    states.delete(node);
    installed.delete(node);
  });
});
