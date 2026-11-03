// AI Prompt Pixaroma - the one thing this node asks the server for.
//
// The formula lives ON the node, so there is nothing here to save, reset,
// import or export server-side. All that is left is the list of models on
// disk for the picker.
//
// Re-fetched on every panel open (convention #18): a custom picker backed by
// our own route gets NOTHING from ComfyUI's R refresh, so a session cache
// would look permanently stale after somebody renames a file.

import { pixApiUrl } from "../shared/api_url.mjs";

/**
 * { ok, models: [...], error? }
 *
 * Never rejects. The panel must still open and say what is wrong when the
 * server is unreachable, rather than showing an empty picker with no
 * explanation - an empty folder and a failed scan must not look identical.
 */
async function post(route, body) {
  try {
    const res = await fetch(pixApiUrl("/pixaroma/api/ai_prompt" + route), {
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
 * The shipped presets and the user's own.
 *
 * A preset is a formula AND the settings that make it work: the Krea 2 wording
 * rambles at temperature 0.7 and behaves at 0.3, so shipping the text without
 * the number would ship something that looks broken.
 */
export async function fetchPresets() {
  try {
    const res = await fetch(pixApiUrl("/pixaroma/api/ai_prompt/presets"), {
      cache: "no-store",
    });
    if (!res.ok) throw new Error("presets -> " + res.status);
    const data = await res.json();
    // The route answers 200 with an `error` field when its own read threw, so
    // ignoring that field turned a server-side failure into a confident empty
    // library - the exact lie the rest of this is built to avoid. Three
    // channels exist (HTTP status, `error`, `userError`); honour all three.
    if (data?.error) {
      return { ok: false, shipped: [], user: [], userError: false,
               error: String(data.error) };
    }
    return {
      ok: true,
      shipped: Array.isArray(data?.shipped) ? data.shipped : [],
      user: Array.isArray(data?.user) ? data.user : [],
      // The server read the file and could not understand it. An empty library
      // and an unreadable one must never look the same: in the second case the
      // user still HAS presets, and saving would have overwritten them.
      userError: !!data?.userError,
    };
  } catch (e) {
    return { ok: false, shipped: [], user: [], userError: false,
             error: String(e?.message || e) };
  }
}

export function savePreset(preset) {
  return post("/presets/save", preset);
}

export function deletePreset(name) {
  return post("/presets/delete", { name });
}

export async function fetchModels() {
  try {
    const res = await fetch(pixApiUrl("/pixaroma/api/ai_prompt/models"), {
      cache: "no-store",
    });
    if (!res.ok) throw new Error("models -> " + res.status);
    const data = await res.json();
    return {
      ok: !data?.error,
      models: Array.isArray(data?.models) ? data.models : [],
      // Byte size per name, for the picker's size label. A SEPARATE map on
      // purpose: `models` stays a plain string array because several
      // `.includes(...)` checks in the panels depend on it.
      sizes: (data && typeof data.sizes === "object" && data.sizes) || {},
      error: data?.error ? String(data.error) : null,
    };
  } catch (e) {
    return { ok: false, models: [], sizes: {}, error: String(e?.message || e) };
  }
}
