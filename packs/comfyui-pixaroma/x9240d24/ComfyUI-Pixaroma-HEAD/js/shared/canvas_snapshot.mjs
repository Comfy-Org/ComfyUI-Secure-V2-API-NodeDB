// ╔═══════════════════════════════════════════════════════════════╗
// ║  Canvas snapshot: a node-body canvas that costs nothing idle  ║
// ╚═══════════════════════════════════════════════════════════════╝
//
// WHY THIS EXISTS (measured 2026-09-26, D:\Claude Tests\_perf_bench, CLAUDE.md
// node UI convention #41). A <canvas> on screen in a Nodes 2.0 node body costs
// the browser's GPU process work on EVERY frame the page draws, even when
// nothing on it changes - and while a run goes, ComfyUI redraws the page several
// times a second. That work is taken out of the generation: three Image Compare
// nodes made an SD1.5 render 3-4% slower (GPU-process CPU +0.68 s per run).
// The SAME pixels shown as an <img> cost nothing (+0.04 s; the render time fell
// back to what any three extra nodes cost). A CPU canvas (willReadFrequently)
// did NOT help - it is the canvas being on screen, not how it is drawn.
//
// So a node canvas shows a lossless PICTURE of itself while it is static, and
// the live canvas only while it is being drawn. The node calls `changed()` at
// the end of every render: the live canvas comes back at once, and after
// `idleMs` with no further render it is encoded (PNG, lossless) into an <img>
// laid exactly over it, and the canvas is hidden.
//
// Rules it relies on, each one load-bearing:
//  - The picture never adds layout: FILL mode copies an absolute canvas's own
//    inline style, OVERLAY mode is absolute inside a host the node does not
//    measure (the two modes are described just above the function). An in-flow
//    canvas with no host gets a no-op handle.
//  - Show/hide is VISIBILITY on both elements, never `hidden`/display: the
//    copied style carries display:block, which beats the hidden attribute, and
//    visibility keeps both boxes so nothing moves.
//  - Pointer events keep going to the node's own root: a visibility:hidden
//    canvas and a pointer-events:none image are never hit.
//  - A render always wins: every changed() bumps a generation number, and a
//    snapshot that lands after a newer render is thrown away unseen.
//  - It degrades to today's behavior (the live canvas stays up) when toBlob
//    throws (a tainted canvas) or yields nothing.
//  - dispose() on teardown (renderer switch, node removed): it revokes the
//    object URL, removes the image and leaves the canvas visible.

const NOOP = { changed() {}, dispose() {}, get showing() { return "canvas"; } };

// A snapshot is a PNG encode, and past a few megapixels its synchronous part
// stalls the page. MEASURED (2026-09-26, a photo + text, RTX 2060): 1.6 Mpx
// 11 ms on the main thread, 5 Mpx 29 ms, 10 Mpx 78 ms, 24 Mpx (the backing cap
// of a big node zoomed far in) 186 ms plus a 19 MB image held in memory. Above
// this the live canvas simply stays, which is exactly the behavior before this
// helper existed; normal node sizes are far below it.
const MAX_SNAPSHOT_PX = 6e6;

