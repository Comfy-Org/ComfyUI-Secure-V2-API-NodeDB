import { comfy } from '/comfy/api/v2.js';

// Preserve the three owned targets and the source's external ClipVision target.
comfy.defs.extend([
  'ReduxFineTune', 'ReduxFineTuneAdvanced', 'ClipVision', 'ClipVisionStyleLoader'
], (definition) => {
  definition.onCreated((node) => {
    node.setColor('#222e40');
    node.setBgColor('#364254');
    const size = node.getSize();
    node.setSize({ width: 340, height: size?.height ?? 80 });
  });
});
