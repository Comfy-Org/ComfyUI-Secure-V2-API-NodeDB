// H3 Timeline Pixaroma - the saved state and the shared constants.
//
// PURE (no imports). The scenes live on node.properties.h3Timeline (an OBJECT)
// and reach Python through the hidden TimelineState input, injected by the
// graphToPrompt hook in index.js. Python re-checks everything
// (nodes/_h3_timeline_helpers.parse_state): the browser is not trusted.
//
// Which scene is selected and the last run's readout are RUNTIME only, so
// clicking a row can never flag a workflow modified.

export const CLASS = "PixaromaH3Timeline";
export const HIDDEN_INPUT = "TimelineState";
export const PROP = "h3Timeline";

// Same rails as nodes/_h3_timeline_helpers.py (MIN / MAX / DEFAULT / MAX_SCENES).
export const SCENE_MIN_S = 4;
export const SCENE_MAX_S = 120;
export const SCENE_DEFAULT_S = 10;
export const SCENE_STEP_S = 0.5;
export const MAX_SCENES = 12;
export const MAX_WORDS = 2000;
export const FPS = 24;
const CHUNK = 17;

export const ROLE_LOOK = "look";
export const ROLE_PERSON = "person";

function num(v, fallback) {
  if (typeof v === "boolean" || v === null || v === undefined || v === "") return fallback;
  const f = Number(v);
  return Number.isFinite(f) ? f : fallback;
}

const unit = (v) => Math.min(1, Math.max(0, num(v, 0.5)));

export function cleanLength(v) {
  return Math.min(SCENE_MAX_S, Math.max(SCENE_MIN_S, num(v, SCENE_DEFAULT_S)));
}

export function newScene(length = SCENE_DEFAULT_S) {
  return { length, words: "", picture: null, role: ROLE_LOOK, x: 0.5, y: 0.5, fit: "cut", cut: false, keep: false };
}

// The longest window in seconds (0 = automatic, 15 s). Shorter windows use less
// memory at big sizes (nodes/_h3_timeline_helpers.window_chunks): the face offers
// these, Python accepts 0 to 15.
export const WINDOWS = [0, 10, 7, 5];
export const cleanWindow = (v) => {
  const f = num(v, 0);
  return f > 0 ? Math.min(15, Math.max(5, f)) : 0;
};

function cleanScene(s) {
  if (!s || typeof s !== "object") return null;
  const pic = typeof s.picture === "string" && s.picture.trim() ? s.picture.trim().slice(0, 512) : null;
  return {
    length: cleanLength(s.length),
    // RAW, as typed: the field must keep a trailing space while you type.
    words: typeof s.words === "string" ? s.words.slice(0, MAX_WORDS) : "",
    picture: pic,
    role: s.role === ROLE_PERSON ? ROLE_PERSON : ROLE_LOOK,
    x: unit(s.x),
    y: unit(s.y),
    fit: s.fit === "fit" ? "fit" : "cut",
    // a clean cut INTO this scene (never on scene 1, Python ignores it there), and Keep = hold this scene as the
    // last Run made it (Python checks the last Run still fits)
    cut: s.cut === true,
    keep: s.keep === true,
  };
}

/** A healed COPY of the saved state. Never writes, so it is safe on the load path. */
export function readState(node) {
  let raw = node?.properties?.[PROP];
  if (typeof raw === "string") {
    try { raw = JSON.parse(raw); } catch { raw = null; }
  }
  if (!raw || typeof raw !== "object") raw = {};
  const scenes = [];
  if (Array.isArray(raw.scenes)) {
    for (const s of raw.scenes.slice(0, MAX_SCENES)) {
      const c = cleanScene(s);
      if (c) scenes.push(c);
    }
  }
  if (!scenes.length) scenes.push(newScene());
  return { scenes, window: cleanWindow(raw.window) };
}

/** The ONLY writer. Call it from user actions, never from a load path. The window
 *  setting is kept as it is unless one is given. */
export function writeState(node, scenes, window) {
  if (!node) return;
  const w = window === undefined ? readState(node).window : cleanWindow(window);
  node.properties = node.properties || {};
  node.properties[PROP] = { v: 1, scenes: scenes.slice(0, MAX_SCENES).map((s) => ({ ...cleanScene(s) })), window: w };
}

/** Exactly what Python receives. */
export function injectedState(node) {
  const st = readState(node);
  return { v: 1, scenes: st.scenes, window: st.window };
}

/** The clip's frame count: the scenes added up, on H3's 17n + 5 grid. MUST match
 *  _h3_timeline_helpers.clip_frames (Python's round() is banker's; the value
 *  being rounded here is never an exact .5 for real lengths, checked in
 *  D:\Claude Tests\_h3_timeline_test.py). */
export function clipFrames(lengths) {
  const total = lengths.reduce((a, v) => a + cleanLength(v), 0) || SCENE_DEFAULT_S;
  return CHUNK * Math.max(6, Math.round((total * FPS - 5) / CHUNK)) + 5;
}

/** "10 s", "7.5 s": seconds for a label. */
export const fmtS = (v) => `${Math.round(v * 10) / 10} s`;

/** Where each scene starts, in seconds (the face's time bar). */
export function sceneStarts(scenes) {
  const out = [];
  let t = 0;
  for (const s of scenes) {
    out.push(t);
    t += s.length;
  }
  return { starts: out, total: t };
}

/** What a scene shows: its own picture, or the look it carries on from the scenes
 *  before it; and whether an added person is in the frame. */
export function sceneLooks(scenes) {
  let look = null;
  const people = new Set();          // the same person added twice joins once (as in Python)
  return scenes.map((s, i) => {
    let entering = false;
    if (s.picture) {
      if (i === 0 || s.role !== ROLE_PERSON) look = s;
      else if (!people.has(s.picture)) { people.add(s.picture); entering = true; }
    }
    return { look, people: people.size, entering, own: !!s.picture };
  });
}
