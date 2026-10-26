import { comfy } from '/comfy/api/v2.js';
import { SERVICE as CONFIG_SERVICE } from './services/config_service.js';
// Imported for their registrations, which every node type must receive before this
// module's `define` runs (extendEveryNodeType in base_node.js; Reroute is listed in
// DEFINED_NODE_TYPES).
import './menu_queue_node.js';
import './feature_import_individual_nodes.js';

// Reroute (rgthree), revision 9. Source: the unpublished consumer `3bed5217` (lineage
// 7114981b → 6f8ba765 → cd29f060 → 3bed5217), rebased onto revision 8 with four
// changes: no `onBeforeConnect` registration (F17), the exact 0.6 zoom boundary, the
// geometry relay (layer L2) feature-detected, and the sandbox guest's answers handled
// where they differ from the in-process API (below).
//
// The node's algorithm stays here. Resolution, topology changes, slot geometry and
// Primitive declarations use the public facade; no renderer class or live link record
// is patched. A reroute resolves as `{forwardTo: {nodeId: self.id, input: 0}}`.
//
// Still REFUSED, as in revisions 1-8 (the techniques, not the node):
//   - trapping the canvas's gesture state (`Object.defineProperty(canvas,
//     "connecting_links", …)`) to splice a reroute into a link mid-drag;
//   - replacing the node's own plumbing (`findInputSlot`, `disconnectInput`, `setSize`,
//     `clone`, `configure`, `onMouseMove`, …) on the class;
//   - writing the link table (`app.graph.links[id]`, `origin_id` / `target_slot`);
//   - impersonating another node's widget (`inputs[0].widget = {name: "value"}` plus
//     core's private widget config). The public `widget` / `widgetConfig` slot patch
//     declares the same thing;
//   - assigning `link.color`, a per-link write into the renderer's own record.
// Whole-node drawing is the bounded `node.canvas` surface with `presentation`
// (`title: 'hidden'`, `sizing: 'fixed'`), as for Label.
//
// MISSING (pending items):
//   - F05: inserting or moving a reroute during an unfinished link drag (the
//     fast-reroute shortcut). It needs a host-owned link-gesture contribution.
//   - F06 (part): per-link colour. The output slot takes the type's colour; the links
//     keep the host's.
//   - F17: the loop guard. The canvas reads that answer synchronously, so
//     `onBeforeConnect` is not available to a sandboxed pack. It is not registered (no
//     refusal and no notice). The rule is kept, unregistered, as `rerouteConnectionRule`
//     for the host's declarative connection policy. A link that closes a ring is
//     accepted; `stabilize` stops at nodes it has visited.
//
// LIVE HOST r3 (guest `c6b97a15`) and r4a r2 (guest `16924bbe`) lack the geometry relay
// (L2): the node handle has no `getBounds` / `getScreenRect`. Then the label is drawn at
// every zoom (the original hides it below 0.6), nothing subscribes to `onViewportChanged`,
// and no error is raised. With L2 the original's rule applies.
const TYPE = 'Reroute (rgthree)';
const SIDES = ['Top', 'Right', 'Bottom', 'Left'];
const OPPOSITE = { Left: 'Right', Right: 'Left', Top: 'Bottom', Bottom: 'Top' };
const DIRECTIONS = { Left: 'left', Right: 'right', Top: 'up', Bottom: 'down' };
const LEGACY_DIRECTIONS = { 0: 'none', 1: 'up', 2: 'down', 3: 'left', 4: 'right', 5: 'center' };
const states = new Map();
let stopViewport;
const keyOf = (node) => `${node.graphId ?? ''}:${node.id}`;
const isReroute = (node) => !!node?.type?.includes('Reroute');
const scopeOf = (node) => node.graphId && node.graphId !== comfy.graph.id
    ? comfy.graph.subgraphs().find((scope) => scope.id === node.graphId)
    : comfy.graph;
// `defs.typeColor` and `defs.isTypeCompatible` answer synchronously in the published API
// and on guest r4a (R6-9). Host r3's guest forwards both over its generic call channel,
// so there they answer with a Promise. A Promise must never reach a slot patch: it
// cannot be structured-cloned.
const isPending = (answer) => !!answer && typeof answer.then === 'function';

