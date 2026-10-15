import { comfy } from '/comfy/api/v2.js';
import { mountedLines, resultLines, textLines } from './display-state.mjs';
const states = new Map();
comfy.defs.extend('SimpleReadableMetadataSG', builder => {
  builder.onCreated(node => {
    const state = { properties: textLines(node.getProperty('imagePropertiesText') ?? []), metadata: textLines(node.getProperty('imageMetadataText') ?? []) };
    states.set(node.id, state); node.setSizeConstraints({ minWidth: 400, autoHeight: true });
    state.ui = mountedLines(node, 'metadata_readout', () => {
      const mode = node.widgets.get('show_info')?.getValue() ?? 'both';
      return mode === 'none' ? [] : [...(['both','properties'].includes(mode) ? state.properties : []), ...(['both','metadata'].includes(mode) ? state.metadata : [])];
    });
    const widget = node.widgets.get('show_info');
    if (widget) state.ui.disposers.push(widget.on('change', state.ui.render));
  });
  builder.onExecuted((node, result) => {
    const state = states.get(node.id); if (!state) return;
    const lines = resultLines(result); state.properties = lines.slice(0,3); state.metadata = lines.slice(4); state.ui.render();
  });
  builder.onConfigured((node, info) => {
    const state = states.get(node.id); if (!state) return;
    state.properties = textLines(info.imagePropertiesText ?? node.getProperty('imagePropertiesText') ?? []);
    state.metadata = textLines(info.imageMetadataText ?? node.getProperty('imageMetadataText') ?? []); state.ui.render();
  });
  builder.onSerialize(node => {
    const state = states.get(node.id); return state ? { imagePropertiesText: state.properties, imageMetadataText: state.metadata } : {};
  });
  builder.onRemoved(node => states.delete(node.id));
});
