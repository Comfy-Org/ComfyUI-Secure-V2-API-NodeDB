// Music Prompt Pixaroma - state.
//
// Vue Compat #9: everything lives on node.properties.musicPromptState and is
// injected into the hidden MusicPromptState input at graphToPrompt time, so the
// node has no visible widgets and no stray input dots beyond the two real ones
// (clip, text).
//
// THE KEYS ARE snake_case ON PURPOSE, matching AI Prompt and Video Prompt:
// Python's parse_state reads them directly, so there is no camelCase mapping
// layer to get out of step.
//
// THERE IS NO FORMULA HERE, and that is the deliberate difference from AI
// Prompt, whose whole design is that the formula lives on the node. Both
// wordings here were measured, and the lyrics one took three rounds; they are
// tuned to a TEMPERATURE as much as to a model, so exposing them as an editable
// box would mostly offer people a way to break something that works. The
// CONTROLS are the dial instead.

export const CLASS = "PixaromaMusicPrompt";
export const HIDDEN_INPUT = "MusicPromptState";
export const STATE_PROP = "musicPromptState";

export const MIN_W = 330;
export const DEFAULT_W = 360;

// ⚠️ MIN_H is DERIVED, and it has to stay that way.
//
// MEASURED (2026-08-19): the face's rows at full squish need 350px of widget
// (+4 slack for font-metric differences between machines), and this node's
// title plus its three output slot rows cost a measured 86px on top - so
// anything under 440 pushes the readout's bottom and the button row below the
// node frame, which is exactly what the user reported ("if i make it smaller
// it doesnt look right"). The old 360 was a guess made before the face had
// settled.
//
// These live HERE, beside MIN_H, rather than in ui.mjs where the widget floor
// is used, because the two numbers are ONE fact and a comment cannot enforce
// an invariant. Split across two files, whoever adds a row to the face later
// bumps the widget floor, gets a correct Nodes 2.0 floor for free (the resize
// floor reads it directly) and a SILENTLY STALE Classic clamp - reproducing
// this very bug in one renderer only, which is the hardest shape to notice.
// ui.mjs imports core.mjs and core.mjs imports nothing, so the constant moves
// DOWN here cycle-free; the reverse would not be.
//
// A node SAVED between 360 and 440 gets grown by the Classic clamp once its
// load gate clears, so an untouched workflow will offer to save itself once.
// Accepted deliberately: the node shipped 2026-08-18 and DEFAULT_H is 470, so
// only a deliberately dragged-down node is affected, and for that node the
// saved size was visibly broken.
export const WIDGET_MIN_H = 354;
export const SLOT_OVERHEAD = 86;
export const MIN_H = WIDGET_MIN_H + SLOT_OVERHEAD;   // 440
export const DEFAULT_H = 470;

export const SEED_FIXED = "fixed";
export const SEED_RANDOM = "random";

// The real ceiling, from comfy/ldm/minimax_music/ar.py:
// MAX_AUDIO_FRAMES 9000 / AUDIO_FRAMES_PER_SECOND 25. It is 360, not the 300
// that gets assumed. The encode node itself defaults to 120, so this matches it.
export const MAX_SECONDS = 360;
export const MIN_SECONDS = 5;
export const DEFAULT_SECONDS = 120;
export const SECONDS_CHIPS = [30, 60, 120, 180];

// 0 = let the length decide, which is the formula's own shape rule and the path
// every reliability measurement was taken on.
export const VERSES_AUTO = 0;
// MEASURED: 1 and 2 come back exactly as asked on both seeds, 3 drifts (asking
// for 3 verses returned 2 on both seeds of the live check), and asking for 6
// returns 5. The chips stop at 3 and the face calls it a request. DO NOT raise
// this without new measurements.
export const MAX_VERSES = 3;

// Which readout the single box is showing. Cosmetic, never sent - see
// PROMPT_KEYS: a cosmetic key in the injected state would make flipping the tab
// re-run a 5 GB model.
export const VIEW_CAPTION = "caption";
export const VIEW_LYRICS = "lyrics";

