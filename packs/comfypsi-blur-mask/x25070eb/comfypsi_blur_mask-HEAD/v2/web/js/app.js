import { comfy } from "/comfy/api/v2.js";

let unsubscribe = null;

export function install() {
  if (unsubscribe !== null) return;
  unsubscribe = comfy.defs.extend("comfypsi_blur_mask", (builder) => {
    builder.onCreated((node) => {
      node.setSize({ width: 225, height: node.getSize().height });
    });
  });
}

export function dispose() {
  if (unsubscribe === null) return;
  unsubscribe();
  unsubscribe = null;
}

install();
