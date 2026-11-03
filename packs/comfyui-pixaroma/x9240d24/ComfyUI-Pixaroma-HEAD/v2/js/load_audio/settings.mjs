// Load Audio Pixaroma - the floating settings panel (the gear).
//
// Only the things that cannot live on the face: what to do when nothing is
// wired into the duration input, and what to do when the window runs off the
// end of the file. Both belong on the node rather than in ComfyUI's Settings
// panel, because two of these nodes on one canvas can want different answers
// (patterns/node-settings-accent.md).

import { app } from "../../../scripts/app.js";
import { accentOf, createAccentSection } from "../shared/node_settings.mjs";
import { passComfyShortcut } from "../shared/text_shortcuts.mjs";
import { readState, writeState } from "./core.mjs";

let PANEL = null;
let PANEL_NODE = null;
let _followRaf = 0;
let _userMoved = false;
let _cssDone = false;

const P = "pix-lap";

function injectCSS() {
  if (_cssDone) return;
  _cssDone = true;
  const css = `
  .${P}{
    position:fixed; z-index:10800; width:300px; max-height:82vh; overflow:auto;
    background:#2b2b2b; border:1px solid #444; border-radius:8px;
    box-shadow:0 10px 34px rgba(0,0,0,0.55);
    font:12px 'Segoe UI',sans-serif; color:#ddd;
  }
  .${P} .hd{
    display:flex; align-items:center; gap:7px; padding:8px 11px;
    background:#333; border-bottom:1px solid #444; cursor:move; user-select:none;
  }
  .${P} .hd b{ font-weight:500; font-size:12px; }
  .${P} .hd .x{
    margin-left:auto; background:none; border:none; color:#999; cursor:pointer;
    font-size:15px; line-height:1; padding:0 2px;
  }
  .${P} .hd .x:hover{ color:#fff; }
  .${P} .bd{ padding:11px; display:flex; flex-direction:column; gap:11px; }
  .${P} .sec{ display:flex; flex-direction:column; gap:6px; }
  .${P} .lbl{
    font-size:11px; text-transform:uppercase; letter-spacing:.4px;
    color:var(--pix-acc,#f66744);
  }
  .${P} .pills{ display:flex; gap:4px; }
  .${P} .pill{
    flex:1; text-align:center; box-sizing:border-box;
    background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.14);
    border-radius:4px; color:rgba(255,255,255,0.72); font-size:11px;
    padding:5px 4px; cursor:pointer;
  }
  .${P} .pill:hover{ border-color:var(--pix-acc,#f66744); color:#ddd; }
  .${P} .pill.on, .${P} .pill.on:hover{
    background:var(--pix-acc,#f66744); border-color:var(--pix-acc,#f66744); color:#fff;
  }
  .${P} .fld{
    background:#1d1d1d; border:1px solid #444; border-radius:4px;
    display:flex; align-items:center; justify-content:space-between; padding:4px 7px; gap:4px;
  }
  .${P} .fld:focus-within{ border-color:var(--pix-acc,#f66744); }
  .${P} .fld span{ font-size:10px; color:var(--pix-acc,#f66744); letter-spacing:.3px; }
  .${P} .fld input{
    width:70px; background:none; border:none; outline:none; text-align:right;
    color:var(--pix-acc,#f66744); font:12px 'Segoe UI',sans-serif;
  }
  .${P} .note{ font-size:11px; color:rgba(255,255,255,0.45); line-height:1.5; }
  `;
  const el = document.createElement("style");
  el.textContent = css;
  document.head.appendChild(el);
}

function section(title) {
  const s = document.createElement("div");
  s.className = "sec";
  const l = document.createElement("div");
  l.className = "lbl";
  l.textContent = title;
  s.appendChild(l);
  return s;
}

function pills(options, current, onPick) {
  const wrap = document.createElement("div");
  wrap.className = "pills";
  for (const [value, label, tip] of options) {
    const p = document.createElement("div");
    p.className = "pill" + (current === value ? " on" : "");
    p.textContent = label;
    p.title = tip;
    p.addEventListener("click", () => onPick(value));
    wrap.appendChild(p);
  }
  return wrap;
}

export function closeLoadAudioPanelFor(node) {
  if (PANEL && (!node || PANEL_NODE === node)) closePanel();
}

function closePanel() {
  if (_followRaf) cancelAnimationFrame(_followRaf);
  _followRaf = 0;
  try { PANEL?.remove(); } catch (_e) { /* already gone */ }
  PANEL = null;
  PANEL_NODE = null;
  // Reset on CLOSE, not open: on open it would teach the next panel to sit
  // still wherever the last one happened to be dragged (convention #29).
  _userMoved = false;
  document.removeEventListener("pointerdown", outsideClose, true);
  document.removeEventListener("keydown", escClose, true);
}

function outsideClose(e) {
  if (!PANEL) return;
  // The colour picker lives on document.body OUTSIDE the panel, and this guard
  // is capture-phase, so without the exception picking a colour would dismiss
  // the panel underneath (node-settings-accent.md invariant 3).
  if (PANEL.contains(e.target)
      || e.target?.closest?.(".pix-cp-popup, .pix-cp-modal-backdrop, .pix-nset-pop")) return;
  closePanel();
}

