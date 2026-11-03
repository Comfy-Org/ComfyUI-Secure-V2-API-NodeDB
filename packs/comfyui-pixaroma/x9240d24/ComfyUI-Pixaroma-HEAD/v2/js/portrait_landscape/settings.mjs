// Portrait Landscape Pixaroma - the floating settings panel (the gear).
//
// The size step is stored PER NODE (node.properties.portraitLandscapeState), not
// as a global setting, because the whole point is that one workflow can hold
// several of these set up differently. That is why this is a small custom panel
// rather than a `rows` entry on registerNodeAccent: those rows write a shared
// ComfyUI setting, which every node of the type would then follow.

import { app } from "../../../scripts/app.js";
import { createAccentSection, accentOf } from "../shared/node_settings.mjs";
import { MULTIPLES, readState, writeState } from "./state.mjs";

let PANEL = null;
let PANEL_NODE = null;
let _followRaf = 0;
let _userMoved = false;
let _cssDone = false;

const CLS = "pix-plp";

function injectCSS() {
  if (_cssDone) return;
  _cssDone = true;
  const s = document.createElement("style");
  s.textContent = `
  .${CLS}{
    position:fixed; z-index:10800; width:290px; max-height:82vh; overflow:auto;
    background:#2b2b2b; border:1px solid #444; border-radius:8px;
    box-shadow:0 10px 34px rgba(0,0,0,0.55);
    font:12px 'Segoe UI',sans-serif; color:#ddd;
  }
  .${CLS} .hd{
    display:flex; align-items:center; gap:7px; padding:8px 11px;
    background:#333; border-bottom:1px solid #444; cursor:move; user-select:none;
  }
  .${CLS} .hd b{ font-weight:500; font-size:12px; }
  .${CLS} .hd .x{
    margin-left:auto; background:none; border:none; color:#999; cursor:pointer;
    font-size:15px; line-height:1; padding:0 2px;
  }
  .${CLS} .hd .x:hover{ color:#fff; }
  .${CLS} .bd{ padding:11px; display:flex; flex-direction:column; gap:10px; }
  .${CLS} .lbl{
    font-size:11px; text-transform:uppercase; letter-spacing:.4px;
    color:var(--pix-acc,#f66744);
  }
  .${CLS} .pills{ display:flex; gap:4px; }
  .${CLS} .pill{
    flex:1; text-align:center; box-sizing:border-box;
    background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.14);
    border-radius:4px; color:rgba(255,255,255,0.72); font-size:11px;
    padding:5px 2px; cursor:pointer;
  }
  .${CLS} .pill:hover{ border-color:var(--pix-acc,#f66744); color:#ddd; }
  .${CLS} .pill.on, .${CLS} .pill.on:hover{
    background:var(--pix-acc,#f66744); border-color:var(--pix-acc,#f66744); color:#fff;
  }
  .${CLS} .note{ font-size:11px; color:rgba(255,255,255,0.45); line-height:1.5; }
  `;
  document.head.appendChild(s);
}

export function closePortraitPanelFor(node) {
  if (PANEL && (!node || PANEL_NODE === node)) closePanel();
}

function closePanel() {
  if (_followRaf) cancelAnimationFrame(_followRaf);
  _followRaf = 0;
  try { PANEL?.remove(); } catch {}
  PANEL = null;
  PANEL_NODE = null;
  // Reset on CLOSE, not on open, or one dragged panel teaches the next to sit
  // still where its node is not.
  _userMoved = false;
  document.removeEventListener("pointerdown", outsideClose, true);
  document.removeEventListener("keydown", escClose, true);
}

function outsideClose(e) {
  if (!PANEL) return;
  // The colour picker lives on document.body, OUTSIDE the panel, so without
  // this exception picking a colour would dismiss the panel underneath.
  if (PANEL.contains(e.target)
      || e.target?.closest?.(".pix-cp-popup, .pix-cp-modal-backdrop")) return;
  closePanel();
}

function escClose(e) {
  if (e.key === "Escape" && PANEL) { e.stopPropagation(); closePanel(); }
}

function place(node) {
  if (!PANEL) return;
  const canvas = app.canvas?.canvas, ds = app.canvas?.ds;
  if (!canvas || !ds) return;
  const r = canvas.getBoundingClientRect();
  const w = PANEL.offsetWidth || 290, h = PANEL.offsetHeight || 240;
  const scr = gx => r.left + (gx + ds.offset[0]) * ds.scale;
  const right = scr(node.pos[0] + (node.size?.[0] || 0)) + 12;
  const left = scr(node.pos[0]) - w - 12;
  // Prefer the right, flip to the LEFT when there is no room. Clamping instead
  // would slide the panel back OVER the node it is editing.
  let x = right;
  if (right + w > window.innerWidth - 8) x = left >= 8 ? left : Math.max(8, window.innerWidth - w - 8);
  const y = r.top + (node.pos[1] + ds.offset[1]) * ds.scale - 26;
  PANEL.style.left = `${Math.max(8, Math.min(window.innerWidth - w - 8, x))}px`;
  PANEL.style.top = `${Math.max(8, Math.min(window.innerHeight - h - 8, y))}px`;
}

