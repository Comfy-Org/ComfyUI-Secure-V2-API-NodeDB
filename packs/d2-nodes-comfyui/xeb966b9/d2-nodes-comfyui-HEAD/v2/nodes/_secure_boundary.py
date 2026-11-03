"""Guest boundary adapters; no host imports or resource caches."""
from comfy_api.latest import sdk

class SecureConversionRefusal(RuntimeError):
    """An upstream branch has no faithful public-SDK representation."""

async def data_input(value, node):
    if isinstance(value, sdk.ValueRef):
        return await value.value()
    if isinstance(value, sdk.TensorRef):
        return await value.raw()
    if isinstance(value, sdk.Ref):
        raise SecureConversionRefusal(
            f"d2-nodes-comfyui/{node}: formatting opaque host objects is not yet converted to Secure Nodes V2")
    if isinstance(value, list):
        return [await data_input(item, node) for item in value]
    if isinstance(value, tuple):
        return tuple([await data_input(item, node) for item in value])
    if isinstance(value, dict):
        return {key: await data_input(item, node) for key, item in value.items()}
    return value
