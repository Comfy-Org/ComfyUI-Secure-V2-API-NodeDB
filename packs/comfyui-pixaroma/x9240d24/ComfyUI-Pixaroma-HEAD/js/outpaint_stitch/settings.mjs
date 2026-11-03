// Outpaint Stitch Pixaroma - the floating "Slider colour" panel (same pattern as
// Sliders Pixaroma / Run Timer / Save Image: themed panel beside the node,
// draggable by its header, closes on outside click or Esc). Slim: the only thing
// here is the accent colour (per node, with a global default), so nobody is
// forced into the Pixaroma orange.

import { app } from "../../../scripts/app.js";
import { isVueNodes } from "../shared/nodes2.mjs";
import { openPixaromaColorPickerPopup, BUTTON_PALETTE } from "../shared/color_picker.mjs";
import { accentOf, setAccent, BRAND, ACCENT_SETTING } from "./core.mjs";
import { GLOBAL_ACCENT_SETTING, repaintAllAccents } from "../shared/node_settings.mjs";

let _panel = null;
let _panelNode = null;
let _onChange = null;
let _cpHandle = null;

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}

function injectCSS() {
  if (document.getElementById("pix-opsp-css")) return;
  const s = document.createElement("style");
  s.id = "pix-opsp-css";
  s.textContent = `
    .pix-opsp { position:fixed; z-index:10010; width:360px; max-width:94vw; background:#1a1a1a;
      border:1px solid #3a3a3a; border-radius:10px; box-shadow:0 18px 50px rgba(0,0,0,0.6);
      color:#d8d8d8; font:12px 'Segoe UI',-apple-system,sans-serif; overflow:hidden; }
    .pix-opsp-t { display:flex; align-items:center; gap:8px; padding:10px 12px; background:#232323;
      border-bottom:1px solid #333; cursor:grab; user-select:none; }
    .pix-opsp-t .x { margin-left:auto; color:#8a8a8a; cursor:pointer; padding:0 4px; }
    .pix-opsp-t .x:hover { color:#fff; }
    .pix-opsp-b { padding:14px 12px; }
    .pix-opsp-acc { display:flex; align-items:center; gap:10px; }
    .pix-opsp-acc .lab { font-size:12px; color:#cfcfcf; }
    .pix-opsp-acc .sub { font-size:11px; color:#8a8a8a; margin-top:2px; }
    .pix-opsp-sw { width:34px; height:24px; border-radius:5px; border:1px solid #555; cursor:pointer; flex:none; }
    .pix-opsp-sw:hover { border-color:#fff; }
    .pix-opsp-f { display:flex; gap:8px; padding:10px 12px; border-top:1px solid #333; background:#1f1f1f; }
    .pix-opsp-btn { border:1px solid #444; background:rgba(255,255,255,0.04); color:#d8d8d8; border-radius:5px;
      padding:5px 12px; font:12px 'Segoe UI',sans-serif; cursor:pointer; }
    .pix-opsp-btn:hover { border-color:var(--acc,${BRAND}); color:#fff; }
    .pix-opsp-push { margin-left:auto; }
  `;
  document.head.appendChild(s);
}

function getNodeScreenRect(node) {
  if (isVueNodes() && node && node.id != null) {
    const e = document.querySelector(`[data-node-id="${node.id}"]`);
    if (e) return e.getBoundingClientRect();
  }
  const c = app.canvas;
  const ds = c && c.ds;
  const cv = c && c.canvas;
  if (!ds || !cv || !node?.pos || !node?.size) return null;
  const cr = cv.getBoundingClientRect();
  const titleH = window.LiteGraph?.NODE_TITLE_HEIGHT || 30;
  const sc = ds.scale || 1;
  const off = ds.offset || [0, 0];
  const left = cr.left + (node.pos[0] + off[0]) * sc;
  const top = cr.top + (node.pos[1] - titleH + off[1]) * sc;
  const width = node.size[0] * sc;
  const height = (node.size[1] + titleH) * sc;
  return { left, top, right: left + width, bottom: top + height, width, height };
}

function placeBeside(panel, rect) {
  const vw = window.innerWidth, vh = window.innerHeight;
  const mw = panel.offsetWidth, mh = panel.offsetHeight;
  const gap = 12, pad = 8;
  if (!rect) {
    panel.style.left = Math.max(pad, (vw - mw) / 2) + "px";
    panel.style.top = Math.max(pad, (vh - mh) / 2) + "px";
    return;
  }
  let left = rect.right + gap;
  if (left + mw > vw - pad) left = rect.left - gap - mw;
  if (left < pad) left = Math.max(pad, vw - mw - pad);
  let top = rect.top;
  if (top + mh > vh - pad) top = vh - mh - pad;
  if (top < pad) top = pad;
  panel.style.left = left + "px";
  panel.style.top = top + "px";
}

