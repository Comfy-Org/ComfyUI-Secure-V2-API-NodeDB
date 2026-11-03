// Browser mirror of nodes/_dropdown_helpers.py.
//
// THE PARITY RULE: this file and _dropdown_helpers.py must agree on `readable`
// and on every coercion. The panel uses `readable` to mark a row that will not
// read as the chosen type, and the LIVE PREVIEW uses `coerceValue` to show what
// the row will send. If the two drift, the panel confidently tells the user
// something the run then contradicts, which is worse than showing nothing.
//
// The rules are deliberately simple so mirroring stays trivial. Resist any urge
// to be clever here (locale-aware numbers, thousands separators, math
// expressions): every such rule is a second place for the two languages to
// disagree. Number Pixaroma owns math expressions; this node does not.

export const TYPES = ["text", "int", "float", "bool"];

// Shown on the socket and in the type chips. The socket word is short on
// purpose - it sits on the node row next to the dot and must not eat width.
export const TYPE_LABELS = {
  text: "Text",
  int: "Whole number",
  float: "Decimal",
  bool: "On / off",
};
export const SOCKET_LABELS = { text: "text", int: "int", float: "float", bool: "on/off" };

// What LiteGraph should call the output slot, so the canvas refuses a wrong
// drag. Python declares ANY; this is the frontend half of that story.
export const SOCKET_TYPES = { text: "STRING", int: "INT", float: "FLOAT", bool: "BOOLEAN" };

// ⚠ The SAVED type above is not the type the canvas may use for a drag.
// A plain "STRING" output CANNOT be dragged onto a COMBO widget input -
// LiteGraph's isValidConnection("STRING", "COMBO") is false (measured) - and a
// COMBO widget is exactly what a sampler_name / scheduler / ckpt_name is. So
// the node could drive them only if the wire already existed in the file: once
// the user disconnected one, it could never be reconnected by hand. That is the
// main thing this node is for, so the type has to say COMBO as well.
//
// LiteGraph reads a comma-joined type as a LIST of accepted names (the same
// mechanism behind core's multi-type inputs, Vue Compat #22), so this keeps the
// real refusals: "STRING,COMBO" -> COMBO true, -> STRING true, -> IMAGE FALSE.
//
// Only `text` gets it. A ComfyUI combo carries STRINGS, so an int/float/bool
// Dropdown has no business claiming it can feed one.
//
// The suffix is a DRAG-TIME concern only and is stripped again in the
// `serialize` wrap (js/dropdown/index.js), so saved workflows keep the exact
// output type they have always had and no existing file is flagged modified
// just by being opened (Vue Compat #18).
export const WIRE_SUFFIX = ",COMBO";
export const WIRE_TYPES = { ...SOCKET_TYPES, text: SOCKET_TYPES.text + WIRE_SUFFIX };

export const FALLBACKS = { text: "", int: 0, float: 0.0, bool: false };

const TRUE_WORDS = new Set(["true", "yes", "on", "y", "t"]);
const FALSE_WORDS = new Set(["false", "no", "off", "n", "f"]);

// Same clamp as the Python side and as Control Panel's _value_of.
const LIMIT = 1e12;

// THE shared number grammar, character for character the same as _NUMBER_RE in
// _dropdown_helpers.py. Deliberately NOT Number(): a parity run over 228 cases
// caught Number("0x10") returning 16 where Python's float() refuses it, so the
// panel said "sends 16" and the run sent 0. Python likewise accepts "1_0",
// which Number() refuses. Neither native parser is the contract; this is.
//   accepts: 5  5.  .5  5.5  +5  -3  1e3  1E3  -1e3
//   refuses: 0x10  0b1  1_0  1,024  1024px  abc  Infinity  NaN  (and "")
const NUMBER_RE = /^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$/;

// Halves go AWAY from zero. Math.round breaks ties toward +Infinity
// (Math.round(-3.5) === -3) and Python's round() is banker's rounding
// (round(2.5) === 2); they disagree on every exact half. Half-away-from-zero is
// also what someone typing 2.5 into a whole-number list means.
function roundHalfAway(value) {
  return value >= 0 ? Math.floor(value + 0.5) : -Math.floor(-value + 0.5);
}

// A number -> the string Python will emit for it in text mode. Python's str()
// on a whole float keeps a '.0' that JS drops; _number_to_text there matches
// THIS, so both show what the browser shows.
function numberToText(value) {
  return String(value);
}

export function normalizeType(kind) {
  if (typeof kind !== "string") return "text";
  const k = kind.trim().toLowerCase();
  if (TYPES.includes(k)) return k;
  if (k === "string" || k === "str") return "text";
  if (k === "integer" || k === "whole") return "int";
  if (k === "decimal" || k === "number" || k === "double") return "float";
  if (k === "boolean" || k === "toggle" || k === "onoff" || k === "on/off") return "bool";
  return "text";
}

// raw -> finite number, or null. Mirrors _as_number.
function asNumber(raw) {
  if (typeof raw === "boolean") return raw ? 1 : 0;
  if (typeof raw === "number") return Number.isFinite(raw) ? raw : null;
  if (typeof raw === "string") {
    const text = raw.trim();
    // The grammar needs at least one digit, so this covers "" and "   " too.
    if (!NUMBER_RE.test(text)) return null;
    const value = Number(text);
    return Number.isFinite(value) ? value : null;
  }
  return null;
}

export function readable(raw, kind) {
  kind = normalizeType(kind);
  if (kind === "text") return true;
  if (kind === "bool") {
    if (typeof raw === "boolean") return true;
    if (typeof raw === "string") {
      const w = raw.trim().toLowerCase();
      if (TRUE_WORDS.has(w) || FALSE_WORDS.has(w)) return true;
    }
    // The clamp cannot change a zero/non-zero answer, so magnitude is
    // irrelevant for on/off.
    return asNumber(raw) !== null;
  }
  const n = asNumber(raw);
  if (n === null) return false;
  // A value the clamp would MOVE is not readable, even though it parsed. See
  // the matching note in _dropdown_helpers.py: without this a 15-digit seed got
  // no warning mark and the run then sent 1000000000000 instead.
  return n >= -LIMIT && n <= LIMIT;
}

export function coerceValue(raw, kind) {
  kind = normalizeType(kind);

  if (kind === "text") {
    if (raw == null) return "";
    if (typeof raw === "string") return raw;
    // Match Python: emit the spelling a person would type, not the language's.
    if (typeof raw === "boolean") return raw ? "true" : "false";
    if (typeof raw === "number") return numberToText(raw);
    return String(raw);
  }

  if (kind === "bool") {
    if (typeof raw === "boolean") return raw;
    if (typeof raw === "string") {
      const w = raw.trim().toLowerCase();
      if (TRUE_WORDS.has(w)) return true;
      if (FALSE_WORDS.has(w)) return false;
    }
    const n = asNumber(raw);
    if (n === null) return FALLBACKS.bool;
    return n !== 0;
  }

  let n = asNumber(raw);
  if (n === null) return FALLBACKS[kind];
  n = Math.max(-LIMIT, Math.min(LIMIT, n));
  if (kind === "int") return roundHalfAway(n);
  return n;
}

// A short, single-line rendering of a value for the node face and the popup
// hint. A value may be multi-line (a trigger sentence), and a raw multi-line
// string would blow apart a one-line row - so take the first line only.
export function previewText(raw, kind) {
  const v = coerceValue(raw, kind);
  const s = typeof v === "string" ? v : String(v);
  const firstLine = s.split("\n")[0];
  return firstLine.length === s.length ? firstLine : firstLine + "…";
}
