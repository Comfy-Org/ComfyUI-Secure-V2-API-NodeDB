import { comfy } from '/comfy/api/v2.js';


const INTERACTIVE = 'TTP_Smart_Tile_Interactive_Crop_Experimental';
const LOOP_SOURCE = 'TTP_Smart_Tile_Loop_Source_Experimental';
const LOOP_COLLECT = 'TTP_Smart_Tile_Loop_Collect_Experimental';
const MAX_TILES = 64;
const editors = new Map();
const loops = new Map();

const keyFor = (node) => `${String(node.graphId ?? '')}:${String(node.id)}`;

function widget(node, name) {
    return node.widgets.get(name);
}

function widgetValue(node, name, fallback) {
    const value = widget(node, name)?.getValue();
    return value === undefined || value === null ? fallback : value;
}

function setWidget(node, name, value) {
    widget(node, name)?.setValue(value);
}

function bounded(value, fallback, minimum, maximum) {
    const number = Number(value);
    return Number.isFinite(number)
        ? Math.max(minimum, Math.min(maximum, number))
        : fallback;
}

function normalizedTile(raw = {}, index = 0) {
    const x0 = bounded(raw.x0 ?? raw.x ?? 0, 0, 0, 1);
    const y0 = bounded(raw.y0 ?? raw.y ?? 0, 0, 0, 1);
    const x1 = bounded(raw.x1 ?? (x0 + Number(raw.w ?? 0.5)), 1, 0, 1);
    const y1 = bounded(raw.y1 ?? (y0 + Number(raw.h ?? 0.5)), 1, 0, 1);
    const left = Math.min(x0, x1);
    const top = Math.min(y0, y1);
    const right = Math.max(left + 0.01, Math.max(x0, x1));
    const bottom = Math.max(top + 0.01, Math.max(y0, y1));
    return {
        ...raw,
        name: String(raw.name ?? `tile_${index + 1}`).slice(0, 128),
        x0: Number(left.toFixed(6)),
        y0: Number(top.toFixed(6)),
        x1: Number(Math.min(1, right).toFixed(6)),
        y1: Number(Math.min(1, bottom).toFixed(6)),
    };
}

function grid(columns, rows) {
    const cols = Math.max(1, Math.min(8, Math.round(Number(columns) || 1)));
    const rowCount = Math.max(1, Math.min(8, Math.round(Number(rows) || 1)));
    const result = [];
    for (let row = 0; row < rowCount; row += 1) {
        for (let column = 0; column < cols; column += 1) {
            result.push(normalizedTile({
                name: `grid_${row + 1}_${column + 1}`,
                label: 'grid tile',
                source: 'manual_grid',
                x0: column / cols,
                y0: row / rowCount,
                x1: (column + 1) / cols,
                y1: (row + 1) / rowCount,
            }, result.length));
        }
    }
    return result.slice(0, MAX_TILES);
}

function parseLayout(node) {
    try {
        const parsed = JSON.parse(String(widgetValue(node, 'layout_json', '') || '{}'));
        const tiles = Array.isArray(parsed.tiles) ? parsed.tiles : [];
        if (tiles.length) return tiles.slice(0, MAX_TILES).map(normalizedTile);
    } catch (_error) {
        // A malformed saved value is repaired to the pack's default layout.
    }
    return grid(2, 2);
}

function serializedLayout(state) {
    return JSON.stringify({
        version: 1,
        type: 'ttp_smart_tile_interactive_layout',
        defaults: {
            pad: Math.round(bounded(widgetValue(state.node, 'default_pad', 128), 128, 0, 4096)),
            blend: Math.round(bounded(widgetValue(state.node, 'default_blend', 64), 64, 0, 2048)),
        },
        tiles: state.tiles.slice(0, MAX_TILES).map(normalizedTile),
    });
}

