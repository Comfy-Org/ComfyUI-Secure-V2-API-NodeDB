// ╔═══════════════════════════════════════════════════════════════╗
// ║  Pixaroma Workflows - the cards                                ║
// ╚═══════════════════════════════════════════════════════════════╝
//
// Grid of picture cards, or a dense list once somebody has hundreds. Single
// click selects, double click OPENS (not renames - renaming is F2 or the
// right-click menu), and a card can be dragged onto a folder in the left
// column. The help text once described a double-click rename that has never
// existed, copied out of an earlier version of this comment.

import { el, markRendering, isRendering } from "./window.mjs";
import { drawMap, coverFor } from "./cover.mjs";
import { passComfyShortcut } from "../shared/text_shortcuts.mjs";

const fmtWhen = (secs) => {
  if (!secs) return "";
  const d = (Date.now() - secs * 1000) / 1000;
  if (d < 90) return "just now";
  if (d < 3600) return Math.round(d / 60) + " min ago";
  if (d < 86400) return Math.round(d / 3600) + "h ago";
  if (d < 86400 * 7) return Math.round(d / 86400) + " days ago";
  return new Date(secs * 1000).toLocaleDateString();
};

/** Cover element for one entry: a real picture when we have one, otherwise the
 *  drawn graph map. The map is a canvas, so it is painted after layout when its
 *  box has a real width. */
export function coverEl(entry, state, cls) {
  const c = coverFor(entry, state.meta);
  if (c.kind === "image") {
    const img = el("img", cls);
    img.loading = "lazy";
    img.src = c.url;
    img.alt = "";
    // A cover recorded from an output that has since been deleted must not
    // leave a broken-image icon in the grid: fall back to the drawn map.
    img.addEventListener("error", () => {
      const cv = el("canvas", cls);
      img.replaceWith(cv);
      requestAnimationFrame(() => drawMap(cv, entry.map));
    }, { once: true });
    return img;
  }
  const cv = el("canvas", cls);
  requestAnimationFrame(() => drawMap(cv, entry.map));
  return cv;
}

export function renderGrid(main, state, H) {
  // The clear is what removes an open rename box, and it fires that box's blur
  // SYNCHRONOUSLY - so the flag has to be up across exactly this statement.
  // Self-protecting rather than relying on the caller to wrap it.
  markRendering(() => { main.textContent = ""; });
  const list = state.visible;

  if (!list.length) {
    main.append(el("div", "pixwb-empty", state.query
      ? `Nothing matches "${state.query}".`
      : "Nothing in here yet."));
    dropRename(true);              // no cards, so nothing to put a rename box on
    return;
  }

  const wrap = el("div", state.view === "list" ? "pixwb-list" : "pixwb-grid");
  const openNow = new Set(state.openPaths);

  for (const entry of list) {
    const card = el("div", state.view === "list" ? "pixwb-row" : "pixwb-card");
    card.dataset.rel = entry.rel;
    if (state.selected.has(entry.rel)) card.classList.add("sel");
    if (state.kbdRel === entry.rel) card.classList.add("kbd");
    card.title = entry.error ? `${entry.name}\n${entry.error}` : entry.name;

    if (state.view === "list") {
      card.append(coverEl(entry, state, "pixwb-rowcov"));
      card.append(el("span", "pixwb-rowname", entry.name));
      const right = el("span", "pixwb-rowfold",
        `${entry.folder || ""}  ${fmtWhen(entry.modified)}`.trim());
      card.append(right);
    } else {
      card.append(coverEl(entry, state, "pixwb-cov"));
      const nm = el("div", "pixwb-cardname", entry.name);
      card.append(nm);
      card.append(el("div", "pixwb-cardmeta",
        entry.error ? "unreadable" : `${fmtWhen(entry.modified)} · ${entry.node_count} nodes`));
    }

    if (openNow.has(entry.rel)) {
      const mark = el("div", "pixwb-openmark");
      mark.title = "Open right now";
      card.append(mark);
    }

    const fav = state.favourites.has(entry.rel);
    const list = state.view === "list";
    const star = el("div", "pixwb-star" + (list ? " pixwb-rowstar" : "") + (fav ? " on" : ""),
                    fav ? "★" : "☆");
    star.title = fav ? "Remove from favourites" : "Add to favourites";
    star.addEventListener("click", (e) => { e.stopPropagation(); H.onStar(entry); });
    // Two quick clicks on the star would otherwise reach the card's dblclick
    // and open the workflow, which is not what anyone means by tapping a star.
    star.addEventListener("dblclick", (e) => e.stopPropagation());
    // In BOTH views. List view used to have no star at all, so switching to it
    // hid which workflows were favourites and left no way to set one without
    // going through the detail pane - while the same star sits on every card,
    // in the left column and on the detail button.
    card.append(star);

    card.addEventListener("click", (e) => H.onSelect(entry, e));
    card.addEventListener("dblclick", () => H.onOpen(entry));
    card.addEventListener("contextmenu", (e) => { e.preventDefault(); H.onContext(entry, e); });

    // ── drag onto a folder ──
    card.draggable = true;
    card.addEventListener("dragstart", (e) => {
      // Never hijack a click on the star or a rename box: a drag starting there
      // steals the interaction and the user cannot tell why.
      const t = e.target;
      const tag = (t.tagName || "").toLowerCase();
      if (tag === "input" || tag === "textarea" || t.classList?.contains("pixwb-star")) {
        e.preventDefault();
        return;
      }
      H.onDragStart(entry, e);
    });

    wrap.append(card);
  }
  main.append(wrap);
  // Last, once every card is in the DOM: a rename that was open before this
  // render goes back where it was, with what had been typed still in it.
  restoreRename(main);
}

