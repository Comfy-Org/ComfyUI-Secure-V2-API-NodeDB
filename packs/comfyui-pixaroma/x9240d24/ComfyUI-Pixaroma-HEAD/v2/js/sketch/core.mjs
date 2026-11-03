// Sketch Pixaroma - the saved state, the shared constants, and the BROWSER
// MIRROR of the prompt.
//
// nodes/_sketch_helpers.py is the source of truth. What is mirrored here and
// must never drift from it: COLORS, WIDTHS, the geometry constants, oneLine()
// and buildPrompt() including the left/right wording for repeated marks.
// Pinned by D:\Claude Tests\_sketch_parity.mjs (both languages, one table).
//
// The marks live on node.properties.sketchState (an OBJECT, never a JSON
// string) and reach Python through the hidden SketchState input, injected by
// the graphToPrompt hook in index.js. Only what changes the OUTPUT is injected:
// the tool, colour and line width you have picked are runtime-only, so picking
// a tool can never flag a workflow modified or re-run the graph.

export const CLASS = "PixaromaSketch";
export const HIDDEN_INPUT = "SketchState";
export const PROP = "sketchState";
export const SETTING_AUTO = "Pixaroma.Sketch.AutoColor";

// name -> RGB. The NAME is what the prompt says. MUST match the Python.
export const COLORS = {
  red: [255, 43, 43],
  blue: [43, 123, 255],
  green: [22, 195, 90],
  purple: [160, 70, 255],
  yellow: [255, 210, 26],
  white: [255, 255, 255],
  black: [17, 17, 17],
};
export const SWATCHES = ["red", "blue", "green", "purple", "yellow", "white", "black"];
// "Each new mark takes the next colour" walks this, so a prompt can say "the
// red box" and "the blue circle" without the two ever being confused.
export const AUTO_ORDER = ["red", "blue", "green", "purple"];
export const WIDTHS = { S: 0.006, M: 0.010, L: 0.016, XL: 0.030 };
export const WIDTH_KEYS = ["S", "M", "L", "XL"];
export const TYPES = ["box", "ellipse", "pen", "arrow", "text"];

export const MAX_MARKS = 64;
export const MAX_POINTS = 4000;
export const MAX_TEXT = 60;
export const MAX_NOTE = 400;
export const MIN_LINE_PX = 2;
export const TEXT_SCALE = 5.2;
export const TEXT_BASELINE = 0.35;
export const HEAD_SCALE = 4.2;
export const HEAD_HALF = 0.45;
export const HEAD_MIN = 6;
export const REMOVE_LINE = "Remove all the colored marks and keep everything else the same.";

export const rgbOf = (name) => {
  const c = COLORS[name] || COLORS.red;
  return `rgb(${c[0]},${c[1]},${c[2]})`;
};

// ── reading ────────────────────────────────────────────────────────────────
function num(v) {
  if (typeof v === "boolean" || v === null || v === "") return null;
  const f = Number(v);
  return Number.isFinite(f) ? f : null;
}

/** Collapse whitespace runs to one space, cap by CODE POINT - the Python
 *  _one_line exactly (JS \s is the same 25-character set as its _JS_WS). */
export function oneLine(s, cap) {
  if (typeof s !== "string") return "";
  const joined = s.split(/\s+/).filter(Boolean).join(" ");
  const cps = Array.from(joined);
  return cps.length > cap ? cps.slice(0, cap).join("") : joined;
}

function cleanMark(m) {
  if (!m || typeof m !== "object" || !TYPES.includes(m.type) || !Array.isArray(m.pts)) return null;
  let pts = [];
  for (const p of m.pts.slice(0, MAX_POINTS)) {
    if (!Array.isArray(p) || p.length < 2) continue;
    const x = num(p[0]);
    const y = num(p[1]);
    if (x == null || y == null) continue;
    pts.push([Math.min(1, Math.max(0, x)), Math.min(1, Math.max(0, y))]);
  }
  if (pts.length < (m.type === "text" ? 1 : 2)) return null;
  if (m.type === "box" || m.type === "ellipse" || m.type === "arrow") pts = pts.slice(0, 2);
  else if (m.type === "text") pts = pts.slice(0, 1);
  const out = {
    type: m.type,
    color: COLORS[m.color] ? m.color : "red",
    w: WIDTHS[m.w] ? m.w : "M",
    pts,
    // RAW, as typed: the note box must keep a trailing space while you type.
    // It is normalised only where it leaves for the prompt (injectedState).
    note: typeof m.note === "string" ? m.note.slice(0, MAX_NOTE * 2) : "",
  };
  if (m.type === "text") {
    const t = oneLine(m.text, MAX_TEXT);
    if (!t) return null;
    out.text = t;
  }
  if (m.type === "pen") out.closed = m.closed === true;
  return out;
}

/** A healed COPY of the saved state. Never writes, so it is safe on the load path. */
export function readState(node) {
  let raw = node?.properties?.[PROP];
  if (typeof raw === "string") {
    try { raw = JSON.parse(raw); } catch { raw = null; }
  }
  if (!raw || typeof raw !== "object") raw = {};
  const marks = [];
  if (Array.isArray(raw.marks)) {
    for (const m of raw.marks.slice(0, MAX_MARKS)) {
      const c = cleanMark(m);
      if (c) marks.push(c);
    }
  }
  const aspect = num(raw.picAspect);
  return { marks, removeMarks: raw.removeMarks !== false, picAspect: aspect && aspect > 0 ? aspect : null };
}

