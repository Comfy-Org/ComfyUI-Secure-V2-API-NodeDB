// Video Prompt Pixaroma - state.
//
// Vue Compat #9: everything lives on node.properties.videoPromptState and is
// injected into the hidden VideoPromptState input at graphToPrompt time, so the
// node has no visible widgets and no stray input dots beyond the three real
// ones (first_frame, last_frame, clip).
//
// THE KEYS ARE snake_case ON PURPOSE. Python's parse_state reads them directly,
// so there is no camelCase-to-snake mapping layer to get out of step. The pack
// usually uses camelCase here; the uniformity is worth more than the house
// style on a state blob this wide.
//
// THE MODE IS NOT IN HERE. It is derived from which image inputs are connected,
// every time it is needed. A mode that is never stored can never be restored
// wrongly, and the connection handler writes no serialized state - which is
// what keeps this node clear of the configure-replay bug class (Vue Compat
// #17 / #19) that has hit the Switch family twice.

export const CLASS = "PixaromaVideoPrompt";
export const HIDDEN_INPUT = "VideoPromptState";
export const STATE_PROP = "videoPromptState";

export const MODES = ["text_to_video", "first_frame", "first_last"];
export const MODE_LABELS = {
  text_to_video: "Text to video",
  first_frame: "First frame",
  first_last: "First and last frame",
};
export const MODE_HINTS = {
  text_to_video: "no images wired",
  first_frame: "1 image wired",
  first_last: "2 images wired",
};

export const MIN_W = 330;
export const DEFAULT_W = 390;
export const MIN_H = 380;
export const DEFAULT_H = 470;

export const SEED_FIXED = "fixed";
export const SEED_RANDOM = "random";

// The idea box used to be a fixed 52px - about two and a half lines - and it
// was the one thing on the node that could not be made bigger, because the
// prompt box took every pixel the node grew by. Both boxes now share that
// growth, and the grip under the idea box moves the line between them.
// The bounds are on the SHARE, not on pixels: the CSS min-heights are the
// pixel floor, and a share clamp is the only kind that stays right at any
// canvas zoom.
export const IDEA_SHARE_DEFAULT = 0.32;
export const IDEA_SHARE_MIN = 0.12;
export const IDEA_SHARE_MAX = 0.8;

export const DEFAULT_STATE = {
  // --- what Python reads --------------------------------------------------
  idea: "",
  tier_index: 1, // 8 seconds: the surest for a talking idea (6/6 against 5s's 5/6)
  tier_name: "8 seconds",
  seed: 0,
  model: "qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn.safetensors",
  clip_type: "minimax",
  temperature: 0.3,
  max_length: 512,
  top_k: 64,
  top_p: 0.95,
  min_p: 0.05,
  repetition_penalty: 1.05,
  presence_penalty: 0.0,
  thinking: false,
  use_default_template: true,
  release_model: false,
  // Off means the tier's TEXT is not appended, for somebody running their own
  // wording. The tier still sets the DURATION - the seconds come from its
  // name - so frames and seconds keep working either way.
  length_block: true,
  // Multi-token prediction, core Generate Text's `mtp` (ai-prompt.md #34). On =
  // core's default and the generate call exactly as before.
  mtp: true,
  // The frame shape of the video model this feeds. Defaults are MiniMax H3;
  // the settings panel offers Duration Pixaroma's recipe list so the frames
  // output is right for Wan, Hunyuan, LTX or no snapping at all.
  fps: 24,
  step: 17,
  plus: 5,
  min_frames: 5,
  // --- face only, never sent (see PROMPT_KEYS) ----------------------------
  seed_mode: SEED_FIXED,
  speech_hint: true,
  // How the node's spare height is split between the idea box and the prompt
  // box, as the idea's share of the two. A RATIO rather than a pixel height so
  // it survives a node resize, and so the canvas zoom cancels out of the grip
  // drag that edits it. Presentation only - sending it would change the node's
  // cache signature and re-run a 10 GB model for a taller text box.
  idea_share: IDEA_SHARE_DEFAULT,
};

// Exactly the keys Python reads. Anything outside this list is presentation,
// and sending it would change the node's cache signature - so toggling the
// speech hint would silently re-run the model for no reason.
const PROMPT_KEYS = [
  "idea", "tier_index", "tier_name", "seed", "model", "clip_type",
  "temperature", "max_length", "top_k", "top_p", "min_p",
  "repetition_penalty", "presence_penalty", "thinking",
  "use_default_template", "release_model", "length_block",
  "fps", "step", "plus", "min_frames", "mtp",
];

