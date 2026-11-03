// Duration Pixaroma - asking the server what a CUSTOM formula produces.
//
// The recipe maths is mirrored in the browser (compute.mjs) because it is six
// lines of integer arithmetic that can be parity-tested. A formula is not: it
// would mean shipping a second expression evaluator that agrees with Python's
// simpleeval until the day it does not, and the node would then show one number
// and generate another. So the ONE evaluator is Python's, and the face asks it.
//
// Only the custom path goes over the wire, so an ordinary recipe node never
// makes a request at all.

import { pixApiUrl } from "../shared/api_url.mjs";

const CACHE = new Map();        // key -> {ok, frames, actual}
const INFLIGHT = new Map();     // key -> Promise
const MAX_CACHE = 200;

function keyOf(st) {
  return JSON.stringify([st.formula, st.seconds, st.fps, st.step, st.plus, st.minFrames]);
}

/**
 * -> {ok, frames, actual}. `ok:false` means the formula did not evaluate, and
 * `frames` is then the recipe fallback Python would use, so the face can say
 * what will really happen rather than just "error".
 *
 * Never rejects: a preview that throws would leave the readout stuck on
 * "working it out...".
 */
export async function previewCustom(node, st) {
  const key = keyOf(st);
  if (CACHE.has(key)) return CACHE.get(key);
  if (INFLIGHT.has(key)) return INFLIGHT.get(key);

  const req = (async () => {
    try {
      const res = await fetch(pixApiUrl("/pixaroma/api/duration/preview"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        // no-store: this is a computed answer, and a cached one would go stale
        // the moment the formula is edited.
        cache: "no-store",
        body: JSON.stringify({
          formula: st.formula, seconds: st.seconds, fps: st.fps,
          step: st.step, plus: st.plus, minFrames: st.minFrames,
        }),
      });
      if (!res.ok) return { ok: false, frames: 0, actual: 0 };
      const data = await res.json();
      const out = {
        ok: !!data?.ok,
        frames: Number(data?.frames) || 0,
        actual: Number(data?.actual) || 0,
      };
      if (CACHE.size >= MAX_CACHE) CACHE.clear();
      CACHE.set(key, out);
      return out;
    } catch {
      // Server down, route missing on an older install, offline: degrade to
      // "cannot preview", never to a wrong number.
      return { ok: false, frames: 0, actual: 0 };
    } finally {
      INFLIGHT.delete(key);
    }
  })();

  INFLIGHT.set(key, req);
  return req;
}
