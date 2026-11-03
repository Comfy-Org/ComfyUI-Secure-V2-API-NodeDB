// Info Pixaroma - Edit: Note Pixaroma's own editor, plus a strip on top for the
// button (title, icon, colour).
//
// Note's editor is reused UNCHANGED. It reads node._noteCfg and saves into the
// node's note_json widget, which is exactly where Info keeps its state. What
// Info adds is done from outside, on this one editor instance:
//   - the strip is inserted into the editor's panel, under its header;
//   - the instance's save() is wrapped so the strip's values are written into
//     the same saved state, in the same Save (Cancel throws them away);
//   - the instance's _cleanup() is wrapped to refresh the button and, when the
//     editor was opened from the reading window, open that window again.

import { NoteEditor } from "../note/core.mjs";
import "../note/toolbar.mjs";
import "../note/blocks.mjs";
import { openPixaromaCompactColorPickerPopup, PIXAROMA_PALETTE } from "../shared/color_picker.mjs";
import { notifyGraphChanged } from "../shared/graph_changed.mjs";
import { sanitize } from "../note/sanitize.mjs";
import { ICONS, COLORS, TITLE_MAX, readCfg, iconUrl, inkFor, iconOrDefault } from "./core.mjs";
import { refitToContent, STARTERS, starterSection } from "./starters.mjs";

const CSS = [
  ".pix-info-strip{display:flex;flex-direction:column;gap:10px;padding:10px 14px;background:#222;border-bottom:1px solid #333;}",
  ".pix-info-srow{display:flex;align-items:center;flex-wrap:wrap;gap:10px 14px;min-width:0;}",
  ".pix-info-slab{font-size:11px;font-weight:700;color:#8f8f8f;letter-spacing:.05em;}",
  ".pix-info-sin{background:#111;border:1px solid #444;border-radius:5px;padding:5px 9px;color:#eee;font:13px 'Segoe UI',system-ui,sans-serif;width:150px;outline:none;}",
  ".pix-info-sin:focus{border-color:#f66744;}",
  ".pix-info-sicb{display:inline-flex;align-items:center;gap:6px;border:1px solid #444;border-radius:6px;padding:4px 8px;background:#111;color:#f66744;cursor:pointer;}",
  ".pix-info-sicb:hover,.pix-info-sicb.on{border-color:#f66744;}",
  ".pix-info-sicb small{color:#999;font-size:10px;}",
  ".pix-info-mi{display:block;background:currentColor;-webkit-mask:var(--i) center/contain no-repeat;mask:var(--i) center/contain no-repeat;}",
  ".pix-info-sw{display:flex;gap:5px;align-items:center;}",
  ".pix-info-sw button{width:20px;height:20px;border-radius:50%;border:2px solid transparent;padding:0;cursor:pointer;}",
  ".pix-info-sw button:hover{border-color:#ffffffaa;}",
  ".pix-info-sw button.on{border-color:#fff;}",
  ".pix-info-sw .pix-info-more{background:conic-gradient(#f66744,#d9a520,#3f9a4f,#2a9d8f,#3d7cc9,#8a5cc7,#c0392b,#f66744);}",
  // The preview takes what is left of the row and truncates a long title,
  // so it never wraps onto a line of its own (flex-basis 110px decides the wrap;
  // the title box is 150px so the row still fits with the Template button, measured
  // on an 891px row).
  ".pix-info-pw{flex:1 1 110px;min-width:0;display:flex;justify-content:flex-end;}",
  ".pix-info-prev{display:inline-flex;align-items:center;gap:7px;border-radius:9px;padding:6px 13px;font:600 13px 'Segoe UI',system-ui,sans-serif;",
  "box-shadow:inset 0 1px 0 rgba(255,255,255,.18);white-space:nowrap;max-width:100%;min-width:0;overflow:hidden;}",
  ".pix-info-prev > span:last-child{overflow:hidden;text-overflow:ellipsis;min-width:0;}",
  ".pix-info-prev .pix-info-mi{width:17px;height:17px;flex:none;}",
  ".pix-info-igrid{display:none;grid-template-columns:repeat(9, 38px);gap:5px;}",
  ".pix-info-igrid.open{display:grid;}",
  ".pix-info-igrid button{height:34px;border-radius:6px;border:1px solid transparent;background:#2a2a2a;color:#e6e6e6;cursor:pointer;display:flex;align-items:center;justify-content:center;padding:0;}",
  ".pix-info-igrid button:hover{border-color:#f66744;}",
  ".pix-info-igrid button.on{background:#f66744;color:#fff;}",
  ".pix-info-igrid .pix-info-mi{width:19px;height:19px;}",
  // The Template button and its menu (a ready-made section at the cursor).
  ".pix-info-strip{position:relative;}",
  ".pix-info-tpl{display:inline-flex;align-items:center;gap:6px;border:1px solid #444;border-radius:6px;padding:4px 9px;background:#111;color:#ddd;cursor:pointer;font:12px 'Segoe UI',system-ui,sans-serif;}",
  ".pix-info-tpl:hover,.pix-info-tpl.on{border-color:#f66744;color:#fff;}",
  ".pix-info-tpl small{color:#999;font-size:10px;}",
  ".pix-info-tmenu{position:absolute;z-index:6;display:none;min-width:210px;background:#262626;border:1px solid #474747;border-radius:8px;box-shadow:0 12px 28px rgba(0,0,0,.65);padding:5px;}",
  ".pix-info-tmenu.open{display:block;}",
  ".pix-info-tmenu .hint{padding:4px 10px 6px;color:#8f8f8f;font:11px 'Segoe UI',system-ui,sans-serif;}",
  ".pix-info-tmenu button{display:flex;align-items:center;gap:9px;width:100%;padding:6px 10px;border:0;border-radius:5px;background:none;color:#ddd;font:13px 'Segoe UI',system-ui,sans-serif;text-align:left;cursor:pointer;}",
  ".pix-info-tmenu button:hover{background:#353535;color:#fff;}",
  ".pix-info-tmenu .pix-info-mi{width:16px;height:16px;flex:none;}",
].join("\n");
let _cssDone = false;
function injectStripCSS() {
  if (_cssDone) return;
  _cssDone = true;
  const s = document.createElement("style");
  s.setAttribute("data-pixaroma-info-strip", "1");
  s.textContent = CSS;
  document.head.appendChild(s);
}

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}
function maskIcon(id, size) {
  const i = el("span", "pix-info-mi");
  i.style.setProperty("--i", `url("${iconUrl(id)}")`);
  if (size) { i.style.width = `${size}px`; i.style.height = `${size}px`; }
  return i;
}

