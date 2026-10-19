"""Public typed output boundary for the assigned Light Tool consumers only.

Requires the reviewed SDK successor: MaskRef.from_value and
ImageRef.from_tensor. No private constructor or rank/layout conversion.
"""
import inspect
from comfy_api.latest import io, sdk
from ._runtime import materialize


async def publish(value, kind, is_list=False):
    if value is None or isinstance(value, sdk.Ref):
        return value
    if is_list:
        return [await publish(item, kind) for item in value]
    if kind == 'IMAGE':
        return await sdk.ImageRef.from_tensor(value)
    if kind == 'MASK':
        return await sdk.MaskRef.from_value(value)
    return value


async def run(method, kwargs, kinds, lists):
    result = method(**{key: await materialize(value) for key, value in kwargs.items()})
    if inspect.isawaitable(result):
        result = await result
    if isinstance(result, dict):
        values, ui = result.get('result', ()), result.get('ui')
    else:
        values, ui = result, None
    if not isinstance(values, (list, tuple)):
        values = tuple(values) if isinstance(values, str) else (values,)
    wrapped = [await publish(value, kinds[index], lists[index]) for index, value in enumerate(values)]
    return io.NodeOutput(*wrapped, ui=ui)
