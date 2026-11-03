// Prompt Pixaroma - the fullscreen tag library editor.
//
// Opens from the node's "Tags" button, filling the viewport like the other
// Pixaroma editors: a category sidebar on the left, tag rows on the right, with
// search, add, move-between-categories, export, and an import that resolves
// same-name clashes. It edits a WORKING copy of the library and pushes changes
// through commitLibrary (debounced persist + live notify to every node).

import { app } from "../../../scripts/app.js";
import { installGraphUndoGuard } from "../shared/graph_undo_guard.mjs";
import { pixAsset } from "../shared/api_url.mjs";
import { BRAND } from "../shared/utils.mjs";
import { followSpellcheck } from "../shared/spellcheck.mjs";
import {
  getLibrary, reloadLibrary, isSameAsStored, commitLibrary, flushLibrary, exportLibraryJSON, parseImport, applyImport,
  importCategories, subsetImport, isListTag, tagLines, catOf, sideOfCat, tagMode, catMode,
  reorderCategoryStep, reorderCategoryTo, canMoveCategory,
  TEXT_BUCKET, LIST_BUCKET, NAME_RE,
} from "./library.mjs";
import {
  MODES, MODE_LABEL, DEFAULT_MODE, hasPosition, listKey, catKey, cursorInfo, resetCursor,
  renameCursor, flushCursors,
} from "./cursors.mjs";

const PAL = ["#e0894b", "#5aa9e6", "#8e7bd6", "#5fbf8f", "#d76b98", "#c9a24b", "#6fb3b8"];
const MAX_IMPORT_BYTES = 8 * 1024 * 1024;
const ICON_BASE = "icons/ui/";
// Dragging a category row carries its SIDE in the MIME TYPE, because the type list is
// the only thing readable during dragover (getData is blocked until the drop). That is
// what lets a Text row refuse a List row on sight instead of accepting the drop and
// then explaining itself - see the drag wiring in mkCat.
const CAT_MIME = (side) => `application/x-pixaroma-prompt-cat-${side}`;
// The sidebar width the user dragged, remembered across opens in an UNREGISTERED
// setting (Vue Compat #20: it persists without being declared, like the library
// itself). Clamped on both write and read, so a hand-edited or stale value can never
// leave the category list unusably narrow or wide enough to bury the cards.
const SIDE_W_SETTING = "Pixaroma.Prompt.LibrarySidebar";
const SIDE_W_DEFAULT = 220, SIDE_W_MIN = 150, SIDE_W_MAX = 460;
const clampSideW = (n) => Math.max(SIDE_W_MIN, Math.min(SIDE_W_MAX, Math.round(Number(n) || 0) || SIDE_W_DEFAULT));

let _overlay = null;
let _node = null;
let _opts = null;
let _data = null;       // working copy
let _curCat = "All";
let _search = "";
let _undoGuardOff = null;
let _catMenu = null;
let _accent = BRAND;
// In-progress create-form values, kept alive across re-renders (clicking a sidebar
// category or typing in search rebuilds the form) so a typed OR prefilled name/text
// is never lost. Cleared on Create and on close. `kind` starts as a List when the
// text has 2+ lines (a saved multi-line selection is almost always a list) and stops
// following the text once the user clicks the switch (kindTouched).
function newDraft(text) {
  const t = text || "";
  // `cat` lives on the draft for the same reason name/text do: renderContent rebuilds
  // the form on every search keystroke and every sidebar click, and a chosen category
  // held only in a local would silently snap back to the bucket - so a tag you filed
  // under Lighting was created in Text with no warning. null = follow the sidebar.
  return { name: "", text: t, cat: null, kind: tagLines(t).length > 1 ? "list" : "text", kindTouched: false };
}
let _createDraft = newDraft();

function clone(d) {
  return {
    version: 1,
    categories: [...d.categories],
    listCats: [...(d.listCats || [])],
    catModes: { ...(d.catModes || {}) },
    tags: d.tags.map((t) => ({ ...t })),
  };
}
function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
function sanitizeName(n) { return String(n || "").replace(NAME_RE, ""); }
function colorOf(cat) {
  // The two buckets are not real categories - neutral grey, like the old Uncategorized.
  if (!cat || cat === TEXT_BUCKET || cat === LIST_BUCKET) return "#7a7a7a";
  const i = _data.categories.indexOf(cat);
  return PAL[(i < 0 ? 0 : i) % PAL.length];
}
function tagsIn(cat) { return _data.tags.filter((t) => catOf(t) === cat); }
// Which side a name sits on, against the WORKING copy (not the persisted library).
function sideOf(cat) { return sideOfCat(cat, _data); }
// Real categories on one side, in order.
function catsOnSide(side) { return _data.categories.filter((c) => sideOf(c) === side); }
// A side's bucket is listed only when a tag actually sits in it.
function bucketUsed(side) {
  return _data.tags.some((t) => !t.cat && (isListTag(t) ? "list" : "text") === side);
}
const bucketOf = (side) => (side === "list" ? LIST_BUCKET : TEXT_BUCKET);
// "Text" / "List" (and the legacy "Uncategorized") name buckets, never categories.
function isReservedName(v) {
  const k = String(v || "").trim().toLowerCase();
  return k === TEXT_BUCKET.toLowerCase() || k === LIST_BUCKET.toLowerCase() || k === "uncategorized";
}
// Add a category on a side (the List side is recorded in listCats).
function addCategory(name, side) {
  _data.categories.push(name);
  if (side === "list") _data.listCats.push(name);
}
function uniqueNameExcept(base, exceptTag) {
  let n = sanitizeName(base) || "tag";
  const taken = (x) => { const k = x.toLowerCase(); return _data.tags.some((t) => t !== exceptTag && t.name.toLowerCase() === k); };
  if (!taken(n)) return n;
  let i = 2; while (taken(n + "-" + i)) i++; return n + "-" + i;
}
function commit() { commitLibrary(_data); }

// ── applying a change ──────────────────────────────────────
// THERE IS DELIBERATELY NO UNDO. An earlier build had one (a whole-library snapshot
// stack, a change-signature gate, a Ctrl+Z handler and a floating Undo bar) and it was
// by a wide margin the largest source of bugs this editor has ever had: because it made
// "save the library" also mean "end the undo offer", every one of the twelve callers of
// commit() became a place undo could silently die, and the floating bar brought its own
// mouse-button, double-click, keyboard and z-order defects. Five review rounds kept
// finding fresh damage from the previous round's repairs to it.
//
// Anything that can lose something now ASKS FIRST (confirmDanger) and is then applied
// straight through. One question, one answer, no state living between them.
// Do NOT reintroduce undo without reading .claude/patterns/prompt.md #41.
function applyChange(mutate) {
  mutate();
  commit();
  render();
}

