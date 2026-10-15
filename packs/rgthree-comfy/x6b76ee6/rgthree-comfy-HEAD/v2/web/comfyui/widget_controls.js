// These are rgthree's own controls, shared by its modules in the same realm.
// Nothing calls an unpublished method on a host handle or another pack.
const controls = new Map();
const key = (node, name) => JSON.stringify([node.graphId ?? '', node.id, name]);
export function registerWidgetControl(node, name, control) {
    const identity = key(node, name);
    controls.set(identity, control);
    return () => { if (controls.get(identity) === control) controls.delete(identity); };
}
export function getWidgetControl(node, name) {
    return controls.get(key(node, name));
}
