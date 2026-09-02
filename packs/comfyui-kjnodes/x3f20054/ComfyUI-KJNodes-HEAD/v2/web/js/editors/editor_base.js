import { comfy } from '/comfy/api/v2.js';
import { makeUUID, watchImageInputs } from '../utility.js';

export function createEditorStylesheet(id, className) {
  let styleTag = document.head.querySelector(`#${id}`)
  if (!styleTag) {
    styleTag = document.createElement('style')
    styleTag.type = 'text/css'
    styleTag.id = id
    styleTag.innerHTML = `
      .${className} {
        position: absolute;
        font: 12px monospace;
        line-height: 1.5em;
        padding: 10px;
        z-index: 0;
        overflow: hidden;
      }
      .${className} canvas {
        position: relative;
        z-index: 2;
      }
    `
    document.head.appendChild(styleTag)
  }
}

function styleMenuItem(menuItem) {
  menuItem.style.display = "block";
  menuItem.style.padding = "5px";
  menuItem.style.color = "#FFF";
  menuItem.style.fontFamily = "Arial, sans-serif";
  menuItem.style.fontSize = "16px";
  menuItem.style.textDecoration = "none";
  menuItem.style.marginBottom = "5px";
}

function createMenuItem(id, textContent) {
  let menuItem = document.createElement("a");
  menuItem.href = "#";
  menuItem.dataset.menuId = id;
  menuItem.textContent = textContent;
  styleMenuItem(menuItem);
  return menuItem;
}

function setupMenuItems(contextMenu, menuItems) {
  menuItems.forEach(mi => {
    mi.addEventListener('mouseover', function () { this.style.backgroundColor = "gray"; });
    mi.addEventListener('mouseout', function () { this.style.backgroundColor = "#202020"; });
    contextMenu.appendChild(mi);
  });
}

export function createContextMenuElement(className) {
  const menu = document.createElement("div");
  if (className) menu.className = className;
  menu.id = `context-menu-${Math.random().toString(36).slice(2, 10)}`;
  menu.style.display = "none";
  menu.style.position = "absolute";
  menu.style.backgroundColor = "#202020";
  menu.style.minWidth = "100px";
  menu.style.boxShadow = "0px 8px 16px 0px rgba(0,0,0,0.2)";
  menu.style.zIndex = "100";
  menu.style.padding = "5px";
  return menu;
}

// ─── Base Editor Canvas ───

const maxDisplayDim = 1024;
const buttonRowHeight = 28;

// Node handles hold no arbitrary properties, so everything the editor used to
// hang off the node (editor instance, uuid, context menu, mounted element,
// height) lives here, keyed by node id, and is dropped when the node's mounted
// widget is destroyed.
const editorState = new Map();

function stateFor(node) {
  let state = editorState.get(node.id);
  if (!state) {
    state = {};
    editorState.set(node.id, state);
  }
  return state;
}

// Reached from two directions — the mounted widget being destroyed, and the node
// itself being removed — so it has to tolerate running twice.
function teardownNode(node) {
  const state = editorState.get(node.id);
  if (!state) return;
  editorState.delete(node.id);
  state.resizeObserver?.disconnect();
  state.bgWatch?.stop();
  clearTimeout(state.autoCreatePending);
  if (state.editor) state.editor.destroy();
  if (state.contextMenu?.parentNode) state.contextMenu.parentNode.removeChild(state.contextMenu);
}

export class BaseEditorCanvas {
  constructor(context, reset = false) {
    this.node = context;
    this.reset = reset;
    this.bgImage = null;
    this.margin = 14;
    this.dragIndex = -1;
    this.dragType = null;
    this.dragOffset = null;

    // Widget listeners are additive rather than a single overwritten callback,
    // so a replaced editor has to drop its own.
    this._widgetSubscriptions = [];
    this._uploadGeneration = 0;
  }

  // ─── Shared Methods ───

  setNodeWidth(width) {
    this.node.setSize({ width, height: this.node.getSize().height });
    const nodeEl = document.querySelector(`[data-node-id="${this.node.id}"]`);
    if (nodeEl) nodeEl.style.setProperty('--node-width', `${width}px`);
  }

  // Scale factors: coord space → canvas space
  get scaleX() { return this.width / this.coordWidth; }
  get scaleY() { return this.height / this.coordHeight; }

