// ╔═══════════════════════════════════════════════════════════════╗
// ║  Pixaroma Workflows - the left column                          ║
// ╚═══════════════════════════════════════════════════════════════╝
//
// Three stacked groups:
//   the shortcuts (everything / favourites / recent / needs tidying),
//   the REAL folders on disk, nested,
//   and the collections the index worked out for itself.
//
// The collections deliberately sit BELOW the folders and never replace them:
// the folders are the user's own filing and must stay the primary thing. The
// collections are there so filing is no longer the only way to find something.
//
// Only real folders accept a drop. A collection is derived from what is inside
// a file, so dropping onto one would promise a move that cannot happen.

import { el, markRendering, isRendering } from "./window.mjs";
import { FOLDER_MIME, isFolderDrag, DROP_TARGET_ATTR } from "./drag.mjs";
import { passComfyShortcut } from "../shared/text_shortcuts.mjs";
import { byPath } from "./sort.mjs";

// Two clicks on the same folder row this close together mean "rename". Module
// scope on purpose: the row element does not survive the first click, so the
// state cannot live on it. 400ms is the usual OS double-click window - long
// enough to catch a real double click, short enough that going back to a folder
// a moment later just selects it.
const DBL_MS = 400;
let lastFoldClick = { path: null, at: 0 };

// The MIME that marks a drag as "a folder being re-ordered" rather than
// "workflow cards being filed", and the test for it, both live in drag.mjs now -
// the drop guard there needs the same two constants, and two copies of a MIME
// string is exactly the drift that lets a guard silently stop recognising the
// drag it exists to catch.

const FOLDER_COLORS = ["#4d7ea8", "#7ea84d", "#a8794d", "#8a4da8", "#a84d4d", "#4da8a0", "#8f8f8f", "#6d78a8"];

/**
 * Folder order.
 *
 * On disk there is no such thing as folder order - the server lists them
 * alphabetically. A chosen order lives in the sidecar as a list of paths, and
 * anything not in it falls back to alphabetical, so a newly created folder
 * still appears somewhere sensible instead of vanishing to the end of nowhere.
 *
 * Sorting happens per PARENT, and the result is walked as a tree, so a child
 * always follows its own parent no matter where either was dragged to. Sorting
 * the flat list instead would let a re-ordered parent end up below somebody
 * else's children.
 */
export function orderedFolders(folders, order) {
  const rank = new Map((order || []).map((p, i) => [p, i]));
  const kids = new Map();               // parent path -> child paths
  for (const f of folders) {
    const parent = f.includes("/") ? f.slice(0, f.lastIndexOf("/")) : "";
    if (!kids.has(parent)) kids.set(parent, []);
    kids.get(parent).push(f);
  }
  const byRank = (a, b) => {
    const ra = rank.has(a) ? rank.get(a) : Infinity;
    const rb = rank.has(b) ? rank.get(b) : Infinity;
    if (ra !== rb) return ra - rb;
    return byPath(a, b);                // "2. Edit" before "10. Video" (sort.mjs)
  };
  const out = [];
  const walk = (parent) => {
    const list = (kids.get(parent) || []).slice().sort(byRank);
    for (const f of list) { out.push(f); walk(f); }
  };
  walk("");
  // A folder whose parent is missing from the list would never be walked to;
  // append it rather than dropping it off the panel entirely.
  for (const f of folders) if (!out.includes(f)) out.push(f);
  return out;
}

/** Every folder path ABOVE this one, outermost first. "a/b/c" -> ["a", "a/b"]. */
export function ancestorsOf(path) {
  const parts = String(path || "").split("/");
  const out = [];
  for (let i = 1; i < parts.length; i++) out.push(parts.slice(0, i).join("/"));
  return out;
}

/** Does any folder sit inside this one? Drives whether a row gets a twisty. */
export function hasChildren(path, folders) {
  const prefix = path + "/";
  return (folders || []).some((f) => f.startsWith(prefix));
}

/**
 * Which folders are drawn open for THIS render.
 *
 * The stored list is the ones the user opened - absent means closed, so a fresh
 * install starts tidy instead of pouring every sub-folder down the column.
 *
 * The branch holding the folder being VIEWED is added on top, and deliberately
 * only for the render: selecting a sub-folder must not silently rewrite the
 * user's saved choices, or every click would be an edit and the sidecar would
 * be written on navigation.
 */