/** The ONLY writer. Call it from user actions, never from a load path. */
export function writeState(node, patch) {
  if (!node) return;
  const cur = readState(node);
  const next = { ...cur, ...patch };
  node.properties = node.properties || {};
  node.properties[PROP] = {
    v: 1,
    marks: next.marks,
    removeMarks: next.removeMarks !== false,
    ...(next.picAspect ? { picAspect: next.picAspect } : {}),
  };
}

const r4 = (v) => Math.round(v * 10000) / 10000;

/** Exactly what Python receives. Coordinates rounded so the prompt is small
 *  and stable; notes normalised here and nowhere else. */
export function injectedState(node) {
  const st = readState(node);
  return {
    v: 1,
    removeMarks: st.removeMarks,
    marks: st.marks.map((m) => {
      const o = { type: m.type, color: m.color, w: m.w, pts: m.pts.map(([x, y]) => [r4(x), r4(y)]), note: oneLine(m.note, MAX_NOTE) };
      if (m.type === "text") o.text = m.text;
      if (m.type === "pen") o.closed = !!m.closed;
      return o;
    }),
  };
}

// ── the prompt (MIRROR of _sketch_helpers.build_prompt) ────────────────────
const ORDINALS = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth"];

function ordinal(n) {
  if (n >= 1 && n <= ORDINALS.length) return ORDINALS[n - 1];
  const m100 = n % 100;
  const suffix = (m100 >= 10 && m100 <= 20) ? "th" : ({ 1: "st", 2: "nd", 3: "rd" }[n % 10] || "th");
  return `${n}${suffix}`;
}

function phraseKey(m) {
  if (m.type === "text") return JSON.stringify(["text", m.color, m.text]);
  if (m.type === "pen") return JSON.stringify(["pen", m.color, !!m.closed]);
  return JSON.stringify([m.type, m.color]);
}

function center(m) {
  if (m.type === "arrow") return m.pts[1];
  const xs = m.pts.map((p) => p[0]);
  const ys = m.pts.map((p) => p[1]);
  return [(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2];
}

function positions(marks) {
  const groups = new Map();
  marks.forEach((m, i) => {
    const k = phraseKey(m);
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k).push(i);
  });
  const pos = marks.map(() => ["", ""]);
  for (const idx of groups.values()) {
    if (idx.length < 2) continue;
    const cs = idx.map((i) => center(marks[i]));
    const xs = cs.map((c) => c[0]);
    const ys = cs.map((c) => c[1]);
    const horizontal = (Math.max(...xs) - Math.min(...xs)) >= (Math.max(...ys) - Math.min(...ys));
    const a = horizontal ? 0 : 1;
    const order = idx.map((_, k) => k).sort((p, q) =>
      (cs[p][a] - cs[q][a]) || (cs[p][1 - a] - cs[q][1 - a]) || (idx[p] - idx[q]));
    const n = idx.length;
    let words = null;
    if (n === 2) words = horizontal ? ["left", "right"] : ["top", "bottom"];
    else if (n === 3) words = horizontal ? ["left", "middle", "right"] : ["top", "middle", "bottom"];
    order.forEach((k, rank) => {
      pos[idx[k]] = words
        ? [words[rank] + " ", ""]
        : [ordinal(rank + 1) + " ", horizontal ? " from the left" : " from the top"];
    });
  }
  return pos;
}

function where(m, [before, after]) {
  const c = m.color;
  switch (m.type) {
    case "box": return `Inside the ${before}${c} box${after}`;
    case "ellipse": return `Inside the ${before}${c} circle${after}`;
    case "pen": return m.closed ? `Inside the ${before}${c} outline${after}` : `The ${before}${c} sketch${after}`;
    case "arrow": return `Where the ${before}${c} arrow${after} points`;
    default: return `Where the ${before}${c} text${after} says "${m.text}"`;
  }
}

/** Takes INJECTED marks (injectedState(node).marks), so the preview is built
 *  from the very numbers and text Python will see. */
export function buildPrompt(marks, removeMarks = true) {
  const pos = positions(marks);
  const lines = [];
  marks.forEach((m, i) => {
    const note = (m.note || "").trim();
    if (!note) return;
    const end = /[.!?]$/.test(note) ? "" : ".";
    lines.push(`${where(m, pos[i])}: ${note}${end}`);
  });
  if (lines.length && removeMarks) lines.push(REMOVE_LINE);
  return lines.join(" ");
}

/** What a mark is called in the list beside the picture. */
export function markName(m) {
  if (m.type === "pen") return `${m.color} ${m.closed ? "outline" : "sketch"}`;
  const noun = { box: "box", ellipse: "circle", arrow: "arrow", text: "text" }[m.type] || m.type;
  return `${m.color} ${noun}`;
}

/** The colour the NEXT mark gets when auto-colour is on: the one after the
 *  last mark's, so reopening a workflow carries on where it left off. */
export function nextAutoColor(marks) {
  const last = marks.length ? marks[marks.length - 1].color : null;
  const i = AUTO_ORDER.indexOf(last);
  return i < 0 ? (last ? AUTO_ORDER[0] : "red") : AUTO_ORDER[(i + 1) % AUTO_ORDER.length];
}
