import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";
import { passComfyShortcut } from "../shared/text_shortcuts.mjs";
import { isVueNodes, applyAdaptiveCanvasOnly } from "../shared/nodes2.mjs";
import { installResizeFloor } from "../shared/resize_floor.mjs";
import { installCanvasZoomPassthrough } from "../shared/canvas_zoom.mjs";
import { registerNodeHelp } from "../shared/help.mjs";
import { installNodeAccent, registerNodeAccent, nodeSetting } from "../shared/node_settings.mjs";
import { pixAsset } from "../shared/api_url.mjs";

// ╔══════════════════════════════════════════════════════════════════════╗
// ║  Run Log Pixaroma — the last 10 run times, on the node                ║
// ╚══════════════════════════════════════════════════════════════════════╝
//
// A companion to Run Timer. Frontend-only node (never runs in Python). It listens
// to ComfyUI's run events and, when a run FINISHES successfully, drops the whole-
// workflow time onto the top of a per-node list (newest first, last 10 kept). The
// list lives on node.properties.runLogHistory, so it travels WITH the workflow and
// survives a reload — "this workflow only", exactly as asked. Times only; no
// workflow names.
//
// This is a NORMAL titled node (unlike title-less Run Timer), so it uses ONE
// addDOMWidget for BOTH renderers — no canvas paint path needed (a titled node is
// dragged by its title bar, so a DOM body widget doesn't eat drag/right-click).
//
// Dirty-on-load safe (Vue Compat #18): the load path (nodeCreated microtask +
// onConfigure) only READS node.properties and rebuilds the DOM. The only writes to
// serialized state are the recorded time on a genuine finished run and the Clear
// action — both user/run driven, both accepted like Run Timer's runTimerLastMs.

const BRAND = "#f66744";
const NODE_NAME = "PixaromaRunLog";
const HIST_PROP = "runLogHistory";
const HISTORY_MAX = 10;
// Longest per-run label. One line, clipped with an ellipsis when the row is too
// narrow (full text lives in the row tooltip).
const LABEL_MAX = 60;

// The panel always shows all 10 rows — the MIN height fits caption + 10 rows +
// footer, so the node can't be dragged small enough to clip runs (user feedback).
// Default = minimum (convention #5); width is still free, taller is harmless. Both
// heights are CONSTANTS → dirty-on-load safe (byte-identical every save/load).
// The screen is sized to EXACTLY the 10 rows and no more (flex:none, not flex:1).
// It used to stretch to fill the node, which left a black strip under the last
// row - measured at 20.7px, almost a whole row (user feedback, 2026-07-23). A
// fixed height means that strip cannot come back at any node size: spare height
// now sits outside the panel, as node background, instead of inside it as dead
// black. box-sizing is border-box, so this height INCLUDES the 5px padding and
// the 1px border: 10*20 + 10 + 2 = 212 → a 200px content box = exactly 10 rows.
const ROW_H = 20;
const SCREEN_H = HISTORY_MAX * ROW_H + 12;
// caption(14) + gap(6) + screen + gap(6) + footer(20).
// WHICH floor actually protects row 10 differs per renderer, and the comment
// that used to sit here named the wrong one (review, 2026-07-23):
//   Nodes 2.0 - getMinHeight / computeLayoutSize + installResizeFloor. Our widget
//     is an 'auto' grid track and every child is flex:none, so the node grows to
//     fit its content and the drag floor is pinned during a resize.
//   LEGACY    - the MIN_H clamp below, NOT getMinHeight. LiteGraph's DOM-widget
//     auto-grow converges on node.size[1] = WIDGET_MIN_H + 2, and getBounding
//     then hands the ELEMENT computedHeight - 2*margin, i.e. WIDGET_MIN_H - 20:
//     20px SHORT of the content. getMinHeight alone would clip row 10; MIN_H is
//     what actually delivers the full height.
const WIDGET_MIN_H = SCREEN_H + 46;      // 258 - the TRUE content height
// ── The 16px over-reservation, and why LAYOUT_MIN_H is not WIDGET_MIN_H ──────
// Read from the bundle (LGraphNode.computeSize) and confirmed against a live
// measurement (reported 258 -> computeSize 296, exactly):
//     computeSize.height = a*NODE_SLOT_HEIGHT + (minHeight + 4) + 8 + 6
//                        = 20 + minHeight + 18            (a = 1: no slots)
//                        = minHeight + 38
// but the element the widget actually GETS is only node.size[1] - 22
// (widgets_start_y 2 + 2 x the DOM margin 10). So LiteGraph RESERVES 38 and
// HANDS BACK 22: every DOM-widget node of this shape is permanently 16px taller
// than its own content, and computeSize - not our MIN_H clamp - is the real
// resize floor. That 16px is what showed as a gap above the footer buttons.
// Reporting content - 16 makes computeSize land on 280, which hands the element
// exactly 258 = the content. Degrades safely: if a future LiteGraph changes
// either number the node is off by the delta - too big is invisible slack, too
// small is absorbed by the 18px-in-20px footer buttons and clipped by
// .pix-rl-root rather than spilling onto the canvas.
const LG_COMPUTE_PAD = 38;               // what computeSize adds to minHeight
const NODE_CHROME_H = 22;                // what the element actually loses
const LAYOUT_MIN_H = WIDGET_MIN_H - (LG_COMPUTE_PAD - NODE_CHROME_H);   // 242
// NODE_CHROME_H (declared above) is widgets_start_y (2) + the DOM widget margin
// twice (10 each). NOT the title bar - node.size[1] EXCLUDES it
// (bodyHeight === size[1]), so a build with a taller title bar does not change
// it. Do NOT "correct" it to a NODE_TITLE_HEIGHT.
// Deliberately 0. A cushion here is visible as node background between the panel
// and the footer buttons - i.e. the dead space the user asked to remove - and
// overflow:hidden on .pix-rl-root ALREADY delivers what the cushion was for
// (the footer can never paint outside the node onto the canvas). Raise it only if
// a LiteGraph change actually starts clipping the footer: the buttons are 18px in
// a 20px row so a small shortfall is absorbed, and Export / Copy / Clear stay
// reachable from the right-click menu regardless.
const SAFETY_PAD = 0;
const DEFAULT_W = 300;   // room for a label; existing nodes keep their saved width
const DEFAULT_H = WIDGET_MIN_H + NODE_CHROME_H + SAFETY_PAD;   // 280
const MIN_W = 200;
const MIN_H = DEFAULT_H;

