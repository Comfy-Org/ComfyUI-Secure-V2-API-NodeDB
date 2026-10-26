import { comfy } from '/comfy/api/v2.js';

// These are rgthree's authored connection layouts. The old implementation
// replaced getConnectionPos; the same expanded-node positions are now declared
// through public slot patches. No host renderer or global routing is replaced.
//
// Revision 9 R2 (F01). Sources: the successor tranche's module and MOE's
// draft (one extend per type, so no `builder.def`; two fixed menu labels
// chosen by `when`, never a label function). Registered here only; no
// `onBeforeConnect`. Uses the published contract shipped with revision 8.
// Whole-node collapsed title-edge socket geometry remains partial pending
// an approved API or a separate critical-pack shim.
const withSuffix = (name) => `${name} (rgthree)`;
export const LAYOUT_TYPES = [
    'Any Switch', 'Context', 'Context Big', 'Context Switch', 'Context Switch Big', 'Context Merge', 'Context Merge Big',
    'Display Any', 'Display Int', 'Image Comparer', 'Power Lora Loader', 'Power Prompt', 'Power Prompt - Simple',
    'SDXL Power Prompt - Positive', 'SDXL Power Prompt - Simple / Negative', 'Seed', 'Mute / Bypass Relay',
    'Mute / Bypass Repeater', 'Fast Muter', 'Fast Bypasser', 'Fast Actions Button', 'Node Collector', 'Node Combiner', 'Random Unmuter',
].map(withSuffix);
const layoutTypes = new Set(LAYOUT_TYPES);
const collapsibleTypes = new Set([
    'Mute / Bypass Relay', 'Mute / Bypass Repeater', 'Fast Muter', 'Fast Bypasser', 'Fast Actions Button',
    'Node Collector', 'Node Combiner', 'Random Unmuter',
].map(withSuffix));
const displayTypes = new Set(['Display Any', 'Display Int'].map(withSuffix));
const OPPOSITE = { Left: 'Right', Right: 'Left', Top: 'Bottom', Bottom: 'Top' };
const DIRECTION = { Left: 'left', Right: 'right', Top: 'up', Bottom: 'down' };
const LEGACY_DIRECTION = { 0: 'none', 1: 'up', 2: 'down', 3: 'left', 4: 'right', 5: 'center' };
// The original default geometry uses 20px rows and a 10px socket inset.
// They are pack layout values here, not reads of private renderer constants.
const ROW_HEIGHT = 20, INSET = 10;
const STATE_KEY = 'rgthree_connections_v1';
const states = new Map();
const keyOf = (node) => JSON.stringify([node.graphId ?? '', node.id]);
const slotKey = (side, slot) => `${side}:${slot.id}`;
const collectionFor = (node, side) => side === 'input' ? node.inputs : node.outputs;

function stateFor(node) {
    const key = keyOf(node);
    let state = states.get(key);
    if (!state) { state = { slots: new Map(), pending: false }; states.set(key, state); }
    return state;
}
function recordFor(state, side, slot) {
    const key = slotKey(side, slot);
    let record = state.slots.get(key);
    if (!record) {
        record = { label: slot.label, labelHidden: false, slotHidden: false, disabled: false };
        state.slots.set(key, record);
    }
    return record;
}
function layoutFor(node) {
    let layout = node.getProperty('connections_layout') ?? ['Left', 'Right'];
    if (typeof layout === 'string') layout = layout.split(' -> ');
    if (!Array.isArray(layout) || !OPPOSITE[layout[0]]) return ['Left', 'Right'];
    const second = layout[1] ?? (node.outputs.length ? undefined : OPPOSITE[layout[0]]);
    return OPPOSITE[second] ? [layout[0], second] : ['Left', 'Right'];
}

// onConfigured publishes a serialized copy of this node. Legacy rgthree saved
// its hidden-label backup directly on a slot; read those authored fields here,
// never by inspecting a private live slot. New writes use the pack-owned key.
function configureState(node, data) {
    const state = stateFor(node);
    const owned = data?.[STATE_KEY]?.schema === 1 ? data[STATE_KEY] : undefined;
    for (const side of ['input', 'output']) {
        const serialized = owned?.[`${side}s`] ?? data?.[`${side}s`];
        if (!Array.isArray(serialized)) continue;
        const slots = collectionFor(node, side).all();
        for (const [index, slot] of slots.entries()) {
            const source = serialized[index];
            if (!source || (source.name !== undefined && source.name !== slot.name)) continue;
            const record = recordFor(state, side, slot);
            if (owned) {
                record.label = source.label_present && typeof source.label === 'string' ? source.label : undefined;
                record.labelHidden = !!source.label_hidden;
                record.slotHidden = !!source.slot_hidden;
                record.disabled = !!source.disabled;
                record.color = typeof source.color === 'string' ? source.color : undefined;
                record.colorWhenUnconnected = typeof source.color_when_unconnected === 'string' ? source.color_when_unconnected : undefined;
            } else {
                record.label = source.has_old_label ? source.old_label : slot.label;
                record.labelHidden = !!source.has_old_label;
                record.slotHidden = !!source.hidden;
                record.disabled = !!source.disabled;
                record.color = source.color_on === '#666665' ? source._color_on_org : source.color_on;
                record.colorWhenUnconnected = source.color_off === '#666665' ? source._color_off_org : source.color_off;
            }
        }
    }
}

