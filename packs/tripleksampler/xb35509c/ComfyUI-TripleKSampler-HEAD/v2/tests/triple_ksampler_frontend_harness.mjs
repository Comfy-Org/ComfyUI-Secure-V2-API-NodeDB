import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';


function check(condition, message) {
    if (!condition) throw new Error(message);
}


const hooks = {};
let selector = null;
let interrupted = null;
let queueRuns = 0;
const notifications = [];
const nodesById = new Map();
const nodesByType = new Map();

const builder = {
    onCreated(callback) { hooks.created = callback; },
    onConfigured(callback) { hooks.configured = callback; },
    onConnectionsChanged(callback) { hooks.connections = callback; },
    onExecuted(callback) { hooks.executed = callback; },
    onRemoved(callback) { hooks.removed = callback; },
};

const comfy = {
    defs: {
        extend(value, apply) {
            selector = value;
            apply(builder);
        },
    },
    graph: {
        node(id) { return nodesById.get(String(id)); },
        nodesOfType(type) { return [...(nodesByType.get(type) ?? [])]; },
    },
    queue: {
        run() {
            queueRuns += 1;
            return Promise.resolve();
        },
        onInterrupted(callback) {
            interrupted = callback;
            return () => { if (interrupted === callback) interrupted = null; };
        },
    },
    commands: {
        notify(payload) { notifications.push(payload); },
    },
};

const context = vm.createContext({ console });
const facade = new vm.SyntheticModule(
    ['comfy'],
    function initialize() { this.setExport('comfy', comfy); },
    { context, identifier: '/comfy/api/v2.js' },
);
const source = fs.readFileSync(process.env.TARGET_JS, 'utf8');
const guest = new vm.SourceTextModule(source, {
    context,
    identifier: path.resolve(process.env.TARGET_JS),
});
await guest.link(async (specifier) => {
    if (specifier === '/comfy/api/v2.js') return facade;
    throw new Error(`unexpected import: ${specifier}`);
});
await guest.evaluate();

check(typeof selector === 'function', 'definition selector was not registered');
check(selector({ type: 'TripleKSamplerWan22LightningAdvanced' }), 'standard advanced missing');
check(selector({ type: 'TripleWVSamplerAdvanced' }), 'Wan advanced missing');
check(!selector({ type: 'TripleKSamplerWan22LightningAdvancedAlt' }), 'Alt should stay static');
check(!selector({ type: 'TripleWVSampler' }), 'simple Wan should stay static');
for (const name of ['created', 'configured', 'connections', 'executed', 'removed']) {
    check(typeof hooks[name] === 'function', `missing ${name} hook`);
}
check(typeof interrupted === 'function', 'queue interruption hook missing');
for (const name of [
    'window', 'document', 'parent', 'app', 'fetch', 'XMLHttpRequest',
    'WebSocket', 'setTimeout', 'setInterval', 'requestAnimationFrame',
    'localStorage',
]) {
    check(
        vm.runInContext(`typeof ${name}`, context) === 'undefined',
        `${name} leaked into the guest realm`,
    );
}


function makeWidget(name, initial) {
    let value = initial;
    let hidden = false;
    const listeners = new Map();
    function callbacks(event) {
        if (!listeners.has(event)) listeners.set(event, new Set());
        return listeners.get(event);
    }
    return {
        name,
        getValue() { return value; },
        setValue(next) {
            const previous = value;
            if (Object.is(previous, next)) return;
            value = next;
            for (const callback of callbacks('change')) callback(next, previous);
        },
        setHidden(next) { hidden = Boolean(next); },
        isHidden() { return hidden; },
        on(event, callback) {
            callbacks(event).add(callback);
            return () => callbacks(event).delete(callback);
        },
        emit(event) {
            for (const callback of callbacks(event)) callback(value);
        },
        count(event) { return callbacks(event).size; },
    };
}


function makeNode(id, type) {
    const widgets = new Map([
        ['switch_strategy', makeWidget('switch_strategy', '50% of steps')],
        ['switch_step', makeWidget('switch_step', -1)],
        ['switch_boundary', makeWidget('switch_boundary', 0.875)],
        ['base_steps', makeWidget('base_steps', -1)],
        ['base_quality_threshold', makeWidget('base_quality_threshold', 20)],
        ['dry_run', makeWidget('dry_run', false)],
    ]);
    const source = { value: null };
    const node = {
        id: String(id),
        type,
        source,
        widgets: {
            get(name) { return widgets.get(name); },
            add(definition) {
                const widget = makeWidget(definition.name, definition.value);
                widget.definition = definition;
                widgets.set(definition.name, widget);
                return widget;
            },
        },
        inputs: {
            byName(name) {
                if (name !== 'switch_strategy') return null;
                return { source() { return source.value; } };
            },
        },
    };
    nodesById.set(node.id, node);
    if (!nodesByType.has(type)) nodesByType.set(type, []);
    nodesByType.get(type).push(node);
    return node;
}


