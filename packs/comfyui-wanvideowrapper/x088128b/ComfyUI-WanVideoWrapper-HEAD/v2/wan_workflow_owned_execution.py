"""Shared owned NN/progress/device lifetime for preserved child sampler bodies."""
import asyncio
from contextlib import AsyncExitStack
from dataclasses import dataclass
import gc
import os
from threading import Event
import traceback

from .wan_workflow_context import clone_model, clone_options, model_options
from .wan_workflow_model_runtime import materialize_model
from .wan_workflow_sampler_runtime import PipelineState, ExecutionState
from .wan_workflow_sampler_progress import progress_scope
from .wan_workflow_control_contract import bind_control_inputs
from .wan_workflow_lora_contract import LORA_PLAN_KEY, apply_ordered_lora_plan


@dataclass(frozen=True)
class OwnedDevices:
    main_device: object
    offload_device: object

    def validate_cpu_scope(self):
        import torch
        if torch.device(self.main_device).type != 'cpu' or torch.device(self.offload_device).type != 'cpu':
            raise NotImplementedError('This owned lifecycle is CPU-only; no CUDA/device fallback')

    def soft_empty_cache(self):
        self.validate_cpu_scope()
        gc.collect()


def owned_cpu_devices():
    """The current main6 owner policy; never infer an accelerator fallback."""
    import torch
    return OwnedDevices(torch.device('cpu'), torch.device('cpu'))


_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__)) + os.sep


def release_failed_call_frames(tb):
    """Release what the finished frames of a failed owned call keep alive; the error is unchanged.

    tb is the error's traceback as caught by the owner: its first entry is the owner's own, still
    executing frame and every later entry is a finished frame of the failed call. frame.clear() drops
    a frame's locals but not the function object it ran, and a nested function's closure keeps the
    cells of its enclosing scope, so a raise inside a nested sampler closure (the vendored
    predict_with_cfg) would still retain that scope, including the owned NN. For finished frames of
    this package's own code (the vendored sampler math) the cell variables they created are therefore
    emptied first (PEP 667 write-through frame locals, CPython 3.13+); then every finished frame is
    cleared. Frames of other code (torch, diffusers, ...) are only cleared and never have cells
    written, so closures a library keeps beyond the call are untouched. Free variables are never
    written. The error's type, message and traceback lines are unchanged.
    """
    from inspect import CO_OPTIMIZED
    if tb is None:
        return
    for frame, _ in traceback.walk_tb(tb.tb_next):
        code = frame.f_code
        if (code.co_flags & CO_OPTIMIZED and code.co_cellvars
                and os.path.abspath(code.co_filename).startswith(_PACKAGE_DIR)):
            scope = frame.f_locals
            for name in code.co_cellvars:
                if name in scope:
                    scope[name] = None
        try:
            frame.clear()
        except RuntimeError:
            pass


async def _finish_worker(task, cancelled):
    """Retain NN/resource owners until the synchronous worker actually finishes."""
    interruption = None
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError as error:
            cancelled.set()
            interruption = error
        except BaseException:
            if interruption is None:
                raise
            break
    if interruption is not None:
        # Retrieve the worker's error so cancellation never leaves an orphan
        # task exception; preserve the original async cancellation for callers.
        try:
            task.result()
        except BaseException:
            pass
        raise interruption
    return task.result()