function defaultSize() {
    const dimension = (key, fallback) => {
        const value = Number(CONFIG_SERVICE.getConfigValue(key, fallback));
        return Math.max(Math.round((Number.isFinite(value) && value ? value : fallback) / 10) * 10, 10);
    };
    let width = dimension('nodes.reroute.default_width', 40);
    let height = dimension('nodes.reroute.default_height', 30);
    while (width * height < 400) { width += 10; height += 10; }
    return [width, height];
}

function layoutOf(node) {
    const configured = node.getProperty('connections_layout') ?? CONFIG_SERVICE.getConfigValue('nodes.reroute.default_layout', ['Left', 'Right']);
    const value = typeof configured === 'string' ? configured.split(' -> ') : configured;
    const input = Array.isArray(value) && SIDES.includes(value[0]) ? value[0] : 'Left';
    const output = Array.isArray(value) && SIDES.includes(value[1]) && input !== value[1] ? value[1] : OPPOSITE[input];
    return [input, output];
}

// Sends only what differs from the slot's snapshot, so a repeated pass writes nothing.
function applyLayout(node) {
    const { width, height } = node.getSize();
    const layout = layoutOf(node);
    const directions = node.getProperty('connections_dir');
    const positions = {
        Left: { x: 5, y: height / 2 }, Right: { x: width + 1 - 5, y: height / 2 },
        Top: { x: width / 2, y: 5 }, Bottom: { x: width / 2, y: height - 5 },
    };
    for (const [index, slot] of [node.inputs.at(0), node.outputs.at(0)].entries()) {
        if (!slot) continue;
        const override = (width === 10 || height === 10) && Array.isArray(directions)
            ? LEGACY_DIRECTIONS[directions[index]] : undefined;
        const position = positions[layout[index]], direction = override ?? DIRECTIONS[layout[index]];
        const snapshot = slot.snapshot(), patch = {};
        if (snapshot.position?.x !== position.x || snapshot.position?.y !== position.y) patch.position = position;
        if (snapshot.direction !== direction) patch.direction = direction;
        if (snapshot.label !== ' ') patch.label = ' ';
        if (Object.keys(patch).length) slot.modify(patch);
    }
}

function applySize(node) {
    const value = node.getProperty('size');
    const fallback = defaultSize();
    const size = [0, 1].map((index) => Array.isArray(value) && Number.isFinite(Number(value[index]))
        ? Math.max(10, Number(value[index])) : fallback[index]);
    const current = node.getSize();
    if (current.width !== size[0] || current.height !== size[1]) node.setSize({ width: size[0], height: size[1] });
    applyLayout(node);
}

// Preserve upstream's side/direction changes when a resize creates a 10px strip.
function stabilizeResizeLayout(node, oldSize, newSize) {
    if (newSize[0] !== 10 && newSize[1] !== 10) return;
    const layout = [...(node.getProperty('connections_layout') || ['Left', 'Right'])];
    const directions = [...(node.getProperty('connections_dir') || [-1, -1])];
    if (oldSize[0] > 10 && newSize[0] === 10) {
        directions[0] = 2; directions[1] = 1;
        if (layout[0] === 'Bottom') layout[1] = 'Top';
        else if (layout[1] === 'Top') layout[0] = 'Bottom';
        else { layout[0] = 'Top'; layout[1] = 'Bottom'; directions[0] = 1; directions[1] = 2; }
    } else if (oldSize[1] > 10 && newSize[1] === 10) {
        directions[0] = 4; directions[1] = 3;
        if (layout[0] === 'Right') layout[1] = 'Left';
        else if (layout[1] === 'Left') layout[0] = 'Right';
        else { layout[0] = 'Left'; layout[1] = 'Right'; directions[0] = 3; directions[1] = 4; }
    }
    node.setProperty('connections_layout', layout);
    node.setProperty('connections_dir', directions);
}

function saveSize(node, width, height) {
    node.setProperty('size', [width, height]);
    applySize(node);
}

