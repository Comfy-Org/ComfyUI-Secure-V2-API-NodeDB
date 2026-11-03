// ╔═══════════════════════════════════════════════════════════════╗
// ║  Pixaroma Help browser - styles                               ║
// ╚═══════════════════════════════════════════════════════════════╝
//
// One injected stylesheet for the floating help window and the toolbar button.
// Everything is scoped under `.pixhb-` so it cannot leak into a node body.
//
// Colour rule (convention #19): NOTHING here hardcodes the Pixaroma orange.
// Every accent uses `var(--pix-acc, #f66744)`, and the window element gets that
// variable set from the master accent each time it opens, so the browser
// follows the user's chosen colour like the rest of the suite. A leftover
// rgba(246,103,68,...) would stay orange while everything around it recoloured,
// which reads as a bug.

import { PIXAROMA_LOGO } from "../shared/index.mjs";
import { pixAsset } from "../shared/api_url.mjs";

const CSS_ID = "pixaroma-help-browser-css";
const ACC = "var(--pix-acc, #f66744)";

// The icons live HERE rather than being passed in. The stylesheet is injected
// exactly once, by whichever caller gets there first, so an icon supplied by a
// later caller would silently never appear. That is not hypothetical: the
// toolbar mounts before the window is ever built, so passing the logo from the
// window produced `mask: url("undefined")`, which masks the element out
// entirely - it computes as "a mask is present" while painting nothing.
const QUESTION_ICON = pixAsset("icons/note/question-mark.svg");
const LOGO_ICON = PIXAROMA_LOGO;