function injectCSS() {
  if (document.getElementById("pix-prled-css")) return;
  const s = document.createElement("style");
  s.id = "pix-prled-css";
  s.textContent = `
    .pix-prled { position:fixed; inset:0; z-index:10040; background:#181818; color:#e6e6e6;
      font:14px 'Segoe UI',system-ui,sans-serif; display:flex; flex-direction:column; }
    .pix-prled * { scrollbar-color:#3d3d3d #181818; scrollbar-width:thin; }
    .pix-prled ::-webkit-scrollbar { width:12px; height:12px; }
    .pix-prled ::-webkit-scrollbar-track { background:#181818; }
    .pix-prled ::-webkit-scrollbar-thumb { background:#3d3d3d; border-radius:6px; border:2px solid #181818; }
    .pix-prled ::-webkit-scrollbar-thumb:hover { background:#505050; }
    .pix-prled-bar { display:flex; align-items:center; gap:10px; background:#161616; border-bottom:1px solid #0e0e0e; padding:11px 16px; }
    .pix-prled-bar .ttl { font-weight:500; font-size:15px; color:#fff; display:flex; align-items:center; gap:8px; }
    .pix-prled-bar .ttl .cr { color:var(--acc); }
    .pix-prled-srch { width:320px; max-width:36vw; display:flex; align-items:center; gap:8px; background:#1d1d1d; border:1px solid #3a3a3a; border-radius:6px; padding:6px 10px; margin-left:8px; }
    .pix-prled-srch input { flex:1; background:transparent; border:0; outline:none; color:#e6e6e6; font:13px 'Segoe UI',sans-serif; }
    .pix-prled-srch .i { color:#767676; }
    .pix-prled-bar .priv { margin-left:6px; color:#767676; font-size:11.5px; }
    .pix-prled-bar .help { margin-left:auto; width:30px; height:30px; display:flex; align-items:center; justify-content:center; color:#a6a6a6; cursor:pointer; border-radius:6px; }
    .pix-prled-bar .help:hover { background:rgba(255,255,255,.08); color:#fff; }
    .pix-prled-bar .help .pix-prled-svg { width:17px; height:17px; }
    .pix-prled-bar .x { color:#a6a6a6; cursor:pointer; font-size:20px; line-height:1; padding:3px 9px; border-radius:6px; }
    .pix-prled-bar .x:hover { background:rgba(255,255,255,.08); color:#fff; }
    .pix-prled-main { flex:1; display:flex; min-height:0; }
    .pix-prled-side { width:220px; flex:none; background:#1b1b1b; border-right:1px solid #101010; padding:10px; overflow-y:auto; display:flex; flex-direction:column; gap:3px; }
    /* Drag the seam between the sidebar and the cards to widen the category list.
       A 6px strip sitting ON the border, so the border itself stays 1px. */
    .pix-prled-grip { flex:none; width:6px; margin-left:-3px; margin-right:-3px; z-index:2;
      cursor:col-resize; background:transparent; transition:background .12s; }
    .pix-prled-grip:hover, .pix-prled-grip.on { background:var(--acc); }
    /* While dragging the seam, nothing else may take the pointer or paint a selection. */
    .pix-prled.resizing { cursor:col-resize; user-select:none; }
    .pix-prled.resizing .pix-prled-main * { pointer-events:none; }
    .pix-prled.resizing .pix-prled-grip { pointer-events:auto; background:var(--acc); }
    /* Reordering a category by hand: the accent line shows which side of the row it
       lands on, and the row being carried dims. Same language as the Workflows folders. */
    .pix-prled-cat.ins-above { box-shadow: inset 0 2px 0 0 var(--acc); }
    .pix-prled-cat.ins-below { box-shadow: inset 0 -2px 0 0 var(--acc); }
    .pix-prled-cat.dragging-me { opacity:.45; }
    .pix-prled-side .lbl { font:600 10px 'Segoe UI',sans-serif; letter-spacing:.1em; text-transform:uppercase; color:#767676; padding:4px 8px 8px; }
    .pix-prled-cat { display:flex; align-items:center; gap:9px; padding:9px 10px; border-radius:7px; cursor:pointer; color:#c9c9c9; font:13px 'Segoe UI',sans-serif; }
    .pix-prled-cat:hover { background:rgba(255,255,255,.05); color:#fff; }
    .pix-prled-cat.on { background:color-mix(in srgb, var(--acc) 18%, transparent); color:#fff; }
    .pix-prled-cat .cd { width:11px; height:11px; border-radius:50%; flex:none; }
    .pix-prled-cat .nm { flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .pix-prled-cat .cnt { font-size:11px; color:#767676; }
    .pix-prled-cat.on .cnt { color:rgba(255,255,255,.7); }
    .pix-prled-cat .act { opacity:0; color:#767676; font-size:12px; padding:0 2px; }
    /* A category's actions used to be two hover-only glyphs, and the result was that
       nobody found them - the first report about this editor was "you cannot delete a
       category" when you could. One ⋯ that is ALWAYS on screen (dimmed until the row
       is hovered) is the fix; do not put these back behind hover. */
    .pix-prled-cat .act.more { opacity:.6; font-size:14px; line-height:1; padding:1px 5px; border-radius:4px; }
    .pix-prled-cat:hover .act { opacity:1; }
    .pix-prled-cat .act:hover { color:var(--acc); }
    .pix-prled-cat .act.more:hover { background:rgba(255,255,255,.1); color:#fff; }
    .pix-prled-cat.on .act.more { opacity:.85; }
    /* The two BUCKET rows (Text / List) are not categories - they are where tags with
       no category of their own are shown, and they vanish on their own once empty.
       They used to be drawn identically to a real category, so the obvious thing to
       try was to delete one, and nothing happened. Italic + dimmed says "different
       kind of row" at a glance; the tooltip and the ⋯ menu say the rest. */
    .pix-prled-cat.bucket .nm { font-style:italic; color:#9a9a9a; }
    /* ...but it must still brighten with the rest of the row on hover, or the bucket is
       the one sidebar label that stays grey while its background and count light up.
       Needs the same specificity as the .bucket rule to win. */
    .pix-prled-cat.bucket:hover .nm { color:#fff; }
    .pix-prled-cat.bucket.on .nm { color:#e0e0e0; }
    .pix-prled-cat .catinput { flex:1; min-width:0; background:#151515; border:1px solid var(--acc); border-radius:4px; color:#e6e6e6; font:12.5px monospace; padding:4px 6px; outline:none; }
    .pix-prled-newcat { margin-top:6px; padding-top:9px; border-top:1px solid #262626; }
    .pix-prled-btn { background:rgba(255,255,255,.05); border:1px solid #4a4a4a; color:#a6a6a6; border-radius:6px; padding:7px 13px; font:12.5px 'Segoe UI',sans-serif; cursor:pointer; display:inline-flex; gap:6px; align-items:center; transition:.12s; }
    .pix-prled-btn:hover { border-color:var(--acc); color:#fff; }
    .pix-prled-btn.pri { color:#fff; background:var(--acc); border-color:var(--acc); }
    .pix-prled-btn.pri:hover { filter:brightness(1.08); }
    .pix-prled-newcat .pix-prled-btn { width:100%; justify-content:center; }
    .pix-prled-content { flex:1; display:flex; flex-direction:column; min-width:0; background:#212121; }
    .pix-prled-chead { display:flex; align-items:center; gap:10px; padding:12px 16px; border-bottom:1px solid #171717; }
    /* min-width:0 + ellipsis, or a long category name shoves the Picks control and
       its start-over button past the right edge where they cannot be clicked
       (category names are free text - no length cap, no sanitising). */
    .pix-prled-chead .h { display:flex; align-items:center; gap:9px; font-size:15px; color:#fff; font-weight:500; min-width:0; overflow:hidden; }
    .pix-prled-chead .h > span:not(.cd) { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .pix-prled-chead .h .cd { width:12px; height:12px; border-radius:50%; }
    .pix-prled-chead .h .c { color:#767676; font-weight:400; font-size:12.5px; }
    /* the CREATE form: fill name + text in one place and hit Create (no hunting for
       a button on the far side of the editor) */
    /* wrap + a capped category pill, so a long category name cannot push the
       Create tag button off the row on a smaller window */
    .pix-prled-create { display:flex; align-items:center; flex-wrap:wrap; row-gap:8px; gap:8px; padding:11px 16px; background:#1e1e1e; border-bottom:1px solid #171717; }
    .pix-prled-create .ccat { max-width:220px; }
    .pix-prled-create input, .pix-prled-create textarea { background:#151515; border:1px solid #3a3a3a; border-radius:5px; color:#e6e6e6; font:12.5px monospace; padding:8px 9px; outline:none; height:36px; box-sizing:border-box; }
    .pix-prled-create input:focus, .pix-prled-create textarea:focus { border-color:var(--acc); }
    .pix-prled-create .cnm { width:170px; flex:none; color:var(--acc); }
    .pix-prled-create .ctx { flex:1; min-width:0; resize:none; line-height:1.5; white-space:pre-wrap; overflow-y:auto; }
    .pix-prled-create .ccat { flex:none; height:36px; }
    .pix-prled-create .ccat .car { font-size:9px; opacity:.85; margin-left:1px; }
    .pix-prled-create .cbtn { flex:none; background:var(--acc); border:none; color:#fff; border-radius:5px; padding:9px 15px; font:500 12.5px 'Segoe UI',sans-serif; cursor:pointer; height:36px; }
    .pix-prled-create .cbtn:hover { filter:brightness(1.08); }
    /* CARD GRID: tags as compact cards that fill the width in columns - each card
       keeps its name, text, and actions together (no reaching across the editor). */
    .pix-prled-grid { flex:1; overflow-y:auto; padding:13px 15px; display:grid;
      grid-template-columns:repeat(auto-fill, minmax(255px, 1fr)); gap:11px; align-content:start; }
    .pix-prled-card { background:#282828; border:1px solid #333; border-radius:9px; padding:10px; display:flex; flex-direction:column; gap:7px; min-width:0; }
    .pix-prled-card .ctop { display:flex; align-items:center; gap:6px; }
    .pix-prled-card .cnm { flex:1; min-width:0; background:#1d1d1d; border:1px solid #3a3a3a; border-radius:5px; color:var(--acc); font:13px monospace; padding:6px 8px; outline:none; }
    .pix-prled-card .cnm:focus { border-color:var(--acc); }
    .pix-prled-card .ctop .pix-prled-pill { flex:none; max-width:52%; }
    .pix-prled-card .ctx { background:#1d1d1d; border:1px solid #3a3a3a; border-radius:5px; color:#e0e0e0; font:11.5px/1.45 monospace; padding:7px 8px; outline:none; resize:vertical; min-height:66px; }
    .pix-prled-card .ctx:focus { border-color:var(--acc); }
    .pix-prled-card .cfoot { display:flex; gap:6px; }
    .pix-prled-svg { display:block; width:15px; height:15px; background-color:currentColor;
      -webkit-mask-repeat:no-repeat; mask-repeat:no-repeat; -webkit-mask-position:center; mask-position:center; -webkit-mask-size:contain; mask-size:contain; }
    .pix-prled-empty { color:#767676; font-size:13px; padding:24px; text-align:center; }
    /* Lighter gray (node-like), NOT the #1d1d1d of the editable inputs, so the
       category chip reads as a clickable label rather than a text field. */
    .pix-prled-pill { display:inline-flex; align-items:center; gap:7px; background:#3a3a3a; border:1px solid #4a4a4a; border-radius:20px; padding:6px 11px; font:12px 'Segoe UI',sans-serif; color:#d6d6d6; cursor:pointer; white-space:nowrap; overflow:hidden; }
    .pix-prled-pill:hover { border-color:var(--acc); color:#fff; }
    .pix-prled-pill .cd { width:10px; height:10px; border-radius:50%; flex:none; }
    .pix-prled-insert { flex:1; min-width:74px; height:30px; border-radius:5px; border:1px solid var(--acc); background:transparent;
      color:var(--acc); cursor:pointer; font:12px 'Segoe UI',sans-serif; display:flex; align-items:center; justify-content:center; gap:5px; }
    .pix-prled-insert:hover { background:var(--acc); color:#fff; }
    .pix-prled-insert .pix-prled-svg { width:13px; height:13px; }
    .pix-prled-insert.ok, .pix-prled-insert.ok:hover { background:#3ec371; border-color:#3ec371; color:#fff; }
    .pix-prled-ic { width:32px; height:30px; border-radius:5px; border:1px solid #4a4a4a; background:transparent; color:#a6a6a6; cursor:pointer; display:flex; align-items:center; justify-content:center; font-size:14px; }
    .pix-prled-ic:hover { border-color:var(--acc); color:#fff; }
    .pix-prled-ic.del:hover { background:#e2554a; border-color:#e2554a; color:#fff; }
    /* Text / List switch (card footer + create form). BOTH choices stay visible so it
       is obvious you can pick either; the active one is the accent (a single toggling
       button hid the alternative, and a second accent colour is not wanted). */
    .pix-prled-kindsw { flex:none; display:inline-flex; height:30px; border:1px solid #4a4a4a; border-radius:5px; overflow:hidden; }
    .pix-prled-kindsw:hover { border-color:var(--acc); }
    .pix-prled-kindsw button { background:transparent; border:0; color:#a6a6a6; padding:0 9px; cursor:pointer;
      font:11.5px 'Segoe UI',sans-serif; display:inline-flex; align-items:center; white-space:nowrap; }
    .pix-prled-kindsw button:hover { background:rgba(255,255,255,.07); color:#fff; }
    .pix-prled-kindsw button.on, .pix-prled-kindsw button.on:hover { background:var(--acc); color:#fff; }
    .pix-prled-card.islist { border-color:color-mix(in srgb, var(--acc) 42%, #333); }
    .pix-prled-card .cfoot { flex-wrap:wrap; row-gap:6px; }
    .pix-prled-create .pix-prled-kindsw { height:36px; }
    /* how a list / category picks: its own row, so the position has room to be shown */
    .pix-prled-moderow { display:flex; align-items:center; gap:7px; min-width:0; }
    .pix-prled-moderow .cap { flex:none; color:#767676; font:600 9.5px 'Segoe UI',sans-serif; letter-spacing:.09em; text-transform:uppercase; }
    .pix-prled-mode { flex:none; height:26px; padding:0 9px; border-radius:5px; border:1px solid #4a4a4a; background:transparent;
      color:#a6a6a6; cursor:pointer; font:11.5px 'Segoe UI',sans-serif; display:inline-flex; align-items:center; gap:6px; white-space:nowrap; }
    .pix-prled-mode:hover { border-color:var(--acc); color:#fff; }
    .pix-prled-mode.set { border-color:var(--acc); color:var(--acc); }
    .pix-prled-mode .car { font-size:9px; opacity:.85; }
    .pix-prled-moderow .pos { flex:1; min-width:0; text-align:right; color:#767676; font-size:11px;
      overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .pix-prled-moderow .rst { flex:none; width:24px; height:24px; border-radius:5px; border:1px solid #4a4a4a;
      background:transparent; color:#a6a6a6; cursor:pointer; font-size:12px; line-height:1; display:none;
      align-items:center; justify-content:center; }
    .pix-prled-moderow.on .rst { display:flex; }
    .pix-prled-moderow .rst:hover { border-color:var(--acc); color:#fff; }
    .pix-prled-menu .mi.on { color:var(--acc); }
    .pix-prled-chead .pix-prled-moderow { margin-left:auto; flex:0 0 auto; }
    .pix-prled-chead .pix-prled-moderow .pos { flex:0 0 auto; }
    /* import preview: which categories from the file to bring in */
    .pix-prled-pick { display:flex; flex-direction:column; gap:6px; max-height:42vh; overflow-y:auto; padding:2px 16px 8px; }
    .pix-prled-pick .row { display:flex; align-items:center; gap:10px; background:#262626; border:1px solid #333;
      border-radius:8px; padding:9px 12px; cursor:pointer; }
    .pix-prled-pick .row:hover { border-color:var(--acc); }
    .pix-prled-pick .row input { accent-color:var(--acc); width:15px; height:15px; cursor:pointer; flex:none; }
    .pix-prled-pick .row .cd { width:10px; height:10px; border-radius:50%; flex:none; }
    .pix-prled-pick .row .nm { flex:1; min-width:0; color:#fff; font:13px 'Segoe UI',sans-serif; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .pix-prled-pick .row .cnt { color:#a6a6a6; font-size:11.5px; flex:none; }
    .pix-prled-mfoot { display:flex; align-items:center; gap:9px; padding:2px 16px 16px; }
    .pix-prled-mfoot .push { margin-left:auto; }
    .pix-prled-mlink { background:none; border:0; color:var(--acc); font:12px 'Segoe UI',sans-serif; cursor:pointer; padding:2px 4px; }
    .pix-prled-mlink:hover { text-decoration:underline; }
    .pix-prled-menu .mrow { display:flex; align-items:center; gap:9px; }
    .pix-prled-menu .mrow .nm { flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .pix-prled-menu .mrow .cnt { color:#767676; font-size:11px; flex:none; }
    .pix-prled-menu .mi.dim { opacity:.45; cursor:default; }
    .pix-prled-menu .mi.dim:hover { background:none; color:#cfcfcf; }
    .pix-prled-menu .msep { height:1px; background:#2a2a2a; margin:4px 2px; }
    .pix-prled-menu .mhead { padding:4px 10px 5px; font:600 9.5px 'Segoe UI',sans-serif; letter-spacing:.09em; text-transform:uppercase; color:#767676; }
    .pix-prled-menu .mnote { padding:0 10px 7px; font:11.5px/1.45 'Segoe UI',sans-serif; color:#8f8f8f; white-space:normal; }
    .pix-prled-foot { display:flex; align-items:center; gap:9px; padding:10px 16px; border-top:1px solid #0e0e0e; background:#161616; }
    .pix-prled-foot .push { margin-left:auto; }
    /* max-height + scroll so a library with many categories can't push the menu (this
       one AND the category picker) off the top or bottom of the screen. */
    .pix-prled-menu { position:fixed; z-index:10050; background:#1d1d1d; border:1px solid #4a4a4a; border-radius:7px; padding:5px; box-shadow:0 12px 30px rgba(0,0,0,.6); min-width:170px; max-height:min(60vh,520px); overflow-y:auto; }
    .pix-prled-menu .mi { display:flex; align-items:center; gap:9px; padding:7px 10px; border-radius:5px; cursor:pointer; font:12.5px 'Segoe UI',sans-serif; color:#cfcfcf; }
    .pix-prled-menu .mi:hover { background:rgba(255,255,255,.06); color:#fff; }
    .pix-prled-menu .mi .cd { width:10px; height:10px; border-radius:50%; }
    .pix-prled-menu .mi.newc { border-top:1px solid #2a2a2a; margin-top:4px; padding-top:8px; color:var(--acc); }
    .pix-prled-menu input { width:100%; background:#151515; border:1px solid #4a4a4a; border-radius:4px; color:#e6e6e6; font:12px monospace; padding:6px 8px; outline:none; margin-top:5px; }
    .pix-prled-modal { position:absolute; inset:0; background:rgba(0,0,0,.6); display:flex; align-items:center; justify-content:center; z-index:10045; }
    .pix-prled-mcard { background:#202020; border:1px solid #0e0e0e; border-radius:12px; width:460px; max-width:92vw; box-shadow:0 20px 60px rgba(0,0,0,.6); overflow:hidden; }
    .pix-prled-mcard .mh { padding:14px 16px; border-bottom:1px solid #171717; font:500 15px 'Segoe UI',sans-serif; color:#fff; }
    .pix-prled-mcard .mb { padding:14px 16px; color:#a6a6a6; font-size:13px; line-height:1.6; }
    .pix-prled-mcard .mb b { color:#fff; font-weight:500; }
    .pix-prled-mcard .conf { background:#1a1a1a; border:1px solid #2a2a2a; border-radius:7px; padding:8px 11px; margin:9px 0;
      font:12px monospace; color:#e0894b; max-height:110px; overflow-y:auto; white-space:pre-wrap; word-break:break-word; }
    .pix-prled-opts { display:flex; flex-direction:column; gap:8px; padding:2px 16px 16px; }
    .pix-prled-opt { display:flex; align-items:center; gap:11px; background:#262626; border:1px solid #333; border-radius:8px; padding:11px 13px; cursor:pointer; transition:.12s; }
    .pix-prled-opt:hover, .pix-prled-opt.rec { border-color:var(--acc); }
    .pix-prled-opt .oic { width:30px; height:30px; border-radius:7px; background:color-mix(in srgb, var(--acc) 16%, transparent); color:var(--acc); display:flex; align-items:center; justify-content:center; font-size:15px; flex:none; }
    .pix-prled-opt .t { font:500 13px 'Segoe UI',sans-serif; color:#fff; }
    .pix-prled-opt .t small { display:block; color:#a6a6a6; font-weight:400; font-size:11.5px; margin-top:1px; }
    .pix-prled-opt .rtag { margin-left:auto; font-size:10px; color:#3ec371; border:1px solid rgba(62,195,113,.4); border-radius:12px; padding:1px 8px; }
    .pix-prled-help-card { width:560px; }
    .pix-prled-help-card .mb { max-height:60vh; overflow-y:auto; }
    .pix-prled-help-card .mb p { margin:0 0 11px; }
    .pix-prled-help-card .mb p:last-child { margin-bottom:0; }
    .pix-prled-help-foot { display:flex; justify-content:flex-end; padding:0 16px 16px; }
    /* A menu row that destroys something must never look like the ordinary ones. */
    .pix-prled-menu .mi.danger { color:#e2554a; }
    .pix-prled-menu .mi.danger:hover { background:rgba(226,85,74,.15); color:#ff8d81; }
    /* This hint carries the COUNT of what is about to be lost, so it has to be the
       readable one - at .7 alpha it composited to about 2.8:1, dimmer than the neutral
       hint beside it. */
    .pix-prled-menu .mi.danger .cnt { color:#d98079; }
    /* The button that carries the consequence must not read WEAKER than the Cancel
       next to it: a near-invisible border made it the quieter of the two. */
    .pix-prled-btn.danger { border-color:#e2554a; color:#ff8378; background:rgba(226,85,74,.12); }
    .pix-prled-btn.danger:hover { background:#e2554a; border-color:#e2554a; color:#fff; }
  `;
  document.head.appendChild(s);
}

