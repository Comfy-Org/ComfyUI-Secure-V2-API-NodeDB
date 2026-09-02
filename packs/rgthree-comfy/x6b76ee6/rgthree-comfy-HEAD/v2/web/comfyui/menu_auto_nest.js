// Auto-nesting for long flat menus: when a combo lists more than N values that contain
// "/" or "\", group them into 📁 submenus. This is what makes a thousand-checkpoint list
// usable.
//
// REFUSED, not a pending gap: replacing the host's menu class. The whole file is
// `LiteGraph.ContextMenu = class extends LiteGraph.ContextMenu {…}`, installed at module
// load, so every menu the application opens — core's, this pack's, and every other
// pack's — is constructed by rgthree from then on. It rebuilds the value list into
// `has_submenu` / `submenu.options` entries and rewires each item's callback back to the
// original one it replaced. Two things follow, and neither is fixable by publishing a
// hook: a menu the user opens is no longer built by whoever raised it, and two packs
// doing this cannot both win — the second to load wraps the first, and which that is
// depends on import order. The menu is also exactly what the renderer replacement
// changes shape of, so a pack subclassing it pins us to today's menu.
//
// REFUSED, not a pending gap: `options.scale` read from `app.canvas.ds.scale`, so the
// menu draws at the graph's zoom. The viewport transform is the renderer's, and how big
// a menu is belongs to the host's chrome rather than to a pack.
//
// Where the capability now lives, checked rather than assumed: a combo's values are no
// longer presented through this menu at all. `useComboWidget` routes a model-valued
// combo to the asset browser, which groups by `model_type:*` tags and keeps hierarchical
// paths (`assetMetadataUtils.getPrimaryCategoryTag`), and every other combo to
// `WidgetSelectDefault`, which is a filterable select rather than a flat click-through
// list. That is the same treatment for every combo in the application instead of
// whichever pack loaded last, and it is the layer that should decide it. Grouping a long
// list further is a request to make of the host; it is not something a pack can install
// over everyone else's menus. The `rgthree_doNotNest` opt-out this file honoured, passed
// through `LiteGraph.ContextMenu`'s `extra` field by rgthree.js's own canvas menu, has
// nothing left to opt out of.
//
// INOPERABLE: nothing. This file adds no node and registers no type; what it changed was
// how every other menu in the application is built.

export {}
