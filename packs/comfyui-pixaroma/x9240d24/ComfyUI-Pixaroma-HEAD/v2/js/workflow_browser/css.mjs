// ╔═══════════════════════════════════════════════════════════════╗
// ║  Pixaroma Workflows - the one stylesheet                       ║
// ╚═══════════════════════════════════════════════════════════════╝
//
// Injected ONCE, and therefore it OWNS every value that goes into it. Do not
// add a parameter to injectWorkflowCSS: the toolbar button mounts long before
// the window is built, so whichever caller happened to be first would decide
// the icon url, and the Help browser has already been bitten by exactly that -
// the logo arrived as `mask: url("undefined")`, and an invalid mask hides the
// element while still computing as present, so every check passed and nothing
// was painted. (help-browser pattern #2.)
//
// Palette deliberately matches the Help window, so the two panels read as the
// same pair of tools rather than two separate products.
//
// ── The density scale ────────────────────────────────────────────────────────
// Every size a person can perceive as "big or small" goes through z(), which
// multiplies it by --pixwb-k. Small = 1 (what the panel shipped as), and the
// toolbar's A button sets 1.15 or 1.32 on the ROOT element.
//
// Deliberately NOT done with CSS `zoom` or a transform, even though one line
// would have replaced forty. The window writes its own left/top/width/height
// in pixels on .pixwb-win while being dragged and resized, so zooming that
// element makes it render at a size other than the number just written and the
// resize math fights itself. calc() leaves every measurement in the code
// (getBoundingClientRect, gridTemplateColumns, the drag hit tests) working in
// exactly the units it already assumes.
//
// The variable is set on document.documentElement rather than on the window,
// because the right-click menu and the toast are position:fixed children of
// <body> and would not inherit it from the panel.

import { pixAsset } from "../shared/api_url.mjs";

const CSS_ID = "pixaroma-workflows-css";

const ICON = pixAsset("icons/ui/workflow.svg");
const ACC = "var(--pix-acc, #f66744)";

/** One scalable length. Keeps the original number visible and readable, and
 *  makes it impossible to add a size that forgets the density variable. */
const z = (n) => `calc(${n}px * var(--pixwb-k, 1))`;