function hideCatMenu() { if (_catMenu) { _catMenu.remove(); _catMenu = null; } }

// Clamp a body-appended popup to the viewport, flipping above the anchor when there is
// no room below. Call it again if the menu GROWS after it was first placed.
function placeMenu(menu, anchor) {
  const r = anchor.getBoundingClientRect();
  menu.style.left = Math.max(8, Math.min(r.left, window.innerWidth - menu.offsetWidth - 8)) + "px";
  const below = window.innerHeight - r.bottom;
  menu.style.top = (below < menu.offsetHeight + 8
    ? Math.max(8, r.top - menu.offsetHeight - 6)
    : r.bottom + 4) + "px";
}

// Category picker for ONE side: that side's categories + its bucket + a New-category
// row (which creates on that side), calling onPick(catValue) ("" = the bucket).
// Does NOT re-render - the caller decides (so the create form keeps its typed values).
function openCategoryMenu(anchor, onPick, side) {
  hideCatMenu();
  const sd = side === "list" ? "list" : "text";
  const menu = document.createElement("div");
  menu.className = "pix-prled-menu";
  for (const c of [...catsOnSide(sd), bucketOf(sd)]) {
    const mi = document.createElement("div");
    mi.className = "mi";
    mi.innerHTML = `<span class="cd" style="background:${colorOf(c)}"></span>${esc(c)}`;
    mi.addEventListener("click", () => { hideCatMenu(); onPick(c === bucketOf(sd) ? "" : c); });
    menu.appendChild(mi);
  }
  const nc = document.createElement("div");
  nc.className = "mi newc";
  nc.innerHTML = `<span>＋</span> New ${sd === "list" ? "list " : ""}category`;
  const inp = document.createElement("input");
  inp.placeholder = "name"; inp.style.display = "none";
  nc.addEventListener("click", () => {
    inp.style.display = "block";
    inp.focus();
    // The menu was positioned against its pre-growth height, so on a short window the
    // revealed field could sit below the bottom edge with the user typing blind.
    placeMenu(menu, anchor);
  });
  inp.addEventListener("keydown", (e) => {
    e.stopPropagation();
    if (e.key === "Enter") {
      const v = inp.value.trim();
      // Enter on an empty box used to just close the menu, which from the bucket's
      // "Put them all in a category..." reads as a broken button (onPick never fires, so
      // the caller's own "pick a real category" message never runs either).
      if (!v) { toast("info", "Type a name for the new category."); inp.focus(); return; }
      // A bucket name is NOT a real category: typing it just files the tag in that
      // bucket (never push it -> a phantom duplicate sidebar row).
      const reserved = v && isReservedName(v);
      // If it case-collides with an existing category, use the EXISTING (canonical)
      // one - never assign the tag a wrong-case category that no sidebar row matches.
      const existing = (v && !reserved) ? _data.categories.find((c) => c.toLowerCase() === v.toLowerCase()) : null;
      if (v && !reserved && !existing) {
        addCategory(v, sd); commit();
        // Refresh the SIDEBAR only. A full render() would rebuild the create form and
        // throw away whatever the user has typed into it (which is precisely why this
        // picker does not re-render), but without this the new category is saved and
        // yet missing from the sidebar, its counts and the export menu until something
        // unrelated happens to re-render.
        const side = _overlay && _overlay.querySelector(".pix-prled-side");
        if (side) renderSidebar(side);
      }
      hideCatMenu();
      // An existing name keeps ITS side, so only pick it when the sides agree -
      // otherwise the tag would land in a category that cannot hold it.
      if (v) onPick(reserved || (existing && sideOf(existing) !== sd) ? "" : (existing || v));
    }
    if (e.key === "Escape") hideCatMenu();
  });
  menu.append(nc, inp);
  _overlay.appendChild(menu);
  placeMenu(menu, anchor);
  _catMenu = menu;
}
// Moving an existing tag between categories: only its OWN side is offered, since a
// category holds one kind. Persist + re-render.
function openCatMenu(tag, anchor) {
  openCategoryMenu(anchor, (c) => { tag.cat = c; commit(); render(); }, isListTag(tag) ? "list" : "text");
}
document.addEventListener("mousedown", (e) => {
  if (_catMenu && !_catMenu.contains(e.target) && !e.target.closest(".pix-prled-pill")) hideCatMenu();
}, true);

// ── render ─────────────────────────────────────────────────────────────
// The Text / List switch, shared by the cards and the create form. Both segments are
// always on screen so the choice is visible without clicking anything; `paint(isList,
// count)` sets the active one and, for a List, shows how many options it holds.
function makeKindSwitch(onPick) {
  const sw = document.createElement("div");
  sw.className = "pix-prled-kindsw";
  const bText = document.createElement("button"); bText.type = "button"; bText.textContent = "Text";
  bText.title = "Text: one piece of text, and @name drops in all of it";
  const bList = document.createElement("button"); bList.type = "button"; bList.textContent = "List";
  bList.title = "List: one option per line, and #name picks one at random every run";
  sw.append(bText, bList);
  bText.addEventListener("click", (e) => { e.stopPropagation(); onPick(false); });
  bList.addEventListener("click", (e) => { e.stopPropagation(); onPick(true); });
  return {
    el: sw,
    paint(isList, count) {
      bText.classList.toggle("on", !isList);
      bList.classList.toggle("on", !!isList);
      bList.textContent = isList && count != null ? `List · ${count}` : "List";
    },
  };
}

// Pick how a list / category chooses: Random, Shuffle (all of them before any
// repeat) or In order. Reuses the dark menu, so Escape + outside-click close it.
const MODE_HINT = {
  random: "any one, every time",
  shuffle: "all of them before any repeat",
  order: "1, 2, 3 and around again",
};
function openModeMenu(anchor, current, onPick) {
  hideCatMenu();
  const menu = document.createElement("div");
  menu.className = "pix-prled-menu";
  menu.style.minWidth = "240px";
  for (const m of MODES) {
    const mi = document.createElement("div");
    mi.className = "mi mrow" + (m === current ? " on" : "");
    mi.innerHTML = `<span class="nm">${MODE_LABEL[m]}</span><span class="cnt">${MODE_HINT[m]}</span>`;
    mi.addEventListener("click", () => { hideCatMenu(); onPick(m); });
    menu.appendChild(mi);
  }
  _overlay.appendChild(menu);
  placeMenu(menu, anchor);
  _catMenu = menu;
}
// The "Random ▾ · next 3 of 12 · ↺" row shared by a List card and a category header.
// getMode/setMode read+write wherever the mode lives; key/len drive the position text.
function makeModeRow({ getMode, setMode, key, len, what }) {
  const row = document.createElement("div");
  row.className = "pix-prled-moderow";
  // Without a caption the bare "Random ▾" reads as decoration and gets missed.
  const cap = document.createElement("span");
  cap.className = "cap"; cap.textContent = "Picks";
  const btn = document.createElement("button");
  btn.className = "pix-prled-mode";
  const pos = document.createElement("span");
  pos.className = "pos";
  const rst = document.createElement("button");
  rst.className = "rst"; rst.textContent = "↺";
  const paint = () => {
    const m = getMode();
    // Accent = "not the default", so a list that behaves unusually stands out in the
    // grid. Whether it has a POSITION is a different question (Random never does).
    btn.classList.toggle("set", m !== DEFAULT_MODE);
    btn.innerHTML = `<span>${MODE_LABEL[m]}</span><span class="car">▾</span>`;
    btn.title = `How this ${what} picks: ${MODE_LABEL[m]} - ${MODE_HINT[m]}`;
    row.classList.toggle("on", hasPosition(m));
    // On Random there is no position to show, so say what Random DOES - that is the
    // line that tells you the control is worth clicking.
    pos.textContent = cursorInfo(key(), len(), m) || MODE_HINT[m];
    rst.title = `Start this ${what} over`;
  };
  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    openModeMenu(btn, getMode(), (m) => { setMode(m); commit(); paint(); });
  });
  rst.addEventListener("click", (e) => {
    e.stopPropagation();
    resetCursor(key());
    paint();
    toast("info", `Started that ${what} over`);
  });
  row.append(cap, btn, pos, rst);
  paint();
  return { el: row, paint };
}

