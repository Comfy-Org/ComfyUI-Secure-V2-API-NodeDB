// Music Prompt Pixaroma - named formula sets.
//
// A SET is the two instructions plus the sampling that makes them work, under a
// name that says what it is for. The node ships one measured set; a second
// model becomes another entry rather than a rewrite.
//
// The model LIST comes from AI Prompt's route, which already lists
// text_encoders - see settings.mjs. This file is only about the sets.

import { pixApiUrl } from "../shared/api_url.mjs";

async function post(route, body) {
  try {
    const res = await fetch(pixApiUrl("/pixaroma/api/music_prompt" + route), {
      method: "POST",
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    const data = await res.json();
    return { ok: !!data?.ok, message: String(data?.message || "") };
  } catch (e) {
    return { ok: false, message: String(e?.message || e) };
  }
}

/**
 * { ok, shipped, user, userError, error? } - never rejects.
 *
 * Three channels, and all three matter. `error` is the route itself failing;
 * `userError` is the user's file existing and being unreadable, which must NOT
 * look like an empty library - in that case they still HAVE sets and saving
 * would destroy them.
 *
 * Re-fetched on every panel open (house convention #18): a custom picker backed
 * by our own route gets nothing from ComfyUI's R refresh.
 */
export async function fetchPresets() {
  try {
    const res = await fetch(pixApiUrl("/pixaroma/api/music_prompt/presets"), {
      cache: "no-store",
    });
    if (!res.ok) throw new Error("presets -> " + res.status);
    const data = await res.json();
    if (data?.error) {
      return { ok: false, shipped: [], user: [], userError: false,
               error: String(data.error) };
    }
    return {
      ok: true,
      shipped: Array.isArray(data?.shipped) ? data.shipped : [],
      user: Array.isArray(data?.user) ? data.user : [],
      userError: !!data?.userError,
      error: null,
    };
  } catch (e) {
    return { ok: false, shipped: [], user: [], userError: false,
             error: String(e?.message || e) };
  }
}

export function savePreset(set) {
  return post("/presets/save", set);
}

export function deletePreset(name) {
  return post("/presets/delete", { name });
}
