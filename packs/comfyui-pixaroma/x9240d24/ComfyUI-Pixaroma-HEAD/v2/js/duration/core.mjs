// Duration Pixaroma - state.
//
// Vue Compat #9: everything lives on node.properties.durationState and is
// injected into the hidden DurationState input at graphToPrompt time, so the
// node has no visible widgets and no stray input dot.

import { DEFAULTS as MATH_DEFAULTS } from "./compute.mjs";

export const CLASS = "PixaromaDuration";
export const HIDDEN_INPUT = "DurationState";
export const STATE_PROP = "durationState";

// Wider than it used to be, and shorter. In Classic the picker row sits IN the
// output-slot band, so it has to share that line with the right-aligned "frames"
// / "seconds" labels - at 260 the fourth chip wrapped onto its own line and
// stretched full width. A control node is better wide and flat than narrow and
// tall, and this buys back more height than it costs width.
export const MIN_W = 280;
export const DEFAULT_W = 330;
export const ROW_H = 26;
export const READOUT_H = 18;
export const BODY_PAD = 6;

// How you pick the number. The face follows this, which is the whole reason
// there is one Duration node instead of a chips one and a slider one.
export const PICK_CHIPS = "chips";
export const PICK_SLIDER = "slider";
export const PICK_NUMBER = "number";

export const DEFAULT_STATE = {
  // --- what Python computes with (these, and ONLY these, reach the prompt) ---
  seconds: 5,
  fps: 24,
  step: 17,
  plus: 5,
  minFrames: 5,
  mode: "recipe",          // "recipe" | "custom"
  formula: "",
  // --- how the face behaves (never sent; see injectedState) -----------------
  pick: PICK_CHIPS,
  values: [3, 5, 10, 15],  // chips mode
  min: 1,                  // slider mode
  max: 10,
  stepSec: 0.5,
  recipeName: "MiniMax H3",
};

// The keys Python reads. Anything else is presentation, and sending it would
// change the node's cache signature - so renaming a recipe or editing the chip
// list you are not using would silently re-run the whole workflow.
const PROMPT_KEYS = ["seconds", "fps", "step", "plus", "minFrames", "mode", "formula"];

function clampNum(value, fallback, lo, hi) {
  const out = typeof value === "number" ? value : parseFloat(value);
  if (!Number.isFinite(out)) return fallback;
  return Math.max(lo, Math.min(hi, out));
}

export function readState(node) {
  const raw = node?.properties?.[STATE_PROP];
  const st = { ...DEFAULT_STATE, ...(raw && typeof raw === "object" ? raw : {}) };
  st.seconds = clampNum(st.seconds, DEFAULT_STATE.seconds, -100000, 100000);
  st.fps = clampNum(st.fps, DEFAULT_STATE.fps, 0, 1000);
  st.step = Math.trunc(clampNum(st.step, DEFAULT_STATE.step, 0, 100000));
  st.plus = Math.trunc(clampNum(st.plus, DEFAULT_STATE.plus, 0, 100000));
  st.minFrames = Math.trunc(clampNum(st.minFrames, DEFAULT_STATE.minFrames, 0, 1000000));
  st.min = clampNum(st.min, DEFAULT_STATE.min, 0, 100000);
  st.max = clampNum(st.max, DEFAULT_STATE.max, 0, 100000);
  if (st.max < st.min) st.max = st.min;
  st.stepSec = clampNum(st.stepSec, DEFAULT_STATE.stepSec, 0.01, 100000);
  if (!Array.isArray(st.values)) st.values = [...DEFAULT_STATE.values];
  // A chip list is a set of numbers, sorted, deduped, and capped - it is drawn
  // as one row of buttons, so an accidental 500-entry paste must not make the
  // node unusable.
  st.values = [...new Set(st.values
    .map((v) => clampNum(v, NaN, 0, 100000))
    .filter((v) => Number.isFinite(v)))].sort((a, b) => a - b).slice(0, 12);
  if (!st.values.length) st.values = [...DEFAULT_STATE.values];
  if (![PICK_CHIPS, PICK_SLIDER, PICK_NUMBER].includes(st.pick)) st.pick = PICK_CHIPS;
  st.mode = String(st.mode || "recipe").toLowerCase() === "custom" ? "custom" : "recipe";
  st.formula = typeof st.formula === "string" ? st.formula : "";
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

/** In chips mode, snap a value to the nearest allowed chip. */
export function nearestValue(values, seconds) {
  if (!values.length) return seconds;
  let best = values[0];
  for (const v of values) {
    if (Math.abs(v - seconds) < Math.abs(best - seconds)) best = v;
  }
  return best;
}

/** The seconds actually selectable right now, given the pick mode. */
export function clampToPick(st, seconds) {
  if (st.pick === PICK_CHIPS) return nearestValue(st.values, seconds);
  const lo = Math.min(st.min, st.max);
  const hi = Math.max(st.min, st.max);
  let v = Math.max(lo, Math.min(hi, seconds));
  if (st.pick === PICK_SLIDER && st.stepSec > 0) {
    // Snap to the slider's grid, measured FROM the minimum so a range like
    // 1..10 step 0.5 gives 1, 1.5, 2 ... rather than 0.5-offset values.
    v = lo + Math.round((v - lo) / st.stepSec) * st.stepSec;
    v = Math.max(lo, Math.min(hi, v));
  }
  // Kill float dust from the multiply (1.2000000000000002).
  return Math.round(v * 1e6) / 1e6;
}

export { MATH_DEFAULTS };
