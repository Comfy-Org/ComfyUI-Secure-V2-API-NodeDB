/**
 * Pixaroma Workflows panel - name order.
 *
 * Numbers in names compare as NUMBERS ("2." before "10."): a text sort listed an
 * episode folder as 1, 10, 11, 2 and a viewer thought the files were mixed up.
 * No imports, so an offline test can load it (D:\Claude Tests\_workflow_sort_test.mjs).
 */

// ONE collator: localeCompare with options builds a new one per call, ~30x slower
// on a 2000-file Name sort, and computeVisible runs on every arrow key.
const COLLATOR = new Intl.Collator(undefined, { sensitivity: "base", numeric: true });

/** Two folder paths (or any two names), numbers as numbers, case ignored. */
export const byPath = (a, b) => COLLATOR.compare(a, b);

/** Segment by segment, so a parent's sub-folders follow it as in the folder tree:
 *  compared whole, " " "(" "-" sort before "/" and "EP36 Workflows (old)" would land
 *  between "EP36 Workflows" and "EP36 Workflows/1. Edit". */
function byFolder(a, b) {
  const x = a.split("/"), y = b.split("/");
  for (let i = 0; i < Math.min(x.length, y.length); i++) {
    const c = byPath(x[i], y[i]);
    if (c) return c;
  }
  return x.length - y.length;
}

/**
 * Two index entries: folder first, so a parent folder keeps each sub-folder's
 * files together instead of interleaving every sub-folder's "1.", then name.
 * Also the tie-break for the date and node-count sorts: files unpacked from one
 * zip share the same date.
 */
export const byFolderName = (a, b) =>
  byFolder(a.folder || "", b.folder || "") || byPath(a.name || "", b.name || "");