function commit(state) {
    state.tiles = state.tiles.slice(0, MAX_TILES).map(normalizedTile);
    state.selected = Math.max(0, Math.min(state.tiles.length - 1, state.selected));
    setWidget(state.node, 'layout_json', serializedLayout(state));
    draw(state);
}

function point(event, canvas) {
    const bounds = canvas.getBoundingClientRect();
    return {
        x: bounded((event.clientX - bounds.left) / Math.max(1, bounds.width), 0, 0, 1),
        y: bounded((event.clientY - bounds.top) / Math.max(1, bounds.height), 0, 0, 1),
    };
}

function hitTile(state, position) {
    for (let index = state.tiles.length - 1; index >= 0; index -= 1) {
        const tile = state.tiles[index];
        if (position.x >= tile.x0 && position.x <= tile.x1
            && position.y >= tile.y0 && position.y <= tile.y1) return index;
    }
    return -1;
}

function draw(state) {
    const { canvas, context } = state;
    if (!canvas || !context) return;
    const width = canvas.width;
    const height = canvas.height;
    context.clearRect(0, 0, width, height);
    context.fillStyle = '#111827';
    context.fillRect(0, 0, width, height);
    if (state.image) {
        context.globalAlpha = 0.72;
        context.drawImage(state.image, 0, 0, width, height);
        context.globalAlpha = 1;
    }
    context.strokeStyle = '#334155';
    context.lineWidth = 1;
    for (let step = 1; step < 8; step += 1) {
        context.beginPath();
        context.moveTo(width * step / 8, 0);
        context.lineTo(width * step / 8, height);
        context.stroke();
        context.beginPath();
        context.moveTo(0, height * step / 8);
        context.lineTo(width, height * step / 8);
        context.stroke();
    }
    state.tiles.forEach((tile, index) => {
        const x = tile.x0 * width;
        const y = tile.y0 * height;
        const w = (tile.x1 - tile.x0) * width;
        const h = (tile.y1 - tile.y0) * height;
        const selected = state.selectedSet.has(index);
        context.fillStyle = selected
            ? 'rgba(56,189,248,.28)'
            : 'rgba(129,140,248,.16)';
        context.strokeStyle = selected ? '#7dd3fc' : '#a5b4fc';
        context.lineWidth = selected ? 3 : 1.5;
        context.fillRect(x, y, w, h);
        context.strokeRect(x, y, w, h);
        context.fillStyle = '#f8fafc';
        context.font = 'bold 12px system-ui';
        context.fillText(`T${index + 1}`, x + 5, y + 15);
    });
    if (state.paintCanvas && state.paintHasPixels) {
        context.globalAlpha = 0.42;
        context.drawImage(state.paintCanvas, 0, 0, width, height);
        context.globalAlpha = 1;
    }
    state.status.textContent = state.message
        || `${state.tiles.length} tile(s); drag edges to resize, Shift-click to multi-select.`;
}

function parseAnnotatedImageName(value) {
    let name = String(value || '').trim();
    let type = 'input';
    const match = name.match(/\s*\[(input|output|temp)\]\s*$/i);
    if (match) {
        type = match[1].toLowerCase();
        name = name.slice(0, match.index).trim();
    }
    name = name.replaceAll('\\', '/');
    const slash = name.lastIndexOf('/');
    return {
        filename: slash >= 0 ? name.slice(slash + 1) : name,
        subfolder: slash >= 0 ? name.slice(0, slash) : '',
        type,
    };
}

function inputImageUrl(value) {
    const parsed = parseAnnotatedImageName(value);
    if (!parsed.filename) return '';
    const query = new URLSearchParams(parsed);
    return comfy.backend.url(`/view?${query.toString()}`);
}

function loadInputPreview(state, factory) {
    const url = inputImageUrl(widgetValue(state.node, 'image', ''));
    if (!url) {
        state.image = null;
        draw(state);
        return;
    }
    const image = factory.createElement('img');
    image.addEventListener('load', () => {
        state.image = image;
        state.message = '';
        draw(state);
    });
    image.addEventListener('error', () => {
        state.image = null;
        state.message = 'Selected input image could not be previewed.';
        draw(state);
    });
    image.src = url;
}

