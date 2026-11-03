// H3 Timeline Pixaroma - scene pictures: the input-folder list, upload, the
// picture URL, each picture's real size, and the picker (Load Image's own).
//
// A scene picture is a NAME in ComfyUI's input folder ("singer.jpg",
// "Studio/hat.png", "pixaroma_folders/..." for one taken from a folder), exactly
// like core Load Image's value, so Python resolves it the same way
// (nodes/node_h3_timeline._resolve_picture, input folder only).

import { api } from "../../../scripts/api.js";
import { openImageDropdown, injectCSS as injectLiCSS } from "../load_image/ui.mjs";
import { pixApiUrl } from "../shared/api_url.mjs";
import { comboViewRoute } from "../shared/view_url.mjs";

/** The picture's URL for an <img> or a CSS background (never root-relative). */
export const pictureUrl = (name) => pixApiUrl(comboViewRoute(name));

const sizes = new Map();          // name -> {w, h} | "loading" | "failed"

/** The picture's real size, loaded once; `then` runs when it arrives. */
export function pictureSize(name, then) {
  if (!name) return null;
  const s = sizes.get(name);
  if (s && typeof s === "object") return s;
  if (s === "loading" || s === "failed") return null;
  sizes.set(name, "loading");
  const img = new Image();
  img.onload = () => { sizes.set(name, { w: img.naturalWidth, h: img.naturalHeight }); then?.(); };
  img.onerror = () => { sizes.set(name, "failed"); then?.(); };
  img.src = pictureUrl(name);
  return null;
}
export const pictureFailed = (name) => sizes.get(name) === "failed";

/** Core's own list of input pictures (core Load Image's choices). Fetched on every
 *  open, so a file added outside ComfyUI shows (convention #18). */
export async function listPictures() {
  try {
    const res = await api.fetchApi("/object_info/LoadImage", { cache: "no-store" });
    const info = await res.json();
    const spec = info?.LoadImage?.input?.required?.image;
    const list = Array.isArray(spec?.[0]) ? spec[0] : (spec?.[1]?.options || []);
    return list.filter((n) => typeof n === "string");
  } catch {
    return [];
  }
}

/** Upload a picture File into the input folder; -> its name there. */
export async function uploadPicture(file) {
  const body = new FormData();
  body.append("image", file, file.name || "timeline.png");
  const res = await api.fetchApi("/upload/image", { method: "POST", body });
  if (res.status !== 200) throw new Error(`the upload answered ${res.status}`);
  const d = await res.json();
  return d?.subfolder ? `${d.subfolder}/${d.name}` : d?.name;
}

/** Ask for a picture file (the system dialog); -> File or null. */
export function askFile() {
  return new Promise((resolve) => {
    const inp = document.createElement("input");
    inp.type = "file";
    inp.accept = "image/*";
    inp.onchange = () => resolve(inp.files?.[0] || null);
    inp.click();
  });
}

let openPop = null;
let openReq = 0;

export function closePicker() {
  openReq += 1;                     // a picker still waiting for its list never opens
  const p = openPop;
  openPop = null;
  if (p?.isConnected) p._pixClose?.();
}

/** The picker under a scene: Load Image's own (search, + Folder, S / L, the
 *  folders on the left, thumbnails), reused through its `target` option, with
 *  Upload (and Remove, when the scene may have none) in its top row.
 *  `onPick(name | null)`. */
export async function openPicker(anchor, { current, canRemove, onPick, onUpload }) {
  closePicker();
  const my = openReq;
  injectLiCSS();                    // the picker does not inject its own stylesheet (load-image-mini.md)
  // Nothing shows while the list loads: any click but on something that opens a picker itself (the same row's
  // words box and the crop caption included) or Esc in that time cancels the open, or the picker would pop up
  // later and take the caret or cover the crop view. A click on another picture opens that one instead.
  const cancel = (e) => {
    if (e.type === "keydown" ? e.key === "Escape" : !e.target?.closest?.("[data-pix-h3t-pick]")) openReq += 1;
  };
  window.addEventListener("pointerdown", cancel, true);
  window.addEventListener("keydown", cancel, true);
  let values;
  try {
    values = await listPictures();
  } finally {
    window.removeEventListener("pointerdown", cancel, true);
    window.removeEventListener("keydown", cancel, true);
  }
  if (my !== openReq || !anchor.isConnected) return;
  const actions = [{
    label: "Upload", cls: "pix-h3t-upload",
    title: "Upload a picture from your computer (it goes into the input folder)",
    onClick: onUpload,
  }];
  if (canRemove) actions.push({
    label: "Remove",
    title: "No picture: this scene keeps the look of the scene before it",
    onClick: () => onPick(null),
  });
  openPop = openImageDropdown(null, anchor, (name) => onPick(name), { values, current, actions });
}