// ── DOM helper ──────────────────────────────────────────────────────────────
function el(tag, cls) { const e = document.createElement(tag); if (cls) e.className = cls; return e; }

// ── time formatting ─────────────────────────────────────────────────────────
// Under a minute → seconds with one decimal (14.8s). A minute or more → m:ss
// (1:23). Math.floor so a float ms never leaks raw decimals.
function fmtTime(ms) {
  const s = ms / 1000;
  // Decide the format on the ROUNDED value: a hair under a minute (e.g. 59.96s)
  // would otherwise show "60.0s" (toFixed(1) rounds up) instead of flipping to "1:00".
  const r = Math.round(s * 10) / 10;
  if (r < 60) return r.toFixed(1) + "s";
  const total = Math.round(s);
  const m = Math.floor(total / 60), sec = total % 60;
  if (m < 60) return m + ":" + String(sec).padStart(2, "0");
  return Math.floor(m / 60) + ":" + String(m % 60).padStart(2, "0") + ":" + String(sec).padStart(2, "0");
}

// ── the optional hardware line ──────────────────────────────────────────────
// Off by default. Reads ComfyUI's OWN /system_stats, so there is no new backend
// route, no extra dependency and nothing to install; it is the same endpoint
// Version Check already uses.
//
// ⚠️ READ LIVE, NEVER PERSISTED - this is the whole design and it must stay that
// way. The text is derived at render time and is never written to
// node.properties, so (a) it can never dirty a clean workflow on load
// (Vue Compat #18, the bug class that has bitten four nodes), and (b) it can
// never travel inside a shared workflow file and tell a stranger what hardware
// this machine has. The show/hide choice is a per-USER setting rather than
// per-node for the same reason: it describes the machine, not the workflow.
// Deliberately NOT included in the .txt Export either - see #13.
const SETTING_SHOW_HW = "Pixaroma.RunLog.ShowHardware";

let _hwPromise = null;   // one fetch per page, shared by every Run Log node

/** "cuda:0 NVIDIA GeForce RTX 4090 : cudaMallocAsync" -> "RTX 4090".
 *  Defensive on purpose: only KNOWN decorations are stripped, and anything that
 *  does not match falls through UNCHANGED. A slightly ugly name beats a mangled
 *  one, and the string differs per backend (mps / hip / cpu / xpu all differ),
 *  so this must never assume the NVIDIA shape. */
function shortGpu(raw) {
  const orig = String(raw == null ? "" : raw).trim();
  if (!orig) return "";
  let s = orig.split(" : ")[0];                        // drop the allocator suffix
  s = s.replace(/^(?:cuda|hip|xpu|mps|cpu|privateuseone):\d+\s*/i, "");
  s = s.replace(/^NVIDIA\s+/i, "").replace(/^GeForce\s+/i, "");
  s = s.trim();
  return s || orig;
}

/** Bytes -> a whole number of GB ("24GB"). Empty string when it is not a usable
 *  number, so a missing field drops its segment instead of printing "NaNGB". */
function gbLabel(bytes) {
  const n = Number(bytes);
  if (!isFinite(n) || n <= 0) return "";
  return Math.round(n / 1073741824) + "GB";
}

/** Build "RTX 4090 · 24GB VRAM · 128GB RAM" from a /system_stats payload. */
function hwLineFrom(stats) {
  const dev = (stats && Array.isArray(stats.devices) ? stats.devices[0] : null) || {};
  const sys = (stats && stats.system) || {};
  const parts = [];
  const gpu = shortGpu(dev.name);
  if (gpu) parts.push(gpu);
  // Only claim "VRAM" for a device that actually has a separate pool. Apple
  // silicon (mps) shares one pool with the system, so printing "24GB VRAM ·
  // 24GB RAM" there would be telling the user the same memory twice; a CPU run
  // has no VRAM at all.
  const type = String(dev.type || "").toLowerCase();
  if (type === "cuda" || type === "hip" || type === "xpu") {
    const v = gbLabel(dev.vram_total);
    if (v) parts.push(v + " VRAM");
  }
  const r = gbLabel(sys.ram_total);
  if (r) parts.push(r + (type === "mps" ? " unified" : " RAM"));
  return parts.join(" · ");
}

/** The line, fetched once per page and cached. Never rejects: on any failure it
 *  resolves to "" and the row simply stays empty, because a run-time ledger must
 *  not break over a cosmetic extra. */
function getHwLine() {
  if (!_hwPromise) {
    _hwPromise = Promise.resolve()
      .then(() => api.fetchApi("/system_stats"))
      .then((r) => (r && r.ok ? r.json() : null))
      .then((d) => {
        const line = hwLineFrom(d);
        // Only a REAL answer is cached. Caching a failure would disable the
        // line for the rest of the page over one hiccup (e.g. asking while the
        // server is still starting), with no way back but a reload.
        if (!line) _hwPromise = null;
        return line;
      })
      .catch(() => { _hwPromise = null; return ""; });
  }
  return _hwPromise;
}

/** Paint (or clear) one node's hardware line. Safe to call any time; reads the
 *  setting LIVE so the gear toggle applies with no reload. */
function renderHw(node, forcedOn) {
  const box = node && node._pixRlHw;
  if (!box) return;
  // `forcedOn` is the value handed to the settings row's change callback. Use it
  // in preference to re-reading, per the house rule that a setting's onChange
  // can run BEFORE the store write lands - re-reading there returns the OLD
  // value and the row appears to do nothing (which is exactly what happened on
  // the first build of this).
  const on = forcedOn === undefined ? !!nodeSetting(SETTING_SHOW_HW, false) : !!forcedOn;
  if (!on) {
    box.textContent = "";
    box.removeAttribute("title");
    box.style.display = "none";
    return;
  }
  box.style.display = "";
  getHwLine().then((line) => {
    // The user may have toggled it back off while the fetch was in flight, and
    // this promise resolves for every node that asked. `on` is this call's own
    // decision, so a later call always wins.
    if (!node._pixRlHw || node._pixRlHw !== box) return;
    if (box.style.display === "none") return;
    box.textContent = line;
    // The full text on hover, since a narrow node truncates it.
    if (line) box.title = line;
    else box.removeAttribute("title");
  });
}

/** Repaint every live node's line (used by the settings toggle). */
function renderHwAll(forcedOn) { for (const n of _logs) renderHw(n, forcedOn); }

