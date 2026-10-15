"""Original WanVideoDiffusionForcingSampler bound to the shared owned executor.

Public interface: the 20 original process arguments and defaults (teacache_args
stays a hidden method argument) and the single native LATENT output. The model
recipe is materialized, sampled and released by the shared owned CPU lifecycle;
the original force_offload branch offloads that node-owned transformer.

MERVYN m_dfc57819ea: the original pre-sampling global unload
(mm.unload_all_models / soft_empty_cache) evicts other workloads' models and is
a refused technique; the host owns memory policy. The converted process has no
release phase there and this node adds no SDK call.
"""
from comfy_api.latest import io, sdk

from .wan_pending_control_schemas import diffusion_forcing_schema


async def _refused_global_unload():
    # The unchanged shared lifecycle signature still requires a callable. The
    # converted process never awaits it; fail loudly rather than fake a release.
    raise RuntimeError('Pre-sampling global unload is refused for the converted '
                       'forcing sampler (MERVYN m_dfc57819ea)')


class WanVideoDiffusionForcingSampler(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'assets')

    @classmethod
    def define_schema(cls):
        return diffusion_forcing_schema()

    @classmethod
    async def execute(cls, model, text_embeds, image_embeds, shift, fps, steps,
                      addnoise_condition, cfg, seed, scheduler, force_offload=True,
                      samples=None, prefix_samples=None, denoise_strength=1.0,
                      slg_args=None, rope_function='default', cache_args=None,
                      teacache_args=None, experimental_args=None, unianimate_poses=None):
        from .wan_control_consumer_adapters import run_forcing_with_owned_lifecycle
        from .wan_workflow_owned_execution import owned_cpu_devices
        result = await run_forcing_with_owned_lifecycle(
            sdk.current_context(), model=model, text_embeds=text_embeds,
            image_embeds=image_embeds, shift=shift, fps=fps, steps=steps,
            addnoise_condition=addnoise_condition, cfg=cfg, seed=seed,
            scheduler=scheduler, force_offload=force_offload, samples=samples,
            prefix_samples=prefix_samples, denoise_strength=denoise_strength,
            slg_args=slg_args, rope_function=rope_function, cache_args=cache_args,
            teacache_args=teacache_args, experimental_args=experimental_args,
            unianimate_poses=unianimate_poses, devices=owned_cpu_devices(),
            release_owned_conditioning=_refused_global_unload)
        return io.NodeOutput(*result)


NODE_CLASS_MAPPINGS = {'WanVideoDiffusionForcingSampler': WanVideoDiffusionForcingSampler}
