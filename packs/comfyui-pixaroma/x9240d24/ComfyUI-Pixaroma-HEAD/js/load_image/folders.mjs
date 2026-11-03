// Load Image Pixaroma + Load Image Mini: pictures from the user's OWN folders.
// Built 2026-09-29. Full design: .claude/patterns/load-image.md ("Folders").
//
//   * The folders are a per-PERSON list in an unregistered setting, never in
//     node.properties, so adding one can never mark a workflow modified.
//   * A folder is added ONLY through the operating system's folder window
//     (Load Images from Folder's pick_native route). That window is what
//     APPROVES it on the server, and it is the only thing that can: a web
//     request can make the window appear, but only a person can pick and OK.
//   * A picture taken from a folder is COPIED into input/pixaroma_folders by the
//     import route, and the node holds that ordinary input name. So the preview,
//     Mask Editor, clipspace, validation and saved workflows all keep working
//     exactly as they do for an uploaded file. At Run the node refreshes the copy
//     from the original (nodes/_folder_source.py).
//   * Which folder the current picture came from lives on node.properties
//     (pixLiFolderPick), written only by a real pick, so the arrows can step
//     through that folder and the picker can open on it.

import { app } from "../../../scripts/app.js";
import { pixApiUrl } from "../shared/api_url.mjs";
import { listFolder, thumbURL, pickNativeFolder } from "../load_images_folder/api.mjs";
import { setSelectedImage } from "./api.mjs";

export const FOLDER_PREFIX = "pixaroma_folders/";
const SETTING = "Pixaroma.LoadImage.Folders";
const CACHE_MS = 15000;

export { thumbURL as folderThumbURL };

/** Is this image value one of our folder copies? */
export function isFolderCopy(value) {
  return String(value ?? "").replace(/\\/g, "/").startsWith(FOLDER_PREFIX);
}

/** "Photos / cat.png" for a copy (the folder's own name, without the hash). */
export function folderCopyLabel(value) {
  const parts = String(value ?? "").replace(/\\/g, "/").split("/");
  if (parts.length !== 3 || parts[0] + "/" !== FOLDER_PREFIX) return String(value ?? "");
  return `${parts[1].replace(/_[0-9a-f]{8}$/, "")} / ${parts[2]}`;
}

/** The last part of a folder path, for labels. */
export function folderName(path) {
  const p = String(path || "").replace(/[\\/]+$/, "");
  const i = Math.max(p.lastIndexOf("\\"), p.lastIndexOf("/"));
  return (i >= 0 ? p.slice(i + 1) : p) || p;
}

function normFolder(p) {
  let s = String(p || "").replace(/\\/g, "/").replace(/\/+$/, "");
  // Windows paths compare without case (a drive letter or a \\server share)
  if (/^[a-z]:/i.test(s) || s.startsWith("//")) s = s.toLowerCase();
  return s;
}

export function sameFolder(a, b) {
  return normFolder(a) === normFolder(b);
}

// ── the per-person folder list ─────────────────────────────────────────────

export function getFolders() {
  let v;
  try { v = app.ui?.settings?.getSettingValue?.(SETTING); } catch (e) { v = null; }
  if (!Array.isArray(v)) return [];
  const out = [];
  for (const f of v) {
    if (typeof f === "string" && f.trim() && !out.some((x) => sameFolder(x, f))) out.push(f);
  }
  return out;
}

async function setFolders(list) {
  try { await app.ui?.settings?.setSettingValueAsync?.(SETTING, list); } catch (e) {
    console.warn("[Pixaroma] could not save the folder list", e);
  }
}

export async function removeFolder(path) {
  await setFolders(getFolders().filter((f) => !sameFolder(f, path)));
}

/**
 * Open the operating system's folder window and add what the user picks.
 * Returns {ok:true, path} / {ok:false, cancelled:true} / {ok:false, message}.
 */
export async function addFolderViaDialog() {
  const r = await pickNativeFolder("");
  if (r?.ok && r.path) {
    const list = getFolders();
    if (!list.some((f) => sameFolder(f, r.path))) {
      list.push(r.path);
      await setFolders(list);
    }
    if (r.remembered === false) {
      return { ok: true, path: r.path, message: "Added, but the approval could not be saved, so pictures from it may be refused. Check that ComfyUI's user folder is writable." };
    }
    return { ok: true, path: r.path };
  }
  if (r?.cancelled) return { ok: false, cancelled: true };
  if (r?.busy) return { ok: false, message: "A folder window is already open. Finish with that one first." };
  if (r?.unavailable) {
    return { ok: false, message: "This ComfyUI cannot open a folder window (it runs on another computer, or without a screen). Its own input and output folders always work; see Help for approving another folder by hand." };
  }
  return { ok: false, message: r?.message || "Could not open the folder window." };
}

// ── listing a folder ───────────────────────────────────────────────────────

