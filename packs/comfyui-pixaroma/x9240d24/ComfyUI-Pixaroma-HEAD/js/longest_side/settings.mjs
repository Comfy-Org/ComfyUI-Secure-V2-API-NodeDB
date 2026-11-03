// Longest Side Pixaroma - the floating settings panel (the gear).
//
// Everything here is PER NODE (node.properties.longestSideState), not a shared
// ComfyUI setting, so one workflow can hold several of these set up for
// different jobs. That is why it is a custom panel rather than `rows` on
// registerNodeAccent: those rows write a shared setting every node of the type
// would then follow.

import { app } from "../../../scripts/app.js";
import { createAccentSection, accentOf } from "../shared/node_settings.mjs";
import {
  readState, writeState, snapToMultiple, MAX_ROW_ITEMS, LOCKED_RATIO, STEPS,
  DEFAULT_SIZES, DEFAULT_RATIOS, RATIO_CHOICES, ANCHORS, RESAMPLES,
  MIN_DIM, MAX_DIM,
} from "./core.mjs";

let PANEL = null;
let PANEL_NODE = null;
let _followRaf = 0;
let _userMoved = false;
let _cssDone = false;
// The colour picker lives on document.body, outside the panel, so closing the
// panel programmatically (node deleted, workflow loaded) would otherwise strand
// it over the canvas with its own document listeners still attached.
let _cpHandle = null;

const CLS = "pix-lsp";

function injectCSS() {
  if (_cssDone) return;
  _cssDone = true;
  const s = document.createElement("style");
  s.textContent = `
  .${CLS}{
    position:fixed; z-index:10800; width:300px; max-height:82vh; overflow:auto;
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
  .${CLS} .bd{ padding:11px; display:flex; flex-direction:column; gap:13px; }
  .${CLS} .sec{ display:flex; flex-direction:column; gap:6px; }
  .${CLS} .lbl{
    font-size:11px; text-transform:uppercase; letter-spacing:.4px;
    color:var(--pix-acc,#f66744); display:flex; align-items:center; gap:6px;
  }
  .${CLS} .lbl .rst{
    margin-left:auto; text-transform:none; letter-spacing:0; font-size:10px;
    color:rgba(255,255,255,0.4); background:none; border:none; cursor:pointer;
    padding:0; font-family:inherit;
  }
  .${CLS} .lbl .rst:hover{ color:var(--pix-acc,#f66744); }
  .${CLS} .grid3{ display:grid; grid-template-columns:repeat(3,1fr); gap:4px; }
  .${CLS} input[type=text]{
    box-sizing:border-box; width:100%; background:#1d1d1d; color:#e0e0e0;
    border:1px solid #444; border-radius:4px; padding:5px 6px;
    font:12px 'Segoe UI',sans-serif; outline:none; text-align:center;
  }
  .${CLS} input[type=text]:focus{ border-color:var(--pix-acc,#f66744); }
  .${CLS} input[type=text].bad{ border-color:#c0504a; color:#e79b95; }
  .${CLS} .pills{ display:flex; gap:4px; flex-wrap:wrap; }
  .${CLS} .pill{
    flex:1 1 auto; min-width:0; text-align:center; box-sizing:border-box;
    background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.14);
    border-radius:4px; color:rgba(255,255,255,0.72); font-size:11px;
    padding:5px 6px; cursor:pointer; font-family:inherit; white-space:nowrap;
  }
  .${CLS} .pill:hover{ border-color:var(--pix-acc,#f66744); color:#ddd; }
  .${CLS} .pill.on, .${CLS} .pill.on:hover{
    background:var(--pix-acc,#f66744); border-color:var(--pix-acc,#f66744); color:#fff;
  }
  /* The 3x3 crop anchor. Borderless cells inside a bordered box, so they hover
     with a white bg tint rather than a border (UI convention #13). */
  .${CLS} .anchor{
    display:grid; grid-template-columns:repeat(3,1fr); gap:1px;
    background:#444; border:1px solid #444; border-radius:4px; overflow:hidden;
    width:96px;
  }
  .${CLS} .acell{
    height:26px; background:#1d1d1d; cursor:pointer; border:none; padding:0;
  }
  .${CLS} .acell:hover{ background:rgba(255,255,255,0.18); }
  .${CLS} .acell.on{ background:var(--pix-acc,#f66744); }
  .${CLS} .rowline{ display:flex; align-items:center; gap:8px; }
  .${CLS} .rowline label{ cursor:pointer; }
  /* accent-color, or the browser draws its own BLUE, which is not in the brand
     and reads as unfinished (UI convention #13b). */
  .${CLS} input[type=checkbox]{ accent-color:var(--pix-acc,#f66744); cursor:pointer; }
  .${CLS} .note{ font-size:11px; color:rgba(255,255,255,0.45); line-height:1.5; }
  /* The shape palette: every shape on offer, the ones on the row lit up. */
  .${CLS} .sugg{ display:flex; gap:4px; flex-wrap:wrap; }
  .${CLS} .chip{
    background:#1d1d1d; border:1px solid #444; border-radius:4px;
    color:rgba(255,255,255,0.6); font-size:11px; padding:4px 8px; cursor:pointer;
    font-family:inherit; min-width:38px; text-align:center;
  }
  .${CLS} .chip:hover{ border-color:var(--pix-acc,#f66744); color:#ddd; }
  .${CLS} .chip.on, .${CLS} .chip.on:hover{
    background:var(--pix-acc,#f66744); border-color:var(--pix-acc,#f66744); color:#fff;
  }
  /* keep is always on the row, so it must not look clickable. */
  .${CLS} .chip.locked{ cursor:default; opacity:0.8; }
  .${CLS} .chip.locked:hover{ border-color:var(--pix-acc,#f66744); }
  `;
  document.head.appendChild(s);
}

