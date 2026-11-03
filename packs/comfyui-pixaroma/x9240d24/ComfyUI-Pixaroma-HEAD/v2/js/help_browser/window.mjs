// ╔═══════════════════════════════════════════════════════════════╗
// ║  Pixaroma Help browser - the floating window frame            ║
// ╚═══════════════════════════════════════════════════════════════╝
//
// A draggable, resizable panel appended to document.body. It is NOT a node and
// NOT a DOM widget, so none of the Nodes 2.0 widget rules apply to it, and it
// renders identically in both renderers.
//
// Two deliberate behaviours, both different from js/shared/help.mjs's popup:
//
//   1. It STAYS OPEN across workflow switches. The small per-node popup closes
//      on loadGraphData because it belongs to one node; this window belongs to
//      the app. Anything it shows that depends on the open graph must therefore
//      be re-read on render, never cached across a switch.
//   2. It writes NOTHING that gets serialized into a workflow - no node.size,
//      no properties, no slots - so opening and closing it can never make a
//      clean workflow ask "Save Changes?" (Vue Compat #18).
//
// Position and size live in UNREGISTERED settings (Vue Compat #20: unregistered
// ids persist fine and add no rows to the Settings panel).

import { app } from "../../../scripts/app.js";
import { globalAccent, BRAND } from "../shared/index.mjs";
import { el, makeRect, startDrag } from "../shared/floating_window.mjs";
import { injectHelpBrowserCSS } from "./css.mjs";

// No icon constants here on purpose. css.mjs injects its stylesheet ONCE and
// therefore owns every value in it (see pattern #2) - a second copy sitting
// here is an invitation to pass one in again and get `url("undefined")`.
const RECT_SETTING = "Pixaroma.Help.Rect";

const MIN_W = 420;
const MIN_H = 280;

// The size it opens at on a screen with room for it. Most people are on a big
// monitor, and at this size two columns of cards and a full article both read
// comfortably without anyone having to resize it first. On a smaller screen it
// shrinks to fit rather than hanging off the edge (see defaultRect).
const PREF_W = 980;
const PREF_H = 756;
// Breathing room kept between the window and the edge of the browser, so the
// canvas is still visible around it and the corner grip is never flush.
const EDGE = 24;
// Where it opens from, when there is room. Top left rather than centred: this
// is a panel you read while you work on the canvas to the right of it.
const HOME_X = 60;
const HOME_Y = 70;

// The sidebar is DRAGGABLE. Several page names are longer than any sensible
// default width ("Buttons or nodes missing?", "Image Composer Pixaroma"), so
// they were ellipsed with no way to read them - and the first thing anyone does
// is try to drag the divider, which did nothing. SIDE_DEF is the width it opens
// at; SIDE_MIN keeps it usable; the max is a share of the window so the article
// can never be squeezed to nothing on a small screen.
// 204 is the width the divider was actually settled at in use, and it is the
// number that matters: it is the point where every name under "Start here"
// fits, which is the first thing anyone reads. Long node names still clip and
// that is deliberate (see pattern #23) - the divider is there to be dragged.
const SIDE_DEF = 204;
const SIDE_MIN = 130;
const SIDE_MAX_FRAC = 0.55;

// Sizing, position, sidebar width and the viewport clamping that keeps a window
// saved on a big monitor reachable on a laptop. The behaviour lives in
// js/shared/floating_window.mjs so the Workflows panel cannot get it subtly
// wrong; the NUMBERS stay here, because they are this window's own.
const RECT = makeRect({
  settingKey: RECT_SETTING,
  minW: MIN_W, minH: MIN_H,
  prefW: PREF_W, prefH: PREF_H,
  edge: EDGE, homeX: HOME_X, homeY: HOME_Y,
  sideDef: SIDE_DEF, sideMin: SIDE_MIN, sideMaxFrac: SIDE_MAX_FRAC,
});
const { clampRect, readRect, saveRect, sideMax, floorY } = RECT;

// Re-exported: actions/content/controls/index all import `el` from here.
export { el };

