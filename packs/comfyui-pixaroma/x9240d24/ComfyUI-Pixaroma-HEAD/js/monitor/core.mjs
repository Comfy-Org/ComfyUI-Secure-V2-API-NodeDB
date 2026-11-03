// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  Monitor Pixaroma - state, the metric model, and the shared geometry     ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// Both renderers draw from THIS file, which is the whole point of it: the M
// table below is multiplied by the scale in the classic canvas painter AND in
// the Nodes 2.0 CSS, so the two faces cannot drift apart. Run Timer learned that
// the hard way (its pattern file #1c) - two separate width formulas that agreed
// until the day one of them changed.
//
// The live numbers are deliberately NOT part of the state. A monitor writes a
// new reading every second, and node.properties is SERIALIZED: persisting a
// reading would mark the workflow modified on every tick and fill the undo
// history with nothing (Vue Compat #18). Readings live on runtime fields and on
// the module cache in poll.mjs; only the SETTINGS are state.

export const NODE_NAME = "PixaromaMonitor";
export const STATE_PROP = "monitorState";

// ── sizes at scale 1 ────────────────────────────────────────────────────────
// Every number here is multiplied by the node's scale. Keep them in step with
// the CSS in ui.mjs, which is written as calc() off the same values.
export const M = {
  padX: 9,
  padY: 7,
  gap: 5,
  titleH: 11,     // the small device line at the top
  rowH: 13,       // a bar row: label + track + value
  barH: 9,
  barR: 3,
  labelW: 38,
  valueW: 88,
  stripH: 12,     // the temp / power / peak line
  btnH: 20,
  font: 11,
  titleFont: 9,
  stripFont: 10,
  btnFont: 10.5,
};

// The floor is set by the WIDEST line the face can hold, which is the temp /
// power / peak strip ("TEMP 40° PWR 69 W PEAK 1.5 GB" is about 174px of mono at
// scale 1, plus its gaps and the padding), NOT by the bar rows. It doubles as
// the width the auto-widen pulls a scaled-up node out to, so getting it from the
// widest line is what stops a 2x node clipping its own last readout.
export const MIN_W = 215;

// The width a fresh node opens at. (An earlier revision also used this in an
// "is this width ours" ownership test for the Size control - that heuristic
// ratcheted and is gone; see index.js::scaledWidth for the model that replaced
// it.)
export const BASE_W = 305;
export const MIN_S = 1;     // the drag floor: never smaller than the design size
export const MAX_S = 5;     // sanity cap, so one wild drag cannot fill the canvas

// Bars turn amber then red so COLOUR ONLY EVER MEANS "getting tight". Everything
// else on the face is the node's accent, which is why a coloured bar reads as a
// warning instead of as decoration.
export const WARN_PCT = 85;
export const CRIT_PCT = 95;
export const WARN_COLOR = "#e8a33d";
export const CRIT_COLOR = "#e05252";

// ── the readouts ────────────────────────────────────────────────────────────
// `bar` entries are a row with a track; `scalar` entries share the one-line
// strip under them. The ORDER here is the order they appear on the node.
export const BARS = [
  { key: "vram", label: "VRAM", hint: "Video memory in use on the graphics card, out of its total." },
  { key: "ram", label: "RAM", hint: "System memory in use, out of the total installed." },
  { key: "gpu", label: "GPU", hint: "How busy the graphics card is right now." },
  { key: "cpu", label: "CPU", hint: "How busy the processor is right now." },
  { key: "comfy", label: "COMFY", hint: "Video memory ComfyUI itself is holding, mostly loaded models." },
  { key: "sysram", label: "COMFY R", hint: "System memory the ComfyUI process is using." },
];

export const SCALARS = [
  { key: "temp", label: "TEMP", hint: "Graphics card temperature." },
  { key: "power", label: "PWR", hint: "Power the graphics card is drawing." },
  { key: "peak", label: "PEAK", hint: "The highest video memory reached during the last run." },
];