// Pictures directly in the folder first, then each subfolder in turn - the
// picker groups them that way, and the arrows must step in the same order.
const dirOf = (f) => { const i = f.file.lastIndexOf("/"); return i >= 0 ? f.file.slice(0, i) : ""; };
// ONE collator, made once: calling localeCompare with options inside a sort
// comparator rebuilds it on every call - measured 2.25 s to sort 50,000
// pictures against 0.15 s this way, identical order (review round 1).
const cmp = new Intl.Collator(undefined, { numeric: true, sensitivity: "base" }).compare;
const byPath = (a, b) => {
  const da = dirOf(a), db = dirOf(b);
  if (da !== db) return da === "" ? -1 : db === "" ? 1 : cmp(da, db);
  return cmp(a.file, b.file);
};

/**
 * The pictures in a folder (and its subfolders), sorted the way the picker
 * shows them, so the arrows step in the same order. Kept on the node for a
 * short while so holding an arrow does not re-read the disk every step.
 * Returns {ok, files, message?, denied?}.
 */
export async function folderFiles(node, folder, { fresh = false } = {}) {
  const c = node?._pixLiFolderFiles;
  if (!fresh && c && sameFolder(c.folder, folder) && Date.now() - c.at < CACHE_MS) {
    return { ok: true, files: c.files };
  }
  const r = await listFolder(folder, true);
  if (!r?.ok) return { ok: false, files: [], message: r?.message || "Could not read the folder.", denied: !!r?.denied };
  const files = (r.files || []).filter((f) => f && typeof f.file === "string").sort(byPath);
  if (node) node._pixLiFolderFiles = { folder, files, at: Date.now() };
  return { ok: true, files };
}

// ── taking a picture from a folder ─────────────────────────────────────────

async function importFromFolder(folder, file) {
  try {
    const r = await fetch(pixApiUrl("/pixaroma/api/load_image/import"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ folder, file }),
      cache: "no-store",
    });
    return await r.json();
  } catch (e) {
    return { ok: false, message: String(e?.message || e) };
  }
}

/**
 * Copy `file` from `folder` into input and make it the node's picture.
 * Returns {ok:true, name} or {ok:false, message}.
 */
export async function pickFromFolder(node, folder, file) {
  const r = await importFromFolder(folder, file);
  if (!r?.ok || !r.name) return { ok: false, message: r?.message || "Could not take the picture." };
  if (!node.graph) return { ok: false, message: "The node was removed." };
  if (!node.properties) node.properties = {};
  // Before setSelectedImage, whose change capture then includes it.
  node.properties.pixLiFolderPick = { folder, file, name: r.name };
  setSelectedImage(node, r.name);
  return { ok: true, name: r.name };
}

/** Copy one folder picture into input WITHOUT touching any node (H3 Timeline's
 *  scene pictures): -> { ok, name } or { ok: false, message }. */
export async function takeFolderPicture(folder, file) {
  const r = await importFromFolder(folder, file);
  if (!r?.ok || !r.name) return { ok: false, message: r?.message || "Could not take the picture." };
  return { ok: true, name: r.name };
}

/** The folder the CURRENT picture came from, or null. */
export function folderContext(node) {
  const pick = node?.properties?.pixLiFolderPick;
  const value = node?._pixLiImageWidget?.value;
  if (!pick || typeof pick !== "object") return null;
  if (typeof pick.folder !== "string" || typeof pick.file !== "string" || pick.name !== value) return null;
  return pick;
}

/**
 * Arrows / PageUp / PageDown while the picture came from a folder: step through
 * THAT folder. Returns false when the picture did not come from one, so the
 * caller steps through the input folder exactly as before.
 */
export function stepFolder(node, offset, onDone) {
  const pick = folderContext(node);
  if (!pick) return false;
  if (node._pixLiFolderStepping) return true;      // one step at a time
  node._pixLiFolderStepping = true;
  (async () => {
    try {
      const res = await folderFiles(node, pick.folder);
      const files = res.files || [];
      if (!files.length) return;
      const n = files.length;
      const i = files.findIndex((f) => f.file === pick.file);
      const next = i < 0 ? (offset > 0 ? 0 : n - 1) : ((i + offset) % n + n) % n;
      const r = await pickFromFolder(node, pick.folder, files[next].file);
      if (r.ok) onDone?.(r.name);
    } catch (e) {
      console.warn("[Pixaroma] folder step failed", e);
    } finally {
      node._pixLiFolderStepping = false;
    }
  })();
  return true;
}

/**
 * After a workflow is opened the folder has not been listed yet, so the counter
 * would stay blank until the arrows were used. List it once in the background
 * and call `onReady` (a label refresh). A GET that writes nothing, so it is safe
 * on the load path; on a refusal it simply does not call back (no retry loop).
 */
export function primeFolderListing(node, onReady) {
  const pick = folderContext(node);
  if (!pick || node._pixLiFolderPriming) return;
  const c = node._pixLiFolderFiles;
  if (c && sameFolder(c.folder, pick.folder)) return;
  node._pixLiFolderPriming = true;
  folderFiles(node, pick.folder).then(
    (r) => { node._pixLiFolderPriming = false; if (r.ok && node.graph) onReady?.(); },
    () => { node._pixLiFolderPriming = false; },
  );
}