function syncPaintMask(state) {
    if (!state.paintCanvas || !state.paintHasPixels) {
        setWidget(state.node, 'auto_paint_mask', '');
        return;
    }
    const data = state.paintCanvas.toDataURL('image/png');
    setWidget(state.node, 'auto_paint_mask', JSON.stringify({
        data,
        width: state.paintCanvas.width,
        height: state.paintCanvas.height,
    }));
}

function paintBounds(state) {
    if (!state.paintCanvas || !state.paintHasPixels) return null;
    const context = state.paintCanvas.getContext('2d');
    const pixels = context.getImageData(
        0, 0, state.paintCanvas.width, state.paintCanvas.height).data;
    let left = state.paintCanvas.width;
    let top = state.paintCanvas.height;
    let right = -1;
    let bottom = -1;
    for (let y = 0; y < state.paintCanvas.height; y += 1) {
        for (let x = 0; x < state.paintCanvas.width; x += 1) {
            if (pixels[(y * state.paintCanvas.width + x) * 4 + 3] <= 8) continue;
            left = Math.min(left, x);
            top = Math.min(top, y);
            right = Math.max(right, x);
            bottom = Math.max(bottom, y);
        }
    }
    if (right < left || bottom < top) return null;
    return normalizedTile({
        name: `paint_${state.tiles.length + 1}`,
        label: 'paint mask',
        source: 'paint_mask',
        x0: left / state.paintCanvas.width,
        y0: top / state.paintCanvas.height,
        x1: (right + 1) / state.paintCanvas.width,
        y1: (bottom + 1) / state.paintCanvas.height,
    }, state.tiles.length);
}

function uncoveredTiles(tiles) {
    const steps = 16;
    const cells = [];
    for (let row = 0; row < steps; row += 1) {
        for (let column = 0; column < steps; column += 1) {
            const x = (column + 0.5) / steps;
            const y = (row + 0.5) / steps;
            if (!tiles.some((tile) => x >= tile.x0 && x <= tile.x1
                && y >= tile.y0 && y <= tile.y1)) cells.push({ row, column });
        }
    }
    return cells.map(({ row, column }, index) => normalizedTile({
        name: `gap_${index + 1}`,
        label: 'gap fill',
        source: 'gap_fill',
        x0: column / steps,
        y0: row / steps,
        x1: (column + 1) / steps,
        y1: (row + 1) / steps,
    }, tiles.length + index));
}

function control(factory, tag, text = '') {
    const item = factory.createElement(tag);
    if (text) item.textContent = text;
    item.style.boxSizing = 'border-box';
    item.style.minHeight = '28px';
    item.style.color = '#e5e7eb';
    item.style.background = '#1e293b';
    item.style.border = '1px solid #475569';
    item.style.borderRadius = '5px';
    item.style.padding = '3px 7px';
    return item;
}

function button(factory, label, action) {
    const item = control(factory, 'button', label);
    item.type = 'button';
    item.style.cursor = 'pointer';
    item.addEventListener('click', action);
    return item;
}

function applyBackendLayout(state, result) {
    const payload = result?.raw?.ttp_smart_tile_layout;
    const item = Array.isArray(payload) ? payload[0] : payload;
    if (!item || typeof item !== 'object') return;
    if (item.layout_json) {
        setWidget(state.node, 'layout_json', String(item.layout_json));
        state.tiles = parseLayout(state.node);
        state.selected = 0;
    }
    state.message = String(item.message || (item.ok ? 'Auto layout ready.' : 'Auto layout failed.'));
    draw(state);
}