/** Keep the panel with its node through zoom and pan (convention #29). */
function startFollowing(node) {
  const ds = app.canvas?.ds;
  if (!ds) return;
  let last = { s: ds.scale, x: ds.offset[0], y: ds.offset[1] };
  const tick = () => {
    if (!PANEL || PANEL_NODE !== node || !PANEL.isConnected) { _followRaf = 0; return; }
    _followRaf = requestAnimationFrame(tick);
    if (_userMoved) return;
    const d = app.canvas?.ds;
    if (!d) return;
    if (d.scale === last.s && d.offset[0] === last.x && d.offset[1] === last.y) return;
    last = { s: d.scale, x: d.offset[0], y: d.offset[1] };
    place(node);
  };
  _followRaf = requestAnimationFrame(tick);
}

export function openPortraitPanel(node, onChange) {
  injectCSS();
  if (PANEL && PANEL_NODE === node) { closePanel(); return; }
  closePanel();

  const panel = document.createElement("div");
  panel.className = CLS;
  panel.style.setProperty("--pix-acc", accentOf(node));
  PANEL = panel;
  PANEL_NODE = node;

  const hd = document.createElement("div");
  hd.className = "hd";
  const title = document.createElement("b");
  title.textContent = "Portrait Landscape settings";
  const x = document.createElement("button");
  x.className = "x";
  x.textContent = "✕";
  x.title = "Close";
  x.addEventListener("click", closePanel);
  hd.append(title, x);

  const bd = document.createElement("div");
  bd.className = "bd";
  panel.append(hd, bd);

  const rebuild = () => {
    bd.textContent = "";
    fill(bd, node, () => { onChange?.(node); rebuild(); });
  };
  rebuild();

  document.body.appendChild(panel);
  place(node);
  startFollowing(node);

  hd.addEventListener("pointerdown", (e) => {
    if (e.target === x) return;
    const sx = e.clientX, sy = e.clientY;
    const r = panel.getBoundingClientRect();
    try { hd.setPointerCapture(e.pointerId); } catch {}
    // setPointerCapture AND the buttons guard: a release that goes missing
    // otherwise leaves the panel stuck to the cursor (convention #20).
    const move = (mv) => {
      if (!(mv.buttons & 1)) { end(); return; }
      _userMoved = true;
      panel.style.left = `${Math.max(8, Math.min(window.innerWidth - r.width - 8, r.left + mv.clientX - sx))}px`;
      panel.style.top = `${Math.max(8, Math.min(window.innerHeight - r.height - 8, r.top + mv.clientY - sy))}px`;
    };
    const end = () => {
      hd.removeEventListener("pointermove", move);
      try { hd.releasePointerCapture(e.pointerId); } catch {}
    };
    hd.addEventListener("pointermove", move);
    hd.addEventListener("pointerup", end, { once: true });
    hd.addEventListener("pointercancel", end, { once: true });
    hd.addEventListener("lostpointercapture", end, { once: true });
  });

  document.addEventListener("pointerdown", outsideClose, true);
  document.addEventListener("keydown", escClose, true);
}

function fill(bd, node, changed) {
  const st = readState(node);

  const sec = document.createElement("div");
  const lbl = document.createElement("div");
  lbl.className = "lbl";
  lbl.textContent = "Round sizes to";
  sec.appendChild(lbl);

  const pills = document.createElement("div");
  pills.className = "pills";
  for (const m of MULTIPLES) {
    const p = document.createElement("div");
    p.className = "pill" + (st.multiple === m ? " on" : "");
    p.textContent = m === 0 ? "Off" : String(m);
    p.title = m === 0
      ? "Send the numbers exactly as you typed them"
      : `Round both numbers to the nearest ${m} pixels`;
    p.addEventListener("click", () => { writeState(node, { multiple: m }); changed(); });
    pills.appendChild(p);
  }
  sec.appendChild(pills);

  const note = document.createElement("div");
  note.className = "note";
  note.textContent = "Models usually want sizes in steps of 8, 16, 32 or 64. "
    + "This rounds to the NEAREST step, so 900 becomes 896 at 64. "
    + "This node only, and the button on the node does the same thing.";
  sec.appendChild(note);
  bd.appendChild(sec);

  try {
    bd.appendChild(createAccentSection(node, {
      onChange: () => {
        PANEL?.style.setProperty("--pix-acc", accentOf(node));
        changed();
      },
    }));
  } catch {}
}
