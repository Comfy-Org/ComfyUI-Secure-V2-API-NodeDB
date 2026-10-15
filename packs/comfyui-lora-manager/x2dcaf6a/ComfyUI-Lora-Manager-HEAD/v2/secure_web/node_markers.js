// Typed menu/state adapter for the pinned LoraManager.NodeMarker feature.
// Browser/standalone registry integration remains pending.
import { ROLES, markState, clearState } from './marker_logic.js';

/** @param {import('../comfy-api').NodeHandle} node */
function markerState(node) {
  const title = node.getTitle();
  return { title, properties: {
    lm_marker_role: node.getProperty('lm_marker_role'),
    lm_marker_original_title: node.getProperty('lm_marker_original_title'),
  }};
}

/**
 * Register on all node types, as the original marker menu does.
 * `changed` connects the converted manager's own workflow-registry consumer;
 * no ambient window event or prototype callback is used.
 * @param {import('../comfy-api').Comfy} comfy
 * @param {(node: import('../comfy-api').NodeHandle) => void} changed
 */
export function registerNodeMarkers(comfy, changed = () => {}) {
  let disposed = false;
  const write = (node, state) => {
    if (disposed || node.isDeleted) return;
    node.setProperty('lm_marker_role', state.properties.lm_marker_role);
    node.setProperty('lm_marker_original_title', state.properties.lm_marker_original_title);
    node.setTitle(state.title);
    changed(node);
  };
  const unsubscribe = comfy.defs.extend(/.*/, builder => {
    builder.addMenuItem({
      label: '\uD83C\uDFAF Mark as',
      items(node) {
        const role = node.getProperty('lm_marker_role');
        const items = Object.entries(ROLES).map(([key, definition]) => ({
          label: `${role === key ? '\u2713 ' : ''}${definition.label}`,
          run(target) {
            if (disposed || target.isDeleted || target.getProperty('lm_marker_role') === key) return;
            write(target, markState(markerState(target), key));
          },
        }));
        if (role) items.push({
          label: 'Clear marker',
          run(target) { write(target, clearState(markerState(target))); },
        });
        return items;
      },
    });
  });
  if (typeof unsubscribe !== 'function') throw new Error('Definition unsubscribe contract is unavailable');
  return () => {
    if (disposed) return;
    disposed = true;
    unsubscribe();
  };
}
