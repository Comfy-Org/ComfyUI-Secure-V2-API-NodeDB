import { comfy } from '/comfy/api/v2.js';

// MOSTLY DISSOLVED — 316 lines in, three exports out.
//
// This was rgthree's replacement for ComfyUI's node class, and it reached the graph by
// intercepting registration:
//
//     const oldregisterNodeType = LiteGraph.registerNodeType;
//     LiteGraph.registerNodeType = function (nodeId, baseClass) {
//       const clazz = OVERRIDDEN_SERVER_NODES.get(baseClass) || baseClass;
//       return oldregisterNodeType.call(LiteGraph, nodeId, clazz);
//     };
//
// NOT A GAP. `registerForOverride` is a *composition style*, not a capability: it swaps
//   ComfyUI's generated class for one of rgthree's so the subclass's constructor,
//   configure, onConnectionsChange, onExecuted and onRemoved run. Every one of those is
//   a `comfy.defs.extend` hook. Seed, Image Inset Crop, Image or Latent Size, Any
//   Switch, Context and Power Primitive are converted on that basis, and the virtual
//   half — `RgthreeBaseVirtualNode.setUp()` → `LiteGraph.registerNodeType(this.type,
//   this)` — is `comfy.defs.define({type, execution: 'frontend'})`, which is how the
//   Fast Muter, Fast Bypasser, Node Collector, Mute/Bypass Relay and Repeater, Random
//   Unmuter and Power Conductor are now registered.
//
// NOT A GAP: `setupFromServerNodeData()`. It walks `nodeData.input.required/optional`,
//   calls `ComfyWidgets[type](...)` itself and builds outputs with
//   `LiteGraph.GRID_SHAPE` / `CIRCLE_SHAPE`, because a node built from rgthree's own
//   class no longer runs ComfyUI's def-to-node construction. Under `defs.extend` the
//   class *is* ComfyUI's generated one, so the host does all of it —
//   `src/services/litegraphService.ts` reads the same def and applies the same
//   `GRID_SHAPE` for a list output. The routine is not reimplementable through the
//   published API and does not need to be: it only ever existed to replace the host.
//
// NOT A GAP: `clone()`. `structuredClone(cloned.properties)` guards against a copy
//   sharing property objects with its original, which litegraph's own `clone()` already
//   prevents — it round-trips through `serialize()`, so properties are deep-copied by
//   construction. `cloned.graph = this.graph` re-parented the copy so code in the
//   subclass could read a graph before insertion; a handle resolves by id and carries
//   `graphId`, so nothing needs the reference. Resetting state a copy must not inherit
//   is `b.onCreated`, whose event says `restored` and `loading` — which the original
//   could not distinguish and which is exactly what tells a paste from a file load.
//
// NOT A GAP: `removeWidget` / `replaceWidget`. `widgets.remove(name)` +
//   `widgets.add(def)` + `widgets.move(name, index)` are the three moves, and the name
//   of a widget at a position is `widgets.at(i).name`, so "anything, including core's"
//   is still addressable.
//
// `onDragOver` / `onDragDrop` are two lines that forward to
// feature_import_individual_nodes.js after an `isDropEnabled` check. Nothing about the
// drop target is decided here, so the gap is stated once, there.
//
// `defaultGetSlotMenuOptions` is not a hook — it is a copy of litegraph's own default
// slot menu (Disconnect Links / Remove Slot / Rename Slot), kept so that a subclass
// overriding `getSlotMenuOptions` could fall back to it. Power Lora Loader is its only
// caller, and the slot menu it exists to compose with is stated there and in
// dynamic_context.js. With no override to compose with, the copy has nothing to do.
//
// COSMETIC: the "🛟 Node Help" entry was spliced in after "Properties Panel" by
//   string-matching core's own items. `b.addMenuItem` appends, so the entry is present
//   and its position among core's entries is not.
//
// `defineProperty(this, "mode", {get, set})` — the sole driver of Mute/Bypass Repeater
// and Relay — is deleted, not converted. `comfy.onNodeChanged` reports a mode change on
// any node, filtered on `e.property === 'mode'`, so nothing has to rewrite a core
// property on someone else's node to hear about it.
//
// `onConstructed` / `checkAndRunOnConstructed` are not a gap either: the setTimeout in
// the constructor existed because a base constructor cannot see whether a subclass has
// finished, and `b.onCreated` is the published per-node hook that fires once the node is
// real.

/**
 * The pack's own cross-node action registry — `Clazz.exposedActions` plus
 * `handleAction()`, which the Fast Actions Button reads off a neighbour's
 * `node.constructor` and invokes on the instance.
 *
 * Not an API gap: every node that declares an action and the single node that calls one
 * are both rgthree's, so this is the pack coordinating with itself and never needed the
 * host. What it may no longer do is hang the table off the class — a handle has no
 * `constructor`, and holds no arbitrary properties — so it is keyed by node type here,
 * which is what `node.constructor.exposedActions` meant anyway.
 */
const actionsByType = new Map();
/** Declares the actions a node type answers to, and the handler that runs one. */
export function exposeActions(type, actions, handler) {
    actionsByType.set(type, { actions, handler });
}
/** What the Fast Actions Button offers for a connected node. */
export function exposedActionsFor(type) {
    return actionsByType.get(type)?.actions ?? [];
}
/** Runs one. Silently does nothing for a type that exposes none, as `handleAction` did. */
export async function handleAction(node, action) {
    await actionsByType.get(node.type)?.handler(node, action);
}

/**
 * Help content by node type, so the entry and the shortcut read the same text.
 *
 * `getHelp()` was an instance method on the class and `Clazz.help` a static; both are
 * one string per type, which is what this is.
 */
const helpByType = new Map();

function showHelp(node) {
    const content = helpByType.get(node.type);
    if (!content)
        return;
    comfy.ui.showDialog({
        key: `rgthree.help.${node.type}`,
        title: node.type.replace(/\s*\(rgthree\).*/, " by rgthree"),
        render(container) {
            container.innerHTML = content;
        },
    });
}

/**
 * The "🛟 Node Help" context-menu entry, which `getHelp()` used to feed through
 * `addHelpMenuItem` and `showHelp()`.
 *
 * Takes the type as well as the content because help is per node type — it was
 * `Clazz.help` and an instance `getHelp()` returning one constant string — and the
 * keyboard shortcut below has to find the same text without a menu having been opened.
 *
 * The pack's own `RgthreeHelpDialog` is a plain DOM dialog and still exists, but the
 * published dialog is the one the host manages, stacks and closes; the pack's styling
 * ("-iconed -help") and its `close` event go with it, which is cosmetic.
 */
export function helpMenuItem(type, content) {
    helpByType.set(type, content);
    return { label: "🛟 Node Help", run: showHelp };
}

// `onKeyDown` opened the help dialog when the user pressed "?" over a node. Node key
// events are not published — deliberately, since a key belongs to the application and
// not to whatever the pointer is over — and a command is: it declares the binding as a
// *default*, so a user who rebinds "?" keeps their binding across reloads, which the
// node hook could never honour. `scope: 'canvas'` keeps it from firing while the user is
// typing into a text widget, which the original had to check for by hand.
//
// LIMITATION: the original asked the node the canvas was routing keys to; this asks the
// selection, so help opens for a selected node rather than a merely hovered one. It also
// opens for each of several selected nodes rather than for one.
comfy.commands.register({
    id: "rgthree.showNodeHelp",
    label: "🛟 Node Help",
    keybinding: { key: "?" },
    scope: "canvas",
    run() {
        for (const node of comfy.graph.selection()) {
            showHelp(node);
        }
    },
});