export function injectHelpBrowserCSS() {
  if (document.getElementById(CSS_ID)) return;
  const style = document.createElement("style");
  style.id = CSS_ID;
  style.textContent = `
/* ── toolbar button (sits beside Align) ─────────────────────── */
.pixhb-btn .pixhb-btn-icon {
  display: inline-block; width: 18px; height: 18px;
  background-color: currentColor; pointer-events: none;
  mask-image: url(${QUESTION_ICON}); -webkit-mask-image: url(${QUESTION_ICON});
  mask-size: contain; -webkit-mask-size: contain;
  mask-repeat: no-repeat; -webkit-mask-repeat: no-repeat;
  mask-position: center; -webkit-mask-position: center;
}
/* Off / on exactly like the Align button beside it: grey when the window is
   closed, accent when it is open. Same values as js/align/index.js so the two
   toggles in that toolbar are visibly the same control. */
.pixhb-btn {
  background-color: #2a2c2e !important; color: #ddd !important; border-color: #444 !important;
}
.pixhb-btn:hover { background-color: #3a3d40 !important; }
.pixhb-btn.pixhb-btn-open {
  background-color: ${ACC} !important; color: #fff !important; border-color: ${ACC} !important;
}
.pixhb-btn.pixhb-btn-open:hover { background-color: ${ACC} !important; filter: brightness(1.08); }


/* ── the floating window ────────────────────────────────────── */
.pixhb-win {
  position: fixed; z-index: 1400;
  background: #141312; border: 1px solid #3d3936; border-radius: 10px;
  box-shadow: 0 24px 70px rgba(0,0,0,.62);
  display: flex; flex-direction: column; overflow: hidden;
  color: #cfcac7; font-family: inherit; font-size: 13px; line-height: 1.55;
  -webkit-font-smoothing: antialiased;
}
.pixhb-win * { box-sizing: border-box; }

.pixhb-title {
  display: flex; align-items: center; gap: 8px; flex: none;
  padding: 8px 10px; background: #232120; border-bottom: 1px solid #302d2b;
  cursor: grab; user-select: none;
}
.pixhb-title.pixhb-dragging { cursor: grabbing; }
.pixhb-title .pixhb-name {
  font-weight: 600; color: #fff; font-size: 12.5px;
  display: flex; align-items: center; gap: 7px;
}
.pixhb-title .pixhb-logo {
  display: inline-block; width: 15px; height: 15px; flex: none;
  background-color: ${ACC};
  mask: url("${LOGO_ICON}") center / contain no-repeat;
  -webkit-mask: url("${LOGO_ICON}") center / contain no-repeat;
}
.pixhb-title .pixhb-sp { flex: 1; }
.pixhb-wbtn {
  width: 22px; height: 22px; border-radius: 4px; border: none; flex: none;
  background: rgba(255,255,255,.05); color: #a49d99; cursor: pointer;
  font-size: 12px; display: grid; place-items: center; padding: 0;
}
.pixhb-wbtn:hover { background: ${ACC}; color: #fff; }
.pixhb-wbtn:focus-visible { outline: 2px solid ${ACC}; outline-offset: 1px; }

.pixhb-bar {
  display: flex; align-items: center; gap: 7px; flex: none;
  padding: 8px 10px; background: #1d1c1b; border-bottom: 1px solid #302d2b;
}
.pixhb-nav {
  width: 24px; height: 24px; flex: none; border-radius: 5px; padding: 0;
  border: 1px solid #3d3936; background: rgba(255,255,255,.04); color: #8e8783;
  cursor: pointer; font-size: 12px; display: grid; place-items: center;
}
.pixhb-nav:hover:not(:disabled) { border-color: ${ACC}; color: #fff; }
.pixhb-nav:disabled { opacity: .3; cursor: default; }

.pixhb-search { position: relative; flex: 1; min-width: 0; }
.pixhb-search input {
  width: 100%; background: #141312; border: 1px solid #3d3936; color: #cfcac7;
  border-radius: 5px; padding: 6px 10px 6px 28px; font-size: 12px; font-family: inherit; outline: none;
}
.pixhb-search input::placeholder { color: #6e6764; }
.pixhb-search input:focus { border-color: ${ACC}; }
.pixhb-search::before {
  content: ""; position: absolute; left: 9px; top: 50%;
  width: 12px; height: 12px; transform: translateY(-50%); background: #7d7673;
  -webkit-mask: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='2.4' stroke-linecap='round'><circle cx='11' cy='11' r='7'/><path d='M20 20l-4-4'/></svg>") center/contain no-repeat;
  mask: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='2.4' stroke-linecap='round'><circle cx='11' cy='11' r='7'/><path d='M20 20l-4-4'/></svg>") center/contain no-repeat;
}

/* position:relative so the toast can anchor to the BODY rather than to the
   window. See the toast rule at the bottom for why that matters. */
.pixhb-body { flex: 1; display: flex; min-height: 0; position: relative; }
/* Width is set inline from the saved rect and is user-draggable, so no width
   here - only the floor, in case the inline value is ever missing. */
.pixhb-side {
  width: 200px; min-width: 130px; flex: none; background: #1d1c1b;
  overflow-y: auto; padding: 8px 5px; min-height: 0;
}
/* The draggable divider. Visually a 1px line like the old border, with a wider
   invisible grab area either side so it is easy to hit. */
.pixhb-sidegrip {
  flex: none; width: 7px; margin: 0 -3px; cursor: ew-resize; position: relative;
  background: transparent; z-index: 2;
}
.pixhb-sidegrip::before {
  content: ""; position: absolute; top: 0; bottom: 0; left: 3px; width: 1px;
  background: #302d2b; transition: background .12s;
}
.pixhb-sidegrip:hover::before, .pixhb-sidegrip.pixhb-dragging::before {
  background: ${ACC}; left: 2px; width: 3px;
}
.pixhb-main { flex: 1; overflow-y: auto; min-height: 0; }
.pixhb-pad { padding: 14px 18px 28px; }

.pixhb-grip { position: absolute; right: 0; bottom: 0; width: 16px; height: 16px; cursor: nwse-resize; }
.pixhb-grip::after {
  content: ""; position: absolute; right: 3px; bottom: 3px; width: 7px; height: 7px;
  border-right: 2px solid #5c5653; border-bottom: 2px solid #5c5653;
}

/* ── sidebar nav ────────────────────────────────────────────── */
.pixhb-group { margin-bottom: 1px; }
.pixhb-gbtn {
  width: 100%; text-align: left; background: none; border: none; cursor: pointer;
  color: #cfcac7; font-weight: 600; font-size: 11.5px; font-family: inherit; padding: 5px 7px; border-radius: 5px;
  display: flex; align-items: center; gap: 6px;
}
.pixhb-gbtn:hover { background: rgba(255,255,255,.05); }
.pixhb-gbtn .pixhb-cnt { margin-left: auto; font-size: 9.5px; color: #8e8783; font-variant-numeric: tabular-nums; }
.pixhb-gbtn .pixhb-arw { font-size: 8px; color: #8e8783; transition: transform .15s; }
.pixhb-group.pixhb-open .pixhb-arw { transform: rotate(90deg); }
.pixhb-items { display: none; padding: 1px 0 5px 18px; }
.pixhb-group.pixhb-open .pixhb-items { display: block; }
.pixhb-item {
  display: block; width: 100%; text-align: left; background: none; border: none;
  cursor: pointer; color: #8e8783; font-size: 11.5px; font-family: inherit; padding: 3px 7px;
  border-radius: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.pixhb-item:hover { color: #cfcac7; background: rgba(255,255,255,.04); }
.pixhb-item.pixhb-on {
  color: #fff; background: color-mix(in srgb, ${ACC} 13%, transparent);
  box-shadow: inset 2px 0 0 ${ACC};
}

/* ── shared bits ────────────────────────────────────────────── */
.pixhb-h {
  font-size: 9.5px; font-weight: 700; color: ${ACC}; text-transform: uppercase;
  letter-spacing: .09em; margin: 0 0 6px; font-family: monospace;
}
.pixhb-btn2 {
  font-size: 11.5px; font-family: inherit; padding: 5px 10px; border-radius: 5px; cursor: pointer;
  border: 1px solid #3d3936; background: rgba(255,255,255,.04); color: #cfcac7;
  transition: background .12s, border-color .12s, color .12s; white-space: nowrap;
}
.pixhb-btn2:hover { background: ${ACC}; border-color: ${ACC}; color: #fff; }
.pixhb-btn2.pixhb-primary { background: ${ACC}; border-color: ${ACC}; color: #fff; }
.pixhb-btn2.pixhb-primary:hover { filter: brightness(1.1); }
.pixhb-btn2:focus-visible { outline: 2px solid ${ACC}; outline-offset: 1px; }
.pixhb-win code {
  font-family: monospace; font-size: 11px; background: rgba(255,255,255,.08);
  border-radius: 3px; padding: 1px 5px; color: #ffd2c4;
}
.pixhb-win mark { background: color-mix(in srgb, ${ACC} 26%, transparent); color: #fff; border-radius: 2px; padding: 0 1px; }
.pixhb-empty { text-align: center; color: #8e8783; padding: 28px 12px; font-size: 12px; }

/* ── home screen ────────────────────────────────────────────── */
.pixhb-strip { display: flex; gap: 6px; overflow-x: auto; padding-bottom: 5px; margin-bottom: 13px; }
.pixhb-mini {
  flex: none; display: flex; align-items: center; gap: 6px; background: #1d1c1b;
  border: 1px solid #302d2b; border-radius: 6px; padding: 5px 9px; cursor: pointer;
  color: #cfcac7; font-size: 11px; font-family: inherit; white-space: nowrap;
}
.pixhb-mini:hover { border-color: ${ACC}; color: #fff; }
.pixhb-hero {
  border: 1px solid color-mix(in srgb, ${ACC} 36%, transparent);
  background: linear-gradient(180deg, color-mix(in srgb, ${ACC} 12%, transparent), transparent);
  border-radius: 8px; padding: 13px 14px; margin-bottom: 14px;
}
.pixhb-hero h3 { margin: 0 0 3px; color: #fff; font-size: 14px; font-weight: 600; }
.pixhb-hero p { margin: 0 0 10px; color: #cfcac7; font-size: 11.5px; }
.pixhb-startgrid { display: grid; gap: 7px; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); }
.pixhb-startcard {
  background: #1d1c1b; border: 1px solid #302d2b; border-radius: 6px; padding: 9px 10px;
  cursor: pointer; text-align: left; color: inherit; display: flex; gap: 8px; align-items: flex-start;
}
.pixhb-startcard:hover { border-color: ${ACC}; }
.pixhb-startcard .pixhb-sc-n { color: #fff; font-size: 11.5px; font-weight: 600; }
.pixhb-startcard .pixhb-sc-d { color: #8e8783; font-size: 10.5px; line-height: 1.4; }
.pixhb-rowhead { display: flex; align-items: baseline; gap: 9px; margin: 14px 0 6px; flex-wrap: wrap; }
.pixhb-rowhead .pixhb-h { margin: 0; }
.pixhb-rowhead .pixhb-hint { font-size: 10.5px; color: #8e8783; }
.pixhb-chips { display: flex; gap: 5px; flex-wrap: wrap; }
.pixhb-chip {
  font-size: 11px; font-family: inherit; padding: 4px 9px; border-radius: 99px; cursor: pointer; white-space: nowrap;
  border: 1px solid #3d3936; background: transparent; color: #8e8783;
}
.pixhb-chip:hover { border-color: ${ACC}; color: #fff; }
.pixhb-chip.pixhb-on { background: ${ACC}; border-color: ${ACC}; color: #fff; }
.pixhb-grid { display: grid; gap: 8px; grid-template-columns: repeat(auto-fill, minmax(168px, 1fr)); margin-top: 7px; }
.pixhb-card {
  background: #1d1c1b; border: 1px solid #302d2b; border-radius: 7px; padding: 10px;
  cursor: pointer; text-align: left; color: inherit; display: flex; flex-direction: column;
  gap: 5px; position: relative; transition: border-color .13s, transform .13s, background .13s;
}
.pixhb-card:hover { border-color: ${ACC}; transform: translateY(-2px); background: #232120; }
.pixhb-card:focus-visible { outline: 2px solid ${ACC}; outline-offset: 2px; }
.pixhb-card-top { display: flex; align-items: center; gap: 8px; }
.pixhb-card-ic {
  width: 24px; height: 24px; border-radius: 6px; display: grid; place-items: center;
  font-size: 12px; flex: none; background: color-mix(in srgb, ${ACC} 13%, transparent);
}
.pixhb-card-n { color: #fff; font-weight: 600; font-size: 12px; line-height: 1.25; }
.pixhb-card-d { color: #8e8783; font-size: 10.5px; line-height: 1.45; }
.pixhb-card-cat {
  font-family: monospace; font-size: 8.5px; letter-spacing: .06em; text-transform: uppercase;
  color: #8e8783; margin-top: auto; padding-top: 3px; display: flex; align-items: center;
  gap: 5px; flex-wrap: wrap;
}
.pixhb-badge {
  font-family: monospace; font-size: 8px; letter-spacing: .08em; text-transform: uppercase;
  padding: 2px 5px; border-radius: 3px; background: rgba(255,255,255,.09); color: #8e8783; font-weight: 700;
}
.pixhb-star {
  position: absolute; top: 6px; right: 6px; background: none; border: none; cursor: pointer;
  color: #4b4643; font-size: 12px; line-height: 1; padding: 2px;
}
.pixhb-star:hover, .pixhb-star.pixhb-on { color: ${ACC}; }
/* ── footer bar (part of the FRAME, so it is on every page) ──── */
/* flex:none and a right pad that clears the resize grip in the corner. */
.pixhb-foot {
  display: flex; gap: 6px; flex-wrap: wrap; align-items: center; flex: none;
  padding: 7px 20px 7px 10px; background: #1d1c1b; border-top: 1px solid #302d2b;
}
.pixhb-foot .pixhb-fsp { flex: 1; min-width: 4px; }
.pixhb-flink {
  display: flex; align-items: center; gap: 6px; font-size: 11.5px; font-family: inherit; padding: 5px 9px;
  border-radius: 6px; border: 1px solid #3d3936; color: #cfcac7; cursor: pointer; background: transparent;
}
.pixhb-flink:hover { border-color: ${ACC}; color: #fff; }
.pixhb-flink.pixhb-discord:hover { background: #5865F2; border-color: #5865F2; color: #fff; }
.pixhb-flink.pixhb-yt:hover { background: #ff0033; border-color: #ff0033; color: #fff; }
.pixhb-ver {
  font-family: monospace; font-size: 10px; color: #a49d99; white-space: nowrap; cursor: pointer;
  border: 1px dashed #3d3936; padding: 5px 9px; border-radius: 5px; background: none;
}
.pixhb-ver:hover { border-color: ${ACC}; color: #fff; }
/* Links inside an article body, same look as the footer ones. */
.pixhb-linkrow { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px; }

/* ── article ────────────────────────────────────────────────── */
.pixhb-crumb {
  font-family: monospace; font-size: 10px; letter-spacing: .06em; text-transform: uppercase;
  color: #8e8783; margin-bottom: 8px;
}
.pixhb-crumb b { color: ${ACC}; font-weight: 600; }
.pixhb-arth {
  margin: 0 0 5px; font-size: 19px; color: #fff; font-weight: 600; letter-spacing: -.01em;
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}
.pixhb-vername { color: ${ACC}; font-weight: 600; }
.pixhb-ver:hover .pixhb-vername { color: #fff; }
.pixhb-articon {
  display: inline-block; width: 22px; height: 22px; vertical-align: -3px;
  margin-right: 9px; background-color: ${ACC};
  mask-size: contain; -webkit-mask-size: contain;
  mask-repeat: no-repeat; -webkit-mask-repeat: no-repeat;
  mask-position: center; -webkit-mask-position: center;
}
.pixhb-arttag { margin: 0 0 13px; color: #e2ddda; font-size: 12.5px; }
.pixhb-sect { margin-bottom: 14px; }
.pixhb-sect p { margin: 0 0 6px; color: #cfcac7; font-size: 12.5px; white-space: pre-wrap; }
.pixhb-sect ul { margin: 0; padding-left: 16px; font-size: 12.5px; }
.pixhb-sect li { margin-bottom: 3px; }
.pixhb-defs { display: grid; grid-template-columns: auto 1fr; gap: 4px 12px; align-items: baseline; font-size: 12.5px; }
.pixhb-defs dt { color: #fff; font-weight: 600; white-space: nowrap; }
.pixhb-defs dd { margin: 0; color: #bcb6b3; }
/* The bar block: a real proportional meter with a legend, for a node whose face
   carries one. Deliberately taller than the node's own bar (14 vs 8px) - here it
   is the subject of the page, not a glance-at readout.
   NB: no backticks in this file's comments - it is one big template literal. */
.pixhb-meterwrap { margin: 2px 0 4px; }
.pixhb-metercap {
  display: flex; justify-content: space-between; font-size: 11px;
  color: #9a9a9a; margin-bottom: 5px;
}
.pixhb-meter {
  height: 14px; border-radius: 4px; overflow: hidden; display: flex; background: #1d1d1d;
}
.pixhb-meter i { display: block; height: 100%; min-width: 0; }
.pixhb-meter i + i { box-shadow: inset 1px 0 0 #191919; }
.pixhb-meterkey { display: flex; flex-wrap: wrap; gap: 6px 16px; margin-top: 8px; font-size: 12px; }
.pixhb-meterkeyitem { display: flex; align-items: center; gap: 6px; color: #bcb6b3; }
.pixhb-meterkeyitem b { color: #fff; font-weight: 600; }
.pixhb-metersw { width: 12px; height: 12px; border-radius: 3px; flex: none; }
.pixhb-meternote { margin-top: 8px; font-size: 12.5px; color: #cfcac7; }
.pixhb-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.pixhb-table th {
  text-align: left; padding: 5px 8px; color: #9a9a9a; font-weight: 600; font-size: 10px;
  text-transform: uppercase; letter-spacing: .4px; border-bottom: 1px solid #3a3a3a;
}
.pixhb-table td { padding: 5px 8px; border-bottom: 1px solid #262626; vertical-align: top; color: #cfcac7; }
.pixhb-tip {
  margin-top: 4px; padding: 8px 11px; border-radius: 3px; color: #ddd; font-size: 12px;
  background: color-mix(in srgb, ${ACC} 12%, transparent); border-left: 2px solid ${ACC};
}
.pixhb-acts { display: flex; gap: 6px; flex-wrap: wrap; margin: 0 0 14px; }
.pixhb-rel { display: flex; gap: 5px; flex-wrap: wrap; }
.pixhb-relchip {
  font-size: 11px; font-family: inherit; padding: 4px 9px; border-radius: 99px; cursor: pointer;
  border: 1px solid #3d3936; background: transparent; color: #8e8783; white-space: nowrap;
}
.pixhb-relchip:hover { border-color: ${ACC}; color: #fff; }

/* ── what each control does ─────────────────────────────────── */
.pixhb-ctls { display: flex; flex-direction: column; gap: 7px; }
.pixhb-ctl { border-left: 2px solid #3a3a3a; padding: 1px 0 1px 10px; }
.pixhb-ctl-h { display: flex; align-items: baseline; gap: 7px; flex-wrap: wrap; }
.pixhb-ctl-n { color: #fff; font-weight: 600; font-size: 12.5px; }
.pixhb-ctl-t {
  font-family: monospace; font-size: 9px; letter-spacing: .05em; color: #8e8783;
  background: rgba(255,255,255,.06); border-radius: 3px; padding: 1px 5px;
}
.pixhb-ctl-opt { font-size: 9.5px; color: #8e8783; font-style: italic; }
.pixhb-ctl-d { font-family: monospace; font-size: 9.5px; color: #8e8783; margin-left: auto; }
.pixhb-ctl-tip { color: #cfcac7; font-size: 12px; margin-top: 2px; }
.pixhb-ctl-ch { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }
.pixhb-ctl-chv {
  font-size: 9.5px; padding: 1px 6px; border-radius: 3px;
  background: rgba(255,255,255,.05); color: #b4aeab;
}
.pixhb-ctl-note { color: #8e8783; font-size: 11.5px; margin: 0 0 7px; font-style: italic; }

/* ── search results ─────────────────────────────────────────── */
.pixhb-res { display: flex; align-items: center; gap: 9px; padding: 7px 9px; border-radius: 6px;
  cursor: pointer; border: 1px solid transparent; }
.pixhb-res:hover, .pixhb-res.pixhb-cur { background: #232120; border-color: #3d3936; }
.pixhb-res.pixhb-cur { box-shadow: inset 2px 0 0 ${ACC}; }
.pixhb-res-t { flex: 1; min-width: 0; }
.pixhb-res-t .pixhb-rn { color: #fff; font-size: 12px; font-weight: 600; }
.pixhb-res-t .pixhb-rd { color: #8e8783; font-size: 10.5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* ── toast ──────────────────────────────────────────────────── */
/* Anchored to .pixhb-body, NOT to the window, so it can never cover the footer
   bar however tall that gets. A hardcoded "bottom: 54px" measured against a
   one-row footer was wrong the moment the footer WRAPPED: at the minimum window
   width the links need two rows (74px) and the toast landed on top of them.
   Anchoring to the body makes the overlap structurally impossible, so a longer
   label or a wider version string cannot bring it back. */
.pixhb-toast {
  position: absolute; left: 50%; bottom: 14px; transform: translateX(-50%) translateY(8px);
  background: #111010; border: 1px solid ${ACC}; color: #fff; padding: 8px 14px; border-radius: 7px;
  font-size: 12px; opacity: 0; pointer-events: none; transition: opacity .16s, transform .16s;
  z-index: 60; max-width: 82%; box-shadow: 0 10px 30px rgba(0,0,0,.5);
}
.pixhb-toast.pixhb-on { opacity: 1; transform: translateX(-50%) translateY(0); }

/* ── the drag ghost (document-level, so NOT prefixed pixhb-card) ── */
.pixhb-dragghost {
  position: fixed; z-index: 9999; pointer-events: none; background: #252423;
  border: 1px solid ${ACC}; border-radius: 7px; padding: 7px 11px; color: #fff;
  font: 600 11.5px sans-serif; box-shadow: 0 10px 26px rgba(0,0,0,.45); opacity: .95;
}

@media (prefers-reduced-motion: reduce) {
  .pixhb-win *, .pixhb-toast { transition: none !important; }
}
`;
  document.head.appendChild(style);
}
