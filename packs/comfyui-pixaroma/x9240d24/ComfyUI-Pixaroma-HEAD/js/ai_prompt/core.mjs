// AI Prompt Pixaroma - state.
//
// Vue Compat #9: everything lives on node.properties.aiPromptState and is
// injected into the hidden AIPromptState input at graphToPrompt time, so the
// node has no visible widgets and no stray input dots beyond the five real
// ones (clip, image, video, audio, text).
//
// THE KEYS ARE snake_case ON PURPOSE, matching Video Prompt: Python's
// parse_state reads them directly, so there is no camelCase-to-snake mapping
// layer to get out of step.
//
// THE FORMULA IS IN HERE, not in a file. That is the deliberate difference
// from Video Prompt. Three consequences, all wanted:
//   - a duplicate of the node gets its own copy, so a chain can hold three
//     different instructions;
//   - a shared workflow carries its instructions with it;
//   - the formula is part of the node's cache signature, so editing it
//     re-runs by itself. Video Prompt's formulas live on disk and needed an
//     IS_CHANGED fingerprint bolted on afterwards, because editing one
//     changed nothing until something else did (video-prompt.md #8).

export const CLASS = "PixaromaAIPrompt";
export const HIDDEN_INPUT = "AIPromptState";
export const STATE_PROP = "aiPromptState";

export const MIN_W = 320;
export const DEFAULT_W = 400;
export const MIN_H = 300;
export const DEFAULT_H = 430;

export const SEED_FIXED = "fixed";
export const SEED_RANDOM = "random";

export const ORDER_IDEA = "idea";
export const ORDER_WIRED = "wired";

// Mirrors Prompt Pixaroma's SEP_OPTIONS and the Python SEP_MAP, so wiring text
// into either node behaves the same way.
export const SEP_OPTIONS = [
  ["newline", "New line"],
  ["blank", "Blank line"],
  ["space", "Space"],
  ["comma", "Comma"],
  ["period", "Full stop"],
  ["pipe", "Pipe"],
  ["break", "BREAK"],
  ["none", "Nothing"],
];

// Same ratio model as Video Prompt: the idea box and the prompt box share the
// node's height, and the grip between them moves the line. A RATIO rather than
// a pixel height because every rect measured inside a node body is in SCREEN
// pixels (element px times the canvas zoom), so a stored pixel height is wrong
// at every zoom but the one it was set at.
export const IDEA_SHARE_DEFAULT = 0.36;
export const IDEA_SHARE_MIN = 0.12;
export const IDEA_SHARE_MAX = 0.8;

// There is NO expanded-preview state here, and that is deliberate. One was built
// and taken out the same day: the face already carries a banner, two caption rows,
// two text boxes, a grip and a button row, so on a 320x368 node the idea box is
// already under its own 44px minimum. A third box collapsed to an 11px sliver, and
// the only ways out were forcing the node taller than the user had made it or
// letting the buttons spill past the frame. The tag COLOURS in the idea box already
// answer "is this tag real", which is the part that earns its space; what a slot
// rolled shows up in the generated prompt underneath. See ai-prompt.md #21.

export const DEFAULT_STATE = {
  // --- what Python reads --------------------------------------------------
  idea: "",
  formula: "",
  // Empty on purpose. Video Prompt ships a filename and auto-picks a
  // substitute because it cannot work without a vision model; this node CAN
  // work with none - it passes its text through - so there is nothing to
  // guess and nothing to go wrong on somebody else's machine.
  model: "",
  clip_type: "minimax",
  order: ORDER_IDEA,
  sep: "newline",
  seed: 0,
  // Core's Generate Text defaults, exactly, so a workflow moved between the
  // two nodes behaves the same (comfy_extras/nodes_textgen.py).
  temperature: 0.7,
  max_length: 512,
  top_k: 64,
  top_p: 0.95,
  min_p: 0.05,
  repetition_penalty: 1.05,
  presence_penalty: 0.0,
  do_sample: true,
  thinking: false,
  use_default_template: true,
  release_model: false,
  // The formula as the model's SYSTEM message, like core's TextGenerate
  // system_prompt (2026-10-16). Python decides whether the model can take one
  // (nodes/_ai_prompt_helpers.py plan_prompt) and says so when it cannot.
  system_formula: false,
  // Multi-token prediction, core Generate Text's `mtp` (auto / off). On = core's
  // default; off is for a card where MTP drafting crashes (ai-prompt.md #34).
  // Machine-specific, so deliberately NOT in SETTING_KEYS: a preset, a recipe or
  // Reset must never switch it back on.
  mtp: true,
  // NOTE: no "passthrough" flag, deliberately. Passing the text through is what
  // the node does when there is no model or nothing to send, and a switch to
  // turn that off could only mean "error instead", which is strictly worse.
  // --- face only, never sent (see PROMPT_KEYS) ----------------------------
  seed_mode: SEED_FIXED,
  idea_share: IDEA_SHARE_DEFAULT,
};