// ── Template: a starter's empty headings, inserted where the cursor is ──────

// The caret in the note body, or null (the focus is in the strip, say).
function bodyRange(editor) {
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0 || !editor._editArea) return null;
  const r = sel.getRangeAt(0);
  return editor._editArea.contains(r.commonAncestorContainer) ? r.cloneRange() : null;
}

// The same direct DOM insert Note's own blocks use (blocks.mjs separator):
// after the top-level block holding the caret, replacing it when it is an empty
// line, else at the end. One undo step (snapBefore / snapAfter).
function insertSection(editor, st, savedRange) {
  editor._dirty = true;
  if (editor._mode === "code" && editor._codeView?.textarea) {
    const ta = editor._codeView.textarea;
    // AFTER a selection, never over it: Code view has no undo for this
    // (Note's Ctrl+Z works on the preview), so replacing selected text lost
    // it until Cancel (reproduced). Preview mode never replaces either.
    const at = ta.selectionEnd ?? ta.value.length;
    ta.focus();
    ta.setRangeText(starterSection(st, !!ta.value.trim()), at, at, "end");
    ta.dispatchEvent(new Event("input", { bubbles: true }));
    return;
  }
  const area = editor._editArea;
  if (!area) return;
  editor._normalizeEditArea?.();
  area.focus();
  editor._snapBefore?.();
  const wrap = document.createElement("div");
  wrap.innerHTML = sanitize(starterSection(st, !!area.textContent.trim()));
  const nodes = [...wrap.childNodes];
  if (!nodes.length) return;
  const top = (n) => {
    if (!n) return null;
    if (n.nodeType !== 1) n = n.parentNode;
    while (n && n.parentNode !== area && n !== area) n = n.parentNode;
    return n && n.parentNode === area ? n : null;
  };
  // Note's own empty-line rule (blocks.mjs): no children, one <br>, or one
  // blank text node. A test on "no text" alone also matched an empty TABLE
  // (its cells hold only <br>) and the insert deleted it (reproduced).
  const isEmptyBlock = (b) => {
    if (!b || b.nodeType !== 1 || !/^(P|DIV|H1|H2|H3)$/.test(b.tagName)) return false;
    const cs = b.childNodes;
    if (cs.length === 0) return true;
    if (cs.length !== 1) return false;
    if (cs[0].nodeType === 1) return cs[0].tagName === "BR";
    return cs[0].nodeType === 3 && !(cs[0].nodeValue || "").replace(/\s/g, "");
  };
  const anchor = savedRange && area.contains(savedRange.startContainer) ? top(savedRange.startContainer) : null;
  if (anchor && isEmptyBlock(anchor)) anchor.replaceWith(...nodes);
  else if (anchor) anchor.after(...nodes);
  else area.append(...nodes);
  // The caret at the end of what was inserted, ready to type.
  try {
    const r = document.createRange();
    r.selectNodeContents(nodes[nodes.length - 1]);
    r.collapse(false);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(r);
    nodes[0].scrollIntoView?.({ block: "nearest" });
  } catch (_e) {}
  editor._snapAfter?.();
  editor._refreshActiveStates?.();
}

