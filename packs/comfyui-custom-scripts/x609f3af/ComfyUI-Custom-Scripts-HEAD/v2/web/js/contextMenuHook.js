// Previously published a global extension point for the legacy canvas context
// menu: it wrapped LiteGraph.ContextMenu.prototype.addItem in a Proxy whose
// `constructor` returned a second Proxy, patched the LiteGraph.ContextMenu
// constructor to unwrap that proxy again, and exposed ctor/preAddItem/addItem
// callback arrays on a window symbol so other packs could filter or replace menu
// entries as they were built. Its own comment called it "a big ol' hack".
//
// REFUSED, not a pending gap: intercepting the renderer's menu construction.
// LiteGraph.ContextMenu is the renderer's, and the renderer is ours to replace;
// this file replaced its constructor and its prototype outright, so every menu
// raised in the application — core's, this pack's, and every other pack's — was
// built through one pack's code. Two packs doing it leaves the answer to load
// order, and the second Proxy exists only because the first one broke a type
// check inside litegraph, which is what depending on internals costs.
//
// REFUSED, not a pending gap: a pack-to-pack registry on `window`. The symbol
// store was there so other packs could register handlers into this one. An
// unversioned mutable global shared between packs that cannot see each other is
// precisely the coupling this migration deletes, and re-creating it under a
// different name would change nothing.
//
// The capability is not refused. Contributing to a node's menu is
// `b.addMenuItem({ label, when, items, run })`, which accumulates across packs
// rather than overwriting, and raising a menu of your own is
// `comfy.ui.showMenu({ items, event })`, which nests to any depth. What is gone is
// editing somebody else's entries as they are built, and nothing in this pack used
// it: no other file here reads window.__pysssss__.
//
// INOPERABLE: window.__pysssss__.contextMenuHook, for any pack that registered
// ctor / preAddItem / addItem handlers into it.

export {}