// TWO WAYS TO LAY THE PICTURE OVER THE CANVAS:
//  - FILL (no opts.host): the canvas fills its box by itself with an INLINE
//    position:absolute (Compare, Preview Image). The picture is its sibling and
//    copies its inline style, so it covers the same pixels. No bookkeeping.
//  - OVERLAY (opts.host): the canvas sits in the normal flow, or is placed by a
//    CSS class. The picture goes into `host` - a POSITIONED ancestor whose
//    children the node does NOT count when it measures its own height (an extra
//    child there can grow a saved node on load, Vue Compat #18) - and is placed
//    over the canvas's box each time it is shown. The box is summed up the
//    offsetParent chain, which is in layout pixels, so the graph zoom's CSS
//    transform never enters into it. If `host` is not in that chain, or the
//    canvas is not laid out, the swap simply never happens (the live canvas
//    stays - today's behavior). A style watcher hides the picture whenever the
//    node hides the canvas itself (display:none for the Classic look), and a
//    resize watcher re-places it if the box moves while it is showing.
export function attachCanvasSnapshot(canvas, opts = {}) {
  if (!canvas || !canvas.parentNode) return NOOP;
  const host = opts.host || null;
  const fill = !host && (canvas.style.position || "") === "absolute";
  if (!fill && !host) return NOOP;
  const idleMs = opts.idleMs ?? 400;

  const img = document.createElement("img");
  img.className = "pix-canvas-snapshot";
  img.alt = "";
  img.draggable = false;
  img.decoding = "async";
  if (fill) {
    img.style.cssText = canvas.style.cssText;
  } else {
    img.style.cssText = "position:absolute;left:0;top:0;width:0;height:0;margin:0;padding:0;"
      + "border:0;display:block;box-sizing:border-box;";
  }
  img.style.pointerEvents = "none";
  img.style.visibility = "hidden";
  if (fill) canvas.insertAdjacentElement("afterend", img);
  else host.appendChild(img);

  let url = null;
  let timer = 0;
  let gen = 0;
  let disposed = false;
  let showing = "canvas";

  const showCanvas = () => {
    canvas.style.visibility = "";
    img.style.visibility = "hidden";
    showing = "canvas";
  };

  // OVERLAY only: put the picture exactly over the canvas's box, relative to
  // the host's padding edge. offsetLeft/Top are measured from the offsetParent's
  // padding edge, so each intermediate offsetParent's border (clientLeft/Top)
  // is added back. Returns false when the box cannot be found.
  const placeOverlay = () => {
    if (fill) return true;
    let x = 0, y = 0, e = canvas;
    while (e && e !== host) {
      x += e.offsetLeft;
      y += e.offsetTop;
      const p = e.offsetParent;
      if (p && p !== host) { x += p.clientLeft; y += p.clientTop; }
      e = p;
    }
    if (e !== host || !canvas.offsetWidth || !canvas.offsetHeight) return false;
    img.style.left = x + "px";
    img.style.top = y + "px";
    img.style.width = canvas.offsetWidth + "px";
    img.style.height = canvas.offsetHeight + "px";
    return true;
  };

  let mo = null;
  let ro = null;
  if (!fill) {
    const standDown = () => { gen++; clearTimeout(timer); timer = 0; showCanvas(); };
    try {
      mo = new MutationObserver(() => {
        if (showing === "image" && canvas.style.display === "none") standDown();
      });
      mo.observe(canvas, { attributes: true, attributeFilter: ["style"] });
    } catch (_e) { mo = null; }
    try {
      ro = new ResizeObserver(() => {
        if (showing === "image" && !placeOverlay()) standDown();
      });
      ro.observe(canvas);
      ro.observe(host);
    } catch (_e) { ro = null; }
  }

  const snapshot = () => {
    timer = 0;
    if (disposed || !canvas.isConnected || !canvas.width || !canvas.height) return;
    if (canvas.width * canvas.height > MAX_SNAPSHOT_PX) return;
    const my = gen;
    try {
      canvas.toBlob((blob) => {
        if (disposed || my !== gen || !blob) return;
        const next = URL.createObjectURL(blob);
        img.src = next;
        img.decode().then(() => {
          if (disposed || my !== gen) { URL.revokeObjectURL(next); return; }
          if (url && url !== next) URL.revokeObjectURL(url);
          url = next;
          if (!fill && (canvas.style.display === "none" || !placeOverlay())) return;
          img.style.visibility = "visible";
          canvas.style.visibility = "hidden";
          showing = "image";
        }, () => {
          URL.revokeObjectURL(next);
        });
      }, "image/png");
    } catch (_e) {
      // A tainted canvas cannot be read back: keep the live canvas.
    }
  };

  return {
    // Call at the END of every render (the canvas now holds the new pixels).
    changed() {
      if (disposed) return;
      gen++;
      showCanvas();
      clearTimeout(timer);
      timer = setTimeout(snapshot, idleMs);
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      gen++;
      clearTimeout(timer);
      try { mo?.disconnect(); } catch (_e) { /* ignore */ }
      try { ro?.disconnect(); } catch (_e) { /* ignore */ }
      canvas.style.visibility = "";
      try { img.remove(); } catch (_e) { /* ignore */ }
      if (url) URL.revokeObjectURL(url);
      url = null;
    },
    get showing() { return showing; },
  };
}