export function applyConnectionLayout(node) {
    if (node.isDeleted || !layoutTypes.has(node.type)) return;
    const state = stateFor(node), activeSlots = new Set();
    const layout = layoutFor(node), collapse = !!node.getProperty('collapse_connections');
    const size = node.getSize(), overrides = node.getProperty('connections_dir');
    for (const [sideIndex, side] of ['input', 'output'].entries()) {
        const edge = layout[sideIndex], slots = collectionFor(node, side).all();
        let hiddenBefore = 0;
        for (const [index, slot] of slots.entries()) {
            const record = recordFor(state, side, slot), key = slotKey(side, slot);
            activeSlots.add(key);
            const displayIndex = collapse ? 0 : index - hiddenBefore;
            if (record.slotHidden) hiddenBefore++;
            const position = edge === 'Left' ? { x: INSET, y: (displayIndex + 0.7) * ROW_HEIGHT }
                : edge === 'Right' ? { x: size.width + 1 - INSET, y: (displayIndex + 0.7) * ROW_HEIGHT }
                : edge === 'Top' ? { x: size.width / 2, y: INSET }
                : { x: size.width / 2, y: size.height - INSET };
            const direction = (size.width === 10 || size.height === 10) && Array.isArray(overrides)
                ? LEGACY_DIRECTION[overrides[sideIndex]] ?? DIRECTION[edge] : DIRECTION[edge];
            const snapshot = slot.snapshot(), patch = {};
            if (snapshot.position?.x !== position.x || snapshot.position?.y !== position.y) patch.position = position;
            if (snapshot.direction !== direction) patch.direction = direction;
            // A dynamic node may have supplied a new caption since we hid it.
            // Keep that caption, not the stale pre-layout copy.
            if (!record.labelHidden || slot.label !== ' ') record.label = slot.label;
            const hide = edge === 'Top' || edge === 'Bottom' || collapse
                || (side === 'input' ? edge === 'Right' : edge === 'Left');
            const label = hide ? ' ' : record.label;
            if (slot.label !== label) patch.label = label;
            record.labelHidden = hide;
            if (record.disabled) {
                if (!record.grayApplied) {
                    patch.color = '#666665'; patch.colorWhenUnconnected = '#666665'; record.grayApplied = true;
                }
            } else if (record.grayApplied) {
                patch.color = record.color ?? null; patch.colorWhenUnconnected = record.colorWhenUnconnected ?? null;
                record.grayApplied = false;
            }
            if (Object.keys(patch).length) slot.modify(patch);
        }
    }
    for (const key of state.slots.keys()) if (!activeSlots.has(key)) state.slots.delete(key);
}

function schedule(node) {
    const state = stateFor(node);
    if (state.pending) return;
    state.pending = true;
    queueMicrotask(() => {
        if (states.get(keyOf(node)) !== state) return;
        state.pending = false;
        if (!node.isDeleted) applyConnectionLayout(node);
    });
}
function serializedState(node) {
    const state = stateFor(node), result = { schema: 1 };
    for (const side of ['input', 'output']) result[`${side}s`] = collectionFor(node, side).all().map((slot) => {
        const record = recordFor(state, side, slot);
        if (!record.labelHidden || slot.label !== ' ') record.label = slot.label;
        return { name: slot.name, label_present: record.label !== undefined, ...(record.label === undefined ? {} : { label: record.label }),
            label_hidden: record.labelHidden, slot_hidden: record.slotHidden, disabled: record.disabled,
            ...(record.color === undefined ? {} : { color: record.color }),
            ...(record.colorWhenUnconnected === undefined ? {} : { color_when_unconnected: record.colorWhenUnconnected }) };
    });
    return { [STATE_KEY]: result };
}

for (const layoutType of LAYOUT_TYPES) comfy.defs.extend(layoutType, (builder) => {
    const choices = displayTypes.has(layoutType) ? [['Left'], ['Right']] : [['Left', 'Right'], ['Right', 'Left']];
    builder.addMenuItem({ label: 'Connections Layout', items: choices.map((choice) => ({
        label: choice.join(' -> '), run(node) {
            const layout = choice.length === 1 ? [choice[0], OPPOSITE[choice[0]]] : [...choice];
            node.setProperty('connections_layout', layout); schedule(node);
        },
    })) });
    if (collapsibleTypes.has(layoutType)) for (const [label, collapsed] of [
        ['Show Connections', false], ['Collapse Connections', true],
    ]) builder.addMenuItem({
        label,
        when(node) { return !!node.getProperty('collapse_connections') !== collapsed; },
        run(node) { node.setProperty('collapse_connections', collapsed); schedule(node); },
    });
    builder.onCreated((node) => schedule(node));
    builder.onConfigured((node, data) => { configureState(node, data); schedule(node); });
    builder.onPropertyChanged((node, event) => {
        if (['connections_layout', 'connections_dir', 'collapse_connections'].includes(event.name)) schedule(node);
    });
    builder.onConnectionsChanged((node) => schedule(node));
    builder.onResized((node) => schedule(node));
    builder.onSerialize(serializedState);
    builder.onRemoved((node) => states.delete(keyOf(node)));
});

// Scope limits are explicit. Widget-backed inputs keep these positions only
// where the host honours an authored position for them (S03, in the live
// frontend). The original computeSize override that removed collapsed slot
// rows from the minimum body height needs a host layout primitive; socket
// grouping does not rewrite that private routine. None of these limits permits
// omitting the saved layouts.
