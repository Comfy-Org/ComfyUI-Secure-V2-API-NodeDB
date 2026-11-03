// Video Prompt Pixaroma - talking to the server about formulas.
//
// The formulas are FILES, not settings: 8.7k to 12.3k characters each, times
// three modes, plus four duration tiers apiece. That is far too much to sit in
// ComfyUI's settings store, and it wants to survive a pack update, so the
// shipped copies live in assets/video_prompt_formulas and a user's edits go to
// <ComfyUI user dir>/pixaroma/video_prompt_formulas.
//
// Everything here is re-fetched on every panel open (convention #18): a picker
// backed by our own route gets nothing from ComfyUI's R refresh, so a session
// cache would look permanently stale after an edit made anywhere else.

import { pixApiUrl } from "../shared/api_url.mjs";

const BASE = "/pixaroma/api/video_prompt";

async function call(route, options) {
  const res = await fetch(pixApiUrl(BASE + route), {
    cache: "no-store",
    ...(options || {}),
  });
  if (!res.ok) throw new Error(route + " -> " + res.status);
  return res.json();
}

function post(route, body) {
  return call(route, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
}

/**
 * Everything the settings panel needs, in ONE request.
 *
 * Returns { modes: { <mode>: { formula, chars, edited, durations } },
 *           models: [...], model_dir_ok: bool }
 *
 * Never rejects - the panel must still open and say what is wrong when the
 * server is unreachable, rather than showing an empty shell with no
 * explanation.
 */
export async function fetchAll() {
  try {
    const data = await call("/formulas");
    return { ok: true, ...data };
  } catch (e) {
    return {
      ok: false,
      error: String(e && e.message ? e.message : e),
      modes: {},
      models: [],
      sizes: {},
    };
  }
}

export async function saveFormula(mode, text) {
  try {
    const data = await post("/formula", { mode, text });
    return data && data.ok === true;
  } catch (e) {
    return false;
  }
}

export async function saveDurations(mode, tiers) {
  try {
    const data = await post("/durations", { mode, tiers });
    return data && data.ok === true;
  } catch (e) {
    return false;
  }
}

/** Delete the user's override so the shipped formula is used again. */
export async function resetMode(mode) {
  try {
    const data = await post("/reset", { mode });
    return data && data.ok === true;
  } catch (e) {
    return false;
  }
}