// ── history (per node, on node.properties) ──────────────────────────────────
// An entry is { ms, label }. v1 (v1.4.54 and earlier) stored a BARE ms number,
// so getHist normalises both shapes on read and a bare number reads as an
// unlabelled entry. It deliberately NEVER writes the normalised form back: the
// load path must stay read-only or a plain open would dirty the workflow
// (Pattern #3, Vue Compat #18). Old entries are rewritten in the new shape only
// when a write was going to happen anyway - a finished run, a label edit, Clear.
function normEntry(e) {
  if (typeof e === "number") {
    return isFinite(e) && e >= 0 ? { ms: e, label: "" } : null;
  }
  if (e && typeof e === "object" && typeof e.ms === "number" && isFinite(e.ms) && e.ms >= 0) {
    // Normalise on READ exactly as setLabel normalises on write, so the two can
    // never disagree. A whitespace-only label (hand-edited file, or a future
    // writer that bypasses setLabel) would otherwise be truthy: the row would
    // show nothing AND lose its "add note" placeholder, and the row tooltip
    // would gain an empty segment.
    const label = typeof e.label === "string"
      ? e.label.replace(/\s+/g, " ").trim().slice(0, LABEL_MAX) : "";
    return { ms: e.ms, label };
  }
  return null;
}
function getHist(node) {
  const raw = node.properties && node.properties[HIST_PROP];
  if (!Array.isArray(raw)) return [];
  const out = [];
  for (const e of raw) {
    const n = normEntry(e);
    if (n) out.push(n);
    if (out.length >= HISTORY_MAX) break;
  }
  return out;
}
function pushHistory(node, ms) {
  const dur = Math.round(Number(ms));
  if (!isFinite(dur) || dur < 0) return;
  const next = [{ ms: dur, label: "" }, ...getHist(node)].slice(0, HISTORY_MAX);
  if (!node.properties) node.properties = {};
  node.properties[HIST_PROP] = next;
}
// Write one entry's label. No-op when nothing actually changes, so opening an
// editor and pressing Escape (or clicking away untouched) never dirties the
// workflow. A real change does dirty it - same accepted precedent as recording
// a run (Pattern #3).
// Returns true when it actually wrote (and therefore re-rendered), so the caller
// can avoid a second rebuild of the whole screen on the no-op path.
function setLabel(node, i, text) {
  const hist = getHist(node);
  if (!(i >= 0 && i < hist.length)) return false;
  const label = String(text == null ? "" : text).replace(/\s+/g, " ").trim().slice(0, LABEL_MAX);
  if (hist[i].label === label) return false;
  hist[i] = { ms: hist[i].ms, label };
  if (!node.properties) node.properties = {};
  node.properties[HIST_PROP] = hist;
  renderList(node);
  if (!isVueNodes()) node.setDirtyCanvas && node.setDirtyCanvas(true, true);
  return true;
}
function clearHistory(node) {
  // DISCARD an open editor rather than commit it: the list is about to be wiped,
  // so committing would be a pointless serialized write (and an extra render)
  // for a label that ceases to exist two lines later.
  node._pixRlCommitEdit = null;
  if (!node.properties) node.properties = {};
  node.properties[HIST_PROP] = [];
  renderList(node);
  if (!isVueNodes()) node.setDirtyCanvas && node.setDirtyCanvas(true, true);
}

// ── render the ledger (both renderers — one DOM widget) ─────────────────────
function renderList(node) {
  const screen = node._pixRlScreen;
  const status = node._pixRlStatus;
  if (!screen) return;
  const hist = getHist(node);

  // footer buttons are dead when there's nothing to export / clear
  const has = hist.length > 0;
  if (node._pixRlExportBtn) node._pixRlExportBtn.disabled = !has;
  if (node._pixRlClearBtn) node._pixRlClearBtn.disabled = !has;

  if (status) {
    if (node._rlRunning) {
      status.className = "pix-rl-status pix-rl-running";
      status.innerHTML = "";
      status.appendChild(el("span", "pix-rl-rdot"));
      status.appendChild(document.createTextNode("running"));
    } else {
      status.className = "pix-rl-status";
      status.textContent = "this workflow";
    }
  }

  screen.innerHTML = "";
  if (!hist.length) {
    const empty = el("div", "pix-rl-empty");
    const t = el("div", "pix-rl-empty-t"); t.textContent = "No runs yet";
    const s = el("div", "pix-rl-empty-s"); s.textContent = "Press Run to time this workflow";
    empty.appendChild(t); empty.appendChild(s);
    screen.appendChild(empty);
    return;
  }

  // fastest of the ten (index 0 is newest)
  let bestIdx = 0;
  for (let i = 1; i < hist.length; i++) if (hist[i].ms < hist[bestIdx].ms) bestIdx = i;

  hist.forEach((entry, i) => {
    const isNow = i === 0;
    const isBest = i === bestIdx;
    const row = el("div", "pix-rl-row" + (isNow ? " pix-rl-row--now" : (isBest ? " pix-rl-row--best" : "")));
    const idx = el("span", "pix-rl-idx"); idx.textContent = String(i + 1).padStart(2, "0");
    // Fixed-width marker column: the bolt marks the fastest. Keeping it its own
    // column means labels stay aligned whether or not a row carries a bolt.
    const mark = el("span", "pix-rl-mark"); mark.textContent = isBest ? "⚡" : "";
    // The label owns the middle of the row (it replaced the LAST / BEST words -
    // both states are already carried by the orange bar and the bolt + colour).
    const lbl = el("span", "pix-rl-lbl" + (entry.label ? "" : " pix-rl-lbl--empty"));
    lbl.textContent = entry.label;
    const time = el("span", "pix-rl-time"); time.textContent = fmtTime(entry.ms);

    // The words are gone, so name the state in the tooltip - the information
    // must not be colour-only.
    const state = isNow ? (isBest ? "Newest run, and the fastest of the ten" : "Newest run")
                        : (isBest ? "Fastest of the ten" : "");
    row.title = [state, entry.label, "Double-click to add a note"]
      .filter(Boolean).join(" — ");

    row.addEventListener("dblclick", (e) => {
      e.preventDefault();
      e.stopPropagation();
      startEdit(node, i);
    });

    row.appendChild(idx); row.appendChild(mark); row.appendChild(lbl); row.appendChild(time);
    screen.appendChild(row);
  });
}

