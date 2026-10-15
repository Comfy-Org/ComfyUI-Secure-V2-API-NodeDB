"""Explicit CPU execution policy for the owned Wan mathematical package.

This is a pack module, not a replacement import for comfy.model_management.
Device facts refer to the CPU-only conversion scope. Cancellation is owned by
the SDK worker; a synchronous caller may also install a real polling callback.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import gc
import torch

_interrupt_check = ContextVar('wan_interrupt_check', default=None)


def get_torch_device():
    return torch.device('cpu')


def get_autocast_device(device):
    if torch.device(device).type != 'cpu':
        raise ValueError('Wan workflow CPU scope does not admit accelerator devices')
    return 'cpu'


def is_device_mps(device):
    return torch.device(device).type == 'mps'


def is_directml_enabled():
    return False


def is_intel_xpu():
    return False


def soft_empty_cache():
    # CPU has no CUDA allocator cache. Release Python-owned cycles only.
    gc.collect()


def throw_exception_if_processing_interrupted():
    check = _interrupt_check.get()
    if check is not None:
        check()


@contextmanager
def interrupt_scope(check):
    if not callable(check):
        raise TypeError('Wan interrupt callback must be callable')
    token = _interrupt_check.set(check)
    try:
        yield
    finally:
        _interrupt_check.reset(token)


def unavailable_comfy_attention(*args, **kwargs):
    raise NotImplementedError('The Core optimized_attention backend is outside this staged SDPA CPU scope')
