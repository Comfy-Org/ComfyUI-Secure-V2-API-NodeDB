// Longest Side Pixaroma - state, and the browser mirror of the maths.
//
// Python (nodes/_longest_side_helpers.py) is the authority: it is what actually
// runs. Everything below exists so the node face can show the size BEFORE a run,
// and a change here needs the same change there. The parity block in
// D:\Claude Tests\_longest_side_test.py locks the two together.
//
// Integer arithmetic only, exactly as Python does it.
//
// Worth being precise about WHY, because the obvious shortcut looks harmless
// from this side: for positive integers `Math.round(a / b)` gives the SAME
// answer as the integer form, since JS rounds .5 up. Swapping it here changes
// nothing, and a parity run stays green - measured.
//
// The danger is on the PYTHON side. Its `round()` is banker's rounding (ties to
// even), so the moment that file uses its own native round the two drift:
// measured at 83 disagreements across 6930 combinations, including 680 vs 688 -
// a whole step - on a 1500x1000 source at 9:16. Both sides therefore use the
// integer form, and neither is allowed to "simplify" to a native round.

export const STATE_PROP = "longestSideState";
export const HIDDEN_INPUT_NAME = "LongestSideState";

export const STEPS = [0, 8, 16, 32, 64];
export const MIN_DIM = 8;
export const MAX_DIM = 16384;

// How many tabs / chips a row may hold. Five, so each one stays comfortably
// wide on a small node.
export const MAX_ROW_ITEMS = 5;

export const DEFAULT_SIZES = [864, 1024, 1216, 1536, 2048];
export const DEFAULT_RATIOS = ["keep", "1:1", "16:9", "9:16", "2:3"];

// `keep` is not a shape, it is "leave the shape alone", and it is the way back
// from any crop. It is therefore always slot 0 and cannot be removed - without
// it a node cropped to 9:16 would have no control that undoes the crop.
export const LOCKED_RATIO = "keep";

export const ANCHORS = [
  "top-left", "top", "top-right",
  "left", "center", "right",
  "bottom-left", "bottom", "bottom-right",
];

export const RESAMPLES = ["auto", "lanczos", "bicubic", "bilinear", "nearest"];

// Shapes offered in the settings picker. Anything the user types is accepted
// too, as long as it parses as w:h.
export const RATIO_CHOICES = [
  "keep", "1:1", "16:9", "9:16", "4:3", "3:4",
  "3:2", "2:3", "5:4", "4:5", "21:9", "9:21", "2:1", "1:2",
];

export const DEFAULT_STATE = {
  size: 1216,
  sizes: [...DEFAULT_SIZES],
  ratio: "keep",
  ratios: [...DEFAULT_RATIOS],
  step: 0,
  anchor: "center",
  allow_upscale: true,
  resample: "auto",
};

// UI-only keys. They must never reach the injected state: editing or reordering
// the list would change the string ComfyUI caches on, re-running the node for a
// change that alters nothing about the output.
const UI_ONLY_KEYS = ["sizes", "ratios"];

const clampInt = (v, lo, hi, fallback) => {
  const n = Math.trunc(Number(v));
  if (!Number.isFinite(n)) return fallback;
  return Math.max(lo, Math.min(n, hi));
};

/** Read + normalize. Writes NOTHING, so it is safe on the load path (Vue Compat #18). */
export function readState(node) {
  const raw = node?.properties?.[STATE_PROP];
  const d = raw && typeof raw === "object" ? raw : {};

  const sizes = Array.isArray(d.sizes) && d.sizes.length
    ? d.sizes.map((v) => clampInt(v, MIN_DIM, MAX_DIM, 1024)).slice(0, MAX_ROW_ITEMS)
    : [...DEFAULT_SIZES];

  // `keep` is forced into slot 0 whatever the stored list says, so it can never
  // be edited away and always sits in the same place.
  const stored = Array.isArray(d.ratios)
    ? d.ratios.filter((r) => typeof r === "string" && r.trim() && r !== LOCKED_RATIO)
    : [...DEFAULT_RATIOS].filter((r) => r !== LOCKED_RATIO);
  const ratios = [LOCKED_RATIO, ...stored].slice(0, MAX_ROW_ITEMS);

  const step = Number(d.step);
  // An active shape that is no longer ON the row would leave every chip looking
  // off while the run still cropped, so it falls back to what is showing.
  let ratio = typeof d.ratio === "string" && d.ratio.trim() ? d.ratio : LOCKED_RATIO;
  if (!ratios.includes(ratio)) ratio = LOCKED_RATIO;

  return {
    size: clampInt(d.size, MIN_DIM, MAX_DIM, DEFAULT_STATE.size),
    sizes,
    ratio,
    ratios,
    step: STEPS.includes(step) ? step : 0,
    anchor: ANCHORS.includes(d.anchor) ? d.anchor : "center",
    allow_upscale: d.allow_upscale === undefined ? true : !!d.allow_upscale,
    resample: RESAMPLES.includes(d.resample) ? d.resample : "auto",
  };
}

