// Info Pixaroma - shared state, constants and measurement.
//
// The node keeps EVERYTHING in its hidden note_json widget, in the same shape
// Note Pixaroma uses (so Note's editor can be reused unchanged), plus an
// "info" block for the button itself: { title, icon, color }.
//
// Widget, not node.properties: the editor writes the widget, ComfyUI saves
// both widgets_values copies from widget.value (Vue Compat #25), and a single
// home for the whole state cannot drift between two.

import { app } from "../../../scripts/app.js";
import { pixAsset } from "../shared/api_url.mjs";
import { notifyGraphChanged } from "../shared/graph_changed.mjs";

export const NODE = "PixaromaInfo";
export const WIDGET = "note_json";

// The icons a button can wear. A FIXED list, chosen by Pixaroma and shipped
// with the pack, so a shared workflow shows the same icon on every PC. The
// files live in assets/icons/note/ (the Note icon folder, so nothing is stored
// twice). Order = the order of the picker (9 per row, 3 rows).
export const ICONS = [
  "info", "question-v2", "idea", "attention", "to-do", "notebook", "prompt", "run-timer", "link",
  "edit", "image", "gear", "checkmark", "download-model", "model-v1", "model-v4", "model-v7", "checkpoint-v2",
  "LORA", "file", "folder-v1", "node-v5", "node-v6", "workflow-v3", "workflow-v4", "pixaroma", "bunny",
];
const ICON_SET = new Set(ICONS);
export const DEFAULT_ICON = "info";

// Button colours offered in the editor strip (any hex is accepted).
export const COLORS = [
  "#f66744", "#c8742a", "#c9921a", "#3f9a4f", "#2a9d8f",
  "#3d7cc9", "#4a6fa5", "#8a5cc7", "#c0392b", "#3a3a3a",
];

export const DEFAULT_INFO = { title: "Info", icon: DEFAULT_ICON, color: "#f66744" };
// Keep in sync with the widget default in nodes/node_info.py.
export const DEFAULT_CFG = {
  version: 1,
  content: "",
  buttonColor: "#f66744",
  lineColor: "#f66744",
  info: { ...DEFAULT_INFO },
};

export const TITLE_MAX = 60;
const HEX_RE = /^#[0-9a-f]{6}$/i;

export function iconOrDefault(id) {
  return ICON_SET.has(id) ? id : DEFAULT_ICON;
}

function cleanInfo(raw) {
  const r = raw && typeof raw === "object" ? raw : {};
  const title = typeof r.title === "string" ? r.title.replace(/[\r\n\t]+/g, " ").slice(0, TITLE_MAX) : DEFAULT_INFO.title;
  const out = {
    title,
    // Unknown ids are KEPT (a newer pack may have the icon); drawing falls
    // back to the Info icon via iconOrDefault, never a blank.
    icon: typeof r.icon === "string" && /^[A-Za-z0-9_-]{1,64}$/.test(r.icon) ? r.icon : DEFAULT_ICON,
    color: typeof r.color === "string" && HEX_RE.test(r.color) ? r.color.toLowerCase() : DEFAULT_INFO.color,
  };
  const reader = cleanReader(r.reader);
  if (reader) out.reader = reader;
  // The reading window's text size for THIS button (A- / A+), 1 = normal.
  const ts = Number(r.textScale);
  if (Number.isFinite(ts) && Math.abs(ts - 1) > 0.001) out.textScale = clampTextScale(ts);
  return out;
}

export const TEXT_SCALE = { min: 0.8, max: 2, step: 0.1 };
export function clampTextScale(v) {
  const n = Number.isFinite(v) ? v : 1;
  return Math.round(Math.max(TEXT_SCALE.min, Math.min(TEXT_SCALE.max, n)) * 10) / 10;
}

// Every place that rebuilds the button's info (the editor's Save, a starter,
// the reader's size and text controls) goes through this, so fields it does
// not own - the window size, the text size, anything added later - are kept.
export function withInfo(cfg, changes) {
  return { ...cfg, info: { ...cfg.info, ...changes } };
}

// The reading window's size for THIS button, saved with the workflow (the
// user's call: a short note opens small, a long one big, as its author set
// it). Missing = the default width and a height that fits the note.
export const READER_MIN = { w: 360, h: 180 };
const READER_MAX = { w: 4000, h: 4000 };
function cleanReader(r) {
  if (!r || typeof r !== "object") return null;
  const w = Number(r.w), h = Number(r.h);
  if (!Number.isFinite(w) || !Number.isFinite(h)) return null;
  return {
    w: Math.round(Math.max(READER_MIN.w, Math.min(READER_MAX.w, w))),
    h: Math.round(Math.max(READER_MIN.h, Math.min(READER_MAX.h, h))),
  };
}

export function findWidget(node) {
  return (node?.widgets || []).find((w) => w && w.name === WIDGET) || null;
}