function buildTemplate(editor, strip, ui) {
  const btn = el("button", "pix-info-tpl");
  btn.type = "button";
  btn.title = "Insert a ready-made section (headings to fill in) where the cursor is";
  btn.appendChild(el("span", null, "Template"));
  btn.appendChild(el("small", null, "▾"));
  const menu = el("div", "pix-info-tmenu");
  menu.appendChild(el("div", "hint", "Add a section where the cursor is"));
  let saved = null;
  const close = () => { menu.classList.remove("open"); btn.classList.remove("on"); };
  ui.menuOpen = () => menu.classList.contains("open");
  ui.closeMenu = close;
  for (const st of STARTERS) {
    if (!st.h1) continue;
    const b = el("button");
    b.type = "button";
    const ic = maskIcon(st.icon);
    ic.style.color = st.color;
    b.appendChild(ic);
    b.appendChild(el("span", null, st.name));
    // Keep the body's focus and caret: the insert goes where it was.
    b.addEventListener("mousedown", (e) => e.preventDefault());
    b.addEventListener("click", () => {
      close();
      insertSection(editor, st, saved || bodyRange(editor));
      saved = null;
    });
    menu.appendChild(b);
  }
  btn.addEventListener("mousedown", (e) => {
    e.preventDefault();
    saved = bodyRange(editor);
  });
  btn.addEventListener("click", () => {
    if (ui.menuOpen()) { close(); return; }
    const sr = strip.getBoundingClientRect(), br = btn.getBoundingClientRect();
    menu.style.top = `${br.bottom - sr.top + 4}px`;
    menu.classList.add("open");
    btn.classList.add("on");
    // Under the button, but kept inside the strip: the panel clips its
    // overflow, and on a narrow window the button sits near the right edge
    // (measured: up to 110 px of the menu cut off at a 776 px panel).
    const maxLeft = Math.max(0, strip.clientWidth - menu.offsetWidth - 4);
    menu.style.left = `${Math.min(Math.max(0, br.left - sr.left), maxLeft)}px`;
  });
  // A press anywhere else closes it.
  ui.onDocDown = (e) => {
    if (!ui.menuOpen() || menu.contains(e.target) || btn.contains(e.target)) return;
    close();
  };
  document.addEventListener("pointerdown", ui.onDocDown, true);
  strip.appendChild(menu);
  return btn;
}

