// ╔═══════════════════════════════════════════════════════════════╗
// ║  Pixaroma Workflows - every call that touches a workflow       ║
// ╚═══════════════════════════════════════════════════════════════╝
//
// Deliberately the ONLY file in this feature that talks to the server or to
// ComfyUI's workflow store, so the calls that can cost somebody their work sit
// in one small file that can be read end to end.
//
// ── How a workflow is opened, and why it looks like this ────────────────────
//
// The obvious call is a trap. `app.extensionManager.workflow.openWorkflow(wf)`
// returns a Promise that resolves immediately and flips `activeWorkflow` to the
// target, but it NEVER LOADS THE GRAPH: measured against a real 14-node file,
// `isLoaded` stayed false and the canvas still showed the previous workflow
// after six seconds of polling, and the workflow was not even added to the open
// tabs. It is store bookkeeping, not an open.
//
// ComfyUI's own sidebar goes through a workflow SERVICE that lives in a
// hash-named chunk (dialogService-<hash>.js). That is not reachable from an
// extension - not on app.extensionManager, not in window.comfyAPI, and
// app.workflowManager does not exist - and importing the chunk by name would
// break on every frontend release.
//
// So we replay the app's own call, built only from stable public objects. This
// was verified against a live ComfyUI (2026-07-29):
//   - a 14-node file loads all 14 nodes into the correct tab, unmodified;
//   - switching AWAY from a workflow with unsaved edits does not lose them,
//     they stay in that workflow's tab exactly as with the native sidebar;
//   - switching BACK to an open, modified workflow restores the MODIFIED state,
//     not the version on disk.
//
// Two rules must never be relaxed:
//   1. NEVER pass { force: true } to load(). It refetches from disk and would
//      silently throw away unsaved edits.
//   2. NEVER call save()/saveAs() except from an explicit user action.

import { app } from "../../../scripts/app.js";
import { pixApiUrl } from "../shared/api_url.mjs";

// Left BARE on purpose: this prefix is concatenated onto, and a hosted ComfyUI
// appends its auth token as a QUERY STRING - so a wrapped prefix would put the
// token in the middle of the url. The WHOLE url is wrapped at the fetch instead.
const BASE = "/pixaroma/api/workflows";

const store = () => app.extensionManager?.workflow;

// ── server ───────────────────────────────────────────────────────────────────

