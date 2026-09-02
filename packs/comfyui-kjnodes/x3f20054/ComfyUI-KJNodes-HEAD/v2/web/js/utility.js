import { comfy } from '/comfy/api/v2.js';

// ─── General-purpose helpers shared across KJNodes JS ───

export function makeUUID() {
  let dt = new Date().getTime()
  const uuid = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = ((dt + Math.random() * 16) % 16) | 0
    dt = Math.floor(dt / 16)
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16)
  })
  return uuid
}

// Four exports of this module have no callers left, and each was infrastructure
// for the surface being retired rather than something a caller lost:
//   chainCallback     — the pack's prototype/callback monkey-patcher. Every site
//                       is now a registered listener (b.onExecuted, w.on('change')),
//                       which composes instead of depending on load order.
//   hideWidgetForGood — the origType/origComputeSize/origSerializeValue dance
//                       around type = 'converted-widget'. widget.setHidden(true)
//                       is the whole of it, and it cascades through linked
//                       widgets on its own.
//   clientToCanvas    — screen→graph conversion out of lgCanvas.ds.scale/offset.
//                       comfy.graph.pointerPosition() answers in graph space
//                       already, so callers never needed the transform.
//   getNodeAtPoint    — a linear scan of graph._nodes calling isPointInside.
//                       comfy.graph.nodeAt() is the renderer's own answer and
//                       respects z-order and collapsed nodes.

export function typesCompatible(a, b) {
  if (a === "*" || b === "*") return true;
  if (a === b) return true;
  if (typeof a !== "string" || typeof b !== "string") return false;
  if (a.toUpperCase() === b.toUpperCase()) return true;
  // ComfyUI accepts union types like "STRING,INT" — match if any token overlaps
  if (a.includes(",") || b.includes(",")) {
    const aTokens = a.toUpperCase().split(",").map(s => s.trim()).filter(Boolean);
    const bTokens = b.toUpperCase().split(",").map(s => s.trim()).filter(Boolean);
    if (aTokens.includes("*") || bTokens.includes("*")) return true;
    return aTokens.some(t => bTokens.includes(t));
  }
  return false;
}

// ─── Slot position helper ───
// The renderer's own answer, so it stays right for collapsed nodes, widget-backed
// inputs and layouts that are not the default vertical stack.
export function getSlotPos(node, isInput, slotIdx) {
  const pos = node.getSlotPosition(isInput ? "input" : "output", slotIdx);
  return pos ? [pos.x, pos.y] : null;
}

// ─── Middle-click pan passthrough for DOM widgets ───
//
// Previously: on middle-button mousedown over a mounted element, read
// app.canvas.ds.offset and .scale, then write ds.offset[0]/[1] on every
// mousemove and call app.canvas.setDirty(true, true) — re-implementing the
// editor's pan, including its screen-delta-over-scale correction.
//
// REFUSED, not a pending gap: driving the renderer's view transform. The
// published API gives setZoom and onViewportChanged, and onViewportChanged
// deliberately carries no payload because "the pan offset and zoom factor stay
// the renderer's business". A pack that writes ds.offset has adopted the
// renderer's coordinate model as its own, and it is that model Nodes 2.0
// replaces. Note the neighbouring addWheelPassthrough is NOT refused and is
// untouched: it re-dispatches the user's real wheel event to the canvas and
// lets the host zoom. A wheel tick is one stateless event, so forwarding is
// honest; a pan is a stateful gesture with pointer capture, and forwarding a
// synthesised pointerdown means owning the capture, the moves and the release —
// which is re-implementing the gesture, not delegating it.
//
// The capability is not refused. Panning while the pointer is over a pack's own
// widget is the host's to deliver, and the published drawing surface says so:
// CanvasDef.onPointerDown claims the primary button only, "Middle and right
// belong to panning and the context menu, which still have to work over the
// widget". What a pack must not do is claim the middle button itself — which is
// why editor_base's blanket e.stopPropagation() on pointerdown now lets the
// middle button through.
//
// DROPPED: for elements mounted with widgets.mount rather than widgets.canvas,
// the pack no longer emulates a pan the host does not deliver. Every call site
// and the helper itself are gone rather than left as a no-op, so nothing claims
// to pan and then does not.