/** "3 / 42" inside the folder, when its listing is at hand; "" otherwise. */
export function folderCounter(node) {
  const pick = folderContext(node);
  const c = node?._pixLiFolderFiles;
  if (!pick || !c || !sameFolder(c.folder, pick.folder) || c.files.length < 2) return "";
  const i = c.files.findIndex((f) => f.file === pick.file);
  return i >= 0 ? `${i + 1} / ${c.files.length}` : "";
}

// ── the "Picture folders" section for a settings panel ─────────────────────

let _cssDone = false;
function injectFoldersCSS() {
  if (_cssDone || document.getElementById("pix-lifold-css")) { _cssDone = true; return; }
  _cssDone = true;
  const s = document.createElement("style");
  s.id = "pix-lifold-css";
  s.textContent = `
    .pix-lifold { display:flex; flex-direction:column; gap:7px; }
    .pix-lifold-h { font-size:12px; color:#ddd; font-weight:600; }
    .pix-lifold-hint { font-size:11px; color:#8a8a8a; line-height:1.4; }
    .pix-lifold-list { display:flex; flex-direction:column; gap:4px; }
    .pix-lifold-row { display:flex; align-items:center; gap:8px; padding:5px 6px 5px 8px;
      background:rgba(255,255,255,0.04); border:1px solid #333; border-radius:5px; }
    .pix-lifold-txt { flex:1; min-width:0; display:flex; flex-direction:column; }
    .pix-lifold-name { font-size:12px; color:#ddd; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .pix-lifold-path { font-size:10px; color:#777; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .pix-lifold-x { flex:none; width:22px; height:22px; border:1px solid #444; border-radius:4px;
      background:transparent; color:#999; cursor:pointer; font-size:12px; line-height:1; padding:0; }
    .pix-lifold-x:hover { border-color:var(--pix-acc, var(--acc, #f66744)); color:#fff; }
    .pix-lifold-empty { font-size:11px; color:#777; }
    .pix-lifold-add { align-self:flex-start; border:1px solid #444; background:rgba(255,255,255,0.04);
      color:#d8d8d8; border-radius:5px; padding:5px 12px; font-size:12px; cursor:pointer; font-family:inherit; }
    .pix-lifold-add:hover { border-color:var(--pix-acc, var(--acc, #f66744)); background:var(--pix-acc, var(--acc, #f66744)); color:#fff; }
    .pix-lifold-add[disabled] { opacity:.5; cursor:default; }
    .pix-lifold-msg { font-size:11px; color:#e0a060; line-height:1.4; }
    .pix-lifold-msg:empty { display:none; }
  `;
  document.head.appendChild(s);
}

/**
 * The "Picture folders" block for a settings panel: the list, a remove button
 * per folder, and "Add folder". `onChanged` runs after an add or a remove.
 */
export function buildFoldersSection({ onChanged } = {}) {
  injectFoldersCSS();
  const wrap = document.createElement("div");
  wrap.className = "pix-lifold";
  const h = document.createElement("div");
  h.className = "pix-lifold-h";
  h.textContent = "Picture folders";
  const hint = document.createElement("div");
  hint.className = "pix-lifold-hint";
  hint.textContent = "Folders listed here show up in the file picker, beside ComfyUI's input folder. "
    + "Add one by picking it in the folder window, which also approves it. A picture you take "
    + "is copied into the input folder, and refreshed from the original at each Run.";
  const list = document.createElement("div");
  list.className = "pix-lifold-list";
  const msg = document.createElement("div");
  msg.className = "pix-lifold-msg";
  const add = document.createElement("button");
  add.type = "button";
  add.className = "pix-lifold-add";
  add.textContent = "Add folder…";
  add.title = "Opens the folder window on the computer running ComfyUI";

  const render = () => {
    list.replaceChildren();
    const folders = getFolders();
    if (!folders.length) {
      const e = document.createElement("div");
      e.className = "pix-lifold-empty";
      e.textContent = "No folders yet.";
      list.appendChild(e);
      return;
    }
    for (const f of folders) {
      const row = document.createElement("div");
      row.className = "pix-lifold-row";
      const txt = document.createElement("div");
      txt.className = "pix-lifold-txt";
      const n = document.createElement("span");
      n.className = "pix-lifold-name";
      n.textContent = folderName(f);
      const p = document.createElement("span");
      p.className = "pix-lifold-path";
      p.textContent = f;
      txt.title = f;
      txt.append(n, p);
      const x = document.createElement("button");
      x.type = "button";
      x.className = "pix-lifold-x";
      x.textContent = "✕";
      x.title = "Remove from the list. The folder and its pictures are not touched.";
      x.addEventListener("click", async (e) => {
        e.stopPropagation();
        await removeFolder(f);
        render();
        onChanged?.();
      });
      row.append(txt, x);
      list.appendChild(row);
    }
  };

  add.addEventListener("click", async (e) => {
    e.stopPropagation();
    add.disabled = true;
    msg.textContent = "";
    try {
      const r = await addFolderViaDialog();
      if (r.message) msg.textContent = r.message;
      if (r.ok) { render(); onChanged?.(); }
    } finally {
      add.disabled = false;
    }
  });

  render();
  wrap.append(h, hint, list, add, msg);
  return wrap;
}
