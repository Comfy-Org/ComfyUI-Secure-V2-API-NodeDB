// Portrait Landscape Pixaroma - state.
//
// node.properties.portraitLandscapeState used to be the bare string "portrait"
// or "landscape". It is an object now, { orient, multiple }, so the size step
// can live per node. readState MIGRATES the old form on read and writeState
// only ever writes the new one, so a workflow saved before the step existed
// opens with its orientation intact and the step Off.
//
// The migration is READ-ONLY on the load path: nothing here writes to
// node.properties unless the user changes something, or an untouched workflow
// would open flagged "modified" (Vue Compat #18).

export const STATE_PROP = "portraitLandscapeState";
export const HIDDEN_INPUT_NAME = "PortraitLandscapeState";

/** What the face cycles through and the panel offers. 0 is Off. */
export const MULTIPLES = [0, 8, 16, 32, 64];

export const DEFAULT_STATE = { orient: "portrait", multiple: 0 };

export function readState(node) {
  const raw = node?.properties?.[STATE_PROP];
  if (raw === "portrait" || raw === "landscape") {
    return { orient: raw, multiple: 0 };            // legacy, pre-multiple
  }
  if (raw && typeof raw === "object") {
    const orient = raw.orient === "landscape" ? "landscape" : "portrait";
    const m = Number(raw.multiple);
    return { orient, multiple: MULTIPLES.includes(m) ? m : 0 };
  }
  return { ...DEFAULT_STATE };
}

export function writeState(node, patch) {
  if (!node) return { ...DEFAULT_STATE };
  const next = { ...readState(node), ...(patch || {}) };
  if (!MULTIPLES.includes(Number(next.multiple))) next.multiple = 0;
  next.multiple = Number(next.multiple);
  if (next.orient !== "landscape") next.orient = "portrait";
  node.properties = node.properties || {};
  node.properties[STATE_PROP] = next;
  return next;
}

/** The next step in the Off -> 8 -> 16 -> 32 -> 64 -> Off cycle. */
export function nextMultiple(current) {
  const i = MULTIPLES.indexOf(Number(current));
  return MULTIPLES[(i < 0 ? 0 : i + 1) % MULTIPLES.length];
}

/** The label the little button on the node shows. */
export function multipleLabel(m) {
  return Number(m) > 0 ? `x${m}` : "Off";
}

/**
 * The browser mirror of snap_to_multiple in nodes/node_portrait_landscape.py.
 * Python is the authority - it is what actually runs - so a change here needs
 * the same change there, checked by _portrait_landscape_test.py's parity block.
 *
 * Integer arithmetic, matching Python exactly: `(v + m//2) // m * m`. Doing it
 * as `Math.round(v / m) * m` would bring float representation into a
 * whole-pixel decision AND round halves the other way from Python on some
 * values, so the face would promise a size the run did not produce.
 */
export function snapToMultiple(value, multiple) {
  const v = Math.trunc(Number(value));
  const m = Math.trunc(Number(multiple));
  if (!Number.isFinite(v) || !Number.isFinite(m) || m <= 1) return v;
  const snapped = Math.floor((v + Math.floor(m / 2)) / m) * m;
  return Math.max(m, snapped);
}

/**
 * What the node will actually send, for the little preview on the face.
 * Returns { text, wired }. `wired` means a size is coming down a wire, so the
 * browser cannot know it - we say so rather than show a number that is wrong.
 */
export function previewSize(node) {
  const wired = (name) => {
    const inp = (node?.inputs || []).find((i) => (i.widget?.name || i.name) === name);
    return !!inp && inp.link != null;
  };
  if (wired("width") || wired("height")) return { text: "from input", wired: true };

  const val = (name) => Number(node?.widgets?.find((w) => w.name === name)?.value);
  const w = val("width");
  const h = val("height");
  if (!Number.isFinite(w) || !Number.isFinite(h)) return { text: "", wired: false };

  const st = readState(node);
  const sw = snapToMultiple(w, st.multiple);
  const sh = snapToMultiple(h, st.multiple);
  const lo = Math.min(sw, sh);
  const hi = Math.max(sw, sh);
  const [outW, outH] = st.orient === "landscape" ? [hi, lo] : [lo, hi];
  return { text: `${outW}x${outH}`, wired: false };
}