// Layer L2: present when the node handle carries both geometry reads.
const hasGeometry = (node) => typeof node?.getBounds === 'function' && typeof node?.getScreenRect === 'function';

/**
 * The original hid the label while `ds.scale` was truthy and below 0.6. The renderer's
 * scale is `getScreenRect().width / getBounds().width`, and `getScreenRect` computes that
 * width as the same product, so the comparison is made on the product: exact at a scale
 * of exactly 0.6, where the quotient falls below 0.6 for some widths (109 is the first
 * integer). Without L2, or with no finite geometry to measure, the label stays shown.
 */
export function labelHiddenByZoom(node) {
    if (!hasGeometry(node)) return false;
    let bounds, screenRect;
    try {
        bounds = node.getBounds();
        screenRect = node.getScreenRect();
    } catch {
        // Gone, outside its graph, or no finite host geometry: no scale to apply.
        return false;
    }
    if (!screenRect || !(bounds?.width > 0) || !(screenRect.width > 0)) return false;
    return screenRect.width < bounds.width * 0.6;
}

function redraw(node) {
    const state = states.get(keyOf(node));
    if (!state) return;
    const size = node.getSize();
    if (!node.getProperty('showLabel') || !(size.width > 10)) {
        state.canvas?.remove(); state.canvas = undefined; state.canvasError = undefined;
        return;
    }
    const bounds = { x: 0, y: 0, width: size.width, height: size.height };
    try {
        if (state.canvas) state.canvas.setBounds(bounds);
        else {
            state.canvas = node.canvas({ bounds, layer: 'foreground', draw: (context) => drawLabel(node, context) });
            state.canvas.redraw();
        }
        state.canvasError = undefined;
    } catch (error) {
        // A display-surface quota must not disable the node's data forwarding.
        // Keep the saved size and label setting, and report the real limitation.
        state.canvas?.remove(); state.canvas = undefined;
        const detail = String(error?.message ?? error);
        if (state.canvasError !== detail) comfy.commands.notify({ severity: 'warn', summary: 'Could not draw Reroute label', detail });
        state.canvasError = detail;
    }
}

export function drawLabel(node, context) {
    if (!node.getProperty('showLabel')) return;
    const { width, height } = node.getSize();
    if (!(width > 10)) return;
    if (labelHiddenByZoom(node)) return;
    const title = node.getTitle();
    context.save();
    context.fillStyle = '#888';
    context.font = `${Math.min(14, (height * 0.65) | 0)}px Arial`;
    context.textAlign = 'center';
    context.textBaseline = 'middle';
    context.fillText(String(title && title !== TYPE ? title : node.outputs.at(0)?.type || ''), width / 2, height / 2, width - 30);
    context.restore();
}

function schedule(node, delay = 64) {
    const state = states.get(keyOf(node));
    if (!state || state.timer != null) return;
    state.timer = setTimeout(() => {
        state.timer = undefined;
        if (!node.isDeleted) stabilize(node);
    }, delay);
}

