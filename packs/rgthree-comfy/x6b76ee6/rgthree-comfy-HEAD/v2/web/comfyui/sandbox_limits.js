// The sandbox host refuses a few registrations whose result it would need synchronously:
// comfy.defs.extend hooks such as onBeforeConnect, onUnplacedLink and onDragOver, and
// menu items whose label is a function. A refusal must cost only that behaviour, never
// the whole module, so each such registration goes through `whereSupported`. Any other
// error is re-thrown unchanged. Each refused behaviour is reported once per node type.
const REFUSED = /is not available to a sandboxed pack|needs a string label/;
const reported = new Set();

export function whereSupported(nodeType, behaviour, register) {
    try {
        register();
        return true;
    }
    catch (error) {
        if (!REFUSED.test(String(error?.message ?? error))) {
            throw error;
        }
        const key = `${nodeType}\u0000${behaviour}`;
        if (!reported.has(key)) {
            reported.add(key);
            console.warn(`[rgthree-comfy] ${nodeType}: ${behaviour} is not available in the sandbox yet.`);
        }
        return false;
    }
}