  // Returns mouse position in coord space
  getLocalMouse(e) {
    const rect = this.canvas.getBoundingClientRect();
    const canvasScaleX = this.canvas.width / rect.width;
    const canvasScaleY = this.canvas.height / rect.height;
    const canvasX = (e.clientX - rect.left) * canvasScaleX - this.margin;
    const canvasY = (e.clientY - rect.top) * canvasScaleY - this.margin;
    return {
      x: canvasX / this.scaleX,
      y: canvasY / this.scaleY
    };
  }

  // Clamp to coord space
  clamp(x, y) {
    return {
      x: Math.max(0, Math.min(this.coordWidth, x)),
      y: Math.max(0, Math.min(this.coordHeight, y))
    };
  }

  // ─── Canvas Setup ───

  createCanvas(parentElement) {
    this.canvas = document.createElement('canvas');
    this.canvas.width = this.width + this.margin * 2;
    this.canvas.height = this.height + this.margin * 2;
    this.ctx = this.canvas.getContext('2d');
    parentElement.appendChild(this.canvas);
  }

  resizeCanvas() {
    this.canvas.width = this.width + this.margin * 2;
    this.canvas.height = this.height + this.margin * 2;
  }

  // ─── Event Listeners ───

  setupEventListeners() {
    this._onDragMove = (e) => this.onMouseMove(e);
    this._onDragEnd = (e) => this.onMouseUp(e);
    // The middle button belongs to panning, which has to keep working over a
    // widget. Right stays claimed: the spline and point editors delete a point
    // with it, which is why contextmenu is suppressed below.
    this._onCanvasPointerDown = (e) => { if (e.button === 1) return; e.stopPropagation(); this.onMouseDown(e); };
    this._onCanvasPointerMove = (e) => this.onMouseMove(e);
    this._onCanvasContextMenu = (e) => { e.preventDefault(); e.stopPropagation(); };
    this.canvas.addEventListener('pointerdown', this._onCanvasPointerDown);
    this.canvas.addEventListener('pointermove', this._onCanvasPointerMove);
    this.canvas.addEventListener('contextmenu', this._onCanvasContextMenu);
  }

  removeEventListeners() {
    if (this.canvas) {
      this.canvas.removeEventListener('pointerdown', this._onCanvasPointerDown);
      this.canvas.removeEventListener('pointermove', this._onCanvasPointerMove);
      this.canvas.removeEventListener('pointermove', this._onDragMove);
      this.canvas.removeEventListener('pointerup', this._onDragEnd);
      this.canvas.removeEventListener('contextmenu', this._onCanvasContextMenu);
    }
    document.removeEventListener('pointermove', this._onDragMove);
    document.removeEventListener('pointerup', this._onDragEnd);
  }

  startDocumentDrag(e) {
    if (e && e.pointerId !== undefined) {
      this.canvas.setPointerCapture(e.pointerId);
      this._capturedPointerId = e.pointerId;
      // With pointer capture, events fire on the canvas, not document
      this.canvas.addEventListener('pointermove', this._onDragMove);
      this.canvas.addEventListener('pointerup', this._onDragEnd);
    } else {
      document.addEventListener('pointermove', this._onDragMove);
      document.addEventListener('pointerup', this._onDragEnd);
    }
  }

  endDrag() {
    this.dragIndex = -1;
    this.dragType = null;
    this.dragOffset = null;
    this.canvas.style.cursor = 'default';
    if (this._capturedPointerId !== undefined) {
      try { this.canvas.releasePointerCapture(this._capturedPointerId); } catch (_) {}
      this._capturedPointerId = undefined;
      this.canvas.removeEventListener('pointermove', this._onDragMove);
      this.canvas.removeEventListener('pointerup', this._onDragEnd);
    } else {
      document.removeEventListener('pointermove', this._onDragMove);
      document.removeEventListener('pointerup', this._onDragEnd);
    }
  }

  // ─── Render Batching ───

  render() {
    if (this._renderPending) return;
    this._renderPending = true;
    requestAnimationFrame(() => {
      this._renderPending = false;
      this._render();
    });
  }

  // Subclasses must implement _render()

  // ─── Common Render Helpers ───

  // Convert coord-space point to canvas-space pixel
  toCanvas(x, y) {
    return { x: x * this.scaleX, y: y * this.scaleY };
  }