export const BUTTONS = [
  {
    key: "free",
    label: "Free VRAM",
    hint: "Unload the models and clear the cached results, the same as ComfyUI's own Free model and node cache. The next run reloads everything.",
  },
  {
    key: "unload",
    label: "Unload models",
    hint: "Unload the models but keep the cached results, so parts of the graph that did not change are not recomputed.",
  },
  { key: "reset", label: "Reset peak", hint: "Clear the peak mark and start measuring again." },
  {
    key: "settings",
    label: "Settings",
    // The BUNDLED gear SVG, never the ⚙ emoji (house rule #28): an emoji is drawn
    // by the operating system, so it is a different shape on Windows, Mac and
    // Linux and sits on its own baseline. `compact` keeps it a square at the end
    // of the row so the two text buttons get the rest of the width.
    icon: "gear",
    compact: true,
    hint: "Choose which readouts to show, the layout, the size and how often it updates. The same panel as right-clicking the node.",
  },
];

export const DEFAULT_STATE = {
  version: 1,
  layout: "bars",            // "bars" | "strip"
  scale: 1,                  // the portable size (see the note in index.js)
  device: 0,                 // which card, when there is more than one
  show: {
    vram: true,
    ram: true,
    gpu: true,
    cpu: true,
    comfy: false,
    sysram: false,
    temp: true,
    power: true,
    peak: true,
  },
  buttons: { free: true, unload: false, reset: true, settings: true },
  interval: 1000,            // ms between samples
  fastWhileRunning: true,    // sample 3x faster while a workflow is running
  warn: true,                // amber past 85%, red past 95%
  pauseHidden: true,         // stop sampling while the browser tab is hidden
  showTitle: true,           // the small card-name line at the top
};

export function readState(node) {
  const raw = node?.properties?.[STATE_PROP];
  const st = { ...DEFAULT_STATE, ...(raw && typeof raw === "object" ? raw : {}) };
  st.show = { ...DEFAULT_STATE.show, ...(raw?.show || {}) };
  st.buttons = { ...DEFAULT_STATE.buttons, ...(raw?.buttons || {}) };
  return st;
}

// ONLY ever called from a real user action - never from the load path and never
// from a sample (Vue Compat #18).
export function writeState(node, patch) {
  if (!node) return readState(node);
  node.properties = node.properties || {};
  const next = { ...readState(node), ...(patch || {}) };
  if (patch && patch.show) next.show = { ...readState(node).show, ...patch.show };
  if (patch && patch.buttons) next.buttons = { ...readState(node).buttons, ...patch.buttons };
  node.properties[STATE_PROP] = next;
  return next;
}

// ── formatting ──────────────────────────────────────────────────────────────
const GB = 1024 * 1024 * 1024;

export function gbNum(bytes) {
  const v = (Number(bytes) || 0) / GB;
  // one decimal while it still means something; a 128 GB machine does not need
  // to be told it has 128.0
  return v >= 100 ? String(Math.round(v)) : v.toFixed(1);
}

function clampPct(v) {
  if (v == null || !isFinite(v)) return null;
  return Math.max(0, Math.min(100, v));
}

const NA = "–";   // en dash: a readout this machine cannot supply

/**
 * Turn one sample into the rows the face draws.
 *
 * ⚠️ THE ROW SET COMES FROM THE SETTINGS, NEVER FROM WHICH DATA HAPPENED TO
 * ARRIVE. A row that dropped out when its number was missing would change the
 * node's HEIGHT - as the first sample lands, when nvidia-smi answers a moment
 * after psutil, and every time a reading is missed. `node.size` is serialized,
 * so a height that moves on its own marks a workflow modified for no reason
 * (Vue Compat #18), and a face whose rows shuffle while you read it is horrible
 * besides. So an enabled readout ALWAYS keeps its row and shows a dash until it
 * has something to say.
 *
 * Each row is `{key, label, pct, main, tail, hint}` and `pct` may be null, which
 * means "no track" - an honest blank rather than a confident-looking 0%.
 */
