"""Full Wan VAE resource loader and confined, digest-bound reconstruction."""
import re
from comfy_api.latest import io, sdk
from ._wan_catalogue import valid_catalogue_name
from .secure_tensor_nodes import _bound_payload

RECIPE_KEYS = {'format', 'model_name', 'weights_sha256', 'precision', 'compile_args', 'use_cpu_cache', 'verbose'}


async def load_full_vae(model_name, precision='bf16', compile_args=None, use_cpu_cache=False, verbose=False, expected_sha256=None, preserve_rng=False):
    import torch
    from .wanvideo.wan_video_vae import WanVideoVAE, WanVideoVAE38
    if not valid_catalogue_name(model_name):
        raise ValueError('Wan VAE requires a confined catalogue name')
    if not model_name.lower().endswith(('.safetensors', '.sft')):
        raise ValueError('Full Wan VAE currently requires a safetensors resource')
    if precision not in ('fp16', 'fp32', 'bf16') or type(use_cpu_cache) is not bool or type(verbose) is not bool:
        raise ValueError('Invalid Wan VAE precision/cache/verbosity')
    if compile_args is not None:
        _bound_payload(compile_args)
        if not isinstance(compile_args, dict):
            raise ValueError('Wan compile settings must be a plain dictionary')
    assets = sdk.current_context().assets
    asset = await assets.resolve('vae', model_name)
    size = await assets.size(asset)
    if not 0 < size <= 512 * 1024 * 1024:
        raise ValueError('Wan VAE exceeds the bounded 512 MiB weight domain')
    digest = await assets.digest(asset)
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError('Selected full Wan VAE resource changed')
    # Public SDK model-weight path: the broker admits the exact asset and sends
    # lossless tensor copies through its negotiated buffer channel. All model
    # construction, strict state loading and numerical VAE work remain here.
    state = await assets.load_state_dict(asset)
    if await assets.digest(asset) != digest:
        raise ValueError('Full Wan VAE resource changed during weight loading')
    if not any(key.startswith('model.') for key in state):
        state = {'model.' + key: value for key, value in state.items()}
    dim = state['model.decoder.conv1.bias'].shape[0]
    pruning_rate = 0.75 if dim == 96 else 0.0
    channels = state['model.conv2.weight'].shape[0]
    dtype = {'fp16': torch.float16, 'fp32': torch.float32, 'bf16': torch.bfloat16}[precision]
    # Reconstructing a resource at a graph boundary must not consume the noise
    # stream again. The producer's first construction keeps native RNG effects.
    with torch.random.fork_rng(devices=[], enabled=preserve_rng):
        if channels == 16:
            model = WanVideoVAE(dtype=dtype, pruning_rate=pruning_rate, cpu_cache=use_cpu_cache, verbose=verbose)
        elif channels == 48:
            model = WanVideoVAE38(dtype=dtype, pruning_rate=pruning_rate, cpu_cache=use_cpu_cache, verbose=verbose)
        else:
            raise ValueError('Full Wan VAE requires native 16 or 48 latent channels')
        model.load_state_dict(state, strict=True)
    del state
    model.eval()
    model.to(device='cpu', dtype=dtype)
    if compile_args is not None:
        model.model.decoder = torch.compile(model.model.decoder, fullgraph=compile_args['fullgraph'], dynamic=compile_args['dynamic'], backend=compile_args['backend'], mode=compile_args['mode'])
    recipe = {'format': 'wan-full-vae-recipe-v1', 'model_name': model_name, 'weights_sha256': digest,
              'precision': precision, 'compile_args': compile_args, 'use_cpu_cache': use_cpu_cache, 'verbose': verbose}
    return model, recipe


async def rebuild_full_vae(recipe):
    if not isinstance(recipe, dict) or set(recipe) != RECIPE_KEYS or recipe.get('format') != 'wan-full-vae-recipe-v1':
        raise ValueError('Invalid full Wan VAE recipe')
    digest = recipe['weights_sha256']
    if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
        raise ValueError('Full Wan VAE requires an exact resource digest')
    return await load_full_vae(recipe['model_name'], recipe['precision'], recipe['compile_args'], recipe['use_cpu_cache'], recipe['verbose'], digest, preserve_rng=True)