  // Call at start of _render() — clears and draws background
  beginRender() {
    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    ctx.save();
    ctx.translate(this.margin, this.margin);
    ctx.fillStyle = '#222';
    ctx.fillRect(0, 0, this.width, this.height);
    ctx.strokeStyle = 'gray';
    ctx.lineWidth = 2;
    ctx.strokeRect(0, 0, this.width, this.height);
    if (this.bgImage) {
      ctx.drawImage(this.bgImage, 0, 0, this.width, this.height);
    }
  }

  endRender() {
    this.ctx.restore();
  }

  // ─── Image Handling ───

  handleImageLoad = (img, downscaledImg) => {
    // Set coord space to image dimensions, rescaling existing points if the space changed
    const oldCoordW = this.coordWidth, oldCoordH = this.coordHeight;
    this.coordWidth = img.width;
    this.coordHeight = img.height;
    this.widthWidget.setValue(img.width);
    this.heightWidget.setValue(img.height);
    if (oldCoordW && oldCoordH && (oldCoordW !== img.width || oldCoordH !== img.height)) {
      this.onCoordSpaceResized?.(oldCoordW, oldCoordH);
    }
    this.onImageResize?.(img);

    // Cap display size to the current node width if the user has already resized it,
    // otherwise fall back to maxDisplayDim. This prevents the node from expanding to
    // fill the image — instead the image scales to fit the node.
    const nodeCanvasW = Math.max(64, Math.round(this.node.getSize().width - 45));
    const fitDim = Math.min(nodeCanvasW, maxDisplayDim);
    let displayW = img.width, displayH = img.height;
    if (displayW > fitDim || displayH > fitDim) {
      const scale = fitDim / Math.max(displayW, displayH);
      displayW = Math.round(displayW * scale);
      displayH = Math.round(displayH * scale);
    }

    if (displayW !== this.width || displayH !== this.height) {
      this.width = displayW;
      this.height = displayH;
      this.resizeCanvas();

      // Only expand the node width if it's narrower than the image — never shrink it
      if (displayW + 45 > this.node.getSize().width) this.setNodeWidth(displayW + 45);
      this.onSizeChanged();
    }

    // Use downscaled image if available to avoid holding full-res in memory
    this.bgImage = downscaledImg || img;
    this.render();
    this.onDataChanged();
  };

  // resizeCanvas: if true (default), resize editor canvas to match image.
  // If false, just store the image and update the background without resizing.
  processImage = (img, { resize = true } = {}) => {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    let width = img.width, height = img.height;
    if (width > maxDisplayDim || height > maxDisplayDim) {
      const scale = maxDisplayDim / Math.max(width, height);
      width = Math.round(width * scale);
      height = Math.round(height * scale);
    }
    canvas.width = width;
    canvas.height = height;
    ctx.drawImage(img, 0, 0, width, height);

    const embed = comfy.settings.get("KJNodes.editors.embedBackgroundImage") ?? false;

    // Use the downscaled canvas directly as bgImage — drawImage accepts canvas elements,
    // avoids a data URL round-trip, and is immediately available (no async decode).
    const onStored = () => {
      if (resize) {
        this.handleImageLoad(img, canvas);
      } else {
        this.bgImage = canvas;
        this.render();
      }
    };

    const gen = ++this._uploadGeneration;
    if (embed) {
      const base64String = canvas.toDataURL('image/webp', 0.5).replace(/^data:.+?,/, '');
      if (gen !== this._uploadGeneration) return;
      this.node.setProperty('imgData', { type: 'image/webp', base64: base64String });
      onStored();
    } else {
      canvas.toBlob((blob) => {
        if (gen !== this._uploadGeneration) return;
        const filename = `editor_bg_${this.node.id}_${Date.now()}.webp`;
        const formData = new FormData();
        formData.append('image', blob, filename);
        formData.append('type', 'temp');
        formData.append('overwrite', 'true');
        fetch('/upload/image', { method: 'POST', body: formData })
          .then(r => r.json())
          .then(result => {
            if (gen !== this._uploadGeneration) return;
            this.node.setProperty('imgData', { type: 'temp', filename: result.name });
            onStored();
          })
          .catch(e => console.error("Failed to upload editor background:", e));
      }, 'image/webp', 0.5);
    }
  };

