// Free VRAM Pixaroma - state and geometry.
//
// Vue Compat #9: everything lives on node.properties.freeVramState and is
// injected into the hidden FreeVramState input at graphToPrompt time, so the
// node has no visible widgets and no stray input dot.

export const CLASS = "PixaromaFreeVram";
export const HIDDEN_INPUT = "FreeVramState";
export const STATE_PROP = "freeVramState";

// The chips. Mirrors MODES in nodes/_free_vram_helpers.py - if you add one,
// add it there too or Python will quietly fall back to "all".
export const MODE_ALL = "all";
export const MODE_MODELS = "models";
export const MODE_CACHE = "cache";

export const MODES = [
  {
    id: MODE_ALL,
    label: "All",
    title: "Let go of the models AND hand the spare memory back to the card. " +
           "The one to use when the next stage needs room.",
  },
  {
    id: MODE_MODELS,
    label: "Models",
    title: "Let go of the models but let ComfyUI keep its reserved memory. " +
           "Slightly faster, and enough when only ComfyUI itself needs the room.",
  },
  {
    id: MODE_CACHE,
    label: "Cache",
    title: "Keep the models loaded and only hand the spare memory back to the " +
           "card. Use this when something OUTSIDE ComfyUI wants the card.",
  },
];

// Mirrors THRESHOLD_MIN_GB / THRESHOLD_MAX_GB in the Python helpers.
export const THRESHOLD_MIN_GB = 0.5;
export const THRESHOLD_MAX_GB = 128;

export const DEFAULT_STATE = {
  // --- what Python reads (these, and ONLY these, reach the prompt) ---------
  mode: MODE_ALL,
  gc: true,
  everyRun: true,
  useThreshold: false,
  thresholdGb: 8,
  // --- how the face looks (never sent; see injectedState) ------------------
  showBar: true,
};

// The keys Python reads. Anything else is presentation, and sending it would
// change the node's cache signature - so hiding the bar would silently re-run
// the whole workflow downstream.
const PROMPT_KEYS = ["mode", "gc", "everyRun", "useThreshold", "thresholdGb"];

// ── geometry ───────────────────────────────────────────────────────────────
export const MIN_W = 250;
export const DEFAULT_W = 290;
// Trimmed 2026-08-24 on the user's "save some space in height". Nodes 2.0
// already puts a 4px gap above the widget and 12px of its own padding plus a
// 20px node-pack badge row below it, so OUR padding is the only part of that
// stack we own - and 6px on top of core's 4px read as a gap. Every value here
// is deliberate: ROW_H is the chip height, BAR_H is thin enough to read as a
// rule rather than a control, and READOUT_H fits 11px text with no clipping.
// PAD_X and PAD_Y are separate: the sides need real padding so the chips do not
// touch the node edge, but every vertical pixel here sits between the input dots
// and the buttons, which is the gap the user kept pointing at.
export const PAD_X = 6;
// ZERO. Core already pads above and below the widget block in Nodes 2.0, and
// LiteGraph gives the element a margin in Classic, so any vertical padding of
// ours is padding on top of padding.
export const PAD_Y = 0;
// EXACTLY the chip's own height (4px padding x2 + 13.2 line + 1px border x2).
// It was 26, which centred a 23px chip and left 1.5px of slack above it.
// DO NOT shrink further by trimming the chip's padding: the chips are the
// node's main control and the height that is left is the control itself.
export const ROW_H = 23;
// A rule, not a control - nobody clicks it, so it only has to be readable.
// 8, not 6: it carries THREE tones plus hairline separators, and at 6 the two
// greys were not tellable apart. Readability wins the 2px back off the trim.
export const BAR_H = 8;
// MEASURED IN THE TALLEST STATE, which is the one with a result on screen: the
// 13px bold freed-amount renders the row at 17px, while every other wording
// needs 15-16. Declaring the tallest is what keeps the face a FIXED height
// whatever it is saying - a height that changed after a run would leave Classic
// (where the element gets exactly node.size[1] - 46) shaving the number.
// Two wrong values were measured on the way here: 14 from the plain 11px text,
// and 16 from the empty state, because the unwired hint correctly takes priority
// over the report and hid the bold from the test.
export const READOUT_H = 17;
export const GAP = 2;
// Nodes 2.0 puts `gap-1` (4px) between the slot block and the widget block.
// A negative top margin on our root cancels it, which is the only way to reach
// that particular 4px - it belongs to core's body, not to us. Vue-only: Classic
// has no such gap, and pulling up there would ride into the slot row.
export const VUE_GAP_CANCEL = 4;

/** The height the face's own content needs, with the bar shown or not. */
export function contentHeight(showBar = true) {
  const bar = showBar ? BAR_H + GAP : 0;
  return PAD_Y * 2 + ROW_H + GAP + bar + READOUT_H;
}

function clampNum(value, fallback, lo, hi) {
  const out = typeof value === "number" ? value : parseFloat(value);
  if (!Number.isFinite(out)) return fallback;
  return Math.max(lo, Math.min(hi, out));
}

function clampBool(value, fallback) {
  return typeof value === "boolean" ? value : fallback;
}

export function readState(node) {
  const raw = node?.properties?.[STATE_PROP];
  const st = { ...DEFAULT_STATE, ...(raw && typeof raw === "object" ? raw : {}) };
  if (!MODES.some((m) => m.id === st.mode)) st.mode = MODE_ALL;
  st.gc = clampBool(st.gc, DEFAULT_STATE.gc);
  st.everyRun = clampBool(st.everyRun, DEFAULT_STATE.everyRun);
  st.useThreshold = clampBool(st.useThreshold, DEFAULT_STATE.useThreshold);
  st.showBar = clampBool(st.showBar, DEFAULT_STATE.showBar);
  st.thresholdGb = clampNum(
    st.thresholdGb, DEFAULT_STATE.thresholdGb, THRESHOLD_MIN_GB, THRESHOLD_MAX_GB,
  );
  return st;
}

export function writeState(node, patch) {
  if (!node) return DEFAULT_STATE;
  const next = { ...readState(node), ...(patch || {}) };
  node.properties = node.properties || {};
  node.properties[STATE_PROP] = next;
  return next;
}

/** Only the keys Python reads (see PROMPT_KEYS). */
export function injectedState(node) {
  const st = readState(node);
  const out = {};
  for (const key of PROMPT_KEYS) out[key] = st[key];
  return out;
}

/**
 * The last run's report, RUNTIME ONLY - deliberately never serialized.
 *
 * It is a measurement that is already stale by the time it is read again, the
 * same call Monitor Pixaroma makes (monitor.md #2). Persisting it would write a
 * new number into node.properties on every run, so an untouched workflow would
 * start flagging itself modified and the undo history would fill with readings.
 * The accepted cost: the readout is blank again after a workflow tab switch.
 */
export function readReport(node) {
  return node?._pixFvReport || null;
}

export function writeReport(node, report) {
  if (node) node._pixFvReport = report || null;
  return report;
}

/** Human bytes, mirroring format_bytes in nodes/_free_vram_helpers.py. */
export function formatBytes(value, places = 1) {
  const num = Number(value);
  if (!Number.isFinite(num)) return "-";
  const sign = num < 0 ? "-" : "";
  const abs = Math.abs(num);
  const GB = 1024 ** 3;
  if (abs >= GB) return `${sign}${(abs / GB).toFixed(places)} GB`;
  if (abs >= 1024 * 1024) return `${sign}${Math.round(abs / (1024 * 1024))} MB`;
  if (abs >= 1024) return `${sign}${Math.round(abs / 1024)} KB`;
  return `${sign}${Math.round(abs)} B`;
}