function makeCard(tag) {
  const card = document.createElement("div");
  card.className = "pix-prled-card";
  const top = document.createElement("div"); top.className = "ctop";
  const nm = document.createElement("input");
  nm.className = "cnm"; nm.value = tag.name; nm.spellcheck = false;
  nm.addEventListener("input", () => {
    const cleaned = sanitizeName(nm.value);
    if (cleaned !== nm.value) {
      // Writing the field back moves the caret to the end, so typing an illegal
      // character mid-name teleported the cursor and the rest of the typing landed in
      // the wrong place. Put it back where it was, minus what was stripped.
      const at = nm.selectionStart;
      const dropped = nm.value.length - cleaned.length;
      nm.value = cleaned;
      const p = Math.max(0, (at == null ? cleaned.length : at) - dropped);
      try { nm.setSelectionRange(p, p); } catch { /* detached / unsupported */ }
    }
    // An invalid name must NEVER reach the working copy, not just never be committed.
    // It used to be assigned unconditionally and only the commit() was gated, so while
    // a name field sat empty (or duplicated) the tag was invalid IN `_data` - and the
    // very next commit() from ANY other control (deleting another tag, editing another
    // card, renaming a category) pushed `_data` through normalize(), which DROPS an
    // empty-named tag. The tag and its text vanished from the store and from every
    // node's highlighting on the spot; closing the editor resurrected it under the
    // made-up name "tag", so the original name was gone for good. Verified live
    // 2026-07-26 (store 30 vs grid 31).
    // The field keeps showing whatever was typed; the model keeps the last good name
    // until a valid one is typed or blur settles it.
    const dup = !!cleaned && _data.tags.some((o) => o !== tag && o.name.toLowerCase() === cleaned.toLowerCase());
    if (cleaned && !dup) {
      tag.name = cleaned;
      // The store is renamed on THIS keystroke, so the position has to move now too.
      // Deferring it to blur left a window where a run looked up the new name, found
      // nothing and started a fresh sequence, which blur then overwrote.
      if (nameAtFocus.v && nameAtFocus.v !== tag.name) {
        try { renameCursor(listKey(nameAtFocus.v), listKey(tag.name)); } catch { /* ignore */ }
        nameAtFocus.v = tag.name;
      }
      commit();
    }
    paintKind(); // the kind button's tooltip quotes the tag name
  });
  // Tracks the name the position is currently filed under, so a rename can carry it
  // (see the input + blur handlers). Storage writes are debounced, so moving it per
  // keystroke costs nothing.
  const nameAtFocus = { v: tag.name };
  // SEPARATE from nameAtFocus, which the input handler moves on every valid keystroke
  // because it tracks where the sequence position is currently filed. Escape needs the
  // name as it was when the field was entered, which nothing else may touch.
  let nameOnEntry = tag.name;
  nm.addEventListener("focus", () => { nameAtFocus.v = tag.name; nameOnEntry = tag.name; });
  // Escape must ABANDON what was typed. onKey is capture-phase, so without a handle it
  // fell through to the generic `active.blur()`, which runs the blur listener below and
  // COMMITS: typing a name that is already taken and pressing Escape renamed the tag to
  // `thatname-2` - a name nobody typed. Putting the
  // original name back first makes the blur a no-op by its own equality check.
  nm._pixCancel = () => {
    // The input handler applies and COMMITS a valid rename on every keystroke, so by
    // the time Escape arrives `tag.name` is already the typed name. Repainting the
    // field alone left the rename standing - Escape only reverted the invalid case,
    // while the sibling category rename reverts properly. Put the model back too.
    const back = nameOnEntry;
    if (back && back !== tag.name && !_data.tags.some((o) => o !== tag && o.name.toLowerCase() === back.toLowerCase())) {
      try { renameCursor(listKey(tag.name), listKey(back)); } catch { /* ignore */ }
      tag.name = back;
      nm.value = back;
      commit();
      nm.blur();
      render();          // the card's Insert / bin / switch labels all quote the name
      return;
    }
    nm.value = tag.name;
    nm.blur();
  };
  nm.addEventListener("blur", () => {
    // Left EMPTY: the tag keeps the name it already had, and the field shows it again.
    // uniqueNameExcept("") invents "tag" (or "tag-2"), which threw away a name the user
    // never asked to change just because they cleared the box to retype and clicked away.
    if (!sanitizeName(nm.value)) { nm.value = tag.name; return; }
    const u = uniqueNameExcept(nm.value, tag);
    // Nothing changed (the usual case - you clicked into the box and back out, or the
    // input handler already applied a valid rename). Do NOT commit: commit() is what
    // a real change; committing an identical library is pointless work on every
    // focus-and-leave. Same shape as commitRename's no-op guard.
    if (u === tag.name) { if (nm.value !== u) nm.value = u; return; }
    tag.name = u; nm.value = u;
    if (nameAtFocus.v && nameAtFocus.v !== tag.name) {
      try { renameCursor(listKey(nameAtFocus.v), listKey(tag.name)); } catch { /* ignore */ }
      nameAtFocus.v = tag.name;
    }
    commit();
  });
  nm.addEventListener("keydown", (e) => e.stopPropagation());
  const cc = catOf(tag);
  const pill = document.createElement("button");
  pill.className = "pix-prled-pill"; pill.title = "Move to another category";
  pill.innerHTML = `<span class="cd" style="background:${colorOf(cc)}"></span><span>${esc(cc)}</span>`;
  pill.addEventListener("click", (e) => { e.stopPropagation(); openCatMenu(tag, pill); });
  top.append(nm, pill);
  const tx = document.createElement("textarea");
  tx.className = "ctx"; tx.value = tag.text; followSpellcheck(tx); tx.rows = 3;
  tx.addEventListener("input", () => { tag.text = tx.value; commit(); paintKind(); });
  tx.addEventListener("keydown", (e) => e.stopPropagation());
  const foot = document.createElement("div"); foot.className = "cfoot";
  // Declared up here (not beside its listener below) so paintKind can keep its tooltip
  // on the right noun - a List card's bin used to say "tag" while the undo label for
  // the same click correctly said "Deleted #name".
  const del = document.createElement("button");
  const ins = document.createElement("button");
  ins.className = "pix-prled-insert";
  ins.innerHTML = `<span class="lbl">Insert</span>`;
  ins.addEventListener("click", () => {
    // A List card inserts #name (rolls one line); a snippet inserts @name.
    _opts?.onInsert?.(tag.name, isListTag(tag) ? "#" : "@");
    ins.classList.add("ok");
    const l = ins.querySelector(".lbl"); if (l) l.textContent = "Inserted ✓";
    setTimeout(() => { ins.classList.remove("ok"); const ll = ins.querySelector(".lbl"); if (ll) ll.textContent = "Insert"; }, 850);
  });
  // Text <-> List. The stored kind is cosmetic + convenience (the SYMBOL in the
  // prompt is what actually decides at expand time), so flipping it can never break
  // an existing prompt: @name keeps giving the whole block either way.
  const kindSw = makeKindSwitch((toList) => {
    if (isListTag(tag) === !!toList) return;
    const side = toList ? "list" : "text";
    const bucket = bucketOf(side);
    // A category belongs to ONE side, so a flipped tag cannot stay in it: it goes to
    // its new side's bucket, where the user can file it from the category pill.
    const from = tag.cat && sideOf(tag.cat) !== side ? tag.cat : "";
    const flip = () => applyChange(() => {
      if (toList) tag.kind = "list"; else delete tag.kind;
      if (from) tag.cat = "";
    });
    // Flipping OUT of a category throws that filing away, and switching straight back
    // does not restore it (the tag lands in the other bucket, not where it came from).
    // With no undo, that was the one place left in the editor that could lose something
    // on a single unconfirmed click - so it asks, but only when there is something to
    // lose. A tag already sitting in a bucket just flips.
    if (!from) { flip(); return; }
    confirmDanger({
      title: `Move ${esc(tag.name)} out of ${esc(from)}?`,
      lead: `A category holds one kind, so making this a <b>${toList ? "List" : "Text"}</b> tag takes it out of ` +
        `<b>${esc(from)}</b> and puts it in <b>${esc(bucket)}</b>, ready to file somewhere else. ` +
        `Switching back will not return it to ${esc(from)}.`,
      confirmLabel: `Make it a ${toList ? "List" : "Text"} tag`,
      onConfirm: () => {
        flip();
        toast("info", `${toList ? "#" : "@"}${tag.name} moved to ${bucket}`);
      },
    });
  });
  // Only a List picks between things, so only a List needs a mode row.
  const modeRow = makeModeRow({
    getMode: () => tagMode(tag),
    setMode: (m) => { if (m === DEFAULT_MODE) delete tag.mode; else tag.mode = m; },
    key: () => listKey(tag.name),
    len: () => tagLines(tag.text).length,
    what: "list",
  });
  function paintKind() {
    const list = isListTag(tag);
    card.classList.toggle("islist", list);
    kindSw.paint(list, tagLines(tag.text).length);
    tx.placeholder = list ? "one option per line" : "what it expands to - the full prompt text";
    ins.title = list ? "Insert #" + tag.name + " into your prompt (one of its options each run)" : "Insert @" + tag.name + " into your prompt";
    del.title = `Delete this ${list ? "list" : "tag"}`;
    modeRow.el.style.display = list ? "flex" : "none";
    if (list) modeRow.paint();
  }
  paintKind();
  del.className = "pix-prled-ic del";
  del.innerHTML = `<span class="pix-prled-svg" style="-webkit-mask-image:url(${pixAsset(ICON_BASE + "delete.svg")});mask-image:url(${pixAsset(ICON_BASE + "delete.svg")})"></span>`;
  // Asks first, and shows the tag's own text in the question so you can see whether it
  // is the one you meant. There is no undo behind it.
  del.addEventListener("click", () => {
    const list = isListTag(tag);
    const sym = list ? "#" : "@";
    const body = (tag.text || "").trim();
    confirmDanger({
      title: `Delete ${sym}${tag.name}?`,
      // Show what is actually in it. For one tag this is the whole point of asking:
      // you can see at a glance whether it is the one you meant.
      lead: `This deletes the ${list ? "list" : "tag"} <b>${esc(sym + tag.name)}</b>` +
        (body ? ` and what it holds:` : `, which is empty.`),
      listing: body ? (body.length > 400 ? body.slice(0, 400) + " …" : body) : "",
      confirmLabel: "Delete it",
      onConfirm: () => applyChange(() => {
        const i = _data.tags.indexOf(tag);
        if (i > -1) _data.tags.splice(i, 1);
        // Drop its position too, or a NEW list later given the same name inherits the
        // dead one's half-drained deck (deleteCat already does this for a category).
        try { resetCursor(listKey(tag.name)); } catch { /* ignore */ }
      }),
    });
  });
  foot.append(ins, kindSw.el, del);
  card.append(top, tx, modeRow.el, foot);
  return card;
}