function escClose(e) {
  if (e.key === "Escape" && PANEL) { e.stopPropagation(); closePanel(); }
}

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

function place(node) {
  if (!PANEL) return;
  const canvas = app.canvas?.canvas;
  const ds = app.canvas?.ds;
  if (!canvas || !ds) return;
  const r = canvas.getBoundingClientRect();
  const w = PANEL.offsetWidth || 300;
  const h = PANEL.offsetHeight || 280;
  const scr = (gx) => r.left + (gx + ds.offset[0]) * ds.scale;
  const right = scr(node.pos[0] + (node.size?.[0] || 0)) + 12;
  const left = scr(node.pos[0]) - w - 12;
  // Flip to the left rather than clamp: clamping slides the panel back OVER the
  // node it is editing, which is the one place it must never sit.
  let x = right;
  if (right + w > window.innerWidth - 8) x = left >= 8 ? left : Math.max(8, window.innerWidth - w - 8);
  const y = r.top + (node.pos[1] + ds.offset[1]) * ds.scale - 26;
  PANEL.style.left = `${Math.max(8, Math.min(window.innerWidth - w - 8, x))}px`;
  PANEL.style.top = `${Math.max(8, Math.min(window.innerHeight - h - 8, y))}px`;
}

export function openLoadAudioPanel(node, onChange) {
  injectCSS();
  if (PANEL && PANEL_NODE === node) { closePanel(); return; }
  closePanel();

  const panel = document.createElement("div");
  panel.className = P;
  panel.style.setProperty("--pix-acc", accentOf(node));
  PANEL = panel;
  PANEL_NODE = node;

  const hd = document.createElement("div");
  hd.className = "hd";
  const title = document.createElement("b");
  title.textContent = "Load Audio settings";
  const close = document.createElement("button");
  close.className = "x";
  close.textContent = "✕";
  close.title = "Close";
  close.addEventListener("click", closePanel);
  hd.append(title, close);

  const bd = document.createElement("div");
  bd.className = "bd";
  panel.append(hd, bd);

  const rebuild = () => {
    const scroll = bd.scrollTop;
    bd.textContent = "";
    fill(bd, node, () => { onChange?.(node); rebuild(); });
    bd.scrollTop = scroll;
  };
  rebuild();

  document.body.appendChild(panel);
  place(node);
  startFollowing(node);

  hd.addEventListener("pointerdown", (e) => {
    if (e.target === close) return;
    const sx = e.clientX, sy = e.clientY;
    const r = panel.getBoundingClientRect();
    try { hd.setPointerCapture(e.pointerId); } catch (_x) { /* mouse only */ }
    const move = (mv) => {
      // The buttons guard, or a lost release sticks the panel to the cursor.
      if (!(mv.buttons & 1)) { end(); return; }
      _userMoved = true;
      panel.style.left = `${Math.max(8, Math.min(window.innerWidth - r.width - 8, r.left + mv.clientX - sx))}px`;
      panel.style.top = `${Math.max(8, Math.min(window.innerHeight - r.height - 8, r.top + mv.clientY - sy))}px`;
    };
    const end = () => {
      hd.removeEventListener("pointermove", move);
      try { hd.releasePointerCapture(e.pointerId); } catch (_x) { /* fine */ }
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

  const unwired = section("When nothing is wired in");
  unwired.appendChild(pills([
    ["whole", "Whole file", "Take everything from the start point to the end of the file."],
    ["length", "Use length", "Take the number of seconds set below."],
  ], st.whenUnwired, (v) => { writeState(node, { whenUnwired: v }); changed(); }));

  const fld = document.createElement("div");
  fld.className = "fld";
  const lb = document.createElement("span");
  lb.textContent = "LENGTH";
  const inp = document.createElement("input");
  inp.type = "text";
  inp.value = String(st.length);
  inp.addEventListener("keydown", (e) => {
    if (passComfyShortcut(e, inp, { blur: true })) return;   // save / run after the commit (UI#44)
    e.stopPropagation();
    if (e.key === "Enter") { e.preventDefault(); inp.blur(); }
  });
  inp.addEventListener("change", () => {
    const v = parseFloat(inp.value);
    if (Number.isFinite(v)) { writeState(node, { length: Math.max(0, v) }); changed(); }
  });
  fld.append(lb, inp);
  unwired.appendChild(fld);

  const note = document.createElement("div");
  note.className = "note";
  note.textContent = "Ignored while the duration dot is connected: the wire always wins.";
  unwired.appendChild(note);
  bd.appendChild(unwired);

  const short = section("If the file runs out");
  short.appendChild(pills([
    ["silence", "Silence", "Fill the rest of the window with real silence."],
    ["loop", "Loop", "Go back to the start of your selection and keep going."],
  ], st.whenShort, (v) => { writeState(node, { whenShort: v }); changed(); }));
  bd.appendChild(short);

  try {
    bd.appendChild(createAccentSection(node, {
      onChange: () => {
        PANEL?.style.setProperty("--pix-acc", accentOf(node));
        changed();
      },
    }));
  } catch (_e) { /* the colour block is a nicety, never a blocker */ }
}