// A rename that is happening RIGHT NOW, so it can survive the grid being
// rebuilt underneath it. Anything at all can trigger a re-render while the box
// is open - a background run finishing and refreshing a cover, a favourite
// toggled from the detail pane - and every one of those used to throw the
// half-typed name away without a word.
let activeRename = null;

// Told to the user when a rename is abandoned because its row went away. Set
// once by the panel; without it the typing just vanished with no explanation.
let onRenameLost = null;
export function setRenameLostNotifier(fn) { onRenameLost = fn; }

/** Forget any rename in progress, WITHOUT committing it.
 *
 *  Called when there is no row left to put the box back on, and when the panel
 *  closes. The close case matters: hiding the panel suppresses the commit (the
 *  render flag is up) but used to leave this state set, so reopening resurrected
 *  the box - with focus - still holding the half-typed name. The next keystroke
 *  or click then committed a rename the user had walked away from. */
export function dropRename(tell) {
  if (!activeRename) return;
  const { currentName } = activeRename;
  activeRename = null;
  if (tell) { try { onRenameLost?.(currentName); } catch { /* no panel */ } }
}

/** Put the rename box back after a re-render. Called at the end of every grid
 *  render; does nothing when no rename is in progress. */
export function restoreRename(main) {
  if (!activeRename) return;
  const { rel, value, currentName, commit } = activeRename;
  // The card may be gone entirely (deleted, filtered out by a search, or in a
  // folder no longer being shown). Renaming something invisible is not a thing,
  // so drop it rather than leaving a box that can never reappear - but SAY so,
  // because otherwise the half-typed name simply disappears and it looks like
  // the panel ate it.
  if (!rowFor(main, rel)) { dropRename(true); return; }
  beginRename(main, rel, currentName, commit, value);
}

/** The element a rename box should go into for this workflow.
 *
 *  One workflow can be on screen TWICE - the tidy screen shows it once per
 *  problem it has. Only one of those rows offers Rename, so it is marked, and a
 *  plain first-match lookup would otherwise put the edit box on whichever
 *  section happened to render first. */
function rowFor(main, rel) {
  const sel = `[data-rel="${CSS.escape(rel)}"]`;
  return main.querySelector(sel + "[data-rename]") || main.querySelector(sel);
}

/** Turn a card's name into an input, in place. Enter commits, Escape cancels.
 *  `startValue` is what to put in the box when it differs from the name on
 *  disk - only used when restoring a rename that a re-render interrupted. */
export function beginRename(main, rel, currentName, commit, startValue) {
  const card = rowFor(main, rel);
  if (!card) return;
  // Already renaming. Without this, a second call in LIST view fell through to
  // the `span` fallback, matched the folder/date span (the only one left once
  // the name had been swapped for an input) and destroyed it, leaving two live
  // rename boxes on one row.
  if (card.querySelector("input")) return;
  const nameEl = card.querySelector(".pixwb-cardname") || card.querySelector(".pixwb-rowname");
  if (!nameEl) return;

  const input = el("input", "pixwb-rename");
  const resuming = startValue !== undefined;
  input.value = resuming ? startValue : currentName;
  const restore = () => { input.replaceWith(nameEl); };
  nameEl.replaceWith(input);
  input.focus();
  // Select-all on a FRESH rename (type straight over the old name), but caret
  // at the end when resuming - selecting there would mean the next keystroke
  // wiped everything typed before the interruption.
  if (resuming) input.setSelectionRange(input.value.length, input.value.length);
  else input.select();

  activeRename = { rel, currentName, commit, value: input.value };

  let done = false;
  const finish = (save) => {
    if (done) return;
    done = true;
    activeRename = null;
    const value = input.value.trim();
    restore();
    if (save && value && value !== currentName) commit(value);
  };
  input.addEventListener("input", () => {
    if (activeRename) activeRename.value = input.value;
  });
  input.addEventListener("keydown", (e) => {
    // ComfyUI's save / run go on (UI#44). NO blur: this box's blur handler tells
    // a re-render from the user clicking away, and a forced blur would rename early.
    if (passComfyShortcut(e, input)) return;
    e.stopPropagation();                       // Escape here must not close the window
    if (e.key === "Enter") finish(true);
    else if (e.key === "Escape") finish(false);
  });
  input.addEventListener("blur", () => {
    // A re-render REMOVED the box rather than the user clicking away. Without
    // this test an unrelated refresh commits whatever had been typed so far,
    // renaming the file to a half-finished name behind the user's back.
    // Leave activeRename set; the render that removed it puts it back.
    //
    // NOT `input.isConnected` - that was tried and never fires. Chrome sends
    // blur while the element is STILL ATTACHED and detaches it afterwards, so
    // isConnected reads true in here for both cases (measured, not assumed).
    if (isRendering()) return;
    finish(true);
  });
  input.addEventListener("click", (e) => e.stopPropagation());
  input.addEventListener("dblclick", (e) => e.stopPropagation());
}
