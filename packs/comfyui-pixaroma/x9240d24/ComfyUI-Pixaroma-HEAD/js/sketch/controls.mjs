// Sketch Pixaroma - the controls both surfaces share (the node face and the big
// view): tools, undo/redo/clear, colours + line width, the numbered notes list,
// and the prompt preview with its "remove the marks" switch.
//
// Built ONCE per surface; sync() only flips classes and text, so a click never
// rebuilds the button it came from. The notes list is the one thing rebuilt,
// and only on a structural change (a mark added, deleted, undone), never while
// typing - a rebuild would steal the note box's focus mid-word.

import { isComfyTextShortcut } from "../shared/text_shortcuts.mjs";
import {
  COLORS, SWATCHES, WIDTH_KEYS, buildPrompt, injectedState, markName, readState, rgbOf,
} from "./core.mjs";
import {
  clearMarks, deleteMark, redo, refresh, setNote, setRemoveMarks, uiState, undo,
} from "./actions.mjs";

const svg = (inner) => `<svg viewBox="0 0 24 24" aria-hidden="true">${inner}</svg>`;
const S = 'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"';

export const TOOLS = [
  { id: "box", key: "B", title: "Box: drag a rectangle around what to change (B)", icon: svg(`<rect x="4" y="5" width="16" height="14" rx="1" ${S}/>`) },
  { id: "ellipse", key: "C", title: "Circle: drag an oval around what to change (C)", icon: svg(`<ellipse cx="12" cy="12" rx="8.5" ry="7" ${S}/>`) },
  { id: "pen", key: "P", title: "Freehand: draw a loop around something, or sketch a shape to add (P)", icon: svg(`<path d="M4 17c2-7 6-11 10-11s6 4 3 7-8 3-9 0 3-6 8-4" ${S}/>`) },
  { id: "arrow", key: "A", title: "Arrow: drag from where you start to what you point at (A)", icon: svg(`<path d="M5 19L18 6M18 6h-8M18 6v8" ${S}/>`) },
  { id: "text", key: "T", title: "Text: click on the picture and type a word (T)", icon: svg(`<path d="M5 6h14M12 6v13" ${S} stroke-width="2.4"/>`) },
];

const ICON_UNDO = svg(`<path d="M9 7L4 12l5 5M4 12h9a6 6 0 010 12h-2" ${S} transform="translate(0,-3)"/>`);
const ICON_REDO = svg(`<path d="M15 7l5 5-5 5M20 12h-9a6 6 0 000 12h2" ${S} transform="translate(0,-3)"/>`);
const ICON_CLEAR = svg(`<path d="M5 7h14M9 7V5h6v2M7 7l1 13h8l1-13" ${S}/>`);
const ICON_EXPAND = svg(`<path d="M4 10V4h6M20 14v6h-6M4 4l6 6M20 20l-6-6" ${S}/>`);

function btn(cls, title, html) {
  const b = document.createElement("button");
  b.type = "button";
  b.className = cls;
  b.title = title;
  if (html) b.innerHTML = html;
  return b;
}

function sep(vertical) {
  const s = document.createElement("span");
  s.className = vertical ? "pix-sketch-hsep" : "pix-sketch-sep";
  return s;
}

/** The five tools. Returns sync(). */
export function buildTools(node, host, { vertical = false } = {}) {
  const buttons = TOOLS.map((t) => {
    const b = btn("pix-sketch-btn", t.title, t.icon);
    b.dataset.tool = t.id;
    b.addEventListener("click", (e) => {
      e.stopPropagation();
      uiState(node).tool = t.id;
      refresh(node, false);
    });
    host.appendChild(b);
    return b;
  });
  void vertical;
  return () => {
    const tool = uiState(node).tool;
    for (const b of buttons) b.classList.toggle("on", b.dataset.tool === tool);
  };
}

/** Undo / Redo / Clear, plus the optional Expand and Gear. Returns sync(). */
export function buildActions(node, host, { vertical = false, onExpand = null, onGear = null } = {}) {
  if (vertical) host.appendChild(sep(true));
  const u = btn("pix-sketch-btn", "Undo the last change (Ctrl+Z in the big view)", ICON_UNDO);
  const r = btn("pix-sketch-btn", "Redo (Ctrl+Y in the big view)", ICON_REDO);
  const c = btn("pix-sketch-btn", "Remove every mark", ICON_CLEAR);
  u.addEventListener("click", (e) => { e.stopPropagation(); undo(node); });
  r.addEventListener("click", (e) => { e.stopPropagation(); redo(node); });
  c.addEventListener("click", (e) => { e.stopPropagation(); clearMarks(node); });
  host.append(u, r, c);
  if (onExpand) {
    const x = btn("pix-sketch-btn", "Open a big view for careful marking", ICON_EXPAND);
    x.addEventListener("click", (e) => { e.stopPropagation(); onExpand(); });
    host.appendChild(x);
  }
  if (onGear) {
    const g = btn("pix-sketch-btn pix-sketch-gear", "Settings", "");
    g.addEventListener("click", (e) => { e.stopPropagation(); onGear(); });
    host.appendChild(g);
  }
  return () => {
    const ui = uiState(node);
    const has = readState(node).marks.length > 0;
    u.disabled = !ui.undo.length;
    r.disabled = !ui.redo.length;
    c.disabled = !has;
  };
}

