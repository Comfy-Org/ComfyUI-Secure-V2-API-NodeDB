// ╔═══════════════════════════════════════════════════════════════╗
// ║  Pixaroma Workflows - the tidy-up screen                       ║
// ╚═══════════════════════════════════════════════════════════════╝
//
// "Needs tidying" used to be a plain filter: it showed you the affected
// workflows as ordinary cards and left you to work out which of the three
// problems each one had, and what to do about it. Three different problems
// wearing the same card is not a review screen.
//
// This is the review screen. One section per problem, each row carrying the fix
// that actually applies to THAT problem - rename for a leftover name, keep-one
// for a set of duplicates, copy-the-list for missing nodes.
//
// NOTHING here acts on its own. There is no undo in this version (see the
// pattern file, #14), so every destructive button goes through the same confirm
// the rest of the panel uses, and the header says so before the first row.

import { el, markRendering } from "./window.mjs";
import { coverEl, restoreRename } from "./grid.mjs";

/** A row's worth of buttons. Kept in one place so the three sections cannot
 *  drift into three slightly different button sets. */
function actions(specs) {
  const wrap = el("div", "pixwb-tdacts");
  for (const s of specs) {
    if (!s) continue;
    const b = el("button", "pixwb-tdbtn" + (s.danger ? " danger" : "") + (s.primary ? " primary" : ""),
                 s.label);
    b.type = "button";
    if (s.title) b.title = s.title;
    b.addEventListener("click", (e) => { e.stopPropagation(); s.fn(); });
    wrap.append(b);
  }
  return wrap;
}

/** One workflow, as a line: picture, name, where it lives, then its fix.
 *
 *  `renamable` tags the row as the one beginRename should edit. It is set for
 *  the leftover-names section ONLY, because that is the only section offering
 *  Rename - and one workflow can appear in more than one section at once (still
 *  called "Unsaved Workflow" AND one of a duplicate set). beginRename resolves
 *  by data-rel and takes the first match in the document, so tagging every row
 *  would put the edit box on whichever happened to render first. */
function row(entry, state, H, extras, trailing, renamable) {
  const r = el("div", "pixwb-tdrow");
  // data-rel plus a .pixwb-rowname is exactly what beginRename looks for, so
  // Rename edits the name in place here just as it does on a card - no dialog,
  // no second code path. Set on EVERY row, because the keyboard walks the rows
  // by it; the rename box is aimed with data-rename instead.
  r.dataset.rel = entry.rel;
  if (renamable) r.dataset.rename = "1";
  // The same two states every card shows. Without them, clicking a row updated
  // the pane on the right and the arrow keys moved an invisible cursor, so the
  // whole screen looked unresponsive to both.
  if (state.selected.has(entry.rel)) r.classList.add("sel");
  if (state.kbdRel === entry.rel) r.classList.add("kbd");
  r.title = entry.rel;
  r.append(coverEl(entry, state, "pixwb-rowcov"));

  const mid = el("div", "pixwb-tdmid");
  mid.append(el("span", "pixwb-rowname", entry.name));
  if (trailing) mid.append(el("span", "pixwb-tdsub", trailing));
  r.append(mid);

  if (entry.folder) r.append(el("span", "pixwb-tdfold", entry.folder));
  r.append(actions(extras));
  r.addEventListener("click", (e) => H.onSelect(entry, e));
  r.addEventListener("dblclick", () => H.onOpen(entry));
  return r;
}

function section(title, blurb, count) {
  const s = el("div", "pixwb-tdsec");
  const head = el("div", "pixwb-tdhead");
  head.append(el("span", "pixwb-tdtitle", title));
  head.append(el("span", "pixwb-tdcount", String(count)));
  s.append(head);
  if (blurb) s.append(el("div", "pixwb-tdblurb", blurb));
  return s;
}

