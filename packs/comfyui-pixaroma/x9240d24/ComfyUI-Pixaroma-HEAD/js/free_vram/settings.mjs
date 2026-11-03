// Free VRAM Pixaroma - the floating settings panel.
//
// Same shape as Save Video's: a draggable card that opens BESIDE the node and
// FOLLOWS it as the canvas is zoomed or panned (convention #29). The placement,
// follow loop and drag come from js/shared/node_panel.mjs, which carries the
// bug fixes they earned; this file owns only its singleton state and its rows.

import { createAccentSection } from "../shared/node_settings.mjs";
import { followNode, placeBeside, getNodeScreenRect, makeDraggable } from "../shared/node_panel.mjs";
import { THRESHOLD_MIN_GB, readState, writeState } from "./core.mjs";

let _panel = null;
let _panelNode = null;
let _onChange = null;
let _stopFollow = null;
let _userMoved = false; // has the user dragged the panel somewhere deliberately?
let _cpHandle = null;   // an open Pixaroma colour picker, so close can take it too
let _cssDone = false;

// The slider's ceiling. Deliberately a constant and not read from the card:
// a control whose range moves once a run has happened is a control that behaves
// differently the second time you open it. 64 covers every consumer and
// prosumer card; readState still accepts up to 128 so a hand-set value from a
// bigger machine survives a round trip.
const THRESHOLD_MAX_SLIDER = 64;

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text != null) node.textContent = text;
  return node;
}

function injectPanelCSS() {
  if (_cssDone || document.getElementById("pix-fv-panel-css")) return;
  _cssDone = true;
  const style = document.createElement("style");
  style.id = "pix-fv-panel-css";
  style.textContent = [
    ".pix-fv-panel{position:fixed;z-index:10010;width:320px;max-width:94vw;background:#1a1a1a;border:1px solid #444;border-radius:6px;box-shadow:0 8px 24px rgba(0,0,0,.6);font-family:'Segoe UI',system-ui,sans-serif;overflow:hidden;max-height:88vh;display:flex;flex-direction:column;}",
    ".pix-fv-phead{display:flex;align-items:center;justify-content:space-between;padding:10px 12px;border-bottom:1px solid #333;color:#ddd;font-size:13px;font-weight:600;cursor:move;}",
    ".pix-fv-px{border:0;background:transparent;color:#999;font-size:13px;cursor:pointer;padding:2px 7px;border-radius:4px;}",
    ".pix-fv-px:hover{color:#fff;}",
    ".pix-fv-pbody{padding:12px;display:flex;flex-direction:column;gap:12px;color:#ddd;overflow-y:auto;min-height:0;}",
    ".pix-fv-prow{display:flex;align-items:center;gap:9px;}",
    ".pix-fv-plab{font-size:12px;color:#ddd;}",
    ".pix-fv-psub{font-size:10px;color:#8f8f8f;margin-top:2px;line-height:1.4;}",
    ".pix-fv-qval{font-size:12px;color:var(--pix-acc,#f66744);min-width:62px;text-align:right;white-space:nowrap;}",
    ".pix-fv-qsl{flex:1;min-width:0;accent-color:var(--pix-acc,#f66744);}",
    ".pix-fv-qsl:disabled{opacity:.35;}",
    '.pix-fv-sw{width:30px;height:16px;border-radius:8px;background:#555;position:relative;display:inline-block;cursor:pointer;flex:0 0 auto;transition:background .15s;}',
    '.pix-fv-sw::after{content:"";position:absolute;top:2px;left:2px;width:12px;height:12px;border-radius:50%;background:#ccc;transition:left .15s;}',
    ".pix-fv-sw.on{background:var(--pix-acc,#f66744);}",
    ".pix-fv-sw.on::after{left:16px;background:#fff;}",
    // No rule for .pix-nset-sec on purpose: the shared accent section carries no
    // padding of its own and expects the panel BODY to pad it, which this body
    // does (12px, like Save Video's). A panel that pads PER SECTION instead has
    // to add one, or the colour block sits flush to the edges (monitor.md #17).
  ].join("\n");
  document.head.appendChild(style);
}

function stopFollowing() {
  _stopFollow?.();
  _stopFollow = null;
}

