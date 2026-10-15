"""Pinned-resource reconstruction for Wan's original visual-only CLIPModel.

The name of the upstream loader says TextEncoder, but its actual CLIPModel
constructs the visual tower and log_scale only. No text tower is substituted.
"""
import re
from comfy_api.latest import io, sdk
from ._wan_catalogue import valid_catalogue_name

FORMAT = 'wan-clip-vision-recipe-v1'
RECIPE_KEYS = {'format', 'model_name', 'folder', 'weights_sha256', 'precision', 'load_device'}
MAX_WEIGHT_BYTES = 3 * 1024**3


def validate_recipe(recipe):
    if (not isinstance(recipe, dict) or set(recipe) != RECIPE_KEYS
            or recipe['format'] != FORMAT
            or not valid_catalogue_name(recipe['model_name'])
            or recipe['folder'] not in ('clip_vision', 'text_encoders')
            or not isinstance(recipe['weights_sha256'], str)
            or re.fullmatch('[0-9a-f]{64}', recipe['weights_sha256']) is None
            or recipe['precision'] not in ('fp16', 'fp32', 'bf16')
            or recipe['load_device'] not in ('main_device', 'offload_device')):
        raise ValueError('Invalid digest-bound Wan CLIP recipe')


async def load_wan_clip(model_name, precision='fp16', load_device='offload_device', *, folder=None, expected_sha256=None, preserve_rng=False):
    import torch
    if not valid_catalogue_name(model_name) or not model_name.lower().endswith(('.safetensors', '.sft')):
        raise ValueError('Wan CLIP requires a confined safetensors catalogue resource')
    if precision not in ('fp16', 'fp32', 'bf16') or load_device not in ('main_device', 'offload_device'):
        raise ValueError('Invalid original Wan CLIP precision or load device')
    if folder is not None and folder not in ('clip_vision', 'text_encoders'):
        raise ValueError('Wan CLIP resource folder must be clip_vision or text_encoders')
    assets = sdk.current_context().assets
    # Preserve the intended legacy text_encoders fallback without admitting
    # a filesystem path or treating unrelated broker failures as absence.
    if folder is None:
        folder = 'clip_vision'
        try:
            asset = await assets.resolve(folder, model_name)
        except FileNotFoundError:
            folder = 'text_encoders'
            asset = await assets.resolve(folder, model_name)
    else:
        asset = await assets.resolve(folder, model_name)
    size = await assets.size(asset)
    if not 0 < size <= MAX_WEIGHT_BYTES:
        raise ValueError('Wan CLIP exceeds the bounded 3 GiB weight domain')
    digest = await assets.digest(asset)
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError('Wan CLIP resource changed since the producer loaded it')
    state = await assets.load_state_dict(asset)
    if await assets.digest(asset) != digest:
        raise ValueError('Wan CLIP resource changed during weight loading')
    if 'log_scale' not in state:
        raise ValueError("Invalid CLIP model, this node expectes the 'open-clip-xlm-roberta-large-vit-huge-14' model")
    from .secure_wan_clip_math import CLIPModel
    dtype = {'fp16': torch.float16, 'fp32': torch.float32, 'bf16': torch.bfloat16}[precision]
    # The current admitted compute tier is CPU: both named native placements
    # are CPU. Keep the original selection in the recipe for explicit policy.
    device = torch.device('cpu')
    with torch.random.fork_rng(devices=[], enabled=preserve_rng):
        model = CLIPModel(dtype=dtype, device=device, state_dict=state)
    model.model.to(device)
    del state
    recipe = {'format': FORMAT, 'model_name': model_name, 'folder': folder,
              'weights_sha256': digest, 'precision': precision, 'load_device': load_device}
    return model, recipe


async def rebuild_wan_clip(recipe):
    validate_recipe(recipe)
    return await load_wan_clip(recipe['model_name'], recipe['precision'], recipe['load_device'],
        folder=recipe['folder'], expected_sha256=recipe['weights_sha256'], preserve_rng=True)


class LoadWanVideoClipTextEncoder(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw', 'assets', 'models.download')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='LoadWanVideoClipTextEncoder', display_name='WanVideo CLIP Text Encoder Loader', category='WanVideoWrapper',
            description="Loads Wan clip_vision model from 'ComfyUI/models/clip_vision'",
            inputs=[io.Combo.Input('model_name', options=[], tooltip="These models are loaded from 'ComfyUI/models/clip_vision'",
                remote=io.RemoteOptions(route='/models/clip_vision', refresh_button=True, control_after_refresh='first')),
                io.Combo.Input('precision', options=['fp16', 'fp32', 'bf16'], default='fp16'),
                io.Combo.Input('load_device', options=['main_device', 'offload_device'], default='offload_device', optional=True)],
            outputs=[io.Custom('CLIP_VISION').Output(display_name='wan_clip_vision')])

    @classmethod
    def validate_inputs(cls, input_types=None, **kwargs):
        name = kwargs.get('model_name')
        return True if name is None or valid_catalogue_name(name) else 'Wan CLIP requires a confined logical catalogue name'

    @classmethod
    async def execute(cls, model_name, precision, load_device='offload_device'):
        _, recipe = await load_wan_clip(model_name, precision, load_device)
        return io.NodeOutput(recipe)


NODE_CLASS_MAPPINGS = {'LoadWanVideoClipTextEncoder': LoadWanVideoClipTextEncoder}