// ── inline label editor ─────────────────────────────────────────────────────
// Swaps the label cell for a focused text input. Enter / blur commit, Escape
// reverts, empty clears the label. node._pixRlCommitEdit lets the run lifecycle
// flush an in-progress edit BEFORE a new run shifts every index (see finishRun).
function startEdit(node, i) {
  // Flush any other open editor FIRST - committing can rebuild the whole screen,
  // which would detach the row element. Only then resolve the row, by INDEX, so
  // we always act on the live DOM. (Capturing the cell first left the editor
  // inserted into an orphaned row: focus() silently no-ops, the double-click
  // appears dead, and because the input never gains focus the next keystrokes
  // reach ComfyUI's canvas shortcuts - Delete would remove the node.)
  node._pixRlCommitEdit?.();
  const screen = node._pixRlScreen;
  const row = screen && screen.children[i];
  const cell = row && row.querySelector(".pix-rl-lbl");
  if (!cell) return;                       // no such row (or the empty-state block)
  const hist = getHist(node);
  const cur = hist[i] ? hist[i].label : "";
  // Identity of the run being edited, so commit can tell whether the list moved.
  const msAtOpen = hist[i] ? hist[i].ms : null;

  const input = el("input", "pix-rl-lblin");
  input.type = "text";
  input.maxLength = LABEL_MAX;
  input.value = cur;
  input.placeholder = "what was different?";
  input.spellcheck = false;
  cell.replaceWith(input);
  input.focus();
  input.select();

  let done = false;
  const commit = (save) => {
    if (done) return;
    done = true;
    node._pixRlCommitEdit = null;
    // The node was deleted while this editor was open. Nulling the handle in
    // onRemoved does NOT disarm us - the input's own blur listener still holds
    // this closure, and some browsers fire blur when a focused element is
    // detached - so bail explicitly instead of relying on the writes happening
    // to be harmless on an orphan.
    if (node._pixRlDead) return;
    // Only write if index i STILL means the run that was being edited. Test the
    // ENTRY (its time), not input.isConnected: a detached input does not imply a
    // shifted list - Nodes 2.0 re-parents the widget root, which would throw the
    // text away for nothing - and a shifted list does not imply a detached input.
    // This is a BACKSTOP, not the guarantee: ms values are rounded ints, so two
    // runs CAN share one. What actually makes a shift-under-an-open-editor
    // impossible is that every mutator flushes first (see the flush invariant).
    // No renderList in this branch: whatever moved the list is mid-rebuild and
    // will draw the row correctly (re-rendering here can duplicate the rows).
    const now = getHist(node);
    if (!now[i] || now[i].ms !== msAtOpen) {
      // Unreachable today, but never leave a dead field sitting in the list.
      if (input.isConnected) input.replaceWith(el("span", "pix-rl-lbl"));
      return;
    }
    // setLabel re-renders when it writes; only rebuild here on the no-op path.
    if (!setLabel(node, i, save ? input.value : cur)) renderList(node);
  };
  node._pixRlCommitEdit = () => commit(true);

  // Keep typing away from ComfyUI's canvas shortcuts, and clicks from starting a
  // node drag or re-triggering the row's dblclick.
  input.addEventListener("keydown", (e) => {
    // Ctrl/Cmd+S and Ctrl/Cmd+Enter go on to ComfyUI; blur first commits the
    // typed note so the save / run sees it (UI#44).
    if (passComfyShortcut(e, input, { blur: true })) return;
    e.stopPropagation();
    if (e.key === "Enter") { e.preventDefault(); commit(true); }
    else if (e.key === "Escape") { e.preventDefault(); commit(false); }
  });
  input.addEventListener("blur", () => commit(true));
  for (const ev of ["mousedown", "pointerdown", "dblclick", "click"]) {
    input.addEventListener(ev, (e) => e.stopPropagation());
  }
}

// ── run lifecycle (drives every Run Log on the canvas) ──────────────────────
// Each live node stamps the run origin on itself at start (node._rlRunStart), the
// same way Run Timer does (node._rtStart), so a node's recorded time is always
// measured from the origin captured when its own run began. ComfyUI runs the queue
// sequentially (one execution_start per finish), so runs don't overlap in practice.
const _logs = new Set();
let _runStart = null;

function startRun() {
  _runStart = performance.now();
  for (const node of _logs) {
    node._pixRlCommitEdit?.();   // renderList below would discard an open editor
    node._rlRunning = true;
    node._rlRunStart = _runStart; // stamp the origin on the node (Run Timer parity)
    renderList(node);
    if (!isVueNodes()) node.setDirtyCanvas && node.setDirtyCanvas(true, true);
  }
}
function finishRun(success) {
  // ONE timestamp for the whole sweep. Reading performance.now() per node would
  // fold our own DOM work (an editor flush, the previous node's re-render) into
  // the measured duration, and would give two Run Log nodes different times for
  // the same run.
  const end = performance.now();
  for (const node of _logs) {
    if (!node._rlRunning) continue;   // idempotent: first finish wins (some builds
                                      // fire BOTH 'executing'(null) AND success)
    // Flush an open editor BEFORE pushHistory: a new run unshifts the list, so
    // committing afterwards would write the typed text onto the wrong row.
    node._pixRlCommitEdit?.();
    node._rlRunning = false;
    // Successes only — an interrupted / errored run gives a partial, misleading time.
    if (success && node._rlRunStart != null) pushHistory(node, end - node._rlRunStart);
    renderList(node);
    if (!isVueNodes()) node.setDirtyCanvas && node.setDirtyCanvas(true, true);
  }
}

let _listenersInstalled = false;
function installRunListeners() {
  if (_listenersInstalled) return;
  _listenersInstalled = true;
  api.addEventListener("execution_start", () => startRun());
  // 'executing' with a null node id = queue item finished (older builds);
  // execution_success covers newer builds.
  api.addEventListener("executing", (e) => {
    const d = e && e.detail;
    const nodeId = (d && typeof d === "object") ? d.node : d;
    if (nodeId == null) finishRun(true);
  });
  api.addEventListener("execution_success", () => finishRun(true));
  api.addEventListener("execution_error", () => finishRun(false));
  api.addEventListener("execution_interrupted", () => finishRun(false));
}