// Parsed cfg, cached on the RAW widget string: the painter calls this every
// frame, and a string compare is all it costs while nothing changed.
export function readCfg(node) {
  const w = findWidget(node);
  const raw = w && typeof w.value === "string" ? w.value : "";
  if (node._pixInfoRaw === raw && node._pixInfoCfg) return node._pixInfoCfg;
  let parsed = {};
  if (raw && raw !== "{}") {
    try { parsed = JSON.parse(raw) || {}; } catch (_e) { parsed = {}; }
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) parsed = {};
  const cfg = { ...DEFAULT_CFG, ...parsed, info: cleanInfo(parsed.info) };
  if (typeof cfg.content !== "string") cfg.content = "";
  node._pixInfoRaw = raw;
  node._pixInfoCfg = cfg;
  return cfg;
}

// Write a cfg back. ONLY from a user action (never on the load path, Vue
// Compat #18): it changes serialized state on purpose.
export function writeCfg(node, cfg) {
  const w = findWidget(node);
  if (!w) return;
  const json = JSON.stringify(cfg);
  w.value = json;
  // Note's save mirrors into the live widgets_values too; serialize rebuilds
  // both saved copies from widget.value anyway (Vue Compat #25).
  if (Array.isArray(node.widgets_values)) {
    const i = node.widgets.indexOf(w);
    if (i > -1) node.widgets_values[i] = json;
  }
  node._pixInfoRaw = null;
  readCfg(node);
  node._pixInfoRefresh?.();
  try { node.setDirtyCanvas?.(true, false); } catch (_e) {}
  notifyGraphChanged();
}

// ── Sizes ───────────────────────────────────────────────────────────────────
// Every face size at scale 1. Both renderers multiply the same numbers, so the
// canvas and the CSS cannot drift apart (the Run Timer lesson).
export const M = { h: 34, padX: 14, icon: 18, gap: 8, font: 13, radius: 9, slack: 4 };
export const MIN_S = 0.6;
export const MAX_S = 8;
export const FONT_STACK = '"Segoe UI", system-ui, -apple-system, sans-serif';
export function fontAt(px) { return `600 ${px}px ${FONT_STACK}`; }

let _measCtx = null;
const _titleW = new Map();
export function titleWidth(title) {
  const t = String(title || "");
  if (!t) return 0;
  let w = _titleW.get(t);
  if (w != null) return w;
  try {
    _measCtx = _measCtx || document.createElement("canvas").getContext("2d");
    _measCtx.font = fontAt(M.font);
    w = Math.ceil(_measCtx.measureText(t).width);
  } catch (_e) { w = t.length * 7; }
  if (_titleW.size > 500) _titleW.clear();
  _titleW.set(t, w);
  return w;
}

// The button's width at scale 1 for this title: padding, icon, gap, text.
// "slack" covers the DOM measuring a pixel wider than the canvas.
export function unitWidth(info) {
  const tw = titleWidth(info?.title);
  return M.padX * 2 + M.icon + (tw ? M.gap + tw : 0) + M.slack;
}

export function clampS(s) {
  return Math.max(MIN_S, Math.min(MAX_S, Number.isFinite(s) && s > 0 ? s : 1));
}

// Text and icon on a light button go dark, so a pale colour stays readable.
export function isLight(hex) {
  const m = HEX_RE.exec(hex || "") ? hex : "#f66744";
  const n = parseInt(m.slice(1), 16);
  const lin = (c) => { c /= 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
  const L = 0.2126 * lin((n >> 16) & 255) + 0.7152 * lin((n >> 8) & 255) + 0.0722 * lin(n & 255);
  return L > 0.42;
}
export function inkFor(hex) { return isLight(hex) ? "#1b1b1b" : "#ffffff"; }

export function iconUrl(id) {
  return pixAsset(`icons/note/${iconOrDefault(id)}.svg`);
}

// ── Icon pictures for the CLASSIC canvas ────────────────────────────────────
// A canvas cannot use a CSS mask, so each icon is turned into an <img> of the
// SVG with its fill set to the ink colour. Loaded once per (icon, ink); while
// it loads the painter skips the icon and the canvas repaints when it lands.
const _imgs = new Map();
export function iconImage(id, ink) {
  const key = `${iconOrDefault(id)}|${ink}`;
  const hit = _imgs.get(key);
  if (hit) return hit.ok ? hit.img : null;
  const entry = { ok: false, img: null };
  _imgs.set(key, entry);
  fetch(iconUrl(id), { cache: "force-cache" })
    .then((r) => (r.ok ? r.text() : Promise.reject(new Error(String(r.status)))))
    .then((svg) => {
      const tinted = svg.replace(/<svg\b/, `<svg fill="${ink}"`);
      const img = new Image();
      img.onload = () => {
        entry.ok = true;
        entry.img = img;
        try { app.graph?.setDirtyCanvas?.(true, false); } catch (_e) {}
      };
      img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(tinted);
    })
    // Keep the failed entry: deleting it would refetch on EVERY frame. The
    // button simply shows no icon until the next page load.
    .catch(() => { entry.failed = true; });
  return null;
}