export function closeLongestSidePanelFor(node) {
  if (PANEL && (!node || PANEL_NODE === node)) closePanel();
}

function closePanel() {
  try { _cpHandle?.close?.(); } catch {}
  _cpHandle = null;
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
  // The gear must be exempt too, or it can never CLOSE the panel: this is a
  // capture-phase pointerdown, so pressing the gear closed the panel here and
  // the click that followed immediately reopened it - and because closePanel
  // resets _userMoved, a panel the user had dragged aside snapped back to the
  // node. Looked like "the gear does nothing". Reproduced with a real pointer
  // sequence; a synthetic .click() does NOT show it, because it fires no
  // pointerdown. Switching from one node's gear to another still works: that
  // click reaches openLongestSidePanel with a different node, which closes the
  // previous panel before opening its own.
  if (e.target?.closest?.(".pix-ls-gear")) return;
  // Let a half-typed field COMMIT before the panel goes. This runs in the
  // CAPTURE phase, so without this the panel is torn down before the browser
  // moves focus, the input is detached with a pending edit, and no `change`
  // event ever fires - typing a size and then clicking the canvas silently
  // threw the value away. Blurring first fires `change` synchronously.
  try {
    const active = document.activeElement;
    if (active && PANEL.contains(active)) active.blur?.();
  } catch { /* committing is best-effort; closing must still happen */ }
  closePanel();
}

function escClose(e) {
  if (e.key !== "Escape" || !PANEL) return;
  // Do not swallow Escape belonging to the Help or Workflows windows. This is a
  // CAPTURE listener on document and theirs bubble on their own element, so
  // without the exemption ours always wins: reading the Help window with this
  // panel open, Escape closed the panel and left the window up. The shared
  // settings panel carries the same exemption.
  if (e.target?.closest?.(".pixhb-win, .pixwb-win")) return;
  e.stopPropagation();
  closePanel();
}

