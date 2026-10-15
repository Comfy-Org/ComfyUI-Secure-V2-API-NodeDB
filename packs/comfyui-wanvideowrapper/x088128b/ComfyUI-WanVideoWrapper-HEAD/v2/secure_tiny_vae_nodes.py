"""Tiny Wan VAE loader candidate: validate weights, retain a confined recipe.

The owned consumer must rebuild the immutable selected model in its admitted
execution. No live Python model or host path is exported across the graph.
"""
import hashlib
import io as buffers
import re
from comfy_api.latest import io, sdk
from ._wan_catalogue import valid_catalogue_name


async def _weights(model_name, expected_sha256=None):
    if not valid_catalogue_name(model_name):
        raise ValueError('Wan tiny VAE requires a confined catalogue name')
    assets = sdk.current_context().assets
    asset = await assets.resolve('vae_approx', model_name)
    size = await assets.size(asset)
    if not 0 < size <= 64 * 1024 * 1024:
        raise ValueError('Wan tiny VAE exceeds the bounded 64 MiB weight domain')
    digest = await assets.digest(asset)
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError('Selected tiny VAE resource changed')
    chunks = []
    for offset in range(0, size, 4 * 1024 * 1024):
        count = min(4 * 1024 * 1024, size - offset)
        chunk = await assets.read_range(asset, offset=offset, length=count)
        if len(chunk) != count:
            raise ValueError('Truncated tiny VAE resource')
        chunks.append(chunk)
    data = b''.join(chunks)
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('Tiny VAE resource changed during read')
    return data, digest


async def load_tiny_model(model_name, precision='fp16', parallel=False, expected_sha256=None):
    import torch
    from .taehv import TAEHV
    if precision not in ('fp16', 'fp32', 'bf16') or type(parallel) is not bool:
        raise ValueError('Invalid Wan tiny VAE precision or parallel setting')
    data, digest = await _weights(model_name, expected_sha256)
    if model_name.lower().endswith(('.safetensors', '.sft')):
        from safetensors.torch import load
        state = load(data)
    else:
        state = torch.load(buffers.BytesIO(data), map_location='cpu', weights_only=True)
    dtype = {'fp16': torch.float16, 'fp32': torch.float32, 'bf16': torch.bfloat16}[precision]
    model = TAEHV(state, parallel=parallel, dtype=dtype, model_name=model_name)
    model.to(device=torch.device('cpu'), dtype=dtype)
    recipe = {'format': 'wan-tiny-vae-recipe-v1', 'model_name': model_name,
              'weights_sha256': digest, 'precision': precision, 'parallel': parallel}
    return model, recipe, data


async def rebuild_tiny_vae(recipe):
    if not isinstance(recipe, dict) or set(recipe) != {'format', 'model_name', 'weights_sha256', 'precision', 'parallel'} or recipe['format'] != 'wan-tiny-vae-recipe-v1':
        raise ValueError('Invalid Wan tiny VAE recipe')
    if not isinstance(recipe['weights_sha256'], str) or not re.fullmatch('[0-9a-f]{64}', recipe['weights_sha256']):
        raise ValueError('Wan tiny VAE requires an exact resource digest')
    return await load_tiny_model(recipe['model_name'], recipe['precision'], recipe['parallel'], recipe['weights_sha256'])


class WanVideoTinyVAELoader(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw', 'assets', 'models.download')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoTinyVAELoader', display_name='WanVideo Tiny VAE Loader', category='WanVideoWrapper',
                         description="Loads Wan VAE model from 'ComfyUI/models/vae_approx'",
                         inputs=[io.Combo.Input('model_name', options=[], tooltip="These models are loaded from 'ComfyUI/models/vae_approx'",
                                                remote=io.RemoteOptions(route='/models/vae_approx', refresh_button=True, control_after_refresh='first')),
                                 io.Combo.Input('precision', options=['fp16', 'fp32', 'bf16'], optional=True, default='fp16'),
                                 io.Boolean.Input('parallel', optional=True, default=False, tooltip='uses more memory but is faster')],
                         outputs=[io.Custom('WANVAE').Output(display_name='vae')])

    @classmethod
    def validate_inputs(cls, input_types=None, **kwargs):
        name = kwargs.get('model_name')
        return True if name is None or valid_catalogue_name(name) else 'Wan tiny VAE requires a confined logical catalogue name'

    @classmethod
    async def execute(cls, model_name, precision='fp16', parallel=False):
        _, recipe, _ = await load_tiny_model(model_name, precision, parallel)
        return io.NodeOutput(recipe)


NODE_CLASS_MAPPINGS = {'WanVideoTinyVAELoader': WanVideoTinyVAELoader}