export function barRows(node, st, sample) {
  const dev = pickDevice(st, sample);
  const ram = sample?.ram;
  const out = [];
  const add = (key, label, pct, main, tail, hint) => {
    if (!st.show[key]) return;
    out.push({
      key,
      label,
      pct: clampPct(pct),
      main: main == null ? NA : main,
      tail: main == null ? "" : tail,
      hint,
    });
  };

  add("vram", "VRAM",
    dev && dev.total ? (dev.used / dev.total) * 100 : null,
    dev ? gbNum(dev.used) : null,
    dev ? "/" + gbNum(dev.total) + " GB" : "",
    BARS[0].hint);
  add("ram", "RAM", ram?.pct ?? null,
    ram ? gbNum(ram.used) : null,
    ram ? "/" + gbNum(ram.total) + " GB" : "",
    BARS[1].hint);
  add("gpu", "GPU", dev?.util ?? null,
    dev?.util == null ? null : String(Math.round(dev.util)), "%", BARS[2].hint);
  add("cpu", "CPU", sample?.cpu?.pct ?? null,
    sample?.cpu?.pct == null ? null : String(Math.round(sample.cpu.pct)), "%", BARS[3].hint);
  add("comfy", "COMFY",
    dev && dev.torchUsed != null && dev.total ? (dev.torchUsed / dev.total) * 100 : null,
    dev && dev.torchUsed != null ? gbNum(dev.torchUsed) : null, " GB", BARS[4].hint);
  add("sysram", "COMFY R", sample?.proc?.pct ?? null,
    sample?.proc?.used == null ? null : gbNum(sample.proc.used), " GB", BARS[5].hint);
  return out;
}

/** Same rule as barRows: an enabled readout keeps its place and shows a dash. */
export function scalarItems(st, sample, peak) {
  const dev = pickDevice(st, sample);
  const out = [];
  if (st.show.temp) {
    out.push({
      key: "temp", label: "TEMP",
      text: dev?.temp == null ? NA : Math.round(dev.temp) + "°",
      hot: dev?.temp != null && dev.temp >= 80,
      hint: SCALARS[0].hint,
    });
  }
  if (st.show.power) {
    out.push({
      key: "power", label: "PWR",
      text: dev?.power == null ? NA : Math.round(dev.power) + " W",
      hint: SCALARS[1].hint,
    });
  }
  if (st.show.peak) {
    out.push({
      key: "peak", label: "PEAK",
      text: peak?.used > 0 ? gbNum(peak.used) + " GB" : NA,
      hint: SCALARS[2].hint,
    });
  }
  return out;
}

export function pickDevice(st, sample) {
  const list = sample?.devices;
  if (!Array.isArray(list) || !list.length) return null;
  const i = Math.max(0, Math.min(list.length - 1, Number(st?.device) || 0));
  return list[i];
}

export function deviceLabel(dev) {
  if (!dev) return "";
  // "cuda:0 NVIDIA GeForce RTX 4090 : cudaMallocAsync" is what ComfyUI reports;
  // only the card's name is worth the pixels.
  let s = String(dev.name || "");
  s = s.replace(/^\s*\w+:\d+\s*/, "").replace(/\s*:\s*cuda\w*$/i, "").trim();
  s = s.replace(/^NVIDIA\s+/i, "").replace(/^GeForce\s+/i, "");
  return s || "GPU";
}

// ── the label column sizes itself to the longest ENABLED label ─────────────
// M.labelW is only the MINIMUM. A fixed column truncated "COMFY R" to "COMF…"
// at every size (user-reported with screenshots): the column is scaled by the
// same factor as the text, so making the node larger grows the box and the
// text together and the fit never changes. Measured once per label set on a
// shared canvas ctx; both faces read this, so they stay in step.
let _lwCanvas = null;
const _lwCache = new Map();

export function labelUnitWidth(rows) {
  const key = rows.map((r) => r.label).join("|");
  const hit = _lwCache.get(key);
  if (hit) return hit;
  let w = M.labelW;
  try {
    if (!_lwCanvas) _lwCanvas = document.createElement("canvas");
    const c = _lwCanvas.getContext("2d");
    c.font = `${M.font}px ui-monospace, "Cascadia Mono", Consolas, monospace`;
    for (const r of rows) {
      // +3 covers the DOM face's .03em letter-spacing, which the canvas
      // measurement does not include
      w = Math.max(w, Math.ceil(c.measureText(r.label).width) + 3);
    }
  } catch (_e) {
    /* no canvas (tests): the minimum column */
  }
  if (_lwCache.size > 16) _lwCache.clear();
  _lwCache.set(key, w);
  return w;
}

