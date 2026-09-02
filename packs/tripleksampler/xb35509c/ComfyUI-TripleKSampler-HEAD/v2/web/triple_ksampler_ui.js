import { comfy } from '/comfy/api/v2.js';


const TARGETS = new Set([
    'TripleKSamplerWan22LightningAdvanced',
    'TripleWVSamplerAdvanced',
]);
const states = new WeakMap();


function targetDefinition(definition) {
    return TARGETS.has(definition.type);
}


function dispose(disposer) {
    if (typeof disposer === 'function') disposer();
}


function strategyValue(node) {
    const source = node.inputs.byName('switch_strategy')?.source();
    if (source) {
        const origin = comfy.graph.node(source.nodeId);
        const value = origin?.widgets.get('switch_strategy')?.getValue();
        return typeof value === 'string' && value.length > 0 ? value : null;
    }
    const value = node.widgets.get('switch_strategy')?.getValue();
    return typeof value === 'string' && value.length > 0 ? value : null;
}


function updateStrategyVisibility(node) {
    const strategy = strategyValue(node);
    let showStep = false;
    let showBoundary = false;
    if (strategy === null) {
        // A connected source that is not readable must not hide controls that
        // may be needed by the actual runtime strategy.
        showStep = true;
        showBoundary = true;
    } else {
        const base = strategy.replace(' (refined)', '');
        showStep = base === 'Manual switch step';
        showBoundary = base === 'Manual boundary';
        if (![
            '50% of steps', 'Manual switch step', 'T2V boundary',
            'I2V boundary', 'Manual boundary',
        ].includes(base)) {
            showStep = true;
            showBoundary = true;
        }
    }
    node.widgets.get('switch_step')?.setHidden(!showStep);
    node.widgets.get('switch_boundary')?.setHidden(!showBoundary);
}


function updateBaseVisibility(node) {
    const automatic = Number(node.widgets.get('base_steps')?.getValue()) === -1;
    node.widgets.get('base_quality_threshold')?.setHidden(!automatic);
}


function subscribeToStrategySource(node) {
    const state = states.get(node);
    if (!state) return;
    dispose(state.sourceSubscription);
    state.sourceSubscription = null;
    const source = node.inputs.byName('switch_strategy')?.source();
    const sourceWidget = source
        ? comfy.graph.node(source.nodeId)?.widgets.get('switch_strategy')
        : null;
    if (sourceWidget) {
        state.sourceSubscription = sourceWidget.on(
            'change',
            () => updateStrategyVisibility(node),
        );
    }
    updateStrategyVisibility(node);
}


function boundedNotification(payload, fallbackSummary, fallbackSeverity) {
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return;
    const severity = ['info', 'success', 'warn', 'error'].includes(payload.severity)
        ? payload.severity
        : fallbackSeverity;
    const summary = String(payload.summary ?? fallbackSummary).slice(0, 160);
    const detail = String(payload.detail ?? '').slice(0, 16000);
    const requestedLife = Number(payload.life);
    const life = Number.isFinite(requestedLife)
        ? Math.max(1000, Math.min(30000, Math.trunc(requestedLife)))
        : 5000;
    comfy.commands.notify({ severity, summary, detail, life });
}


function resetDryRun(node) {
    const widget = node.widgets.get('dry_run');
    if (widget?.getValue() === true) widget.setValue(false);
}


function resetAllDryRuns() {
    for (const type of TARGETS) {
        for (const node of comfy.graph.nodesOfType(type)) resetDryRun(node);
    }
}


comfy.defs.extend(targetDefinition, (builder) => {
    builder.onCreated((node) => {
        const state = { subscriptions: [], sourceSubscription: null };
        states.set(node, state);

        const strategy = node.widgets.get('switch_strategy');
        if (strategy) {
            state.subscriptions.push(
                strategy.on('change', () => updateStrategyVisibility(node)),
            );
        }
        const baseSteps = node.widgets.get('base_steps');
        if (baseSteps) {
            state.subscriptions.push(
                baseSteps.on('change', () => updateBaseVisibility(node)),
            );
        }

        const dryRun = node.widgets.get('dry_run');
        dryRun?.setHidden(true);
        const button = node.widgets.add({
            type: 'button',
            name: '🧪 Run Dry Run',
            value: null,
            options: { serialize: false },
        });
        state.subscriptions.push(button.on('activate', () => {
            dryRun?.setValue(true);
            const queued = comfy.queue.run();
            if (queued && typeof queued.catch === 'function') {
                void queued.catch(() => resetDryRun(node));
            }
        }));

        subscribeToStrategySource(node);
        updateBaseVisibility(node);
    });

    builder.onConfigured((node) => {
        subscribeToStrategySource(node);
        updateBaseVisibility(node);
        node.widgets.get('dry_run')?.setHidden(true);
    });

    builder.onConnectionsChanged((node) => subscribeToStrategySource(node));

    builder.onExecuted((node, result) => {
        const raw = result?.raw;
        boundedNotification(
            raw?.triple_ksampler_overlap,
            'TripleKSampler: Stage overlap',
            'warn',
        );
        boundedNotification(
            raw?.triple_ksampler_dry_run,
            'TripleKSampler: Dry Run',
            'info',
        );
        resetDryRun(node);
    });

    builder.onRemoved((node) => {
        const state = states.get(node);
        if (!state) return;
        for (const subscription of state.subscriptions) dispose(subscription);
        dispose(state.sourceSubscription);
        states.delete(node);
    });
});


comfy.queue.onInterrupted(resetAllDryRuns);