export function createHelpWindow({ onRender, onClose }) {
  injectHelpBrowserCSS();

  const win = el("div", "pixhb-win");
  win.style.display = "none";

  // ── title bar ──
  const title = el("div", "pixhb-title");
  // The Pixaroma logo mark rather than the crown emoji: this is an app panel,
  // not a node, so it should carry the brand rather than the node-menu icon.
  // Drawn as a mask so it takes the accent colour instead of being locked to
  // orange while everything around it recolours.
  const name = el("div", "pixhb-name");
  name.append(el("span", "pixhb-logo"), el("span", null, "Pixaroma Help"));
  const sp = el("div", "pixhb-sp");
  const closeBtn = el("button", "pixhb-wbtn", "✕");
  closeBtn.type = "button";
  closeBtn.title = "Close (Esc)";
  title.append(name, sp, closeBtn);

  // ── toolbar row (filled by content.mjs) ──
  const bar = el("div", "pixhb-bar");

  // ── body ──
  const body = el("div", "pixhb-body");
  const side = el("div", "pixhb-side");
  // The divider between the list and the page. It is a real handle because
  // people TRY to drag it: several page names are longer than any default width
  // and were ellipsed with no way to widen the column and read them.
  const sideGrip = el("div", "pixhb-sidegrip");
  sideGrip.title = "Drag to resize the list. Double-click to reset.";
  const main = el("div", "pixhb-main");
  body.append(side, sideGrip, main);

  // ── footer bar (filled by index.js) ──
  // Part of the FRAME, not of the home screen, so the version and the places to
  // ask are visible on every page. It used to live at the bottom of the home
  // screen only, which meant a page telling someone to include their version
  // had to send them to another screen to find it.
  const foot = el("div", "pixhb-foot");

  const grip = el("div", "pixhb-grip");
  win.append(title, bar, body, foot, grip);
  document.body.appendChild(win);

  let rect = readRect();
  const applyRect = () => {
    win.style.left = rect.x + "px";
    win.style.top = rect.y + "px";
    win.style.width = rect.w + "px";
    win.style.height = rect.h + "px";
    // Re-clamped on every apply, not just on drag: making the WINDOW narrower
    // must also pull the sidebar in, or the article ends up with no room.
    rect.sw = Math.max(SIDE_MIN, Math.min(rect.sw ?? SIDE_DEF, sideMax(rect.w)));
    side.style.width = rect.sw + "px";
  };
  applyRect();

  // ── dragging, for the title bar, the resize grip and the sidebar divider ──
  //
  // startDrag itself is shared (js/shared/floating_window.mjs): it holds the
  // pointer capture plus the buttons-are-up guard, without which a drag whose
  // release goes missing leaves the panel stuck to the cursor forever. All that
  // belongs to this window is what happens when a drag FINISHES.
  const onDragEnd = () => {
    title.classList.remove("pixhb-dragging");
    saveRect(rect);
  };

  title.addEventListener("pointerdown", (e) => {
    if (e.target.closest(".pixhb-wbtn")) return;
    const ox = e.clientX - win.offsetLeft;
    const oy = e.clientY - win.offsetTop;
    if (!startDrag(title, e, (ev) => {
      rect.x = Math.max(0, Math.min(ev.clientX - ox, window.innerWidth - Math.min(rect.w, 160)));
      rect.y = Math.max(floorY(), Math.min(ev.clientY - oy, window.innerHeight - 40));
      applyRect();
    }, onDragEnd)) return;
    title.classList.add("pixhb-dragging");
  });

  grip.addEventListener("pointerdown", (e) => {
    const left = win.offsetLeft, top = win.offsetTop;
    // Where inside the grip the pointer actually landed. Without this the
    // corner jumps to sit exactly under the cursor the moment you grab it,
    // which reads as the window twitching. The title drag already does this.
    const ox = e.clientX - (left + win.offsetWidth);
    const oy = e.clientY - (top + win.offsetHeight);
    startDrag(grip, e, (ev) => {
      rect.w = Math.max(MIN_W, Math.min(ev.clientX - ox - left, window.innerWidth - left));
      rect.h = Math.max(MIN_H, Math.min(ev.clientY - oy - top, window.innerHeight - top));
      applyRect();
    }, onDragEnd);
    e.stopPropagation();
  });

  // The sidebar divider. Goes through the SAME startDrag as the other two, so
  // it inherits pointer capture and the buttons-are-up guard - a drag that
  // loses its release must not leave the divider stuck to the cursor either
  // (pattern #4: synthetic events do not reproduce that, so do not hand-roll a
  // third copy of the drag logic here).
  sideGrip.addEventListener("pointerdown", (e) => {
    const bodyLeft = body.getBoundingClientRect().left;
    startDrag(sideGrip, e, (ev) => {
      rect.sw = Math.round(Math.max(SIDE_MIN, Math.min(ev.clientX - bodyLeft, sideMax(rect.w))));
      side.style.width = rect.sw + "px";
    }, onDragEnd);
    sideGrip.classList.add("pixhb-dragging");
    e.stopPropagation();
  });
  // startDrag's own end() clears the window-drag class; this one is ours.
  ["pointerup", "pointercancel", "lostpointercapture"].forEach((t) =>
    sideGrip.addEventListener(t, () => sideGrip.classList.remove("pixhb-dragging")));
  sideGrip.addEventListener("dblclick", () => {
    rect.sw = SIDE_DEF;
    applyRect();
    saveRect(rect);
  });

  // Keep the window reachable if the browser window shrinks under it.
  window.addEventListener("resize", () => {
    if (win.style.display === "none") return;
    rect = clampRect(rect);
    applyRect();
  });

  // Esc closes, but only when the focus is inside the window - otherwise this
  // would swallow Escape for the whole app.
  win.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { e.stopPropagation(); api.close(); }
  });

  // Clicks inside must not reach the canvas underneath, or reading the help
  // would deselect whatever the user had selected before they opened it.
  win.addEventListener("pointerdown", (e) => e.stopPropagation());

  const api = {
    el: win, bar, side, main, title, foot,
    isOpen: () => win.style.display !== "none",
    open() {
      // Re-read the accent every open so the window follows a colour the user
      // changed while it was shut.
      win.style.setProperty("--pix-acc", globalAccent() || BRAND);
      rect = clampRect(rect);
      applyRect();
      win.style.display = "flex";
      onRender?.();
      // Focus something inside so Esc and typing land here, not on the canvas.
      setTimeout(() => bar.querySelector("input")?.focus(), 20);
    },
    close() {
      win.style.display = "none";
      // Clear the search box, or reopening shows a leftover query above an
      // unrelated article and the next keystroke jumps back to old results.
      const q = bar.querySelector("input");
      if (q) q.value = "";
      onClose?.();
    },
    toggle() { api.isOpen() ? api.close() : api.open(); },
    destroy() { win.remove(); },
  };

  closeBtn.addEventListener("click", () => api.close());
  return api;
}
