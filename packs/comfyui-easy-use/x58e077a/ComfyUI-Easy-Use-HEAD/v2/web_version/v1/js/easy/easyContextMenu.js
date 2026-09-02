// Previously nested the model picker. When a combo widget opened a list of more
// than ten paths, this file split them on "/" or "\", rebuilt the flat list as
// recursive submenus, and drew a thumbnail into each row by putting an element's
// outerHTML in the entry's `title`. It did that by assigning over
// LiteGraph.ContextMenu — `LiteGraph.ContextMenu = function(values, options){…}`
// followed by re-pointing the replacement's prototype at the original's.
//
// REFUSED, not a pending gap: replacing a host constructor in place. This is not
// a hook the pack registers, it is the application's menu class swapped for the
// pack's own, so EVERY menu — core's, every other pack's, menus over nodes
// easy-use has never heard of — is routed through this file and re-entered
// through `existingContextMenu.apply(this, arguments)` when it declines. The
// ten-item threshold and the "every value is a string" test in the guard exist
// only to work out which menus it accidentally intercepted; that guard is the
// mechanism confessing what it is. A pack cannot own a class it did not bring,
// and load order decides which of two packs doing this wins, silently.
//
// REFUSED, not a pending gap: markup as a menu entry. `title: newContent.outerHTML`
// hands the host a string of HTML to inject into a row it lays out. That makes
// the pack responsible for chrome we restyle, and it is why MenuItemDef.label
// and NodeSubMenuItem.label are plain strings. This one is not waiting on a
// richer menu API; a menu that renders pack-supplied HTML is the thing being
// declined.
//
// The capability is not refused and is not lost: core ships model browsing,
// with previews, for exactly these widgets. `WidgetSelect.vue` switches a
// model-valued combo into asset mode (`assetService.shouldUseAssetBrowser(nodeType,
// widget.name)`, WidgetSelect.vue:112) and opens `useAssetBrowserDialog`, whose
// `AssetCard.vue:28` and `AssetsListItem.vue:45` render `asset.preview_url`.
// So a user picking a checkpoint gets a browsable, filterable picker with
// thumbnails — the feature this file approximated by rewriting a menu — and
// gets it from the layer that owns model metadata rather than from a
// `/easyuse/models/thumbnail` scrape correlated by substring match.
//
// DROPPED: the `Comfy.EasyUse.MenuNestSub` setting, and with it the pack's own
// folder nesting for combos core does NOT treat as assets. Core's browser is
// keyed on the widget being a model input; a non-model combo with many
// slash-separated values is a flat list again.
//
// INOPERABLE: nothing. No node type is registered or extended by this file.

export {}
