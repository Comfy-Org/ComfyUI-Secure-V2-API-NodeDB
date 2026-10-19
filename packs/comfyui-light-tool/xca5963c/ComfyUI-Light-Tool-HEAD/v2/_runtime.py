"""Ref/data boundary; image algorithms remain in their original node modules."""
import inspect
from comfy_api.latest import io, sdk


def missing_api(operation, requirement):
    raise NotImplementedError(f"Pending Secure SDK operation {operation}: {requirement}")


async def materialize(value):
    if isinstance(value, sdk.TensorRef):
        return await value.raw()
    if isinstance(value, sdk.ValueRef):
        return await value.value()
    if isinstance(value, list):
        return [await materialize(x) for x in value]
    if isinstance(value, tuple):
        return tuple([await materialize(x) for x in value])
    if isinstance(value, dict):
        return {k: await materialize(v) for k, v in value.items()}
    return value


async def publish(value, kind, is_list=False):
    if value is None or isinstance(value, sdk.Ref):
        return value
    if is_list:
        return [await publish(x, kind) for x in value]
    if kind == 'IMAGE':
        if value.ndim != 4:
            return missing_api('TensorRef.from_value', 'Publish the original grayscale IMAGE tensor without changing its rank or declared schema')
        return await sdk.ImageRef.from_value(value)
    if kind == 'MASK':
        return missing_api('MaskRef.from_value', 'Publish a MASK tensor through a public typed constructor preserving rank, dtype, and values')
    import numpy as np
    if isinstance(value, np.generic):
        return value.item()
    # The original wildcard outputs can also carry an image tensor.
    if kind == '*':
        import torch
        import numpy as np
        if isinstance(value, torch.Tensor):
            return missing_api('TensorRef.from_value', 'Publish a generic tensor through a public typed constructor')
        if isinstance(value, np.generic):
            return value.item()
    return value


async def run(method, kwargs, kinds, lists):
    result = method(**{k: await materialize(v) for k, v in kwargs.items()})
    if inspect.isawaitable(result):
        result = await result
    if isinstance(result, dict):
        values, ui = result.get('result', ()), result.get('ui')
    else:
        values, ui = result, None
    # Preserve malformed source scalar returns (e.g. invalid KeyValue JSON).
    if not isinstance(values, (list, tuple)):
        values = tuple(values) if isinstance(values, str) else (values,)
    wrapped = [await publish(v, kinds[i], lists[i]) for i, v in enumerate(values)]
    return io.NodeOutput(*wrapped, ui=ui)
