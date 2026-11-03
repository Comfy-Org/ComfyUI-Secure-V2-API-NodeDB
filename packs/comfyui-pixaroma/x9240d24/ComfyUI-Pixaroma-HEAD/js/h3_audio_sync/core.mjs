// H3 Audio Sync Pixaroma - state.
//
// This node has no per-node choices worth storing on the node itself: "how long
// before you warn me" and "what to do if the track runs out" are preferences,
// not things two copies of the node on one canvas would sensibly disagree
// about. So they live as settings rows on the shared panel (the gear), and this
// module turns them into the blob Python reads.
//
// The ids are deliberately UNREGISTERED. A registered setting always reads back
// its defaultValue, so getSettingValue cannot tell "never touched" from
// "deliberately chosen" - which is why every read here goes through
// nodeSetting(id, fallback) with its own default (node-settings-accent.md).

import { nodeSetting } from "../shared/node_settings.mjs";

export const CLASS = "PixaromaH3AudioSync";
export const HIDDEN_INPUT = "H3SyncState";

export const SET_LIMIT = "Pixaroma.H3AudioSync.LongestClip";
export const SET_OVER = "Pixaroma.H3AudioSync.WhenLonger";
export const SET_SHORT = "Pixaroma.H3AudioSync.WhenShort";

export const LIMIT_OPTIONS = ["10 seconds", "15 seconds", "20 seconds", "No limit"];
export const LIMIT_DEFAULT = "15 seconds";
export const OVER_OPTIONS = ["Just warn me", "Stop the run"];
export const OVER_DEFAULT = "Just warn me";
export const SHORT_OPTIONS = ["Silence", "Loop"];
export const SHORT_DEFAULT = "Silence";

export const MIN_W = 260;
export const DEFAULT_W = 300;

/** "15 seconds" -> 15, "No limit" -> 0 (which switches the guard off). */
function limitSeconds(label) {
  const n = parseFloat(String(label || ""));
  return Number.isFinite(n) ? n : 0;
}

/** Exactly the three keys Python reads, and nothing cosmetic. */
export function injectedState() {
  return {
    limit: limitSeconds(nodeSetting(SET_LIMIT, LIMIT_DEFAULT)),
    overMode: nodeSetting(SET_OVER, OVER_DEFAULT) === "Stop the run" ? "stop" : "warn",
    whenShort: nodeSetting(SET_SHORT, SHORT_DEFAULT) === "Loop" ? "loop" : "silence",
  };
}
