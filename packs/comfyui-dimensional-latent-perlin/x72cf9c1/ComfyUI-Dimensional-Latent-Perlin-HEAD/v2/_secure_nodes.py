"""One bounded pack-side Perlin algorithm with opaque model metadata projection."""
import math
import torch
from comfy_api.latest import io, sdk
from .dimensional_latent_perlin import NoisyLatentPerlinD as Algorithm

MAX_OUTPUT_BYTES = 64 * 1024 * 1024
MAX_PROJECTED_BYTES = 128 * 1024 * 1024
MAX_DRAW_WORK = 16_777_216


class ShapeOnlySamples:
    """Source accesses only this exact public shape, never input tensor values."""
    __slots__ = ('shape',)

    def __init__(self, shape):
        self.shape = tuple(shape)


def preflight(seed, width, height, batch_size, detail_level, downsample_factor,
              target_shape=None, latent_channels=None):
    # Exact source UI ranges, plus explicit resource bounds beyond that schema.
    for name, value, low, high in (
        ('seed', seed, 0, 2**64-1), ('width', width, 8, 8192),
        ('height', height, 8, 8192), ('batch_size', batch_size, 1, 64),
        ('downsample_factor', downsample_factor, 1, 64),
    ):
        if type(value) is not int or not low <= value <= high:
            raise ValueError(name + ' bounded integer required')
    if type(detail_level) not in (int, float) or not math.isfinite(detail_level) or not -1 <= detail_level <= 1:
        raise ValueError('bounded finite detail_level required')
    size = height // downsample_factor, width // downsample_factor
    if target_shape is not None:
        target = tuple(target_shape)
        if len(target) not in (4, 5):
            raise ValueError('admitted LATENT must have four or five dimensions')
        if any(type(v) is not int or v < 0 for v in target):
            raise TypeError('LATENT sample shape requires nonnegative integer dimensions')
    else:
        target = None
    channels = latent_channels if latent_channels is not None else (target[1] if target is not None else 4)
    if type(channels) is not int or not 0 <= channels <= 4096:
        raise ValueError('bounded latent channel count required')
    if target is not None and target[1] > 4096:
        raise ValueError('bounded target latent channel count required')
    plane = math.prod(size)
    output = batch_size * channels * plane * 4  # Source explicit float32 output.
    repeated = output
    if target is not None and target[1] > channels and channels:
        # Native repeat owns rounded-up channels even after narrow/slicing.
        repeated = output * math.ceil(target[1] / channels)
    floating_size = {torch.float32: 4, torch.float64: 8,
                     torch.float16: 2, torch.bfloat16: 2}[torch.get_default_dtype()]
    # Grid, tile_grads, four dot fields, fade powers, nested lerps, transform:
    # 64 simultaneous floating planes is a conservative local estimate.
    # Fixed allowance includes gradients/range buffers and scalar temporaries.
    per_plane = 64 * floating_size * plane + 65_536
    # No input buffer is materialized: describe() projects only small scalars.
    projected = output + 3 * repeated + per_plane
    if output > MAX_OUTPUT_BYTES or repeated > MAX_OUTPUT_BYTES or projected > MAX_PROJECTED_BYTES:
        raise ValueError('Perlin projected allocation/transport ownership budget exceeded')
    if batch_size * channels * max(plane, 1) > MAX_DRAW_WORK:
        raise ValueError('Perlin cumulative draw/work budget exceeded')
    return {'output_bytes': output, 'repeat_backing_bytes': repeated,
            'input_snapshot_bytes': 0, 'projected_bytes': projected,
            'channels': channels, 'spatial': size}


class NoisyLatentPerlinD(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw', 'inspect')

    @classmethod
    def define_schema(cls):
        original = Algorithm.INPUT_TYPES()
        inputs = []
        for name, spec in original['required'].items():
            kind = io.Float if spec[0] == 'FLOAT' else io.Int
            inputs.append(kind.Input(name, **spec[1]))
        inputs.extend([io.Latent.Input('latent_image', optional=True),
                       io.Model.Input('model', optional=True)])
        return io.Schema(node_id='NoisyLatentPerlinD', display_name='Noisy Latent Perlin Dimensional',
            category='latent/noise', inputs=inputs, outputs=[io.Latent.Output()])

    @classmethod
    async def execute(cls, seed, width, height, batch_size, detail_level,
                      downsample_factor, latent_image=None, model=None):
        if model is not None and not isinstance(model, sdk.ModelRef):
            raise TypeError('MODEL requires an opaque public ModelRef')
        channels = None if model is None else await model.latent_channels()
        target = None
        if latent_image is not None:
            if not isinstance(latent_image, sdk.LatentRef):
                raise TypeError('LATENT requires an opaque public LatentRef')
            target = (await latent_image.describe())['shape']
            if target is None:
                raise TypeError('LATENT samples must have an admitted tensor shape')
        preflight(seed, width, height, batch_size, detail_level, downsample_factor,
                  target, channels)
        shape_only = None if target is None else {'samples': ShapeOnlySamples(target)}
        result = Algorithm().generate_noise(seed, width, height, batch_size, detail_level,
                    downsample_factor, latent_image=shape_only, latent_channels=channels)
        return io.NodeOutput(await sdk.LatentRef.from_value(result[0]))