function renderSidebar(sideEl) {
  sideEl.innerHTML = "";
  // `menu`: null (All tags) | "cat" (a real category) | "bucket" (Text / List, the
  // holding rows for tags with no category - NOT categories, see openBucketActions).
  const mkCat = (label, color, count, key, menu) => {
    const bucket = menu === "bucket";
    const r = document.createElement("div");
    r.className = "pix-prled-cat" + (_curCat === key ? " on" : "") + (bucket ? " bucket" : "");
    if (bucket) {
      r.title = `Not a category: it is where ${key === LIST_BUCKET ? "lists" : "tags"} with no category of their own are shown. ` +
        `It disappears once it is empty.`;
    }
    if (menu === "cat") r.title = "Drag to move it up or down the list";
    r.innerHTML = (color ? `<span class="cd" style="background:${color}"></span>` : `<span style="width:11px"></span>`) +
      `<span class="nm">${esc(label)}</span>` +
      (menu ? `<span class="act more" title="${bucket ? "What this row is, and what you can do with it" : "Move, rename, export or delete this category"}">⋯</span>` : "") +
      `<span class="cnt">${count}</span>`;
    r.addEventListener("click", (e) => {
      if (e.target.classList.contains("more")) {
        e.stopPropagation();
        if (bucket) openBucketActions(key, e.target); else openCatActions(r, key, e.target);
        return;
      }
      if (_curCat !== key) {
        _curCat = key;
        // Picking a category in the sidebar SAYS what you are about to make, so the
        // create form must follow it again. `kindTouched` was being carried across a
        // Create and never cleared, so after making one List tag the form stopped
        // following the sidebar and every later tag landed in a bucket instead of the
        // category you had selected. (Third time this exact failure has been fixed.)
        _createDraft.kindTouched = false;
      }
      render();
    });
    // Right-click the row opens the same menu - it is the first place people reach.
    if (menu) {
      r.addEventListener("contextmenu", (e) => {
        // Not over the rename field. startRenameCat puts a real <input> INSIDE this row,
        // and category names are free text people paste into - swallowing the browser's
        // own menu there took away the only way to paste one.
        if (e.target.closest("input, textarea")) return;
        e.preventDefault(); e.stopPropagation();
        const anchor = r.querySelector(".more") || r;
        if (bucket) openBucketActions(key, anchor); else openCatActions(r, key, anchor);
      });
    }
    // ── drag to reorder (real categories only) ──
    // A bucket is not stored anywhere, and "All tags" is not a category, so neither can
    // be carried or dropped on. Same gesture as the Workflows folder list.
    if (menu === "cat") {
      const mime = CAT_MIME(sideOf(key));
      const carries = (e) => !!e.dataTransfer && [...e.dataTransfer.types].includes(mime);
      const dropAbove = (e) => {
        const box = r.getBoundingClientRect();
        return (e.clientY - box.top) < box.height / 2;
      };
      const clearMarks = () => r.classList.remove("ins-above", "ins-below");
      r.draggable = true;
      r.addEventListener("dragstart", (e) => {
        // Mid-rename, or a grab that started on the ⋯ : neither is a reorder gesture,
        // and letting the drag win would take the rename field's text selection away.
        // BELT: this target test is NOT trusted on its own. Node UI convention #11
        // records that with draggable on the ROW the browser fires dragstart with
        // e.target set to the row itself, in which case closest() can never match and
        // this line does nothing. The real protection is startRenameCat turning
        // draggable OFF for the duration of the rename, which is correct whichever
        // element the browser reports. Keep BOTH - they cover different builds.
        if (e.target.closest("input, textarea, .act")) { e.preventDefault(); return; }
        // BRACES: a rename field anywhere in this row means the row is being edited,
        // regardless of where the drag was reported from.
        if (r.querySelector("input, textarea")) { e.preventDefault(); return; }
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData(mime, key);
        e.dataTransfer.setData("text/plain", key);   // some browsers refuse a drag with no text/plain
        r.classList.add("dragging-me");
      });
      r.addEventListener("dragend", () => {
        r.classList.remove("dragging-me");
        // A drag released over nothing never reaches a row's drop handler, so clear any
        // line still showing anywhere in the sidebar rather than only on this row.
        for (const el of sideEl.querySelectorAll(".ins-above, .ins-below")) el.classList.remove("ins-above", "ins-below");
      });
      r.addEventListener("dragover", (e) => {
        // NOT preventing the default is what makes the browser show "you cannot drop
        // here" over the other block. A category belongs to one side, and carrying it
        // across would clear the category off every tag in it.
        if (!carries(e)) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
        const above = dropAbove(e);
        r.classList.toggle("ins-above", above);
        r.classList.toggle("ins-below", !above);
      });
      r.addEventListener("dragleave", (e) => {
        // The row has child spans (dot, name, ⋯, count). Crossing onto one fires
        // dragleave on the row although the cursor never left it, so the line flickered.
        if (e.relatedTarget && r.contains(e.relatedTarget)) return;
        clearMarks();
      });
      r.addEventListener("drop", (e) => {
        if (!carries(e)) return;
        e.preventDefault();
        const above = dropAbove(e);
        clearMarks();
        const moved = e.dataTransfer.getData(mime);
        if (!moved || moved === key) return;
        const next = reorderCategoryTo(_data, moved, key, above);
        if (!next) return;   // refused, or it already sat there: no commit, no re-render
        applyChange(() => { _data.categories = next; });
      });
    }
    return r;
  };
  sideEl.appendChild(mkCat("All tags", "", _data.tags.length, "All", null));

  // One block per side. A category belongs to exactly one of them, so the lists never
  // mix in with the text snippets - each block also gets its own New category button.
  const block = (sd, heading) => {
    sideEl.appendChild(Object.assign(document.createElement("div"), { className: "lbl", textContent: heading }));
    if (bucketUsed(sd)) {
      const b = bucketOf(sd);
      sideEl.appendChild(mkCat(b, colorOf(b), tagsIn(b).length, b, "bucket"));
    }
    for (const c of catsOnSide(sd)) sideEl.appendChild(mkCat(c, colorOf(c), tagsIn(c).length, c, "cat"));
    const nc = document.createElement("div");
    nc.className = "pix-prled-newcat";
    const btn = document.createElement("button");
    btn.className = "pix-prled-btn";
    btn.innerHTML = `<span>＋</span> New category`;
    btn.title = sd === "list" ? "A category that holds lists" : "A category that holds text tags";
    btn.addEventListener("click", () => {
      const inp = document.createElement("input");
      inp.placeholder = sd === "list" ? "list category name" : "category name";
      inp.style.cssText = "width:100%;margin-top:6px;background:#151515;border:1px solid var(--acc);border-radius:6px;color:#e6e6e6;font:12px monospace;padding:7px 9px;outline:none;";
      btn.style.display = "none"; nc.appendChild(inp); inp.focus();
      // Giving up on the field must NOT call the global render(). It used to, 120ms
      // after blur, which tore down the whole editor underneath whatever the user had
      // moved on to: opening the other side's New-category field, or clicking into a
      // card name and typing (focus was silently lost, and because render() REMOVES a
      // focused input rather than blurring it, that card's name-recovery blur handler
      // never ran, so an empty or duplicate name could be normalized away = tag lost).
      // Just put the button back; nothing else on screen is affected.
      const cancel = () => { if (inp.isConnected) inp.remove(); btn.style.display = ""; };
      inp._pixCancel = cancel;   // so Escape can cancel directly, not via a blur event
      inp.addEventListener("keydown", (e) => {
        e.stopPropagation();
        if (e.key === "Enter") {
          const v = inp.value.trim();
          if (v && !isReservedName(v) && !_data.categories.some((c) => c.toLowerCase() === v.toLowerCase())) {
            addCategory(v, sd); _curCat = v; commit();
            // Landing on the just-made category IS picking it, so the create form must
            // follow its side again (5th sighting of the kindTouched carry - the rule:
            // EVERY `_curCat = <real category>` clears the override; grep `_curCat =`).
            _createDraft.kindTouched = false;
            render();   // a real action: the new category needs a row and a selection
            return;
          }
          // Say why instead of just closing - a name that is taken or reserved used to
          // dismiss the field silently, which reads as a broken button. (The sibling
          // picker was fixed for this; this one was missed.)
          if (v) {
            toast("info", isReservedName(v)
              ? `"${v}" is a built-in name, so it cannot be a category.`
              : `You already have a category called "${v}".`);
            inp.focus();
            return;
          }
          cancel();
          return;
        }
        if (e.key === "Escape") cancel();
      });
      inp.addEventListener("blur", () => setTimeout(cancel, 120));
    });
    nc.appendChild(btn); sideEl.appendChild(nc);
  };
  block("text", "Text categories");
  block("list", "List categories");
}
function startRenameCat(row, cat) {
  const nmSpan = row.querySelector(".nm");
  if (!nmSpan) return;   // already renaming this row (the label is swapped out)
  const inp = document.createElement("input");
  inp.className = "catinput"; inp.value = cat;
  // A draggable ANCESTOR hijacks a drag-select inside its own text field: the browser
  // starts dragging the row and the selection silently fails (node UI convention #11).
  // Turning it off for the life of the field is the fix that does not depend on which
  // element the browser names as the dragstart target. Restored on every exit path
  // below - commit, cancel, and the render() that a real rename triggers, which
  // rebuilds the row from scratch with draggable back on.
  const wasDraggable = row.draggable;
  row.draggable = false;
  const restoreDrag = () => { row.draggable = wasDraggable; };
  nmSpan.replaceWith(inp); inp.focus(); inp.select();
  // Clicking inside the field to place the cursor / select letters must NOT bubble
  // to the row's click handler (which re-renders the sidebar and destroys the field).
  inp.addEventListener("mousedown", (e) => e.stopPropagation());
  inp.addEventListener("click", (e) => e.stopPropagation());
  const commitRename = () => {
    const v = inp.value.trim();
    // Nothing changed: put the label back in place instead of calling render().
    // A full render on blur destroyed whatever you were mousedown-ing on, so the
    // click never landed and the sidebar / a card button had to be clicked twice.
    // "Nothing changed" is an EXACT comparison, and the taken-name check skips the row
    // being renamed. Both used to fold case, so re-capitalising a category ("styles" ->
    // "Styles") was read as a no-op AND as a clash with itself, and silently did
    // nothing - people worked around it by adding a letter and deleting it again
    // (reported 2026-08-02). A case-only rename is a real rename: it is the name people
    // see on every row, in every menu and in an export file.
    if (!v || v === cat || isReservedName(v) ||
        _data.categories.some((c) => c !== cat && c.toLowerCase() === v.toLowerCase())) {
      if (inp.isConnected) inp.replaceWith(nmSpan);
      restoreDrag();     // this row stays on screen, so it must be draggable again
      return;
    }
    const idx = _data.categories.indexOf(cat);
    if (idx > -1) _data.categories[idx] = v;
    const li = _data.listCats.indexOf(cat);   // keep it on the same side
    if (li > -1) _data.listCats[li] = v;
    if (_data.catModes && _data.catModes[cat]) {   // and keep how it picks
      _data.catModes[v] = _data.catModes[cat];
      delete _data.catModes[cat];
    }
    // ...and where it had got to. A rename is not a change of contents.
    try { renameCursor(catKey(cat), catKey(v)); } catch { /* ignore */ }
    for (const t of _data.tags) if (t.cat === cat) t.cat = v;
    if (_curCat === cat) _curCat = v;
    commit();
    render();   // the name really changed, so the sidebar and the header must follow
  };
  const cancelRename = () => { if (inp.isConnected) inp.replaceWith(nmSpan); restoreDrag(); };
  // onKey is a CAPTURE-phase window listener, so this field's own keydown never sees
  // Escape. Expose the cancel as a handle it can call directly - the same fix the
  // new-category field already had. Without it, onKey's generic `active.blur()` ran the
  // blur listener below, which COMMITS: pressing Escape to abandon a rename applied it
  // instead, with no way back.
  inp._pixCancel = cancelRename;
  inp.addEventListener("keydown", (e) => { e.stopPropagation(); if (e.key === "Enter") commitRename(); if (e.key === "Escape") cancelRename(); });
  inp.addEventListener("blur", commitRename);
}
// One step up / down inside this category's own block. Non-destructive (nothing can be
// lost and the reverse step puts it back), so it applies straight through like a rename
// rather than asking first.
function moveCatStep(cat, dir) {
  const next = reorderCategoryStep(_data, cat, dir);
  if (!next) return;
  applyChange(() => { _data.categories = next; });
}
// Everything you can do to a category, in one place that is always on screen. The two
// deletes are deliberately SEPARATE rows: "drop the folder, keep my tags" and "take
// the tags with it" are completely different outcomes, and hiding both behind one
// ambiguous ✕ is how you lose someone's work.
function openCatActions(row, cat, anchor) {
  hideCatMenu();
  const n = tagsIn(cat).length;
  const word = sideOf(cat) === "list" ? "list" : "tag";
  const many = (k) => `${k} ${word}${k === 1 ? "" : "s"}`;
  const menu = document.createElement("div");
  menu.className = "pix-prled-menu";
  menu.style.minWidth = "250px";
  const add = (label, hint, cls, fn) => {
    const mi = document.createElement("div");
    mi.className = "mi mrow" + (cls ? " " + cls : "");
    mi.innerHTML = `<span class="nm">${esc(label)}</span>` + (hint ? `<span class="cnt">${esc(hint)}</span>` : "");
    if (fn) mi.addEventListener("click", () => { hideCatMenu(); fn(); });
    menu.appendChild(mi);
  };
  // Reordering leads the menu: dragging a row is the quicker gesture but nothing on
  // screen announces it, so this is where people find out the order is theirs to set.
  // The dimmed state comes from the SAME function that performs the move, so a row
  // that looks available can never turn out to do nothing (patterns #30, #43).
  const canUp = canMoveCategory(_data, cat, -1), canDn = canMoveCategory(_data, cat, 1);
  add("Move up", canUp ? "" : "already first", canUp ? "" : "dim", canUp ? () => moveCatStep(cat, -1) : null);
  add("Move down", canDn ? "" : "already last", canDn ? "" : "dim", canDn ? () => moveCatStep(cat, 1) : null);
  menu.appendChild(Object.assign(document.createElement("div"), { className: "msep" }));
  add("Rename", "", "", () => startRenameCat(row, cat));
  add("Export this category", n ? many(n) : "empty", "", () => exportScope(cat));
  menu.appendChild(Object.assign(document.createElement("div"), { className: "msep" }));
  if (n) {
    add("Delete category", `keeps the ${many(n)}`, "danger", () => confirmDeleteCat(cat));
    add(`Delete category and its ${n === 1 ? word : word + "s"}`, `${many(n)} deleted`, "danger", () => confirmDeleteCatWithTags(cat));
  } else {
    add("Delete category", "it is empty", "danger", () => confirmDeleteCat(cat));
  }
  _overlay.appendChild(menu);
  placeMenu(menu, anchor);
  _catMenu = menu;
}
// The Text / List BUCKET rows. They are not categories - they are drawn only while a
// tag with no category of its own exists on that side, and they go away by themselves
// once that stops being true. So there is nothing to rename and nothing to delete, and
// the FIRST thing this menu does is say so: a bucket drawn like a category had someone
// hunting for a delete that could never exist (reported 2026-07-26). What it offers
// instead are the two things that actually make the row go away.
function openBucketActions(bucket, anchor) {
  hideCatMenu();
  const side = bucket === LIST_BUCKET ? "list" : "text";
  const n = tagsIn(bucket).length;
  const word = side === "list" ? "list" : "tag";
  const many = (k) => `${k} ${word}${k === 1 ? "" : "s"}`;
  const menu = document.createElement("div");
  menu.className = "pix-prled-menu";
  menu.style.minWidth = "285px";
  menu.appendChild(Object.assign(document.createElement("div"), { className: "mhead", textContent: "This is not a category" }));
  menu.appendChild(Object.assign(document.createElement("div"), {
    className: "mnote",
    textContent: `It is where ${side === "list" ? "lists" : "tags"} with no category of their own are shown. ` +
      `Give them one and this row disappears on its own.`,
  }));
  menu.appendChild(Object.assign(document.createElement("div"), { className: "msep" }));
  const add = (label, hint, cls, fn) => {
    const mi = document.createElement("div");
    mi.className = "mi mrow" + (cls ? " " + cls : "");
    mi.innerHTML = `<span class="nm">${esc(label)}</span>` + (hint ? `<span class="cnt">${esc(hint)}</span>` : "");
    mi.addEventListener("click", () => { hideCatMenu(); fn(); });
    menu.appendChild(mi);
  };
  add(n === 1 ? "Put it in a category…" : "Put them all in a category…", many(n), "", () => {
    // openCategoryMenu replaces this menu with the picker (it calls hideCatMenu itself).
    openCategoryMenu(anchor, (c) => {
      // "" means the picker landed back on the bucket itself, or the typed name was
      // unusable. Saying nothing made the button look broken.
      if (!c) { toast("info", `Pick a real category to move ${side === "list" ? "these lists" : "these tags"} into.`); return; }
      moveBucketTags(bucket, c);
    }, side);
  });
  // Singularise like every sibling menu does - "Export these tags · 1 tag" read wrong.
  const these = n === 1 ? `this ${word}` : `these ${word}s`;
  add(`Export ${these}`, many(n), "", () => exportScope(bucket));
  add(`Delete ${these}`, `${many(n)} deleted`, "danger", () => confirmDeleteBucket(bucket));
  _overlay.appendChild(menu);
  placeMenu(menu, anchor);
  _catMenu = menu;
}
// File every tag sitting in a bucket into a real category, which is the tidy way to
// make the bucket row go away. A move, not a loss, so it does not ask.
function moveBucketTags(bucket, cat) {
  const moving = tagsIn(bucket);
  if (!moving.length) return;
  const word = bucket === LIST_BUCKET ? "list" : "tag";
  applyChange(() => {
    for (const t of moving) t.cat = cat;
    // The bucket is emptied by this, so its own *wildcard position means nothing now.
    // Every other path that empties a bucket drops it; this one was stranding it for a
    // later bucket of the same size to inherit.
    try { resetCursor(catKey(bucket)); } catch { /* ignore */ }
    if (_data.catModes) delete _data.catModes[bucket];   // as confirmDeleteBucket does
    if (_curCat === bucket) {
      _curCat = cat;   // follow them, the old row is about to go
      // Landing on a real category IS picking it, so the create form must follow it
      // again - same rule as the sidebar row click. (4th instance of this failure:
      // every path that points _curCat at a real category must drop the override.)
      _createDraft.kindTouched = false;
    }
  });
}
function confirmDeleteBucket(bucket) {
  const shown = tagsIn(bucket);          // for the dialog's own wording only
  const n = shown.length;
  const word = bucket === LIST_BUCKET ? "list" : "tag";
  confirmDanger({
    title: `Delete the ${n} ${word}${n === 1 ? "" : "s"} with no category?`,
    lead: `<b>${esc(bucket)}</b> is not a category, so there is nothing there to delete on its own. ` +
      `This deletes the ${word}${n === 1 ? "" : "s"} sitting in it:`,
    listing: shown.slice(0, 40).map((t) => (isListTag(t) ? "#" : "@") + t.name).join(" · ") +
      (n > 40 ? ` … and ${n - 40} more` : ""),
    confirmLabel: `Delete ${n} ${word}${n === 1 ? "" : "s"}`,
    offerExport: true,
    exportCat: bucket,
    onConfirm: () => {
      // RE-RESOLVE at confirm time rather than holding the tag OBJECTS captured when
      // the dialog was built - the library can move underneath an open dialog, and a
      // delete-by-identity would then match nothing while still reporting success.
      const doomed = tagsIn(bucket);
      const k = doomed.length;
      if (!k) { toast("info", "Nothing left to delete there."); return; }
      applyChange(() => {
        const gone = new Set(doomed);
        _data.tags = _data.tags.filter((t) => !gone.has(t));
        for (const t of doomed) { try { resetCursor(listKey(t.name)); } catch { /* ignore */ } }
        // A bucket is a real *wildcard target, so it has a Picks mode and a position of
        // its own. Every other delete drops both (dropCategoryRecord); this one used to
        // strand them, so a rebuilt bucket of the same size resumed the dead sequence
        // and silently inherited the old mode.
        try { resetCursor(catKey(bucket)); } catch { /* ignore */ }
        if (_data.catModes) delete _data.catModes[bucket];
        if (_curCat === bucket) _curCat = "All";
      });
    },
  });
}

