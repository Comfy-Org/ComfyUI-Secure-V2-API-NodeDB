import { comfy } from '/comfy/api/v2.js';
import { mountedLines, resultLines, textLines, managedView, imageProperties } from './display-state.mjs';
const states = new Map();
comfy.defs.extend('SimpleReadableMetadataMAXSG', builder => {
  builder.onCreated(node => {
    const state = { lines: textLines(node.getProperty('imageParamsText') ?? []), sequence: 0, closed: false };
    states.set(node.id, state); node.setSizeConstraints({ minWidth: 400, autoHeight: true });
    state.ui = mountedLines(node, 'metadata_readout', () => state.lines);
    node.widgets.mount({ name: 'metadata_preview', height: 0, serialize: false, sendToPrompt: false,
      render(container) {
        const widget = node.widgets.get('image'), doc = container.ownerDocument;
        const changed = label => {
          const ticket = ++state.sequence;
          state.removeLoaded?.(); state.image?.remove(); state.image = undefined;
          if (!label || state.closed) return;
          const image = doc.createElement('img'), name = `srm-preview-${node.id}-${ticket}`;
          image.setAttribute('data-name', name); image.style.display = 'none';
          const loaded = async () => {
            try {
              const handle = comfy.element(name);
              const width = await handle.get('naturalWidth'), height = await handle.get('naturalHeight');
              if (state.closed || ticket !== state.sequence || !states.has(node.id)) return;
              state.lines = imageProperties(width, height); state.ui.render();
            } catch (error) { if (!state.closed && ticket === state.sequence) console.error('Image preview failed', String(error)); }
          };
          image.addEventListener('load', loaded); container.append(image);
          state.removeLoaded = () => image.removeEventListener('load', loaded);
          state.image = image; image.src = managedView(comfy, label);
        };
        state.off = widget?.on('change', changed);
      },
      destroy() { state.closed = true; state.sequence++; state.off?.(); state.removeLoaded?.(); state.image = undefined; },
    });
  });
  builder.onExecuted((node, result) => { const state = states.get(node.id); if (state) { state.sequence++; state.lines = resultLines(result); state.ui.render(); } });
  builder.onConfigured((node, info) => { const state = states.get(node.id); if (state) { state.lines = textLines(info.imageParamsText ?? node.getProperty('imageParamsText') ?? []); state.ui.render(); } });
  builder.onSerialize(node => { const state = states.get(node.id); return state ? { imageParamsText: state.lines } : {}; });
  builder.onRemoved(node => { const state = states.get(node.id); if (state) { state.closed = true; state.sequence++; state.off?.(); state.removeLoaded?.(); } states.delete(node.id); });
});