function mountEditor(node) {
    const key = keyFor(node);
    const state = {
        node,
        tiles: parseLayout(node),
        selected: 0,
        selectedSet: new Set([0]),
        canvas: null,
        context: null,
        status: null,
        drag: null,
        message: '',
        image: null,
        paintCanvas: null,
        paintMode: 'off',
        paintHasPixels: false,
        unsubscribers: [],
    };
    editors.set(key, state);
    for (const name of ['layout_json', 'auto_detect_request', 'auto_paint_mask']) {
        widget(node, name)?.setHidden(true);
    }
    node.setSizeConstraints({ minWidth: 430, minHeight: 520 });
    node.widgets.mount({
        name: 'ttp_smart_tile_editor_v2',
        height: 390,
        hideOnZoom: false,
        serialize: false,
        sendToPrompt: false,
        render(container) {
            const factory = container.ownerDocument;
            const root = control(factory, 'section');
            root.style.display = 'grid';
            root.style.gap = '7px';
            root.style.padding = '7px';
            root.style.background = '#0f172a';
            root.style.font = '12px system-ui, sans-serif';
            const title = control(factory, 'strong', 'Smart Tile layout');
            title.style.border = '0';
            title.style.background = 'transparent';
            root.appendChild(title);
            const canvas = factory.createElement('canvas');
            canvas.width = 400;
            canvas.height = 230;
            canvas.style.width = '100%';
            canvas.style.height = '230px';
            canvas.style.border = '1px solid #475569';
            canvas.style.borderRadius = '5px';
            canvas.style.touchAction = 'none';
            canvas.style.cursor = 'move';
            state.canvas = canvas;
            state.context = canvas.getContext('2d');
            state.paintCanvas = factory.createElement('canvas');
            state.paintCanvas.width = canvas.width;
            state.paintCanvas.height = canvas.height;
            root.appendChild(canvas);

            const row = factory.createElement('div');
            row.style.display = 'flex';
            row.style.gap = '5px';
            row.style.flexWrap = 'wrap';
            const columns = control(factory, 'input');
            columns.type = 'number';
            columns.min = '1';
            columns.max = '8';
            columns.value = '2';
            columns.style.width = '52px';
            const rows = control(factory, 'input');
            rows.type = 'number';
            rows.min = '1';
            rows.max = '8';
            rows.value = '2';
            rows.style.width = '52px';
            row.append(
                columns,
                rows,
                button(factory, 'Set grid', () => {
                    state.tiles = grid(columns.value, rows.value);
                    state.selected = 0;
                    state.selectedSet = new Set([0]);
                    state.message = 'Grid layout applied.';
                    commit(state);
                }),
                button(factory, 'Grid in selected', () => {
                    const selected = state.tiles[state.selected];
                    if (!selected) return;
                    const children = grid(columns.value, rows.value).map((tile, index) => normalizedTile({
                        ...tile,
                        name: `${selected.name}_grid_${index + 1}`,
                        x0: selected.x0 + tile.x0 * (selected.x1 - selected.x0),
                        y0: selected.y0 + tile.y0 * (selected.y1 - selected.y0),
                        x1: selected.x0 + tile.x1 * (selected.x1 - selected.x0),
                        y1: selected.y0 + tile.y1 * (selected.y1 - selected.y0),
                    }, index));
                    state.tiles.splice(state.selected, 1, ...children);
                    state.tiles = state.tiles.slice(0, MAX_TILES);
                    state.selectedSet = new Set([state.selected]);
                    state.message = 'Selected tile split into a grid.';
                    commit(state);
                }),
                button(factory, 'Add tile', () => {
                    if (state.tiles.length >= MAX_TILES) return;
                    state.tiles.push(normalizedTile({
                        name: `manual_${state.tiles.length + 1}`,
                        label: 'manual focus',
                        source: 'manual',
                        x0: 0.25,
                        y0: 0.25,
                        x1: 0.75,
                        y1: 0.75,
                    }, state.tiles.length));
                    state.selected = state.tiles.length - 1;
                    state.selectedSet = new Set([state.selected]);
                    state.message = 'Tile added.';
                    commit(state);
                }),
                button(factory, 'Delete', () => {
                    if (state.tiles.length <= 1) return;
                    state.tiles.splice(state.selected, 1);
                    state.selected = Math.max(0, state.selected - 1);
                    state.selectedSet = new Set([state.selected]);
                    state.message = 'Tile removed.';
                    commit(state);
                }),
                button(factory, 'Merge selected', () => {
                    const indexes = [...state.selectedSet].sort((a, b) => a - b);
                    if (indexes.length < 2) return;
                    const chosen = indexes.map((index) => state.tiles[index]).filter(Boolean);
                    const merged = normalizedTile({
                        ...chosen[0],
                        name: 'merged_tile',
                        label: 'merged tiles',
                        source: 'manual_merge',
                        x0: Math.min(...chosen.map((tile) => tile.x0)),
                        y0: Math.min(...chosen.map((tile) => tile.y0)),
                        x1: Math.max(...chosen.map((tile) => tile.x1)),
                        y1: Math.max(...chosen.map((tile) => tile.y1)),
                    });
                    state.tiles = state.tiles.filter((_tile, index) => !state.selectedSet.has(index));
                    state.tiles.push(merged);
                    state.selected = state.tiles.length - 1;
                    state.selectedSet = new Set([state.selected]);
                    state.message = 'Selected tiles merged.';
                    commit(state);
                }),
                button(factory, 'Fill gaps', () => {
                    const gaps = uncoveredTiles(state.tiles);
                    const room = MAX_TILES - state.tiles.length;
                    const added = Math.min(gaps.length, room);
                    state.tiles.push(...gaps.slice(0, room));
                    state.message = gaps.length
                        ? `${added} gap tile(s) added.`
                        : 'Layout already covers the image.';
                    commit(state);
                }),
                button(factory, 'Brush', () => {
                    state.paintMode = state.paintMode === 'paint' ? 'off' : 'paint';
                    state.message = state.paintMode === 'paint' ? 'Paint mask mode.' : 'Paint mode off.';
                    draw(state);
                }),
                button(factory, 'Erase', () => {
                    state.paintMode = state.paintMode === 'erase' ? 'off' : 'erase';
                    state.message = state.paintMode === 'erase' ? 'Erase mask mode.' : 'Paint mode off.';
                    draw(state);
                }),
                button(factory, 'Mask to tile', () => {
                    const tile = paintBounds(state);
                    if (!tile || state.tiles.length >= MAX_TILES) return;
                    state.tiles.push(tile);
                    state.selected = state.tiles.length - 1;
                    state.selectedSet = new Set([state.selected]);
                    state.message = 'Paint mask bounds added as a tile.';
                    syncPaintMask(state);
                    commit(state);
                }),
                button(factory, 'Clear mask', () => {
                    state.paintCanvas.getContext('2d').clearRect(
                        0, 0, state.paintCanvas.width, state.paintCanvas.height);
                    state.paintHasPixels = false;
                    state.paintMode = 'off';
                    syncPaintMask(state);
                    state.message = 'Paint mask cleared.';
                    draw(state);
                }),
                button(factory, 'Auto Tile', async () => {
                    syncPaintMask(state);
                    setWidget(node, 'auto_detect_request', Number(widgetValue(node, 'auto_detect_request', 0)) + 1);
                    state.message = 'Auto layout queued…';
                    draw(state);
                    await comfy.queue.run();
                }),
                button(factory, 'Auto SAM', async () => {
                    syncPaintMask(state);
                    setWidget(node, 'auto_detect_mode', 'sam3.1');
                    setWidget(node, 'auto_detect_request', Number(widgetValue(node, 'auto_detect_request', 0)) + 1);
                    state.message = 'SAM3 layout queued…';
                    draw(state);
                    await comfy.queue.run();
                }),
            );
            root.appendChild(row);
            const status = factory.createElement('output');
            status.style.color = '#cbd5e1';
            state.status = status;
            root.appendChild(status);
            container.appendChild(root);

            canvas.addEventListener('pointerdown', (event) => {
                const position = point(event, canvas);
                if (state.paintMode !== 'off') {
                    state.drag = { mode: 'paint', pointer: position };
                    canvas.setPointerCapture?.(event.pointerId);
                    const paint = state.paintCanvas.getContext('2d');
                    paint.globalCompositeOperation = state.paintMode === 'erase'
                        ? 'destination-out' : 'source-over';
                    paint.fillStyle = '#ffffff';
                    paint.beginPath();
                    paint.arc(position.x * canvas.width, position.y * canvas.height, 12, 0, Math.PI * 2);
                    paint.fill();
                    state.paintHasPixels = true;
                    draw(state);
                    return;
                }
                const index = hitTile(state, position);
                if (index < 0) return;
                state.selected = index;
                if (event.shiftKey) {
                    if (state.selectedSet.has(index) && state.selectedSet.size > 1) state.selectedSet.delete(index);
                    else state.selectedSet.add(index);
                } else {
                    state.selectedSet = new Set([index]);
                }
                const tile = state.tiles[index];
                const edge = 0.03;
                const nearRight = Math.abs(position.x - tile.x1) <= edge;
                const nearBottom = Math.abs(position.y - tile.y1) <= edge;
                state.drag = {
                    mode: nearRight || nearBottom ? 'resize' : 'move',
                    resizeX: nearRight,
                    resizeY: nearBottom,
                    pointer: position,
                    tile: { ...tile },
                };
                canvas.setPointerCapture?.(event.pointerId);
                draw(state);
            });
            canvas.addEventListener('pointermove', (event) => {
                if (!state.drag) return;
                const position = point(event, canvas);
                if (state.drag.mode === 'paint') {
                    const paint = state.paintCanvas.getContext('2d');
                    paint.globalCompositeOperation = state.paintMode === 'erase'
                        ? 'destination-out' : 'source-over';
                    paint.strokeStyle = '#ffffff';
                    paint.lineWidth = 24;
                    paint.lineCap = 'round';
                    paint.beginPath();
                    paint.moveTo(
                        state.drag.pointer.x * canvas.width,
                        state.drag.pointer.y * canvas.height,
                    );
                    paint.lineTo(position.x * canvas.width, position.y * canvas.height);
                    paint.stroke();
                    state.drag.pointer = position;
                    state.paintHasPixels = true;
                    draw(state);
                    return;
                }
                const dx = position.x - state.drag.pointer.x;
                const dy = position.y - state.drag.pointer.y;
                const base = state.drag.tile;
                if (state.drag.mode === 'resize') {
                    state.tiles[state.selected] = normalizedTile({
                        ...base,
                        x1: state.drag.resizeX ? position.x : base.x1,
                        y1: state.drag.resizeY ? position.y : base.y1,
                    }, state.selected);
                    draw(state);
                    return;
                }
                const width = base.x1 - base.x0;
                const height = base.y1 - base.y0;
                const x0 = bounded(base.x0 + dx, base.x0, 0, 1 - width);
                const y0 = bounded(base.y0 + dy, base.y0, 0, 1 - height);
                state.tiles[state.selected] = normalizedTile({
                    ...base,
                    x0,
                    y0,
                    x1: x0 + width,
                    y1: y0 + height,
                }, state.selected);
                draw(state);
            });
            const finish = (event) => {
                if (!state.drag) return;
                const painted = state.drag.mode === 'paint';
                state.drag = null;
                canvas.releasePointerCapture?.(event.pointerId);
                if (painted) {
                    syncPaintMask(state);
                    state.message = 'Paint mask updated.';
                    draw(state);
                } else {
                    state.message = 'Tile position updated.';
                    commit(state);
                }
            };
            canvas.addEventListener('pointerup', finish);
            canvas.addEventListener('pointercancel', finish);
            state.unsubscribers.push(widget(node, 'image')?.on(
                'change', () => loadInputPreview(state, factory)) ?? (() => {}));
            loadInputPreview(state, factory);
            commit(state);
        },
        destroy() {
            for (const unsubscribe of state.unsubscribers.splice(0)) unsubscribe();
            editors.delete(key);
        },
    });
    return state;
}