// Preserve upstream order: walk inputs to the first non-reroute, then the
// output branches in stack order. A visited set additionally terminates corrupt
// cycles loaded from a file without trapping the worker in an infinite walk.
function stabilize(node) {
    const scope = scopeOf(node);
    if (!scope) return;
    const update = new Map();
    const visited = new Set();
    let current = node;
    let input;
    while (current) {
        if (visited.has(current.id)) break;
        visited.add(current.id);
        update.set(current.id, current);
        const link = current.inputs.at(0)?.link();
        if (!link) break;
        const parent = scope.node(link.sourceNodeId);
        if (!parent) { current.inputs.at(0)?.disconnect(); break; }
        if (isReroute(parent)) {
            if (visited.has(parent.id)) { current.inputs.at(0)?.disconnect(); break; }
            current = parent;
        } else {
            input = parent.outputs.at(link.sourceIndex);
            break;
        }
    }
    const inputType = input?.type;
    let outputType;
    let widgetConfig;
    const queue = [node];
    const traversed = new Set();
    while (queue.length) {
        current = queue.pop();
        if (traversed.has(current.id)) continue;
        traversed.add(current.id);
        for (const link of current.outputs.at(0)?.links() ?? []) {
            const target = scope.node(link.targetNodeId);
            if (!target) continue;
            if (isReroute(target)) {
                if (!traversed.has(target.id)) { queue.push(target); update.set(target.id, target); }
                continue;
            }
            const output = target.inputs.at(link.targetIndex);
            if (!output) continue;
            if (inputType && inputType !== '*' && output.type !== '*') {
                const compatible = comfy.defs.isTypeCompatible(inputType, output.type);
                if (isPending(compatible)) {
                    // Host r3: decide when the answer arrives; the disconnect restabilizes.
                    compatible.then((ok) => { if (ok === false) output.disconnect(); }, () => {});
                } else if (!compatible) {
                    output.disconnect();
                    continue;
                }
            }
            outputType = output.type;
            widgetConfig = undefined;
            if (output.isWidgetInput) {
                const config = output.widgetConfig();
                if (config) {
                    // `mergeWidgetConfig` is published; guests r3 and r4a r2 do not
                    // provide it yet, so the target's own declaration is used there.
                    widgetConfig = (typeof output.mergeWidgetConfig === 'function' ? output.mergeWidgetConfig(config) : undefined) ?? config;
                    outputType = Array.isArray(config.type) ? config.type.join(',') : config.type;
                }
            }
        }
    }
    const displayType = inputType || outputType || '*';
    const color = comfy.defs.typeColor(displayType);
    const colorPatch = (value) => ({ color: typeof value === 'string' && value ? value : null });
    for (const reroute of update.values()) {
        const output = reroute.outputs.at(0);
        output?.modify({ type: inputType || '*', name: input?.name || '', ...(isPending(color) ? {} : colorPatch(color)) });
        const ownInput = reroute.inputs.at(0);
        if (widgetConfig) ownInput?.modify({ widget: 'value', widgetConfig });
        else ownInput?.modify({ widget: null });
        // Only this pack's owned nodes receive its presentation. Other reroute
        // types remain ordinary peers, as they were during original propagation.
        if (reroute.type === TYPE) { applyLayout(reroute); redraw(reroute); }
    }
    if (isPending(color)) {
        // Host r3: the colour follows when its answer arrives, for the nodes still there.
        color.then((value) => {
            for (const reroute of update.values()) scope.node(reroute.id)?.outputs.at(0)?.modify(colorPatch(value));
        }, () => {});
    }
}

/**
 * The loop guard, as the original's onConnectInput/onConnectOutput applied it: refuse a
 * link whose far end is reached from this node through reroutes. MISSING (F17
 * connection policy): nothing registers it in the sandbox; see the top of this file.
 */
export function rerouteConnectionRule(node, event) {
    if (!event.peerNodeId) return undefined;
    const scope = scopeOf(node);
    let current = scope?.node(event.peerNodeId);
    const seen = new Set();
    const queue = current ? [current] : [];
    while (queue.length) {
        current = queue.pop();
        if (current.id === node.id) return false;
        if (!isReroute(current) || seen.has(current.id)) continue;
        seen.add(current.id);
        const links = event.side === 'input'
            ? [current.inputs.at(0)?.link()].filter(Boolean)
            : current.outputs.at(0)?.links() ?? [];
        for (const link of links) {
            const peer = scope.node(event.side === 'input' ? link.sourceNodeId : link.targetNodeId);
            if (peer) queue.push(peer);
        }
    }
    return undefined;
}

function rotate(node, degrees) {
    const step = degrees === -90 ? -1 : degrees === 180 ? 2 : 1;
    node.setProperty('connections_layout', layoutOf(node).map((side) => SIDES[(SIDES.indexOf(side) + step + 4) % 4]));
    const { width, height } = node.getSize();
    // This matches upstream, including its size swap for a 180-degree action.
    saveSize(node, height, width);
}

function flip(node, horizontal) {
    const changed = horizontal ? ['Left', 'Right'] : ['Top', 'Bottom'];
    node.setProperty('connections_layout', layoutOf(node).map((side) => changed.includes(side) ? OPPOSITE[side] : side));
    applyLayout(node);
}