async function getJSON(url) {
  // no-store on our side too: this list must match the disk, and a heuristically
  // cached copy would quietly show workflows that have been renamed or deleted.
  const r = await fetch(pixApiUrl(url), { cache: "no-store" });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

async function postJSON(url, body) {
  const r = await fetch(pixApiUrl(url), {
    method: "POST",
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

export const fetchIndex = () => getJSON(`${BASE}/index`);
export const fetchMeta = () => getJSON(`${BASE}/meta`);
export const saveMeta = (patch) => postJSON(`${BASE}/meta`, patch);
export const folderAction = (body) => postJSON(`${BASE}/folder`, body);
export const reveal = (path) => postJSON(`${BASE}/reveal`, { path });

/** Store a hand-picked cover as a real file. It used to be embedded in the
 *  sidecar as base64, which meant the whole panel re-downloaded every cover on
 *  every open - three of them already made that file 96 KB. */
export const setCover = (rel, dataUrl) => postJSON(`${BASE}/cover`, { rel, dataUrl });

/** Remove a cover. The server deletes the picture too, unless another workflow
 *  still points at it. */
export const clearCover = (rel) => saveMeta({ covers: { [rel]: null } });

// ── ComfyUI's workflow store ────────────────────────────────────────────────

/** The store keys workflows as "workflows/<relative path>". */
export const toStorePath = (rel) => (rel.startsWith("workflows/") ? rel : `workflows/${rel}`);
export const fromStorePath = (p) => (p || "").replace(/^workflows\//, "");

export function activePath() {
  return fromStorePath(store()?.activeWorkflow?.path || "");
}

export function openPaths() {
  return (store()?.openWorkflows || []).map((w) => fromStorePath(w.path));
}

export function isModified(rel) {
  const w = store()?.getWorkflowByPath?.(toStorePath(rel));
  return !!w?.isModified;
}

/**
 * The store's object for a workflow, with one retry through syncWorkflows.
 *
 * The panel's own listing comes from OUR server route, which reads the folder -
 * so it shows a file the instant it exists. ComfyUI's STORE only knows files it
 * has synced, and a workflow dropped into the folder from Explorer (or written
 * by anything else while ComfyUI runs) is not in it yet. Every action then
 * failed with "That workflow is no longer there." - about a file the user could
 * SEE in the panel. One sync closes the gap; if the file genuinely is gone, the
 * retry misses too and the message is finally true.
 */
async function storeWorkflow(rel) {
  const s = store();
  if (!s?.getWorkflowByPath) throw new Error("This ComfyUI build has no workflow store.");
  let wf = s.getWorkflowByPath(toStorePath(rel));
  if (!wf && typeof s.syncWorkflows === "function") {
    try {
      await s.syncWorkflows();
      wf = s.getWorkflowByPath(toStorePath(rel));
    } catch { /* the throw below says what matters */ }
  }
  return wf;
}

/**
 * Open a workflow. See the note at the top of this file before changing ANY
 * line of this function.
 */
export async function openWorkflow(rel) {
  const wf = await storeWorkflow(rel);
  if (!wf) throw new Error("That workflow is no longer there.");

  // No { force: true }: on an already-open workflow this is a no-op and its
  // unsaved edits survive. Forcing would refetch from disk and lose them.
  await wf.load();
  await app.loadGraphData(wf.activeState, true, true, wf);
  return wf;
}

/** Is there already a workflow at this path? Asked before a rename, move or
 *  save-as.
 *
 *  How much work it is doing differs by caller, which is worth knowing before
 *  trusting or removing it. For RENAME and DUPLICATE it is only a courtesy: both
 *  reach the server with `?overwrite=false` (rename via core's moveUserData,
 *  duplicate explicitly), so the server refuses on its own and this check merely
 *  buys a sentence naming the file instead of a status code. For SAVE-AS it is
 *  the only check we have - core's saveAs is not documented to refuse - so do
 *  not drop it there. */
export async function exists(rel) {
  try {
    // Core's own route, and it needs wrapping just as much as ours: a bare
    // /api/... resolves against the PAGE origin, which on a hosted ComfyUI is
    // not the API. apiURL leaves an address that already starts with /api
    // alone apart from the deployment prefix, so this is unchanged locally.
    const r = await fetch(pixApiUrl(`/api/userdata/${encodeURIComponent(toStorePath(rel))}`),
                          { method: "HEAD", cache: "no-store" });
    return r.ok;
  } catch {
    return false;      // unreachable server: let the real call report the problem
  }
}

/** Rename OR move - a move is just a rename with a different folder in it.
 *
 *  The exists() check above is for the MESSAGE, not for safety. Core's rename
 *  goes through moveUserData, which defaults to `?overwrite=false`, so the
 *  server refuses to clobber an existing file on its own and nothing can be
 *  lost in the gap between the check and the move. What the server returns in
 *  that case is a bare status line ("Failed to rename file 'x': 409 Conflict"),
 *  so the gap is closed by translating it rather than by trying to win a race
 *  that has no prize. */
export async function renameOrMove(rel, newRel) {
  const leaf = () => newRel.split("/").pop();
  // Changing only the CAPITALISATION cannot be done, and saying "there is
  // already a workflow called that" would be describing the file itself. On a
  // case-insensitive disk the destination resolves to the same file, and
  // ComfyUI's own move refuses it with a 409 (measured) - so this is a core
  // limitation to report plainly, not something to route around by moving the
  // file behind the store's back.
  const caseOnly = rel !== newRel && rel.toLowerCase() === newRel.toLowerCase();
  if (caseOnly) {
    throw new Error("Only the capitalisation changed, and ComfyUI cannot rename a "
      + "workflow to the same name in a different case. Rename it to something "
      + "else first, then back.");
  }
  if (rel !== newRel && await exists(newRel)) {
    throw new Error(`There is already a workflow called "${leaf()}" there.`);
  }
  const s = store();
  const wf = await storeWorkflow(rel);
  if (!wf) throw new Error("That workflow is no longer there.");
  // Through the store, never by moving the file behind its back: this is what
  // keeps an open tab pointing at the right file and its modified flag intact.
  try {
    if (typeof wf.rename === "function") await wf.rename(toStorePath(newRel));
    else if (typeof s.renameWorkflow === "function") await s.renameWorkflow(wf, toStorePath(newRel));
    else throw new Error("This ComfyUI build cannot rename workflows.");
  } catch (err) {
    const msg = String(err?.message || err);
    if (/\b409\b|conflict|exists/i.test(msg)) {
      throw new Error(`There is already a workflow called "${leaf()}" there.`);
    }
    throw err;
  }
  await s.syncWorkflows?.();
}

export async function remove(rel) {
  const s = store();
  const wf = await storeWorkflow(rel);
  if (!wf) throw new Error("That workflow is no longer there.");
  if (typeof wf.delete === "function") await wf.delete();
  else if (typeof s.deleteWorkflow === "function") await s.deleteWorkflow(wf);
  else throw new Error("This ComfyUI build cannot delete workflows.");
  await s.syncWorkflows?.();
}

/**
 * Save the workflow that is open RIGHT NOW into a folder. User action only.
 *
 * ⚠ A NEVER-SAVED workflow cannot go through saveAs, and the failure is silent.
 * Core's `UserFile.saveAs(path)` is:
 *
 *     async saveAs(path) {
 *       const f = this.isTemporary ? this : UserFile.createTemporary(path)
 *       f.content = this.content; await f.save(); return f
 *     }
 *
 * so for a TEMPORARY workflow it saves ITSELF at ITS OWN path and the path we
 * asked for is discarded. Measured: "Save open workflow here" into a folder
 * wrote `workflows/Unsaved Workflow.json` at the ROOT, the chosen folder AND the
 * chosen name both ignored, while the panel toasted "Saved". The workflow was
 * persisted by that write, so a SECOND attempt took the other branch and worked
 * - which is why it reads as "it only saves the second time" and why the folder
 * (usually a folder just created, hence empty) gets the blame.
 *
 * Core's own saveWorkflowAs never calls saveAs on a temporary workflow. It
 * RENAMES it to the destination first and then saves, which is what this does.
 * Going through the store's renameWorkflow rather than `wf.rename` matters: for
 * a temporary file rename is only an in-memory `updatePath`, and the store is
 * what re-keys its lookup and the open-tab list to the new path.
 */
export async function saveCurrentAs(newRel, { overwrite = false } = {}) {
  if (!overwrite && await exists(newRel)) {
    throw new Error(`There is already a workflow called "${newRel.split("/").pop()}" there.`);
  }
  const s = store();
  const wf = s?.activeWorkflow;
  if (!wf) throw new Error("Nothing is open to save.");
  const path = toStorePath(newRel);

  if (wf.isTemporary) {
    if (typeof s.renameWorkflow === "function") await s.renameWorkflow(wf, path);
    else if (typeof wf.rename === "function") await wf.rename(path);
    else throw new Error("This ComfyUI build cannot save an unsaved workflow into a folder.");
    // Same call core makes between the rename and the write: it snapshots the
    // graph the change tracker will compare against, so the workflow is not
    // left looking modified the instant it has been saved.
    wf.changeTracker?.prepareForSave?.();
    if (typeof s.saveWorkflow === "function") await s.saveWorkflow(wf);
    else if (typeof wf.save === "function") await wf.save();
    else throw new Error("This ComfyUI build cannot save workflows.");
  } else {
    if (typeof wf.saveAs !== "function") throw new Error("This ComfyUI build cannot save-as.");
    await wf.saveAs(path);
  }
  await s.syncWorkflows?.();
}

/**
 * Copy a workflow beside itself. Uses ComfyUI's own userdata endpoints rather
 * than reading and rewriting the file ourselves, so the copy is byte-identical
 * and lands where core expects it.
 */
export async function duplicate(rel, newRel) {
  const enc = (p) => encodeURIComponent(toStorePath(p));
  // Wrapped for the same reason as in exists() above.
  const r = await fetch(pixApiUrl(`/api/userdata/${enc(rel)}`), { cache: "no-store" });
  if (!r.ok) throw new Error("Could not read that workflow.");
  const body = await r.text();
  const w = await fetch(pixApiUrl(`/api/userdata/${enc(newRel)}?overwrite=false`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  });
  if (!w.ok) throw new Error(w.status === 409 ? "A workflow with that name already exists." : "Could not save the copy.");
  await store()?.syncWorkflows?.();
}

/**
 * ComfyUI does NOT read the favourites file at startup. Its bookmark store is
 * empty until something calls loadBookmarks() - normally its own Workflows
 * sidebar being opened. Two consequences, and the second one destroys data:
 *
 *   1. reading the list straight away reports NO favourites even when the file
 *      has some, so every star showed as unset;
 *   2. toggling in that state appends to an EMPTY in-memory list and saves it,
 *      which overwrites the file and wipes every favourite that was on disk.
 *      This wiped a real one during development.
 *
 * So the store is loaded from disk before the list is read AND before anything
 * is toggled. It is one small local file, and being right matters more than the
 * few milliseconds.
 */
export async function ensureFavouritesLoaded() {
  const bm = bookmarkStore();
  if (typeof bm?.loadBookmarks !== "function") return false;
  try {
    await bm.loadBookmarks();
    return true;
  } catch {
    return false;
  }
}

/** Favourites are ComfyUI's own bookmarks, so its sidebar shows the same stars.
 *  Only meaningful after ensureFavouritesLoaded() has resolved. */
export function favourites() {
  return new Set((store()?.bookmarkedWorkflows || []).map((w) => fromStorePath(w.path)));
}

/**
 * Favourites live in ComfyUI's `workflowBookmark` store, which persists them to
 * `user/default/workflows/.index.json` - the same file and the same stars its
 * own sidebar shows.
 *
 * That store is NOT on `app.extensionManager` (which exposes only a read-only
 * `bookmarkedWorkflows` list), so it has to be reached through pinia.
 *
 * There is deliberately NO fallback that writes `.index.json` ourselves. It was
 * tried and it DESTROYS DATA: the store holds its own copy in memory, so a
 * direct write drifts from it, the star does not light up, and the app's next
 * save overwrites the file from its stale copy. During development that silently
 * wiped a real favourite. Failing honestly is better than a fallback that can
 * delete the other favourites as a side effect.
 */
function bookmarkStore() {
  try {
    const pinia = document.querySelector("#vue-app")?.__vue_app__?.config?.globalProperties?.$pinia;
    return pinia?._s?.get("workflowBookmark") || null;
  } catch {
    return null;
  }
}

export async function toggleFavourite(rel) {
  const bm = bookmarkStore();
  if (typeof bm?.toggleBookmarked !== "function") {
    throw new Error("This ComfyUI build keeps favourites somewhere this panel cannot reach. "
      + "Use the star in ComfyUI's own Workflows sidebar.");
  }
  // MUST come first. Toggling against a store that has not read the file yet
  // saves a list built from nothing and erases every existing favourite.
  await ensureFavouritesLoaded();
  await bm.toggleBookmarked(toStorePath(rel));
  return true;
}

export async function refreshStore() {
  await store()?.syncWorkflows?.();
}