async def full_decode(vae, latent, samples, enable_vae_tiling, tile_x, tile_y, tile_stride_x, tile_stride_y, normalization):
    import torch
    model, _ = await rebuild_full_vae(vae)
    if latent.shape[1] != model.z_dim:
        raise ValueError('Wan latent channels do not match the selected full VAE')
    latents = latent.clone().to(device='cpu', dtype=model.dtype)
    if samples.get('has_ref', False):
        latents = latents[:, :, 1:]
    if samples.get('drop_last', False):
        latents = latents[:, :, :-1]
    if latents.shape[2] == 0:
        raise ValueError('Wan reference/drop flags leave no latent frames')
    end_image = samples.get('end_image', None)
    with torch.inference_mode():
        images = model.decode(latents, device=torch.device('cpu'), end_=(end_image is not None), tiled=enable_vae_tiling,
                              tile_size=(tile_x//8, tile_y//8), tile_stride=(tile_stride_x//8, tile_stride_y//8))[0]
        images = images.cpu().float()
        if normalization != 'none':
            if normalization == 'minmax':
                images.sub_(images.min()).div_(images.max() - images.min())
            else:
                images.clamp_(-1.0, 1.0)
                images.add_(1.0).div_(2.0)
        if samples.get('looped', False):
            temp_latents = torch.cat([latents[:, :, -3:]] + [latents[:, :, :2]], dim=2)
            temp_images = model.decode(temp_latents, device=torch.device('cpu'), end_=(end_image is not None), tiled=enable_vae_tiling,
                                       tile_size=(tile_x//model.upsampling_factor, tile_y//model.upsampling_factor),
                                       tile_stride=(tile_stride_x//model.upsampling_factor, tile_stride_y//model.upsampling_factor))[0]
            temp_images = temp_images.cpu().float()
            temp_images = (temp_images - temp_images.min()) / (temp_images.max() - temp_images.min())
            images = torch.cat([temp_images[:, 9:].to(images), images[:, 5:]], dim=1)
        if end_image is not None:
            images = images[:, 0:-1]
        images.clamp_(0.0, 1.0)
    return io.NodeOutput(images.permute(1, 2, 3, 0))


class WanVideoVAELoader(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw', 'assets', 'models.download')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoVAELoader', display_name='WanVideo VAE Loader', category='WanVideoWrapper',
                         description="Loads Wan VAE model from 'ComfyUI/models/vae'",
                         inputs=[io.Combo.Input('model_name', options=[], tooltip="These models are loaded from 'ComfyUI/models/vae'",
                                                remote=io.RemoteOptions(route='/models/vae', refresh_button=True, control_after_refresh='first')),
                                 io.Combo.Input('precision', options=['fp16', 'fp32', 'bf16'], optional=True, default='bf16'),
                                 io.Custom('WANCOMPILEARGS').Input('compile_args', optional=True),
                                 io.Boolean.Input('use_cpu_cache', optional=True, default=False, tooltip='Reduces VRAM usage, but slows the VAE down a lot'),
                                 io.Boolean.Input('verbose', optional=True, default=False, tooltip='Enables memory usage logging when using the model')],
                         outputs=[io.Custom('WANVAE').Output(display_name='vae')])

    @classmethod
    def validate_inputs(cls, input_types=None, **kwargs):
        name = kwargs.get('model_name')
        return True if name is None or valid_catalogue_name(name) else 'Wan VAE requires a confined logical catalogue name'

    @classmethod
    async def execute(cls, model_name, precision='bf16', compile_args=None, use_cpu_cache=False, verbose=False):
        _, recipe = await load_full_vae(model_name, precision, compile_args, use_cpu_cache, verbose)
        return io.NodeOutput(recipe)


NODE_CLASS_MAPPINGS = {'WanVideoVAELoader': WanVideoVAELoader}