export function writeState(node, patch) {
  if (!node) return { ...DEFAULT_STATE };
  const next = { ...readState(node), ...(patch || {}) };
  node.properties = node.properties || {};
  node.properties[STATE_PROP] = next;
  return readState(node);
}

/** What goes in the hidden input: the run keys only. */
export function runState(node) {
  const st = readState(node);
  const out = {};
  for (const k of Object.keys(st)) if (!UI_ONLY_KEYS.includes(k)) out[k] = st[k];
  return out;
}

export function nextStep(current) {
  const i = STEPS.indexOf(Number(current));
  return STEPS[(i < 0 ? 0 : i + 1) % STEPS.length];
}

export function stepLabel(s) {
  return Number(s) > 0 ? `x${s}` : "Off";
}

// ── the maths, mirroring _longest_side_helpers.py ───────────────────────────

/** `a / b` rounded half UP, integers only. Python: (a + b//2) // b */
function roundDiv(a, b) {
  const bi = Math.trunc(b);
  if (!bi) return 0;
  return Math.floor((Math.trunc(a) + Math.floor(bi / 2)) / bi);
}

export function snapToMultiple(value, multiple) {
  const v = Math.trunc(Number(value));
  const m = Math.trunc(Number(multiple));
  if (!Number.isFinite(v) || !Number.isFinite(m) || m <= 1) return v;
  return Math.max(m, Math.floor((v + Math.floor(m / 2)) / m) * m);
}

export function parseRatio(name) {
  if (typeof name !== "string") return null;
  const text = name.trim().toLowerCase();
  if (!text || ["keep", "off", "none", "original"].includes(text)) return null;
  for (const sep of [":", "x", "/"]) {
    const i = text.indexOf(sep);
    if (i < 0) continue;
    const rw = Math.trunc(Number(text.slice(0, i).trim()));
    const rh = Math.trunc(Number(text.slice(i + 1).trim()));
    if (Number.isFinite(rw) && Number.isFinite(rh) && rw > 0 && rh > 0) return [rw, rh];
    return null;
  }
  return null;
}

function anchorOffset(anchor, outerW, innerW, outerH, innerH) {
  const a = (anchor || "center").toLowerCase();
  let x;
  if (a.includes("left")) x = 0;
  else if (a.includes("right")) x = outerW - innerW;
  else x = Math.floor((outerW - innerW) / 2);
  let y;
  if (a.includes("top")) y = 0;
  else if (a.includes("bottom")) y = outerH - innerH;
  else y = Math.floor((outerH - innerH) / 2);
  return [Math.max(0, x), Math.max(0, y)];
}

export function cropRect(w, h, ratio, anchor = "center") {
  w = Math.trunc(w); h = Math.trunc(h);
  if (w <= 0 || h <= 0) return [0, 0, Math.max(0, w), Math.max(0, h)];
  if (!ratio) return [0, 0, w, h];
  const [rw, rh] = ratio;
  let cw, ch;
  if (w * rh > h * rw) { ch = h; cw = roundDiv(h * rw, rh); }
  else { cw = w; ch = roundDiv(w * rh, rw); }
  cw = Math.max(1, Math.min(cw, w));
  ch = Math.max(1, Math.min(ch, h));
  const [x, y] = anchorOffset(anchor, w, cw, h, ch);
  return [x, y, cw, ch];
}