// The idea box and the readout share the node's height and the grip moves the
// line. A RATIO rather than a pixel height, because every rect measured inside a
// node body is in SCREEN pixels (element px times the canvas zoom), so a stored
// pixel height renders wrong at every zoom but the one it was set at.
export const IDEA_SHARE_DEFAULT = 0.34;
export const IDEA_SHARE_MIN = 0.12;
export const IDEA_SHARE_MAX = 0.8;

export const DEFAULT_STATE = {
  // --- what Python reads --------------------------------------------------
  idea: "",
  // Empty on purpose: the node passes its text through with no model, so there
  // is nothing to guess and nothing to go wrong on somebody else's machine.
  model: "",
  // MUST match AI Prompt, or the shared model cache never hits - see the
  // note on DEFAULT_STATE in nodes/_music_prompt_helpers.py.
  clip_type: "minimax",
  seed: 0,
  seconds: DEFAULT_SECONDS,
  verses: VERSES_AUTO,
  bridge: false,
  instrumental: false,
  // NOT the same as `instrumental`: that adds one instrumental SECTION to a
  // sung song, this means no singing anywhere. Its own key so an old saved
  // workflow simply reads false.
  no_vocals: false,
  release_model: false,
  // Multi-token prediction, core Generate Text's `mtp` (ai-prompt.md #34). On =
  // core's default. Machine-specific, so a formula SET never carries it.
  mtp: true,
  // --- the formula set ----------------------------------------------------
  // EMPTY MEANS THE BUILT-IN. A blank box cannot be mistaken for a formula, and
  // going back to the measured wording is just clearing it - so the node keeps
  // following the built-in if that is ever re-measured. These MUST mirror
  // DEFAULT_STATE in nodes/_music_prompt_helpers.py.
  caption_formula: "",
  lyrics_formula: "",
  caption_temperature: 0.3,
  caption_max_length: 500,
  lyrics_temperature: 0.8,
  lyrics_max_length: 900,
  // --- face only, never sent (see PROMPT_KEYS) ----------------------------
  seed_mode: SEED_FIXED,
  idea_share: IDEA_SHARE_DEFAULT,
  view: VIEW_CAPTION,
};

// Exactly the keys Python reads. Anything outside this list is presentation,
// and sending it would change the node's cache signature - so switching the
// readout tab would re-run the model
// (reference_cosmetic_key_in_injected_state_recaches).
const PROMPT_KEYS = [
  "idea", "model", "clip_type", "seed", "seconds", "verses",
  "bridge", "instrumental", "no_vocals", "release_model", "mtp",
  // The formula set CHANGES THE OUTPUT, so it belongs in the cache signature -
  // editing an instruction must re-run the model by itself, exactly as editing
  // the idea does. That is the same property AI Prompt gets from keeping its
  // formula on the node (ai-prompt.md #1), and it is why neither node needs an
  // IS_CHANGED.
  "caption_formula", "lyrics_formula",
  "caption_temperature", "caption_max_length",
  "lyrics_temperature", "lyrics_max_length",
];

function num(value, fallback, lo, hi) {
  const out = typeof value === "number" ? value : parseFloat(value);
  if (!Number.isFinite(out)) return fallback;
  return Math.max(lo, Math.min(hi, out));
}

function str(value, fallback) {
  return typeof value === "string" ? value : fallback;
}

