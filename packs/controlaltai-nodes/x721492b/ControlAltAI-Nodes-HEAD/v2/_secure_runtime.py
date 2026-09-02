"""Frozen schema and wire helpers for the pinned ControlAltAI conversion."""
from __future__ import annotations

import copy
import hashlib
import inspect
import json
import pathlib
import re
import sys
from typing import Any, Awaitable, Callable

from comfy_api.latest import io, sdk


SCHEMAS = json.loads(pathlib.Path(__file__).with_name("_schemas.json").read_text())


def _io_class(io_type: str):
    for value in vars(io).values():
        if isinstance(value, type) and getattr(value, "io_type", None) == io_type:
            return value
    return io.Custom(io_type)


def _input(value: dict[str, Any]):
    if value["kind"] != "standard":
        raise ValueError(f"unsupported frozen input kind {value['kind']!r}")
    result = object.__new__(_io_class(value["io_type"]).Input)
    result.__dict__.update(copy.deepcopy(value["attrs"]))
    return result


def _output(value: dict[str, Any]):
    if value["kind"] != "standard":
        raise ValueError(f"unsupported frozen output kind {value['kind']!r}")
    result = object.__new__(_io_class(value["io_type"]).Output)
    result.__dict__.update(copy.deepcopy(value["attrs"]))
    return result


def schema_for(node_id: str) -> io.Schema:
    value = SCHEMAS[node_id]["schema"]
    attrs = copy.deepcopy(value["attrs"])
    attrs["inputs"] = [_input(item) for item in value["inputs"]]
    attrs["outputs"] = [_output(item) for item in value["outputs"]]
    attrs["hidden"] = [io.Hidden[name] for name in value["hidden"]]
    return io.Schema(**attrs)


async def wrap_output(value: Any, io_type: str, is_list: bool = False) -> Any:
    if value is None or isinstance(value, sdk.Ref):
        return value
    if is_list:
        return [await wrap_output(item, io_type) for item in value]
    if io_type == "IMAGE":
        return await sdk.ImageRef._from_raw(value)
    if io_type == "MASK":
        return await sdk.MaskRef._from_raw(value)
    if io_type == "LATENT":
        return await sdk.LatentRef.from_value(value)
    if io_type == "CONDITIONING":
        return await sdk.CondRef.from_value(value)
    return value


async def node_output(node_id: str, result: Any) -> io.NodeOutput:
    if isinstance(result, io.NodeOutput):
        return result
    ui_result = None
    if isinstance(result, dict) and ("result" in result or "ui" in result):
        ui_result = result.get("ui")
        values = result.get("result", ())
    else:
        values = result
    if values is None:
        values = ()
    elif not isinstance(values, (tuple, list)):
        values = (values,)

    outputs = schema_for(node_id).outputs
    if len(values) != len(outputs):
        raise RuntimeError(
            f"{node_id} returned {len(values)} outputs; schema declares "
            f"{len(outputs)}"
        )
    wrapped = [
        await wrap_output(value, output.io_type, output.is_output_list)
        for value, output in zip(values, outputs, strict=True)
    ]
    return io.NodeOutput(*wrapped, ui=ui_result)


Handler = Callable[..., Awaitable[Any]]


def bind_node(
    node_id: str,
    handler: Handler,
    *,
    permissions: tuple[str, ...] = (),
) -> type[io.ComfyNode]:
    definition = SCHEMAS[node_id]

    def define_schema(cls) -> io.Schema:
        return schema_for(node_id)

    async def execute(cls, **kwargs: Any) -> io.NodeOutput:
        result = handler(**kwargs)
        if inspect.isawaitable(result):
            result = await result
        return await node_output(node_id, result)

    async def validate(cls, **kwargs: Any):
        result = validator(**kwargs)
        return await result if inspect.isawaitable(result) else result

    class_name = re.sub(r"\W+", "_", definition["class"])
    suffix = hashlib.sha1(node_id.encode("utf-8")).hexdigest()[:10]
    attrs = {
        "__module__": handler.__module__,
        "SDK_REFS": True,
        "SDK_PERMISSIONS": tuple(permissions),
        "define_schema": classmethod(define_schema),
        "execute": classmethod(execute),
    }
    validator = getattr(handler, "validate_inputs", None)
    if validator is not None:
        attrs["validate_inputs"] = classmethod(validate)
    generated = type(f"{class_name}Secure_{suffix}", (io.ComfyNode,), attrs)
    owner = sys.modules.get(handler.__module__)
    if owner is not None:
        setattr(owner, generated.__name__, generated)
    return generated


__all__ = ["SCHEMAS", "bind_node", "io", "schema_for", "sdk"]