function buildStrip(editor, staged, ui) {
  const strip = el("div", "pix-info-strip");
  const row = el("div", "pix-info-srow");
  strip.appendChild(row);
  const markDirty = () => { editor._dirty = true; };

  row.appendChild(el("span", "pix-info-slab", "TITLE"));
  const input = el("input", "pix-info-sin");
  input.type = "text";
  input.maxLength = TITLE_MAX;
  input.value = staged.title;
  input.placeholder = "Button title";
  input.spellcheck = false;
  input.title = "The text on the button";
  input.addEventListener("input", () => {
    staged.title = input.value.replace(/[\r\n\t]+/g, " ");
    markDirty();
    paintPreview();
  });
  row.appendChild(input);

  row.appendChild(el("span", "pix-info-slab", "ICON"));
  const icb = el("button", "pix-info-sicb");
  icb.type = "button";
  icb.title = "Pick the button's icon";
  const icbIcon = maskIcon(iconOrDefault(staged.icon), 18);
  icb.appendChild(icbIcon);
  icb.appendChild(el("small", null, "▾"));
  row.appendChild(icb);

  row.appendChild(el("span", "pix-info-slab", "COLOUR"));
  const sw = el("div", "pix-info-sw");
  const swatches = [];
  for (const c of COLORS) {
    const b = el("button");
    b.type = "button";
    b.style.background = c;
    b.title = c;
    b.dataset.c = c;
    b.addEventListener("click", () => { staged.color = c; markDirty(); syncSwatches(); paintPreview(); });
    swatches.push(b);
    sw.appendChild(b);
  }
  const more = el("button", "pix-info-more");
  more.type = "button";
  more.title = "More colours";
  more.addEventListener("click", () => {
    openPixaromaCompactColorPickerPopup(more, {
      initialColor: staged.color,
      swatches: PIXAROMA_PALETTE.slice(0, 35),
      resetColor: "#f66744",
      onPick: (c) => {
        if (typeof c !== "string" || !/^#[0-9a-f]{6}$/i.test(c)) return;
        staged.color = c.toLowerCase();
        markDirty(); syncSwatches(); paintPreview();
      },
    });
  });
  sw.appendChild(more);
  row.appendChild(sw);
  row.appendChild(buildTemplate(editor, strip, ui));

  const pw = el("div", "pix-info-pw");
  const prev = el("span", "pix-info-prev");
  prev.title = "How the button will look";
  pw.appendChild(prev);
  row.appendChild(pw);

  const grid = el("div", "pix-info-igrid");
  const iconBtns = [];
  for (const id of ICONS) {
    const b = el("button");
    b.type = "button";
    b.title = id;
    b.dataset.id = id;
    b.appendChild(maskIcon(id));
    b.addEventListener("click", () => {
      staged.icon = id;
      markDirty();
      syncIcons();
      paintPreview();
      grid.classList.remove("open");
      icb.classList.remove("on");
    });
    iconBtns.push(b);
    grid.appendChild(b);
  }
  icb.addEventListener("click", () => {
    const open = !grid.classList.contains("open");
    grid.classList.toggle("open", open);
    icb.classList.toggle("on", open);
  });
  strip.appendChild(grid);

  function syncSwatches() {
    for (const b of swatches) b.classList.toggle("on", b.dataset.c === staged.color);
  }
  function syncIcons() {
    const id = iconOrDefault(staged.icon);
    for (const b of iconBtns) b.classList.toggle("on", b.dataset.id === id);
    icbIcon.style.setProperty("--i", `url("${iconUrl(id)}")`);
  }
  function paintPreview() {
    prev.innerHTML = "";
    prev.style.background = staged.color;
    prev.style.color = inkFor(staged.color);
    prev.appendChild(maskIcon(iconOrDefault(staged.icon)));
    if (staged.title) prev.appendChild(el("span", null, staged.title));
  }
  syncSwatches();
  syncIcons();
  paintPreview();
  return strip;
}

// The open callback is passed in by index.js, so this module and the reader
// never import each other.
export function openInfoEditor(node, opts = {}) {
  if (!node) return;
  // One editor per node (Vue Compat #2: trust isConnected, not the reference).
  if (node._noteEditor?._el?.isConnected) return;
  if (node._noteEditor && !node._noteEditor._el?.isConnected) {
    try { node._noteEditor._cleanup(); } catch (_e) {}
  }
  injectStripCSS();
  const cfg = JSON.parse(JSON.stringify(readCfg(node)));
  node._noteCfg = cfg;
  const staged = { ...cfg.info };
  const ui = {};   // the Template menu's handles (buildTemplate)

  const editor = new NoteEditor(node);
  node._noteEditor = editor;

  // Note's open() reconciles a saved page colour with node.bgcolor (its own
  // node is painted in it). An Info node is never painted in it, so show the
  // editor the saved colour for that one check and put node.bgcolor back:
  // otherwise the page colour would be dropped on every open.
  const savedBg = node.bgcolor;
  const pageBg = typeof cfg.backgroundColor === "string" && /^#[0-9a-f]{6}$/i.test(cfg.backgroundColor)
    ? cfg.backgroundColor : null;
  if (pageBg) node.bgcolor = pageBg;

  // Note's _keyBlock (window capture) takes Ctrl/Cmd+Z, Y, B, I and U for the
  // note body: pressed in the TITLE box they undid the NOTE's last edit and
  // moved the focus there (reproduced). Registered BEFORE editor.open(), so on
  // the same target and phase this runs first: for those keys typed in the
  // strip it stops Note's handler (and ComfyUI's), and the box's own undo /
  // redo still happens, because nothing calls preventDefault.
  const stripKeys = (e) => {
    // Esc closes the Template menu first, not the whole editor.
    if (e.key === "Escape" && ui.menuOpen?.()) {
      if (e.type === "keydown") ui.closeMenu();
      e.preventDefault();
      e.stopImmediatePropagation();
      return;
    }
    if (!(e.ctrlKey || e.metaKey) || !e.target?.closest?.(".pix-info-strip")) return;
    const k = (e.key || "").toLowerCase();
    if (k === "z" || k === "y" || k === "b" || k === "i" || k === "u") e.stopImmediatePropagation();
  };
  window.addEventListener("keydown", stripKeys, true);

  const origSave = editor.save;
  editor.save = function () {
    const oldInfo = readCfg(node).info;
    // Spread the CURRENT info first: the window size and text size are not
    // edited here, and must survive the save (withInfo in core.mjs).
    const info = {
      ...oldInfo,
      title: String(staged.title || "").slice(0, TITLE_MAX),
      // Kept as stored: an icon this pack does not know (a newer version
      // added it) must survive a save here. It is drawn as the Info icon.
      icon: staged.icon,
      color: staged.color,
    };
    this.cfg.info = info;
    // Note stamps its own node size into the cfg; Info's size lives on the node.
    const r = origSave.apply(this, arguments);
    if (oldInfo.title !== info.title || oldInfo.icon !== info.icon) refitToContent(node, oldInfo, info);
    node._pixInfoRaw = null;
    node._pixInfoRefresh?.();
    notifyGraphChanged();
    return r;
  };

  const origCleanup = editor._cleanup;
  let cleaned = false;
  editor._cleanup = function () {
    const r = origCleanup.apply(this, arguments);
    if (cleaned) return r;
    cleaned = true;
    window.removeEventListener("keydown", stripKeys, true);
    if (ui.onDocDown) document.removeEventListener("pointerdown", ui.onDocDown, true);
    node._pixInfoRaw = null;
    node._pixInfoRefresh?.();
    try { node.setDirtyCanvas?.(true, true); } catch (_e) {}
    if (opts.reopenReader && typeof opts.onReopen === "function" && node.graph) {
      setTimeout(() => opts.onReopen(node), 0);
    }
    return r;
  };

  try {
    editor.open();
  } catch (e) {
    window.removeEventListener("keydown", stripKeys, true);
    throw e;
  } finally {
    if (pageBg) node.bgcolor = savedBg;
  }

  // The strip goes under the editor's header; the title reads "Info Editor".
  try {
    const panel = editor._el?.querySelector(".pix-note-panel");
    const header = panel?.querySelector(".pix-note-header");
    if (panel && header) header.after(buildStrip(editor, staged, ui));
    const title = header?.querySelector(".pix-note-title");
    if (title) {
      for (const n of title.childNodes) {
        if (n.nodeType === 3 && /Note Editor/.test(n.nodeValue)) n.nodeValue = n.nodeValue.replace("Note Editor", "Info Editor");
      }
    }
  } catch (e) {
    console.warn("[Pixaroma Info] could not add the button strip", e);
  }
}
