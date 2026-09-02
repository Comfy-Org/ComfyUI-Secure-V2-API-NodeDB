import { comfy } from '/comfy/api/v2.js';
import { NodeTypesString } from "../constants.js";

// Lists the Bookmark nodes in the current workflow, sorted by title, and picks the next
// free shortcut character for a new one.
//
// `reduceNodesDepthFirst(app.graph.nodes, …)` descended into every subgraph, because a
// bookmark in one must still be listed. `comfy.graph.subgraphs()` is that descent: a
// subgraph *definition* holds its nodes once, which is what "each of my bookmarks" wants
// — a subgraph placed three times still has one bookmark to jump to.
//
// `node.shortcutKey` was a getter on the Bookmark class returning `widgets[0].value`. A
// handle carries no methods of the pack's own, so it is read from the widget by name
// here, which is what the getter did.
const SHORTCUT_DEFAULTS = "1234567890abcdefghijklmnopqrstuvwxyz".split("");
export function shortcutKeyOf(node) {
    return String(node.widgets.get("shortcut_key")?.getValue() ?? "").toLocaleLowerCase();
}
class BookmarksService {
    getCurrentBookmarks() {
        return [comfy.graph, ...comfy.graph.subgraphs()]
            .flatMap((graph) => graph.nodes())
            .filter((n) => n.type === NodeTypesString.BOOKMARK)
            .sort((a, b) => a.getTitle().localeCompare(b.getTitle()));
    }
    getExistingShortcuts() {
        const bookmarkNodes = this.getCurrentBookmarks();
        const usedShortcuts = new Set(bookmarkNodes.map((n) => shortcutKeyOf(n)));
        return usedShortcuts;
    }
    getNextShortcut() {
        var _a;
        const existingShortcuts = this.getExistingShortcuts();
        return (_a = SHORTCUT_DEFAULTS.find((char) => !existingShortcuts.has(char))) !== null && _a !== void 0 ? _a : "1";
    }
}
export const SERVICE = new BookmarksService();
