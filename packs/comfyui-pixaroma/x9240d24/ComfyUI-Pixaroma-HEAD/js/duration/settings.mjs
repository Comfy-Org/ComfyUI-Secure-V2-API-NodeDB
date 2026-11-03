// Duration Pixaroma - the floating settings panel (the gear).
//
// Holds the two things that make one node different from another: which
// durations are allowed, and how seconds become frames. Both are stored ON the
// node, so two Duration nodes on one canvas can be set up for two models.

import { app } from "../../../scripts/app.js";
import { createAccentSection, accentOf } from "../shared/node_settings.mjs";
import { passComfyShortcut } from "../shared/text_shortcuts.mjs";
import {
  PICK_CHIPS, PICK_SLIDER, PICK_NUMBER, readState, writeState, clampToPick,
} from "./core.mjs";
import { RECIPES, CUSTOM_NAME, recipePatch, matchRecipe } from "./recipes.mjs";
import { computeLocal } from "./compute.mjs";
import { previewCustom } from "./api.mjs";

let PANEL = null;
let PANEL_NODE = null;
let _followRaf = 0;
let _userMoved = false;
let _cssDone = false;

const PANEL_CLASS = "pix-durp";

function injectCSS() {
  if (_cssDone) return;
  _cssDone = true;
  const css = `
  .${PANEL_CLASS}{
    position:fixed; z-index:10800; width:330px; max-height:82vh; overflow:auto;
    background:#2b2b2b; border:1px solid #444; border-radius:8px;
    box-shadow:0 10px 34px rgba(0,0,0,0.55);
    font:12px 'Segoe UI',sans-serif; color:#ddd;
  }
  .${PANEL_CLASS} .hd{
    display:flex; align-items:center; gap:7px; padding:8px 11px;
    background:#333; border-bottom:1px solid #444; cursor:move; user-select:none;
  }
  .${PANEL_CLASS} .hd b{ font-weight:500; font-size:12px; }
  .${PANEL_CLASS} .hd .x{
    margin-left:auto; background:none; border:none; color:#999; cursor:pointer;
    font-size:15px; line-height:1; padding:0 2px;
  }
  .${PANEL_CLASS} .hd .x:hover{ color:#fff; }
  .${PANEL_CLASS} .bd{ padding:11px; display:flex; flex-direction:column; gap:11px; }
  .${PANEL_CLASS} .sec{ display:flex; flex-direction:column; gap:6px; }
  .${PANEL_CLASS} .lbl{
    font-size:11px; text-transform:uppercase; letter-spacing:.4px;
    color:var(--pix-acc,#f66744);
  }
  .${PANEL_CLASS} .pills{ display:flex; gap:4px; }
  .${PANEL_CLASS} .pill{
    flex:1; text-align:center; box-sizing:border-box;
    background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.14);
    border-radius:4px; color:rgba(255,255,255,0.72); font-size:11px;
    padding:5px 4px; cursor:pointer;
  }
  .${PANEL_CLASS} .pill:hover{ border-color:var(--pix-acc,#f66744); color:#ddd; }
  .${PANEL_CLASS} .pill.on, .${PANEL_CLASS} .pill.on:hover{
    background:var(--pix-acc,#f66744); border-color:var(--pix-acc,#f66744); color:#fff;
  }
  .${PANEL_CLASS} input[type=text], .${PANEL_CLASS} textarea{
    box-sizing:border-box; width:100%; background:#1d1d1d; border:1px solid #444;
    border-radius:4px; color:#e0e0e0; font:12px monospace; padding:6px 8px; outline:none;
  }
  .${PANEL_CLASS} input[type=text]:focus, .${PANEL_CLASS} textarea:focus{
    border-color:var(--pix-acc,#f66744);
  }
  .${PANEL_CLASS} textarea{ resize:vertical; min-height:52px; }
  .${PANEL_CLASS} .grid3{ display:flex; gap:6px; }
  .${PANEL_CLASS} .fld{
    flex:1; min-width:0; background:#1d1d1d; border:1px solid #444; border-radius:4px;
    display:flex; align-items:center; justify-content:space-between; padding:4px 7px; gap:4px;
  }
  .${PANEL_CLASS} .fld:focus-within{ border-color:var(--pix-acc,#f66744); }
  .${PANEL_CLASS} .fld span{ font-size:10px; color:var(--pix-acc,#f66744); letter-spacing:.3px; }
  .${PANEL_CLASS} .fld input{
    width:52px; background:none; border:none; outline:none; text-align:right;
    color:var(--pix-acc,#f66744); font:12px 'Segoe UI',sans-serif;
  }
  .${PANEL_CLASS} .prev{
    background:rgba(0,0,0,0.25); border-radius:4px; padding:7px 9px;
    font:11px/1.6 monospace; color:rgba(255,255,255,0.8); white-space:pre;
    max-height:132px; overflow:auto;
  }
  .${PANEL_CLASS} .prev .n{ color:var(--pix-acc,#f66744); }
  .${PANEL_CLASS} .note{ font-size:11px; color:rgba(255,255,255,0.45); line-height:1.5; }
  `;
  const el = document.createElement("style");
  el.textContent = css;
  document.head.appendChild(el);
}