export function targetSize(cw, ch, longest, allowUpscale = true) {
  cw = Math.trunc(cw); ch = Math.trunc(ch);
  if (cw <= 0 || ch <= 0) return [MIN_DIM, MIN_DIM];
  let L = Math.trunc(Number(longest));
  if (!Number.isFinite(L) || L <= 0) L = MIN_DIM;
  const srcLongest = Math.max(cw, ch);
  if (!allowUpscale && L > srcLongest) L = srcLongest;
  let outW, outH;
  if (cw >= ch) { outW = L; outH = roundDiv(L * ch, cw); }
  else { outH = L; outW = roundDiv(L * cw, ch); }
  return [Math.max(1, outW), Math.max(1, outH)];
}

function clampDims(w, h) {
  return [
    Math.max(MIN_DIM, Math.min(Math.trunc(w), MAX_DIM)),
    Math.max(MIN_DIM, Math.min(Math.trunc(h), MAX_DIM)),
  ];
}

/** The whole job, for a known input size. Mirrors compute() in Python. */
export function computeSize(inW, inH, st) {
  inW = Math.trunc(inW || 0); inH = Math.trunc(inH || 0);
  if (inW <= 0 || inH <= 0) return { crop: [0, 0, 0, 0], size: [MIN_DIM, MIN_DIM] };
  const [x, y, cw, ch] = cropRect(inW, inH, parseRatio(st.ratio), st.anchor);
  let [w, h] = targetSize(cw, ch, st.size, st.allow_upscale);
  if (st.step > 0) { w = snapToMultiple(w, st.step); h = snapToMultiple(h, st.step); }
  const [fw, fh] = clampDims(w, h);
  return { crop: [x, y, cw, ch], size: [fw, fh] };
}

/**
 * What the face shows.
 *
 * `dims` is the incoming image's size when it is known, resolved by
 * input_size.mjs (which reads the UPSTREAM node's own preview, so no run is
 * needed) and falling back to what the last run actually received. This module
 * stays free of ComfyUI imports on purpose - that is what lets the parity
 * harness load it with plain node - so the resolving happens outside and the
 * answer is handed in.
 *
 * With no size available we do NOT invent a confident number. With a shape
 * picked we can still say what the shape and size intend, marked as an
 * estimate, because integer rounding of the crop box moves it by a pixel: 9:16
 * at 1216 is 684 from a square source but 685 from a 1920x1080 one. With `keep`
 * even that is unknowable, so we say only the part that is always true.
 */
export function previewText(node, dims, connected = true) {
  const st = readState(node);

  if (dims?.w > 0 && dims?.h > 0) {
    const [w, h] = computeSize(dims.w, dims.h, st).size;
    // Say WHERE the size came from. "upstream" is read live off the node
    // feeding us, so it is current. "run" is what the last execution received:
    // a real measurement, but of the last run, so it can be out of date if
    // something upstream changed since. Both are worth showing as a real
    // number; only the wording differs, and the tooltip must not claim a live
    // source it did not read.
    const fromRun = dims.source === "run";
    return {
      text: `${w}x${h}`,
      dim: false,
      // Do NOT say "the node feeding this one shows no preview": the two
      // Pixaroma loaders take this branch precisely BECAUSE they show a big
      // preview we refuse to measure (it is the file, not what they output).
      // Describing the screen wrongly is worse than saying less.
      title: fromRun
        ? `This node will send ${w} x ${h}. Measured on the last run, from a `
          + `${dims.w} x ${dims.h} picture. The incoming size cannot be read `
          + `live here, so it may be out of date.`
        : `This node will send ${w} x ${h}, from a ${dims.w} x ${dims.h} picture`,
    };
  }

  if (!connected) {
    return { text: `${st.size} long side`, dim: true,
      title: `Wire a picture in and this shows the exact size. The longer side will be ${st.size}.` };
  }

  const ratio = parseRatio(st.ratio);
  if (ratio) {
    // Estimate from the shape itself, as though the source were exactly it.
    let [w, h] = targetSize(ratio[0], ratio[1], st.size, true);
    if (st.step > 0) { w = snapToMultiple(w, st.step); h = snapToMultiple(h, st.step); }
    return { text: `~${w}x${h}`, dim: true,
      title: `About ${w} x ${h}. The exact size needs the incoming picture's size.` };
  }

  return { text: `${st.size} long side`, dim: true,
    title: `The longer side will be ${st.size}. The other side needs the incoming picture's size.` };
}