// The category RECORD itself (its place in the order, its side, how it picks, and
// where it had got to). Shared by both deletes so they can never drift apart.
function dropCategoryRecord(cat) {
  const idx = _data.categories.indexOf(cat);
  if (idx > -1) _data.categories.splice(idx, 1);
  const li = _data.listCats.indexOf(cat);
  if (li > -1) _data.listCats.splice(li, 1);
  if (_data.catModes) delete _data.catModes[cat];
  try { resetCursor(catKey(cat)); } catch { /* ignore */ }   // don't strand its position
}
// Drop the category, KEEP its tags (they fall into their own side's bucket).
// Behind a confirm like everything else: the tags survive, but the category's name,
// its side and how it picks do not, and with no undo a mis-click is final.
function confirmDeleteCat(cat) {
  const n = tagsIn(cat).length;
  const word = sideOf(cat) === "list" ? "list" : "tag";
  confirmDanger({
    title: `Delete the category ${cat}?`,
    lead: n
      ? `The <b>${n} ${word}${n === 1 ? "" : "s"}</b> in it are kept - they move to ` +
        `<b>${esc(sideOf(cat) === "list" ? LIST_BUCKET : TEXT_BUCKET)}</b>, ready to file somewhere else. ` +
        `Only the category itself goes.`
      : `It is empty, so only the category itself goes.`,
    confirmLabel: "Delete the category",
    offerExport: true,   // an empty category still has a name, a side and a Picks mode
    exportCat: cat,
    onConfirm: () => deleteCat(cat),
  });
}
function deleteCat(cat) {
  applyChange(() => {
    dropCategoryRecord(cat);
    const landed = new Set();
    for (const t of _data.tags) {
      if (t.cat !== cat) continue;
      t.cat = "";                                        // -> that tag's own bucket
      landed.add(isListTag(t) ? LIST_BUCKET : TEXT_BUCKET);
    }
    // Those buckets just changed size, so their own sequence position is meaningless.
    for (const b of landed) { try { resetCursor(catKey(b)); } catch { /* ignore */ } }
    if (_curCat === cat) _curCat = "All";
  });
}
// Drop the category AND everything filed under it. Always behind confirmDanger.
function deleteCatWithTags(cat) {
  const doomed = tagsIn(cat);
  const n = doomed.length;
  const word = sideOf(cat) === "list" ? "list" : "tag";
  applyChange(() => {
    const gone = new Set(doomed);
    _data.tags = _data.tags.filter((t) => !gone.has(t));
    // Each one's position goes too, or a later tag with the same name inherits a
    // half-drained deck (same rule the single-tag delete follows).
    for (const t of doomed) { try { resetCursor(listKey(t.name)); } catch { /* ignore */ } }
    dropCategoryRecord(cat);
    if (_curCat === cat) _curCat = "All";
  });
}
function confirmDeleteCatWithTags(cat) {
  const doomed = tagsIn(cat);
  const n = doomed.length;
  const word = sideOf(cat) === "list" ? "list" : "tag";
  confirmDanger({
    title: `Delete ${cat} and everything in it?`,
    lead: `This deletes the category <b>${esc(cat)}</b> and the <b>${n} ${word}${n === 1 ? "" : "s"}</b> filed under it:`,
    listing: doomed.slice(0, 40).map((t) => (isListTag(t) ? "#" : "@") + t.name).join(" · ") +
      (n > 40 ? ` … and ${n - 40} more` : ""),
    confirmLabel: `Delete ${n} ${word}${n === 1 ? "" : "s"}`,
    offerExport: true,
    exportCat: cat,
    onConfirm: () => deleteCatWithTags(cat),
  });
}
// Start over with nothing. Tucked behind the footer ⋯ so it can't be hit by accident,
// and the dialog hands you an export before it will do it.
function confirmDeleteEverything() {
  const n = _data.tags.length;
  const c = _data.categories.length;
  if (!n && !c) { toast("info", "Your library is already empty."); return; }
  confirmDanger({
    title: "Delete your whole tag library?",
    lead: `This removes <b>${n} tag${n === 1 ? "" : "s"}</b> and <b>${c} categor${c === 1 ? "y" : "ies"}</b>, ` +
      `leaving you with an empty library. Any @tag, #list or *category already typed into a Prompt node stops working.`,
    confirmLabel: "Delete everything",
    offerExport: true,
    exportCat: null,
    onConfirm: () => applyChange(() => {
      for (const t of _data.tags) { try { resetCursor(listKey(t.name)); } catch { /* ignore */ } }
      for (const cc of _data.categories) { try { resetCursor(catKey(cc)); } catch { /* ignore */ } }
      // The two buckets are *wildcard targets too, so they hold positions of their own
      // that the loop above (real categories only) would have left behind.
      for (const b of [TEXT_BUCKET, LIST_BUCKET]) { try { resetCursor(catKey(b)); } catch { /* ignore */ } }
      _data.tags = []; _data.categories = []; _data.listCats = []; _data.catModes = {};
      _curCat = "All";
      // Clear the search BOX as well, not just the flag - the top bar is not part of
      // render(), so the field went on showing a filter that was no longer applied.
      _search = "";
      const s = _overlay && _overlay.querySelector(".pix-prled-srch input");
      if (s) s.value = "";
    }),
  });
}
// The footer ⋯ - library-wide actions that are not Export or Import.
function openLibraryMenu(anchor) {
  hideCatMenu();
  const menu = document.createElement("div");
  menu.className = "pix-prled-menu";
  menu.style.minWidth = "230px";
  const n = _data.tags.length;
  const mi = document.createElement("div");
  mi.className = "mi mrow danger";
  mi.innerHTML = `<span class="nm">Delete everything…</span><span class="cnt">${n} tag${n === 1 ? "" : "s"}</span>`;
  mi.addEventListener("click", () => { hideCatMenu(); confirmDeleteEverything(); });
  menu.appendChild(mi);
  _overlay.appendChild(menu);
  // Footer button: open UPWARD when there is no room below.
  placeMenu(menu, anchor);
  _catMenu = menu;
}
// A localized create form pinned at the top: fill name + text in one place and
// hit Create - no bouncing to a button on the far side of the editor. New tags land
// in the currently-selected category, or that side's Text / List bucket under "All".
function buildCreateForm() {
  // Whichever side the sidebar is showing decides what you are about to make: open a
  // List category and the form is ready for a list. "All tags" has no side, and once
  // the user works the switch themselves their choice sticks.
  const isRealCat = (c) => c !== "All" && c !== TEXT_BUCKET && c !== LIST_BUCKET;
  const sidebarSide = _curCat === "All" ? null : sideOf(_curCat);
  if (sidebarSide && !_createDraft.kindTouched) _createDraft.kind = sidebarSide;
  const sideNow = () => (_createDraft.kind === "list" ? "list" : "text");
  // A category the user PICKED wins over the sidebar, and survives a re-render; it is
  // dropped only if it cannot hold the kind being created, or no longer exists.
  const picked = _createDraft.cat;
  const pickedUsable = picked != null &&
    (picked === "" || (_data.categories.some((c) => c === picked) && sideOf(picked) === sideNow()));
  let createCat = pickedUsable ? picked
    : (isRealCat(_curCat) && sideOf(_curCat) === sideNow() ? _curCat : "");
  if (!pickedUsable) _createDraft.cat = null;
  const form = document.createElement("div");
  form.className = "pix-prled-create";
  const nm = document.createElement("input"); nm.className = "cnm"; nm.placeholder = "new tag name"; nm.spellcheck = false;
  // A <textarea> (not <input>) so a multi-line "save selection as a tag" keeps its
  // line breaks (a text input strips newlines on assignment).
  const tx = document.createElement("textarea"); tx.className = "ctx"; followSpellcheck(tx); tx.rows = 1;
  // Text / List for the tag about to be created. Lives on the draft so it survives a
  // re-render, and follows the text (2+ lines = a List) until the user picks for
  // themselves - after that their choice sticks.
  const kindSw = makeKindSwitch((toList) => {
    _createDraft.kind = toList ? "list" : "text";
    _createDraft.kindTouched = true;
    paintKind();
  });
  const paintKind = () => {
    const list = _createDraft.kind === "list";
    kindSw.paint(list, null);
    tx.placeholder = list ? "one option per line - press Enter for the next one" : "what it expands to - the full prompt text";
    // A list needs room to type several lines; a text tag stays on the one-line row.
    tx.style.height = list ? "76px" : "36px";
    // The chosen category only holds one side, so drop it when the kind flips away.
    if (createCat && sideOf(createCat) !== sideNow()) { createCat = ""; _createDraft.cat = null; }
    paintCat();
  };
  // Seed from the in-progress draft so name + text survive a re-render (sidebar
  // category click / search), then keep the draft in sync as the user types.
  nm.value = _createDraft.name; tx.value = _createDraft.text;
  nm.addEventListener("input", () => { _createDraft.name = nm.value; });
  tx.addEventListener("input", () => {
    _createDraft.text = tx.value;
    // Guess from the text ONLY under "All tags", where nothing else says which side
    // this belongs to. Inside a category the side is already settled, so typing one
    // line in a List category must not throw the tag back to Text.
    if (_createDraft.kindTouched || sidebarSide) return;
    const k = tagLines(tx.value).length > 1 ? "list" : "text";
    if (k !== _createDraft.kind) { _createDraft.kind = k; paintKind(); }
  });
  const catBtn = document.createElement("button"); catBtn.className = "pix-prled-pill ccat"; catBtn.title = "Category for the new tag - click to change";
  const paintCat = () => {
    const label = createCat || bucketOf(sideNow());
    catBtn.innerHTML = `<span class="cd" style="background:${colorOf(label)}"></span><span>${esc(label)}</span><span class="car">▾</span>`;
  };
  // Only now that paintCat exists (paintKind calls it) can the first paint run.
  paintKind();
  catBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    openCategoryMenu(catBtn, (c) => { createCat = c; _createDraft.cat = c; paintCat(); }, sideNow());
  });
  const btn = document.createElement("button"); btn.className = "cbtn"; btn.textContent = "Create tag";
  btn.title = "Add this tag to the library (Ctrl+Enter)";
  const doCreate = () => {
    const name = sanitizeName(nm.value);
    // Typing "!!!" strips to nothing, and silently refusing read as a broken button.
    if (!name) {
      toast("info", nm.value.trim()
        ? "A tag name can only use letters, numbers, - and _."
        : "Give the tag a name first.");
      nm.focus();
      return;
    }
    const uniq = uniqueNameExcept(name, null);
    const isList = _createDraft.kind === "list";
    const kindAtCreate = _createDraft.kind;
    const kindTouchedAtCreate = _createDraft.kindTouched;
    const rec = { name: uniq, cat: createCat, text: tx.value };
    if (isList) rec.kind = "list";   // only ever written for a List (library normalize)
    _data.tags.unshift(rec);
    _createDraft = newDraft();       // tag saved -> next render's form is empty
    // ...but keep the Text/List choice if the user made it. Resetting kindTouched let
    // buildCreateForm re-derive the side from the sidebar, so after creating one
    // one-line List the next one silently came out as Text.
    if (kindTouchedAtCreate) { _createDraft.kind = kindAtCreate; _createDraft.kindTouched = true; }
    commit();
    render();
    const nf = _overlay && _overlay.querySelector(".pix-prled-create .cnm");
    if (nf) nf.focus();
    toast("success", "Created tag " + (isList ? "#" : "@") + uniq);
  };
  btn.addEventListener("click", doCreate);
  nm.addEventListener("keydown", (e) => { e.stopPropagation(); if (e.key === "Enter") { e.preventDefault(); doCreate(); } });
  // In LIST mode Enter must start the next option (typing a list is the whole point),
  // so only Ctrl/Cmd+Enter creates. In Text mode Enter still creates and Shift+Enter
  // adds a line, which is what a one-line snippet wants.
  tx.addEventListener("keydown", (e) => {
    e.stopPropagation();
    if (e.key !== "Enter") return;
    if (e.ctrlKey || e.metaKey) { e.preventDefault(); doCreate(); return; }
    if (_createDraft.kind === "list" || e.shiftKey) return;  // let the newline through
    e.preventDefault(); doCreate();
  });
  form.append(nm, tx, catBtn, kindSw.el, btn);
  return form;
}
function buildGrid() {
  const grid = document.createElement("div");
  grid.className = "pix-prled-grid";
  const q = _search.toLowerCase();
  const rows = _data.tags.filter((t) =>
    (_curCat === "All" || catOf(t) === _curCat) &&
    (!q || t.name.toLowerCase().includes(q) || t.text.toLowerCase().includes(q)));
  if (!rows.length) {
    const e = document.createElement("div");
    e.className = "pix-prled-empty"; e.style.gridColumn = "1 / -1";
    e.textContent = _search ? "No tags match your search." : "No tags here yet - create one above.";
    grid.appendChild(e);
  } else for (const t of rows) grid.appendChild(makeCard(t));
  return grid;
}
function renderContent(content) {
  content.innerHTML = "";
  const head = document.createElement("div");
  head.className = "pix-prled-chead";
  const h = document.createElement("div");
  h.className = "h";
  if (_curCat === "All") h.innerHTML = `<span>All tags</span><span class="c">· ${_data.tags.length}</span>`;
  else {
    const n = tagsIn(_curCat).length;
    const word = sideOf(_curCat) === "list" ? "list" : "tag";
    h.innerHTML = `<span class="cd" style="background:${colorOf(_curCat)}"></span><span>${esc(_curCat)}</span>` +
      `<span class="c">· ${n} ${word}${n === 1 ? "" : "s"}</span>`;
  }
  head.append(h);
  // How *thisCategory picks one of its tags. Not shown under "All tags" (there is no
  // *All to configure).
  if (_curCat !== "All") {
    const cat = _curCat;
    head.appendChild(makeModeRow({
      getMode: () => catMode(cat, _data),
      setMode: (m) => {
        _data.catModes = _data.catModes || {};
        if (m === DEFAULT_MODE) delete _data.catModes[cat]; else _data.catModes[cat] = m;
      },
      key: () => catKey(cat),
      len: () => tagsIn(cat).length,
      what: "category",
    }).el);
  }
  content.append(head, buildCreateForm(), buildGrid());
}
function render() {
  if (!_overlay) return;
  hideCatMenu();
  // A bucket row only exists while a tag sits in it. Re-file or delete the last one
  // and the selection would point at a row that is no longer drawn: nothing
  // highlighted, a header reading "Text · 0 tags" with a live Picks control for an
  // empty bucket, and the create form still forced to that side.
  if ((_curCat === TEXT_BUCKET || _curCat === LIST_BUCKET) &&
      !bucketUsed(_curCat === LIST_BUCKET ? "list" : "text")) {
    _curCat = "All";
  }
  renderSidebar(_overlay.querySelector(".pix-prled-side"));
  renderContent(_overlay.querySelector(".pix-prled-content"));
}