// ── copy to clipboard (works over http LAN via an execCommand fallback) ──────
function legacyCopy(text) {
  const ta = document.createElement("textarea");
  ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
  try { document.body.appendChild(ta); ta.select(); document.execCommand("copy"); }
  catch (_e) { /* ignore */ }
  finally { ta.remove(); }
}
function copyText(text) {
  if (navigator.clipboard?.writeText) navigator.clipboard.writeText(text).catch(() => legacyCopy(text));
  else legacyCopy(text);
}
// One text line per entry: "01.   14.8s  with style lora" (label only when set).
// The time is right-aligned in a fixed width so the labels line up in the file.
function fmtLine(entry, i) {
  const line = String(i + 1).padStart(2, "0") + ". " + fmtTime(entry.ms).padStart(7);
  return entry.label ? line + "  " + entry.label : line;
}
function copyTimes(node) {
  node._pixRlCommitEdit?.();   // see the note on exportTxt
  const hist = getHist(node);
  if (!hist.length) return;
  copyText(hist.map(fmtLine).join("\n"));
}
// Save the list as a plain .txt (user-initiated download of their OWN data).
// Flush an open editor FIRST: a note that is still being typed is visible on the
// node, so leaving it out of the file would be a silent lie. Clicking a footer
// button usually blurs the input (which commits) before the click lands, but
// that is browser- and platform-dependent, and the right-click menu path may not
// blur at all - so do not rely on it.
function exportTxt(node) {
  node._pixRlCommitEdit?.();
  const hist = getHist(node);
  if (!hist.length) return;
  const body = hist.map(fmtLine).join("\n");
  const text = "Run Log - last " + hist.length + (hist.length === 1 ? " run" : " runs") + "\n" + body + "\n";
  try {
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "run-log.txt";
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => { try { URL.revokeObjectURL(url); } catch (_e) {} }, 1000);
  } catch (e) {
    // Fallback (rare): copy to clipboard so the times aren't lost.
    copyText(text);
  }
}

// A subtle footer icon button (grey mask icon → brand orange on hover). Reuses the
// shared UI SVGs, asked for through pixAsset (i.e. /pixaroma/api/assets/icons/ui/ —
// a hosted ComfyUI's gateway blocks the older /pixaroma/assets/ form at its edge).
function iconBtn(iconFile, title) {
  const b = el("button", "pix-rl-fbtn");
  b.type = "button"; b.title = title;
  const ico = el("span", "pix-rl-ico");
  const url = "url(" + pixAsset("icons/ui/" + iconFile) + ")";
  ico.style.webkitMaskImage = url; ico.style.maskImage = url;
  b.appendChild(ico);
  return b;
}

