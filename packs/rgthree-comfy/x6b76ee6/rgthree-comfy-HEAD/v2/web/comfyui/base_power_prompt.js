import { comfy } from '/comfy/api/v2.js';

const SERVER_WIDGET_PREFIXES = ['insert_', 'target_', 'crop_', 'values_'];
const states = new Map();

function stateKey(node) {
    return `${node.graphId}:${node.id}`;
}

function comboDeclarations(def) {
    const declarations = new Map();
    for (const input of def.inputs) {
        if (input.values) declarations.set(input.name, [...input.values]);
    }
    for (const [name, declaration] of Object.entries(def.hidden)) {
        if (Array.isArray(declaration) && Array.isArray(declaration[0])) {
            declarations.set(name, [...declaration[0]]);
        }
    }
    return declarations;
}

function filterFor(node) {
    const source = String(node.getProperty('combos_filter') ?? '').trim();
    if (!source) return null;
    try {
        return new RegExp(source, 'i');
    } catch (error) {
        console.error(`Could not parse "${source}" for Regular Expression`, error);
        return null;
    }
}

function writePrompt(state, text) {
    const prompt = state.text?.value ?? String(state.prompt.getValue() ?? '');
    const selectionEnd = state.text?.selection.end ?? 0;
    let first = prompt.substring(0, selectionEnd).replace(/ +$/, '');
    first += first.length && first.at(-1) !== '\n' ? ' ' : '';
    let second = prompt.substring(selectionEnd).replace(/^ +/, '');
    second = second.length && second[0] !== '\n' ? ` ${second}` : second;
    const value = first + text + second;
    const selection = { start: first.length, end: first.length + text.length };
    if (state.text) {
        state.text.setValue(value, selection);
        state.text.focus();
        state.text = { ...state.text, value, selection };
    } else {
        state.prompt.setValue(value);
    }
}

function chooseComboValue(state, key, selected) {
    const values = state.comboOptions.get(key);
    if (!values) return;
    const value = String(selected);
    if (value === String(values[0]) || /^disable\s[a-z]/i.test(value)) return;
    queueMicrotask(() => {
        if (key.includes('embedding')) {
            writePrompt(state, `embedding:${value}`);
        } else if (key.includes('saved')) {
            const saved = state.comboValues.get(`values_${key}`);
            const index = values.findIndex((entry) => String(entry) === value);
            if (saved?.[index] !== undefined) writePrompt(state, String(saved[index]));
        } else if (key.includes('lora')) {
            writePrompt(state, `<lora:${value}:1.0>`);
        }
        const combo = state.combos.get(key);
        if (combo) combo.setValue(values[0]);
    });
}

function refreshCombos(state, def) {
    state.def = def;
    const declarations = comboDeclarations(def);
    const filter = filterFor(state.node);
    state.comboValues.clear();

    for (const [key, values] of declarations) {
        if (key.startsWith('values')) state.comboValues.set(key, values);
        if (!key.startsWith('insert')) continue;

        const filtered = filter
            ? values.filter((value, index) =>
                index < 1 ||
                (index === 1 && /^disable\s[a-z]/i.test(String(value))) ||
                filter.test(String(value)))
            : values;
        const visible = filtered.length > 2 ||
            (filtered.length > 1 && !/^disable\s[a-z]/i.test(String(filtered[1])));
        const existing = state.combos.get(key);
        if (!visible) {
            if (existing) state.node.widgets.remove(key);
            state.combos.delete(key);
            state.comboOptions.delete(key);
            continue;
        }
        state.comboOptions.set(key, filtered);
        if (existing) {
            existing.setOption('values', filtered);
            existing.setValue(filtered[0]);
            continue;
        }
        const widget = state.node.widgets.add({
            type: 'combo',
            name: key,
            value: filtered[0],
            options: { values: filtered },
            serialize: true
        });
        widget.on('change', (selected) => chooseComboValue(state, key, selected));
        state.combos.set(key, widget);
    }
}

function outputEnabled(node, type) {
    if (type.includes('model')) {
        return node.inputs.all().some((slot) =>
            slot.name.includes('model') && slot.isConnected);
    }
    if (type.includes('conditioning') || type.includes('clip')) {
        return node.inputs.all().some((slot) =>
            slot.name.includes('clip') && slot.isConnected);
    }
    return true;
}

