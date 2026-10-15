"""Pack-owned typed boundaries for the original Z-Image sampler compute."""
from comfy_api.latest import sdk


async def sampler_from_name(name):
    return await sdk.SamplerRef.named(name)


async def keep_masked_area(samples, original_samples, original_mask):
    destination = await sdk.LatentRef.from_value({'samples': original_samples})
    source = await sdk.LatentRef.from_value({'samples': samples})
    mask = await sdk.MaskRef._from_raw(original_mask)
    merged = await destination.composite(source, mask=mask)
    return (await merged.value())['samples']


class ProgressPreview:
    """Native hierarchy arithmetic over the broker-owned progress channel.

    This owns only numeric progress. Preview pixels remain engine-owned.
    """
    def __init__(self, steps, parent):
        self.parent = parent[0]
        self.range_min = int(parent[1])
        self.range_max = int(parent[2])
        self.total = steps

    @classmethod
    def from_context(cls, steps=100):
        # Callbacks arrive on another task. Capture the published domain while
        # execute has its SDK binding, rather than looking it up in that task.
        return cls(steps, parent=(_ProgressRoot(steps, sdk.ctx().progress), 0, steps))

    async def update(self, step, total_steps=None):
        self.total = total_steps or self.total
        self.current = min(step, self.total)
        progress_level = float(self.current) / self.total if self.total > 0 else 1.0
        if self.parent:
            parent_value = self.range_min + (progress_level * (self.range_max - self.range_min))
            await self.parent.update(int(parent_value), None)


class _ProgressRoot:
    def __init__(self, total, progress):
        self.total = total
        self.progress = progress

    async def update(self, step, total_steps=None):
        # Native latent_preview.prepare_callback publishes completed steps.
        await self.progress.update(step + 1, total_steps or self.total)


async def normalize_latents(model, samples):
    value = await sdk.LatentRef.from_value({"samples": samples})
    corrected = await model.fix_empty_latent_channels(value)
    return (await corrected.value())["samples"]


async def sample_custom(model, noise, cfg, sampler, sigmas, positive, negative,
                        samples, *, noise_mask=None, callback=None, seed=0):
    value = {"samples": samples}
    if noise_mask is not None:
        value["noise_mask"] = noise_mask
    latent = await sdk.LatentRef.from_value(value)
    noise_ref = await sdk.TensorRef._from_raw(noise)
    sigmas_ref = await sdk.TensorRef._from_raw(sigmas)
    async def on_step(*, step, total):
        if callback is not None:
            await callback.update(step, total)
    result = await sdk.ctx().sample(
        latent, max(1, len(sigmas) - 1), model=model,
        positive=positive, negative=negative, cfg=cfg, seed=seed,
        sampler=sampler, sigmas=sigmas_ref, noise=noise_ref,
        on_step=on_step, fix_empty_latent=False)
    return (await result.value())["samples"]
