import { comfy } from '/comfy/api/v2.js';


export const FRONTEND_INTENTS = Object.freeze([
  'lora-info-base-model-readout',
  'lora-info-details-readout',
  'image-from-url-widget-side-effect-rejected',
  'editor-selection-civitai-prefetch-rejected',
]);


function readout(node, name, type) {
  let widget = node.widgets.get(name);
  if (!widget) {
    widget = node.widgets.add({
      type,
      name,
      value: '',
      disabled: true,
    });
  }
  return widget;
}


function ensureReadouts(node) {
  return {
    model: readout(node, 'Base Model', 'text'),
    output: readout(node, 'output', 'textarea'),
  };
}


function firstString(value) {
  const item = Array.isArray(value) ? value[0] : value;
  return item == null ? '' : String(item);
}


comfy.defs.extend('LoraInfo', (builder) => {
  builder.onCreated((node) => {
    ensureReadouts(node);
    node.setSizeConstraints({ autoHeight: true });
  });

  builder.onExecuted((node, result) => {
    const widgets = ensureReadouts(node);
    widgets.model.setValue(firstString(result?.raw?.model));
    widgets.output.setValue(firstString(result?.raw?.text));
  });
});


// SECURITY REJECTION: upstream POSTed `/lora_info` whenever a combo selection
// changed.  That incidental editor action disclosed a local LoRA digest to a
// remote vendor and mutated a disk cache before the user queued the node.  V2
// performs the bounded lookup only under explicit workflow execution.
//
// SECURITY REJECTION: ImageFromURL accepts an arbitrary host-side URL and
// decodes an unbounded response.  That is an SSRF/private-network primitive;
// the frontend's `/fetch_image` request is also undefined by the upstream
// backend.  No route or node is registered for it in the secure release.