export function openSet(expanded, sel) {
  const open = new Set(expanded || []);
  if (sel && sel.kind === "folder" && sel.value) {
    for (const a of ancestorsOf(sel.value)) open.add(a);
  }
  return open;
}

/** The siblings of a folder, in the order they are displayed. */
export function siblingsOf(path, folders, order) {
  const parent = path.includes("/") ? path.slice(0, path.lastIndexOf("/")) : "";
  return orderedFolders(folders, order).filter((f) => {
    const p = f.includes("/") ? f.slice(0, f.lastIndexOf("/")) : "";
    return p === parent;
  });
}

/** A stable colour per folder, so it looks deliberate without anyone choosing
 *  one and does not shuffle as folders are added. Overridable in the sidecar. */
export function folderColor(path, meta) {
  const chosen = meta?.folderColors?.[path];
  if (chosen) return chosen;
  let h = 0;
  for (let i = 0; i < path.length; i++) h = (h * 31 + path.charCodeAt(i)) >>> 0;
  return FOLDER_COLORS[h % FOLDER_COLORS.length];
}

/**
 * Rebuild the column.
 *
 * onPick(sel)          - {kind, value} for the row that was clicked
 * onDropOn(folderPath) - cards were dropped on a real folder row
 */
export function renderFolders(side, state, { onPick, onDropOn, onRenameFolder, onFolderMenu, onReorderFolder, onToggleFolder }) {
  // The clear fires an open folder-rename box's blur synchronously - the flag
  // has to be up across it so that blur is not mistaken for the user clicking
  // away. See markRendering in window.mjs.
  markRendering(() => { side.textContent = ""; });
  const { entries, folders, collections, meta, favourites, sel, tidyRels } = state;
  const open = openSet(meta?.folderExpanded, sel);

  const is = (kind, value) => sel.kind === kind && (value === undefined || sel.value === value);

  /** Build a row, attach its click, and - for a real folder - its drop target. */
  function addRow({ label, count, on, dot, indent = 0, title, muted, star, twisty }, pick, folderPath) {
    const b = el("button", "pixwb-fold" + (on ? " on" : ""));
    b.type = "button";
    if (title) b.title = title;
    if (muted) b.style.color = "#6e6764";
    if (indent) {
      const sp = el("span", "pixwb-nest");
      sp.style.width = indent * 11 + "px";
      b.append(sp);
    }
    // The twisty, or a spacer exactly its width when this folder has nothing
    // inside it - so every label in the column starts on the same line whether
    // or not that particular folder happens to have sub-folders.
    if (twisty) {
      const c = el("span", "pixwb-chev" + (twisty.open ? " pixwb-chev-open" : ""), "▶");
      c.title = twisty.open ? "Hide what is inside" : "Show what is inside";
      c.addEventListener("click", (e) => {
        // Must not also select the folder, and must not count towards the
        // double-click-to-rename gesture: opening then closing a folder quickly
        // is a completely ordinary thing to do and would otherwise pop a rename
        // box (the same class of bug as pattern #30).
        e.preventDefault();
        e.stopPropagation();
        lastFoldClick = { path: null, at: 0 };
        twisty.onToggle();
      });
      b.append(c);
    } else if (twisty === null) {
      b.append(el("span", "pixwb-chevpad"));
    }
    if (dot) {
      const d = el("span", "pixwb-dot");
      d.style.background = dot;
      b.append(d);
    }
    // The star is its own element so it can be orange while the label stays
    // readable grey - baking it into the label text made it one colour.
    if (star) b.append(el("span", "pixwb-favstar", "★"));
    b.append(el("span", "pixwb-foldlbl", label));
    if (count != null) b.append(el("span", "pixwb-cnt", String(count)));
    b.addEventListener("click", () => {
      // Double click to rename is handled HERE, counting clicks, rather than
      // with a dblclick listener - because a dblclick listener never fires on
      // these rows. The FIRST click selects the folder, which re-renders this
      // whole column and throws this very element away; the second click lands
      // on its replacement, and the browser then emits NO dblclick at all
      // (measured - not even on the shared parent, which is where the spec's
      // "nearest common ancestor" rule would have put it). So the tooltip and
      // the help page both promised a gesture that could not work.
      // A REAL folder only. "(loose files)" is passed as "" - it is the root,
      // shown as a row for convenience, and there is nothing there to rename.
      if (folderPath && onRenameFolder) {
        const now = performance.now();
        if (lastFoldClick.path === folderPath && now - lastFoldClick.at < DBL_MS) {
          lastFoldClick = { path: null, at: 0 };
          onRenameFolder(folderPath, b);   // `b` is the LIVE row: this is the
          return;                          // replacement the first click made
        }
        lastFoldClick = { path: folderPath, at: now };
      } else {
        // Any OTHER row resets the count. Without this, clicking folder A,
        // then a shortcut or a collection, then folder A again inside the
        // window read as a double click - three deliberate single clicks with
        // an unrelated selection in between opened a rename box.
        lastFoldClick = { path: null, at: 0 };
      }
      onPick(pick);
    });

    if (folderPath !== undefined) {
      // A folder row is a drop target for TWO different drags: workflow cards
      // being filed into it, and another folder being re-ordered around it.
      // They are told apart by the drag's data TYPE, which is the only thing
      // readable during dragover (getData is blocked until the drop).
      const clearMarks = () => b.classList.remove(
        "pixwb-droptarget", "pixwb-insert-above", "pixwb-insert-below");

      // Marks this row as somewhere a Pixaroma drag may legitimately land. The
      // guard in drag.mjs cancels our drags everywhere else, so a row that
      // really accepts a drop has to say so - and only the rows inside this
      // branch do, which is why the class name alone would be wrong (the
      // shortcuts and the collections are the same `.pixwb-fold` button).
      b.dataset[DROP_TARGET_ATTR] = "1";

      b.addEventListener("dragover", (e) => {
        e.preventDefault();
        if (e.dataTransfer) e.dataTransfer.dropEffect = "move";
        clearMarks();
        if (isFolderDrag(e)) {
          if (folderPath === "") return;              // (loose files) is not a real folder
          const r = b.getBoundingClientRect();
          const above = (e.clientY - r.top) < r.height / 2;
          b.classList.add(above ? "pixwb-insert-above" : "pixwb-insert-below");
        } else {
          b.classList.add("pixwb-droptarget");
        }
      });
      b.addEventListener("dragleave", (e) => {
        // The row has child spans (indent, dot, label, count). Crossing onto one
        // fires dragleave on the row even though the cursor never left it, so
        // the highlight flickered. Ignore a leave that lands inside.
        if (e.relatedTarget && b.contains(e.relatedTarget)) return;
        clearMarks();
      });
      b.addEventListener("drop", (e) => {
        e.preventDefault();
        const wasFolder = isFolderDrag(e);
        const r = b.getBoundingClientRect();
        const above = (e.clientY - r.top) < r.height / 2;
        clearMarks();
        if (wasFolder) {
          const moved = e.dataTransfer.getData(FOLDER_MIME);
          if (moved && moved !== folderPath && folderPath !== "") {
            onReorderFolder?.(moved, folderPath, above);
          }
        } else {
          onDropOn?.(folderPath);
        }
      });

      // Folders themselves are draggable, so they can be re-ordered by hand
      // rather than only through the right-click menu.
      b.draggable = true;
      b.addEventListener("dragstart", (e) => {
        if (e.target.tagName === "INPUT") { e.preventDefault(); return; }  // mid-rename
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData(FOLDER_MIME, folderPath);
        // The text/plain copy stays (see drag.mjs for why it is not simply
        // dropped) and is what makes every text box on the page a drop target
        // for this path - installDropGuard is what stops that landing.
        e.dataTransfer.setData("text/plain", folderPath);
        b.classList.add("pixwb-dragging-me");
      });
      b.addEventListener("dragend", () => b.classList.remove("pixwb-dragging-me"));
    }

    side.append(b);
    return b;
  }

  // ── shortcuts ──
  addRow({ label: "All workflows", count: entries.length, on: is("all") }, { kind: "all" });
  addRow({ label: "Favourites", star: true, count: favourites.size, on: is("fav") }, { kind: "fav" });
  addRow({ label: "Recent", count: Math.min(20, entries.length), on: is("recent") }, { kind: "recent" });

  // The count is the number of WORKFLOWS the click will show, not the number of
  // issue groups - see collectTidyRels in index.js for why that distinction bit.
  const issueCount = tidyRels?.size || 0;
  if (issueCount) {
    addRow({
      label: "Needs tidying", count: issueCount, on: is("tidy"),
      title: "Leftover names, duplicates, and workflows needing things you do not have",
    }, { kind: "tidy" });
  }

  // ── real folders ──
  side.append(el("div", "pixwb-grouphead", "Folders"));

  // A workflow inside a sub-folder counts for its parents too, or a folder that
  // only holds sub-folders would read as empty.
  const perFolder = new Map();
  for (const e of entries) {
    if (!e.folder) continue;
    const parts = e.folder.split("/");
    for (let i = 1; i <= parts.length; i++) {
      const key = parts.slice(0, i).join("/");
      perFolder.set(key, (perFolder.get(key) || 0) + 1);
    }
  }

  addRow({
    label: "(loose files)", count: entries.filter((e) => !e.folder).length,
    on: is("folder", ""), dot: "#5a5450", twisty: null,
    title: "Workflows sitting outside any folder",
  }, { kind: "folder", value: "" }, "");

  for (const f of folders) {
    // A folder inside a closed one is simply not drawn. `folders` already
    // arrives parent-before-child (orderedFolders walks it as a tree), so the
    // order and the indent stay exactly as they were - the only change is that
    // some rows are left out.
    if (!ancestorsOf(f).every((a) => open.has(a))) continue;

    const kids = hasChildren(f, folders);
    const isOpen = open.has(f);
    const row = addRow({
      label: f.split("/").pop(),
      count: perFolder.get(f) || 0,
      on: is("folder", f),
      dot: folderColor(f, meta),
      indent: f.split("/").length - 1,
      // The NEXT state is decided here, from what is actually drawn - not from
      // the stored list. A folder can be drawn open because it holds the
      // selection while not being in the stored set at all, and a twisty that
      // read the stored set would "open" a row that is already open.
      twisty: kids ? { open: isOpen, onToggle: () => onToggleFolder?.(f, !isOpen) } : null,
      title: f + "\nDouble click to rename, right click for more",
    }, { kind: "folder", value: f }, f);

    // No dblclick listener here: it never fires, because selecting the folder
    // rebuilds this column between the two clicks. The gesture is counted in
    // addRow's click handler instead. Kept only to swallow the browser's own
    // double-click text selection.
    row.addEventListener("dblclick", (e) => e.preventDefault());
    row.addEventListener("contextmenu", (e) => {
      e.preventDefault();
      e.stopPropagation();
      onFolderMenu?.(f, e);
    });
  }

  addRow({ label: "+ New folder", muted: true }, { kind: "newfolder" });

  // ── collections ──
  const kinds = (collections || []).filter((c) => c.group === "kind");
  const models = (collections || []).filter((c) => c.group === "model");

  if (kinds.length) {
    side.append(el("div", "pixwb-grouphead", "What it makes"));
    for (const c of kinds) {
      addRow({ label: c.label, count: c.count, on: is("collection", c.id) },
             { kind: "collection", value: c.id });
    }
  }
  if (models.length) {
    side.append(el("div", "pixwb-grouphead", "Model"));
    for (const c of models) {
      addRow({ label: c.label, count: c.count, on: is("collection", c.id) },
             { kind: "collection", value: c.id });
    }
  }
}

