// Debug Metadata display on published handles; collector/browser gates remain.
import { METADATA_COLORS, displayTokens, executionMetadata,
  metadataSerializeValue, restoreMetadataValue } from './metadata_display_logic.js';
export { displayTokens, executionMetadata } from './metadata_display_logic.js';

const TYPE = 'Debug Metadata (LoraManager)';
const keyOf = node => JSON.stringify([node.graphId, node.id]);

export function registerMetadataDisplay(comfy) {
  const instances = new Map();
  let stopped = false;
  const off = comfy.defs.extend(TYPE, builder => {
    builder.onCreated(node => {
      if (stopped || node.isDeleted) return;
      const key = keyOf(node);
      instances.get(key)?.dispose();
      const previous = node.widgets.get('metadata')?.getValue();
      if (node.widgets.get('metadata')) node.widgets.remove('metadata');
      let alive = true, root = null, metadata = restoreMetadataValue(previous, null);
      let offChange = () => {}, offSerialize = () => {};

      const render = () => {
        if (!alive || node.isDeleted || !root) return;
        // Evaluate before clearing: native stringify/computed errors must not
        // become invented successful data or a new error readout.
        const display = displayTokens(metadata);
        const content = root.ownerDocument.createElement('div');
        content.style.cssText = 'flex:1;overflow:auto;font-family:monospace;font-size:12px;line-height:1.5;white-space:pre-wrap;color:rgba(226,232,240,0.9)';
        const body = root.ownerDocument.createElement(display.placeholder ? 'div' : 'pre');
        if (display.placeholder) {
          body.style.cssText = 'font-style:italic;color:rgba(226,232,240,0.6);text-align:center;padding:20px 0';
          body.textContent = display.text;
        } else {
          body.style.cssText = 'margin:0;padding:0';
          for (const token of display.tokens) {
            const span = root.ownerDocument.createElement('span');
            span.textContent = token.text;
            if (token.kind !== 'plain') span.style.color = METADATA_COLORS[token.kind];
            body.appendChild(span);
          }
        }
        content.appendChild(body);
        root.replaceChildren(content);
      };
      const restore = value => {
        if (!alive || node.isDeleted) return;
        if (!value || typeof value !== 'object') return;
        metadata = restoreMetadataValue(value, metadata); render();
      };
      const dispose = () => {
        if (!alive) return;
        alive = false; offChange(); offSerialize();
        offChange = () => {}; offSerialize = () => {};
        if (!node.isDeleted) root?.replaceChildren();
        root = null;
        if (instances.get(key)?.dispose === dispose) instances.delete(key);
      };
      const widget = node.widgets.mount({
        name: 'metadata', height: 200,
        defaultValue: restoreMetadataValue(previous, null),
        // Preserve the native null serializer, not live metadata. Exact slot
        // alignment and async-Vue versus synchronous hook timing need browser proof.
        serialize: true, sendToPrompt: false,
        render(container, cell) {
          if (!alive || node.isDeleted) return;
          const panel = container.ownerDocument.createElement('div');
          panel.style.cssText = 'padding:8px;background:rgba(40,44,52,0.6);border-radius:6px;height:100%;display:flex;flex-direction:column;overflow:hidden;box-sizing:border-box';
          container.replaceChildren(panel); root = panel;
          offChange(); offChange = cell.onChange(restore);
          metadata = restoreMetadataValue(cell.get(), metadata); render();
        },
        destroy: dispose
      });
      offSerialize = widget.on('beforeSerialize', event => {
        if (alive && !node.isDeleted) event.setSerializedValue(metadataSerializeValue());
      });
      instances.set(key, { dispose, execute(output) {
        if (!alive || node.isDeleted) return;
        const update = executionMetadata(output);
        if (!update.changed) return;
        // Native onExecuted changes the transient Vue ref only. Preserve the
        // mounted cell's external value instead of writing backend data to it.
        metadata = update.value; render();
      }});
    });
    builder.onExecuted((node, result) => instances.get(keyOf(node))?.execute(result.raw));
    builder.onRemoved(node => instances.get(keyOf(node))?.dispose());
  });
  return () => {
    if (stopped) return;
    stopped = true; off();
    for (const instance of [...instances.values()]) instance.dispose();
  };
}