export function injectWorkflowCSS() {
  if (document.getElementById(CSS_ID)) return;
  const style = document.createElement("style");
  style.id = CSS_ID;
  style.textContent = `
/* ── toolbar button (sits beside the Help ?) ─────────────────── */
/* Values measured off the live Align and Help buttons, not guessed: the icon
   is currentColor behind a mask, hover lifts only the BACKGROUND, and the
   rendered border width is 0 so border-color never actually shows.
   NOT scaled by --pixwb-k: it lives in ComfyUI's toolbar next to buttons we do
   not own, and a Pixaroma button taller than the Help ? beside it reads as a
   bug rather than as a preference. */
.pixwb-btn .pixwb-btn-icon {
  display: inline-block; width: 18px; height: 18px;
  background-color: currentColor; pointer-events: none;
  mask-image: url(${ICON}); -webkit-mask-image: url(${ICON});
  mask-size: contain; -webkit-mask-size: contain;
  mask-repeat: no-repeat; -webkit-mask-repeat: no-repeat;
  mask-position: center; -webkit-mask-position: center;
}
.pixwb-btn {
  background-color: #2a2c2e !important; color: #ddd !important; border-color: #444 !important;
}
.pixwb-btn:hover { background-color: #3a3d40 !important; }
.pixwb-btn.pixwb-btn-open {
  background-color: ${ACC} !important; color: #fff !important; border-color: ${ACC} !important;
}
.pixwb-btn.pixwb-btn-open:hover { background-color: ${ACC} !important; filter: brightness(1.08); }

/* ── the window ──────────────────────────────────────────────── */
.pixwb-win {
  position: fixed; z-index: 1300; display: flex; flex-direction: column;
  background: #141312; border: 1px solid #3d3936; border-radius: 10px;
  box-shadow: 0 18px 48px rgba(0,0,0,.6);
  color: #cfcac7; font-family: inherit; font-size: ${z(13)}; line-height: 1.55;
  overflow: hidden; user-select: none;
}
.pixwb-title {
  display: flex; align-items: center; gap: 8px; flex: none;
  padding: 8px 10px; background: #232120; border-bottom: 1px solid #302d2b;
  cursor: move;
}
.pixwb-title.pixwb-dragging { cursor: grabbing; }
.pixwb-name { display: flex; align-items: center; gap: 8px; font-weight: 600; color: #fff; font-size: ${z(12.5)}; }
.pixwb-logo {
  width: ${z(15)}; height: ${z(15)}; display: inline-block; background-color: ${ACC};
  mask: url(${ICON}) center/contain no-repeat;
  -webkit-mask: url(${ICON}) center/contain no-repeat;
}
.pixwb-count { color: #7d7673; font-size: ${z(11)}; font-weight: 400; }
.pixwb-sp { flex: 1; }
.pixwb-wbtn {
  border: none; border-radius: 5px; padding: 3px 8px; cursor: pointer;
  background: rgba(255,255,255,.05); color: #a49d99; font-family: inherit; font-size: ${z(12)};
}
.pixwb-wbtn:hover { background: ${ACC}; color: #fff; }

/* ── toolbar row ─────────────────────────────────────────────── */
.pixwb-bar {
  display: flex; align-items: center; gap: 7px; flex: none; flex-wrap: wrap;
  padding: 8px 10px; background: #1d1c1b; border-bottom: 1px solid #302d2b;
}
.pixwb-search { position: relative; flex: 1; min-width: 90px; }
.pixwb-search input {
  width: 100%; background: #141312; border: 1px solid #3d3936; color: #cfcac7;
  border-radius: 6px; padding: 5px 9px; font-family: inherit; font-size: ${z(12.5)}; outline: none;
}
.pixwb-search input::placeholder { color: #6e6764; }
.pixwb-search input:focus { border-color: ${ACC}; }
.pixwb-seg { display: flex; border: 1px solid #3d3936; border-radius: 6px; overflow: hidden; flex: none; }
.pixwb-seg button {
  border: none; background: rgba(255,255,255,.04); color: #8e8783; cursor: pointer;
  padding: 4px 9px; font-family: inherit; font-size: ${z(11.5)};
}
.pixwb-seg button:hover { color: #fff; }
.pixwb-seg button.on { background: ${ACC}; color: #fff; }
.pixwb-tbtn {
  border: 1px solid #3d3936; background: rgba(255,255,255,.04); color: #cfcac7;
  border-radius: 6px; padding: 5px 10px; cursor: pointer; white-space: nowrap;
  font-family: inherit; font-size: ${z(11.5)};
  transition: background .12s, border-color .12s, color .12s;
}
.pixwb-tbtn:hover { border-color: ${ACC}; color: #fff; }
.pixwb-tbtn.pixwb-primary { background: ${ACC}; border-color: ${ACC}; color: #fff; }
.pixwb-tbtn.pixwb-primary:hover { filter: brightness(1.08); }

/* The size control: three serif A's at three sizes, in the same segmented
   idiom as Grid|List so it reads as part of the panel rather than bolted on.
   Each A is drawn at its OWN size, so the control previews what it does and
   shows which one is currently picked without needing a word for it. */
.pixwb-sizeseg button {
  font-family: Georgia, "Times New Roman", serif; font-weight: 700;
  padding: 3px 8px; line-height: 1.15; align-self: stretch;
}
.pixwb-sizeseg button[data-k="s"] { font-size: ${z(9.5)}; }
.pixwb-sizeseg button[data-k="m"] { font-size: ${z(11.5)}; }
.pixwb-sizeseg button[data-k="l"] { font-size: ${z(13.5)}; }

/* ── body: folders | grid | detail ───────────────────────────── */
.pixwb-body { display: flex; flex: 1; min-height: 0; position: relative; }
.pixwb-side {
  width: ${z(204)}; min-width: ${z(130)}; flex: none; background: #1d1c1b;
  overflow-y: auto; padding: 8px 6px;
}
.pixwb-sidegrip { width: 6px; flex: none; cursor: ew-resize; background: transparent; z-index: 2; }
.pixwb-sidegrip::after {
  content: ""; display: block; width: 1px; height: 100%; margin-left: 2px;
  background: #302d2b; transition: background .12s;
}
.pixwb-sidegrip:hover::after, .pixwb-sidegrip.pixwb-dragging::after { background: ${ACC}; width: 3px; margin-left: 1px; }

.pixwb-grouphead {
  font-size: ${z(9.5)}; font-weight: 700; color: #6e6764; text-transform: uppercase;
  letter-spacing: .07em; padding: 9px 7px 4px;
}
.pixwb-fold {
  display: flex; align-items: center; gap: 7px; width: 100%; text-align: left;
  background: none; border: none; cursor: pointer; color: #b6b0ac;
  font-family: inherit; font-size: ${z(11.5)}; padding: 4px 7px; border-radius: 5px;
}
.pixwb-fold:hover { background: rgba(255,255,255,.05); color: #fff; }
.pixwb-fold.on { color: #fff; background: color-mix(in srgb, ${ACC} 15%, transparent); }
.pixwb-fold .pixwb-cnt { margin-left: auto; font-size: ${z(9.5)}; color: #7d7673; font-variant-numeric: tabular-nums; padding-left: 6px; flex: none; }
.pixwb-fold .pixwb-dot { width: ${z(9)}; height: ${z(9)}; border-radius: 2px; flex: none; background: #4d7ea8; }
.pixwb-fold.pixwb-droptarget { outline: 1px dashed ${ACC}; background: color-mix(in srgb, ${ACC} 10%, transparent); }
/* Dragging a FOLDER shows where it would land instead of highlighting the row,
   because the row is not the destination - the gap next to it is. */
.pixwb-fold.pixwb-insert-above { box-shadow: inset 0 2px 0 0 ${ACC}; }
.pixwb-fold.pixwb-insert-below { box-shadow: inset 0 -2px 0 0 ${ACC}; }
.pixwb-fold.pixwb-dragging-me { opacity: .45; }
.pixwb-fold .pixwb-nest { display: inline-block; flex: none; }
/* The label has to be allowed to shrink or a long folder name pushes its own
   count off the row - a flex item defaults to min-width:auto and refuses to go
   below its text. Only became reachable at the larger densities. */
.pixwb-fold .pixwb-foldlbl {
  flex: 1 1 auto; min-width: 0;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

/* ── the folder twisty ───────────────────────────────────────── */
/* A folder with children gets one; a folder without gets a same-width spacer,
   so every label in the column starts on the same vertical line whether or not
   its folder happens to have sub-folders. */
.pixwb-chev {
  flex: none; width: ${z(13)}; height: ${z(13)}; display: flex;
  align-items: center; justify-content: center;
  border-radius: 3px; color: #7d7673; font-size: ${z(9)}; line-height: 1;
  transition: transform .12s, color .12s, background .12s;
}
.pixwb-chev.pixwb-chev-open { transform: rotate(90deg); }
.pixwb-chev:hover { background: rgba(255,255,255,.14); color: #fff; }
.pixwb-fold.on .pixwb-chev { color: #e8ded9; }
.pixwb-chevpad { flex: none; width: ${z(13)}; }

/* ── the grid ────────────────────────────────────────────────── */
.pixwb-main { flex: 1; min-width: 0; overflow-y: auto; padding: 10px; }
.pixwb-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(${z(132)}, 1fr)); gap: ${z(10)}; align-content: start; }
.pixwb-card {
  background: #1d1c1b; border: 1px solid #302d2b; border-radius: 7px; overflow: hidden;
  cursor: pointer; position: relative; transition: border-color .12s;
}
.pixwb-card:hover { border-color: ${ACC}; }
.pixwb-card.sel { border-color: ${ACC}; box-shadow: 0 0 0 1px color-mix(in srgb, ${ACC} 45%, transparent); }
.pixwb-card.kbd { outline: 1px solid ${ACC}; outline-offset: 1px; }
.pixwb-cov { display: block; width: 100%; height: ${z(68)}; background: #141312; object-fit: cover; }
.pixwb-cardname {
  padding: 5px 6px 1px; font-size: ${z(10.5)}; color: #ddd6d2; line-height: 1.3;
  overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
}
.pixwb-cardmeta { padding: 0 6px 6px; font-size: ${z(9)}; color: #6e6764; }
/* The star was a 12px glyph in the corner and was genuinely hard to hit. It is
   now a proper 26x26 target with its own backdrop, so it is both visible on a
   pale cover and clickable without aiming. */
/* Hollow WHITE when it is not a favourite, filled ORANGE when it is - the same
   pair used in the left column and on the detail button, so all three read as
   one control rather than three. */
.pixwb-star {
  position: absolute; top: 3px; right: 3px;
  width: ${z(26)}; height: ${z(26)}; display: flex; align-items: center; justify-content: center;
  font-size: ${z(15)}; line-height: 1; cursor: pointer; border-radius: 6px;
  color: #ffffff; background: rgba(0,0,0,.34);
  transition: background .12s, color .12s, transform .08s;
}
.pixwb-card:hover .pixwb-star { background: rgba(0,0,0,.55); }
.pixwb-star:hover { background: rgba(0,0,0,.7); transform: scale(1.12); }
.pixwb-star.on { color: ${ACC}; background: rgba(0,0,0,.5); }

/* Same star on a list ROW: in the flow at the end of the line rather than
   floating over a cover, and no dark backdrop because there is no picture
   underneath it to stand out from. */
.pixwb-rowstar {
  position: static; width: ${z(20)}; height: ${z(20)}; font-size: ${z(13)};
  background: none; border-radius: 4px; margin-left: 4px;
  flex: none;                 /* never the thing a narrow row squeezes away */
}
.pixwb-rowstar:hover { background: rgba(255,255,255,.1); transform: scale(1.12); }
.pixwb-rowstar.on { background: none; }

/* the same star, in the left column and on the detail button */
.pixwb-favstar { color: ${ACC}; font-size: ${z(12)}; line-height: 1; flex: none; }
.pixwb-btnstar { color: #ffffff; margin-right: 5px; font-size: ${z(12)}; }
.pixwb-btnstar.on { color: ${ACC}; }
.pixwb-tbtn:hover .pixwb-btnstar { color: #fff; }
.pixwb-openmark {
  position: absolute; top: 4px; left: 5px; width: 6px; height: 6px; border-radius: 50%;
  background: ${ACC}; box-shadow: 0 0 0 2px rgba(0,0,0,.45);
}
.pixwb-rename {
  width: 100%; box-sizing: border-box; background: #141312; border: 1px solid ${ACC};
  border-radius: 3px; color: #fff; font-family: inherit; font-size: ${z(10.5)}; padding: 2px 4px; outline: none;
}
.pixwb-empty { color: #6e6764; font-size: ${z(12)}; padding: 26px 10px; text-align: center; }

/* ── list view ───────────────────────────────────────────────── */
.pixwb-list { display: flex; flex-direction: column; }
.pixwb-row {
  display: flex; align-items: center; gap: 9px; padding: 5px 7px; border-radius: 5px;
  cursor: pointer; font-size: ${z(11.5)}; color: #b6b0ac; border: 1px solid transparent;
}
.pixwb-row:hover { background: rgba(255,255,255,.04); color: #fff; }
.pixwb-row.sel { border-color: ${ACC}; background: color-mix(in srgb, ${ACC} 12%, transparent); color: #fff; }
.pixwb-row .pixwb-rowcov { width: ${z(40)}; height: ${z(23)}; flex: none; border-radius: 3px; background: #141312; object-fit: cover; }
/* Both text cells must be allowed to SHRINK, or a long name simply pushes the
   folder and the date out past the right edge of the panel: a flex item's
   default min-width is auto, which refuses to go below its content. The name
   gets the spare room, the folder/date cell only as much as it needs, and each
   ends in an ellipsis rather than being clipped mid-letter. The full text is on
   the row's title either way. */
.pixwb-row .pixwb-rowname {
  flex: 1 1 auto; min-width: 0;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.pixwb-row .pixwb-rowfold {
  color: #6e6764; font-size: ${z(10)}; margin-left: auto; white-space: nowrap;
  flex: 0 1 auto; min-width: 0; max-width: 45%;
  overflow: hidden; text-overflow: ellipsis;
}

/* ── the tidy-up screen ──────────────────────────────────────── */
/* Replaces the card grid for "Needs tidying". Deliberately looks like a review
   list rather than a gallery: the point is reading three different problems and
   acting on each, not browsing pictures. */
.pixwb-tidy { display: flex; flex-direction: column; gap: 16px; }
.pixwb-tdintro {
  color: #8b8480; font-size: ${z(11)}; line-height: 1.5;
  border-left: 2px solid ${ACC}; padding: 2px 0 2px 9px;
}
.pixwb-tdsec { display: flex; flex-direction: column; gap: 4px; }
.pixwb-tdhead { display: flex; align-items: baseline; gap: 8px; }
.pixwb-tdtitle { color: #efe9e5; font-size: ${z(12.5)}; font-weight: 600; }
.pixwb-tdcount {
  color: ${ACC}; font-size: ${z(10.5)}; padding: 1px 6px; border-radius: 8px;
  background: color-mix(in srgb, ${ACC} 15%, transparent); white-space: nowrap;
}
.pixwb-tdblurb { color: #8b8480; font-size: ${z(11)}; line-height: 1.5; margin-bottom: 3px; }
/* A set of duplicates is bracketed, so it reads as "these belong together"
   rather than as three unrelated rows that happen to be adjacent. */
.pixwb-tdgroup {
  border: 1px solid #332f2c; border-radius: 6px; padding: 3px;
  margin-bottom: 6px; background: rgba(255,255,255,.015);
}
.pixwb-tdrow {
  display: flex; align-items: center; gap: 9px; padding: 5px 7px; border-radius: 5px;
  cursor: pointer; font-size: ${z(11.5)}; color: #b6b0ac; border: 1px solid transparent;
}
.pixwb-tdrow:hover { background: rgba(255,255,255,.04); color: #fff; }
.pixwb-tdrow.sel { border-color: ${ACC}; background: color-mix(in srgb, ${ACC} 12%, transparent); color: #fff; }
/* Same keyboard cursor a card gets, so arrowing through this screen shows where
   you are instead of only changing the pane on the right. */
.pixwb-tdrow.kbd { outline: 1px solid ${ACC}; outline-offset: 1px; }
/* A list row had no keyboard cursor either - only cards did. */
.pixwb-row.kbd { outline: 1px solid ${ACC}; outline-offset: -1px; }
.pixwb-tdrow .pixwb-rowcov { width: ${z(40)}; height: ${z(23)}; flex: none; border-radius: 3px; background: #141312; object-fit: cover; }
/* min-width:0 on the middle cell, or a long name refuses to shrink and pushes
   the buttons off the right edge - the same flex default that bit the list. */
.pixwb-tdmid { flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; gap: 1px; }
.pixwb-tdmid .pixwb-rowname { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pixwb-tdsub {
  color: #8b8480; font-size: ${z(10)};
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.pixwb-tdfold {
  color: #6e6764; font-size: ${z(10)}; flex: 0 1 auto; min-width: 0; max-width: 26%;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
/* A duplicate-set member shown only because its SET matched the search. Dimmed
   so the header's match count and the rows on screen stop looking like they
   disagree - the extra rows visibly read as context, not as matches. */
.pixwb-tdrow.pixwb-tddimmed { opacity: .5; }
.pixwb-tdrow.pixwb-tddimmed:hover { opacity: 1; }

/* flex: none so the fix is never the thing that gets squeezed away. */
.pixwb-tdacts { display: flex; gap: 4px; flex: none; }
.pixwb-tdbtn {
  background: rgba(255,255,255,.05); border: 1px solid rgba(255,255,255,.14);
  color: rgba(255,255,255,.72); font-family: inherit; font-size: ${z(10.5)};
  padding: 3px 8px; border-radius: 4px; cursor: pointer; white-space: nowrap;
}
.pixwb-tdbtn:hover { background: ${ACC}; border-color: ${ACC}; color: #fff; }
.pixwb-tdbtn.primary { border-color: color-mix(in srgb, ${ACC} 55%, transparent); color: #e8ded9; }
.pixwb-tdbtn.danger:hover { background: #a33f27; border-color: #a33f27; }

/* ── detail pane ─────────────────────────────────────────────── */
.pixwb-detail {
  width: ${z(208)}; min-width: ${z(150)}; flex: none; background: #1a1918;
  overflow-y: auto; padding: 10px;
}
.pixwb-detail.hidden { display: none; }
/* Its own grip, so long model filenames can be given room instead of wrapping
   onto three lines. Same treatment as the left divider. */
.pixwb-detgrip { width: 6px; flex: none; cursor: ew-resize; background: transparent; z-index: 2; }
.pixwb-detgrip.hidden { display: none; }
.pixwb-detgrip::after {
  content: ""; display: block; width: 1px; height: 100%; margin-left: 2px;
  background: #302d2b; transition: background .12s;
}
.pixwb-detgrip:hover::after, .pixwb-detgrip.pixwb-dragging::after {
  background: ${ACC}; width: 3px; margin-left: 1px;
}
.pixwb-detcov { width: 100%; height: ${z(104)}; border-radius: 6px; background: #141312; object-fit: cover; display: block; }
.pixwb-detname { color: #fff; font-size: ${z(12.5)}; font-weight: 600; margin: 8px 0 2px; line-height: 1.35; word-break: break-word; }
.pixwb-detpath { color: #6e6764; font-size: ${z(10)}; margin-bottom: 9px; word-break: break-word; }
.pixwb-kv { display: flex; font-size: ${z(10.5)}; color: #8e8783; padding: 2px 0; gap: 8px; }
.pixwb-kv b { color: #cfcac7; font-weight: 500; margin-left: auto; text-align: right; }
.pixwb-warn { color: #d98b5f; }
.pixwb-modlist { margin: 6px 0 9px; }
/* Filenames read best as plain light text; the accent marks the EXTENSION and
   the folder is dimmed. Two earlier goes were worse: accent text on an
   accent-tinted background was orange on orange, and an accent border round
   every chip crowded the text it was meant to help. */
.pixwb-mod {
  background: #131211; border: 1px solid #2b2826;
  border-radius: 4px; padding: 3px 6px;
  font-size: ${z(10)}; margin-bottom: 3px; word-break: break-all; line-height: 1.4;
}
/* The FOLDER is grey and the FILENAME is white, extension included. Colouring
   the extension separately was tried and only broke the name into pieces - the
   filename is one thing and reads best as one thing. */
.pixwb-mod .pixwb-moddir,
.pixwb-mod .pixwb-modsep { color: #7d7673; }
.pixwb-mod .pixwb-modname,
.pixwb-mod .pixwb-modext { color: #f2eeeb; }

/* Copy-all, on the heading rather than as another row in the list. */
.pixwb-headrow { display: flex; align-items: center; gap: 6px; }
.pixwb-headrow .pixwb-grouphead { flex: 1; padding-right: 0; }
.pixwb-copybtn {
  border: 1px solid #3d3936; background: rgba(255,255,255,.04); color: #a49d99;
  border-radius: 5px; padding: 2px 8px; cursor: pointer;
  font-family: inherit; font-size: ${z(10)}; white-space: nowrap;
  transition: background .12s, border-color .12s, color .12s;
}
.pixwb-copybtn:hover { border-color: ${ACC}; color: #fff; }
.pixwb-copybtn.done { background: #3ec371; border-color: #3ec371; color: #fff; }

/* A control that would do nothing in the current view says so, rather than
   silently ignoring the click. */
.pixwb-tbtn:disabled, .pixwb-tbtn[disabled] {
  opacity: .4; cursor: default;
}
.pixwb-tbtn:disabled:hover, .pixwb-tbtn[disabled]:hover {
  border-color: #3d3936; color: #cfcac7;
}

/* ── right-click menu (folders) ──────────────────────────────── */
.pixwb-menu {
  position: fixed; z-index: 1500; min-width: 150px; max-width: 300px; padding: 4px;
  background: #232120; border: 1px solid #3d3936; border-radius: 7px;
  box-shadow: 0 12px 30px rgba(0,0,0,.62);
  /* The "move to folder" list is as long as the user has folders, so it has to
     be able to scroll rather than run off the bottom of the screen. */
  max-height: 60vh; overflow-y: auto;
}
.pixwb-menu button.pixwb-menudanger { color: #e08a6e; }
.pixwb-menu button.pixwb-menudanger:hover { background: #a33f27; color: #fff; }
.pixwb-menu button {
  display: block; width: 100%; text-align: left; background: none; border: none;
  color: #cfcac7; font-family: inherit; font-size: ${z(11.5)}; padding: 5px 9px;
  border-radius: 5px; cursor: pointer;
}
.pixwb-menu button:hover { background: ${ACC}; color: #fff; }
.pixwb-menu button:disabled { opacity: .35; cursor: default; }
.pixwb-menu button:disabled:hover { background: none; color: #cfcac7; }
/* Arrow keys move real focus between the buttons, so the keyboard highlight is
   just :focus - styled to match :hover exactly, or the two ways of reaching the
   same entry would look like two different states. outline is cleared because
   the fill already says where you are. */
.pixwb-menu button:focus { background: ${ACC}; color: #fff; outline: none; }
.pixwb-menu button.pixwb-menudanger:focus { background: #a33f27; color: #fff; }
.pixwb-menu .pixwb-menusep { height: 1px; background: #3d3936; margin: 4px 2px; }

/* inline folder rename */
.pixwb-foldrename {
  width: 100%; box-sizing: border-box; background: #141312; border: 1px solid ${ACC};
  border-radius: 4px; color: #fff; font-family: inherit; font-size: ${z(11.5)};
  padding: 3px 6px; outline: none; margin: 1px 0;
}
.pixwb-note {
  width: 100%; box-sizing: border-box; background: #141312; border: 1px solid #3d3936;
  border-radius: 5px; color: #cfcac7; font-family: inherit; font-size: ${z(11)}; padding: 6px 7px;
  resize: vertical; min-height: 56px; outline: none;
}
.pixwb-note:focus { border-color: ${ACC}; }
.pixwb-acts { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 9px; }
.pixwb-acts .pixwb-tbtn { padding: 4px 8px; font-size: ${z(11)}; }
.pixwb-danger:hover { border-color: #c4553a !important; color: #ff9c80 !important; }

/* ── footer / keyboard hints ─────────────────────────────────── */
.pixwb-foot {
  display: flex; align-items: center; gap: 13px; flex: none; flex-wrap: wrap;
  padding: 6px 12px 6px 10px; background: #1d1c1b; border-top: 1px solid #302d2b;
  font-size: ${z(10)}; color: #6e6764;
}
.pixwb-footsp { flex: 1; }
.pixwb-helpbtn {
  border: 1px solid #3d3936; background: rgba(255,255,255,.04); color: ${ACC};
  border-radius: 5px; width: ${z(22)}; height: ${z(20)}; cursor: pointer; margin-right: 7px;
  font-family: inherit; font-size: ${z(12)}; font-weight: 700; line-height: 1; padding: 0;
  transition: background .12s, border-color .12s, color .12s;
}
.pixwb-helpbtn:hover { background: ${ACC}; border-color: ${ACC}; color: #fff; }
.pixwb-ver {
  border: 1px solid #3d3936; background: rgba(255,255,255,.04); color: #a49d99;
  border-radius: 5px; padding: 2px 8px; cursor: pointer;
  font-family: inherit; font-size: ${z(10)}; white-space: nowrap;
  transition: background .12s, border-color .12s, color .12s;
}
.pixwb-ver:hover { border-color: ${ACC}; color: #fff; }
.pixwb-vername { color: ${ACC}; font-weight: 600; }
.pixwb-ver:hover .pixwb-vername { color: #fff; }
.pixwb-foot b {
  background: #2a2726; border: 1px solid #3d3936; border-radius: 3px; padding: 1px 5px;
  color: #a49d99; font-weight: 500;
}
.pixwb-grip {
  position: absolute; right: 0; bottom: 0; width: 16px; height: 16px; cursor: nwse-resize; z-index: 4;
}
.pixwb-grip::after {
  content: ""; position: absolute; right: 3px; bottom: 3px; width: 7px; height: 7px;
  border-right: 2px solid #4a4542; border-bottom: 2px solid #4a4542;
}

/* ── toast ───────────────────────────────────────────────────── */
.pixwb-toast {
  position: absolute; left: 50%; transform: translateX(-50%); bottom: 14px; z-index: 6;
  background: #232120; border: 1px solid #3d3936; border-left: 3px solid ${ACC};
  border-radius: 6px; padding: 7px 13px; font-size: ${z(11.5)}; color: #ddd6d2;
  box-shadow: 0 8px 20px rgba(0,0,0,.5); max-width: 80%;
}
`;
  document.head.appendChild(style);
}
