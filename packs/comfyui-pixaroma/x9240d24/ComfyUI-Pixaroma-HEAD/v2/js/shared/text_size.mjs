// Text size of the Pixaroma text boxes (a Discord ask, 2026-10-11: "a font size in the options, for the older folks").
//
// ComfyUI already has the setting: Settings > Appearance > Node Widget > "Textarea widget font size"
// (Comfy.TextareaWidget.FontSize, 8-24, default 10). Core writes it to --comfy-textarea-font-size on <html> and its
// own text boxes use it as their size. Ours use it as a ZOOM FACTOR (value / 10), never as a copied size: every box
// keeps the size it was designed with (11-12 px, node by node) at the default 10, and at 15 every one is 1.5x, the
// same step core's boxes take. On top of that each node can have its own level (node.properties.pixTextZoom, the
// right-click "Text size" menu, js/text_size/index.js), written to its DOM widget roots as --pix-text-zoom.
//   size = the box's own size x ComfyUI's value / 10 x the node's level
import { notifyGraphChanged } from "./graph_changed.mjs";

export const TEXT_SIZE_SETTING = "Comfy.TextareaWidget.FontSize";
const ZOOM_PROP = "pixTextZoom";
const CHANGE = "pix-text-size";

// The CSS font-size of a box designed at `px` (a px line-height takes it too; a unitless one follows by itself).
// "* px / 10" and not a pre-divided factor, so the default resolves to exactly px (10 * 12 / 10 = 12).
export function textSize(px) {
  return `calc(var(--comfy-textarea-font-size, 10px) * ${px} / 10 * var(--pix-text-zoom, 1))`;
}

export function nodeTextZoom(node) {
  const z = Number(node?.properties?.[ZOOM_PROP]);
  return z > 0 ? z : 1;
}

// DOM only (a style variable on each DOM widget root), so it is safe on the load path. Writes and notifies only an
// element whose value really changes: the load path calls it twice (js/text_size/index.js).
export function applyNodeTextZoom(node, byUser = false) {
  const z = nodeTextZoom(node);
  const v = z === 1 ? "" : String(z);
  for (const w of node?.widgets || []) {
    const el = w.element;
    if (!el?.style || el.style.getPropertyValue("--pix-text-zoom") === v) continue;
    if (v) el.style.setProperty("--pix-text-zoom", v);
    else el.style.removeProperty("--pix-text-zoom");
    notifyTextSize(el, byUser);
  }
}

// A user action: 1 removes the key, so a node at its normal size saves nothing new.
export function setNodeTextZoom(node, z) {
  z = Math.round(z * 10) / 10;
  if (z === nodeTextZoom(node)) return;
  if (z === 1) delete node.properties[ZOOM_PROP];
  else node.properties[ZOOM_PROP] = z;
  applyNodeTextZoom(node, true);
  notifyGraphChanged();
}

// fn(byUser) runs after el's text size changed: the ComfyUI value or its node's level (byUser), or a saved level put
// back while a workflow opens (not byUser: never grow a node or write anything then). For what does not follow a
// font change on its own: a layer that copies the box's font as px values (the @tag colours of Prompt, AI Prompt
// and Music Prompt), boxes sized to their text. The listener lives on el, so it goes when el goes.
export function onTextSizeChange(el, fn) {
  el.setAttribute("data-pix-text-size", "");
  el.addEventListener(CHANGE, (e) => fn(e.detail.byUser));
}

export function notifyTextSize(root = document, byUser = true) {
  const send = (el) => el.dispatchEvent(new CustomEvent(CHANGE, { detail: { byUser } }));
  if (root.hasAttribute?.("data-pix-text-size")) send(root);
  for (const el of root.querySelectorAll("[data-pix-text-size]")) send(el);
}
