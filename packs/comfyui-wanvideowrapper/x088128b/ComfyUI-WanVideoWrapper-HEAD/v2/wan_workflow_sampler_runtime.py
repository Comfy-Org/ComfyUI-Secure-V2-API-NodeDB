"""Owned per-call sampler state; no transported or fabricated Core patcher."""
import asyncio
from dataclasses import dataclass

from .wan_workflow_context import clone_options
from .wan_workflow_model_runtime import materialize_model
from .wan_workflow_sampler_progress import progress_scope
from .wan_workflow_scheduler_runtime import FORMAT as SCHEDULER_FORMAT, restore_scheduler


@dataclass
class PipelineState:
    """Actual transformer plus its pack-owned execution settings."""
    diffusion_model: object
    values: dict

    def __getitem__(self, key):
        return self.values[key]

    def __setitem__(self, key, value):
        self.values[key] = value


@dataclass
class ExecutionState:
    model: PipelineState
    model_options: dict
    patches: dict
    patch_ownership: object = None

    def unpatch_model(self, device_to=None, unpatch_weights=True):
        """Restore the real plain-NN backups from this explicit owned lifetime."""
        if not unpatch_weights:
            return
        from .wan_workflow_lora_contract import OwnedPatchState
        from .wan_workflow_lora_runtime import restore_owned_backups
        owner = self.patch_ownership
        if not isinstance(owner, OwnedPatchState) or owner.transformer is not self.model.diffusion_model or owner.patches is not self.patches:
            raise ValueError('Unpatch requires backup ownership for the same actual NN')
        restore_owned_backups(owner, device_to)


def load_weights(transformer, sd=None, weight_dtype=None, base_dtype=None,
                 transformer_load_device=None, block_swap_args=None, gguf=False,
                 reader=None, patcher=None, compile_args=None):
    # The normal owned lifecycle supplies already placed actual trained tensors.
    # Keep the genuine full sampler's optional deferred-load call unambiguous.
    if gguf or block_swap_args is not None or compile_args is not None:
        raise NotImplementedError('Advanced deferred weight placement is outside this staged workflow')
    if sd is None:
        raise ValueError('Deferred weight placement requires actual tensors')
    from .wan_workflow_model_runtime import load_plain_weights
    load_plain_weights(transformer, sd, base_dtype)


def resolve_cache_placement(cache_args):
    """Resolve a V2 cache-settings placement label to this owned execution's devices.

    The registered cache producers carry the original closed UI label ('main_device' or 'offload_device')
    instead of a host device. The original producer resolved the label itself (main_device ->
    mm.get_torch_device(), offload_device -> mm.unet_offload_device()); in this CPU-only owned scope both
    labels resolve to the owned CPU devices. All other cache settings pass through unchanged.
    """
    if type(cache_args) is not dict or cache_args.get('cache_device') not in ('main_device', 'offload_device'):
        raise ValueError('Wan cache placement must be main_device or offload_device')
    from .wan_workflow_owned_execution import owned_cpu_devices
    devices = owned_cpu_devices()
    device = devices.main_device if cache_args['cache_device'] == 'main_device' else devices.offload_device
    return dict(cache_args, cache_device=device)


async def sample_workflow(context, model, image_embeds, **kwargs):
    import torch
    from .wan_workflow_math.nodes_sampler import WanVideoSampler
    if type(image_embeds) is not dict or set(image_embeds) != {'target_shape', 'num_frames', 'control_embeds'}:
        raise NotImplementedError('First staged trained workflow requires plain empty T2V conditioning')
    if image_embeds['control_embeds'] is not None:
        raise NotImplementedError('Control embeds await their reviewed execution slice')
    unsupported = ('feta_args',
                   'experimental_args',
                   'unianimate_poses', 'fantasytalking_embeds', 'uni3c_embeds',
                   'multitalk_embeds', 'freeinit_args')
    if any(kwargs.get(key) is not None for key in unsupported):
        raise NotImplementedError('Advanced sampling inputs await their reviewed execution slices')
    if kwargs.get('batched_cfg', False):
        raise NotImplementedError('Batched CFG awaits its reviewed execution slice')
    for key in ('cache_args', 'teacache_args'):
        if kwargs.get(key) is not None:
            kwargs = dict(kwargs, **{key: resolve_cache_placement(kwargs[key])})
    scheduler = kwargs['scheduler']
    if type(scheduler) is dict:
        if scheduler.get('format') != SCHEDULER_FORMAT:
            raise ValueError('Expected the shared owned scheduler recipe')
        kwargs = dict(kwargs, scheduler=restore_scheduler(scheduler))
    # Like the original (nodes_sampler.py: steps = len(timesteps)), a scheduler dict defines the step count;
    # WanVideoSamplerv2 passes steps=None and relies on it.
    effective_steps = (len(kwargs['scheduler']['timesteps']) if type(kwargs['scheduler']) is dict
                       else kwargs.get('steps'))
    if type(effective_steps) is not int or effective_steps < 1:
        raise ValueError('Wan sampling requires a positive integer step count')
    from .wan_workflow_context import model_options
    options = model_options(model)
    if options.get('lora_resource_plan') is not None:
        if options.get('transformer_options', {}).get('controlnet') is not None:
            raise NotImplementedError('Combined control and unmerged LoRA needs its separate trained execution slice')
        from .wan_workflow_owned_execution import run_owned_native_sampler, owned_cpu_devices
        return await run_owned_native_sampler(context, model, WanVideoSampler().process,
            image_embeds=image_embeds, devices=owned_cpu_devices(), **kwargs)
    async with materialize_model(model, context) as (transformer, options):
        pipeline = PipelineState(transformer, {
            'base_dtype': torch.bfloat16, 'weight_dtype': torch.bfloat16,
            'fp8_matmul': False, 'gguf_reader': None, 'control_lora': False,
            'sd': None, 'compile_args': None, 'auto_cpu_offload': False,
            'quantization': 'disabled', 'scale_weights': {}, 'lora': None})
        execution = ExecutionState(pipeline, {'transformer_options': clone_options(options)}, {})
        def run():
            with torch.inference_mode():
                return WanVideoSampler().process(model=execution, image_embeds=image_embeds, **kwargs)
        try:
            with progress_scope(context):
                # The event loop must continue serving actual SDK progress requests.
                # Do not move the coroutine loop into this synchronous model call.
                return await asyncio.to_thread(run)
        except BaseException as error:
            # Finished frames on this error's traceback (the worker's sampler frame and the
            # nested sampler closures it ran) would keep the owned NN alive after this owner
            # exits. Release their scopes with the shared owned-execution helper (imported
            # here because that module imports this one); the error itself (type, message,
            # traceback lines) is re-raised unchanged.
            from .wan_workflow_owned_execution import release_failed_call_frames
            release_failed_call_frames(error.__traceback__)
            raise
        finally:
            execution = pipeline = transformer = None
