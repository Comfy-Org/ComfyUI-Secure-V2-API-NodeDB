import { comfy } from '/comfy/api/v2.js';

const kSampler = ['easy kSampler', 'easy kSamplerTiled', 'easy fullkSampler']

// The grid used to be painted over the node's own image area through
// onDrawBackground, laid out on the renderer's node.imageRects and hit-tested
// against them. It is now the pack's own widget canvas: the drawing and the hit
// test are unchanged in kind, but the surface belongs to the pack, and a widget
// states its own box rather than taking whatever body height is left.
const GRID_HEIGHT = 220;

/**
 * Per node: the previews, what is picked, and the surface they are drawn on.
 * Handles hold no arbitrary properties, so node.imgs, node.selected and
 * node.anti_selected live here.
 */
const choosers = new Map();

const chooserState = (nodeId) => choosers.get(nodeId);

function createChooser(nodeId) {
    const state = { imgs: [], rects: [], selected: new Set(), anti_selected: new Set(), surface: null, progress: null, cancel: null };
    choosers.set(nodeId, state);
    return state;
}

/** Row-major grid over the widget, replacing the renderer's imageRects. */
function cellRects(count, width, height) {
    const cols = Math.ceil(Math.sqrt(count));
    const rows = Math.ceil(count / cols);
    return Array.from({ length: count }, (_, i) => [
        (i % cols) * (width / cols), Math.floor(i / cols) * (height / rows),
        width / cols, height / rows,
    ]);
}

function drawRect(ctx, rect) {
    const padding = 1;
    ctx.strokeRect(rect[0]+padding, rect[1]+padding, rect[2]-padding*2, rect[3]-padding*2);
}

function drawChooser(state, ctx, width, height) {
    state.rects = cellRects(state.imgs.length, width, height);
    for (let i = 0; i < state.imgs.length; i++) {
        // delete underlying image
        ctx.fillStyle = "#000";
        ctx.fillRect(...state.rects[i])
        // draw the new one
        const img = state.imgs[i];
        const cellWidth = state.rects[i][2];
        const cellHeight = state.rects[i][3];

        let wratio = cellWidth/img.width;
        let hratio = cellHeight/img.height;
        var ratio = Math.min(wratio, hratio);

        let imgHeight = ratio * img.height;
        let imgWidth = ratio * img.width;

        const imgX = state.rects[i][0] + (cellWidth - imgWidth)/2;
        const imgY = state.rects[i][1] + (cellHeight - imgHeight)/2;
        const cell_padding = 2;
        ctx.drawImage(img, imgX+cell_padding, imgY+cell_padding, imgWidth-cell_padding*2, imgHeight-cell_padding*2);
    }
    ctx.lineWidth = 2;
    ctx.strokeStyle = "green";
    state.selected.forEach((s) => { if (state.rects[s]) drawRect(ctx, state.rects[s]) });
    ctx.strokeStyle = "#F88";
    state.anti_selected.forEach((s) => { if (state.rects[s]) drawRect(ctx, state.rects[s]) });
}

function click_is_in_image(state, x, y) {
    for (var i = 0; i < state.rects.length; i++) {
        const dx = x - state.rects[i][0];
        const dy = y - state.rects[i][1];
        if ( dx > 0 && dx < state.rects[i][2] &&
            dy > 0 && dy < state.rects[i][3] ) {
                return i;
            }
    }
    return -1;
}

/** Mounts the grid on one chooser node. */
function attachChooser(node, state, imageClicked) {
    const surface = node.widgets.canvas({
        name: "chooser_preview",
        height: GRID_HEIGHT,
        draw: (ctx, size) => drawChooser(state, ctx, size[0], size[1]),
        onPointerDown: (e) => {
            const i = click_is_in_image(state, e.x, e.y);
            if (i >= 0) imageClicked(i);
        },
    });
    // Without this the mounted canvas shares out whatever height the node has
    // spare, instead of the box it just declared.
    surface.widget.setHeight(GRID_HEIGHT);
    state.surface = surface;
}

// REFUSED, not a pending gap: writing the renderer's own image cache.
// `node.imgs = […]` is how the previews also appeared on the body of an
// `easy kSampler`-family node, which is not itself a chooser and carries no grid
// of ours. That array holds the loaded HTMLImageElements core hangs on a node to
// show what it produced; its lifetime is the renderer's, and a pack assigning to
// it makes a node it does not own claim outputs core never gave it.
// `getOutputImages()` is a read for that reason, and has no writer by design.
//
// The capability is not refused and is not lost: a node the pack DOES own draws
// its images itself, on its own surface — `attachChooser` above is exactly that,
// a `widgets.canvas` with `drawImage` in `draw`. And these previews already had
// a second, primary home in the original: the sampler branch opened
// `chooserImageDialog` over the node and still does.
//
// LIMITATION: on an `easy kSampler`-family node the previews appear only in the
// dialog. They used to also fill the node's body while the dialog was open.
function display_preview_images(detail) {
    const node = comfy.graph.node(String(detail.id));
    if (!node) {
        console.log(`Image Chooser Preview - failed to find ${detail.id}`)
        return;
    }
    // Created on demand for a sampler node: it has no grid and no buttons, but
    // the dialog still records its picks against it, exactly as node.selected did.
    const state = chooserState(node.id) ?? createChooser(node.id);
    state.selected.clear();
    state.anti_selected.clear();
    // Was app.getPreviewFormatParam(): the same setting, through the published
    // reader, which serves any id rather than only the ones this pack declared.
    const preview_format = comfy.settings.get('Comfy.PreviewFormat');
    const image = detail.urls.map((u)=> {
        const img = new Image();
        img.onload = () => { state.surface?.redraw(); };
        img.src = comfy.backend.url(`/view?filename=${encodeURIComponent(u.filename)}&type=temp&subfolder=${preview_format ? `&preview=${preview_format}` : ''}`)
        return img;
    })
    state.imgs = image;
    state.surface?.redraw();
    return {node,image,isKSampler:kSampler.includes(node.type)}
}

/** Every node holding picks, not only the choosers: samplers hold them too. */
function resetSelections() {
    for (const state of choosers.values()) {
        state.selected.clear();
        state.anti_selected.clear();
    }
}

export { chooserState, createChooser, attachChooser, display_preview_images, resetSelections }