function num(value, fallback, lo, hi) {
  const out = typeof value === "number" ? value : parseFloat(value);
  if (!Number.isFinite(out)) return fallback;
  return Math.max(lo, Math.min(hi, out));
}

export function readState(node) {
  const raw = node?.properties?.[STATE_PROP];
  const st = { ...DEFAULT_STATE, ...(raw && typeof raw === "object" ? raw : {}) };
  st.idea = typeof st.idea === "string" ? st.idea : "";
  st.tier_name = typeof st.tier_name === "string" ? st.tier_name : "";
  st.tier_index = Math.trunc(num(st.tier_index, 1, 0, 999));
  st.seed = Math.trunc(num(st.seed, 0, 0, Number.MAX_SAFE_INTEGER));
  st.seed_mode = st.seed_mode === SEED_RANDOM ? SEED_RANDOM : SEED_FIXED;
  st.model = typeof st.model === "string" && st.model.trim()
    ? st.model : DEFAULT_STATE.model;
  st.clip_type = typeof st.clip_type === "string" && st.clip_type.trim()
    ? st.clip_type : "minimax";
  st.temperature = num(st.temperature, 0.3, 0.01, 2);
  st.max_length = Math.trunc(num(st.max_length, 512, 1, 32768));
  st.top_k = Math.trunc(num(st.top_k, 64, 0, 1000));
  st.top_p = num(st.top_p, 0.95, 0, 1);
  st.min_p = num(st.min_p, 0.05, 0, 1);
  st.repetition_penalty = num(st.repetition_penalty, 1.05, 0, 5);
  st.presence_penalty = num(st.presence_penalty, 0, 0, 5);
  // floor 1, matching Python. A sub-1-fps video is not a thing, and 0.01 would
  // report 5 frames as 500 seconds on the seconds output.
  st.fps = num(st.fps, 24, 1, 1000);
  st.step = Math.trunc(num(st.step, 17, 0, 100000));
  st.plus = Math.trunc(num(st.plus, 5, 0, 100000));
  st.min_frames = Math.trunc(num(st.min_frames, 5, 0, 1000000));
  st.thinking = st.thinking === true;
  st.use_default_template = st.use_default_template !== false;
  st.release_model = st.release_model === true;
  st.length_block = st.length_block !== false;
  st.mtp = st.mtp !== false;
  st.speech_hint = st.speech_hint !== false;
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
// Mode, derived from the wires
// ---------------------------------------------------------------------------
function slotConnected(node, name) {
  const inputs = node?.inputs || [];
  for (const inp of inputs) {
    if (inp && inp.name === name) return inp.link != null;
  }
  return false;
}

/** Mirrors nodes/_video_prompt_helpers.py::mode_for. Both must agree or the face
 *  announces a different formula than the one that runs. */
export function modeOf(node) {
  const first = slotConnected(node, "first_frame");
  const last = slotConnected(node, "last_frame");
  if (first && last) return "first_last";
  if (first || last) return "first_frame";
  return "text_to_video";
}

// ---------------------------------------------------------------------------
// Seed
// ---------------------------------------------------------------------------
export function rollSeed() {
  // Number.MAX_SAFE_INTEGER, not the full 64-bit range: anything above it stops
  // round-tripping through JSON as the same integer, and a seed that changes on
  // the way to Python would break Fixed mode's whole promise.
  return Math.floor(Math.random() * Number.MAX_SAFE_INTEGER);
}

/**
 * The seed this run will actually use.
 *
 * Random rolls a fresh one per run so the state - and therefore the node's
 * cache signature - differs and the model runs again. Fixed reuses the stored
 * number, so an unchanged node is cached and Run is instant. That is the Seed
 * Pixaroma model, and it is why there is no nonce here (issue #11).
 *
 * The rolled number is remembered on a RUNTIME field, never in node.properties,
 * so a run can never mark a clean workflow as modified (Vue Compat #18).
 */
export function seedForRun(node) {
  const st = readState(node);
  if (st.seed_mode !== SEED_RANDOM) return st.seed;
  const rolled = rollSeed();
  node._pixVpLastSeed = rolled;
  return rolled;
}

/** Only the keys Python reads, with the run's seed baked in. */
export function injectedState(node) {
  const st = readState(node);
  const out = {};
  for (const key of PROMPT_KEYS) out[key] = st[key];
  out.seed = seedForRun(node);
  return out;
}

// ---------------------------------------------------------------------------
// The last run's result
// ---------------------------------------------------------------------------
// SERIALIZED on purpose, and a SEPARATE property from videoPromptState.
//
// It lived on `node._pixVpLast` until 2026-08-14, on the reading that Vue
// Compat #18 forbids a run from writing serialized state. Too broad: #18 is
// about the LOAD window - an untouched workflow must not flag ITSELF modified
// merely by being opened - and a run is the user asking for something.
// MEASURED on the AI Prompt sibling: a workflow tab switch DESTROYS and
// rebuilds every node object, so NO `node._xxx` field survives one, and the
// written prompt vanished (reported by the user). Preview Image Pixaroma has
// always persisted its run output this way.
//
// Outside videoPromptState deliberately: PROMPT_KEYS is an allow-list, so this
// could not reach Python either way, but a separate key cannot touch
// injectedState or IS_CHANGED's fingerprint at all - and on this node a
// cosmetic key in the injected state would re-run a 10 GB encoder.
export const LAST_PROP = "videoPromptLast";

/**
 * The last run AS STORED, or null.
 *
 * ⚠️ Deliberately NOT normalised into a fixed shape. The staleness check in
 * renderFace distinguishes an ABSENT `for*` stamp (`last.forX !== undefined`)
 * from one that differs, so filling defaults in would make a result saved
 * before a given stamp existed read as "changed since this ran" forever. Every
 * stamp is written today, so that guard is inert RIGHT NOW - it earns its keep
 * the moment a fifth stamp is added, which is exactly how `forLengthBlock`
 * arrived (video-prompt.md #18). Normalising would quietly disarm it.
 *
 * ⚠️ Returned BY REFERENCE, not cloned - renderFace runs on every keystroke,
 * so a copy per call is not worth it. Do NOT mutate what you get back: route
 * every write through `writeLast`, or you bypass its whole-object replace and
 * a failure starts inheriting a success's stamps.
 */
export function readLast(node) {
  const raw = node?.properties?.[LAST_PROP];
  return raw && typeof raw === "object" ? raw : null;
}

/** Whole-object write, so a failure cannot inherit a stamp from a success. */
export function writeLast(node, next) {
  if (!node) return;
  node.properties = node.properties || {};
  if (!next) { delete node.properties[LAST_PROP]; return; }
  // Drop undefined here, because JSON.stringify drops it on the way into the
  // saved workflow - so the object behaves identically before and after a tab
  // switch rather than only after one.
  const out = {};
  for (const [k, v] of Object.entries(next)) if (v !== undefined) out[k] = v;
  node.properties[LAST_PROP] = out;
}

/**
 * What the face should show as the seed: the last rolled one in Random, the
 * stored one in Fixed.
 *
 * The runtime field dies with the node object on a workflow tab switch, and
 * once the PROMPT started surviving one (LAST_PROP) that left the chip naming a
 * seed which had nothing to do with the text beside it - and a user who copied
 * that number into Fixed to lock the result in would silently get a different
 * generation. So fall back to the seed Python reported for the run, which is
 * already inside the stored result and outlives the node object.
 */
export function displaySeed(node) {
  const st = readState(node);
  if (st.seed_mode === SEED_RANDOM) {
    if (Number.isFinite(node?._pixVpLastSeed)) return node._pixVpLastSeed;
    const ran = Number(readLast(node)?.seed);
    if (Number.isFinite(ran)) return ran;
  }
  return st.seed;
}

// Speech VERBS only. The first version also counted a bare colon, which made
// the 5-second chip turn yellow for "wide shot: a foggy forest", "close-up: her
// hands" and even "a clock reads 5:30" - so the warning looked like it fired at
// random, which is exactly how a hint gets ignored. It also MISSED "she mutters
// under her breath" and "two friends talking at a cafe".
//
// Scored against a fixed case table (6 speaking, 6 not): the colon rule got 6
// of 12 wrong, this gets 0. Keep that table in mind before adding a pattern -
// a false positive costs more than a miss here, because the hint is advisory
// and a user who learns to ignore it gains nothing from it being right later.
const SPEECH_RE = /\b(say|says|said|saying|speak|speaks|speaking|spoke|tell|tells|telling|told|shout|shouts|shouting|whisper|whispers|whispering|mutter|mutters|muttering|ask|asks|asking|reply|replies|replied|answer|answers|call|calls|yell|yells|scream|screams|sing|sings|singing|talk|talks|talking)\b/i;

/** True when the idea looks like it asks for someone to speak. Used ONLY for
 *  the 5-second hint, which marks that tier without ever blocking it. */
export function looksSpoken(idea) {
  if (typeof idea !== "string" || !idea.trim()) return false;
  return SPEECH_RE.test(idea);
}
