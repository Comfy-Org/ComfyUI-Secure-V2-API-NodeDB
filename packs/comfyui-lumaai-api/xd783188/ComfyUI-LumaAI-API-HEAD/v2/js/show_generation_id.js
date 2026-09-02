import { comfy } from '/comfy/api/v2.js';


export const FRONTEND_INTENTS = Object.freeze([
  'luma-generation-id-readout',
  'luma-generation-running-state',
  'arbitrary-video-url-preview-rejected',
]);


const TYPES = Object.freeze([
  'LumaText2Video',
  'LumaImage2Video',
  'LumaInterpolateGenerations',
  'LumaExtendGeneration',
  'LumaImageGeneration',
  'LumaModifyImage',
]);
const TYPE_SET = new Set(TYPES);


function firstText(value) {
  const item = Array.isArray(value) ? value[0] : value;
  return item == null ? '' : String(item);
}


function populate(node, value) {
  let widget = node.widgets.get('gen_output');
  if (!widget) {
    widget = node.widgets.add({
      type: 'textarea',
      name: 'gen_output',
      value: '',
      disabled: true,
      options: { multiline: true, read_only: true },
    });
  }
  widget.setValue(firstText(value));
  widget.setDisabled(true);
  node.setSizeConstraints({ autoHeight: true });
}


for (const type of TYPES) {
  comfy.defs.extend(type, (builder) => {
    builder.onExecuted((node, result) => {
      populate(node, result?.text?.[0] ?? result?.raw?.text);
    });
  });
}


comfy.onExecutingNodeChanged((node) => {
  if (node && TYPE_SET.has(node.comfyClass || node.type)) {
    populate(node, 'generating...');
  }
});


// SECURITY REJECTION: the source VideoPreview extension assigns an arbitrary
// workflow string directly to an HTML video source. That is ambient browser network
// access, including loopback and private-network destinations. The secure
// release does not register LumaPreviewVideo and exposes no direct fetch or
// media URL facility to this opaque-origin extension.
