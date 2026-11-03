// The browser mirror of nodes/_duration_helpers.py.
//
// It exists so the node face can show the frame count the instant you click a
// chip, with no server round trip. Python remains the authority - it is what
// actually runs - so any change here MUST be made there too and re-checked with
// the parity harness (D:\Claude Tests\_duration_parity.mjs), the same rule the
// text renderer and the FX engine live under.
//
// THE trap this mirror exists to get wrong: JavaScript's % keeps the sign of the
// left operand, so (-3 % 17) is -3 here and 14 in Python. Every modulo below
// goes through mod() for that reason.

export const MAX_FPS = 1000;
export const MAX_STEP = 100000;
export const MAX_FRAMES = 1000000;
export const MAX_SECONDS = 100000;

export const DEFAULTS = {
  seconds: 5, fps: 24, step: 17, plus: 5, minFrames: 5, mode: "recipe", formula: "",
};

/** Python's %, not JavaScript's: always non-negative for a positive modulus. */
function mod(value, n) {
  return ((value % n) + n) % n;
}

/** One field -> a finite number inside [lo, hi], or the fallback. */
export function num(value, fallback, lo, hi) {
  const out = typeof value === "number" ? value : parseFloat(value);
  if (!Number.isFinite(out)) return fallback;
  return Math.max(lo, Math.min(hi, out));
}

/**
 * Python's round() is banker's rounding (round-half-to-EVEN): round(0.5) is 0
 * and round(2.5) is 2, where JS Math.round gives 1 and 3. A duration landing
 * exactly on .5 of a frame is rare but completely reachable (12.5 fps, or
 * 2.5 s at 25 fps), and a one-frame disagreement between the face and the run
 * is precisely the kind of bug nobody thinks to look for.
 */
export function pyRound(value) {
  const floor = Math.floor(value);
  const diff = value - floor;
  if (diff > 0.5) return floor + 1;
  if (diff < 0.5) return floor;
  return floor % 2 === 0 ? floor : floor + 1;
}

/** Round UP to the next value of the form step*n + plus. step <= 1 = no snap. */
export function snapFrames(raw, step, plus) {
  step = Math.trunc(step);
  plus = Math.trunc(plus);
  raw = Math.trunc(raw);
  if (step <= 1) return raw;
  const remainder = mod(raw - plus, step);
  return remainder ? raw + (step - remainder) : raw;
}

/** The recipe path: seconds -> a frame count the model will accept. */
export function framesFromSeconds(seconds, fps, step, plus, minFrames) {
  seconds = num(seconds, DEFAULTS.seconds, -MAX_SECONDS, MAX_SECONDS);
  fps = num(fps, DEFAULTS.fps, 0, MAX_FPS);
  step = Math.trunc(num(step, DEFAULTS.step, 0, MAX_STEP));
  plus = Math.trunc(num(plus, DEFAULTS.plus, 0, MAX_STEP));
  minFrames = Math.trunc(num(minFrames, DEFAULTS.minFrames, 0, MAX_FRAMES));

  let raw = pyRound(seconds * fps);
  if (raw < minFrames) raw = minFrames;
  raw = snapFrames(raw, step, plus);
  return Math.max(0, Math.min(MAX_FRAMES, raw));
}

/**
 * state -> { frames, actual, custom }.
 *
 * A CUSTOM formula is deliberately NOT evaluated here. Re-implementing
 * simpleeval in the browser would be a second expression language that agrees
 * with the real one only until someone uses a function we got slightly wrong -
 * and a wrong number shown confidently is worse than no number. `custom: true`
 * tells the caller to ask the server (js/duration/api.mjs) instead, and the
 * frames returned are the recipe fallback Python would also use if the formula
 * turned out to be broken.
 */
export function computeLocal(state) {
  const st = { ...DEFAULTS, ...(state || {}) };
  const seconds = num(st.seconds, DEFAULTS.seconds, -MAX_SECONDS, MAX_SECONDS);
  const fps = num(st.fps, DEFAULTS.fps, 0, MAX_FPS);
  const frames = framesFromSeconds(seconds, fps, st.step, st.plus, st.minFrames);
  return {
    frames,
    actual: fps > 0 ? frames / fps : 0,
    custom: String(st.mode || "recipe").toLowerCase() === "custom"
      && String(st.formula || "").trim() !== "",
  };
}

/** frames + fps -> the true length, so callers never divide by zero by hand. */
export function actualSeconds(frames, fps) {
  const f = num(fps, DEFAULTS.fps, 0, MAX_FPS);
  return f > 0 ? frames / f : 0;
}
