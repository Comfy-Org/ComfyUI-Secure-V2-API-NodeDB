/**
 * The "batch" stepper Resolution Pixaroma and Sizes Pixaroma show on the level
 * of their `latent` output dot (Discord 2026-10-17: two people asked for a batch
 * size on that latent). It sits in the empty space LEFT of the output labels, so
 * it costs the node no height and adds no widget: the number lives in the node's
 * own hidden state (`batch`, absent = 1), which the graphToPrompt hook already
 * sends, and Python hands it to core's Empty Latent Image.
 *
 * Placement is per renderer, the Longest Side recipe (longest-side.md #1, #1b):
 * - CLASSIC: the band lives in the node's widget root and is lifted onto the slot
 *   row with `placeSlotBand` (computed from the node box, no constant to retune).
 * - NODES 2.0: Vue clips anything above the widget top, so the band is PARKED in
 *   the output-slot block and aligned to the real slot element.
 * Vue replaces the node element on re-render and a renderer flip moves the root,
 * so a light 350 ms check (one per node, stops when the node leaves the graph)
 * re-parks / re-mounts it and keeps the number in step after Ctrl+Z. Every write
 * here is the band's own DOM; only a user's click or typing writes the state.
 */
import { isVueNodes } from "./nodes2.mjs";
import { passComfyShortcut } from "./text_shortcuts.mjs";
import { notifyGraphChanged } from "./graph_changed.mjs";
import { placeSlotBand, BAND_H } from "./slot_band.mjs";
import { accentOf } from "./node_settings.mjs";

export const BATCH_MIN = 1;
export const BATCH_MAX = 64;

/** A saved or typed value as a batch size (anything unusable = 1). */
export function clampBatch(v) {
  const n = Math.round(Number(v));
  if (!Number.isFinite(n)) return 1;
  return Math.min(BATCH_MAX, Math.max(BATCH_MIN, n));
}

let _css = false;
function injectCSS() {
  if (_css) return;
  _css = true;
  const s = document.createElement("style");
  s.id = "pix-latent-batch-css";
  s.textContent = `
.pix-lb-band { position:absolute; height:${BAND_H}px; display:flex; align-items:center; gap:4px;
  pointer-events:none; z-index:2; font-size:11px; white-space:nowrap; }
.pix-lb-band > * { pointer-events:auto; }
.pix-lb-band .pix-lb-lbl { pointer-events:none; color:rgba(255,255,255,0.72); margin-right:2px; }
/* The pack's bordered small control (pixaroma-ui: idle #1d1d1d / #444 / #aaa, hover = accent border, no fill).
   22 px wide with a 4 px gap: centres 26 px apart, so each keeps the 24 px target spacing (WCAG 2.5.8). */
.pix-lb-btn { flex:none; width:22px; height:20px; box-sizing:border-box; padding:0; border-radius:4px;
  border:1px solid #444; background:#1d1d1d; color:#aaa; font-family:inherit; font-weight:700; font-size:13px; line-height:1;
  display:flex; align-items:center; justify-content:center; cursor:pointer; user-select:none; }
.pix-lb-btn:hover { border-color:var(--pix-acc,#f66744); color:#ddd; }
.pix-lb-btn:disabled, .pix-lb-btn:disabled:hover { opacity:0.35; cursor:default; border-color:#444; color:#aaa; }
/* A sunken field you can type in: #1d1d1d / #444 / #e0e0e0, accent border on focus. */
.pix-lb-val { flex:none; width:30px; height:20px; box-sizing:border-box; padding:0; border-radius:4px;
  border:1px solid #444; background:#1d1d1d; color:#e0e0e0; text-align:center; outline:none;
  font-family:inherit; font-weight:600; font-size:11px; }
.pix-lb-val:focus { border-color:var(--pix-acc,#f66744); }
.pix-lb-band.parked { left:8px; }
`;
  document.head.appendChild(s);
}

function vueSlotBlock(el) {
  return el?.querySelector(".lg-slot--output")?.parentElement?.parentElement || null;
}

/**
 * Put the batch stepper on `node`.
 *   opts.outputIndex  which output dot it sits beside (the latent one)
 *   opts.getRoot()    the node's widget root (Classic home of the band)
 *   opts.read()       the current batch (number)
 *   opts.write(n)     store a new batch in the node's state
 *   opts.accent()     optional: the node's colour when it is not the shared accent chain
 * Returns { mount, refresh, uninstall }. Call mount() after anything that empties
 * the root (Resolution's render wipes it).
 */