// ── CSS (no backticks inside the strings — house convention) ────────────────
let _cssDone = false;
function injectCSS() {
  if (_cssDone || document.getElementById("pix-rl-css")) { _cssDone = true; return; }
  _cssDone = true;
  const s = document.createElement("style");
  s.id = "pix-rl-css";
  s.textContent = [
    // overflow:hidden is a backstop: every child is flex:none, so if a future
    // LiteGraph change ever made the element shorter than the content, the
    // footer would otherwise paint outside the node frame, over the canvas.
    ".pix-rl-root{display:flex;flex-direction:column;gap:6px;width:100%;height:100%;box-sizing:border-box;padding:0;overflow:hidden;user-select:none;-webkit-user-select:none;font-family:'Segoe UI',system-ui,sans-serif;}",
    ".pix-rl-cap{display:flex;align-items:center;justify-content:space-between;flex:none;padding:0 2px;height:14px;}",
    ".pix-rl-caplbl{font-family:'Consolas','DejaVu Sans Mono',ui-monospace,monospace;font-size:10px;letter-spacing:0.14em;text-transform:uppercase;color:#6c6960;}",
    ".pix-rl-status{font-family:'Consolas','DejaVu Sans Mono',ui-monospace,monospace;font-size:10px;letter-spacing:0.1em;text-transform:uppercase;color:#57544d;display:flex;align-items:center;gap:5px;}",
    ".pix-rl-running{color:#49c97a;}",
    // A STEADY dot, never an endless CSS animation (2026-09-26). An infinite
    // pulse makes the browser composite a fresh frame 60 times a second for the
    // whole run, on the same GPU that is generating: MEASURED in Nodes 2.0, the
    // pulse alone cost ~2% of every generation. Green + the word "running" is
    // the signal; nothing needs to move.
    ".pix-rl-rdot{width:6px;height:6px;border-radius:50%;background:#49c97a;}",
    // flex:none + an exact height — see SCREEN_H. Never flex:1, or the panel
    // stretches and leaves a black strip under the last row.
    ".pix-rl-screen{flex:none;height:" + SCREEN_H + "px;overflow:hidden;background:#141417;border:1px solid #050506;border-radius:6px;box-shadow:inset 0 1px 0 rgba(255,255,255,0.03),inset 0 0 20px rgba(0,0,0,0.35);padding:5px;box-sizing:border-box;}",
    // [index][bolt marker][label][time]. The marker is its own fixed column so
    // labels stay aligned whether or not a row carries the bolt.
    ".pix-rl-row{display:grid;grid-template-columns:22px 12px 1fr auto;align-items:center;gap:6px;padding:0 8px;border-radius:4px;height:" + ROW_H + "px;box-sizing:border-box;}",
    ".pix-rl-row:nth-child(even){background:rgba(255,255,255,0.022);}",
    // The WHOLE row is the double-click target, so the whole row must respond to
    // the pointer (UI convention #13 - borderless cells inside a bordered
    // container hover to a white tint). Without this a row that already HAS a
    // label had no hover feedback at all, since the only response was the
    // placeholder brightening. Declared after :nth-child(even) so it wins at
    // equal specificity; the newest row keeps its own colour, just brighter.
    ".pix-rl-row:hover{background:rgba(255,255,255,0.06);transition:background 0.12s;}",
    ".pix-rl-idx{font-family:'Consolas','DejaVu Sans Mono',ui-monospace,monospace;font-size:11px;color:#6c6960;text-align:right;}",
    ".pix-rl-mark{font-size:9.5px;line-height:1;text-align:center;color:#8a8781;}",
    // cursor:text lives on the ROW, not here: the double-click listener is on the
    // row, so pointing at the index, the bolt or the time must look editable too.
    ".pix-rl-row{cursor:text;}",
    ".pix-rl-lbl{font-size:11px;color:#b8b4ad;justify-self:stretch;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}",
    // Discoverability: an unlabelled row ALWAYS reads "add note", like
    // placeholder text in a form, in the same grey as the row numbers so it
    // recedes once real labels are typed. (A hover-only hint was tried first and
    // was invisible in practice - user feedback, 2026-07-23.) It brightens on
    // hover so the row still confirms it is interactive.
    ".pix-rl-lbl--empty::after{content:'add note';color:#6c6960;transition:color 0.12s;}",
    ".pix-rl-row:hover .pix-rl-lbl--empty::after{color:#9a968e;}",
    // On the newest row the backdrop is orange-tinted, so the neutral grey would
    // read as dead - warm it to match.
    ".pix-rl-row--now .pix-rl-lbl--empty::after{color:#a8776a;}",
    ".pix-rl-row--now:hover .pix-rl-lbl--empty::after{color:#d9917f;}",
    // The inline editor takes the label's grid column and centres in the 20px
    // row, so the row never shifts VERTICALLY when it opens (the text does move
    // right by the border + padding, which is deliberate - it reads as a field).
    // Explicit line-height so an 11px font in a 14px content box cannot clip a
    // descender on a different font stack.
    ".pix-rl-lblin{grid-column:3;justify-self:stretch;min-width:0;width:100%;box-sizing:border-box;height:16px;line-height:14px;font-family:'Segoe UI',system-ui,sans-serif;font-size:11px;color:#e6e2da;background:#1d1d1d;border:1px solid var(--pix-acc,#f66744);border-radius:3px;padding:0 4px;outline:none;-webkit-user-select:text;user-select:text;}",
    ".pix-rl-lblin::placeholder{color:#57544d;}",
    ".pix-rl-time{font-family:'Consolas','DejaVu Sans Mono',ui-monospace,monospace;font-variant-numeric:tabular-nums;font-size:13px;color:#b8b4ad;font-weight:500;}",
    ".pix-rl-row--now{background:color-mix(in srgb, var(--pix-acc,#f66744) 16%, transparent);box-shadow:inset 2px 0 0 var(--pix-acc,#f66744);}",
    ".pix-rl-row--now:hover{background:color-mix(in srgb, var(--pix-acc,#f66744) 24%, transparent);}",
    // The row classes are mutually exclusive, so when the newest run is ALSO the
    // fastest it carries --now only and the --best bolt rule never applies. Warm
    // the bolt here or it is the one grey element left on an orange row.
    ".pix-rl-row--now .pix-rl-mark{color:var(--pix-acc,#f66744);}",
    ".pix-rl-row--now .pix-rl-time{color:var(--pix-acc,#f66744);font-weight:700;}",
    ".pix-rl-row--now .pix-rl-idx{color:#ff8a63;}",
    ".pix-rl-row--now .pix-rl-lbl{color:#f0cfc4;}",
    ".pix-rl-row--best .pix-rl-time{color:#49c97a;font-weight:600;}",
    ".pix-rl-row--best .pix-rl-mark{color:#49c97a;}",
    ".pix-rl-empty{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:5px;}",
    ".pix-rl-empty-t{font-family:'Consolas','DejaVu Sans Mono',ui-monospace,monospace;font-size:13px;color:#7a776f;}",
    ".pix-rl-empty-s{font-size:11px;color:#57544d;}",
    // Footer: two subtle icon buttons, right-aligned (Export .txt, Clear). Grey
    // icon → brand orange on hover (Pixaroma UI convention #13).
    // margin-top:auto keeps the buttons in the bottom corner if the node is
    // dragged taller than the exact fit (spare height falls between the panel
    // and the footer rather than stranding the footer mid-node).
    ".pix-rl-foot{display:flex;align-items:center;justify-content:flex-end;gap:2px;flex:none;margin-top:auto;height:20px;padding:0 2px;}",
    // The optional hardware line shares the footer ROW with those buttons, so it
    // costs ZERO height - the strip is 20px either way and none of the sizing
    // constants in #5 move. margin-right:auto pushes it left of the buttons and
    // beats the container's justify-content, so the buttons stay in the corner.
    // min-width:0 is required for the ellipsis: a flex item's default
    // min-width:auto refuses to shrink below its text and would push the buttons
    // out of the node instead of truncating. A narrow node therefore clips the
    // line and widening the node reveals it, which is the agreed behaviour.
    ".pix-rl-hw{margin-right:auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"
      + "font-family:'Consolas','DejaVu Sans Mono',ui-monospace,monospace;font-size:10px;color:#57544d;"
      + "letter-spacing:0.02em;padding-left:3px;cursor:default;user-select:none;}",
    // The breathing room between the text and the first button goes on the
    // BUTTON, not on the text. Measured, not reasoned: `padding-right` on the
    // text looks right while the line fits but does NOTHING once it truncates
    // (the clip happens at the padding box, so the ellipsis still lands hard
    // against the icon - 2px, verified at a 200px-wide node). The container's
    // flex `gap:2px` is likewise too tight for text-next-to-a-button, though it
    // is fine between the two icons. A margin on the sibling sits outside the
    // text box entirely, so the gap holds in BOTH the fitting and the truncated
    // case. margin-right:auto on the text still does the pushing.
    ".pix-rl-hw + .pix-rl-fbtn{margin-left:8px;}",
    ".pix-rl-fbtn{display:inline-flex;align-items:center;justify-content:center;width:22px;height:18px;border:0;background:transparent;cursor:pointer;border-radius:4px;padding:0;}",
    ".pix-rl-fbtn:hover{background:rgba(255,255,255,0.06);}",
    ".pix-rl-fbtn:disabled{opacity:0.3;cursor:default;}",
    ".pix-rl-fbtn:disabled:hover{background:transparent;}",
    // The root clips, and the buttons sit flush in the corner, so pull the
    // keyboard focus ring inside or it loses an edge.
    ".pix-rl-fbtn:focus-visible{outline-offset:-2px;}",
    ".pix-rl-ico{width:13px;height:13px;background-color:#7a776f;-webkit-mask-position:center;mask-position:center;-webkit-mask-repeat:no-repeat;mask-repeat:no-repeat;-webkit-mask-size:contain;mask-size:contain;transition:background-color 0.12s;}",
    ".pix-rl-fbtn:hover:not(:disabled) .pix-rl-ico{background-color:var(--pix-acc,#f66744);}",
    // Hide any native widget-input dot column beside our DOM widget in Nodes 2.0
    // (the node has no inputs, so there is nothing to plug in).
    ".lg-node:has(.pix-rl-root) .lg-node-widget > *:first-child:empty{display:none;}",
    // ...and then make our cell span the WHOLE row. Nodes 2.0 lays widgets out
    // on a 3-column subgrid (`min-content minmax(80px,min-content)
    // minmax(125px,1fr)`) and gives a DOM widget `col-span-2`. With the dot
    // column hidden above, that span lands on columns 1-2 and leaves column 3
    // (125px) as DEAD SPACE on the right: measured on a 300px node, the widget
    // was 245.3px and everything - caption, list, footer buttons - sat shoved
    // left with a gap the Classic renderer does not have. `1 / -1` takes it to
    // 288px (the remaining 12px is the row's own right padding), which puts the
    // footer buttons 14px from the node edge, matching Classic.
    // Scoped to our own node so it cannot affect any other pack's widgets, and
    // a no-op in Classic, which has no .lg-node.
    ".lg-node:has(.pix-rl-root) .lg-node-widget > *:has(> .pix-rl-root){grid-column:1 / -1;}",
    // ...and give back the LEFT inset that spanning column 1 just took away.
    // Core styles the widget row `padding: 0 12px 0 0` - right only - because
    // normally column 1 IS the input-dot column and that is what insets the
    // content from the left edge. We hide that column (no inputs) and span
    // across it, so the body ended up flush against the node's left edge while
    // the right kept its 12px: measured leftGap 0 / rightGap 12, which reads as
    // the panel being shoved into the corner. 12px matches core's own right
    // padding exactly, so the two sides are symmetric (Classic is already
    // symmetric on its own, and has no .lg-node, so this cannot touch it).
    ".lg-node:has(.pix-rl-root) .lg-node-widget{padding-left:12px;}",
  ].join("\n");
  (document.head || document.documentElement).appendChild(s);
}