// ── how wide the STRIP layout needs to be, at scale 1 ───────────────────────
// Deterministic from the SETTINGS ONLY, like the row set (#1 in the pattern
// file): a width that followed the LIVE numbers would jitter as readings change
// width, and node.size is serialized. So each enabled readout reserves room for
// its widest plausible reading ("888.8" GB, "100%", "100°", "888 W"), measured
// in the face's own font. Mirrors the classic painter's strip arithmetic
// (label + space, 30px mini bar + gap, value, " · " separators) with slack on
// top, so neither face can clip inside this width.
const STRIP_MAX_VAL = {
  vram: "888.8", ram: "888.8", comfy: "888.8", sysram: "888.8",
  gpu: "100%", cpu: "100%",
};
const _swCache = new Map();

export function stripUnitWidth(st) {
  const segs = [];
  for (const b of BARS) {
    if (st.show[b.key]) segs.push({ label: b.label + " ", mini: true, val: STRIP_MAX_VAL[b.key] || "888.8" });
  }
  if (st.show.temp) segs.push({ label: "", mini: false, val: "100°" });
  if (st.show.power) segs.push({ label: "", mini: false, val: "888 W" });
  if (st.show.peak) segs.push({ label: "", mini: false, val: "88.8 GB" });
  const key = segs.map((x) => x.label + "|" + x.val).join(";");
  const hit = _swCache.get(key);
  if (hit) return hit;
  let w = M.padX * 2;
  try {
    if (!_lwCanvas) _lwCanvas = document.createElement("canvas");
    const c = _lwCanvas.getContext("2d");
    c.font = `${M.font}px ui-monospace, "Cascadia Mono", Consolas, monospace`;
    segs.forEach((sg, i) => {
      if (i) w += c.measureText(" · ").width;
      w += c.measureText(sg.label).width;
      if (sg.mini) w += 30 + 5;
      w += c.measureText(sg.val).width;
    });
    w = Math.ceil(w) + 8;   // slack for the DOM face's flex gaps vs the spaces
  } catch (_e) {
    w = MIN_W;   // no canvas (tests): a sane constant
  }
  w = Math.max(w, MIN_W);
  if (_swCache.size > 16) _swCache.clear();
  _swCache.set(key, w);
  return w;
}

export function barColor(pct, accent, warn) {
  if (!warn || pct == null) return accent;
  if (pct >= CRIT_PCT) return CRIT_COLOR;
  if (pct >= WARN_PCT) return WARN_COLOR;
  return accent;
}

// ── geometry ────────────────────────────────────────────────────────────────
// The list of blocks the face is made of, at scale 1. Both renderers walk this,
// so a row added here appears in both without touching either painter.
export function faceBlocks(node, st, sample, peak) {
  const blocks = [];
  const dev = pickDevice(st, sample);
  if (st.layout === "strip") {
    blocks.push({ kind: "strip1", h: M.stripH + 2 });
  } else {
    if (st.showTitle) blocks.push({ kind: "title", h: M.titleH, text: deviceLabel(dev) });
    for (const r of barRows(node, st, sample)) blocks.push({ kind: "bar", h: M.rowH, row: r });
    const sc = scalarItems(st, sample, peak);
    if (sc.length) blocks.push({ kind: "strip", h: M.stripH, items: sc });
  }
  const btns = visibleButtons(st);
  if (btns.length) blocks.push({ kind: "buttons", h: M.btnH, items: btns });
  return blocks;
}

export function visibleButtons(st) {
  return BUTTONS.filter((b) => st.buttons[b.key]);
}

/** Height of the whole face at scale 1, for the current settings. */
export function contentHeight(node, st, sample, peak) {
  const blocks = faceBlocks(node, st, sample, peak);
  let h = M.padY * 2;
  blocks.forEach((b, i) => {
    h += b.h + (i ? M.gap : 0);
  });
  // an empty face (every readout switched off) still needs to be grabbable
  return Math.max(h, M.padY * 2 + M.rowH);
}