/** Swap a folder row for a text box. Enter commits the new NAME (not path). */
export function beginFolderRename(row, path, commit) {
  if (!row || row.querySelector("input")) return;
  const current = path.split("/").pop();
  const kept = [...row.childNodes];
  const input = el("input", "pixwb-foldrename");
  input.value = current;
  row.textContent = "";
  row.append(input);
  input.focus();
  input.select();

  let done = false;
  const finish = (save) => {
    if (done) return;
    done = true;
    const value = input.value.trim();
    row.textContent = "";
    kept.forEach((n) => row.append(n));
    if (save && value && value !== current) commit(value);
  };
  input.addEventListener("keydown", (e) => {
    // ComfyUI's save / run go on (UI#44). NO blur: the blur handler tells a
    // column rebuild from the user clicking away; a forced blur would rename early.
    if (passComfyShortcut(e, input)) return;
    e.stopPropagation();                  // Escape here must not close the panel
    if (e.key === "Enter") finish(true);
    else if (e.key === "Escape") finish(false);
  });
  input.addEventListener("blur", () => {
    // Only when the USER clicked away. Rebuilding the folder column removes this
    // box too and fires its blur, so without the test an unrelated refresh
    // committed whatever had been typed so far and renamed the folder to a
    // half-finished name. Abandoning the edit is the safe half of that trade;
    // the grid's rename box additionally restores itself, which the folder
    // column does not need as often. (`isConnected` does NOT work here - see
    // the note on the grid's copy.)
    if (isRendering()) return;
    finish(true);
  });
  input.addEventListener("click", (e) => e.stopPropagation());
  input.addEventListener("dblclick", (e) => e.stopPropagation());
}
