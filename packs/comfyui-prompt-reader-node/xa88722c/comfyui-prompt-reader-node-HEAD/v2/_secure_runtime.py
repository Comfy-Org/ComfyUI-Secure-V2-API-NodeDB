"""Frozen schema and wire helpers for the pinned Prompt Reader conversion."""
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
    io_type = value["io_type"]
    # V1 represents selector outputs as their literal choice list.  Preserve
    # that wire type as a COMBO instead of inventing a custom type whose name
    # happens to be the stringified list.
    output_type = (
        io.Combo
        if isinstance(io_type, str)
        and io_type.startswith("[")
        and io_type.endswith("]")
        else _io_class(io_type)
    )
    result = object.__new__(output_type.Output)
    result.__dict__.update(_decode(copy.deepcopy(value["attrs"])))
    return result


_MODEL_COMBOS = {
    "checkpoints": "/models/checkpoints",
    "configs": "/models/configs",
    "loras": "/models/loras",
    "vae": "/models/vae/choices",
}


def _catalogue_for_input(node_id: str, input_id: str) -> str | None:
    if (node_id == "SDParameterGenerator" and input_id == "ckpt_name"
            or node_id == "SDPromptSaver" and input_id == "model_name"
            or node_id == "SDTypeConverter" and input_id == "model_name"):
        return "checkpoints"
    if node_id == "SDParameterGenerator" and input_id == "config_name":
        return "configs"
    if (node_id == "SDPromptSaver" and input_id == "vae_name"
            or node_id == "SDParameterGenerator" and input_id == "vae_name"):
        return "vae"
    if node_id in {"SDLoraLoader", "SDLoraSelector"} and input_id == "lora_name":
        return "loras"
    return None


def schema_for(node_id: str) -> io.Schema:
    value = SCHEMAS[node_id]["schema"]
    attrs = _decode(copy.deepcopy(value["attrs"]))
    attrs["inputs"] = [_input(item) for item in value["inputs"]]
    attrs["outputs"] = [_output(item) for item in value["outputs"]]
    # Prompt/workflow metadata stays in the trusted context. Saver nodes ask
    # the output broker to embed it; WorkflowInputValue uses the graph broker.
    # None of the legacy hidden prompt dictionaries cross into the guest.
    attrs["hidden"] = []
    if node_id == "SDAnyConverter":
        attrs["accept_all_inputs"] = True

    if node_id == "SDPromptReader":
        image = next(item for item in attrs["inputs"] if item.id == "image")
        image.options = []
        image.default = ""
        image.upload = io.UploadType.image
        image.remote = io.RemoteOptions(
            route="/secure-nodes/assets/input?kind=image",
            refresh_button=True,
        )
    elif node_id == "SDBatchLoader":
        original = next(item for item in attrs["inputs"] if item.id == "path")
        replacement = io.Combo.Input(
            "path",
            options=[],
            default="",
            display_name=original.display_name,
            tooltip=(
                "A folder or selected image inside ComfyUI's managed input "
                "directory; host filesystem paths are not accepted."
            ),
            remote=io.RemoteOptions(
                route="/secure-nodes/assets/input?kind=directory",
                refresh_button=True,
            ),
        )
        attrs["inputs"][attrs["inputs"].index(original)] = replacement

    for item in attrs["inputs"]:
        if getattr(item, "io_type", None) != "COMBO":
            continue
        catalogue = _catalogue_for_input(node_id, item.id)
        if catalogue is None:
            continue
        route = _MODEL_COMBOS[catalogue]
        if catalogue == "configs":
            item.options = ["none"]
        elif catalogue == "vae" and node_id == "SDParameterGenerator":
            item.options = ["baked VAE"]
        else:
            item.options = []
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
    accept_all_inputs: bool = False,
) -> type[io.ComfyNode]:
    definition = SCHEMAS[node_id]

    def define_schema(cls) -> io.Schema:
        return schema_for(node_id)

    async def execute(cls, **kwargs: Any) -> io.NodeOutput:
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
    if accept_all_inputs:
        def validate_inputs(cls, **_kwargs: Any) -> bool:
            return True

        attrs["validate_inputs"] = classmethod(validate_inputs)
    generated = type(f"{class_name}Secure_{suffix}", (io.ComfyNode,), attrs)
    owner = sys.modules.get(handler.__module__)
    if owner is not None:
        setattr(owner, generated.__name__, generated)
    return generated


__all__ = ["SCHEMAS", "bind_node", "io", "node_output", "schema_for", "sdk"]