const standard = makeNode('1', 'TripleKSamplerWan22LightningAdvanced');
hooks.created(standard);
const ownStrategy = standard.widgets.get('switch_strategy');
const step = standard.widgets.get('switch_step');
const boundary = standard.widgets.get('switch_boundary');
const baseSteps = standard.widgets.get('base_steps');
const quality = standard.widgets.get('base_quality_threshold');
const dryRun = standard.widgets.get('dry_run');
const button = standard.widgets.get('🧪 Run Dry Run');

check(step.isHidden(), '50% strategy should hide switch_step');
check(boundary.isHidden(), '50% strategy should hide switch_boundary');
ownStrategy.setValue('Manual switch step');
check(!step.isHidden() && boundary.isHidden(), 'manual step visibility is wrong');
ownStrategy.setValue('Manual boundary (refined)');
check(step.isHidden() && !boundary.isHidden(), 'manual boundary visibility is wrong');
ownStrategy.setValue('future strategy');
check(!step.isHidden() && !boundary.isHidden(), 'unknown strategy must expose both controls');
check(!quality.isHidden(), 'automatic base steps should show quality threshold');
baseSteps.setValue(5);
check(quality.isHidden(), 'manual base steps should hide quality threshold');
baseSteps.setValue(-1);
check(!quality.isHidden(), 'automatic base threshold did not return');
check(dryRun.isHidden(), 'dry_run input must remain hidden');
check(button.definition.options.serialize === false, 'dry-run button must be non-serialized');
button.emit('activate');
check(dryRun.getValue() === true, 'dry-run button did not arm hidden input');
check(queueRuns === 1, 'dry-run button did not queue exactly once');

const originStrategy = makeWidget('switch_strategy', 'Manual switch step');
nodesById.set('origin', { id: 'origin', widgets: { get: () => originStrategy } });
standard.source.value = { nodeId: 'origin', outputIndex: 0 };
hooks.connections(standard, {});
check(!step.isHidden() && boundary.isHidden(), 'connected strategy was not read');
check(originStrategy.count('change') === 1, 'connected strategy was not subscribed');
originStrategy.setValue('Manual boundary');
check(step.isHidden() && !boundary.isHidden(), 'connected strategy change was missed');
hooks.connections(standard, {});
check(originStrategy.count('change') === 1, 'connected strategy subscription leaked');
standard.source.value = { nodeId: 'missing', outputIndex: 0 };
hooks.connections(standard, {});
check(!step.isHidden() && !boundary.isHidden(), 'unreadable connection must show both controls');
standard.source.value = null;
ownStrategy.setValue('T2V boundary');
hooks.configured(standard, {});
check(step.isHidden() && boundary.isHidden(), 'configured local strategy is wrong');
check(dryRun.isHidden(), 'configured hook exposed dry_run');

hooks.executed(standard, {
    raw: {
        triple_ksampler_overlap: {
            severity: 'warn', summary: 'Overlap', detail: '2.5%', life: 8000,
        },
        triple_ksampler_dry_run: {
            severity: 'info', summary: 'Dry run', detail: 'Stages', life: 12000,
        },
    },
});
check(notifications.length === 2, 'executed payload did not emit both notifications');
check(notifications[0].summary === 'Overlap', 'overlap notification changed');
check(notifications[1].detail === 'Stages', 'dry-run notification changed');
check(dryRun.getValue() === false, 'executed hook did not reset dry_run');

const wan = makeNode('2', 'TripleWVSamplerAdvanced');
hooks.created(wan);
dryRun.setValue(true);
wan.widgets.get('dry_run').setValue(true);
interrupted();
check(dryRun.getValue() === false, 'interruption did not reset standard dry_run');
check(wan.widgets.get('dry_run').getValue() === false, 'interruption did not reset Wan dry_run');

const ownCount = ownStrategy.count('change');
check(ownCount === 1, 'unexpected own strategy subscription count');
hooks.removed(standard);
check(ownStrategy.count('change') === 0, 'own strategy subscription survived removal');
check(baseSteps.count('change') === 0, 'base_steps subscription survived removal');
check(button.count('activate') === 0, 'button subscription survived removal');

console.log('tripleksampler frontend harness: ok');
