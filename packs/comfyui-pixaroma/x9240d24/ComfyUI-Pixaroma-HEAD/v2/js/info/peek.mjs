// Info Pixaroma - a peek on hover.
//
// Rest the pointer on an Info button for half a second and a small card shows
// the note's first heading and first line, so buttons of the same size and
// colour can be told apart without opening them. Moving away, pressing, the
// wheel or a key closes it; a click still opens the full window.
//
// One passive window listener for the whole app. It does its hit test at most
// once per frame, and only does real work while the pointer is over a button.

import { sanitize } from "../note/sanitize.mjs";
import { readCfg, findWidget } from "./core.mjs";
import { infoAt } from "./hit.mjs";
import { isEmptyNote } from "./face.mjs";
import { nodeScreenRect, starterPopupOpen } from "./starters.mjs";
import { readerNode } from "./reader.mjs";

const DELAY = 500;
const CSS = [
  ".pix-info-peek{position:fixed;z-index:1380;width:290px;max-width:calc(100vw - 16px);background:#252525;border:1px solid #474747;",
  "border-radius:9px;box-shadow:0 10px 28px rgba(0,0,0,.7);padding:10px 12px 9px;pointer-events:none;",
  // overflow-wrap: a long file name has no space to break at and ran out of
  // the card (reported on a Models note).
  "font:12.5px/1.45 'Segoe UI',system-ui,sans-serif;color:#cfcfcf;overflow-wrap:anywhere;}",
  ".pix-info-peek b{display:block;color:#fff;font-size:13.5px;margin-bottom:3px;}",
  ".pix-info-peek .m{margin-top:6px;font-size:11.5px;color:#f66744;}",
].join("\n");
let _cssDone = false;
function injectCSS() {
  if (_cssDone) return;
  _cssDone = true;
  const s = document.createElement("style");
  s.setAttribute("data-pixaroma-info-peek", "1");
  s.textContent = CSS;
  document.head.appendChild(s);
}

let _over = null;      // the button under the pointer
let _timer = null;
let _card = null;
let _raf = 0;
let _last = null;      // the last pointermove, read once per frame

// First heading + first line of text, cached on the saved string.
const _sum = new Map();
function summary(node) {
  const raw = findWidget(node)?.value || "";
  let s = _sum.get(raw);
  if (s) return s;
  const cfg = readCfg(node);
  const html = String(cfg.content || "").trim();
  s = { head: "", text: "" };
  if (html) {
    try {
      const doc = new DOMParser().parseFromString(sanitize(html), "text/html");
      // Note's blocks put their parts in separate elements with no space
      // between ("...safetensors" + "5.75 GB" read "safetensors5.75 GB").
      // textContent joins them, so add a space after each block part and line
      // break, on BOTH sides (the size label sits right after the name, so the
      // missing space was before it); the whitespace is collapsed below.
      for (const el of doc.body.querySelectorAll("[class], br, div")) { el.before(" "); el.after(" "); }
      const h = doc.body.querySelector("h1, h2, h3");
      s.head = (h?.textContent || "").replace(/\s+/g, " ").trim();
      for (const el of doc.body.querySelectorAll("p, li")) {
        const t = (el.textContent || "").replace(/\s+/g, " ").trim();
        if (t && t !== s.head) { s.text = t; break; }
      }
      // Text that lives only in a code block, a table or a quote: show the
      // start of it rather than calling a written note empty (reproduced).
      if (!s.head && !s.text) s.text = (doc.body.textContent || "").replace(/\s+/g, " ").trim();
    } catch (_e) {}
  }
  if (s.text.length > 170) s.text = s.text.slice(0, 167).trimEnd() + "...";
  if (_sum.size > 200) _sum.clear();
  _sum.set(raw, s);
  return s;
}

function hide() {
  if (_timer) { clearTimeout(_timer); _timer = null; }
  if (_card) { _card.remove(); _card = null; }
}

function show(node) {
  _timer = null;
  if (!node || node !== _over || readerNode() === node || starterPopupOpen()) return;
  if (document.querySelector(".pix-note-overlay")) return;   // an editor is open
  injectCSS();
  const info = readCfg(node).info;
  const s = summary(node);
  const card = document.createElement("div");
  card.className = "pix-info-peek";
  card.style.borderTop = `3px solid ${info.color}`;
  const b = document.createElement("b");
  b.textContent = s.head || info.title || "Info";
  card.appendChild(b);
  const t = document.createElement("div");
  // "Empty" comes from the SAME test the button's dashed outline uses.
  t.textContent = s.text || (!s.head && isEmptyNote(node) ? "This note is empty. Click the button to write it." : "");
  if (t.textContent) card.appendChild(t);
  const m = document.createElement("div");
  m.className = "m";
  m.textContent = isEmptyNote(node) ? "" : "Click the button to read all";
  if (m.textContent) card.appendChild(m);
  document.body.appendChild(card);
  _card = card;
  // Above the button, centred on it, kept on screen; below it if no room.
  const r = nodeScreenRect(node);
  const cw = card.offsetWidth, ch = card.offsetHeight;
  let left = r.left + (r.width - cw) / 2;
  let top = r.top - ch - 10;
  if (top < 8) top = r.bottom + 10;
  left = Math.max(8, Math.min(window.innerWidth - cw - 8, left));
  top = Math.max(8, Math.min(window.innerHeight - ch - 8, top));
  card.style.left = `${Math.round(left)}px`;
  card.style.top = `${Math.round(top)}px`;
}

function tick() {
  _raf = 0;
  const e = _last;
  if (!e) return;
  const n = e.buttons ? null : infoAt(e);
  if (n === _over) return;
  _over = n;
  hide();
  if (n) _timer = setTimeout(() => show(n), DELAY);
}

if (typeof window !== "undefined" && !window._pixInfoPeekWired) {
  window._pixInfoPeekWired = true;
  window.addEventListener("pointermove", (e) => {
    _last = e;
    if (e.buttons) { if (_over || _card) { _over = null; hide(); } return; }
    if (!_raf) _raf = requestAnimationFrame(tick);
  }, { capture: true, passive: true });
  const off = () => { _over = null; hide(); };
  window.addEventListener("pointerdown", off, true);
  window.addEventListener("wheel", off, { capture: true, passive: true });
  window.addEventListener("keydown", off, true);
  window.addEventListener("blur", off);
}

export function hidePeek() { _over = null; hide(); }
