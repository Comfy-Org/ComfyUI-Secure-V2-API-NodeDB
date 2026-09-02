import { comfy } from '/comfy/api/v2.js';

// REFUSED, not a pending gap: retuning the renderer's own geometry. The class
// defined a `_collapsed_width` accessor that reached for
// `app.canvas.canvas.getContext('2d')`, swapped in `canvas.title_text_font`,
// measured its own title and wrote the result back, so the collapsed node hugged
// its emoji. Measuring text in the renderer's context, with the renderer's font,
// to set a width the renderer will then use IS the renderer, and the renderer is
// ours to replace — a node that computes its own collapsed pill breaks the day
// collapsed nodes are laid out by anything else. `setSizeConstraints` is the
// published way to state what a node needs, and it deliberately does not reach
// the collapsed pill.
//
// `slot_start_y = -20` needs nothing: this node declares no inputs and no
// outputs, so there is no slot for it to move. It was copied in from a node that
// had some.
//
// The capability is not refused and is not lost: the renderer still draws a
// collapsed node with its title, and the title is still "🔖 <key>", set through
// `setTitle` below. Only the width the pill is drawn at changes.
//
// COSMETIC: a collapsed bookmark is drawn at the renderer's default collapsed
// width rather than one measured from its own emoji and shortcut key.
//
// LIMITATION: the shortcut centres the bookmarked node in the view. It used to
// put the node's top-left 16px in and 40px down from the viewport corner, by
// writing `canvas.ds.offset` directly; `graph.centerOn` is the published
// equivalent and centres instead, so the same node arrives at a slightly
// different place.

const keyListeners = new Map();

function shortcutKey(node) {
    return String(node.widgets.get('shortcut_key')?.getValue() ?? '');
}

function retitle(node) {
    const value = shortcutKey(node).trim();
    node.setTitle(value ? '🔖 ' + value : '🔖');
}

// The original wrote canvas.ds.offset/scale by hand. centerOn puts the node in
// the middle of the view rather than 16px from its top-left corner, which is
// the same intent expressed against the renderer that owns the transform.
function canvasToBookmark(node) {
    comfy.graph.centerOn(node);
    comfy.graph.setZoom(Number(node.widgets.get('zoom')?.getValue() || 1));
}

comfy.defs.define({
    type: 'easy bookmark',
    title: 'Bookmark 🔖',
    category: 'EasyUse/Util',
    execution: 'frontend',

    onCreated(node) {
        node.setSerializeWidgets(true);

        node.widgets.add({ type: 'text', name: 'shortcut_key', value: '1' })
            .on('change', () => retitle(node));
        node.widgets.add({
            type: 'number',
            name: 'zoom',
            value: 1,
            options: { max: 2, min: 0.5, precision: 2 },
        });

        retitle(node);

        const onKeydown = (event) => {
            if (['input', 'textarea'].includes(event.target?.localName)) return;
            const key = shortcutKey(node);
            if (key && event.key.toLocaleLowerCase() === key.toLocaleLowerCase()) {
                canvasToBookmark(node);
            }
        };
        window.addEventListener('keydown', onKeydown);
        keyListeners.set(node.id, onKeydown);
    },

    // Was a setTimeout(…, 1) in onAdded, which existed only to read the widget
    // value after the saved workflow had been applied.
    onConfigured(node) {
        retitle(node);
    },

    onRemoved(node) {
        const onKeydown = keyListeners.get(node.id);
        if (onKeydown) window.removeEventListener('keydown', onKeydown);
        keyListeners.delete(node.id);
    },
});
