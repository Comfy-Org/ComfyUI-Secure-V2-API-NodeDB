"""Frozen schema and wire helpers for the pinned Ultimate SD Upscale conversion."""
from __future__ import annotations

import copy
import hashlib
import inspect
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


_MODEL_COMBOS = {
    "checkpoints": ("/models/checkpoints", {"None", "(use same)"}),
    "loras": ("/models/loras", {"None"}),
    "vae": ("/models/vae/choices", {"None", "Baked VAE"}),
    "controlnet": ("/models/controlnet", {"None", "_"}),
    "upscale_models": ("/models/upscale_models", {"None"}),
}


def _catalogue_for_input(node_id: str, input_id: str) -> str | None:
    lowered = input_id.lower()
    if lowered.startswith("ckpt_name_") or lowered in {
        "ckpt_name", "base_ckpt_name", "refiner_ckpt_name", "hires_ckpt_name",
    }:
        return "checkpoints"
    if lowered.startswith("lora_name_") or lowered in {"lora_name"}:
        return "loras"
    if lowered.startswith("vae_name_") or lowered == "vae_name":
        return "vae"
    if lowered in {"control_net_name", "tile_controlnet"}:
        return "controlnet"
    if lowered == "pixel_upscaler":
        return "upscale_models"
    return None


def schema_for(node_id: str) -> io.Schema:
    value = SCHEMAS[node_id]["schema"]
    attrs = _decode(copy.deepcopy(value["attrs"]))
    attrs["inputs"] = [_input(item) for item in value["inputs"]]
    attrs["outputs"] = [_output(item) for item in value["outputs"]]
    attrs["hidden"] = [io.Hidden[name] for name in value["hidden"]]

    for item in attrs["inputs"]:
        if getattr(item, "io_type", None) != "COMBO":
            continue
        catalogue = _catalogue_for_input(node_id, item.id)
        if catalogue is None:
            continue
        route, known_sentinels = _MODEL_COMBOS[catalogue]
        frozen = list(getattr(item, "options", ()) or ())
        sentinels = [option for option in frozen if option in known_sentinels]
        default = getattr(item, "default", None)
        if default in known_sentinels and default not in sentinels:
            sentinels.append(default)
        item.options = sentinels
        item.remote = io.RemoteOptions(route=route, refresh_button=True)

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
    expand = None
    if isinstance(result, dict) and ("result" in result or "ui" in result):
        ui_result = result.get("ui")
        expand = result.get("expand")
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
            f"{node_id} returned {len(values)} outputs; schema declares {len(outputs)}"
        )
    wrapped = [
        await wrap_output(value, output.io_type, output.is_output_list)
        for value, output in zip(values, outputs, strict=True)
    ]
    return io.NodeOutput(*wrapped, ui=ui_result, expand=expand)


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
        hidden = getattr(cls, "hidden", None)
        for name in definition.get("hidden_parameters", ()):
            source_name = "unique_id" if name == "my_unique_id" else name
            kwargs[name] = getattr(hidden, source_name, None)
        result = handler(**kwargs)
        if inspect.isawaitable(result):
            result = await result
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


__all__ = ["SCHEMAS", "bind_node", "io", "node_output", "schema_for", "sdk"]