function num(el) { const v = parseFloat(el.value); return Number.isFinite(v) ? v : null; }

function section(title) {
  const s = document.createElement("div");
  s.className = "sec";
  const l = document.createElement("div");
  l.className = "lbl";
  l.textContent = title;
  s.appendChild(l);
  return s;
}

function field(label, value, onChange, title) {
  const f = document.createElement("div");
  f.className = "fld";
  const s = document.createElement("span");
  s.textContent = label;
  const i = document.createElement("input");
  i.type = "text";
  i.value = String(value);
  if (title) f.title = title;
  i.addEventListener("change", () => { const v = num(i); if (v !== null) onChange(v); });
  i.addEventListener("keydown", (e) => {
    if (passComfyShortcut(e, i, { blur: true })) return;   // save / run after the commit (UI#44)
    e.stopPropagation();
    if (e.key === "Enter") { e.preventDefault(); i.blur(); }
  });
  f.append(s, i);
  return f;
}

/** The live preview: what each allowed duration turns into, before any run. */
function buildPreview(node, onDone) {
  const box = document.createElement("div");
  box.className = "prev";
  const st = readState(node);
  const list = st.pick === PICK_CHIPS
    ? st.values
    : (() => {
        // A range cannot list every value, so show the ends and the middle -
        // enough to see the pattern and spot a recipe that is wrong.
        const lo = Math.min(st.min, st.max), hi = Math.max(st.min, st.max);
        const out = [lo, lo + (hi - lo) / 2, hi].map((v) => clampToPick(st, v));
        return [...new Set(out)];
      })();

  const render = (rows) => {
    box.textContent = "";
    for (const r of rows) {
      const line = document.createElement("div");
      const secs = document.createElement("span");
      secs.textContent = String(r.seconds).padStart(6, " ") + " s  →  ";
      const n = document.createElement("span");
      n.className = "n";
      n.textContent = r.frames + " frames";
      line.append(secs, n);
      if (r.note) {
        const note = document.createElement("span");
        note.textContent = "  " + r.note;
        note.style.color = "rgba(255,255,255,0.4)";
        line.appendChild(note);
      }
      box.appendChild(line);
    }
    onDone?.();
  };

  if (st.mode !== "custom" || !String(st.formula || "").trim()) {
    render(list.map((v) => {
      const c = computeLocal({ ...st, seconds: v });
      return {
        seconds: v, frames: c.frames,
        note: Math.abs(c.actual - v) > 0.005 ? `(really ${Math.round(c.actual * 100) / 100} s)` : "",
      };
    }));
  } else {
    box.textContent = "working it out...";
    Promise.all(list.map((v) => previewCustom(node, { ...st, seconds: v })
      .then((res) => ({
        seconds: v,
        frames: res?.ok ? res.frames : (res?.frames ?? 0),
        note: res?.ok ? "" : "(formula does not work)",
      })))).then(render);
  }
  return box;
}

export function closeDurationPanelFor(node) {
  if (PANEL && (!node || PANEL_NODE === node)) closePanel();
}

function closePanel() {
  if (_followRaf) cancelAnimationFrame(_followRaf);
  _followRaf = 0;
  try { PANEL?.remove(); } catch {}
  PANEL = null;
  PANEL_NODE = null;
  // Reset on CLOSE, not on open: doing it on open would teach the next panel to
  // sit still wherever the last one was dragged.
  _userMoved = false;
  document.removeEventListener("pointerdown", outsideClose, true);
  document.removeEventListener("keydown", escClose, true);
}

