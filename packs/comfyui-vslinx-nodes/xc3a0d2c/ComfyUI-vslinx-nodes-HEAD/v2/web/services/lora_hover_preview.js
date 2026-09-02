import { comfy } from '/comfy/api/v2.js';

const SETTING = 'vslinx.modelHoverPreviews';
let unregister;

function update(enabled) {
  unregister?.();
  unregister = undefined;
  if (enabled !== true) return;
  unregister = comfy.widgets.registerComboPreview({
    id: 'vslinx.modelHoverPreviews',
    modelCategories: ['loras', 'checkpoints', 'unet', 'diffusion_models'],
    extensions: ['safetensors', 'sft', 'pt', 'ckpt', 'gguf'],
    candidatePolicy: 'adjacent-model-preview-v1',
    media: ['image/png', 'image/webp', 'image/jpeg', 'video/mp4', 'video/webm'],
  });
}

comfy.settings.declare({
  id: SETTING,
  name: 'Show hover previews in all model dropdowns',
  type: 'boolean',
  defaultValue: false,
  category: ['vslinx', 'Models', 'Hover previews'],
  tooltip: 'Show host-managed adjacent image or video previews for model options.',
  onChange: (value) => update(value === true),
});

update(comfy.settings.get(SETTING) === true);