function outsideClose(e) {
  if (!_panel) return;
  if (_panel.contains(e.target)) return;
  // The Pixaroma colour picker and the generic option popup both open on
  // document.body, and this guard is capture phase - so without exempting them,
  // picking a colour would dismiss the panel underneath.
  if (e.target.closest?.(".pix-cp-popup, .pix-cp-modal-backdrop, .pix-nset-pop")) return;
  // The face's own gear acts on `click`, which lands AFTER this pointerdown -
  // without this the panel would close and instantly reopen, so the gear could
  // never shut what it opened.
  if (e.target.closest?.(".pix-fv-gear")) return;
  closeSettingsPanel();
}

function escClose(e) {
  if (e.key === "Escape" && _panel) {
    e.stopPropagation();
    closeSettingsPanel();
  }
}

export function closeSettingsPanel() {
  stopFollowing();
  // Take any open colour picker down with us, or Escape leaves it stranded on
  // document.body with no panel behind it.
  try { _cpHandle?.close?.(); } catch {}
  _cpHandle = null;
  if (_panel) {
    try { _panel.remove(); } catch {}
  }
  _panel = null;
  _panelNode = null;
  _onChange = null;
  // Reset on CLOSE, not on open: resetting on open would make one dragged panel
  // teach the next one to sit still where the node is not.
  _userMoved = false;
  document.removeEventListener("pointerdown", outsideClose, true);
  document.removeEventListener("keydown", escClose, true);
}

// onRemoved hook: only close the panel when it belongs to the deleted node.
export function closeSettingsPanelFor(node) {
  if (_panelNode === node) closeSettingsPanel();
}

export function isPanelOpenFor(node) {
  return _panelNode === node && !!_panel;
}

function section(body, label, sub) {
  const wrap = el("div");
  wrap.appendChild(el("div", "pix-fv-plab", label));
  if (sub) wrap.appendChild(el("div", "pix-fv-psub", sub));
  body.appendChild(wrap);
  return wrap;
}

function switchRow(node, key, label, sub, after) {
  const row = el("div", "pix-fv-prow");
  const sw = el("span", "pix-fv-sw" + (readState(node)[key] ? " on" : ""));
  sw.setAttribute("role", "switch");
  sw.setAttribute("aria-checked", String(!!readState(node)[key]));
  sw.tabIndex = 0;
  const toggle = () => {
    const st = readState(node);
    const next = writeState(node, { [key]: !st[key] });
    sw.classList.toggle("on", next[key]);
    sw.setAttribute("aria-checked", String(!!next[key]));
    after?.(next);
    // Every control in a panel applies through _onChange - it is part of the
    // control, not an optional nicety (monitor.md #16).
    _onChange?.();
  };
  sw.addEventListener("click", toggle);
  sw.addEventListener("keydown", (e) => {
    if (e.key === " " || e.key === "Enter") { e.preventDefault(); toggle(); }
  });
  const txt = el("div");
  txt.appendChild(el("div", "pix-fv-plab", label));
  txt.appendChild(el("div", "pix-fv-psub", sub));
  row.appendChild(sw);
  row.appendChild(txt);
  return row;
}