function loopPayload(result) {
    const raw = result?.raw?.ttp_smart_tile_loop;
    return Array.isArray(raw) ? raw[0] : raw;
}

function setLoopStatus(state, message) {
    state.message = String(message || 'Idle.');
    if (state.status) state.status.textContent = state.message;
}

async function queueLoop(state, restart) {
    if (restart) {
        setWidget(state.node, 'restart_request', Number(widgetValue(state.node, 'restart_request', 0)) + 1);
    }
    setWidget(state.node, 'loop_request', Number(widgetValue(state.node, 'loop_request', 0)) + 1);
    state.active = true;
    setLoopStatus(state, restart ? 'Starting tile loop…' : 'Queueing next tile…');
    try {
        await comfy.queue.run();
    } catch (error) {
        state.active = false;
        setLoopStatus(state, error?.message || 'Could not queue tile loop.');
    }
}

function mountLoop(node) {
    const key = keyFor(node);
    const state = { node, active: false, message: 'Idle.', status: null };
    loops.set(key, state);
    widget(node, 'restart_request')?.setHidden(true);
    widget(node, 'loop_request')?.setHidden(true);
    node.widgets.mount({
        name: 'ttp_smart_tile_loop_v2',
        height: 82,
        serialize: false,
        sendToPrompt: false,
        render(container) {
            const factory = container.ownerDocument;
            const root = factory.createElement('section');
            root.style.display = 'grid';
            root.style.gap = '5px';
            const buttons = factory.createElement('div');
            buttons.style.display = 'flex';
            buttons.style.gap = '6px';
            const start = button(factory, 'Start Loop / Process All Tiles', () => queueLoop(state, true));
            start.style.background = '#2563eb';
            const stop = button(factory, 'Stop', () => {
                state.active = false;
                setLoopStatus(state, 'Stopped.');
            });
            buttons.append(start, stop);
            const status = factory.createElement('output');
            status.textContent = state.message;
            status.style.color = '#cbd5e1';
            state.status = status;
            root.append(buttons, status);
            container.appendChild(root);
        },
        destroy() {
            loops.delete(key);
        },
    });
    return state;
}

