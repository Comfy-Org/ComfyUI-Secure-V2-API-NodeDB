// ╔═══════════════════════════════════════════════════════════════╗
// ║  Pixaroma Workflows - the right-click menu                     ║
// ╚═══════════════════════════════════════════════════════════════╝
//
// One menu, used by both the folder column and the workflow cards. Started life
// inside folders.mjs and moved out when the cards wanted the same thing: a
// second copy would have been a second set of the dismiss rules below to get
// subtly wrong.

import { el } from "./window.mjs";

let menuEl = null;
let cleanup = null;
let returnFocus = null;

// Where focus goes when a menu closes, set once by the panel. A DEFAULT rather
// than an argument at each call site, because there are four of them and the
// failure mode of forgetting it at a fifth is silent: the menu still works, the
// panel just goes deaf to the keyboard afterwards and nobody connects the two.
let focusHome = null;
export function setMenuFocusHome(fn) { focusHome = fn; }

export function closeContextMenu() {
  if (menuEl) { menuEl.remove(); menuEl = null; }
  if (cleanup) { cleanup(); cleanup = null; }
  // Hand focus back to the panel. Without this, dismissing the menu leaves it
  // on a button that has just been removed, which means document.body - and
  // from there no keypress reaches the panel at all, so the arrow keys silently
  // stop working after any right-click (the same trap as clicking a card).
  //
  // A CALLBACK, not the element that had focus when the menu opened: by then it
  // is already too late to read. mousedown runs before contextmenu and blurs
  // whatever was focused, so document.activeElement is body by the time the
  // menu is built, and "restore" restored nothing. Measured, after the arrow
  // keys worked but Escape still left the panel deaf.
  const back = returnFocus;
  returnFocus = null;
  try { back?.(); } catch { /* the panel went away underneath us */ }
}

/**
 * @param items   [{label, fn, disabled, danger}] - null entries draw a separator
 * @param onClose called once the menu is gone, to put focus back in the panel
 */
export function openContextMenu(x, y, items, onClose) {
  closeContextMenu();
  menuEl = el("div", "pixwb-menu");
  for (const it of items) {
    if (!it) { menuEl.append(el("div", "pixwb-menusep")); continue; }
    const b = el("button", it.danger ? "pixwb-menudanger" : null, it.label);
    b.type = "button";
    if (it.disabled) b.disabled = true;
    else b.addEventListener("click", () => { closeContextMenu(); it.fn(); });
    menuEl.append(b);
  }
  document.body.append(menuEl);

  // Keep it on screen: a menu opened near an edge must not run off it.
  const r = menuEl.getBoundingClientRect();
  menuEl.style.left = Math.round(Math.max(6, Math.min(x, window.innerWidth - r.width - 8))) + "px";
  menuEl.style.top = Math.round(Math.max(6, Math.min(y, window.innerHeight - r.height - 8))) + "px";

  // CAPTURE phase. A menu action re-renders the panel, which detaches the
  // clicked element, so a bubble-phase "was this inside the menu" test would
  // already read false and dismiss things in the wrong order.
  const away = (e) => { if (menuEl && !menuEl.contains(e.target)) closeContextMenu(); };

  // ── keyboard ──
  // The buttons are real <button>s, so moving real FOCUS is the whole
  // implementation: Enter and Space already activate a focused button, screen
  // readers already announce it, and the highlight is plain :focus. Tracking an
  // index and a .kbd class instead would have re-implemented all three.
  const options = () => [...menuEl.querySelectorAll("button:not(:disabled)")];
  const step = (delta) => {
    const list = options();
    if (!list.length) return;
    const at = list.indexOf(document.activeElement);
    // -1 (nothing in the menu focused yet) with delta -1 gives the LAST item,
    // which is what Up on a fresh menu should do.
    const next = at < 0 ? (delta > 0 ? 0 : list.length - 1)
                        : (at + delta + list.length) % list.length;
    list[next].focus();
  };
  const keys = (e) => {
    if (!menuEl) return;
    switch (e.key) {
      case "Escape":   e.stopPropagation(); closeContextMenu(); break;
      case "ArrowDown": e.preventDefault(); e.stopPropagation(); step(1); break;
      case "ArrowUp":   e.preventDefault(); e.stopPropagation(); step(-1); break;
      case "Home":      e.preventDefault(); e.stopPropagation(); options()[0]?.focus(); break;
      case "End":       e.preventDefault(); e.stopPropagation(); options().pop()?.focus(); break;
      // Tab would move focus out to whatever is behind the menu while it is
      // still open, leaving keystrokes going somewhere invisible.
      case "Tab":       e.preventDefault(); e.stopPropagation(); step(e.shiftKey ? -1 : 1); break;
      default: break;
    }
  };

  // Deferred, or the very pointerdown that opened the menu closes it again.
  // The id is KEPT so cleanup can cancel it: a menu closed before the timer
  // fires would otherwise still get its listeners attached afterwards, and
  // because they close over the shared menuEl rather than a snapshot they come
  // back to life for the NEXT menu - two live copies, so one ArrowDown moves
  // two rows. Not reachable at human clicking speed, but free to rule out.
  const armed = setTimeout(() => {
    document.addEventListener("pointerdown", away, true);
    document.addEventListener("keydown", keys, true);
  }, 0);
  cleanup = () => {
    clearTimeout(armed);
    document.removeEventListener("pointerdown", away, true);
    document.removeEventListener("keydown", keys, true);
  };

  // Focused only once the listeners are in place, and only now is it worth
  // arming the hand-back.
  returnFocus = onClose || focusHome;
  options()[0]?.focus();
}