export function installLatentBatch(node, opts) {
  injectCSS();
  const band = document.createElement("div");
  band.className = "pix-lb-band";
  band.title = "How many pictures the latent output makes in one run (1 to " + BATCH_MAX + ").";
  const lbl = document.createElement("span");
  lbl.className = "pix-lb-lbl";
  lbl.textContent = "batch";
  const dec = document.createElement("button");
  dec.className = "pix-lb-btn pix-lb-dec";
  dec.type = "button";
  dec.textContent = "−";
  dec.title = "One picture fewer";
  dec.setAttribute("aria-label", "Batch size: one fewer");
  const val = document.createElement("input");
  val.className = "pix-lb-val";
  val.type = "text";
  val.inputMode = "numeric";
  val.spellcheck = false;
  val.title = "Batch size: how many pictures the latent makes per run (1 to " + BATCH_MAX + ")";
  val.setAttribute("aria-label", "Batch size");
  const inc = document.createElement("button");
  inc.className = "pix-lb-btn pix-lb-inc";
  inc.type = "button";
  inc.textContent = "+";
  inc.title = "One picture more";
  inc.setAttribute("aria-label", "Batch size: one more");
  band.append(lbl, dec, val, inc);

  const show = () => {
    // The node's own colour, set on the band itself: in Nodes 2.0 it is parked
    // OUTSIDE the root and would not inherit it (longest-side.md #28). A node that
    // keeps its colour elsewhere (Sizes: in its state) passes opts.accent.
    const acc = opts.accent ? opts.accent() : accentOf(node);
    if (band.style.getPropertyValue("--pix-acc") !== acc) band.style.setProperty("--pix-acc", acc);
    const b = clampBatch(opts.read());
    if (document.activeElement !== val && val.value !== String(b)) val.value = String(b);
    dec.disabled = b <= BATCH_MIN;
    inc.disabled = b >= BATCH_MAX;
  };
  const commit = (n) => {
    const b = clampBatch(n);
    if (b !== clampBatch(opts.read())) {
      opts.write(b);
      notifyGraphChanged();
    }
    val.value = String(b);
    show();
  };

  // The buttons and the box must not start a node drag or a canvas pan.
  for (const el of [dec, val, inc]) {
    el.addEventListener("pointerdown", (e) => e.stopPropagation());
    el.addEventListener("mousedown", (e) => e.stopPropagation());
  }
  dec.addEventListener("click", (e) => { e.stopPropagation(); commit(clampBatch(opts.read()) - 1); });
  inc.addEventListener("click", (e) => { e.stopPropagation(); commit(clampBatch(opts.read()) + 1); });
  val.addEventListener("keydown", (e) => {
    if (passComfyShortcut(e, val, { blur: true })) return;
    e.stopPropagation();
    if (e.key === "Enter") { e.preventDefault(); val.blur(); }
    else if (e.key === "Escape") { val.value = String(clampBatch(opts.read())); val.blur(); }
    else if (e.key === "ArrowUp") { e.preventDefault(); commit(clampBatch(opts.read()) + 1); }
    else if (e.key === "ArrowDown") { e.preventDefault(); commit(clampBatch(opts.read()) - 1); }
  });
  // Typed text: an empty box or anything that is not a number puts the current
  // value back instead of quietly writing 1 (review 2026-10-17); 0 / 999 clamp.
  const commitTyped = () => {
    const txt = String(val.value).trim();
    if (!txt || !Number.isFinite(Number(txt))) { val.value = String(clampBatch(opts.read())); show(); return; }
    commit(txt);
  };
  val.addEventListener("change", commitTyped);
  val.addEventListener("blur", commitTyped);
  val.addEventListener("focus", () => val.select());

  const place = () => {
    try {
      if (isVueNodes()) {
        const root = opts.getRoot();
        const el = document.querySelector(`.lg-node[data-node-id="${node.id}"]`);
        // data-node-id is not page-unique (subgraph ids restart at 1): prove it is ours.
        if (!el || !root || !el.contains(root)) return;
        const block = vueSlotBlock(el);
        if (!block) return;
        if (band.parentElement !== block) {
          if (getComputedStyle(block).position === "static") block.style.position = "relative";
          block.appendChild(band);
        }
        band.classList.add("parked");
        const slot = block.querySelectorAll('[class*="lg-slot--output"]')[opts.outputIndex];
        if (slot) {
          const scale = (block.getBoundingClientRect().height / (block.offsetHeight || 1)) || 1;
          const sr = slot.getBoundingClientRect();
          const br = block.getBoundingClientRect();
          band.style.top = Math.round((sr.top + sr.height / 2 - br.top) / scale - BAND_H / 2) + "px";
          // Line up with the node's own controls: the root's left edge plus its
          // content inset (the chips / pills start that far in).
          const rr = root.getBoundingClientRect();
          band.style.left = Math.round((rr.left - br.left) / scale + (opts.inset ?? 8)) + "px";
        }
        band.style.right = "auto";
      } else {
        const root = opts.getRoot();
        if (!root) return;
        band.classList.remove("parked");
        if (band.parentElement !== root) {
          if (getComputedStyle(root).position === "static") root.style.position = "relative";
          root.insertBefore(band, root.firstChild);
        }
        // Core hides the widget (v-show) while the node is off-screen or in another graph: its box reads as zeros
        // and placing then would park the band far from the row until the next check. The offsets do not change
        // with pan or zoom, so the last good place is still right when the node comes back (review 2026-10-17).
        if (!root.getClientRects().length) return;
        placeSlotBand(node, band, { side: "left", slot: "output", index: opts.outputIndex });
      }
    } catch { /* leave it where it is; the next check tries again */ }
  };

  let timer = null;
  const tick = () => {
    if (!node.graph) { uninstall(); return; }
    place();
    show();
  };
  const mount = () => { place(); show(); };
  function uninstall() {
    if (timer) clearInterval(timer);
    timer = null;
    try { band.remove(); } catch {}
  }
  timer = setInterval(tick, 350);
  queueMicrotask(mount);
  requestAnimationFrame(mount);
  return { band, mount, refresh: show, uninstall };
}
