// Load Audio Pixaroma - state.
//
// Vue Compat #9: everything lives on node.properties.loadAudioState and is
// injected into the hidden LoadAudioState input at graphToPrompt time, so the
// node has no visible widgets and no stray input dot beside the real one.

export const CLASS = "PixaromaLoadAudio";
export const HIDDEN_INPUT = "LoadAudioState";
export const STATE_PROP = "loadAudioState";

// Wide enough that a waveform is actually readable - the whole point of the
// node is seeing where the loud parts are, and at 260 you cannot.
export const MIN_W = 300;
export const DEFAULT_W = 380;
export const WAVE_H = 62;

export const DEFAULT_STATE = {
  file: "",
  start: 0,            // seconds into the file
  length: 5,           // fallback length, used only when nothing is wired in
  whenUnwired: "whole", // "whole" | "length"
  whenShort: "silence", // "silence" | "loop"
};

// The keys Python reads. Everything else is presentation, and sending it would
// change the node's cache signature - so a cosmetic change would silently
// re-run the workflow (Duration pattern #7).
const PROMPT_KEYS = ["file", "start", "length", "whenUnwired", "whenShort"];

function clampNum(value, fallback, lo, hi) {
  const out = typeof value === "number" ? value : parseFloat(value);
  if (!Number.isFinite(out)) return fallback;
  return Math.max(lo, Math.min(hi, out));
}

export function readState(node) {
  const raw = node?.properties?.[STATE_PROP];
  const st = { ...DEFAULT_STATE, ...(raw && typeof raw === "object" ? raw : {}) };
  st.file = typeof st.file === "string" ? st.file : "";
  // 24h ceiling: a nonsense start from a corrupted workflow should clamp, not
  // turn into a sample index big enough to hang the trim.
  st.start = clampNum(st.start, 0, 0, 86400);
  st.length = clampNum(st.length, DEFAULT_STATE.length, 0, 86400);
  st.whenUnwired = st.whenUnwired === "length" ? "length" : "whole";
  st.whenShort = st.whenShort === "loop" ? "loop" : "silence";
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

/** 0:42.5 - short enough for a node face, precise enough to trust. */
export function fmtTime(seconds) {
  const s = Math.max(0, Number(seconds) || 0);
  const m = Math.floor(s / 60);
  const rest = s - m * 60;
  return `${m}:${rest < 10 ? "0" : ""}${rest.toFixed(1)}`;
}