// ─── Resolve preview image/video from a connected source node ───
// Walks the graph link to find what's connected to node.inputs[inputSlot]
// and returns { url, isVideo, videoEl } or null
export function resolveSourcePreview(node, inputSlot) {
  if (node.isDeleted) return null;
  const source = node.inputs.at(inputSlot)?.source();
  if (!source) return null;
  const srcNode = comfy.graph.node(source.nodeId);
  if (!srcNode) return null;

  // Previously the first source tried was another pack's DOM: VideoHelperSuite's
  // "videopreview" widget, read as srcNode.widgets.find(...).videoEl.src to
  // borrow its live <video> element.
  //
  // REFUSED, not a pending gap: reaching into another pack's widget object for
  // the element it mounted. A mounted element belongs to whoever mounted it —
  // its lifetime, its readiness and its name are that pack's, and none of the
  // three is promised to this one. Publishing a way to reach it would make
  // every pack's internal DOM part of every other pack's contract.
  //
  // DROPPED: a VHS video source is no longer previewed from its live element
  // before the node has run. The two paths below still cover it afterwards —
  // a LoadVideo "video" widget resolves to a /view URL, and getOutputImages()
  // covers what the node is showing, previews included.

  // Look for a LoadImage "image" widget or LoadVideo "video" widget
  const w = srcNode.widgets.get("image") ?? srcNode.widgets.get("video");
  if (w?.getValue()) {
    let subfolder = "", fname = w.getValue();
    const lastSlash = fname.lastIndexOf("/");
    if (lastSlash >= 0) { subfolder = fname.substring(0, lastSlash); fname = fname.substring(lastSlash + 1); }
    const isVideo = w.name === "video";
    const url = comfy.backend.url(`/view?filename=${encodeURIComponent(fname)}&type=input&subfolder=${encodeURIComponent(subfolder)}`);
    return { url, isVideo };
  }

  // Fallback: the images the source produced when it last ran
  const [executed] = srcNode.getOutputImages();
  if (executed) {
    return { url: executed, isVideo: false };
  }
  return null;
}

// ─── Source input watcher ───
// Watches a named IMAGE input for connection changes and source widget changes.
// Calls onChange(sources) when connections change or the source node's image/video widget changes.
// sources: array of { url, isVideo } per connected IMAGE input matching inputName (or all if inputName is null).
//
// Returns { refresh, stop }. The original chained node.onConnectionsChange and
// node.onRemoved on the instance from in here; connection and removal callbacks
// are declared per node type now, which is where the two callers already are —
// so the subscription moves out to them and this stays a plain function:
//
//   const watch = watchImageInputs(node, "image", onSources);
//   b.onConnectionsChanged((n, e) => { if (e.side === "input") watch.refresh(); });
//   b.onRemoved(() => watch.stop());
export function watchImageInputs(node, inputName, onChange) {
  let watchedWidgets = [];

  function unwatchWidgets() {
    for (const unwatch of watchedWidgets) unwatch();
    watchedWidgets = [];
  }

  function resolve() {
    if (node.isDeleted) return [];
    const slots = inputName
      ? node.inputs.all().map((inp, i) => inp.name === inputName ? i : -1).filter(i => i >= 0)
      : node.inputs.all().map((inp, i) => inp.type === "IMAGE" ? i : -1).filter(i => i >= 0);
    return slots.map(i => resolveSourcePreview(node, i)).filter(s => s !== null);
  }

  function watch() {
    unwatchWidgets();
    if (node.isDeleted) return;
    const slots = inputName
      ? node.inputs.all().map((inp, i) => inp.name === inputName ? i : -1).filter(i => i >= 0)
      : node.inputs.all().map((inp, i) => inp.type === "IMAGE" ? i : -1).filter(i => i >= 0);
    for (const slotIdx of slots) {
      const source = node.inputs.at(slotIdx)?.source();
      if (!source) continue;
      const srcNode = comfy.graph.node(source.nodeId);
      if (!srcNode) continue;
      const w = srcNode.widgets.get("image") ?? srcNode.widgets.get("video");
      if (!w) continue;
      watchedWidgets.push(w.on("change", () => {
        setTimeout(() => onChange(resolve()), 100);
      }));
    }
  }

  function refresh() {
    watch();
    onChange(resolve());
  }

  refresh();

  return { refresh, stop: unwatchWidgets };
}