function stabilizeOutputs(node) {
    for (const output of node.outputs) {
        const type = output.type.toLowerCase();
        if (type.includes('string')) {
            output.modify({ color: '#7F7', colorWhenUnconnected: '#7F7' });
        } else if (type.includes('model') ||
            type.includes('conditioning') ||
            type.includes('clip')) {
            const color = outputEnabled(node, type) ? null : '#666665';
            output.modify({ color, colorWhenUnconnected: color });
        }
    }
}

function handlePromptKey(state, event) {
    if (event.kind !== 'keydown' ||
        (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') ||
        (!event.ctrlKey && !event.metaKey)) return;

    let { start, end } = event.selection;
    const fullText = event.value;
    let selectedText = fullText.substring(start, end);
    if (!selectedText) {
        const stopOn = '<>()\r\n\t';
        if (fullText[start] === '>') {
            start -= 2;
            end -= 2;
        }
        if (fullText[end - 1] === '<') {
            start += 2;
            end += 2;
        }
        while (start > 0 && !stopOn.includes(fullText[start])) start--;
        while (end < fullText.length && !stopOn.includes(fullText[end - 1])) end++;
        selectedText = fullText.substring(start, end);
    }
    if (!selectedText.startsWith('<lora:') || !selectedText.endsWith('>')) return;

    const match = selectedText.match(/:(-?\d*(\.\d*)?)>$/);
    const current = Number(match?.[1] ?? 1);
    const weight = (Number.isFinite(current) ? current : 1) +
        (event.key === 'ArrowUp' ? 1 : -1) * (event.shiftKey ? 0.01 : 0.1);
    const updatedText = selectedText.replace(
        /(:-?\d*(\.\d*)?)?>$/,
        `:${weight.toFixed(2)}>`
    );
    const value = fullText.slice(0, start) + updatedText + fullText.slice(end);
    const selection = { start, end: start + updatedText.length };
    event.setValue(value, selection);
    event.preventDefault();
    event.stopPropagation();
    state.text = {
        value,
        selection,
        setValue: event.setValue,
        focus: event.focus
    };
}

function attach(node, def) {
    if (node.getProperty('combos_filter') === undefined) {
        node.setProperty('combos_filter', '');
    }
    const prompt = node.widgets.at(0);
    if (!prompt) return;
    for (const name of node.widgets.names()) {
        if (SERVER_WIDGET_PREFIXES.some((prefix) => name.startsWith(prefix))) {
            node.widgets.remove(name);
        }
    }
    const state = {
        node,
        def,
        prompt,
        combos: new Map(),
        comboOptions: new Map(),
        comboValues: new Map(),
        text: null,
        unsubscribes: []
    };
    state.unsubscribes.push(prompt.on('textInteraction', (event) => {
        state.text = {
            value: event.value,
            selection: event.selection,
            setValue: event.setValue,
            focus: event.focus
        };
        handlePromptKey(state, event);
    }));
    states.set(stateKey(node), state);
    refreshCombos(state, def);
    stabilizeOutputs(node);
}

function detach(node) {
    const state = states.get(stateKey(node));
    if (!state) return;
    for (const unsubscribe of state.unsubscribes) unsubscribe();
    states.delete(stateKey(node));
}

export function extendPowerPrompt(builder) {
    const type = builder.def.type;
    builder.onCreated((node) => attach(node, comfy.defs.get(type) ?? builder.def));
    builder.onConfigured((node) => {
        const state = states.get(stateKey(node));
        if (state) refreshCombos(state, comfy.defs.get(type) ?? state.def);
    });
    builder.onConnectionsChanged((node) => stabilizeOutputs(node));
    builder.onPropertyChanged((node, event) => {
        if (event.name !== 'combos_filter') return;
        const state = states.get(stateKey(node));
        if (state) refreshCombos(state, comfy.defs.get(type) ?? state.def);
    });
    builder.onBeforeConnect((node, event) => {
        if (event.side !== 'output') return;
        const output = node.outputs.at(event.index);
        return !output || outputEnabled(node, output.type.toLowerCase());
    });
    builder.onRemoved(detach);
}

comfy.defs.onRefreshed(() => {
    for (const state of states.values()) {
        const def = comfy.defs.get(state.node.type);
        if (def) refreshCombos(state, def);
    }
});