export function readState(node) {
  const raw = node?.properties?.[STATE_PROP];
  const st = { ...DEFAULT_STATE, ...(raw && typeof raw === "object" ? raw : {}) };
  st.idea = str(st.idea, "");
  st.model = str(st.model, "").trim();
  st.clip_type = str(st.clip_type, "").trim() || "minimax";
  st.seed = Math.trunc(num(st.seed, 0, 0, Number.MAX_SAFE_INTEGER));
  st.seed_mode = st.seed_mode === SEED_RANDOM ? SEED_RANDOM : SEED_FIXED;
  st.seconds = Math.trunc(num(st.seconds, DEFAULT_SECONDS, MIN_SECONDS, MAX_SECONDS));
  st.verses = Math.trunc(num(st.verses, VERSES_AUTO, VERSES_AUTO, MAX_VERSES));
  st.bridge = st.bridge === true;
  st.instrumental = st.instrumental === true;
  st.no_vocals = st.no_vocals === true;
  st.release_model = st.release_model === true;
  st.mtp = st.mtp !== false;
  // The same ranges Python clamps to, so the panel can never show a value the
  // node would silently refuse.
  st.caption_formula = str(st.caption_formula, "");
  st.lyrics_formula = str(st.lyrics_formula, "");
  st.caption_temperature = num(st.caption_temperature, 0.3, 0.01, 2);
  st.lyrics_temperature = num(st.lyrics_temperature, 0.8, 0.01, 2);
  st.caption_max_length = Math.trunc(num(st.caption_max_length, 500, 1, 32768));
  st.lyrics_max_length = Math.trunc(num(st.lyrics_max_length, 900, 1, 32768));
  st.idea_share = num(st.idea_share, IDEA_SHARE_DEFAULT, IDEA_SHARE_MIN, IDEA_SHARE_MAX);
  st.view = st.view === VIEW_LYRICS ? VIEW_LYRICS : VIEW_CAPTION;
  return st;
}

export function writeState(node, patch) {
  if (!node) return { ...DEFAULT_STATE };
  const next = { ...readState(node), ...(patch || {}) };
  node.properties = node.properties || {};
  node.properties[STATE_PROP] = next;
  return next;
}

// ---------------------------------------------------------------------------
// Wires
// ---------------------------------------------------------------------------
export function slotConnected(node, name) {
  const inputs = node?.inputs || [];
  for (const inp of inputs) {
    if (inp && inp.name === name) return inp.link != null;
  }
  return false;
}

/**
 * What the model is being GIVEN, as a short phrase for the banner.
 *
 * It says what WILL happen rather than naming what is absent: AI Prompt shipped
 * a hint that read "Model on wire | nothing wired" beside a node that was about
 * to work perfectly well, and it was reported as a bug (ai-prompt.md #11).
 *
 * `clip` is deliberately not in the list: that is the MODEL, and the label
 * beside this hint already reports it.
 */
export function wiredSummary(node) {
  const bits = [];
  if (readState(node).idea.trim()) bits.push("your idea");
  if (slotConnected(node, "text")) bits.push("text");
  if (!bits.length) return "nothing to sing about yet";
  return bits.join(" + ");
}

/** The one rule: a model (picked or on a wire) AND something to say. */
export function willGenerate(node) {
  const st = readState(node);
  if (!st.model && !slotConnected(node, "clip")) return false;
  if (st.idea.trim()) return true;
  // Nothing typed, but wired text counts. We can only see that a wire exists,
  // not what is on it.
  return slotConnected(node, "text");
}

// ---------------------------------------------------------------------------
// Seed
// ---------------------------------------------------------------------------
export function rollSeed() {
  // Number.MAX_SAFE_INTEGER, not the full 64-bit range: above it a value stops
  // round-tripping through JSON as the same integer, and a seed that changed on
  // the way to Python would break Fixed mode's whole promise.
  return Math.floor(Math.random() * Number.MAX_SAFE_INTEGER);
}

/**
 * The seed this run will use.
 *
 * Random rolls a fresh one per run, so the state - and therefore the node's
 * cache signature - differs and the model runs again. Fixed reuses the stored
 * number, so an unchanged node is cached and Run is instant. That is Seed
 * Pixaroma's model, and it is why there is no nonce here.
 *
 * The rolled number goes on a RUNTIME field, never node.properties, so a run
 * cannot mark a clean workflow as modified on the spot (Vue Compat #18).
 */
export function seedForRun(node) {
  const st = readState(node);
  if (st.seed_mode !== SEED_RANDOM) return st.seed;
  const rolled = rollSeed();
  node._pixMpLastSeed = rolled;
  return rolled;
}

export function injectedState(node) {
  const st = readState(node);
  const out = {};
  for (const key of PROMPT_KEYS) out[key] = st[key];
  out.seed = seedForRun(node);
  return out;
}

