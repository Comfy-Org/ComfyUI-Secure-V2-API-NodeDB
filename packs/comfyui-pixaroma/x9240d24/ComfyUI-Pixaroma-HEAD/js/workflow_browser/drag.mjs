// ╔═══════════════════════════════════════════════════════════════╗
// ║  Pixaroma Workflows - what our drags ARE, and where they may land ║
// ╚═══════════════════════════════════════════════════════════════╝
//
// A drag that carries `text/plain` makes EVERY text field on the page a native
// drop target for that string. Release the drag over one and the browser
// performs a real insert and fires an `input` event - so a field that commits on
// input has already saved it, with no undo.
//
// This panel has two such fields and they are the worst two it could have:
//
//   * the note box (`detail.mjs`) commits 500ms after any input, so a missed
//     drag rewrites the note;
//   * the inline rename box (`grid.mjs`) commits on blur, so a missed drag
//     edits the filename being typed and the blur that follows RENAMES THE FILE
//     ON DISK.
//
// Neither is hypothetical: the same class was reported in the Prompt tag library
// (fixed v1.4.76), where a dragged category name spliced itself into a snippet
// and committed. There is no drag handle on a card or a folder row, so
// overshooting the folder column onto something else is the NORMAL learning
// gesture, and no insert line appears over a text box to warn that a drop there
// will be taken literally.
//
// The guard below cancels only OUR drags that missed. An ordinary text drag
// carries neither of our types, so dragging text into the note or the search box
// still works exactly as before.
//
// Two rules worth keeping if a new drag is ever added here:
//
//   1. Put the flag in the MIME TYPE, not the payload. `getData` is blocked
//      until the drop, so `dataTransfer.types` is the ONLY thing a `dragover`
//      handler can read - which is how a folder row already tells a folder
//      re-order from a card being filed.
//   2. `text/plain` stays on the drag on purpose. "Some browsers refuse a drag
//      with no text/plain" is the myth version of the rule (any format
//      satisfies it), but dropping that line changes drag INITIATION, and only
//      a real mouse drag can prove initiation still works. Guarding the landing
//      is verifiable; changing the take-off is not.

/** A folder being re-ordered. */
export const FOLDER_MIME = "application/x-pixaroma-folder";
/** One or more workflow cards being filed into a folder. */
export const CARD_MIME = "application/x-pixaroma-workflow";

// The ONLY elements a Pixaroma drag is allowed to land on. Set in folders.mjs on
// the rows that really have a drop handler - which is not every row in that
// column: the shortcuts (All / Favourites / Recent / Needs tidying) and the
// self-filling collections are the same `.pixwb-fold` button but accept
// nothing, because a collection is derived from what is INSIDE a file and
// dropping onto one would promise a move that cannot happen.
export const DROP_TARGET_ATTR = "wfdrop";
const VALID_TARGET = "[data-wfdrop]";

function hasType(e, mime) {
  if (!e.dataTransfer) return false;
  // `types` is a DOMStringList on older engines, not an array.
  try { return [...e.dataTransfer.types].includes(mime); } catch { return false; }
}

/** A folder being dragged to re-order it, rather than cards being filed. */
export const isFolderDrag = (e) => hasType(e, FOLDER_MIME);

/** Any drag that started inside this panel. */
export const isOurDrag = (e) => hasType(e, FOLDER_MIME) || hasType(e, CARD_MIME);

/** True when this drag is ours AND the thing under the cursor cannot take it. */
function isStrayDrop(e) {
  if (!isOurDrag(e)) return false;                       // somebody else's drag
  const t = e.target;
  if (t && typeof t.closest === "function" && t.closest(VALID_TARGET)) return false;
  return true;
}

let installed = false;

/**
 * Cancel our own drags wherever they land other than a real folder row.
 *
 * CAPTURE phase on `document`, not on the panel: the drag starts inside the
 * panel but the mouse can be released anywhere, including a ComfyUI prompt box
 * on the canvas behind it. Capture also means this runs BEFORE the folder row's
 * own bubble-phase handler, so the legitimate drop is untouched - the stray one
 * never reaches anything.
 *
 * Cancelling the DROP is what actually blocks the insert. `preventDefault` on
 * `dragover` means "allow a drop here", so it cannot be used to refuse one, and
 * the browser allows a text drop on an editable element by default with no
 * handler at all. The `dragover` half below only sets the cursor: engines that
 * honour a `dropEffect` of "none" then fire no drop event, and the ones that do
 * not still hit the drop guard.
 *
 * Idempotent - safe to call on every panel build.
 */
export function installDropGuard() {
  if (installed) return;
  installed = true;

  document.addEventListener("dragover", (e) => {
    if (!isStrayDrop(e)) return;
    try { e.dataTransfer.dropEffect = "none"; } catch { /* read-only in some states */ }
  }, true);

  document.addEventListener("drop", (e) => {
    if (!isStrayDrop(e)) return;
    e.preventDefault();
    e.stopPropagation();
  }, true);
}
