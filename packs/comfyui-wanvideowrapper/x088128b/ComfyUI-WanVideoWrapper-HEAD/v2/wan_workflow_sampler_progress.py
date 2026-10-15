"""Bridge the synchronous sampler callback to actual public SDK progress."""
import asyncio
from contextlib import contextmanager
from contextvars import ContextVar

_active = ContextVar('wan_sampler_progress', default=None)


@contextmanager
def progress_scope(context):
    # The numerical sampler runs via asyncio.to_thread; its context is copied
    # while this loop continues servicing the actual progress domain requests.
    token = _active.set((context, asyncio.get_running_loop()))
    try:
        yield
    finally:
        _active.reset(token)


def prepare_callback(model, steps, x0_output_dict=None):
    active = _active.get()
    if active is None:
        raise RuntimeError('Wan sampler must bind its public SDK progress scope')
    context, loop = active

    def callback(step, x0, x, total_steps):
        if x0_output_dict is not None:
            x0_output_dict['x0'] = x0
        if step is not None:
            asyncio.run_coroutine_threadsafe(
                context.progress.update(step + 1, total_steps), loop).result()

    # Native NoPreviews still supplies a callback and calculates denoised
    # samples. Returning None here would incorrectly change the second output.
    return callback
