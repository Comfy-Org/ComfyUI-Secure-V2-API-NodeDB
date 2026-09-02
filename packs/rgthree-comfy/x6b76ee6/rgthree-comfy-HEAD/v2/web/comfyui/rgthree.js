import { comfy } from '/comfy/api/v2.js';
import { canvasToBookmark } from './bookmark.js';
import { SERVICE as CONFIG_SERVICE } from './services/config_service.js';
import { SERVICE as BOOKMARKS_SERVICE, shortcutKeyOf } from './services/bookmarks_services.js';

let logLevel = String(CONFIG_SERVICE.getConfigValue('log_level') ?? 'ERROR').toUpperCase();

export const rgthree = Object.freeze({
    setLogLevel(value) {
        logLevel = String(value ?? 'ERROR').toUpperCase();
    },
    isDevMode() {
        if (window.location.href.includes('rgthree-dev=false')) return false;
        return logLevel === 'DEV' || window.location.href.includes('rgthree-dev');
    }
});

function nodeItems() {
    return comfy.defs.all()
        .filter((def) => def.type.endsWith('(rgthree)'))
        .sort((a, b) => a.title.localeCompare(b.title))
        .map((def) => ({
            label: def.title,
            run: () => {
                const node = comfy.graph.add(def.type, {
                    position: comfy.graph.pointerPosition() ?? { x: 0, y: 0 }
                });
                comfy.graph.select([node]);
            }
        }));
}

function reroutesToConvert() {
    const selected = comfy.graph.selection();
    const source = selected.length ? selected : comfy.graph.nodes();
    return source.filter((node) => node.type === 'Reroute');
}

async function convertReroutes() {
    const reroutes = reroutesToConvert();
    if (!reroutes.length) return;
    const scope = comfy.graph.selection().length ? 'selected' : 'all';
    const confirmed = window.confirm(
        `Convert ${scope} ComfyUI Reroutes to Reroute (rgthree) nodes?\n` +
        '(First save a copy of your workflow and check reroute connections afterwards)'
    );
    if (!confirmed) return;
    for (const node of reroutes) {
        comfy.graph.replace(node.id, 'Reroute (rgthree)');
    }
}

function bookmarkItems() {
    if (!CONFIG_SERVICE.getFeatureValue('menu_bookmarks.enabled')) return [];
    const bookmarks = BOOKMARKS_SERVICE.getCurrentBookmarks();
    if (!bookmarks.length) return [];
    return [{
        label: 'Bookmarks',
        submenu: bookmarks.map((bookmark) => ({
            label: `[${shortcutKeyOf(bookmark)}] ${bookmark.getTitle()}`,
            run: () => canvasToBookmark(bookmark)
        }))
    }];
}

comfy.ui.addActionBarButton({
    id: 'rgthree.menu',
    icon: 'icon-[lucide--network]',
    label: 'rgthree-comfy',
    run: (event) => {
        const reroutes = reroutesToConvert();
        const scope = comfy.graph.selection().length ? 'selected' : 'all';
        comfy.ui.showMenu({
            event,
            title: 'rgthree-comfy',
            items: [
                { label: 'Nodes', submenu: nodeItems() },
                {
                    label: `Convert ${scope} Reroutes`,
                    disabled: !reroutes.length,
                    run: () => void convertReroutes()
                },
                ...bookmarkItems(),
                {
                    label: 'Settings (rgthree-comfy)',
                    run: () => void comfy.commands.run('rgthree.openSettings')
                },
                {
                    label: 'Star on Github',
                    run: () => window.open('https://github.com/rgthree/rgthree-comfy', '_blank')
                }
            ]
        });
    }
});

// REFUSED: intercepting serialization and queue construction to read or rewrite
// built workflow and prompt payloads. Partial execution uses queue.run({ nodes });
// widget-specific serialization uses beforeSerialize.
// REFUSED: enumerating other packs and invoking their lifecycle callbacks.
// Definition extensions compose through the host registry instead.
// DROPPED: opening the group property editor automatically after Add Group.
// The group menu still exposes Title and Properties Panel through core.
// COSMETIC: the rgthree version badge on the host About page.
// The corrupt-link checker is now core's workflow validation and link fixer,
// adapted from rgthree's implementation in src/utils/linkFixer.ts.