// ── node setup ──────────────────────────────────────────────────────────────
function setupNode(node) {
  injectCSS();
  node._rlRunning = false;
  node._rlRunStart = null;

  const root = el("div", "pix-rl-root");
  const cap = el("div", "pix-rl-cap");
  const lbl = el("span", "pix-rl-caplbl"); lbl.textContent = "Last 10 runs";
  const status = el("span", "pix-rl-status");
  cap.appendChild(lbl); cap.appendChild(status);
  const screen = el("div", "pix-rl-screen");
  const foot = el("div", "pix-rl-foot");
  // Shares the footer row with the buttons, so it adds NO height (see the CSS).
  // First child + margin-right:auto puts it left, buttons stay in the corner.
  const hw = el("div", "pix-rl-hw");
  hw.style.display = "none";
  const exportBtn = iconBtn("download.svg", "Export the times as a .txt file");
  const clearBtn = iconBtn("delete.svg", "Clear the list");
  exportBtn.addEventListener("click", (e) => { e.stopPropagation(); exportTxt(node); });
  clearBtn.addEventListener("click", (e) => { e.stopPropagation(); clearHistory(node); });
  foot.appendChild(hw); foot.appendChild(exportBtn); foot.appendChild(clearBtn);
  root.appendChild(cap); root.appendChild(screen); root.appendChild(foot);

  node._pixRlRoot = root;
  node._pixRlScreen = screen;
  node._pixRlStatus = status;
  node._pixRlExportBtn = exportBtn;
  node._pixRlClearBtn = clearBtn;
  node._pixRlHw = hw;
  renderHw(node);

  installCanvasZoomPassthrough(root);
  installNodeAccent(node, root);   // the face follows this node's accent colour
  const widget = node.addDOMWidget("run_log_ui", "pixaroma_run_log", root, {
    getValue: () => "",
    setValue: () => {},
    getMinHeight: () => WIDGET_MIN_H,
    serialize: false, // history lives on node.properties
  });
  applyAdaptiveCanvasOnly(widget);
  // computeLayoutSize makes the widget an 'auto' grower in Nodes 2.0 so the screen
  // fills the node height; minWidth:1 lets the saved node width round-trip.
  // LAYOUT_MIN_H, not WIDGET_MIN_H: this is the number LiteGraph's computeSize
  // consumes, and it over-reserves by 16 (see the constant's derivation). The
  // TRUE content height still governs everywhere it matters - getMinHeight above
  // (which feeds distributeSpace) and installResizeFloor below (the Nodes 2.0
  // drag floor) - so the panel can never be squeezed below its 10 rows.
  widget.computeLayoutSize = () => ({ minHeight: LAYOUT_MIN_H, minWidth: 1 });
  node._pixRlWidget = widget;
  node._pixRlFloorOff = installResizeFloor(root, () => WIDGET_MIN_H);

  // Fresh-drop default size. configure() runs AFTER nodeCreated (Vue Compat #8/#9)
  // and restores the saved size for a loaded workflow / duplicate, so existing
  // nodes keep their size. Mutate size[0/1] (don't replace the array) for Vue's
  // reactive proxy.
  if (Array.isArray(node.size)) { node.size[0] = DEFAULT_W; node.size[1] = DEFAULT_H; }
  else node.size = [DEFAULT_W, DEFAULT_H];

  _logs.add(node);
  // Render after configure restores node.properties (Vue Compat #8). Read-only →
  // dirty-on-load safe.
  queueMicrotask(() => renderList(node));
}