function outsideClose(e) {
  if (!PANEL) return;
  // The colour picker and its modal live on document.body, OUTSIDE the panel, so
  // without this exception picking an accent dismisses the panel underneath.
  if (PANEL.contains(e.target) || e.target?.closest?.(".pix-cp-popup, .pix-cp-modal-backdrop")) return;
  closePanel();
}

function escClose(e) {
  if (e.key === "Escape" && PANEL) { e.stopPropagation(); closePanel(); }
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

function place(node) {
  if (!PANEL) return;
  const canvas = app.canvas?.canvas;
  const ds = app.canvas?.ds;
  if (!canvas || !ds) return;
  const r = canvas.getBoundingClientRect();
  const w = PANEL.offsetWidth || 330;
  const h = PANEL.offsetHeight || 300;
  const scr = (gx) => r.left + (gx + ds.offset[0]) * ds.scale;
  const right = scr(node.pos[0] + (node.size?.[0] || 0)) + 12;
  const left = scr(node.pos[0]) - w - 12;
  // Prefer the right of the node, but flip to the LEFT when there is no room
  // rather than clamping - clamping slides the panel back OVER the node it is
  // editing, which is the one thing it must never cover.
  let x = right;
  if (right + w > window.innerWidth - 8) x = left >= 8 ? left : Math.max(8, window.innerWidth - w - 8);
  const y = r.top + (node.pos[1] + ds.offset[1]) * ds.scale - 26;
  // Final viewport clamp. Panning the node off-screen would otherwise carry the
  // panel off with it, leaving an open panel you cannot reach or close by hand.
  PANEL.style.left = `${Math.max(8, Math.min(window.innerWidth - w - 8, x))}px`;
  PANEL.style.top = `${Math.max(8, Math.min(window.innerHeight - h - 8, y))}px`;
}

export function openDurationPanel(node, onChange) {
  injectCSS();
  if (PANEL && PANEL_NODE === node) { closePanel(); return; }
  closePanel();

  const panel = document.createElement("div");
  panel.className = PANEL_CLASS;
  panel.style.setProperty("--pix-acc", accentOf(node));
  PANEL = panel;
  PANEL_NODE = node;

  const hd = document.createElement("div");
  hd.className = "hd";
  const title = document.createElement("b");
  title.textContent = "Duration settings";
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

  // Drag by the header. setPointerCapture AND the buttons guard, or a lost
  // release leaves the panel stuck to the cursor (convention #20).
  hd.addEventListener("pointerdown", (e) => {
    if (e.target === close) return;
    const sx = e.clientX, sy = e.clientY;
    const r = panel.getBoundingClientRect();
    try { hd.setPointerCapture(e.pointerId); } catch {}
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

  // ── How you pick ─────────────────────────────────────────────────────────
  const pickSec = section("How you pick");
  const pills = document.createElement("div");
  pills.className = "pills";
  for (const [mode, label, tip] of [
    [PICK_CHIPS, "Buttons", "Show one button per allowed length. Best for a few choices."],
    [PICK_SLIDER, "Slider", "Drag between a smallest and largest length."],
    [PICK_NUMBER, "Type it", "Type any length inside the range."],
  ]) {
    const p = document.createElement("div");
    p.className = "pill" + (st.pick === mode ? " on" : "");
    p.textContent = label;
    p.title = tip;
    p.addEventListener("click", () => {
      const next = writeState(node, { pick: mode });
      writeState(node, { seconds: clampToPick(next, next.seconds) });
      changed();
    });
    pills.appendChild(p);
  }
  pickSec.appendChild(pills);
  bd.appendChild(pickSec);

  // ── Allowed durations ────────────────────────────────────────────────────
  const allowed = section("Allowed durations");
  if (st.pick === PICK_CHIPS) {
    const input = document.createElement("input");
    input.type = "text";
    input.value = st.values.join(", ");
    input.title = "The lengths to offer, in seconds, separated by commas";
    input.addEventListener("keydown", (e) => {
      if (passComfyShortcut(e, input, { blur: true })) return;   // save / run after the commit (UI#44)
      e.stopPropagation();
      if (e.key === "Enter") { e.preventDefault(); input.blur(); }
    });
    input.addEventListener("change", () => {
      const values = input.value.split(",").map((s) => parseFloat(s.trim()))
        .filter((v) => Number.isFinite(v) && v >= 0);
      if (!values.length) { changed(); return; }
      const next = writeState(node, { values });
      writeState(node, { seconds: clampToPick(next, next.seconds) });
      changed();
    });
    allowed.appendChild(input);
    const note = document.createElement("div");
    note.className = "note";
    note.textContent = "Up to 12 lengths. They are sorted for you.";
    allowed.appendChild(note);
  } else {
    const row = document.createElement("div");
    row.className = "grid3";
    row.append(
      field("MIN", st.min, (v) => {
        const next = writeState(node, { min: v });
        writeState(node, { seconds: clampToPick(next, next.seconds) });
        changed();
      }, "Shortest length you can pick"),
      field("MAX", st.max, (v) => {
        const next = writeState(node, { max: v });
        writeState(node, { seconds: clampToPick(next, next.seconds) });
        changed();
      }, "Longest length you can pick"),
      field("STEP", st.stepSec, (v) => {
        const next = writeState(node, { stepSec: v });
        writeState(node, { seconds: clampToPick(next, next.seconds) });
        changed();
      }, "How much the slider moves at a time"),
    );
    allowed.appendChild(row);
  }
  bd.appendChild(allowed);

  // ── Convert to frames ────────────────────────────────────────────────────
  const conv = section("Convert to frames");
  const active = matchRecipe(st);
  const recipePills = document.createElement("div");
  recipePills.className = "pills";
  recipePills.style.flexWrap = "wrap";
  for (const r of [...RECIPES, { name: CUSTOM_NAME, hint: "write your own" }]) {
    const p = document.createElement("div");
    p.className = "pill" + (active === r.name ? " on" : "");
    p.textContent = r.name;
    p.title = r.hint || "";
    p.style.flex = "1 1 44%";
    p.addEventListener("click", () => {
      const patch = recipePatch(r.name);
      if (patch) writeState(node, patch);
      changed();
    });
    recipePills.appendChild(p);
  }
  conv.appendChild(recipePills);

  if (st.mode === "custom") {
    const ta = document.createElement("textarea");
    ta.value = st.formula;
    ta.placeholder = "max(5, round(a * 24))";
    ta.title = "a is the length in seconds. fps and seconds are available too.";
    ta.addEventListener("keydown", (e) => { if (passComfyShortcut(e, ta, { blur: true })) return; e.stopPropagation(); });
    ta.addEventListener("change", () => { writeState(node, { formula: ta.value }); changed(); });
    conv.appendChild(ta);
    const note = document.createElement("div");
    note.className = "note";
    note.textContent = "a is the length in seconds. You can also use fps. "
      + "If the formula does not work the node falls back to the numbers above.";
    conv.appendChild(note);
  } else {
    const row = document.createElement("div");
    row.className = "grid3";
    row.append(
      field("FPS", st.fps, (v) => { writeState(node, { fps: v }); changed(); },
        "Frames per second the model runs at"),
      field("STEP", st.step, (v) => { writeState(node, { step: Math.trunc(v) }); changed(); },
        "Frame count must land on a multiple of this. 1 means no rounding."),
      field("PLUS", st.plus, (v) => { writeState(node, { plus: Math.trunc(v) }); changed(); },
        "Added on top of the multiple, so 17 and 5 means 17, 34, 51 ... plus 5"),
    );
    conv.appendChild(row);
    const row2 = document.createElement("div");
    row2.className = "grid3";
    row2.append(field("LEAST", st.minFrames,
      (v) => { writeState(node, { minFrames: Math.trunc(v) }); changed(); },
      "Never send fewer frames than this"));
    conv.appendChild(row2);
  }
  bd.appendChild(conv);

  // ── What it will send ────────────────────────────────────────────────────
  const prev = section("What it will send");
  prev.appendChild(buildPreview(node));
  bd.appendChild(prev);

  // ── Accent ───────────────────────────────────────────────────────────────
  try {
    bd.appendChild(createAccentSection(node, {
      onChange: () => {
        PANEL?.style.setProperty("--pix-acc", accentOf(node));
        changed();
      },
    }));
  } catch {}
}
