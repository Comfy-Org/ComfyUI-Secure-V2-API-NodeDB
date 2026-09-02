import { comfy } from '/comfy/api/v2.js';

// Per-node preview state. Handles hold no arbitrary properties, so the image
// lives here and the entry is dropped in onRemoved.
const previews = new Map();

comfy.defs.extend('FastPreview', (b) => {
    b.onCreated((node) => {
      node.setSize({ width: 550, height: 550 });

      const state = { img: null };
      state.surface = node.widgets.canvas({
        name: "preview",
        draw: (ctx, [w, h]) => {
          const img = state.img;
          if (!img) return;
          const scale = Math.min(w / img.width, h / img.height);
          const dw = img.width * scale, dh = img.height * scale;
          ctx.drawImage(img, (w - dw) / 2, (h - dh) / 2, dw, dh);
        },
      });
      previews.set(node.id, state);

      const show = blob => {
        const img = new Image();
        img.onload = () => { state.img = img; state.surface.redraw(); };
        img.src = URL.createObjectURL(blob);
      };
      state.show = show;
    });

    // Already correlated to this node — no executing-id global, and no
    // mis-attribution when two FastPreview nodes run at once.
    b.onPreview((node, frame) => {
      previews.get(node.id)?.show(frame.blob);
    });

    b.onRemoved((node) => {
      previews.delete(node.id);
    });
});