async def run_owned_native_sampler(context, model, native_sampler, *, image_embeds,
                                    devices, lora_executor=None,
                                    prior_patch_state=None, **native_kwargs):
    """Call the child's whole original sampler body with actual owned NN state.

    native_sampler is an actual local bound process method supplied by the child.
    Model construction remains the explicit admitted plain1.3B CPU materializer.
    The guarded ordinary sampler selects this route only for an explicit LoRA plan.
    Other original resource families and trained domains remain separate gates.
    """
    import torch
    from .wan_workflow_cpu import interrupt_scope
    from .secure_tensor_nodes import _bound_payload
    if not callable(native_sampler):
        raise TypeError('A genuine local original sampler method is required')
    devices.validate_cpu_scope()
    _bound_payload(image_embeds)
    base = clone_model(model)
    options = clone_options(model_options(model))
    base_options = model_options(base)
    # Only this explicit route consumes control and LoRA metadata. The normal
    # route rejects these fields rather than silently returning unpatched output.
    plan = base_options.pop(LORA_PLAN_KEY, None)
    base_options['transformer_options'].pop('controlnet', None)
    uni3c_input = native_kwargs.get('uni3c_embeds')
    execution = None
    cancelled = Event()
    def check_cancelled():
        if cancelled.is_set():
            raise InterruptedError('Owned sampler execution was cancelled')
    async with AsyncExitStack() as lifetime:
        transformer, _ = await lifetime.enter_async_context(materialize_model(base, context))
        try:
            options, uni3c = await bind_control_inputs(context, lifetime, options,
                                                     uni3c_input, devices=devices)
            patch_state = None
            if plan is not None:
                if lora_executor is None:
                    from .wan_workflow_lora_unmerged import materialize_unmerged_lora_plan
                    patch_state = await materialize_unmerged_lora_plan(context, transformer,
                        plan, devices=devices, prior=prior_patch_state)
                else:
                    patch_state = await apply_ordered_lora_plan(context, transformer, plan,
                        devices=devices, executor=lora_executor, prior=prior_patch_state)
            elif prior_patch_state is not None:
                patch_state = prior_patch_state.fork(transformer)
            pipeline = PipelineState(transformer, {
                'base_dtype': torch.bfloat16, 'weight_dtype': torch.bfloat16,
                'fp8_matmul': False, 'gguf_reader': None, 'control_lora': False,
                'sd': (transformer.state_dict() if patch_state is not None and patch_state.patches and not transformer.patched_linear else None), 'compile_args': None, 'auto_cpu_offload': False,
                'quantization': 'disabled', 'scale_weights': {}, 'lora': None})
            execution = ExecutionState(pipeline, options,
                {} if patch_state is None else patch_state.patches, patch_state)
            call_kwargs = dict(native_kwargs)
            if 'uni3c_embeds' in call_kwargs:
                call_kwargs['uni3c_embeds'] = uni3c
            def run():
                with torch.inference_mode():
                    return native_sampler(model=execution, image_embeds=image_embeds, **call_kwargs)
            with progress_scope(context), interrupt_scope(check_cancelled):
                task = asyncio.create_task(asyncio.to_thread(run))
                return await _finish_worker(task, cancelled)
        except BaseException as error:
            # Finished frames on this error's traceback (the worker's sampler frame and the
            # nested sampler closures it ran) would keep the owned NN alive after this owner
            # exits. Release their scopes; the error itself (type, message, traceback lines)
            # is re-raised unchanged.
            release_failed_call_frames(error.__traceback__)
            raise
        finally:
            execution = transformer = pipeline = None
            # These are cloned private option containers. The graph's original
            # recipes/tensors and any parent's ownership record are unchanged.
            control = options.get('transformer_options', {}).get('controlnet')
            if type(control) is dict:
                control.pop('controlnet', None)
            if 'uni3c' in locals() and type(uni3c) is dict:
                uni3c.pop('controlnet', None)
            gc.collect()


async def run_diffusion_forcing(context, model, native_sampler_type, *, image_embeds,
                                devices, release_owned_conditioning, **native_kwargs):
    """Use the child's exact required-constructor binding, with no fake release.

    release_owned_conditioning is the real async owner operation, such as aclose
    on the separate stack actually owning live text/vision conditioning models.
    The base NN/control stack must not be passed here. No default/no-op, global
    model unload or host model capability is supplied. Caller ownership and the
    original release phase still need actual native/Guest lifetime qualification.
    """
    if not callable(release_owned_conditioning):
        raise TypeError('A real async owned-conditioning release operation is required')
    loop = asyncio.get_running_loop()
    def release_from_worker():
        return asyncio.run_coroutine_threadsafe(release_owned_conditioning(), loop).result()
    original = native_sampler_type(release_owned_conditioning=release_from_worker)
    return await run_owned_native_sampler(context, model, original.process,
        image_embeds=image_embeds, devices=devices, **native_kwargs)
