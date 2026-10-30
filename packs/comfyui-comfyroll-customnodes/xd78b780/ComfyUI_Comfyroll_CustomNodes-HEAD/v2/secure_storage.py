"""Atomic storage capability check; no non-atomic fallback."""
from comfy_api.latest import sdk
import inspect

PENDING = ('Comfyroll atomic storage capability pending: this runtime must provide '
           'storage.read and storage.compare_and_set together; get/set is not a substitute')

def atomic_storage():
    service = sdk.ctx().storage
    # A generic __getattr__ stub/proxy is not evidence that atomic methods
    # exist. Require explicit callable members before any state operation.
    if not all(callable(inspect.getattr_static(service, name, None)) for name in ('read', 'compare_and_set')):
        raise RuntimeError(PENDING)
    return service
