import { comfy } from '/comfy/api/v2.js';
import { DIMENSION_DEFAULTS } from './secureDimensionDefaults.js';

export function pointerDimensions(props, width, height, x, y, w, h, shiftKey, ctrlKey) {
    let vX = Math.max(0, Math.min(1, x / w));
    let vY = Math.max(0, Math.min(1, 1 - y / h));
    if (ctrlKey && shiftKey) {
        const currentAspect = width / height;
        let newX = props.canvas_min_x + (props.canvas_max_x - props.canvas_min_x) * vX;
        let newY = props.canvas_min_y + (props.canvas_max_y - props.canvas_min_y) * vY;
        newX = Math.round(newX); newY = Math.round(newY);
        newY = Math.round(newX / currentAspect);
        vX = (newX - props.canvas_min_x) / (props.canvas_max_x - props.canvas_min_x);
        vY = (newY - props.canvas_min_y) / (props.canvas_max_y - props.canvas_min_y);
    } else if (shiftKey && !ctrlKey) {
        const currentAspect = width / height;
        let newX = props.canvas_min_x + (props.canvas_max_x - props.canvas_min_x) * vX;
        let newY = props.canvas_min_y + (props.canvas_max_y - props.canvas_min_y) * vY;
        let sX = props.canvas_step_x / (props.canvas_max_x - props.canvas_min_x);
        let sY = props.canvas_step_y / (props.canvas_max_y - props.canvas_min_y);
        vX = Math.round(vX / sX) * sX;
        newX = props.canvas_min_x + (props.canvas_max_x - props.canvas_min_x) * vX;
        newY = newX / currentAspect;
        vY = (newY - props.canvas_min_y) / (props.canvas_max_y - props.canvas_min_y);
    } else if (!(ctrlKey && !shiftKey)) {
        let sX = props.canvas_step_x / (props.canvas_max_x - props.canvas_min_x);
        let sY = props.canvas_step_y / (props.canvas_max_y - props.canvas_min_y);
        vX = Math.round(vX / sX) * sX;
        vY = Math.round(vY / sY) * sY;
    }
    let newX = props.canvas_min_x + (props.canvas_max_x - props.canvas_min_x) * vX;
    let newY = props.canvas_min_y + (props.canvas_max_y - props.canvas_min_y) * vY;
    const rnX = Math.pow(10, props.canvas_decimals_x), rnY = Math.pow(10, props.canvas_decimals_y);
    newX = Math.round(rnX * newX) / rnX;
    newY = Math.round(rnY * newY) / rnY;
    return [newX, newY];
}
export function canvasBounds(props, x, y, w, h) {
    const ratio = (props.canvas_max_x - props.canvas_min_x) / (props.canvas_max_y - props.canvas_min_y);
    let canvasW = w - 20, canvasH = h - 20;
    if (ratio > canvasW / canvasH) canvasH = canvasW / ratio;
    else canvasW = canvasH * ratio;
    return { x: x + (w - canvasW) / 2, y: y + (h - canvasH) / 2, w: canvasW, h: canvasH };
}
export function validateCanvasWork(props) {
    const keys = ['canvas_min_x', 'canvas_max_x', 'canvas_step_x', 'canvas_min_y', 'canvas_max_y', 'canvas_step_y',
        'canvas_decimals_x', 'canvas_decimals_y'];
    if (!keys.every(key => Number.isFinite(props[key]))) throw new TypeError('canvas settings must be finite');
    const rx = props.canvas_max_x - props.canvas_min_x, ry = props.canvas_max_y - props.canvas_min_y;
    if (!(rx > 0 && ry > 0 && props.canvas_step_x > 0 && props.canvas_step_y > 0) ||
        Math.ceil(rx / props.canvas_step_x) * Math.ceil(ry / props.canvas_step_y) > 16384)
        throw new RangeError('canvas dot-grid workload refused');
    if (![props.canvas_decimals_x, props.canvas_decimals_y].every(value => Number.isInteger(value) && value >= 0 && value <= 12))
        throw new RangeError('canvas decimal workload refused');
}
export function createDimensionController(node, kind, facade) {
    const defaults = DIMENSION_DEFAULTS[kind];
    const width = node.widgets.get('width'), height = node.widgets.get('height');
    if (!width || !height) throw Error('dimension backend widgets missing');
    let props = {}, alive = true, capture = false, bounds, surface, dialog;
    const offs = [];
    function readProps() {
        props = { ...defaults, ...node.getProperties() };
        validateCanvasWork(props);
        props.valueX = width.getValue(); props.valueY = height.getValue();
        if (![props.valueX, props.valueY].every(Number.isFinite)) throw TypeError('dimensions must be finite');
    }
    readProps();
    for (const [key, value] of Object.entries(defaults))
        if (node.getProperty(key) == null) node.setProperty(key, value);
    width.setHidden(true); height.setHidden(true);
    function dimensions(w, h) {
        if (!alive) return;
        if (![w, h].every(Number.isFinite)) throw TypeError('dimensions must be finite');
        props.valueX = w; props.valueY = h;
        node.setProperty('valueX', w); node.setProperty('valueY', h);
        width.setValue(w); height.setValue(h);
        surface?.redraw();
    }
    for (const widget of node.widgets.all()) {
        if (['width', 'height', 'fps', 'length_selector', 'total_frames', 'num_seconds'].includes(widget.name))
            offs.push(widget.on('change', () => { if (alive) { readProps(); surface?.redraw(); } }));
    }
    const hit = (x, y, rect) => rect && x >= rect.x && x <= rect.x + rect.w && y >= rect.y && y <= rect.y + rect.h;
    function valueDialog(axis) {
        if (!alive || dialog) return;
        const current = axis === 'width' ? width.getValue() : height.getValue();
        let input, apply, feedback;
        const listeners = [];
        const close = () => { const handle = dialog; dialog = null; handle?.close(); };
        const validate = () => {
            const value = parseFloat(input.value);
            const valid = Number.isFinite(value) && value >= 64;
            feedback.textContent = valid ? '' : 'Value must be ≥ 64';
            apply.disabled = !valid; return valid;
        };
        const commit = () => {
            if (!alive || !validate()) return;
            const value = Math.round(parseFloat(input.value));
            dimensions(axis === 'width' ? value : width.getValue(), axis === 'height' ? value : height.getValue());
            close();
        };
        dialog = facade.ui.showDialog({
            key: 'handy-dimension-' + node.graphId + '-' + node.id,
            title: 'Set Custom ' + (axis === 'width' ? 'Width' : 'Height'),
            render(container) {
                const doc = container.ownerDocument;
                input = doc.createElement('input'); input.type = 'number'; input.value = String(current); input.min = '64'; input.step = '.01';
                feedback = doc.createElement('div');
                const cancel = doc.createElement('button'); cancel.textContent = 'Cancel';
                apply = doc.createElement('button'); apply.textContent = 'Apply';
                for (const [element, event, callback] of [[input, 'input', validate], [cancel, 'click', close], [apply, 'click', commit]]) {
                    element.addEventListener(event, callback); listeners.push(() => element.removeEventListener(event, callback));
                }
                container.append(input, feedback, cancel, apply); validate();
            },
            onKeyDown(event) { if (event.key === 'Escape') close(); else if (event.key === 'Enter') commit(); },
            destroy() { dialog = null; for (const off of listeners.splice(0)) off(); },
        });
    }
    const move = ({ x, y, event }) => {
        if (!alive || !capture || !bounds) return;
        if (event.buttons === 0) { capture = false; return; }
        const [w, h] = pointerDimensions(props, width.getValue(), height.getValue(),
            x - bounds.x, y - bounds.y, bounds.w, bounds.h, event.shiftKey, event.ctrlKey);
        dimensions(w, h);
    };
    surface = node.widgets.canvas({
        name: 'tk_dimension_canvas', height: 305, serialize: false, sendToPrompt: false,
        draw(ctx, [widgetWidth]) {
            if (!alive) return;
            readProps();
            if (props.mode !== 'Manual') return;
            if (props.useCustomCalc && props.selectedCategory)
                throw TypeError('this.drawInfoMessage is not a function'); // observed pinned missing-method branch
            bounds = canvasBounds(props, 10, 60, widgetWidth - 20, 200);
            const { x, y, w, h } = bounds;
            const rx = props.canvas_max_x - props.canvas_min_x, ry = props.canvas_max_y - props.canvas_min_y;
            const ix = Math.max(0, Math.min(1, (width.getValue() - props.canvas_min_x) / rx));
            const iy = Math.max(0, Math.min(1, (height.getValue() - props.canvas_min_y) / ry));
            ctx.fillStyle = 'rgba(20,20,20,0.8)'; ctx.strokeStyle = 'rgba(0,0,0,0.5)'; ctx.lineWidth = 1;
            ctx.beginPath(); ctx.roundRect(x - 4, y - 4, w + 8, h + 8, 6); ctx.fill(); ctx.stroke();
            if (props.canvas_dots) {
                ctx.fillStyle = 'rgba(200,200,200,0.5)'; ctx.beginPath();
                const sx = w * props.canvas_step_x / rx, sy = h * props.canvas_step_y / ry;
                for (let dx = sx; dx < w; dx += sx) for (let dy = sy; dy < h; dy += sy) ctx.rect(x + dx - .5, y + dy - .5, 1, 1);
                ctx.fill();
            }
            if (props.canvas_frame) {
                ctx.fillStyle = 'rgba(150,150,250,0.1)'; ctx.strokeStyle = 'rgba(150,150,250,0.7)'; ctx.lineWidth = 1.5;
                ctx.beginPath(); ctx.rect(x, y + h * (1 - iy), w * ix, h * iy); ctx.fill(); ctx.stroke();
            }
            ctx.fillStyle = '#FFF'; ctx.strokeStyle = '#000'; ctx.lineWidth = 2;
            ctx.beginPath(); ctx.arc(x + w * ix, y + h * (1 - iy), 8, 0, 2 * Math.PI); ctx.fill(); ctx.stroke();
            ctx.font = '11px Arial'; ctx.fillStyle = 'rgba(200,200,200,0.8)'; ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
            ctx.fillText(kind === 'TKPhotoUserInputs' ? 'photo_width' : 'video_width', widgetWidth - 20, 15);
            ctx.fillText(kind === 'TKPhotoUserInputs' ? 'photo_height' : 'video_height', widgetWidth - 20, 35);
            ctx.fillStyle = '#bbb'; ctx.font = '12px Arial'; ctx.textAlign = 'center';
            ctx.fillText(width.getValue() + ' × ' + height.getValue() + '  ', widgetWidth / 2, 283);
            if (kind === 'TKVideoUserInputs') {
                const fps = node.widgets.get('fps')?.getValue(), secs = node.widgets.get('num_seconds')?.getValue();
                const frames = node.widgets.get('total_frames')?.getValue(), selector = node.widgets.get('length_selector')?.getValue();
                const text = selector === 'Use # Frames'
                    ? 'FRAMES:' + frames + '   FPS:' + fps + '   DUR:' + (frames / fps).toFixed(1) + '  '
                    : 'FRAMES:' + (fps * secs).toFixed(0) + '   FPS:' + fps + '   DUR:' + secs + '  ';
                ctx.fillText(text, widgetWidth / 2, 268);
            }
        },
        onPointerDown({ x, y, event }) {
            if (!alive || event.button !== 0) return;
            if (hit(x, y, bounds)) { capture = true; move({ x, y, event: { buttons: 1, shiftKey: event.shiftKey, ctrlKey: event.ctrlKey } }); }
            else {
                const w = node.getSize().width;
                if (hit(x, y, { x: w - 65, y: 5, w: 60, h: 20 })) valueDialog('width');
                else if (hit(x, y, { x: w - 65, y: 25, w: 60, h: 20 })) valueDialog('height');
            }
        },
        onPointerMove: move,
        onPointerUp() { if (!alive || !capture) return; capture = false; dimensions(props.valueX, props.valueY); },
    });
    node.setSizeConstraints({ minWidth: 200, minHeight: 300, autoHeight: true });
    return {
        configured() { if (alive) { readProps(); surface.redraw(); } },
        dispose() { if (!alive) return; alive = false; capture = false; dialog?.close(); dialog = null; for (const off of offs.splice(0)) off(); },
    };
}
export function registerDimension(kind) {
    const controllers = new WeakMap();
    comfy.defs.extend(kind, builder => {
        builder.onCreated(node => { controllers.set(node, createDimensionController(node, kind, comfy)); });
        builder.onConfigured(node => { controllers.get(node)?.configured(); });
        builder.onRemoved(node => { controllers.get(node)?.dispose(); controllers.delete(node); });
        builder.onPropertyChanged?.(node => { controllers.get(node)?.configured(); });
    });
}
// Active confined frontend graph; archival diagnostics are outside WEB_DIRECTORY.