// ─── Video frame capture ───
// Draws the current frame of a video element to a fresh canvas at native resolution.
// If the video isn't decoded yet (readyState < 2), waits once for "loadeddata" before capturing.
// Calls callback(canvas) with the resulting canvas. Caller decides whether to use it directly
// (drawImage accepts canvas) or convert via toDataURL.
export function captureVideoFrame(videoEl, callback) {
  const capture = () => {
    if (!videoEl.videoWidth || !videoEl.videoHeight) return;
    const c = document.createElement("canvas");
    c.width = videoEl.videoWidth;
    c.height = videoEl.videoHeight;
    c.getContext("2d").drawImage(videoEl, 0, 0);
    callback(c);
  };
  if (videoEl.readyState >= 2) {
    capture();
  } else {
    const onReady = () => { videoEl.removeEventListener("loadeddata", onReady); capture(); };
    videoEl.addEventListener("loadeddata", onReady);
  }
}

// ─── Bounding box hit test ───
// Tests whether (mx, my) hits a corner handle or the interior of a rect defined by (x1, y1)–(x2, y2).
// Returns "resize-tl", "resize-tr", "resize-bl", "resize-br", "resize-t", "resize-b", "resize-l", "resize-r", "move", or null.
export function rectHitTest(mx, my, x1, y1, x2, y2, radius) {
  const hit = (cx, cy) => Math.abs(mx - cx) < radius && Math.abs(my - cy) < radius;
  // Corners first (higher priority)
  if (hit(x1, y1)) return "resize-tl";
  if (hit(x2, y1)) return "resize-tr";
  if (hit(x1, y2)) return "resize-bl";
  if (hit(x2, y2)) return "resize-br";
  // Edges
  if (mx >= x1 && mx <= x2 && Math.abs(my - y1) < radius) return "resize-t";
  if (mx >= x1 && mx <= x2 && Math.abs(my - y2) < radius) return "resize-b";
  if (my >= y1 && my <= y2 && Math.abs(mx - x1) < radius) return "resize-l";
  if (my >= y1 && my <= y2 && Math.abs(mx - x2) < radius) return "resize-r";
  // Interior
  if (mx >= x1 && mx <= x2 && my >= y1 && my <= y2) return "move";
  return null;
}

// Returns the appropriate CSS cursor for a bbox hit mode string.
export function cursorForBboxMode(mode) {
  if (mode === "move") return "move";
  if (mode === "resize-tl" || mode === "resize-br") return "nwse-resize";
  if (mode === "resize-tr" || mode === "resize-bl") return "nesw-resize";
  if (mode === "resize-t" || mode === "resize-b") return "ns-resize";
  if (mode === "resize-l" || mode === "resize-r") return "ew-resize";
  return null;
}

// ─── Wheel zoom passthrough for DOM widgets ───
// Re-dispatches wheel events to the graph canvas for zoom
export function addWheelPassthrough(element) {
  element.addEventListener("wheel", (e) => {
    const gc = document.getElementById("graph-canvas");
    if (gc) {
      gc.dispatchEvent(new WheelEvent(e.type, e));
      e.preventDefault();
    }
  }, { passive: false });
}