// ---------------------------------------------------------------------------
// The last run's answer
// ---------------------------------------------------------------------------
// A SEPARATE property from musicPromptState, and SERIALIZED on purpose.
//
// A workflow tab switch DESTROYS and rebuilds every node object, so no
// `node._xxx` field survives one (Vue Compat #11, measured). AI Prompt kept its
// answer on a runtime field and the user reported the cost: generate, switch
// tab, come back, the text is gone. Vue Compat #18 is about the LOAD window -
// an untouched workflow must not flag ITSELF modified merely by being opened -
// and a run is the user asking for something.
//
// Kept OUT of musicPromptState deliberately: PROMPT_KEYS is an allow-list, so a
// separate key cannot reach the injected state AT ALL. Zero blast radius on the
// run path, where a mistake costs a model reload.
export const LAST_PROP = "musicPromptLast";

/** The last run's answer, or empty fields for a node that has never run. */
export function readLast(node) {
  const raw = node?.properties?.[LAST_PROP];
  const src = raw && typeof raw === "object" ? raw : {};
  return {
    caption: str(src.caption, ""),
    lyrics: str(src.lyrics, ""),
    meta: str(src.meta, ""),
    error: src.error === true,
    muted: src.muted === true,
    seed: Number.isFinite(Number(src.seed)) ? Number(src.seed) : null,
  };
}

/** Whole-object write, so a failure can never inherit a field from a success. */
export function writeLast(node, next) {
  if (!node) return;
  node.properties = node.properties || {};
  node.properties[LAST_PROP] = {
    caption: str(next?.caption, ""),
    lyrics: str(next?.lyrics, ""),
    meta: str(next?.meta, ""),
    error: next?.error === true,
    muted: next?.muted === true,
    // The seed the run REPORTED, so the chip can still name it after a tab
    // switch has taken _pixMpLastSeed with the node object - see displaySeed.
    seed: Number.isFinite(Number(next?.seed)) ? Number(next.seed) : null,
  };
}

/**
 * The runtime seed field dies with the node object on a tab switch, and once the
 * ANSWER survives one that would leave the chip naming a seed with nothing to do
 * with the text beside it - so a user copying that number into Fixed to lock the
 * result in would silently get a different song. Fall back to what the run
 * reported, which is stored with the answer.
 */
export function displaySeed(node) {
  const st = readState(node);
  if (st.seed_mode === SEED_RANDOM) {
    if (Number.isFinite(node?._pixMpLastSeed)) return node._pixMpLastSeed;
    const ran = readLast(node).seed;
    if (Number.isFinite(ran)) return ran;
  }
  return st.seed;
}

/**
 * A model filename tidied for the banner: the folder and the extension go,
 * because every file has one and neither tells the reader anything.
 *
 * It does NOT truncate. A fixed character cut is wrong at every node width but
 * one; the banner label ellipsises in CSS, so widening the node reveals more
 * (ai-prompt.md #11).
 */
export function shortModel(name) {
  const raw = String(name || "").trim();
  if (!raw) return "";
  return raw.split(/[\\/]/).pop().replace(/\.(safetensors|sft|gguf|pt|bin)$/i, "");
}

/**
 * A plain-words description of the song being asked for, for the tip line.
 *
 * It mirrors what `structure_clause` actually sends, so the face cannot promise
 * something different from what Python builds. Verses are described as a request
 * because that is what they are: 1 and 2 come back exactly, 3 drifts.
 */
export function songSummary(node) {
  const st = readState(node);
  const bits = [`${st.seconds}s`];
  // With no singing the verse and section words would describe settings that
  // are not being used, so the line says what it IS doing instead - including
  // the one pass, because "twice as fast" is the reason to pick this mode and
  // the node should say so where the user is looking.
  if (st.no_vocals) {
    bits.push("no singing", "one pass");
    return bits.join(" · ");
  }
  if (st.verses) bits.push(`${st.verses} verse${st.verses === 1 ? "" : "s"} asked for`);
  else bits.push("length decides the shape");
  if (st.bridge) bits.push("bridge");
  if (st.instrumental) bits.push("instrumental");
  return bits.join(" · ");
}
