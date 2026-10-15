"""Public SDK availability gate; private image factories are never invoked."""
from comfy_api.latest import sdk


def require_image_value_factory():
    factory = getattr(sdk.ImageRef, 'from_value', None)
    if not callable(factory):
        raise NotImplementedError(
            'Original Save IMAGE normalization and returned frames require the public '
            'ImageRef.from_value API; this runtime profile remains unqualified')
    return factory
