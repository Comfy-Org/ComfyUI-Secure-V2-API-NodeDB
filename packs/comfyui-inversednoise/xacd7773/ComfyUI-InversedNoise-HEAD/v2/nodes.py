"""Pinned inversion/noise math; public refs retain host-owned LATENT extras."""
import math
import torch
from comfy_api.latest import io, sdk

MAX_INPUT_BYTES = 32 * 1024 * 1024
MAX_WORK_BYTES = 192 * 1024 * 1024
MAX_AXES = 32


def tensor_budget(value):
    if not isinstance(value, torch.Tensor) or value.layout != torch.strided or value.is_nested:
        raise ValueError('dense nonnested tensor required')
    if value.ndim > MAX_AXES or value.numel() * value.element_size() > MAX_INPUT_BYTES:
        raise ValueError('input rank/byte budget exceeded')
    return value.numel() * value.element_size()


def work_budget(inputs, shape, itemsize, temporaries):
    projected = math.prod(shape) * itemsize
    if projected > MAX_INPUT_BYTES or sum(tensor_budget(t) for t in inputs) + temporaries * projected > MAX_WORK_BYTES:
        raise ValueError('projected output/aggregate workspace budget exceeded')


def local_generator():
    # Execution-local entropy, not a user seed or ambient Torch RNG mutation.
    generator = torch.Generator(device='cpu')
    generator.seed()
    return generator


async def inverse_loop(broker, x, sigmas):
    tensor_budget(x)
    work_budget([x], x.shape, x.element_size(), 6)
    for i in range(1, len(sigmas)):
        sigma_in = sigmas[i-1]
        sigma_t = sigmas[i] if i == 1 else sigma_in
        # The broker expands this scalar to the source's x-dtype batch vector.
        denoised, _ = await broker.denoise(x, sigma_t)
        if i == 1:
            d = (x - denoised) / (2 * sigmas[i])
        else:
            d = (x - denoised) / sigmas[i-1]
        dt = sigmas[i] - sigmas[i-1]
        x = x + d * dt
        await broker.preview(i, x, sigmas[i], sigmas[i], denoised,
            value_phase='after_update', index_base=1, sigma_format='tensor')
    return x / sigmas[-1]


class SamplerInversedEulerNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('closures',)
    FUNCTION = 'execute'

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='SamplerInversedEulerNode', display_name='Inversed Euler Sampler',
            category='sampling/custom_sampling/samplers', inputs=[], outputs=[io.Custom('SAMPLER').Output()])

    @classmethod
    async def execute(cls):
        closure = await sdk.ctx().closures.retain('custom_sampler', inverse_loop)
        return io.NodeOutput(await closure.as_sampler(sigmas_direction='ascending'))


class MixNoiseNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)
    FUNCTION = 'execute'

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='MixNoiseNode', display_name='Mix Noise with Latent', category='noise',
            inputs=[io.Latent.Input('latent'), io.Float.Input('randomness', default=.1, min=0., max=1., step=.01, round=False)],
            outputs=[io.Latent.Output()])

    @classmethod
    async def execute(cls, latent, randomness):
        if type(randomness) not in (int, float) or not math.isfinite(randomness) or not 0 <= randomness <= 1:
            raise ValueError('randomness must be finite in [0,1]')
        latent_image = await (await latent.samples()).raw()
        tensor_budget(latent_image)
        work_budget([latent_image], latent_image.shape, max(latent_image.element_size(), 4), 6)
        rand_noise = torch.empty_like(latent_image, memory_format=torch.preserve_format)
        rand_noise.normal_(generator=local_generator())
        combined_noise = ((1 - randomness) * latent_image + randomness * rand_noise) / ((randomness**2 + (1-randomness)**2) ** 0.5)
        return io.NodeOutput(await latent.with_samples(await sdk.TensorRef.from_value(combined_noise)))


class CombineNoiseLatentNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)
    FUNCTION = 'execute'

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CombineNoiseLatentNode', display_name='Combine Latent Noise', category='noise',
            inputs=[io.Latent.Input('latent'), io.Latent.Input('noise'), io.Custom('SIGMAS').Input('sigmas')],
            outputs=[io.Latent.Output(display_name='noise')])

    @classmethod
    async def execute(cls, latent, noise, sigmas):
        latent_image = await (await latent.samples()).raw()
        noise_image = await (await noise.samples()).raw()
        sigma_values = await (await sdk.TensorRef.from_ref(sigmas)).raw()
        for tensor in (latent_image, noise_image, sigma_values):
            tensor_budget(tensor)
        sigma = sigma_values[0]
        shape = torch.broadcast_shapes(latent_image.shape, noise_image.shape, sigma.shape)
        # Conservative16-byte reserve covers numeric promotion including complex128.
        work_budget([latent_image, noise_image, sigma_values], shape, 16, 3)
        noise_dt = noise_image - (latent_image / sigma)
        return io.NodeOutput(await noise.with_samples(await sdk.TensorRef.from_value(noise_dt)))
