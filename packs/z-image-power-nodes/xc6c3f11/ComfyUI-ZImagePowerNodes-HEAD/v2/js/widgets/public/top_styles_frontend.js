/**
 * Public-API conversion of my_top_styles.js and my_top_styles_editor.js.
 * Original: Martin Rizzo, ComfyUI-ZImagePowerNodes, MIT, source c6c3f11.
 * Source candidate only: actual browser/queue qualification is pending.
 */
const SELECTOR = 'MyTop10Styles //ZImagePowerNodes';
const EDITOR = 'MyTop10StylesEditor //ZImagePowerNodes';

export function isValidStyleName(name) {
    if (typeof name !== 'string') return false;
    const trimmed = name.trim();
    return trimmed !== '' && trimmed !== '-' && trimmed !== 'none';
}

export function installTopStylesFrontend(comfy) {
    const records = [];
    const stops = [];
    let installed = true;
    const styles = node => node.widgets.all().filter(widget => widget.name.startsWith('style_'));
    const recordFor = node => records.find(record => comfy.sameEntity(record.node,node));
    const live = record => installed && !record.disposed && !record.node.isDeleted &&
        record.documentId === comfy.workflow.documentId();
    const inputNode = (node,name) => {
        const source = node.inputs.byName(name)?.source();
        return source ? comfy.graph.node(source.nodeId) : undefined;
    };
    const outputNodes = (node,name) => (node.outputs.byName(name)?.targets() ?? [])
        .map(target => comfy.graph.node(target.nodeId)).filter(Boolean);
    const editorStyles = node => styles(node).map(widget => widget.getValue().toString());

    function updateTopStyles(record,names = []) {
        if (!live(record)) return;
        const next = styles(record.node).map((widget,index) => {
            const name = index < names.length ? names[index] : '';
            const label = isValidStyleName(name) ? `${index + 1} - ${name}` : '-';
            if (record.labels.get(widget.name) !== label) widget.setLabel(label);
            return [widget.name,label];
        });
        record.labels = new Map(next);
    }

    // Native callback mode "no-event" bypasses only this controller. The
    // public commit still runs the host callback chain, so retain the exact
    // quiet transition until its asynchronous change notification arrives.
    function setQuiet(record,widget,value) {
        const oldValue = widget.getValue();
        if (Object.is(oldValue,value)) return;
        const pending = record.quiet.get(widget.name) ?? [];
        const transition = {value,oldValue};
        pending.push(transition);
        record.quiet.set(widget.name,pending);
        try { widget.setValue(value); }
        catch (error) {
            const index = pending.indexOf(transition);
            if (index >= 0) pending.splice(index,1);
            if (!pending.length) record.quiet.delete(widget.name);
            throw error;
        }
    }

    function consumeQuiet(record,name,value,oldValue) {
        const pending = record.quiet.get(name);
        const index = pending?.findIndex(item => Object.is(item.value,value) && Object.is(item.oldValue,oldValue)) ?? -1;
        if (index < 0) return false;
        pending.splice(index,1);
        if (!pending.length) record.quiet.delete(name);
        return true;
    }

    function deselectAll(record) {
        if (!live(record)) return;
        for (const widget of styles(record.node)) if (widget.getValue()) setQuiet(record,widget,false);
    }

    function processChainMessage(sender,message) {
        if (!live(sender)) return;
        let first = sender;
        const left = new Set();
        while (true) {
            if (left.has(first)) { console.error('Recursive chain detected!'); return; }
            left.add(first);
            const node = inputNode(first.node,'input');
            const previous = node?.type === SELECTOR ? recordFor(node) : undefined;
            if (!previous || !live(previous)) break;
            first = previous;
        }
        // The set bounds corrupt cyclic graphs by the actual controller
        // identities. It adds no arbitrary cap to a valid native chain.
        const visiting = new Set();
        function visit(record) {
            if (!live(record)) return;
            if (visiting.has(record)) { console.error('Recursive chain detected!'); return; }
            visiting.add(record);
            const channel = record.node.widgets.get('output_to').getValue();
            if (message.type === 'deselectAllStyles') {
                if (!comfy.sameEntity(record.node,sender.node) && (!message.channel || message.channel === channel)) {
                    deselectAll(record);
                }
            } else if (message.type === 'forceNoRepeatChannels') {
                if (message.channels.has(channel)) deselectAll(record);
                else message.channels.add(channel);
            }
            for (const node of outputNodes(record.node,'output')) {
                const next = node.type === SELECTOR ? recordFor(node) : undefined;
                if (next) visit(next);
            }
            visiting.delete(record);
        }
        visit(first);
    }

    function switchChanged(record,name,value,oldValue) {
        if (!live(record) || consumeQuiet(record,name,value,oldValue)) return;
        for (const widget of styles(record.node)) if (widget.name !== name) setQuiet(record,widget,false);
        processChainMessage(record,{type:'deselectAllStyles',channel:record.node.widgets.get('output_to').getValue()});
    }

    function syncSelector(record) {
        if (!live(record)) return;
        const provider = inputNode(record.node,'top_styles');
        const providerId = provider?.id ?? null;
        if (record.providerId !== providerId) {
            record.providerId = providerId;
            updateTopStyles(record,provider?.type === EDITOR ? editorStyles(provider) : []);
        }
        const origin = inputNode(record.node,'input');
        const originId = origin?.id ?? null;
        if (record.originId !== originId) {
            record.originId = originId;
            if (origin) processChainMessage(record,{type:'forceNoRepeatChannels',channels:new Set()});
        }
    }

    function editorChanged(record) {
        if (!live(record)) return;
        const names = editorStyles(record.node);
        for (const node of outputNodes(record.node,'TOP_STYLES')) {
            const selector = node.type === SELECTOR ? recordFor(node) : undefined;
            if (selector) updateTopStyles(selector,names);
        }
    }

    function drop(record) {
        if (!record || record.disposed) return;
        record.disposed = true;
        for (const stop of record.stops.splice(0)) stop();
        record.quiet.clear();record.labels.clear();
        const index = records.indexOf(record);
        if (index >= 0) records.splice(index,1);
    }

    function bind(node) {
        if (!installed || node.isDeleted || ![SELECTOR,EDITOR].includes(node.type)) return;
        const existing = recordFor(node);
        if (existing && live(existing)) return existing;
        drop(existing);
        const widgets = styles(node);
        if (!widgets.length || (node.type === SELECTOR &&
            (!node.widgets.get('output_to') || !node.widgets.get('control_after_generate')))) {
            console.error(node.type === SELECTOR ? 'Missing required widgets!' : 'MyTopStylesEditorCtrl: No style widgets found!');
            return;
        }
        const record = {node,documentId:comfy.workflow.documentId(),stops:[],quiet:new Map(),labels:new Map(),
            providerId:null,originId:null,disposed:false};
        records.push(record);
        for (const widget of widgets) {
            record.stops.push(widget.on('change',(value,oldValue) => {
                if (!live(record)) return;
                if (node.type === EDITOR) editorChanged(record);
                else switchChanged(record,widget.name,value,oldValue);
            }));
        }
        if (node.type === SELECTOR) {
            updateTopStyles(record,[]);
            syncSelector(record);
        }
        return record;
    }

    function configured(node) {
        drop(recordFor(node));
        queueMicrotask(() => {
            const record = bind(node);
            if (!record) return;
            if (node.type === EDITOR) editorChanged(record);
            else syncSelector(record);
        });
    }

    function advance(record) {
        if (!live(record) || record.node.widgets.get('control_after_generate').getValue() !== 'next') return;
        const widgets = styles(record.node);
        const valid = widget => isValidStyleName(record.labels.get(widget.name));
        const first = widgets.findIndex(valid);
        if (first < 0) { deselectAll(record); return; }
        let index = first;
        for (; index < widgets.length; index++) if (widgets[index].getValue()) { index++; break; }
        for (; index < widgets.length; index++) if (valid(widgets[index])) break;
        if (index >= widgets.length) index = first;
        // Selection changes immediately in the local replica; propagate the
        // native chain rule once rather than waiting for the host echo.
        setQuiet(record,widgets[index],true);
        for (const widget of widgets) if (widget.name !== widgets[index].name) setQuiet(record,widget,false);
        processChainMessage(record,{type:'deselectAllStyles',channel:record.node.widgets.get('output_to').getValue()});
    }

    stops.push(comfy.defs.extend(def => [SELECTOR,EDITOR].includes(def.type),builder => {
        builder.onCreated(node => queueMicrotask(() => bind(node)));
        builder.onConfigured(configured);
        builder.onConnectionsChanged(node => {
            const record = bind(node);
            if (record?.node.type === SELECTOR) syncSelector(record);
        });
        builder.onRemoved(node => drop(recordFor(node)));
    }));
    stops.push(comfy.onWorkflowLoaded(() => {
        for (const record of [...records]) drop(record);
        for (const node of comfy.graph.nodes()) bind(node);
    }));
    stops.push(comfy.queue.onAcceptedSubmission(event => {
        if (!installed || event.documentId !== comfy.workflow.documentId()) return;
        for (const node of comfy.graph.nodes()) if (node.type === SELECTOR) {
            const record = recordFor(node);
            if (record) advance(record);
        }
    }));
    for (const node of comfy.graph.nodes()) bind(node);
    return {dispose() {
        if (!installed) return;
        installed = false;
        for (const record of [...records]) drop(record);
        for (const stop of stops.splice(0)) stop();
    }};
}