function place(node) {
  if (!PANEL) return;
  const canvas = app.canvas?.canvas, ds = app.canvas?.ds;
  if (!canvas || !ds) return;
  const r = canvas.getBoundingClientRect();
  const w = PANEL.offsetWidth || 300, h = PANEL.offsetHeight || 300;
  const scr = (gx) => r.left + (gx + ds.offset[0]) * ds.scale;
  const right = scr(node.pos[0] + (node.size?.[0] || 0)) + 12;
  const left = scr(node.pos[0]) - w - 12;
  // Prefer the right, flip LEFT when there is no room. Clamping instead would
  // slide the panel back over the node it is editing.
  let x = right;
  if (right + w > window.innerWidth - 8) x = left >= 8 ? left : Math.max(8, window.innerWidth - w - 8);
  const y = r.top + (node.pos[1] + ds.offset[1]) * ds.scale - 26;
  PANEL.style.left = `${Math.max(8, Math.min(window.innerWidth - w - 8, x))}px`;
  PANEL.style.top = `${Math.max(8, Math.min(window.innerHeight - h - 8, y))}px`;
}

/** Keep the panel with its node through zoom and pan (UI convention #29). */
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

export function openLongestSidePanel(node, onChange) {
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
  title.textContent = "Longest Side settings";
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
    fill(bd, node, (full) => { onChange?.(node); if (full) rebuild(); });
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
    // otherwise leaves the panel stuck to the cursor (UI convention #20).
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

function section(parent, labelText, onReset) {
  const sec = document.createElement("div");
  sec.className = "sec";
  const lbl = document.createElement("div");
  lbl.className = "lbl";
  lbl.append(document.createTextNode(labelText));
  if (onReset) {
    const rst = document.createElement("button");
    rst.className = "rst";
    rst.textContent = "reset";
    rst.title = "Put the defaults back";
    rst.addEventListener("click", onReset);
    lbl.appendChild(rst);
  }
  sec.appendChild(lbl);
  parent.appendChild(sec);
  return sec;
}

function fill(bd, node, changed) {
  const st = readState(node);

  // ── the step ─────────────────────────────────────────────────────────────
  // Same control as the button on the node. It is first because it also
  // constrains what you can type into the size tabs below.
  {
    const sec = section(bd, "Round sizes to");
    const pills = document.createElement("div");
    pills.className = "pills";
    for (const m of STEPS) {
      const p = document.createElement("button");
      p.className = "pill" + (st.step === m ? " on" : "");
      p.textContent = m === 0 ? "Off" : String(m);
      p.title = m === 0
        ? "Send sizes exactly as they are"
        : `Round both sides to the nearest ${m} pixels`;
      p.addEventListener("click", () => { writeState(node, { step: m }); changed(true); });
      pills.appendChild(p);
    }
    sec.appendChild(pills);
    const note = document.createElement("div");
    note.className = "note";
    note.textContent = "Most models want sizes in steps like these. This node only, "
      + "and the small button on the node does the same thing.";
    sec.appendChild(note);
  }

  // ── size tabs ────────────────────────────────────────────────────────────
  // Typed, because a size is any number you like. The grid IS the row you will
  // see, in the order you will see it, and it costs a fraction of the height an
  // add/remove list would. A blank slot simply drops that tab.
  {
    const sec = section(bd, "Size tabs", () => {
      writeState(node, { sizes: [...DEFAULT_SIZES] });
      changed(true);
    });
    const grid = document.createElement("div");
    grid.className = "grid3";
    for (let i = 0; i < MAX_ROW_ITEMS; i++) {
      const inp = document.createElement("input");
      inp.type = "text";
      inp.value = st.sizes[i] != null ? String(st.sizes[i]) : "";
      // The last value this slot successfully held, so a typo can be refused
      // WITHOUT losing the size that was there. Kept on the element rather than
      // by index, because blank slots make list indices and input indices
      // drift apart.
      inp.dataset.good = inp.value;
      inp.placeholder = "-";
      inp.title = st.step > 0
        ? `A size for the row, rounded to the nearest ${st.step}. Blank drops this tab.`
        : "A size for the row. Blank drops this tab.";
      inp.addEventListener("change", () => {
        const step = readState(node).step;
        const vals = [];
        const inputs = [...grid.querySelectorAll("input")];
        for (const el of inputs) {
          const raw = el.value.trim();
          el.classList.remove("bad");
          if (!raw) { el.dataset.good = ""; continue; }   // blank drops a tab, deliberately
          let n = Math.trunc(Number(raw));
          if (!Number.isFinite(n) || n < MIN_DIM || n > MAX_DIM) {
            // Refuse the typo but KEEP the size that was there. Before this a
            // mistyped character deleted that tab outright and shifted every
            // later one left, with no feedback - the .bad style existed in the
            // stylesheet and was applied to nothing.
            el.classList.add("bad");
            el.title = `Not a size between ${MIN_DIM} and ${MAX_DIM}. The previous value is kept.`;
            const keep = Math.trunc(Number(el.dataset.good));
            if (Number.isFinite(keep) && keep >= MIN_DIM) vals.push(keep);
            continue;
          }
          // A typed size obeys the SAME step as the output, so a tab can never
          // promise a number the run would immediately round away from.
          if (step > 0) n = snapToMultiple(n, step);
          vals.push(n);
        }
        // Never leave the row empty - a node with no size tabs cannot be used
        // and there would be no way back from the face.
        const next = vals.length ? vals : [...DEFAULT_SIZES];
        writeState(node, { sizes: next });

        // changed(FALSE): repaint the node face but do NOT rebuild the panel
        // body. A rebuild here destroys every other control between the
        // mousedown and the mouseup of whatever the user clicked next, so
        // clicking a step pill (or reset, or an anchor cell) right after typing
        // a size did nothing at all and had to be clicked twice. Nothing else
        // in this panel depends on the size list, so writing the normalised
        // values straight back into the fields is enough.
        inputs.forEach((el, i) => {
          if (el.classList.contains("bad")) return;   // leave the typo visible to be corrected
          el.value = next[i] != null ? String(next[i]) : "";
          el.dataset.good = el.value;
          el.title = step > 0
            ? `A size for the row, rounded to the nearest ${step}. Blank drops this tab.`
            : "A size for the row. Blank drops this tab.";
        });
        changed(false);
      });
      grid.appendChild(inp);
    }
    sec.appendChild(grid);
    const note = document.createElement("div");
    note.className = "note";
    note.textContent = st.step > 0
      ? `Type any size. Up to ${MAX_ROW_ITEMS} fit on the row, and each is rounded `
        + `to the nearest ${st.step} to match the step above.`
      : `Type any size. Up to ${MAX_ROW_ITEMS} fit on the row. Blank drops a tab.`;
    sec.appendChild(note);
  }

  // ── shape chips ──────────────────────────────────────────────────────────
  // Picked from a list rather than typed: a shape is one of a known set, and
  // typing invites "16;9" and a chip that silently does nothing.
  {
    const sec = section(bd, "Shape chips", () => {
      writeState(node, { ratios: [...DEFAULT_RATIOS] });
      changed(true);
    });

    const chosen = st.ratios;
    const full = chosen.length >= MAX_ROW_ITEMS;

    const grid = document.createElement("div");
    grid.className = "sugg";
    for (const r of [LOCKED_RATIO, ...RATIO_CHOICES.filter((x) => x !== LOCKED_RATIO)]) {
      const on = chosen.includes(r);
      const locked = r === LOCKED_RATIO;
      const b = document.createElement("button");
      b.className = "chip" + (on ? " on" : "") + (locked ? " locked" : "");
      b.textContent = r;
      if (locked) {
        b.title = "Always on the row. It is the way back from a crop, so it cannot be removed.";
      } else if (on) {
        b.title = `On the row. Click to take ${r} off.`;
      } else if (full) {
        b.title = `The row is full (${MAX_ROW_ITEMS}). Take one off to add ${r}.`;
      } else {
        b.title = `Click to put ${r} on the row.`;
      }
      b.addEventListener("click", () => {
        if (locked) return;                       // keep is not removable
        const cur = readState(node).ratios;
        let next;
        if (cur.includes(r)) next = cur.filter((x) => x !== r);
        else if (cur.length >= MAX_ROW_ITEMS) return;   // full, nothing to do
        else next = [...cur, r];
        writeState(node, { ratios: next });
        changed(true);
      });
      grid.appendChild(b);
    }
    sec.appendChild(grid);

    const note = document.createElement("div");
    note.className = "note";
    note.textContent = full
      ? `The row is full. Click one that is on to take it off, then add another.`
      : `Click to add or remove. Up to ${MAX_ROW_ITEMS} fit, and keep is always there.`;
    sec.appendChild(note);
  }

  // ── crop anchor ──────────────────────────────────────────────────────────
  {
    const sec = section(bd, "Crop from");
    const wrap = document.createElement("div");
    wrap.className = "rowline";
    const grid = document.createElement("div");
    grid.className = "anchor";
    for (const a of ANCHORS) {
      const cell = document.createElement("button");
      cell.className = "acell" + (st.anchor === a ? " on" : "");
      cell.title = `Take the crop from the ${a.replace("-", " ")} of the picture`;
      cell.addEventListener("click", () => { writeState(node, { anchor: a }); changed(true); });
      grid.appendChild(cell);
    }
    const note = document.createElement("div");
    note.className = "note";
    note.style.flex = "1";
    note.textContent = "Which part of the picture to keep when a shape crops it.";
    wrap.append(grid, note);
    sec.appendChild(wrap);
  }

  // ── upscaling ────────────────────────────────────────────────────────────
  {
    const sec = section(bd, "Upscaling");
    const line = document.createElement("div");
    line.className = "rowline";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.id = `pix-ls-up-${node.id}`;
    cb.checked = !!st.allow_upscale;
    cb.addEventListener("change", () => {
      writeState(node, { allow_upscale: cb.checked });
      changed(true);
    });
    const upTitle = "On: a picture smaller than your size is scaled up to it. "
      + "Off: it is left at its own size. The shape is still cropped either way.";
    cb.title = upTitle;
    const lab = document.createElement("label");
    lab.htmlFor = cb.id;
    lab.textContent = "Let small pictures grow";
    lab.title = upTitle;
    line.append(cb, lab);
    sec.appendChild(line);
    const note = document.createElement("div");
    note.className = "note";
    note.textContent = "Off means a picture already smaller than your size is left "
      + "at its own size. The shape is still cropped either way.";
    sec.appendChild(note);
  }

  // ── resample ─────────────────────────────────────────────────────────────
  {
    const sec = section(bd, "Resample");
    const pills = document.createElement("div");
    pills.className = "pills";
    const TITLES = {
      auto: "Lanczos when shrinking, Bilinear when growing. Leave this unless you have a reason.",
      lanczos: "Sharpest when shrinking",
      bicubic: "Smooth, a middle ground",
      bilinear: "Soft, fastest of the smooth ones",
      nearest: "Hard pixel edges, for pixel art",
    };
    for (const r of RESAMPLES) {
      const p = document.createElement("button");
      p.className = "pill" + (st.resample === r ? " on" : "");
      p.textContent = r;
      p.title = TITLES[r] || r;
      p.addEventListener("click", () => { writeState(node, { resample: r }); changed(true); });
      pills.appendChild(p);
    }
    sec.appendChild(pills);
  }

  try {
    bd.appendChild(createAccentSection(node, {
      onChange: () => {
        PANEL?.style.setProperty("--pix-acc", accentOf(node));
        changed(false);
      },
      // Keep the picker's handle so closePanel can take it down with us.
      onPickerOpen: (h) => { _cpHandle = h; },
    }));
  } catch {}
}
