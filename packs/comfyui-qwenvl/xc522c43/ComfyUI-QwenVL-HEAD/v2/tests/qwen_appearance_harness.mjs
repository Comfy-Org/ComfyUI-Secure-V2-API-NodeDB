/** Iframe-realm proof for the real converted QwenVL frontend module. */
import { readFileSync } from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath, pathToFileURL } from 'node:url';


const HERE = path.dirname(fileURLToPath(import.meta.url));
const TARGET = path.resolve(HERE, '../web/js/appearance.js');

function check(condition, message) {
    if (!condition) throw new Error(`ASSERT: ${message}`);
}

let selector;
let created;
const comfy = {
    defs: {
        extend(value, configure) {
            selector = value;
            configure({
                onCreated(callback) {
                    created = callback;
                    return this;
                },
            });
        },
    },
};

const context = vm.createContext({ console });
for (const forbidden of [
    'window', 'document', 'parent', 'top', 'app', 'comfyAPI', 'LiteGraph',
    'fetch', 'XMLHttpRequest', 'WebSocket',
]) {
    check(context[forbidden] === undefined, `${forbidden} leaked into guest`);
}

const api = new vm.SyntheticModule(
    ['comfy'],
    function expose() { this.setExport('comfy', comfy); },
    { context, identifier: '/comfy/api/v2.js' },
);

const source = readFileSync(TARGET, 'utf8');
check(
    !/\b(?:window|document|parent|top|fetch|XMLHttpRequest|WebSocket|app|LiteGraph)\b/.test(source),
    'converted appearance module contains ambient authority',
);
const module = new vm.SourceTextModule(source, {
    context,
    identifier: pathToFileURL(TARGET).href,
});
await module.link(async (specifier) => {
    check(specifier === '/comfy/api/v2.js', `unexpected import ${specifier}`);
    return api;
});
await module.evaluate();

const expected = {
    AILab_QwenVL: ['#28403f', '#374539'],
    AILab_QwenVL_Advanced: ['#28403f', '#374539'],
    AILab_QwenVL_PromptEnhancer: ['#374445', '#474539'],
    AILab_QwenVL_GGUF: ['#474539', '#2c4045'],
    AILab_QwenVL_GGUF_Advanced: ['#474539', '#2c4045'],
    AILab_QwenVL_GGUF_PromptEnhancer: ['#374445', '#474539'],
};

check(Array.isArray(selector), 'appearance selector is not a closed node list');
check(
    JSON.stringify([...selector].sort()) === JSON.stringify(Object.keys(expected).sort()),
    'appearance selector does not cover the exact backend census',
);
check(typeof created === 'function', 'appearance creation hook is missing');

for (const [comfyClass, [color, background]] of Object.entries(expected)) {
    const calls = [];
    let size = { width: 170, height: 93 };
    const node = {
        comfyClass,
        getSize() { return { ...size }; },
        setSize(value) { size = { ...value }; calls.push(['size', value]); },
        setColor(value) { calls.push(['color', value]); },
        setBgColor(value) { calls.push(['background', value]); },
    };
    created(node);
    check(size.width === 340 && size.height === 93, `${comfyClass} size changed incorrectly`);
    check(calls.some(([kind, value]) => kind === 'color' && value === color),
        `${comfyClass} foreground color changed`);
    check(calls.some(([kind, value]) => kind === 'background' && value === background),
        `${comfyClass} background color changed`);
}

console.log('PASS: QwenVL appearance runs in an iframe-safe guest realm');