function applyLoopResult(result) {
    const payload = loopPayload(result);
    if (!payload || typeof payload !== 'object') return;
    const sourceId = String(payload.source_node_id ?? '');
    const source = comfy.graph.node(sourceId);
    if (!source) return;
    const state = loops.get(keyFor(source));
    if (!state || !state.active) return;
    if (payload.done) {
        state.active = false;
        setLoopStatus(state, payload.message || `Done ${payload.count}/${payload.count}`);
        return;
    }
    setLoopStatus(state, payload.message || `Next tile ${Number(payload.index) + 1}/${payload.count}`);
    void queueLoop(state, false);
}


comfy.defs.extend(INTERACTIVE, (builder) => {
    builder.onCreated((node) => mountEditor(node));
    builder.onConfigured((node) => {
        const state = editors.get(keyFor(node));
        if (!state) return;
        state.tiles = parseLayout(node);
        state.selected = 0;
        commit(state);
    });
    builder.onExecuted((node, result) => {
        const state = editors.get(keyFor(node));
        if (state) applyBackendLayout(state, result);
    });
    builder.onRemoved((node) => editors.delete(keyFor(node)));
});

comfy.defs.extend(LOOP_SOURCE, (builder) => {
    builder.onCreated((node) => mountLoop(node));
    builder.onExecuted((_node, result) => applyLoopResult(result));
    builder.onRemoved((node) => loops.delete(keyFor(node)));
});

comfy.defs.extend(LOOP_COLLECT, (builder) => {
    builder.onExecuted((_node, result) => applyLoopResult(result));
});