// `graph.add` answers a handle at once. In process it is real immediately. In the sandbox
// guest it is confirmed when the host answers, and until then its id and slots cannot be
// read (guest r3 throws on `id`; guest r4a refuses every collection read). So the clone is
// wired and selected once it is real, and the attempt ends quietly after about 2 s.
function whenConfirmed(handle, run, attempts = 40) {
    let id;
    try { id = handle.id; } catch { id = undefined; }
    if (id != null && id !== '') { run(); return; }
    if (attempts > 0) setTimeout(() => whenConfirmed(handle, run, attempts - 1), 50);
}

function cloneNextTo(node, before) {
    if (node.graphId && node.graphId !== comfy.graph.id) return;
    const position = node.getPosition();
    const title = node.getTitle();
    const properties = structuredClone(node.getProperties());
    // Read now: the original wired the clone into the links as they were when chosen.
    const inputLink = before ? node.inputs.at(0)?.link() : undefined;
    const outputLinks = before ? [] : node.outputs.at(0)?.links() ?? [];
    // `NodeInit` carries a title and a position; the properties are set on the handle,
    // which queues them until the host confirms the node.
    const clone = comfy.graph.add(TYPE, {
        position: { x: position.x + (before ? -20 : 20), y: position.y + (before ? -20 : 20) },
        ...(title && title !== TYPE ? { title } : {}),
    });
    for (const [key, value] of Object.entries(properties)) clone.setProperty(key, value);
    whenConfirmed(clone, () => {
        // `SlotRef` by position is `{ index }` (a bare number is not a SlotRef).
        comfy.graph.batch(() => {
            if (before) {
                if (inputLink) comfy.graph.node(inputLink.sourceNodeId)?.outputs.at(inputLink.sourceIndex)?.connectTo(clone.id, { index: 0 });
                clone.outputs.at(0)?.connectTo(node.id, { index: 0 });
            } else {
                node.outputs.at(0)?.connectTo(clone.id, { index: 0 });
                for (const link of outputLinks) clone.outputs.at(0)?.connectTo(link.targetNodeId, { index: link.targetIndex });
            }
        });
        comfy.graph.select([clone]);
    });
}

comfy.defs.extend(TYPE, (builder) => {
    builder.onResized((node, size) => {
        const oldSize = node.getProperty('size') || defaultSize();
        const newSize = [size.width, size.height];
        node.setProperty('size', newSize);
        stabilizeResizeLayout(node, oldSize, newSize);
        applyLayout(node);
        redraw(node);
    });
    // MISSING (F17 connection policy): no `builder.onBeforeConnect` here; see
    // `rerouteConnectionRule`.
    const toggleLabel = (node) => {
        node.setProperty('showLabel', !node.getProperty('showLabel')); redraw(node);
    };
    builder.addMenuItem({ label: 'Hide Label/Title', when: (node) => !!node.getProperty('showLabel'), run: toggleLabel });
    builder.addMenuItem({ label: 'Show Label/Title', when: (node) => !node.getProperty('showLabel'), run: toggleLabel });
    const toggleResizing = (node) => {
        const resizable = !node.getProperty('resizable');
        node.setProperty('resizable', resizable);
        node.setResizable(resizable);
        const size = node.getSize();
        saveSize(node, Math.max(40, size.width), Math.max(30, size.height));
    };
    builder.addMenuItem({ label: 'No Resizing', when: (node) => !!node.getProperty('resizable'), run: toggleResizing });
    builder.addMenuItem({ label: 'Allow Resizing', when: (node) => !node.getProperty('resizable'), run: toggleResizing });
    for (const [name, index] of [['Static Width', 0], ['Static Height', 1]]) {
        builder.addMenuItem({ label: name, items: Array.from({ length: 8 }, (_, offset) => ({
            label: String(80 - offset * 10), run(node) {
                const size = node.getSize();
                node.setProperty('resizable', false);
                node.setResizable(false);
                saveSize(node, index === 0 ? 80 - offset * 10 : size.width, index === 1 ? 80 - offset * 10 : size.height);
            },
        })) });
    }
    builder.addMenuItem({ label: 'Connections Layout', items: SIDES.flatMap((input) => SIDES.filter((output) => input !== output).map((output) => ({
        label: `${input} -> ${output}`, run(node) { node.setProperty('connections_layout', [input, output]); applyLayout(node); },
    }))) });
    builder.addMenuItem({ label: 'Rotate', items: [
        { label: 'Rotate 90° Clockwise', run: (node) => rotate(node, 90) },
        { label: 'Rotate 90° Counter-Clockwise', run: (node) => rotate(node, -90) },
        { label: 'Rotate 180°', run: (node) => rotate(node, 180) },
        { label: 'Flip Horizontally', run: (node) => flip(node, true) },
        { label: 'Flip Vertically', run: (node) => flip(node, false) },
    ] });
    builder.addMenuItem({ label: 'Clone New Reroute...', items: [
        { label: 'Before', run: (node) => cloneNextTo(node, true) },
        { label: 'After', run: (node) => cloneNextTo(node, false) },
    ] });
});

