import { comfy } from '/comfy/api/v2.js';


// Preserve the legacy minimum initial sizes through the node facade. The host
// owns resize dispatch and redraw behavior in every supported renderer.
comfy.defs.extend(
  (def) => def.type === 'Y7_SideBySide' || def.type === 'Y7_VideoSideBySide',
  (builder) => {
    const minimum = builder.def.type === 'Y7_SideBySide'
      ? { width: 240, height: 150 }
      : { width: 250, height: 150 };
    builder.onCreated((node) => {
      const size = node.getSize();
      node.setSize({
        width: Math.max(size.width, minimum.width),
        height: Math.max(size.height, minimum.height),
      });
      node.setSizeConstraints({
        minWidth: minimum.width,
        minHeight: minimum.height,
      });
    });
  },
);
