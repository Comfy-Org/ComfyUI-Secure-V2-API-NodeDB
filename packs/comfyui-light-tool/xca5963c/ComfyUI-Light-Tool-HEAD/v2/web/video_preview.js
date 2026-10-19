import { comfy } from '/comfy/api/v2.js';

for (const nodeId of [
  'Light_Tool__PreviewVideo_24e01362ad662b2739c9444e',
  'Light_Tool__SaveVideo_ccbc535096781f2841cdca37',
]) {
  comfy.defs.extend(nodeId, (builder) => {
    builder.onExecuted(async (node, result) => {
      const sources = result.raw?.video_url;
      if (!Array.isArray(sources) || sources.length !== 1) {
        throw new Error('Expected one host-issued video preview descriptor');
      }
      await node.previewVideo(sources[0], {
        autoplay: true, loop: true, muted: true, maxWidth: 768, maxHeight: 768,
      });
      node.setSize({ width: 768, height: 768 });
    });
  });
}
