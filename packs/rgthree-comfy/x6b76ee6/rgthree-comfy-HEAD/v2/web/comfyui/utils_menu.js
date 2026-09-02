import { comfy } from '/comfy/api/v2.js';
import { rgthreeApi } from "../../rgthree/common/rgthree_api.js";

// `comfy.ui.showMenu` is the published free-floating menu, so all three pickers
// convert. Three ContextMenu options go and none is a capability:
//   - `scale` matched the menu to `app.canvas.ds.scale`. The host sizes its own
//     chrome, which is the point of a declarative menu.
//   - `className: "dark"` styled it. Same.
//   - `parentMenu` nested the picker under the menu that opened it. `MenuDef`
//     nests through `submenu` within one definition, not across two calls; no
//     caller in this build passes one, so the parameter is kept for the
//     signature and unused.
const PASS_THROUGH = function (item) {
    return item;
};
export async function showLoraChooser(event, callback, parentMenu, loras) {
    if (!loras) {
        loras = ["None", ...(await rgthreeApi.getLoras().then((loras) => loras.map((l) => l.file)))];
    }
    comfy.ui.showMenu({
        event,
        title: "Choose a lora",
        items: loras.map((lora) => ({ label: lora, run: () => callback(lora) })),
    });
}
// `mapFn` is handed a NodeHandle rather than an LGraphNode; it still returns the
// pack's `{content, value}` option, or null to drop the node.
export function showNodesChooser(event, mapFn, callback, parentMenu) {
    const nodesOptions = comfy.graph.nodes()
        .map(mapFn)
        .filter((e) => e != null);
    nodesOptions.sort((a, b) => {
        return a.value - b.value;
    });
    comfy.ui.showMenu({
        event,
        title: "Choose a node id",
        items: nodesOptions.map((option) => ({
            label: option.content,
            run: () => callback(option.value),
        })),
    });
}
export function showWidgetsChooser(event, node, mapFn, callback, parentMenu) {
    const options = node.widgets.all()
        .map(mapFn)
        .filter((e) => e != null);
    if (options.length) {
        comfy.ui.showMenu({
            event,
            title: "Choose an input/widget",
            items: options.map((option) => ({
                label: option.content,
                run: () => callback(option.value),
            })),
        });
    }
}