// ── help ─────────────────────────────────────────────────────────────────────
const HELP = {
  title: "Run Log Pixaroma",
  tagline: "Keeps the last 10 run times for this workflow on the canvas.",
  sections: [
    { heading: "What it does", body: "A companion to Run Timer. Every time you press Run it times the whole workflow and adds the finished time to the top of the list. It keeps the last 10, newest first, so you can watch a workflow get faster over a session or notice when a change has made it slower." },
    { heading: "Reading the list", body: "The newest run sits at the top, highlighted in orange with an orange bar down its left edge. The fastest of the ten is marked with a lightning bolt, in green (or in orange when the newest run is also the fastest). Times under a minute show as seconds (for example 14.8s); longer runs show as minutes and seconds (for example 1:23). While a run is going a small green 'running' marker shows in the corner, and the new time drops in on top the moment it finishes." },
    { heading: "Label your runs", body: "A list of times tells you that something changed, not what. Double-click any row and type a short note about that run: 'with style lora', 'seed 12345', 'base, no LLM'. Press Enter to save, or click away, which also saves. Escape leaves it as it was. Clearing the text removes the note again.\n\nThe note belongs to that run, so as newer runs push it down the list it travels with its own time, and it disappears with it when it drops off the bottom. Notes are saved in the workflow like the times, and they are included when you export or copy the list." },
    { heading: "This workflow only", body: "The list lives on the node and is saved inside the workflow, so it is only the times for this workflow and it stays with it. Open the workflow again another day and the list is still there. A different workflow keeps its own separate list." },
    { heading: "The two buttons", body: "In the bottom-right corner are two small buttons. The download icon exports the list as a plain .txt file you can save or share. The trash icon clears the list back to 'No runs yet'. The same actions are also on the right-click menu, along with Copy times." },
    { heading: "Showing your hardware", body: "Times only mean something next to the machine that produced them, which matters if you share a screenshot or compare with someone else. Open the gear on the node and switch on 'Show this PC's hardware' to add a small line in the bottom corner, next to those two buttons: your graphics card, its memory and your system memory, for example 'RTX 4090 · 24GB VRAM · 128GB RAM'.\n\nIt sits on the same row as the buttons, so the node does not change size. If your node is narrow the line is cut off with dots at the end: hover it to read the whole thing, or drag the node wider.\n\nThe line is read fresh from ComfyUI each time and is never saved into your workflow, so sharing a workflow file never tells anyone what is inside your PC. The switch applies to every Run Log node you have, since they would all show the same machine anyway. It is off until you turn it on, and it is not included in the exported .txt file." },
    { heading: "Right-click options", defs: [
      ["Copy times", "Copies the whole list as plain text, with your notes, so you can paste it into notes or a message."],
      ["Export as .txt", "Saves the list as a plain text file (same as the download button)."],
      ["Clear Run Log", "Empties the list for this node, back to 'No runs yet' (same as the trash button)."],
    ]},
    { heading: "Good to know", body: "It does not need to be wired to anything; just drop it on the canvas. The node always shows all ten slots and cannot be made too small to read them. Only completed runs are logged; a run you stop or that errors out is skipped. Because the list is saved with the workflow, a small 'unsaved changes' dot appears on the tab after a run, which is normal. It works the same in both the classic and the new node interface." },
  ],
};

app.registerExtension({
  name: "Pixaroma.RunLog",

  setup() {
    installRunListeners();
  },

  getNodeMenuItems(node) {
    // node.type fallback (comfyClass isn't populated on every build/timing).
    if (!node || (node.type !== NODE_NAME && node.comfyClass !== NODE_NAME)) return [];
    const empty = getHist(node).length === 0;
    return [
      null,
      { content: "📋 Copy times", disabled: empty, callback: () => copyTimes(node) },
      { content: "💾 Export as .txt", disabled: empty, callback: () => exportTxt(node) },
      { content: "🧹 Clear Run Log", disabled: empty, callback: () => clearHistory(node) },
    ];
  },

  beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== NODE_NAME) return;
    if (nodeType.prototype._pixRlPatched) return; // hot-reload: don't double-wrap
    nodeType.prototype._pixRlPatched = true;

    // Re-render from restored node.properties on load. READ-ONLY → dirty-on-load
    // safe (never writes serialized state here).
    const _origConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function (info) {
      // CANCEL an open editor, never flush it. This is the one destroyer of the
      // history that must NOT commit: setLabel would be a node.properties write
      // on the load path, i.e. the false "Save Changes?" bug Pattern #3 forbids.
      // Nulling also kills a closure that would otherwise outlive its list.
      this._pixRlCommitEdit = null;
      const r = _origConfigure ? _origConfigure.apply(this, arguments) : undefined;
      renderList(this);
      return r;
    };

    const _origRemoved = nodeType.prototype.onRemoved;
    nodeType.prototype.onRemoved = function () {
      _logs.delete(this);
      // Nulling the handle only blocks an EXTERNAL flush; the open input's own
      // blur listener still holds its commit closure. _pixRlDead is what that
      // closure checks, so a label can never be written to a deleted node.
      this._pixRlDead = true;
      this._pixRlCommitEdit = null;
      try { if (this._pixRlFloorOff) this._pixRlFloorOff(); } catch (_e) {}
      this._pixRlFloorOff = null;
      if (_origRemoved) return _origRemoved.apply(this, arguments);
    };

    // LEGACY-ONLY min clamps (Nodes 2.0 gotcha #1: clamping node.size in Vue
    // desyncs the layout store → jump-on-switch). Nodes 2.0 floors via
    // installResizeFloor + computeLayoutSize instead.
    const _origResize = nodeType.prototype.onResize;
    nodeType.prototype.onResize = function (size) {
      if (!isVueNodes()) {
        if (this.size[0] < MIN_W) this.size[0] = MIN_W;
        if (this.size[1] < MIN_H) this.size[1] = MIN_H;
      }
      if (_origResize) return _origResize.apply(this, arguments);
    };
    const _origFg = nodeType.prototype.onDrawForeground;
    nodeType.prototype.onDrawForeground = function (ctx) {
      const r = _origFg ? _origFg.apply(this, arguments) : undefined;
      if (ctx && !isVueNodes() && !this.flags?.collapsed) {
        if (this.size[0] < MIN_W) this.size[0] = MIN_W;
        if (this.size[1] < MIN_H) this.size[1] = MIN_H;
      }
      return r;
    };
  },

  nodeCreated(node) {
    if (node.type !== NODE_NAME && node.comfyClass !== NODE_NAME) return;
    setupNode(node);
  },
});

registerNodeHelp(NODE_NAME, HELP);

// The colour option: a right-click "Run Log settings" entry, the gear in the
// selection toolbar, and the shared colour panel behind both.
registerNodeAccent("PixaromaRunLog", {
  title: "Run Log",
  rows: [
    { kind: "toggle", setting: SETTING_SHOW_HW, defaultValue: false,
      label: "Show this PC's hardware",
      hint: "Adds a small line in the bottom corner: graphics card, its memory and system memory. It shares the row with the two buttons, so the node does not change size. Widen the node if the text is cut off. It is read fresh each time and is never saved into your workflow." },
  ],
  // ⚠️ onRowChange, NOT onChange - the panel wires the option rows to
  // `def.onRowChange` and reserves `onChange` for the accent colour, so a row
  // handler put on `onChange` is simply never called (first build did that and
  // the toggle appeared dead). The VALUE is passed straight through rather than
  // re-read, per the onChange-fires-before-the-write rule.
  // Every Run Log node shows the same machine, so one toggle repaints them all.
  onRowChange: (n, setting, value) => renderHwAll(value),
});