export function renderTidy(main, state, H) {
  // See renderGrid: the clear fires an open rename box's blur synchronously.
  markRendering(() => { main.textContent = ""; });
  const { issues, byRel, query } = state;

  // The same query box still narrows the screen. Switching to plain cards the
  // moment someone typed would have thrown away the very grouping they came
  // here for.
  //
  // Narrowed by S.visible, NOT by a filter of this screen's own. computeVisible
  // has already run the REAL search over these entries - the weighted one that
  // reads models, LoRAs, notes, node types and prompt text - and the header's
  // "N of M" is counted from its result. The first version re-implemented a
  // name-and-path substring test here, so a query matching only a model name
  // made the header say "3 of 142" while this screen said nothing matched -
  // one search box, two answers. There is exactly one definition of matching,
  // and this screen borrows it.
  const q = (query || "").trim();
  const vis = new Set((state.visible || []).map((e) => e.rel));
  const keep = (rel) => !q || vis.has(rel);
  const get = (rel) => byRel.get(rel);

  const wrap = el("div", "pixwb-tidy");
  wrap.append(el("div", "pixwb-tdintro",
    "Nothing on this screen is changed for you. Each row is a suggestion with "
    + "its fix beside it, and anything that deletes still asks first."));

  let shown = 0;

  // ── 1. leftover names ──
  const unsaved = (issues.unsaved_names || []).map((u) => get(u.rel))
    .filter((e) => e && keep(e.rel));
  if (unsaved.length) {
    shown += unsaved.length;
    const s = section("Still called “Unsaved Workflow”",
      "Saved before they were given a name. Rename edits the name right here: "
      + "type over it and press Enter.", unsaved.length);
    for (const e of unsaved) {
      s.append(row(e, state, H, [
        { label: "Rename", primary: true, fn: () => H.onRename(e),
          title: "Give it a name you will recognise" },
        { label: "Open", fn: () => H.onOpen(e) },
        { label: "Delete", danger: true, fn: () => H.onDelete(e) },
      ], null, true));
    }
    wrap.append(s);
  }

  // ── 2. duplicates ──
  // A GROUP is only worth showing while it still has two members: filtering a
  // set of two down to one by search would offer "keep this one" against
  // nothing, which deletes nothing and reads as a broken button.
  const dupGroups = (issues.duplicates || [])
    .map((g) => g.map((d) => get(d.rel)).filter(Boolean))
    .filter((g) => g.length > 1 && g.some((e) => keep(e.rel)));
  if (dupGroups.length) {
    const files = dupGroups.reduce((n, g) => n + g.length, 0);
    shown += files;
    const s = section("The same workflow saved more than once",
      "Same nodes and same models under different names. “Keep this one” "
      + "deletes the others in its set, and tells you which before it does.",
      `${dupGroups.length} set${dupGroups.length === 1 ? "" : "s"}`);
    for (const g of dupGroups) {
      const box = el("div", "pixwb-tdgroup");
      for (const e of g) {
        const others = g.filter((x) => x.rel !== e.rel);
        const r = row(e, state, H, [
          { label: `Keep this one`, primary: true,
            title: `Delete the other ${others.length} in this set:\n`
                   + others.map((x) => x.name).join("\n"),
            // The NAMES go to the confirmation, not just the count. "Delete 2
            // workflows?" for files the user never individually picked is not
            // enough to agree to when there is no undo.
            fn: () => H.onDeleteMany(others.map((x) => x.rel), {
              title: `Delete the other ${others.length} in this set?`,
              message: `Keeping "${e.name}". These go:\n`
                       + others.map((x) => x.rel).join("\n"),
            }) },
          { label: "Open", fn: () => H.onOpen(e) },
          { label: "Delete", danger: true, fn: () => H.onDelete(e) },
        ], null);
        // A set is shown WHOLE when any member matches the search - half a set
        // cannot be judged. But then some rows on screen do not match the query
        // the header counted, so those are dimmed and say why: without the cue,
        // header "1 of 142" over three visible rows read as a counting bug.
        if (q && !keep(e.rel)) {
          r.classList.add("pixwb-tddimmed");
          r.title += "\nShown for context - it does not match your search, its set does.";
        }
        box.append(r);
      }
      s.append(box);
    }
    wrap.append(s);
  }

  // ── 3. missing nodes ──
  const missing = (issues.missing_nodes || [])
    .filter((m) => get(m.rel) && keep(m.rel));
  if (missing.length) {
    shown += missing.length;
    const s = section("Needs nodes you do not have",
      "These will open with red boxes where the missing nodes should be. Copy "
      + "the list and search for it in ComfyUI Manager to find what installs them.",
      missing.length);
    for (const m of missing) {
      const e = get(m.rel);
      const names = m.missing || [];
      s.append(row(e, state, H, [
        { label: "Copy list", primary: true, title: names.join(", "),
          fn: () => H.onCopyText(names.join("\n"), `Copied ${names.length} node names`) },
        { label: "Open", fn: () => H.onOpen(e) },
        { label: "Delete", danger: true, fn: () => H.onDelete(e) },
      ], names.join(", ")));
    }
    wrap.append(s);
  }

  if (!shown) {
    // Reached either because a search matched nothing, or because the user has
    // actually finished - and those deserve different sentences.
    wrap.append(el("div", "pixwb-empty", q
      ? `Nothing in here matches "${query}".`
      : "Nothing needs tidying. Your workflows folder is in good shape."));
  }

  main.append(wrap);
  // Same as the grid: a rename that was open before this render goes back.
  restoreRename(main);
}
