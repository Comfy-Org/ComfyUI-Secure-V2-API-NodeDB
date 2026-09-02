import { comfy } from '/comfy/api/v2.js';
import { SERVICE as KEY_EVENT_SERVICE } from "./services/key_events_services.js";
import { SERVICE as BOOKMARKS_SERVICE } from "./services/bookmarks_services.js";
import { NodeTypesString } from "./constants.js";
import { getClosestOrSelf } from "../../rgthree/common/utils_dom.js";

// Bookmark — a collapsed marker node with a shortcut key and a zoom level; press the key
// anywhere and the canvas jumps to it.
//
// `canvasToBookmark()` was written entirely in canvas internals —
// `canvas.ds.offset[0] = -this.pos[0] + 16`, `ds.scale = Number(this.widgets[1].value)`,
// `setDirty` — and is `comfy.graph.centerOn(node)` plus `comfy.graph.setZoom(...)`. The
// shortcut itself needs nothing published: the pack's own key service is plain DOM key
// tracking, so the binding still follows the widget's value, which is the whole point of
// a shortcut the user retypes on the node.
//
// REFUSED, not a gap: `_collapsed_width` is a getter/setter pair that measures the title
//   with `canvas.canvas.getContext("2d")` and `canvas.title_text_font` so the collapsed
//   pill fits the emoji title, and `Bookmark.slot_start_y = -20` shifts the slot row.
//   Renderer text metrics and slot geometry are the renderer's, and the renderer is ours
//   to replace — see utils.js. The node collapses; how wide its pill draws is the
//   renderer's answer.
// REFUSED, not a gap: `onMouseDown` reached into litegraph's own widget edit dialog with
//   `query(".graphdialog > input.value")` and attached a listener to it, turning that
//   field into a key-capture box. That is a pack rewriting a dialog it does not own,
//   found by CSS selector — markup we rename freely. COSMETIC: the field is an ordinary
//   text widget and the user types the character instead of pressing it.
// LIMITATION: a bookmark inside a subgraph the user is not currently looking at is
//   listed (see services/bookmarks_services.js) but pressing its key does nothing.
//   `canvasToBookmark` called `canvas.openSubgraph(subgraph, fromNode)` first; nothing
//   published enters a subgraph, and a SubgraphHandle is a definition rather than the
//   node that places one, so there is no `fromNode` to enter through either. Bookmarks
//   in the graph on screen are unaffected.
//
// The `y` options on both widgets positioned them under the collapsed title bar; they go
// with the rest of the renderer geometry above.
const KEYPRESS_LISTENERS = new Map();
function canvasToBookmark(node) {
    comfy.graph.centerOn(node);
    // `centerOn` puts the node in the middle of the view where the original parked it
    // 16/40 from the top-left corner. The user sees that difference; the jump is intact.
    comfy.graph.setZoom(Number(node.widgets.get("zoom")?.getValue() || 1));
}
comfy.defs.define({
    type: NodeTypesString.BOOKMARK,
    title: NodeTypesString.BOOKMARK,
    category: "rgthree",
    // Never reaches the backend: the original was `isVirtualNode` with no
    // `applyToGraph`, so it has no `resolve` and is simply left out of the prompt.
    execution: 'frontend',
    widgets: [
        // The shortcut's initial value depends on which characters the workflow already
        // uses, so it is filled in per node below rather than declared here.
        { type: "text", name: "shortcut_key", value: "1" },
        { type: "number", name: "zoom", value: 1, options: { max: 2, min: 0.5, precision: 2 } },
    ],
    onCreated(node, event) {
        node.setSerializeWidgets(true);
        node.setTitle("🔖");
        // A node arriving with saved state brings its own shortcut; only a fresh one
        // needs the next free character.
        const shortcutWidget = node.widgets.get("shortcut_key");
        if (!shortcutWidget) {
            throw new Error(`[rgthree.Bookmark] node ${node.id} has no "shortcut_key" widget.`);
        }
        if (!event.restored) {
            shortcutWidget.setValue(BOOKMARKS_SERVICE.getNextShortcut());
        }
        const onKeypress = (e) => {
            const originalEvent = e.detail.originalEvent;
            const target = originalEvent.target;
            if (getClosestOrSelf(target, 'input,textarea,[contenteditable="true"]')) {
                return;
            }
            const shortcut = shortcutWidget.getValue();
            if (shortcut && KEY_EVENT_SERVICE.areOnlyKeysDown(shortcut, true)) {
                canvasToBookmark(node);
                originalEvent.preventDefault();
                originalEvent.stopPropagation();
            }
        };
        KEY_EVENT_SERVICE.addEventListener("keydown", onKeypress);
        // Handles hold no arbitrary properties, so `this.keypressBound` lives here and is
        // dropped in onRemoved — which is what `onAdded`/`onRemoved` did with it.
        KEYPRESS_LISTENERS.set(node.id, onKeypress);
    },
    onRemoved(node) {
        const onKeypress = KEYPRESS_LISTENERS.get(node.id);
        if (onKeypress) {
            KEY_EVENT_SERVICE.removeEventListener("keydown", onKeypress);
            KEYPRESS_LISTENERS.delete(node.id);
        }
    },
});
export { canvasToBookmark };
