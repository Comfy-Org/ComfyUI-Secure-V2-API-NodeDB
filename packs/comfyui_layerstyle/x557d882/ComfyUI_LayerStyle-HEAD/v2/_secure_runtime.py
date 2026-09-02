"""Frozen-schema and wire helpers for the pinned LayerStyle conversion."""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import re
import sys
from enum import Enum
from typing import Any, Awaitable, Callable

from comfy_api.latest import io, sdk


SCHEMAS = json.loads(pathlib.Path(__file__).with_name("_schemas.json").read_text())


def _io_class(io_type: str):
    for value in vars(io).values():
        if isinstance(value, type) and getattr(value, "io_type", None) == io_type:
            return value
    return io.Custom(io_type)


def _decode(value: Any):
    if isinstance(value, list):
        return [_decode(item) for item in value]
    if not isinstance(value, dict):
        return value
    tag = value.get("$type")
    if tag is None:
        return {key: _decode(item) for key, item in value.items()}
    if tag == "enum":
        enum_type = getattr(io, value["enum"], None)
        if not isinstance(enum_type, type) or not issubclass(enum_type, Enum):
            raise ValueError(f"unknown frozen schema enum {value['enum']!r}")
        return enum_type[value["name"]]
    if tag == "tuple":
        return tuple(_decode(item) for item in value["items"])
    if tag == "remote-options":
        result = object.__new__(io.RemoteOptions)
        result.__dict__.update(_decode(value["attrs"]))
        return result
    if tag == "io-class":
        return _io_class(value["io_type"])
    raise ValueError(f"unknown frozen schema value tag {tag!r}")


def _input(value: dict[str, Any]):
    if value["kind"] != "standard":
        raise ValueError(f"unsupported frozen input kind {value['kind']!r}")
    result = object.__new__(_io_class(value["io_type"]).Input)
    result.__dict__.update(_decode(copy.deepcopy(value["attrs"])))
    return result


def _output(value: dict[str, Any]):
    if value["kind"] != "standard":
        raise ValueError(f"unsupported frozen output kind {value['kind']!r}")
    result = object.__new__(_io_class(value["io_type"]).Output)
    result.__dict__.update(_decode(copy.deepcopy(value["attrs"])))
    return result


def schema_for(node_id: str) -> io.Schema:
    value = SCHEMAS[node_id]["schema"]
    attrs = _decode(copy.deepcopy(value["attrs"]))
    attrs["inputs"] = [_input(item) for item in value["inputs"]]
    attrs["outputs"] = [_output(item) for item in value["outputs"]]
    attrs["hidden"] = []

    if node_id == "LayerUtility: LoadImagesFromPath":
        original = attrs["inputs"][0]
        attrs["inputs"][0] = io.Combo.Input(
            "path",
            options=[],
            default="",
            display_name=original.display_name,
            tooltip=(
                "A folder inside ComfyUI's managed input directory. "
                "Host filesystem paths are intentionally not accepted."
            ),
            remote=io.RemoteOptions(
                route="/secure-nodes/assets/input?kind=directory",
                refresh_button=True,
            ),
        )
    return io.Schema(**attrs)


async def materialize(value: Any) -> Any:
    if isinstance(value, sdk.TensorRef):
        return await value.raw()
    if isinstance(value, sdk.ValueRef):
        return await value.value()
    if isinstance(value, list):
        return [await materialize(item) for item in value]
    if isinstance(value, tuple):
        return tuple([await materialize(item) for item in value])
    if isinstance(value, dict):
        return {key: await materialize(item) for key, item in value.items()}
    return value


async def _wrap(value: Any, io_type: str, is_list: bool) -> Any:
    if value is None or isinstance(value, sdk.Ref):
        return value
    if is_list:
        return [await _wrap(item, io_type, False) for item in value]
    if io_type == "IMAGE":
        return await sdk.ImageRef._from_raw(value)
    if io_type == "MASK":
        return await sdk.MaskRef._from_raw(value)
    return value


async def node_output(node_id: str, result: Any) -> io.NodeOutput:
    if isinstance(result, io.NodeOutput):
        return result
    ui_result = None
    expand_result = None
    if isinstance(result, dict) and ("result" in result or "ui" in result):
        ui_result = result.get("ui")
        expand_result = result.get("expand")
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
        await _wrap(value, output.io_type, output.is_output_list)
        for value, output in zip(values, outputs, strict=True)
    ]
    return io.NodeOutput(*wrapped, ui=ui_result, expand=expand_result)


Handler = Callable[..., Awaitable[Any]]


def bind_node(
    node_id: str,
    handler: Handler,
    *,
    permissions: tuple[str, ...] = (),
    required_weights: tuple[sdk.HuggingFaceWeight, ...] = (),
) -> type[io.ComfyNode]:
    definition = SCHEMAS[node_id]

    def define_schema(cls) -> io.Schema:
        return schema_for(node_id)

    async def execute(cls, **kwargs: Any) -> io.NodeOutput:
        result = await handler(**kwargs)
        return await node_output(node_id, result)

    class_name = re.sub(r"\W+", "_", definition["class"])
    suffix = hashlib.sha1(node_id.encode("utf-8")).hexdigest()[:10]
    attrs = {
        "__module__": handler.__module__,
        "SDK_REFS": True,
        "SDK_PERMISSIONS": tuple(permissions),
        "SDK_REQUIRED_WEIGHTS": tuple(required_weights),
        "define_schema": classmethod(define_schema),
        "execute": classmethod(execute),
    }
    generated = type(f"{class_name}Secure_{suffix}", (io.ComfyNode,), attrs)
    owner = sys.modules.get(handler.__module__)
    if owner is not None:
        setattr(owner, generated.__name__, generated)
    return generated


def has_tensor_io(node_id: str) -> bool:
    schema = SCHEMAS[node_id]["schema"]
    return any(
        item["io_type"] in {"IMAGE", "MASK", "LATENT"}
        for item in [*schema["inputs"], *schema["outputs"]]
    )


__all__ = [
    "SCHEMAS",
    "bind_node",
    "has_tensor_io",
    "io",
    "materialize",
    "node_output",
    "schema_for",
    "sdk",
]
