import { comfy } from '/comfy/api/v2.js';
import { SERVICE as BOOKMARKS_SERVICE, shortcutKeyOf } from "./services/bookmarks_services.js";
import { SERVICE as CONFIG_SERVICE } from "./services/config_service.js";
import { canvasToBookmark } from "./bookmark.js";

// The rgthree button group in ComfyUI's top bar: a menu with Settings and "Star on
// Github", and a bookmarks button listing the current workflow's Bookmark nodes.
//
// REFUSED, not a gap: how the group got there. `app.menu.settingsGroup.element.before(
//   rgthreeButtonGroup.element)` inserts a pack-built element into the host's chrome by
//   reaching for a named group inside it, and `RgthreeComfyButton` /
//   `RgthreeComfyButtonGroup` / `RgthreeComfyPopup` are 100 lines reimplementing
//   ComfyUI's own button, button-group and popup so the insert matches the surrounding
//   style. Both halves break the moment the chrome is restyled, and restyling the chrome
//   is exactly what the renderer replacement does. The published chrome contribution
//   takes no element, class or style: the pack says what it wants shown and the host
//   renders it. That is the control, not an omission.
//
// So the group becomes two declared buttons. Each is namespaced, each returns a handle,
// and `remove()` / re-registering is what the `comfy_top_bar_menu.enabled` toggle does —
// which is what the original's insert-or-detach dance was for.
//
// COSMETIC: the pack's own rgthree logo becomes a host icon. `ButtonContribution.icon`
//   is an iconify or PrimeIcons class rather than the pack's inline SVG, because the
//   host draws it.
// COSMETIC: two buttons where there was one button opening a popup menu. The chrome
//   takes a button, not a panel; both actions are still one click away, and Settings is
//   also in the command palette (`rgthree.openSettings`, registered in config.js).
// DROPPED: the bookmarks popup — a *list*, rebuilt from the current workflow each time
//   it opened, with one entry per Bookmark node. The chrome takes a fixed button, so
//   there is nowhere in the top bar to put a list. The bookmarks themselves are not lost
//   and were never reached only from here: each Bookmark node carries its own shortcut
//   key and jumps when pressed (bookmark.js), and rgthree.js's own canvas menu lists
//   them. `comfy.ui.addSidebarTab` would hold a list, but the sidebar is a different
//   place in the UI from the one this file targets — a port for the pack's author to
//   decide on, not a translation.
const buttons = new Map();
function addRgthreeTopBarButtons() {
    if (!CONFIG_SERVICE.getFeatureValue("comfy_top_bar_menu.enabled")) {
        for (const button of buttons.values()) {
            button.remove();
        }
        buttons.clear();
        return;
    }
    if (buttons.size) {
        return;
    }
    buttons.set("settings", comfy.ui.addActionBarButton({
        id: "rgthree.settings",
        icon: "pi-cog",
        label: "rgthree-comfy",
        tooltip: "Settings (rgthree-comfy)",
        run: () => {
            void comfy.commands.run("rgthree.openSettings");
        },
    }));
    buttons.set("github", comfy.ui.addActionBarButton({
        id: "rgthree.github",
        icon: "pi-star-fill",
        tooltip: "Star rgthree-comfy on Github",
        run: () => {
            window.open("https://github.com/rgthree/rgthree-comfy", "_blank");
        },
    }));
    if (CONFIG_SERVICE.getFeatureValue("comfy_top_bar_menu.button_bookmarks.enabled")) {
        buttons.set("bookmarks", comfy.ui.addActionBarButton({
            id: "rgthree.bookmarks",
            icon: "pi-bookmark",
            tooltip: "Workflow Bookmarks (rgthree-comfy)",
            // The popup listed every bookmark and jumped to the one clicked. A chrome
            // button has no panel, so the list is raised as a menu from the click
            // instead — `comfy.ui.showMenu` positions it under the pointer, and it is
            // rebuilt on each press exactly as the popup's `onOpen` rebuilt it.
            run: (event) => {
                const bookmarks = BOOKMARKS_SERVICE.getCurrentBookmarks();
                comfy.ui.showMenu({
                    event,
                    title: "Workflow Bookmarks",
                    items: bookmarks.length
                        ? bookmarks.map((b) => ({
                            label: `[${shortcutKeyOf(b)}] ${b.getTitle()}`,
                            run: () => {
                                canvasToBookmark(b);
                            },
                        }))
                        : [{ label: "No bookmarks in current workflow.", disabled: true }],
                });
            },
        }));
    }
}
// `setup()`, which is what `comfy.onReady` is. Re-running on the pack's own
// config-change event is an ordinary listener and needed nothing published.
comfy.onReady(() => {
    addRgthreeTopBarButtons();
    CONFIG_SERVICE.addEventListener("config-change", ((e) => {
        var _a, _b;
        if ((_b = (_a = e.detail) === null || _a === void 0 ? void 0 : _a.key) === null || _b === void 0 ? void 0 : _b.includes("features.comfy_top_bar_menu")) {
            addRgthreeTopBarButtons();
        }
    }));
});