/** Colour swatches then the line width. Returns sync(). */
export function buildColors(node, host, { label = true } = {}) {
  const swatches = SWATCHES.map((name) => {
    const s = btn("pix-sketch-sw", `${name[0].toUpperCase()}${name.slice(1)}: the colour for the next mark`, "");
    s.style.background = rgbOf(name);
    s.dataset.color = name;
    s.addEventListener("click", (e) => {
      e.stopPropagation();
      uiState(node).color = name;
      refresh(node, false);
    });
    host.appendChild(s);
    return s;
  });
  const grow = document.createElement("span");
  grow.className = "pix-sketch-grow";
  host.appendChild(grow);
  if (label) {
    const l = document.createElement("span");
    l.className = "pix-sketch-wl";
    l.textContent = "Line";
    host.appendChild(l);
  }
  const widths = WIDTH_KEYS.map((k) => {
    const b = btn("pix-sketch-w", {
      S: "Thin line", M: "Medium line", L: "Thick line", XL: "Very thick: for colouring in a rough sketch",
    }[k], "");
    b.textContent = k;
    b.dataset.w = k;
    b.addEventListener("click", (e) => {
      e.stopPropagation();
      uiState(node).width = k;
      refresh(node, false);
    });
    host.appendChild(b);
    return b;
  });
  return () => {
    const ui = uiState(node);
    for (const s of swatches) s.classList.toggle("on", s.dataset.color === ui.color);
    for (const b of widths) b.classList.toggle("on", b.dataset.w === ui.width);
  };
}

/** The numbered notes, one row per mark. Rebuilt on structural changes only. */
export function renderList(node, host, { hint = "Drag on the picture to mark what to change, then write the change here." } = {}) {
  const keep = host.scrollTop;     // the list scrolls past four rows: a rebuild must not jump to the top
  host.replaceChildren();
  const marks = readState(node).marks;
  if (!marks.length) {
    const h = document.createElement("div");
    h.className = "pix-sketch-hint";
    h.textContent = hint;
    host.appendChild(h);
    return;
  }
  marks.forEach((m, i) => {
    const row = document.createElement("div");
    row.className = "pix-sketch-mrow";
    const badge = document.createElement("span");
    badge.className = "pix-sketch-badge";
    badge.textContent = String(i + 1);
    badge.style.background = rgbOf(m.color);
    const c = COLORS[m.color] || COLORS.red;
    badge.style.color = c[0] * 0.299 + c[1] * 0.587 + c[2] * 0.114 > 170 ? "#111" : "#fff";
    const name = document.createElement("span");
    name.className = "pix-sketch-name";
    name.textContent = markName(m);
    name.title = m.type === "text" ? `"${m.text}"` : markName(m);
    const note = document.createElement("input");
    note.className = "pix-sketch-note";
    note.type = "text";
    note.placeholder = m.type === "text" ? "optional note" : "what to change here";
    note.value = m.note || "";
    note.title = "What the edit model should do here. It becomes one sentence of the prompt.";
    note.addEventListener("input", () => setNote(node, i, note.value));
    note.addEventListener("keydown", (e) => {
      // Ctrl+Enter still runs the workflow; everything else stays in the box.
      if (isComfyTextShortcut(e)) return;
      e.stopPropagation();
      if (e.key === "Enter") note.blur();
    });
    const del = btn("pix-sketch-del", "Delete this mark", "×");
    del.addEventListener("click", (e) => { e.stopPropagation(); deleteMark(node, i); });
    row.addEventListener("pointerenter", () => { uiState(node).hover = i; refresh(node, false); });
    row.addEventListener("pointerleave", () => {
      if (uiState(node).hover === i) { uiState(node).hover = -1; refresh(node, false); }
    });
    row.append(badge, name, note, del);
    host.appendChild(row);
  });
  host.scrollTop = keep;
}

/** A mark was just drawn: show its row and put the caret in its note, since
 *  what to change there is the next thing to write. preventScroll, because a
 *  plain focus() also scrolls every ancestor to reveal the box, the graph
 *  canvas included. */
export function focusLastNote(host) {
  const notes = host.querySelectorAll(".pix-sketch-note");
  const inp = notes[notes.length - 1];
  if (!inp) return;
  host.scrollTop = host.scrollHeight;
  try { inp.focus({ preventScroll: true }); } catch {}
}

/** The prompt preview (read-only, raised) with the remove-the-marks switch. */
export function buildPromptBox(node, host) {
  const head = document.createElement("div");
  head.className = "pix-sketch-phead";
  const label = document.createElement("span");
  label.className = "pix-sketch-plabel";
  label.textContent = "Prompt";
  label.title = "What the prompt output sends. Wire it into the text encode.";
  const sw = document.createElement("label");
  sw.className = "pix-sketch-swc";
  sw.title = "Adds a last sentence asking the model to remove the drawn marks. Edit models often keep them otherwise.";
  const tog = document.createElement("span");
  tog.className = "pix-sketch-tog";
  const swText = document.createElement("span");
  swText.textContent = "remove the marks";
  sw.append(tog, swText);
  sw.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    setRemoveMarks(node, !readState(node).removeMarks);
  });
  head.append(label, sw);
  const text = document.createElement("div");
  text.className = "pix-sketch-ptext";
  host.append(head, text);
  return () => {
    const st = readState(node);
    tog.classList.toggle("on", st.removeMarks);
    const p = buildPrompt(injectedState(node).marks, st.removeMarks);
    text.classList.toggle("empty", !p);
    text.textContent = p || "Write a note beside a mark and the prompt appears here.";
    text.title = p ? "Select to copy" : "";
  };
}
