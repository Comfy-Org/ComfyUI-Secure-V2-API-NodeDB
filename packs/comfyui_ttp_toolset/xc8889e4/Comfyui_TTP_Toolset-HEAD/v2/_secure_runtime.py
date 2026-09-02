"""Frozen schemas and wire helpers for the pinned TTP Toolset conversion."""
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

    if node_id == "TTP_Smart_Tile_Interactive_Crop_Experimental":
        image = attrs["inputs"][0]
        image.options = []
        image.default = ""
        image.upload = io.UploadType.image
        image.remote = io.RemoteOptions(
            route="/secure-nodes/assets/input?kind=image",
                refresh_button=True,
            )
    elif node_id == "TTP_QwenVL3_Local_Loader_Experimental":
        original = attrs["inputs"][0]
        attrs["inputs"][0] = io.Combo.Input(
            "model_file",
            options=[],
            default="",
            optional=False,
            display_name=original.display_name,
            tooltip=original.tooltip,
            remote=io.RemoteOptions(
                route="/models/text_encoders",
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
    if io_type == "LATENT":
        return await sdk.LatentRef.from_value(value)
    if io_type == "CONDITIONING":
        return await sdk.CondRef.from_value(value)
    if io_type == "TTP_SMART_TILE_SET":
        if not isinstance(value, dict):
            raise TypeError("TTP_SMART_TILE_SET output must be a dictionary")
        result = dict(value)
        result["tile_images"] = [
            item if isinstance(item, sdk.ImageRef)
            else await sdk.ImageRef._from_raw(item)
            for item in value.get("tile_images", [])
        ]
        return result
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
    check_lazy_status: Handler | None = None,
) -> type[io.ComfyNode]:
    definition = SCHEMAS[node_id]

    def define_schema(cls) -> io.Schema:
        return schema_for(node_id)

    async def execute(cls, **kwargs: Any) -> io.NodeOutput:
        result = await handler(**kwargs)
        return await node_output(node_id, result)

    async def fingerprint(cls, **kwargs: Any):
        result = handler_fingerprint(**kwargs)
        return await result if inspect.isawaitable(result) else result

    async def check_lazy(cls, **kwargs: Any):
        result = check_lazy_status(**kwargs)
        return await result if inspect.isawaitable(result) else result

    async def validate(cls, **kwargs: Any):
        result = handler_validate(**kwargs)
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
    handler_fingerprint = getattr(handler, "fingerprint_inputs", None)
    handler_validate = getattr(handler, "validate_inputs", None)
    if handler_fingerprint is not None:
        attrs["fingerprint_inputs"] = classmethod(fingerprint)
    if handler_validate is not None:
        attrs["validate_inputs"] = classmethod(validate)
    if check_lazy_status is not None:
        attrs["check_lazy_status"] = classmethod(check_lazy)
    generated = type(f"{class_name}Secure_{suffix}", (io.ComfyNode,), attrs)
    owner = sys.modules.get(handler.__module__)
    if owner is not None:
        setattr(owner, generated.__name__, generated)
    return generated


__all__ = [
    "SCHEMAS",
    "bind_node",
    "io",
    "materialize",
    "schema_for",
    "sdk",
]
