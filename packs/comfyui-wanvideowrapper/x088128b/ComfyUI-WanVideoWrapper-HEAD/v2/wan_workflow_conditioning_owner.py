"""Actual T5 conditioning lifetime bound to the original forcing release phase.

Internal composition only: no schema/input or transported callback is invented.
The existing public text node still publishes tensors after its own encoder is
closed. This path explicitly constructs and retains the actual owned encoder;
its release callback closes the stack that really owns that encoder and weight
file. Diffusion/control/LoRA owners belong to a separate sampler lifetime.
"""
import asyncio
from contextlib import AsyncExitStack
import gc
from threading import Event

from .wan_workflow_text_runtime import _encoder, _encode_batch, positive_prompts, log
from .wan_workflow_owned_execution import _finish_worker


class OwnedT5Conditioning:
    """One real encoder lease; never transported across a node boundary."""
    def __init__(self, context, t5, *, force_offload=True):
        self._context = context
        self._recipe = t5
        self._force_offload = force_offload
        self._lifetime = AsyncExitStack()
        self._encoder = None
        self._target = None
        self.released_at_native_phase = False

    async def __aenter__(self):
        # The real existing loader validates the pinned resource, actually reads
        # its weights and builds/places T5. No fake encoder or owner is supplied.
        self._encoder, self._target = await self._lifetime.enter_async_context(
            _encoder(self._recipe, self._context, self._force_offload, 'cpu'))
        return self

    async def __aexit__(self, exc_type, exc, tb):
        # Always clean on pre-phase native exceptions and cancellation, too.
        # _finish_worker retains this owner until every real worker is done.
        self._encoder = self._target = None
        try:
            return await self._lifetime.__aexit__(exc_type, exc, tb)
        finally:
            gc.collect()

    async def _batch(self, prompts):
        if self._encoder is None or self.released_at_native_phase:
            raise RuntimeError('Actual conditioning encoder has already been released')
        cancelled = Event()
        task = asyncio.create_task(asyncio.to_thread(
            _encode_batch, self._encoder, prompts, self._target))
        return await _finish_worker(task, cancelled)

    async def encode(self, positive_prompt, negative_prompt):
        if not isinstance(positive_prompt, str) or not isinstance(negative_prompt, str):
            raise TypeError('Wan text prompts must be text')
        prompts, all_weights = positive_prompts(positive_prompt)
        positive = await self._batch(prompts)
        for i, weights in enumerate(all_weights):
            for text, weight in weights.items():
                log.info('Applying weight %s to prompt: %s', weight, text)
                if len(weights) > 0:
                    positive[i] = positive[i] * weight
        negative = await self._batch([negative_prompt])
        return {'prompt_embeds': positive, 'negative_prompt_embeds': negative,
                'echoshot': '[1]' in positive_prompt}

    async def release_from_native_phase(self):
        """Close the live actual encoder/file owner exactly when native asks."""
        if self._encoder is None or self.released_at_native_phase:
            raise RuntimeError('Native release requires an unreleased actual conditioning encoder')
        # No local reference to the live encoder escapes this object. The
        # loader generator still owns it until its real finally runs below.
        self._encoder = self._target = None
        await self._lifetime.aclose()
        self.released_at_native_phase = True
        gc.collect()


async def encode_and_run_diffusion_forcing(
    context, model, t5, positive_prompt, negative_prompt, image_embeds,
    shift, fps, steps, addnoise_condition, cfg, seed, scheduler, *, devices,
    force_offload=True, t5_force_offload=True, **native_optional,
):
    """Concrete local source callsite with actual conditioning resource owners.

    This internal function is not a replacement public forcing schema. It has
    a distinct resource peak: T5 remains live while the actual diffusion model
    is materialized, until the original sampler release phase. Exact resources,
    memory/temp/storage admission and learned/native/Guest lifetime validation
    are required before execution. Existing frozen workflow is not rerun.
    """
    from .wan_control_consumer_adapters import run_forcing_with_owned_lifecycle
    devices.validate_cpu_scope()
    if not isinstance(positive_prompt, str) or not isinstance(negative_prompt, str):
        raise TypeError('Wan text prompts must be text')
    async with OwnedT5Conditioning(context, t5, force_offload=t5_force_offload) as conditioning:
        text_embeds = await conditioning.encode(positive_prompt, negative_prompt)
        result = await run_forcing_with_owned_lifecycle(
            context, model, text_embeds, image_embeds, shift, fps, steps,
            addnoise_condition, cfg, seed, scheduler, force_offload,
            devices=devices,
            release_owned_conditioning=conditioning.release_from_native_phase,
            **native_optional,
        )
        if not conditioning.released_at_native_phase:
            raise RuntimeError('Native forcing returned without releasing its real conditioning owner')
        return result
