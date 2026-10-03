import { comfy } from "/comfy/api/v2.js";
import { PanoramaViewer } from "./panorama_viewer.js";


const viewers = new WeakMap();

function install(nodeType, { video, mountName }) {
  comfy.defs.extend(nodeType, (builder) => {
    builder.onCreated((node) => {
      node.setSizeConstraints({ minWidth: 340, minHeight: 380 });
      let viewer;
      node.widgets.mount({
        name: mountName,
        height: 300,
        hideOnZoom: false,
        serialize: false,
        sendToPrompt: false,
        render(container) {
          viewer = new PanoramaViewer(container, { video });
          viewers.set(node, viewer);
        },
        destroy() {
          viewer?.destroy();
          viewers.delete(node);
        },
      });
    });

    builder.onExecuted((node) => {
      const viewer = viewers.get(node);
      if (!viewer) return;
      const images = node.getOutputImages();
      const fps = video ? Number(node.widgets.get("fps")?.getValue() ?? 30) : 1;
      viewer.setFrames(video ? images : images.slice(0, 1), fps, video);
    });

    builder.onResized((node) => viewers.get(node)?.resize());
    builder.onRemoved((node) => {
      viewers.get(node)?.destroy();
      viewers.delete(node);
    });
  });
}

install("PanoramaViewerNode", { video: false, mountName: "panoramapreview" });
install("PanoramaVideoViewerNode", { video: true, mountName: "panoramavideopreview" });