// ── import / export ────────────────────────────────────────────────────
// Write the library (or one category of it) to a file. `cat` null = everything.
function exportScope(cat) {
  try {
    const count = cat == null ? _data.tags.length : tagsIn(cat).length;
    const blob = new Blob([exportLibraryJSON(cat)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = cat == null ? "prompt-tags.json" : `prompt-tags-${String(cat).replace(/[^a-zA-Z0-9_\-]+/g, "-")}.json`;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    // The noun follows the side, like every menu that launches this. Saying "3 tags"
    // straight after a row that said "3 lists" made one gesture use two words.
    const word = cat == null ? "tag" : (sideOf(cat) === "list" ? "list" : "tag");
    const what = count ? `${count} ${word}${count === 1 ? "" : "s"}` : "an empty category";
    toast("info", cat == null ? `Exported ${what}.` : `Exported ${what} from ${cat}.`);
  } catch (err) {
    console.error("Pixaroma.Prompt export failed", err);
    toast("warn", "Could not write that file");
  }
}
// Everything, or just one category - one click each (reuses the dark menu chrome, so
// Escape / an outside click close it like the category picker).
function openExportMenu(anchor) {
  hideCatMenu();
  const menu = document.createElement("div");
  menu.className = "pix-prled-menu";
  const add = (label, color, count, cat) => {
    const word = cat == null ? "tag" : (sideOf(cat) === "list" ? "list" : "tag");
    const mi = document.createElement("div");
    // Only "Everything" on a completely empty library is genuinely nothing to export.
    const nothing = count === 0 && cat == null;
    mi.className = "mi mrow" + (nothing ? " dim" : "");
    mi.innerHTML = (color ? `<span class="cd" style="background:${color}"></span>` : `<span style="width:10px"></span>`) +
      `<span class="nm">${esc(label)}</span><span class="cnt">${count ? `${count} ${word}${count === 1 ? "" : "s"}` : "empty"}</span>`;
    if (!nothing) mi.addEventListener("click", () => { hideCatMenu(); exportScope(cat); });
    menu.appendChild(mi);
  };
  add("Everything", "", _data.tags.length, null);
  // Same two blocks as the sidebar, so the menu reads like the library looks.
  const block = (sd, heading) => {
    const names = [...(bucketUsed(sd) ? [bucketOf(sd)] : []), ...catsOnSide(sd)];
    if (!names.length) return;
    menu.appendChild(Object.assign(document.createElement("div"), { className: "msep" }));
    menu.appendChild(Object.assign(document.createElement("div"), { className: "mhead", textContent: heading }));
    for (const c of names) add(c, colorOf(c), tagsIn(c).length, c);
  };
  block("text", "Text categories");
  block("list", "List categories");
  _overlay.appendChild(menu);
  // The button sits in the footer, so open UPWARD when there isn't room below.
  placeMenu(menu, anchor);
  _catMenu = menu;
}
function pickImportFile() {
  const inp = document.createElement("input");
  inp.type = "file"; inp.accept = ".json,application/json"; inp.style.display = "none";
  inp.addEventListener("change", () => {
    const file = inp.files && inp.files[0];
    inp.remove();
    if (!file) return;
    // A tag library is text; a real one is kilobytes. Reading a huge file straight
    // into JSON.parse can exhaust the tab's memory before any of our own checks run.
    if (file.size > MAX_IMPORT_BYTES) {
      toast("warn", "That file is too big to be a tag library (over 8 MB).");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => startImport(String(reader.result || ""));
    reader.onerror = () => toast("warn", "Could not read that file");
    reader.readAsText(file);
  });
  // Dismissing the OS file dialog fires no "change", so without this the hidden input
  // stayed in the document for the life of the page - one per cancelled import.
  inp.addEventListener("cancel", () => inp.remove());
  document.body.appendChild(inp); inp.click();
}
function startImport(text) {
  // The file input lives on document.body and FileReader is async, so the editor can
  // be closed (Escape / Done / the node deleted) between choosing the file and the
  // read finishing. Everything below needs _overlay and _data.
  if (!_overlay || !_data) return;
  flushLibrary(); // push any pending write out before we start merging into it
  const parsed = parseImport(text);
  if (parsed.error) { toast("warn", parsed.error); return; }
  showImportPick(parsed);
}
// Step 1 of an import: show what is IN the file, by category, so only the wanted
// buckets come in. Always shown (importing is rare and seeing the contents first is
// the point); the clash step after it only appears if the chosen tags actually clash.
function showImportPick(parsed) {
  if (!_overlay || !_data) return;
  const cats = importCategories(parsed);
  const total = parsed.data.tags.length;
  const modal = document.createElement("div");
  modal.className = "pix-prled-modal";
  modal.innerHTML =
    `<div class="pix-prled-mcard"><div class="mh">Import tags</div>` +
    `<div class="mb">This file has <b>${total} tag${total === 1 ? "" : "s"}</b> in ` +
    `<b>${cats.length} categor${cats.length === 1 ? "y" : "ies"}</b>. Tick what you want to bring in.</div>` +
    // Names that cannot be used are dropped before we ever get here, and the counts
    // above are taken after that - so say it plainly rather than let the file look
    // smaller than it is.
    (parsed.dropped
      ? `<div class="mb" style="padding-top:0"><div class="conf">${parsed.dropped} more ` +
        `tag${parsed.dropped === 1 ? "" : "s"} cannot be brought in: a tag name can only ` +
        `contain letters a to z, numbers, - and _.</div></div>`
      : "") +
    `<div class="pix-prled-pick"></div>` +
    `<div class="pix-prled-mfoot">` +
    `<button class="pix-prled-mlink pk-all">All</button>` +
    `<button class="pix-prled-mlink pk-none">None</button>` +
    `<button class="pix-prled-btn push pk-cancel">Cancel</button>` +
    `<button class="pix-prled-btn pri pk-go">Import</button>` +
    `</div></div>`;
  const pick = modal.querySelector(".pix-prled-pick");
  for (const c of cats) {
    // A <label> row so a click anywhere on it toggles the box natively (no JS toggle
    // that could double-fire when the box itself is clicked).
    const row = document.createElement("label");
    row.className = "row";
    row.dataset.cat = c.name;
    row.innerHTML = `<input type="checkbox" checked><span class="cd" style="background:${colorOf(c.name)}"></span>` +
      `<span class="nm">${esc(c.name)}</span><span class="cnt">${c.count} tag${c.count === 1 ? "" : "s"}</span>`;
    pick.appendChild(row);
  }
  const boxes = () => [...pick.querySelectorAll(".row")];
  modal.querySelector(".pk-all").addEventListener("click", () => boxes().forEach((r) => { r.querySelector("input").checked = true; }));
  modal.querySelector(".pk-none").addEventListener("click", () => boxes().forEach((r) => { r.querySelector("input").checked = false; }));
  modal.querySelector(".pk-cancel").addEventListener("click", () => modal.remove());
  modal.querySelector(".pk-go").addEventListener("click", () => {
    const names = boxes().filter((r) => r.querySelector("input").checked).map((r) => r.dataset.cat);
    const sub = subsetImport(parsed, names);
    // A ticked EMPTY category is a real selection: importCategories offers those so a
    // backup can restore them, and gating on tags alone refused them with a message
    // that was also untrue ("nothing selected" while something was ticked).
    if (!sub.data.tags.length && !sub.data.categories.length) {
      toast("info", "Nothing selected to import."); return;
    }
    modal.remove();
    if (!sub.conflicts.length) { applyLibraryImport(sub, "both"); return; }
    showImportModal(sub);
  });
  modal.addEventListener("mousedown", (e) => { if (e.target === modal) modal.remove(); });
  _overlay.appendChild(modal);
}
function applyLibraryImport(parsed, mode) {
  if (!_overlay) return;
  const before = { categories: [..._data.categories] };
  const res = applyImport(parsed, mode);
  _data = clone(getLibrary());
  render();
  const bits = [];
  if (res.added) bits.push(`${res.added} tag${res.added === 1 ? "" : "s"} added`);
  if (res.replaced) bits.push(`${res.replaced} replaced`);
  // applyImport merges categories, sides and Picks modes INDEPENDENTLY of the tag
  // counts, so a file whose tags were all skipped as duplicates could still add
  // categories. Reporting "Nothing was imported" then was simply false.
  const hadCat = new Set(before.categories.map((c) => c.toLowerCase()));
  const catsAdded = _data.categories.filter((c) => !hadCat.has(c.toLowerCase())).length;
  if (catsAdded) bits.push(`${catsAdded} categor${catsAdded === 1 ? "y" : "ies"} added`);
  toast("info", bits.length ? "Imported: " + bits.join(", ") + "." : "Nothing was imported.");
}
function showImportModal(parsed) {
  if (!_overlay) return;
  const modal = document.createElement("div");
  modal.className = "pix-prled-modal";
  const total = parsed.data.tags.length;
  // Match the other two listings: name a list with # (not always @), and say when the
  // list has been cut short rather than just stopping.
  const symOf = (n) => {
    const t = parsed.data.tags.find((x) => x.name === n);
    return t && t.kind === "list" ? "#" : "@";
  };
  const conf = parsed.conflicts.slice(0, 40).map((n) => symOf(n) + n).join(" · ") +
    (parsed.conflicts.length > 40 ? ` … and ${parsed.conflicts.length - 40} more` : "");
  modal.innerHTML =
    `<div class="pix-prled-mcard"><div class="mh">Import tags</div>` +
    `<div class="mb">Importing <b>${total} tag${total === 1 ? "" : "s"}</b>. ` +
    (parsed.conflicts.length === 1
      ? `<b>1</b> has a name you already use:`
      : `<b>${parsed.conflicts.length}</b> have names you already use:`) +
    `<div class="conf">${esc(conf)}</div>How should ${parsed.conflicts.length === 1 ? "it" : "the clashes"} be handled?</div>` +
    `<div class="pix-prled-opts">` +
    `<div class="pix-prled-opt rec" data-mode="both"><span class="oic">＋</span><span class="t">Keep both<small>Renames the imported one (e.g. @${esc(parsed.conflicts[0])}-2) so nothing is lost</small></span><span class="rtag">recommended</span></div>` +
    `<div class="pix-prled-opt" data-mode="replace"><span class="oic">⟳</span><span class="t">Replace mine<small>Overwrite my tag's text with the imported one</small></span></div>` +
    `<div class="pix-prled-opt" data-mode="skip"><span class="oic">⊘</span><span class="t">Skip duplicates<small>Only add the tags I don't already have</small></span></div>` +
    `</div></div>`;
  modal.addEventListener("mousedown", (e) => { if (e.target === modal) modal.remove(); });
  modal.querySelectorAll(".pix-prled-opt").forEach((o) => o.addEventListener("click", () => {
    const m = o.dataset.mode;
    if (m !== "replace") { modal.remove(); applyLibraryImport(parsed, m); return; }
    // "Replace mine" overwrites text the user WROTE, in one click. It used to be
    // covered by undo; removing undo silently left it as the ONE loss that never
    // asked. Ask like every other destructive path - and keep the options modal
    // open underneath, so Cancel lands back on the choice, not on nothing.
    const n = parsed.conflicts.length;
    confirmDanger({
      title: `Overwrite ${n === 1 ? "1 tag" : n + " tags"} of yours?`,
      lead: `The imported text replaces your own on <b>${n}</b> tag${n === 1 ? "" : "s"}. What you have there now goes away.`,
      listing: parsed.conflicts.slice(0, 40).join(" · ") + (n > 40 ? ` … and ${n - 40} more` : ""),
      confirmLabel: "Replace mine",
      offerExport: true,
      exportCat: null,
      onConfirm: () => { modal.remove(); applyLibraryImport(parsed, "replace"); },
    });
  }));
  _overlay.appendChild(modal);
}
// A real "are you sure?", used ONLY where one click takes away more than one thing.
// There is no undo (see applyChange), so every path that can lose something uses it.
// `lead` is HTML (so it can bold the count); escape any user value before passing it.
function confirmDanger({ title, lead, listing, confirmLabel, offerExport, exportCat, onConfirm }) {
  if (!_overlay) return;
  const modal = document.createElement("div");
  modal.className = "pix-prled-modal";
  modal.innerHTML =
    `<div class="pix-prled-mcard"><div class="mh">${esc(title)}</div>` +
    `<div class="mb">${lead}` +
    (listing ? `<div class="conf">${esc(listing)}</div>` : "") +
    // Its own block: without a listing above it, this ran straight on from the end of
    // `lead` with no gap.
    `<div style="margin-top:10px">This cannot be undone.</div></div>` +
    `<div class="pix-prled-mfoot">` +
    (offerExport ? `<button class="pix-prled-btn dg-exp" type="button">⭳ Export a backup first</button>` : "") +
    `<button class="pix-prled-btn push dg-cancel" type="button">Cancel</button>` +
    `<button class="pix-prled-btn danger dg-go" type="button">${esc(confirmLabel)}</button>` +
    `</div></div>`;
  // Exporting must NOT close the dialog: the point is to save the file and then still
  // be sitting in front of the decision.
  modal.querySelector(".dg-exp")?.addEventListener("click", () => exportScope(exportCat == null ? null : exportCat));
  modal.querySelector(".dg-cancel").addEventListener("click", () => modal.remove());
  modal.querySelector(".dg-go").addEventListener("click", () => { modal.remove(); onConfirm(); });
  modal.addEventListener("mousedown", (e) => { if (e.target === modal) modal.remove(); });
  _overlay.appendChild(modal);
}

function toast(sev, msg) {
  const t = app?.extensionManager?.toast;
  if (t?.add) t.add({ severity: sev, summary: "Prompt Pixaroma", detail: msg, life: 2600 });
  else console.warn("[Pixaroma.Prompt]", msg);
}

// A self-contained help panel, appended to the overlay (reuses the modal chrome so
// it sits above the editor and closes on the X / click-outside / Escape via onKey).
function showLibraryHelp() {
  if (!_overlay) return;
  const modal = document.createElement("div");
  // Marked as the HELP panel rather than a confirm, so gates can tell them apart.
  modal.className = "pix-prled-modal pix-prled-helpmodal";
  modal.innerHTML =
    `<div class="pix-prled-mcard pix-prled-help-card"><div class="mh">How the tag library works</div>` +
    `<div class="mb">` +
    `<p><b>What it is.</b> Your personal, reusable prompt snippets. Type a short <b>@name</b> in a Prompt node and it becomes the full text at run time, so the box stays short. Your library is saved on your machine, stays private to you, and survives updating the plugin - it is never stored inside a workflow.</p>` +
    `<p><b>Create a tag.</b> Fill in the name and the full prompt text along the top, pick a category, and press <b>Create tag</b>. New tags appear at the front.</p>` +
    `<p><b>Edit a tag.</b> Click a card's name or its text and change it - your edits save on their own.</p>` +
    `<p><b>Text or List.</b> Every card has a switch at the bottom with both choices on it. <b>Text</b> is one piece of writing and <b>@name</b> drops in all of it. <b>List</b> holds one option per line (cat, dog, mouse) and <b>#name</b> drops in a random one, fresh every run. Flip the switch any time: it changes what the card is for, never what your saved prompts do. While the create box at the top is set to List, Enter starts the next option and Ctrl+Enter adds the tag.</p>` +
    `<p><b>Categories.</b> Make them in the left sidebar. Click a card's coloured pill to move that tag to another category. The <b>⋯</b> on a category row (right-clicking the row does the same) lets you rename it, export just that category, or delete it. Typing <b>*category</b> in a prompt picks a random tag from it each run.</p>` +
    `<p><b>Put the categories in your own order.</b> Drag a category row up or down to move it, or use <b>Move up</b> and <b>Move down</b> in its <b>⋯</b> menu. The order you set is the order you see everywhere: the sidebar, the export menu, the pill on a card, and the list that pops up when you type <b>@</b>, <b>#</b> or <b>*</b>. Text and List categories are two separate groups, so a row moves within its own group. You can also drag the divider between the sidebar and the cards to make the category list wider, and it stays that way next time you open it (double-click the divider to put it back).</p>` +
    `<p><b>The italic Text and List rows are not categories.</b> They are where tags with no category of their own are shown, so there is nothing to rename or delete about the row itself. Their <b>⋯</b> can file them all into a category at once (and the row then disappears by itself), export them, or delete them.</p>` +
    `<p><b>Deleting.</b> Anything that removes something asks you first and shows you exactly what will go, so you can check it is the one you meant. Deleting a category gives you two choices: keep its tags (they move to Text or List) or delete them along with it. The <b>⋯</b> next to Export and Import has <b>Delete everything</b> for starting over. Where a whole group is going, the question also offers to save you a backup file first. There is no undo, so the answer is final once you give it.</p>` +
    `<p><b>Picks: Shuffle, Random or In order.</b> A List card, and the header of anything you can roll with <b>*name</b>, each have a <b>Picks</b> control for how they choose. <b>Shuffle</b> is the default: it deals a shuffled deck, so every option comes up once before any repeat. <b>Random</b> is any one every time, so the same one can come up twice in a row. <b>In order</b> goes 1, 2, 3 and around again. Shuffle and In order remember their place between runs (the card shows it) and the <b>↺</b> button starts that list over.</p>` +
    `<p><b>Use a tag.</b> Type <b>@</b> (or <b>#</b> for lists, <b>*</b> for categories) in the prompt box for a searchable list, or press <b>Insert</b> on a card to drop it straight into your prompt.</p>` +
    `<p><b>Share.</b> <b>Export</b> saves your tags to a file: everything, or just one category. <b>Import</b> shows you what is in a file so you can pick which categories to bring in, and if a name already exists you choose keep both, replace, or skip.</p>` +
    `</div>` +
    `<div class="pix-prled-help-foot"><button class="pix-prled-btn pri hgot">Got it</button></div>` +
    `</div>`;
  modal.addEventListener("mousedown", (e) => { if (e.target === modal) modal.remove(); });
  modal.querySelector(".hgot").addEventListener("click", () => modal.remove());
  _overlay.appendChild(modal);
}

// ── open / close ───────────────────────────────────────────────────────
export function openLibraryEditor(node, opts) {
  closeLibraryEditor();
  injectCSS();
  _node = node; _opts = opts || {}; _accent = _opts.accent || BRAND;
  _createDraft = newDraft((_opts.prefill || "").trim());
  // Re-read from storage, never the in-memory cache: another tab / window may have
  // edited the library since this page loaded, and the close path writes this working
  // copy back wholesale.
  _data = clone(reloadLibrary());
  _curCat = "All"; _search = "";

  const ov = document.createElement("div");
  ov.className = "pix-prled";
  ov.style.setProperty("--acc", _accent);
  ov.innerHTML =
    `<div class="pix-prled-bar">` +
    `<div class="ttl"><span class="cr">☲</span> Tag library</div>` +
    `<div class="pix-prled-srch"><span class="i">🔍</span><input placeholder="search tags and text"></div>` +
    `<span class="priv">private to you · survives plugin updates</span>` +
    `<span class="help" title="How the tag library works"><span class="pix-prled-svg" style="-webkit-mask-image:url(${pixAsset(ICON_BASE + "help.svg")});mask-image:url(${pixAsset(ICON_BASE + "help.svg")})"></span></span>` +
    `<span class="x" title="Close">✕</span></div>` +
    `<div class="pix-prled-main"><div class="pix-prled-side"></div>` +
    `<div class="pix-prled-grip" title="Drag to resize the category list. Double-click to reset."></div>` +
    `<div class="pix-prled-content"></div></div>` +
    `<div class="pix-prled-foot"><button class="pix-prled-btn imp-export" title="Save your tags to a file: everything, or just one category"><span>⭳</span> Export ▾</button>` +
    `<button class="pix-prled-btn imp-import" title="Bring tags in from a file - you choose which categories"><span>⭱</span> Import</button>` +
    `<button class="pix-prled-btn imp-more" title="More library actions">⋯</button>` +
    `<button class="pix-prled-btn push imp-done">Done</button></div>`;
  document.body.appendChild(ov);
  _overlay = ov;

  const search = ov.querySelector(".pix-prled-srch input");
  search.addEventListener("input", () => { _search = search.value; renderContent(ov.querySelector(".pix-prled-content")); });
  search.addEventListener("keydown", (e) => { e.stopPropagation(); if (e.key === "Escape" && _search) { _search = ""; search.value = ""; renderContent(ov.querySelector(".pix-prled-content")); e.stopImmediatePropagation(); } });
  ov.querySelector(".x").addEventListener("click", closeLibraryEditor);
  ov.querySelector(".help").addEventListener("click", showLibraryHelp);
  ov.querySelector(".imp-done").addEventListener("click", closeLibraryEditor);
  ov.querySelector(".imp-export").addEventListener("click", (e) => openExportMenu(e.currentTarget));
  ov.querySelector(".imp-import").addEventListener("click", pickImportFile);
  ov.querySelector(".imp-more").addEventListener("click", (e) => openLibraryMenu(e.currentTarget));
  installSidebarResize(ov);
  // A dragged category row carries its name as text/plain as well, so the drag starts
  // on every browser - but that ALSO makes every text field in here a native drop
  // target. Releasing a row over a tag card's text box would splice the category name
  // into that snippet, and the card's own input handler commits to the library on the
  // spot, with no undo. There is no drag handle on a row, so overshooting onto the card
  // grid is the normal learning gesture, and no insert line appears there to warn you.
  // Cancel any drop that carries one of OUR row types and did not land on a category
  // row; capture phase, so it beats the field's own default. Ordinary text dragged in
  // from elsewhere carries neither type and is untouched, so dropping text into a tag
  // box still works.
  ov.addEventListener("drop", (e) => {
    if (!e.dataTransfer) return;
    const t = [...e.dataTransfer.types];
    if (!t.includes(CAT_MIME("text")) && !t.includes(CAT_MIME("list"))) return;
    if (e.target.closest && e.target.closest(".pix-prled-cat")) return;   // a real reorder target
    e.preventDefault();
    e.stopPropagation();
  }, true);

  render();
  // Coming from "save selection as a tag": the text is already in the create form,
  // so focus the NAME field - the user only has to name it and hit Create.
  if ((_opts.prefill || "").trim()) {
    const nf = ov.querySelector(".pix-prled-create .cnm");
    if (nf) { nf.focus(); }
  } else {
    search.focus();
  }

  _undoGuardOff = installGraphUndoGuard(() => !!_overlay && _overlay.isConnected);
  window.addEventListener("keydown", onKey, true);
}
// ── the category sidebar's width ───────────────────────────────────────
// Remembered across opens in an UNREGISTERED setting (Vue Compat #20 - it persists
// without being declared anywhere, exactly like the library itself). Never fatal: a
// width is a convenience, so every read and write is wrapped and falls back to the
// default rather than taking the editor down with it.
function readSidebarWidth() {
  try {
    const v = app.ui?.settings?.getSettingValue(SIDE_W_SETTING);
    return v == null ? SIDE_W_DEFAULT : clampSideW(v);
  } catch { return SIDE_W_DEFAULT; }
}
function writeSidebarWidth(px) {
  try {
    const s = app.ui?.settings, w = clampSideW(px);
    if (typeof s?.setSettingValueAsync === "function") s.setSettingValueAsync(SIDE_W_SETTING, w);
    else if (typeof s?.setSettingValue === "function") s.setSettingValue(SIDE_W_SETTING, w);
  } catch { /* ignore */ }
}
function installSidebarResize(overlay) {
  const side = overlay.querySelector(".pix-prled-side");
  const grip = overlay.querySelector(".pix-prled-grip");
  if (!side || !grip) return;
  side.style.width = readSidebarWidth() + "px";
  let pid = null, startX = 0, startW = 0;
  const move = (ev) => {
    // BOTH defences are required (node UI convention #20). A real mouse can lose its
    // release - the pointer leaves the viewport, or something else takes capture - and
    // the seam then follows the cursor for ever with no way to put it down. Synthetic
    // events never reproduce it, so this guard cannot be "tested away".
    if (!(ev.buttons & 1)) { end(); return; }
    side.style.width = clampSideW(startW + (ev.clientX - startX)) + "px";
  };
  const end = () => {
    if (pid === null) return;                 // idempotent: the guard above also calls it
    try { grip.releasePointerCapture(pid); } catch { /* already released */ }
    pid = null;
    grip.classList.remove("on");
    overlay.classList.remove("resizing");
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", end);
    window.removeEventListener("pointercancel", end);
    writeSidebarWidth(parseFloat(side.style.width));
  };
  grip.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    pid = e.pointerId;
    startX = e.clientX;
    startW = side.getBoundingClientRect().width;
    try { grip.setPointerCapture(pid); } catch { /* window listeners still cover it */ }
    grip.classList.add("on");
    overlay.classList.add("resizing");
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", end);
    window.addEventListener("pointercancel", end);
    e.preventDefault();
  });
  grip.addEventListener("lostpointercapture", end);
  // A discoverable way back from a width dragged too far.
  grip.addEventListener("dblclick", () => {
    side.style.width = SIDE_W_DEFAULT + "px";
    writeSidebarWidth(SIDE_W_DEFAULT);
  });
}
function onKey(e) {
  if (e.key !== "Escape") return;
  // Close the TOPMOST modal (last in DOM order), not the first: the Replace-mine
  // confirm stacks on top of the still-open import-options modal, and removing the
  // first match silently deleted the covered one - Escape looked like it did nothing,
  // then Cancel landed on a bare editor with the import choices gone.
  const _modals = _overlay ? _overlay.querySelectorAll(".pix-prled-modal") : [];
  if (_modals.length) { _modals[_modals.length - 1].remove(); e.stopPropagation(); return; }
  if (_catMenu) { hideCatMenu(); e.stopPropagation(); return; }
  // This is a CAPTURE-phase window listener, so it beats every field's own keydown
  // handler (those are bubble-phase). Escape therefore used to close the WHOLE editor
  // from inside a text field, which is never what Escape means there: it binned a
  // half-typed tag (including the text handed over by "Save selection as a tag"), and
  // the per-field Escape handling in the new-category and rename inputs could never
  // run at all. Dismiss the FIELD first; a second Escape closes the editor as usual.
  const active = document.activeElement;
  if (active && _overlay && _overlay.contains(active)) {
    if (active.classList.contains("catinput")) {   // renaming a category: cancel it
      // Call the field's own cancel. blur() would run its blur listener, which COMMITS
      // the rename - the exact opposite of what Escape means.
      if (typeof active._pixCancel === "function") active._pixCancel(); else active.blur();
      e.stopPropagation();
      return;
    }
    // The SEARCH box clears its filter on the first Escape, then gives up focus on the
    // next. The generic INPUT branch below used to swallow it (capture phase, so the
    // field's own handler never ran), leaving the box showing a filter it had dropped.
    if (active.closest(".pix-prled-srch")) {
      if (active.value) {
        _search = ""; active.value = "";
        renderContent(_overlay.querySelector(".pix-prled-content"));
      } else {
        active.blur();
      }
      e.stopPropagation();
      return;
    }
    if (active.closest(".pix-prled-newcat")) {     // naming a new category: cancel it
      // Call the field's own cancel rather than leaning on a blur event to do it.
      if (typeof active._pixCancel === "function") active._pixCancel(); else active.blur();
      e.stopPropagation();
      return;
    }
    const form = _overlay.querySelector(".pix-prled-create");
    if (form && form.contains(active) && (_createDraft.name || _createDraft.text)) {
      active.blur();
      e.stopPropagation();
      return;
    }
    // Any other field in the editor - a card's name or its text, which is where
    // people actually spend their time, and where Escape is also the reflex for
    // dismissing the browser's own autofill list. Give up the field, not the editor.
    const t = active.tagName;
    if (t === "INPUT" || t === "TEXTAREA") {
      // A field that COMMITS on blur must be cancelled through its own handle, never
      // by blur() - blurring it is how Escape ended up applying the very edit it was
      // meant to abandon (twice: the category rename, then the card name).
      if (typeof active._pixCancel === "function") active._pixCancel(); else active.blur();
      e.stopPropagation();
      return;
    }
  }
  e.stopPropagation();
  closeLibraryEditor();
}
export function closeLibraryEditor() {
  window.removeEventListener("keydown", onKey, true);
  hideCatMenu();
  // BELT AND BRACES, not live recovery. Since the card's name input stopped writing an
  // invalid name into the working copy at all (see the makeCard blur/input handlers),
  // nothing can put an empty or duplicate name in `_data.tags` any more, so this loop
  // should never find anything. It stays because an empty name is silently DROPPED by
  // normalize and losing a tag is unrecoverable - keep it as the last line of defence,
  // do not read it as the thing that makes invalid names safe.
  if (_data) {
    for (const t of _data.tags) { const u = uniqueNameExcept(t.name, t); if (u !== t.name) t.name = u; }
    // Only WRITE the working copy back when it actually differs from what is stored.
    // Committing unconditionally meant merely opening and closing the editor stamped
    // this tab's snapshot over the library, silently undoing another tab's edits.
    try { if (!isSameAsStored(_data)) commitLibrary(_data); } catch { /* ignore */ }
  }
  // flushLibrary only writes when a debounced write is actually PENDING, so this
  // cannot lose the last edit and cannot stamp this tab's snapshot over another
  // tab's work either (which an unconditional flush here silently did, cancelling
  // the isSameAsStored guard two lines above).
  try { flushLibrary(); } catch { /* ignore */ }
  try { flushCursors(); } catch { /* ignore */ }   // write any Start-over straight away
  try { _undoGuardOff?.(); } catch { /* ignore */ }
  _undoGuardOff = null;
  if (_overlay) { try { _overlay.remove(); } catch { /* ignore */ } }
  _overlay = null; _node = null; _opts = null; _data = null; _createDraft = newDraft();
}
export function closeLibraryEditorFor(node) { if (_node === node) closeLibraryEditor(); }