comfy.defs.define({
    type: TYPE, title: TYPE, category: 'rgthree', execution: 'frontend',
    presentation: { title: 'hidden', sizing: 'fixed', collapsible: false },
    inputs: [{ name: '', type: '*' }], outputs: [{ name: '', type: '*' }],
    resolve: ({ self }) => ({ 0: { forwardTo: { nodeId: self.id, input: 0 } } }),
    onCreated(node, event) {
        const key = keyOf(node);
        const previous = states.get(key);
        if (previous?.timer != null) clearTimeout(previous.timer);
        previous?.canvas?.remove();
        const state = {};
        states.set(key, state);
        // Only where the geometry relay (L2) exists: without it the label ignores zoom,
        // so a viewport subscription would only cost messages.
        if (!stopViewport && hasGeometry(node)) {
            stopViewport = comfy.onViewportChanged(() => {
                // Labels keep their bounded surface even when the last draw
                // was suppressed at low zoom, so crossing back redraws it.
                for (const current of states.values()) current.canvas?.redraw();
            });
        }
        node.setSerializeWidgets(false);
        if (node.getProperty('resizable') == null) node.setProperty('resizable', !!CONFIG_SERVICE.getConfigValue('nodes.reroute.default_resizable', false));
        if (!node.getProperty('size')) node.setProperty('size', defaultSize());
        if (!node.getProperty('connections_layout')) node.setProperty('connections_layout', layoutOf(node));
        if (event?.restored && !event.loading) {
            node.inputs.at(0)?.modify({ type: '*' }); node.outputs.at(0)?.modify({ type: '*' });
        }
        applySize(node);
        node.setResizable(!!node.getProperty('resizable'));
        redraw(node);
        schedule(node);
    },
    onConfigured(node) { applySize(node); node.setResizable(!!node.getProperty('resizable')); schedule(node); },
    onConnectionsChanged(node, event) {
        if (event.connected && event.side === 'output') {
            const links = node.outputs.at(0)?.links() ?? [];
            const scope = scopeOf(node);
            const types = new Set(links.map((link) => scope?.node(link.targetNodeId)?.inputs.at(link.targetIndex)?.type).filter((type) => type && type !== '*'));
            if (types.size > 1) {
                for (const link of links.slice(0, -1)) scope?.node(link.targetNodeId)?.inputs.at(link.targetIndex)?.disconnect();
            }
        }
        schedule(node);
    },
    onPropertyChanged(node, event) {
        if (['size', 'connections_layout', 'connections_dir', 'resizable', 'showLabel'].includes(event.name)) {
            // The event is before commit. Re-read on the next microtask.
            queueMicrotask(() => {
                if (!node.isDeleted && states.has(keyOf(node))) {
                    applySize(node); node.setResizable(!!node.getProperty('resizable')); redraw(node);
                }
            });
        }
    },
    onRemoved(node) {
        const key = keyOf(node), state = states.get(key);
        if (state?.timer != null) clearTimeout(state.timer);
        state?.canvas?.remove(); states.delete(key);
        if (!states.size) { stopViewport?.(); stopViewport = undefined; }
    },
});
