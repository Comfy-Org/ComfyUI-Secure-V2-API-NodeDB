import { comfy } from '/comfy/api/v2.js';
import { mountedLines, resultLines, textLines, managedView } from './display-state.mjs';
const states = new Map();
comfy.defs.extend('SimpleReadableMetadataVideoSG', builder => {
  builder.onCreated(node => {
    const state = { lines: textLines(node.getProperty('imageParamsText') ?? []), sequence: 0 };
    states.set(node.id, state); node.setSizeConstraints({ minWidth: 400, autoHeight: true });
    state.ui = mountedLines(node, 'metadata_readout', () => state.lines);
    node.widgets.mount({ name: 'metadata_preview', height: 0, serialize: false, sendToPrompt: false,
      render(container) {
        const doc = container.ownerDocument;
        const widget = node.widgets.get('video');
        const changed = label => {
          const ticket = ++state.sequence;
          state.removeLoaded?.(); state.video?.remove(); state.video = undefined;
          if (!label || state.closed) return;
          const video = doc.createElement('video');
          video.preload = 'metadata'; video.style.display = 'none';
          const loaded = () => {
            if (!states.has(node.id) || state.closed || ticket !== state.sequence) return;
            const width = video.videoWidth, height = video.videoHeight;
            if (!Number.isInteger(width) || !Number.isInteger(height) || width < 1 || height < 1 || width * height > 16777216) return;
            state.lines = [`${width}x${height} | ${(width * height / 1000000).toFixed(2)}MP`, 'Ratio: Calculating...', '(Run node to see full metadata)']; state.ui.render();
          };
          video.addEventListener('loadedmetadata', loaded); container.append(video);
          state.removeLoaded = () => video.removeEventListener('loadedmetadata', loaded);
          state.video = video; video.src = managedView(comfy, label);
        };
        state.off = widget?.on('change', changed);
      },
      destroy() { state.closed = true; state.sequence++; state.off?.(); state.removeLoaded?.(); state.video = undefined; },
    });
  });
  builder.onExecuted((node, result) => { const state = states.get(node.id); if (state) { state.sequence++; state.lines = resultLines(result); state.ui.render(); } });
  builder.onConfigured((node, info) => { const state = states.get(node.id); if (state) { state.lines = textLines(info.imageParamsText ?? node.getProperty('imageParamsText') ?? []); state.ui.render(); } });
  builder.onSerialize(node => { const state = states.get(node.id); return state ? { imageParamsText: state.lines } : {}; });
  builder.onRemoved(node => { const state = states.get(node.id); if (state) { state.closed = true; state.sequence++; state.off?.(); state.removeLoaded?.(); } states.delete(node.id); });
});