// Exactly the keys Python reads. Anything outside this list is presentation,
// and sending it would change the node's cache signature - so dragging the
// grip to make the text box taller would re-run a 10 GB model
// (reference_cosmetic_key_in_injected_state_recaches).
const PROMPT_KEYS = [
  "idea", "formula", "model", "clip_type", "order", "sep", "seed",
  "temperature", "max_length", "top_k", "top_p", "min_p",
  "repetition_penalty", "presence_penalty", "do_sample", "thinking",
  "use_default_template", "release_model", "system_formula", "mtp",
];

// Exactly what a PRESET may carry, and it must match SETTING_KEYS in
// nodes/_ai_prompt_presets.py. The idea, the seed, the join order and the
// separator are deliberately absent: those belong to the workflow and the
// wiring, not to the recipe.
export const SETTING_KEYS = [
  "temperature", "max_length", "top_k", "top_p", "min_p",
  "repetition_penalty", "presence_penalty", "do_sample", "thinking",
  "use_default_template", "system_formula",
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
  st.formula = str(st.formula, "");
  st.model = str(st.model, "").trim();
  st.clip_type = str(st.clip_type, "").trim() || "minimax";
  st.order = st.order === ORDER_WIRED ? ORDER_WIRED : ORDER_IDEA;
  st.sep = SEP_OPTIONS.some(([k]) => k === st.sep) ? st.sep : "newline";
  st.seed = Math.trunc(num(st.seed, 0, 0, Number.MAX_SAFE_INTEGER));
  st.seed_mode = st.seed_mode === SEED_RANDOM ? SEED_RANDOM : SEED_FIXED;
  st.temperature = num(st.temperature, 0.7, 0.01, 2);
  st.max_length = Math.trunc(num(st.max_length, 512, 1, 32768));
  st.top_k = Math.trunc(num(st.top_k, 64, 0, 1000));
  st.top_p = num(st.top_p, 0.95, 0, 1);
  st.min_p = num(st.min_p, 0.05, 0, 1);
  st.repetition_penalty = num(st.repetition_penalty, 1.05, 0, 5);
  st.presence_penalty = num(st.presence_penalty, 0, 0, 5);
  st.do_sample = st.do_sample !== false;
  st.thinking = st.thinking === true;
  st.use_default_template = st.use_default_template !== false;
  st.release_model = st.release_model === true;
  st.system_formula = st.system_formula === true;
  st.mtp = st.mtp !== false;
  st.idea_share = num(st.idea_share, IDEA_SHARE_DEFAULT, IDEA_SHARE_MIN, IDEA_SHARE_MAX);
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

// ---------------------------------------------------------------------------
// image_2 ... image_8 (2026-09-29)
// ---------------------------------------------------------------------------
// Extra picture sockets, added one at a time as pictures are wired, because a
// BATCH crops every picture to the first one's size. Python accepts them WITHOUT
// listing them in the schema (nodes/_ai_prompt_helpers.py AIPromptInputs), so a
// node saved before they existed never gains one on load - only a user's own
// wiring adds or removes them (syncImageSlots, called from index.js).
export const MAX_IMAGES = 8;   // `image` + image_2 ... image_8, same cap as Python
const EXTRA_IMAGE = /^image_(\d+)$/;

function extraNumber(inp) {
  const m = EXTRA_IMAGE.exec(inp?.name || "");
  const n = m ? Number(m[1]) : 0;
  return n >= 2 ? n : 0;
}

/** The image_N inputs, in the order they sit on the node. */
export function extraImageInputs(node) {
  return (node?.inputs || []).filter((inp) => extraNumber(inp) > 0);
}

/** How many pictures are wired, `image` included. */
export function connectedImageCount(node) {
  let n = slotConnected(node, "image") ? 1 : 0;
  for (const inp of extraImageInputs(node)) if (inp.link != null) n += 1;
  return n;
}

/**
 * Keep exactly one EMPTY picture socket after the last wired one: `image` wired
 * shows image_2, image_2 wired shows image_3, up to MAX_IMAGES. Only unwired
 * sockets at the END are ever removed, so a wire is never renumbered.
 * Returns how many sockets were added (positive) or removed (negative).
 * Callers must NOT run this during a load or a configure replay.
 */
export function syncImageSlots(node) {
  const inputs = node?.inputs;
  if (!inputs || !inputs.some((inp) => inp?.name === "image")) return 0;
  let last = slotConnected(node, "image") ? 1 : 0;
  let highest = 1;
  for (const inp of extraImageInputs(node)) {
    const n = extraNumber(inp);
    highest = Math.max(highest, n);
    if (inp.link != null) last = Math.max(last, n);
  }
  const want = last ? Math.min(MAX_IMAGES, last + 1) - 1 : 0;   // extra sockets wanted
  let delta = 0;
  while (extraImageInputs(node).length < want && highest < MAX_IMAGES) {
    highest += 1;
    node.addInput(`image_${highest}`, "IMAGE");
    delta += 1;
  }
  while (extraImageInputs(node).length > want) {
    const extras = extraImageInputs(node);
    const tail = extras[extras.length - 1];
    if (!tail || tail.link != null) break;
    node.removeInput(node.inputs.indexOf(tail));
    delta -= 1;
  }
  return delta;
}

/**
 * What the model is being GIVEN, as a short phrase for the banner.
 *
 * It counts the typed idea as well as the wires. It used to list the wires
 * only, so a node with the model on a wire and a full idea typed in read
 * "Model on wire … nothing wired" - a contradiction on one line, and it read
 * as a warning on a node that was about to work perfectly well. The user asked
 * why it said nothing was wired. **A hint beside a working node must say what
 * WILL happen, not name what is absent.**
 *
 * `clip` is deliberately not in the list: that is the MODEL, and the label
 * beside this hint already reports it.
 *
 * It reads the WIRES, which is not the same as what arrived - a muted loader
 * is dropped by graphToPrompt - so the readout below the prompt is still the
 * thing that reports what really ran.
 */
export function wiredSummary(node) {
  const bits = [];
  if (readState(node).idea.trim()) bits.push("your idea");
  const pics = connectedImageCount(node);
  if (pics) bits.push(pics > 1 ? `${pics} images` : "image");
  if (slotConnected(node, "video")) bits.push("video");
  if (slotConnected(node, "audio")) bits.push("audio");
  if (slotConnected(node, "text")) bits.push("text");
  // Nothing but the formula is a real, working state: the model is sent the
  // instruction by itself. Saying so beats reporting an absence.
  if (!bits.length) return "formula only";
  return bits.join(" + ");
}

/** The one rule: a model (picked or on a wire) AND something to send. */
export function willGenerate(node) {
  const st = readState(node);
  if (!st.model && !slotConnected(node, "clip")) return false;
  if (st.formula.trim() || st.idea.trim()) return true;
  // Nothing typed here, but wired text counts as something to send. We cannot
  // see its VALUE from the browser, only that a wire exists.
  return slotConnected(node, "text");
}

// ---------------------------------------------------------------------------
// Seed
// ---------------------------------------------------------------------------
export function rollSeed() {
  // Number.MAX_SAFE_INTEGER, not the full 64-bit range: above it a value stops
  // round-tripping through JSON as the same integer, and a seed that changed
  // on the way to Python would break Fixed mode's whole promise.
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
 * can never mark a clean workflow as modified (Vue Compat #18).
 */
export function seedForRun(node) {
  const st = readState(node);
  if (st.seed_mode !== SEED_RANDOM) return st.seed;
  const rolled = rollSeed();
  node._pixApLastSeed = rolled;
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
// A SEPARATE property from aiPromptState, and SERIALIZED on purpose.
//
// It lived on a runtime `node._pixApOut` field at first, on the reading that
// Vue Compat #18 forbids a run from writing serialized state. That reading was
// too broad, and the user reported the cost: switch workflow tabs, come back,
// and the generated prompt was gone. MEASURED - a tab switch DESTROYS and
// rebuilds every node object (a marker stamped on the node was gone on the way
// back, while node.properties came back intact), so no `node._xxx` field can
// survive one (Vue Compat #11). #18 is about the LOAD window: an untouched
// workflow must not flag ITSELF modified merely by being opened. A run is the
// user asking for something, and the workflow genuinely holds something new
// afterwards - which is exactly why Preview Image Pixaroma already persists
// its own run output this way (`pixaromaFrames`, js/preview/index.js).
//
// Kept OUT of aiPromptState deliberately. PROMPT_KEYS is an allow-list so the
// answer could not reach Python either way, but a separate key cannot touch
// injectedState, the preset SETTING_KEYS, the recipe export or the settings
// panel's "N changed" counter AT ALL - zero blast radius on the run path,
// where a mistake costs a 10 GB model reload.
export const LAST_PROP = "aiPromptLast";

/** The last run's answer, or empty fields for a node that has never run. */
export function readLast(node) {
  const raw = node?.properties?.[LAST_PROP];
  const src = raw && typeof raw === "object" ? raw : {};
  return {
    text: str(src.text, ""),
    meta: str(src.meta, ""),
    error: src.error === true,
    muted: src.muted === true,
    warn: src.warn === true,
    seed: Number.isFinite(Number(src.seed)) ? Number(src.seed) : null,
  };
}

/** Whole-object write, so a failure can never inherit a field from a success. */
export function writeLast(node, next) {
  if (!node) return;
  node.properties = node.properties || {};
  node.properties[LAST_PROP] = {
    text: str(next?.text, ""),
    meta: str(next?.meta, ""),
    error: next?.error === true,
    muted: next?.muted === true,
    // "Send the formula as a system message" was on and could not happen, so
    // the meta line (which says why) is amber. Python's payload `warn`.
    warn: next?.warn === true,
    // The seed the run REPORTED, so the chip can still name it after a tab
    // switch has taken _pixApLastSeed with the node object - see displaySeed.
    seed: Number.isFinite(Number(next?.seed)) ? Number(next.seed) : null,
  };
}

/**
 * The runtime field dies with the node object on a workflow tab switch, and
 * once the ANSWER started surviving one (LAST_PROP) that left the chip naming a
 * seed which had nothing to do with the text beside it - and a user who copied
 * that number into Fixed to lock the result in would silently get a different
 * generation. So fall back to the seed the run reported, which is stored with
 * the answer and outlives the node object.
 */
export function displaySeed(node) {
  const st = readState(node);
  if (st.seed_mode === SEED_RANDOM) {
    if (Number.isFinite(node?._pixApLastSeed)) return node._pixApLastSeed;
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
 * one - it hid the end of the name even on a node made wide enough to show it
 * all. The banner label is `overflow:hidden; text-overflow:ellipsis`, so the
 * name uses whatever room there is and only ellipsises when it genuinely runs
 * out. Widen the node and more of it appears.
 */
export function shortModel(name) {
  const raw = String(name || "").trim();
  if (!raw) return "";
  return raw.split(/[\\/]/).pop().replace(/\.(safetensors|sft|gguf|pt|bin)$/i, "");
}