export function openSettingsPanel(node, onChange) {
  closeSettingsPanel();
  injectPanelCSS();
  _onChange = onChange || null;
  const panel = el("div", "pix-fv-panel");
  _panel = panel;
  _panelNode = node;

  const head = el("div", "pix-fv-phead");
  head.appendChild(el("span", null, "Free VRAM settings"));
  const x = el("button", "pix-fv-px", "✕");
  x.type = "button";
  x.onclick = closeSettingsPanel;
  head.appendChild(x);
  panel.appendChild(head);
  // The ✕ sits INSIDE the drag handle, and makeDraggable calls preventDefault +
  // setPointerCapture on pointerdown - so without ignoreSelector the click
  // never lands and the button does nothing.
  makeDraggable(panel, head, {
    onUserMove: () => { _userMoved = true; },
    ignoreSelector: ".pix-fv-px",
  });

  const body = el("div", "pix-fv-pbody");

  // ── what to let go of ──
  section(body, "What to let go of",
    "The three modes are on the node itself. This is the extra step that goes " +
    "with them.");
  body.appendChild(switchRow(node, "gc", "Collect leftovers",
    "Sweeps up anything Python is still holding on to before measuring again. " +
    "Costs a fraction of a second and usually gets a little more back. Leave it on " +
    "unless you are timing something."));

  // ── when ──
  section(body, "When",
    "A node is normally skipped when nothing above it changed. That is exactly " +
    "the case this node exists for, so by default it ignores that.");
  body.appendChild(switchRow(node, "everyRun", "Free on every run",
    "On: always acts, but everything wired AFTER this node has to run again too, " +
    "because ComfyUI can no longer tell that this node produced the same thing. " +
    "Off: only acts when the workflow actually reaches it, and everything after " +
    "it keeps its cached results."));

  // Declared before the switch that calls it: the switch's callback only fires
  // on a click, so a `const` defined further down would work, but only by
  // accident of timing. An assigned `let` says what is actually true.
  let syncThreshold = () => {};

  const thWrap = el("div");
  thWrap.appendChild(switchRow(node, "useThreshold", "Only when memory is low",
    "Skip the cleanup when there is already plenty of room. Unloading a model " +
    "you did not need to unload costs you the time to load it back.",
    () => syncThreshold()));

  const thRow = el("div", "pix-fv-prow");
  thRow.style.marginTop = "7px";
  const thSl = el("input", "pix-fv-qsl");
  thSl.type = "range";
  thSl.min = String(THRESHOLD_MIN_GB);
  thSl.max = String(THRESHOLD_MAX_SLIDER);
  thSl.step = "0.5";
  thSl.value = String(readState(node).thresholdGb);
  const thVal = el("span", "pix-fv-qval", "");
  // ⚠️ READ THE STATE, NOT `thSl.value`. A range input SANITISES on assignment:
  // giving it 100 when its max is 64 stores 64, and reading `.value` back
  // returns "64". The stored setting still says 100 - readState allows up to 128
  // so a value set on a bigger machine survives a round trip - so printing the
  // input's value made the panel say "under 64 GB" while the node's own face
  // correctly said 100. The panel and the face disagreed about one setting.
  syncThreshold = () => {
    const st = readState(node);
    thSl.disabled = !st.useThreshold;
    thVal.style.opacity = st.useThreshold ? "1" : "0.35";
    thVal.textContent = `under ${st.thresholdGb} GB`;
    thSl.title = st.thresholdGb > THRESHOLD_MAX_SLIDER
      ? `Only free when less than ${st.thresholdGb} GB is already free. That is above `
        + `this slider's range, so the handle sits at its end - moving it will lower the value.`
      : `Only free when less than ${st.thresholdGb} GB is already free`;
    thVal.title = thSl.title;
  };
  thSl.oninput = () => {
    writeState(node, { thresholdGb: parseFloat(thSl.value) });
    syncThreshold();
    _onChange?.();
  };
  syncThreshold();
  thRow.appendChild(thSl);
  thRow.appendChild(thVal);
  thWrap.appendChild(thRow);
  body.appendChild(thWrap);

  // ── show ──
  section(body, "Show");
  body.appendChild(switchRow(node, "showBar", "Show the memory bar",
    "The strip of the whole card under the buttons. Turning it off makes the " +
    "node shorter and leaves the wording on its own."));

  // ── accent colour (convention #19) ──
  // Pass NO title/label/hint: `title` is what the helper puts in the "New <X>
  // nodes" BUTTON, and it already reads "Free VRAM" from the registry.
  body.appendChild(createAccentSection(node, {
    onChange: () => _onChange?.(),
    // Keep the picker's handle so closing this panel takes it down too -
    // Escape closes the panel, and without this the picker would be stranded.
    onPickerOpen: (h) => { _cpHandle = h; },
  }));

  panel.appendChild(body);
  document.body.appendChild(panel);
  placeBeside(panel, getNodeScreenRect(node));
  _stopFollow = followNode(panel, node, {
    isCurrent: () => _panel === panel,
    isUserMoved: () => _userMoved,
  });

  // Deferred so the click that OPENED the panel does not immediately close it.
  setTimeout(() => {
    document.addEventListener("pointerdown", outsideClose, true);
    document.addEventListener("keydown", escClose, true);
  }, 0);
  return panel;
}
