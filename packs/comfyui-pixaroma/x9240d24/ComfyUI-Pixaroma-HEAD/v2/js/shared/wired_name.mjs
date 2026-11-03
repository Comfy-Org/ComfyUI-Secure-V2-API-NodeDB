// The wired `name` input of Save Image / Save Video Pixaroma, resolved for the
// live "Will save as" line. DISPLAY ONLY: Python recomputes the name at save
// time and never sees anything from here.
//
// ONE copy for both nodes (2026-09-29). Save Video had its own version that took
// the FIRST text widget of any name on the source node - on Concatenate Text
// that is its first box, so the line showed `clips_001.mp4` for a file really
// named `clips_-take_001.mp4` - and returned "" when it could not tell, so the
// name silently vanished (`001.mp4`). Save Image printed the literal word
// `name`, which read as a real filename (Discord 2026-09-28).
import { app } from "../../../scripts/app.js";
import { cleanInputName } from "./filename_mirror.mjs";

// Stands in for a wired name that is only known once the workflow runs (a
// Concatenate Text, a Text Join, Load Images from Folder's per-image filename).
// Letters only, so it passes through the date, token and sanitizer-mirror steps
// untouched; setPreviewPath draws it as a marked placeholder.
export const WIRED_UNKNOWN = "PIXWIREDNAMEUNKNOWN";
const WIRED_LABEL = "‹wired name›";
export const WIRED_TIP =
  "The part in ‹ › comes from the node wired into name. That node makes its " +
  "text while the workflow runs, so it cannot be shown here - the file still " +
  "gets the real text.";

// "" when nothing is wired, the cleaned text when the browser can know it, and
// WIRED_UNKNOWN when only a run can. `keepFolders` mirrors the node's own rule
// for slashes in the wired text (Save Video always flattens them).
export function resolveWiredName(node, keepFolders = false) {
  try {
    const inp = node.inputs && node.inputs.find((i) => i && i.name === "name");
    if (!inp || inp.link == null) return "";
    // node.graph first: app.graph holds only TOP-LEVEL nodes and the node may
    // live inside a subgraph
    const graph = node.graph || app.graph;
    let link = graph.links?.[inp.link];
    if (!link && typeof graph.links?.get === "function") link = graph.links.get(inp.link);
    if (!link) return WIRED_UNKNOWN;
    const origin = graph.getNodeById ? graph.getNodeById(link.origin_id) : null;
    if (!origin) return WIRED_UNKNOWN;
    if (origin.comfyClass === "PixaromaLoadImage") {
      const w = origin.widgets?.find((x) => x && x.name === "image");
      let v = typeof w?.value === "string" ? w.value : "";
      v = v.replace(/\s*\[(input|output|temp)\]\s*$/i, "");
      v = v.split("/").pop().split("\\").pop();
      return cleanInputName(v, keepFolders) || WIRED_UNKNOWN;
    }
    // a plain text-ish widget on the origin (Text Pixaroma etc.) - best effort
    const tw = origin.widgets?.find(
      (x) => x && typeof x.value === "string" && x.value &&
        (x.name === "text" || x.name === "value" || x.name === "string")
    );
    if (tw) return cleanInputName(String(tw.value).slice(0, 60), keepFolders) || WIRED_UNKNOWN;
    return WIRED_UNKNOWN; // wired, value only known at run time
  } catch {
    return WIRED_UNKNOWN;
  }
}

// Write the preview path into `el`, drawing any WIRED_UNKNOWN as a marked
// placeholder with the node's own class. DOM text nodes only, never innerHTML:
// the path carries user-typed text. Returns whether a placeholder was drawn.
export function setPreviewPath(el, text, className) {
  const parts = String(text).split(WIRED_UNKNOWN);
  if (parts.length === 1) {
    el.textContent = text;
    return false;
  }
  el.textContent = "";
  parts.forEach((part, i) => {
    if (i > 0) {
      const tag = document.createElement("span");
      tag.className = className;
      tag.textContent = WIRED_LABEL;
      el.appendChild(tag);
    }
    if (part) el.appendChild(document.createTextNode(part));
  });
  return true;
}