  handleImageFile = (file) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => { URL.revokeObjectURL(url); this.processImage(img); };
    img.onerror = () => URL.revokeObjectURL(url);
    img.src = url;
  };

  refreshBackgroundImage = () => {
    const imgData = this.node.getProperty('imgData');
    if (!imgData) return;

    const img = new Image();
    img.onerror = (e) => console.error("Background image failed to load:", e);
    img.onload = () => {
      // Just set the background — don't resize canvas, widget values are already correct from serialization
      this.bgImage = img;
      this.render();
    };

    if (imgData.base64) {
      const mimeType = imgData.type || 'image/png';
      img.src = `data:${mimeType};base64,${imgData.base64}`;
    } else if (imgData.filename) {
      img.src = `/view?filename=${encodeURIComponent(imgData.filename)}&type=temp&no-cache=${Date.now()}`;
    }
  };

  // ─── Context Menu Helpers ───

  // Set up document-level listeners for context menu behavior
  setupContextMenuListeners(editorIdPrefix) {
    const state = stateFor(this.node);
    this._onContextMenu = (e) => {
      if (e.target.closest(`#${editorIdPrefix}-${state.uuid}`) ||
          state.contextMenu.contains(e.target)) {
        e.preventDefault();
      }
    };
    this._onDocClick = (e) => {
      if (!state.contextMenu.contains(e.target)) {
        state.contextMenu.style.display = 'none';
      }
    };
    document.addEventListener('contextmenu', this._onContextMenu);
    document.addEventListener('click', this._onDocClick);
  }

  // Clean up previous editor instance
  cleanupPreviousEditor(context) {
    const state = stateFor(context);
    if (state.editor) {
      state.editor.destroy();
    }
  }

  // Full cleanup — override in subclass to add additional cleanup
  destroy() {
    this._uploadGeneration++;  // Invalidate any pending async image uploads
    this.removeEventListeners();
    for (const unsubscribe of this._widgetSubscriptions) unsubscribe();
    this._widgetSubscriptions = [];
    if (this._onContextMenu) document.removeEventListener('contextmenu', this._onContextMenu);
    if (this._onDocClick) document.removeEventListener('click', this._onDocClick);
    if (this._onKeyUp) document.removeEventListener('keyup', this._onKeyUp);
  }

  // Common menu actions
  openImageFilePicker() {
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = 'image/*';
    fileInput.addEventListener('change', (event) => {
      const file = event.target.files[0];
      if (file) this.handleImageFile(file);
    });
    fileInput.click();
  }

  clearBackgroundImage() {
    this.bgImage = null;
    this.node.setProperty('imgData', null);
    this.render();
  }

  // Find a widget by name on the node
  findWidget(name) {
    const w = this.node.widgets.get(name);
    if (!w) console.warn(`${this.constructor.name}: widget "${name}" not found`);
    return w;
  }

  // Show context menu at mouse position
  showContextMenu(e) {
    this._updateMenuToggleStates();
    const menu = stateFor(this.node).contextMenu;
    menu.style.display = 'block';
    menu.style.left = `${e.clientX}px`;
    menu.style.top = `${e.clientY}px`;
    // Adjust if menu overflows viewport
    const rect = menu.getBoundingClientRect();
    if (rect.right > window.innerWidth) menu.style.left = `${Math.max(0, e.clientX - rect.width)}px`;
    if (rect.bottom > window.innerHeight) menu.style.top = `${Math.max(0, e.clientY - rect.height)}px`;
  }

  // ─── Width/Height Resize ───

  setupSizeCallbacks() {
    this._widgetSubscriptions.push(this.widthWidget.on('change', () => {
      const oldCoordW = this.coordWidth;
      this.coordWidth = this.widthWidget.getValue();
      this.onCoordSpaceResized(oldCoordW, this.coordHeight);
      this.render();
      this.onDataChanged();
    }));
    this._widgetSubscriptions.push(this.heightWidget.on('change', () => {
      const oldCoordH = this.coordHeight;
      this.coordHeight = this.heightWidget.getValue();
      this.onCoordSpaceResized(this.coordWidth, oldCoordH);
      this.render();
      this.onDataChanged();
    }));
  }

  // ─── imgData persistence ───
  // Nothing to install: imgData is a node property, and core serializes and
  // restores properties, so writing it through setProperty is enough.
  static setupImgDataPersistence(node) {}

  // ─── Node registration helper ───
  // Call from onCreated to set up the common editor scaffolding.
  // config: { editorClass, editorKey, heightKey, className, menuItems, hiddenWidgets, initialSize, extraProperties }
  // editorClass: the editor constructor (e.g. SplineEditor)
  // editorKey: state key for the mounted editor element (e.g. 'splineEditor')
  // heightKey: state key for editor height (e.g. 'splineEditorHeight')
  // className: CSS class for the editor container
  // menuItems: { id: { label, action(editor), toggle?(editor) }, ... } — context menu definition
  // menuClassName: optional CSS class for the context menu
  // hiddenWidgets: widget names to hide
  // initialSize: [width, height] for the node
  // extraProperties: array of [name, default, type] to register on first create
  static setupNode(node, created, config) {
    const { editorClass, editorKey, heightKey, className, menuItems,
            menuClassName, hiddenWidgets, initialSize, extraProperties } = config;

    const state = stateFor(node);
    if (node.getProperty('imgData') === undefined) node.setProperty('imgData', null);

    for (const name of (hiddenWidgets || [])) {
      const w = node.widgets.get(name);
      if (w) w.setHidden(true);
    }

    state.uuid = makeUUID();

    // The editor body is a mounted element, so pointer events land on it
    // directly and it resizes with the node.
    node.widgets.mount({
      name: node.type,
      height: 550,
      render: (element) => {
        element.id = `${className}-${state.uuid}`;
        state[editorKey] = { element };
      },
      destroy: () => teardownNode(node),
    });
    state[heightKey] = 550;

    // File handling — dropped images go to the current editor. Both dragover and
    // drop are now ordinary listeners on the element the editor owns, in place of
    // node.onDragOver / node.onDragDrop.
    //
    // DROPPED: node.pasteFile, the hook core called when the user pasted an image
    // onto a selected node, has no published equivalent, so Ctrl+V no longer loads
    // a background. Dropping a file and the "Background image" menu entry both
    // still do.
    const element = state[editorKey].element;
    element.addEventListener("dragover", (e) => {
      if (state.editor && e.dataTransfer && e.dataTransfer.items &&
          [...e.dataTransfer.items].some(f => f.kind === "file" && f.type.startsWith("image/"))) {
        e.preventDefault();
      }
    });
    element.addEventListener("drop", (e) => {
      if (!state.editor) return;
      for (const file of e.dataTransfer.files) {
        if (file.type.startsWith("image/")) {
          e.preventDefault();
          state.editor.handleImageFile(file);
        }
      }
    });

    state.contextMenu = createContextMenuElement(menuClassName);
    state.menuDef = menuItems;
    const menuEls = Object.entries(menuItems).map(([id, def]) => createMenuItem(id, def.label || id));
    setupMenuItems(state.contextMenu, menuEls);
    document.body.appendChild(state.contextMenu);

    // Shared helper — loads the stored background image into the editor.
    // alignToImage: if true, resizes the node to fit the image first (old behaviour).
    //               if false, scales the image to fit the current node size (new behaviour).
    const _reloadBgImage = (alignToImage) => {
      const imgData = node.getProperty('imgData');
      if (!imgData) return;
      const img = new Image();
      img.onload = () => {
        if (!state.editor) return;
        if (alignToImage) {
          // Temporarily lift the node-size cap so processImage can expand the node
          const savedHeight = node.getSize().height;
          node.setSize({ width: Math.min(img.width, maxDisplayDim) + 45, height: savedHeight });
        }
        state.editor.processImage(img);
      };
      if (imgData.base64) {
        img.src = `data:${imgData.type || 'image/png'};base64,${imgData.base64}`;
      } else if (imgData.filename) {
        img.src = `/view?filename=${encodeURIComponent(imgData.filename)}&type=temp&no-cache=${Date.now()}`;
      }
    };

    // Two side-by-side buttons in a single mounted row.
    // "Reset canvas" — clears points and re-fits the image to the current node size.
    // "Align to image" — resizes the node to match the image dimensions (legacy behaviour).
    const buttonRow = document.createElement("div");
    buttonRow.style.cssText = "display:flex;gap:4px;width:100%;box-sizing:border-box;";
    const makeRowBtn = (label, onClick) => {
      const btn = document.createElement("button");
      btn.textContent = label;
      btn.style.cssText = "flex:1;height:24px;padding:0 6px;font:12px sans-serif;cursor:pointer;";
      btn.addEventListener("click", onClick);
      return btn;
    };
    buttonRow.appendChild(makeRowBtn("Reset canvas", () => {
      try {
        state.editor = new editorClass(node, true);
        _reloadBgImage(false);
      } catch (error) { console.error(`Error creating ${editorClass.name}:`, error); }
    }));
    buttonRow.appendChild(makeRowBtn("Align to image", () => {
      try {
        if (!state.editor) state.editor = new editorClass(node);
        _reloadBgImage(true);
      } catch (error) { console.error(`Error aligning ${editorClass.name}:`, error); }
    }));
    node.widgets.mount({
      name: "editor_buttons",
      height: buttonRowHeight,
      render: (container) => container.appendChild(buttonRow),
    });

    node.setSize({ width: initialSize[0], height: initialSize[1] });
    state[editorKey].parentEl = document.createElement("div");
    state[editorKey].parentEl.className = className;
    state[editorKey].parentEl.id = `${className}-${state.uuid}`;
    element.appendChild(state[editorKey].parentEl);

    // Deferred so it runs after a saved workflow has finished restoring widget
    // values — which is what the cancelled-on-configure timeout used to arrange.
    state.autoCreatePending = setTimeout(() => {
      if (!state.editor) {
        try {
          state.editor = new editorClass(node);
          // COSMETIC: addProperty's third argument declared the property's type so
          // the properties panel could pick an editor for it. setProperty carries
          // no type, so the panel falls back to its default. The stored value, and
          // therefore the saved workflow, is unchanged.
          for (const [name, value] of (extraProperties || [])) {
            if (node.getProperty(name) === undefined) node.setProperty(name, value);
          }
        } catch (error) { console.error(`Error creating ${editorClass.name}:`, error); }
      }
    }, 0);

    BaseEditorCanvas.setupImgDataPersistence(node);

    state.resizeObserver = new ResizeObserver(() => {
      const editor = state.editor;
      if (!editor) return;
      const newWidth = Math.max(64, Math.round(node.getSize().width - 45));
      if (newWidth === editor.width) return;

      // Only change display size — coord space stays the same
      editor.width = newWidth;
      editor.height = Math.round(newWidth * (editor.coordHeight / editor.coordWidth));

      editor.resizeCanvas();
      editor.onSizeChanged();
      editor.render();
    });
    state.resizeObserver.observe(element);

    // Load background image from connected source node (LoadImage, LoadVideo, etc.)
    // bgWatchReady is false during reload until the editor has restored its saved
    // background. bgFromConnectedSource tracks whether the current bg came from a
    // connection (vs execution/drop).
    state.bgFromConnectedSource = false;
    // A node that arrived carrying saved state has a stored background to restore
    // first; the old code learned that from onConfigure, and NodeCreatedEvent
    // says it directly.
    state.bgWatchReady = !created?.restored;
    if (!state.bgWatchReady) setTimeout(() => { state.bgWatchReady = true; }, 500);
    state.bgWatch = watchImageInputs(node, "bg_image", (sources) => {
      if (!state.editor || !state.bgWatchReady) return;
      const source = sources[0];
      // DROPPED: a connected video source used to be previewed by grabbing the
      // first frame off VideoHelperSuite's own <video> element — see the refusal
      // in utility.js resolveSourcePreview. Only still images arrive here now.
      if (source && !source.isVideo) {
        state.bgFromConnectedSource = true;
        const img = new Image();
        img.crossOrigin = "anonymous";
        img.onerror = (e) => console.error("[Editor] source image load error:", e);
        img.onload = () => { if (state.editor) state.editor.processImage(img); };
        img.src = source.url;
      } else if (!source && state.bgFromConnectedSource) {
        state.bgFromConnectedSource = false;
        state.editor.clearBackgroundImage();
      }
    });
  }

  // ─── Definition-level hooks ───
  // Call once from the defs.extend body, beside b.onCreated. Execution results,
  // connection changes and removal are declared per node TYPE rather than chained
  // onto each instance, so they cannot be registered from inside setupNode without
  // adding a listener per node. Each one resolves the node's own state by id.
  static setupNodeHooks(b) {
    b.onExecuted((node, result) => {
      const state = editorState.get(node.id);
      if (!state?.editor) return;
      let bg_image = result["bg_image"];
      if (Array.isArray(bg_image)) bg_image = bg_image[0];
      if (!bg_image) return;
      const img = new Image();
      img.src = `data:image/jpeg;base64,${bg_image}`;
      img.onload = () => {
        if (state.editor) state.editor.processImage(img);
      };
    });

    b.onConnectionsChanged((node, event) => {
      if (event.side !== "input") return;
      editorState.get(node.id)?.bgWatch?.refresh();
    });

    b.onRemoved((node) => teardownNode(node));
  }

  // ─── Shared constructor flow ───
  // Call from subclass constructor after setting up widgets and data.
  // editorKey: e.g. 'pointsEditor' or 'splineEditor'
  // heightKey: e.g. 'pointsEditorHeight' or 'splineEditorHeight'
  // heightOffset: pixels added to canvas height for full node height (e.g. 310 or 460)
  initEditor(editorKey, heightKey, heightOffset) {
    this._editorKey = editorKey;
    this._heightKey = heightKey;
    this._heightOffset = heightOffset;

    const state = stateFor(this.node);
    this.createCanvas(state[editorKey].element);

    if (this.width > 256) this.setNodeWidth(this.width + 45);
    state[heightKey] = this.height + 40;
    state[editorKey].element.style.height = `${state[heightKey]}px`;
    this.node.setSize({ width: this.node.getSize().width, height: this.height + heightOffset + buttonRowHeight });

    this.setupEventListeners();
    this.render();
  }

  // Shared onSizeChanged — uses stored heightKey/heightOffset
  onSizeChanged() {
    const state = stateFor(this.node);
    state[this._heightKey] = this.height + 40;
    state[this._editorKey].element.style.height = `${state[this._heightKey]}px`;
    this.node.setSize({ width: this.node.getSize().width, height: this.height + this._heightOffset + buttonRowHeight });
  }

  // Shared constructor preamble — cleanup, reset, context menu, coord/display init
  initEditorPreamble(editorKey, className) {
    this._className = className;
    this.cleanupPreviousEditor(this.node);
    const state = stateFor(this.node);
    if (this.reset && state[editorKey].element) {
      state[editorKey].element.innerHTML = '';
    }
    this.createContextMenu();
  }

  // Shared coord/display size init from widgets + saved node size
  initDisplaySize() {
    this.coordWidth = this.widthWidget.getValue();
    this.coordHeight = this.heightWidget.getValue();
    const savedWidth = Math.max(64, Math.round(this.node.getSize().width - 45));
    this.width = Math.min(savedWidth, maxDisplayDim);
    this.height = Math.round(this.width * (this.coordHeight / this.coordWidth));
  }

  // Shared context menu creation — clone to clear stale listeners, wire up action handlers
  createContextMenu() {
    const state = stateFor(this.node);
    const oldMenu = state.contextMenu;
    const newMenu = oldMenu.cloneNode(true);
    oldMenu.parentNode.replaceChild(newMenu, oldMenu);
    state.contextMenu = newMenu;
    this.setupContextMenuListeners(this._className);

    const self = this;
    newMenu.addEventListener('click', (e) => {
      e.preventDefault();
      if (e.target.tagName !== 'A') return;
      const id = e.target.dataset.menuId;
      const def = state.menuDef[id];
      if (def?.action) {
        def.action(self);
        self._updateMenuToggleStates();
      }
      newMenu.style.display = 'none';
    });
  }

  // Update toggle item styling from menu definitions
  _updateMenuToggleStates() {
    const state = stateFor(this.node);
    const menuDef = state.menuDef;
    state.contextMenu.querySelectorAll('a').forEach(item => {
      const def = menuDef[item.dataset.menuId];
      if (def?.toggle) {
        const on = def.toggle(this);
        item.style.color = on ? '#4fc3f7' : '#FFF';
        item.style.borderLeft = on ? '3px solid #4fc3f7' : '3px solid transparent';
        item.style.paddingLeft = '8px';
      }
    });
  }

  // ─── Hooks for subclasses ───
  // Override these instead of duplicating logic:

  // Called after data changes (render + update widgets)
  onDataChanged() {}

  // Called on image load for editor-specific state (e.g., drawRuler = false)
  onImageResize() {}

  // Called when coord space changes — override to rescale coordinates
  onCoordSpaceResized(_oldWidth, _oldHeight) {}
}
