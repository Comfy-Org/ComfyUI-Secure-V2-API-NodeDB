"""Concrete local consumer bindings, pending native execution qualification.

These helpers are intentionally not node registrations. LoRA preparation now interleaves actual pinned-file validation and real NN
key-map patch parsing before proceeding to each next descriptor. Forcing must receive
the actual resource owner from the shared consumer, never an invented release.
"""
from .wan_lora_resource_preparation import prepare_lora_resources
from .wan_workflow_lora_contract import adopt_prepared_lora_resources
from .wan_forcing_arguments import forcing_arguments


async def prepare_set_loras_for_owned_execution(context, model, lora=None):
    """Read and validate each actual descriptor before advancing to the next."""
    from .wan_workflow_owned_execution import owned_cpu_devices
    from .wan_workflow_sequential_set_loras import prepare_set_loras_sequential
    return await prepare_set_loras_sequential(context, model, lora, devices=owned_cpu_devices())


async def run_forcing_with_owned_lifecycle(
    context, model, text_embeds, image_embeds, shift, fps, steps,
    addnoise_condition, cfg, seed, scheduler, force_offload=True, samples=None,
    prefix_samples=None, denoise_strength=1.0, slg_args=None,
    rope_function='default', cache_args=None, teacache_args=None,
    experimental_args=None, unianimate_poses=None, *, devices,
    release_owned_conditioning,
):
    """Run the complete body with the owner's real devices and phase callback.

    The owner must unwrap public references and retain its actual conditioning
    lifetime before this call. It also owns final V2 publication of the original
    LATENT result. This function does not manufacture or discard that lifetime.
    """
    from .wan_forcing_math import WanVideoDiffusionForcingSampler
    from .wan_workflow_owned_execution import run_diffusion_forcing

    arguments = forcing_arguments(
        model, text_embeds, image_embeds, shift, fps, steps, addnoise_condition,
        cfg, seed, scheduler, force_offload, samples, prefix_samples,
        denoise_strength, slg_args, rope_function, cache_args, teacache_args,
        experimental_args, unianimate_poses,
    )
    return await run_diffusion_forcing(
        context, native_sampler_type=WanVideoDiffusionForcingSampler,
        **arguments, devices=devices,
        release_owned_conditioning=release_owned_conditioning,
    )
