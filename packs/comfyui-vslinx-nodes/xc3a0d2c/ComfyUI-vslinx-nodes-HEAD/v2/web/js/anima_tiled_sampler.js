import { comfy } from '/comfy/api/v2.js';

const NODE = 'vsLinx_AnimaLLLiteTiledSampler';
const TILED_ONLY = ['vae_decode_tiled', 'vae_decode_tile_size'];

function update(node) {
  const visible = node.widgets.get('sampling_mode')?.getValue() === 'multidiffusion';
  for (const name of TILED_ONLY) node.widgets.get(name)?.setHidden(!visible);
  node.setSizeConstraints({ autoHeight: true });
}

comfy.defs.extend(NODE, (builder) => {
  builder.onCreated((node) => {
    node.widgets.get('sampling_mode')?.on('change', () => update(node));
    update(node);
  });
  builder.onConfigured(update);
});