function makeDraggable(panel, handle) {
  handle.addEventListener("pointerdown", (e) => {
    if (e.target.closest(".x")) return;
    e.preventDefault();
    const r = panel.getBoundingClientRect();
    const ox = e.clientX - r.left, oy = e.clientY - r.top;
    // Both defences against a LOST pointerup (convention #20, the same pair as
    // js/shared/node_panel.mjs): when the release never arrives (pointer left
    // the window, capture taken) the panel followed the cursor until a click.
    try { handle.setPointerCapture(e.pointerId); } catch { /* not fatal */ }
    let done = false;
    const move = (ev) => {
      if (!panel.isConnected) return up();
      if (!(ev.buttons & 1)) return up(); // we missed the release
      panel.style.left = Math.max(0, Math.min(window.innerWidth - panel.offsetWidth, ev.clientX - ox)) + "px";
      panel.style.top = Math.max(0, Math.min(window.innerHeight - panel.offsetHeight, ev.clientY - oy)) + "px";
    };
    const up = () => {
      if (done) return; // idempotent: the guard above can call this too
      done = true;
      try { handle.releasePointerCapture(e.pointerId); } catch { /* already gone */ }
      window.removeEventListener("pointermove", move, true);
      window.removeEventListener("pointerup", up, true);
      window.removeEventListener("pointercancel", up, true);
      handle.removeEventListener("lostpointercapture", up);
    };
    window.addEventListener("pointermove", move, true);
    window.addEventListener("pointerup", up, true);
    window.addEventListener("pointercancel", up, true);
    handle.addEventListener("lostpointercapture", up);
  });
}

function outsideClose(e) {
  if (!_panel) return;
  if (_panel.contains(e.target)) return;
  if (e.target.closest?.(".pix-cp-popup, .pix-cp-modal-backdrop")) return; // the colour picker
  closeOpsPanel();
}
function escClose(e) {
  if (e.key === "Escape" && _panel) {
    if (document.querySelector(".pix-cp-popup, .pix-cp-modal-backdrop")) return;
    e.stopPropagation();
    closeOpsPanel();
  }
}

export function closeOpsPanel() {
  try { _cpHandle?.close(); } catch {}
  _cpHandle = null;
  if (_panel) { try { _panel.remove(); } catch {} }
  _panel = null;
  _panelNode = null;
  _onChange = null;
  document.removeEventListener("pointerdown", outsideClose, true);
  document.removeEventListener("keydown", escClose, true);
}

export function closeOpsPanelFor(node) {
  if (_panelNode === node) closeOpsPanel();
}

export function openOpsPanel(node, onChange) {
  closeOpsPanel();
  injectCSS();
  _onChange = onChange || null;
  _panelNode = node;

  const panel = el("div", "pix-opsp");
  panel.style.setProperty("--acc", accentOf(node));

  const title = el("div", "pix-opsp-t");
  title.append(el("span", null, "⚙"), el("span", null, "Slider colour"));
  const x = el("span", "x", "✕");
  x.addEventListener("click", closeOpsPanel);
  title.appendChild(x);

  const body = el("div", "pix-opsp-b");

  const sw = el("div", "pix-opsp-sw");
  sw.title = "Pick the colour these sliders paint with";
  sw.style.background = accentOf(node);

  const repaintAccent = () => {
    const a = accentOf(node);
    panel.style.setProperty("--acc", a);
    sw.style.background = a;
  };

  sw.addEventListener("click", () => {
    // The LIVE picker (roomy SV plane + hue + hex + button-safe swatches) so the
    // sliders recolour live as you drag. No transparent tile - an accent is
    // always a colour. Reset -> the Pixaroma orange.
    _cpHandle = openPixaromaColorPickerPopup(sw, {
      initialColor: accentOf(node),
      swatches: BUTTON_PALETTE,
      wide: true,
      resetColor: BRAND,
      onPick: (c) => {
        setAccent(node, c || BRAND);
        repaintAccent();
        _onChange?.();   // sliders repaint live
      },
    });
  });

  const acc = el("div", "pix-opsp-acc");
  const txt = el("div");
  txt.appendChild(el("div", "lab", "Slider colour"));
  txt.appendChild(el("div", "sub", "This node only. Set the default for new ones below."));
  acc.append(sw, txt);
  body.appendChild(acc);

  const foot = el("div", "pix-opsp-f");
  const mkDefault = el("button", "pix-opsp-btn", "Colour as default");
  mkDefault.title = "Use this node's colour for every new Outpaint Stitch node";
  mkDefault.addEventListener("click", async () => {
    try {
      await app.ui.settings.setSettingValueAsync(ACCENT_SETTING, accentOf(node));
      mkDefault.textContent = "Saved as default";
      setTimeout(() => { mkDefault.textContent = "Colour as default"; }, 1200);
    } catch {}
  });
  const done = el("button", "pix-opsp-btn pix-opsp-push", "Done");
  done.addEventListener("click", closeOpsPanel);

  // The SECOND default: one master colour every Pixaroma node follows unless it
  // (or its node type) has been given one of its own. Written through the shared
  // helper so all the panels agree on the key.
  const mkAll = el("button", "pix-opsp-btn", "Every Pixaroma node");
  mkAll.title = "Every Pixaroma node follows this colour, unless it has been given one of its own";
  mkAll.addEventListener("click", async () => {
    try {
      await app.ui.settings.setSettingValueAsync(GLOBAL_ACCENT_SETTING, accentOf(node));
      mkAll.textContent = "Saved";
      setTimeout(() => { mkAll.textContent = "Every Pixaroma node"; }, 1200);
      repaintAllAccents();
    } catch { /* settings not ready */ }
  });
  foot.append(mkDefault, mkAll, done);

  panel.append(title, body, foot);
  document.body.appendChild(panel);

  placeBeside(panel, getNodeScreenRect(node));
  makeDraggable(panel, title);

  setTimeout(() => {
    if (!_panel) return;
    document.addEventListener("pointerdown", outsideClose, true);
    document.addEventListener("keydown", escClose, true);
  }, 0);
  _panel = panel;
}
