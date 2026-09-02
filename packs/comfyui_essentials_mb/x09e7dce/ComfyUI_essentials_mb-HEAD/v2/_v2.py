"""Small conversion runtime shared by the Essentials V2 mirror.

Schemas are frozen from the pinned V1 snapshot in ``_schemas.json``. The
adapter below is only for nodes whose purpose is ordinary value/tensor
computation: it materializes refs in the guest, invokes the unchanged upstream
method, and wraps tensor outputs back into refs. Nodes that operate on live
models, CLIP, VAE, assets, or application UI use explicit closed SDK methods
instead and never enter this adapter.
"""
from __future__ import annotations

import copy
import inspect
import json
import pathlib
import sys
from typing import Any, Awaitable, Callable

from comfy_api.v0_0_3 import io, sdk


SCHEMAS = json.loads(pathlib.Path(__file__).with_name("_schemas.json").read_text())

_TYPE_NAMES = {
    "*": "AnyType",
    "AUDIO": "Audio",
    "BOOLEAN": "Boolean",
    "CLIP": "Clip",
    "COLOR": "Color",
    "CONDITIONING": "Conditioning",
    "CONTROL_NET": "ControlNet",
    "FLOAT": "Float",
    "GLIGEN": "Gligen",
    "IMAGE": "Image",
    "INT": "Int",
    "LATENT": "Latent",
    "MASK": "Mask",
    "MODEL": "Model",
    "SAMPLER": "Sampler",
    "SIGMAS": "Sigmas",
    "STRING": "String",
    "VAE": "Vae",
}

_VALUE_INPUTS = {"LATENT", "CONDITIONING", "AUDIO"}
_TENSOR_INPUTS = {"IMAGE", "MASK", "SIGMAS"}
_RAW_TYPES = _VALUE_INPUTS | _TENSOR_INPUTS | {"*"}


def _type(io_type: str):
    name = _TYPE_NAMES.get(io_type)
    return getattr(io, name) if name is not None else io.Custom(io_type)


def _common_input(options: dict[str, Any], optional: bool) -> dict[str, Any]:
    return {
        "display_name": options.get("display_name"),
        "optional": optional,
        "tooltip": options.get("tooltip"),
        "lazy": options.get("lazy"),
        "raw_link": options.get("rawLink"),
        "advanced": options.get("advanced"),
    }


def _input(definition: dict[str, Any]) -> io.Input:
    name = definition["name"]
    declared = definition["type"]
    options = copy.deepcopy(definition.get("options") or {})
    common = _common_input(options, definition["optional"])

    if isinstance(declared, list):
        known = {
            "default", "control_after_generate", "image_upload", "tooltip",
            "display_name", "lazy", "rawLink", "advanced",
        }
        extra = {key: value for key, value in options.items() if key not in known}
        return io.Combo.Input(
            name,
            options=declared,
            default=options.get("default", declared[0] if declared else None),
            control_after_generate=options.get("control_after_generate"),
            extra_dict=extra,
            **common,
        )

    target = _type(str(declared))
    widget_common = {
        **common,
        "default": options.get("default"),
        "socketless": options.get("socketless"),
        "force_input": options.get("forceInput"),
    }
    if declared == "INT":
        display = options.get("display")
        return target.Input(
            name,
            min=options.get("min"),
            max=options.get("max"),
            step=options.get("step"),
            control_after_generate=options.get("control_after_generate"),
            display_mode=io.NumberDisplay(display) if display else None,
            **widget_common,
        )
    if declared == "FLOAT":
        display = options.get("display")
        return target.Input(
            name,
            min=options.get("min"),
            max=options.get("max"),
            step=options.get("step"),
            round=options.get("round"),
            display_mode=io.NumberDisplay(display) if display else None,
            **widget_common,
        )
    if declared == "STRING":
        return target.Input(
            name,
            multiline=bool(options.get("multiline", False)),
            placeholder=options.get("placeholder"),
            dynamic_prompts=options.get("dynamicPrompts"),
            **widget_common,
        )
    if declared == "BOOLEAN":
        return target.Input(
            name,
            label_on=options.get("label_on"),
            label_off=options.get("label_off"),
            **widget_common,
        )
    if declared == "COLOR":
        return target.Input(
            name,
            display_name=common["display_name"],
            optional=common["optional"],
            tooltip=common["tooltip"],
            advanced=common["advanced"],
            socketless=options.get("socketless", True),
            default=options.get("default", "#ffffff"),
        )

    # Custom socket types only expose the generic Input constructor. Preserve
    # widget metadata in the V1 compatibility dictionary rather than dropping
    # it (notably the default used by Essentials' wildcard inputs).
    known = {"display_name", "tooltip", "lazy", "rawLink", "advanced"}
    return target.Input(
        name,
        extra_dict={key: value for key, value in options.items() if key not in known},
        **common,
    )


def schema_for(node_id: str) -> io.Schema:
    definition = SCHEMAS[node_id]
    inputs = [_input(item) for item in definition["inputs"]]
    if node_id == "LorasForFluxParams+":
        inputs[0] = io.Combo.Input(
            "lora_1",
            options=[],
            remote=io.RemoteOptions(
                route="/models/loras", refresh_button=True
            ),
            tooltip="The name of the LoRA.",
        )
    outputs = []
    for index, output in enumerate(definition["outputs"]):
        outputs.append(
            _type(str(output["type"])).Output(
                id=f"output_{index}",
                display_name=output["name"],
                is_output_list=output["is_list"],
            )
        )
    hidden = [io.Hidden(value) for value in definition.get("hidden", [])]
    return io.Schema(
        node_id=node_id,
        display_name=definition["display_name"],
        category=definition["category"],
        description=definition.get("description", ""),
        inputs=inputs,
        outputs=outputs,
        hidden=hidden,
        is_input_list=definition.get("is_input_list", False),
        is_output_node=definition.get("is_output_node", False),
        accept_all_inputs=node_id == "DisplayAny",
    )


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
    if io_type == "AUDIO":
        return await sdk.AudioRef.from_value(value)
    return value


async def node_output(node_id: str, result: Any) -> io.NodeOutput:
    ui_result = None
    if isinstance(result, dict):
        ui_result = result.get("ui")
        values = result.get("result", ())
    else:
        values = result
    if values is None:
        values = ()
    elif not isinstance(values, (tuple, list)):
        values = (values,)

    declared = SCHEMAS[node_id]["outputs"]
    if len(values) != len(declared):
        raise RuntimeError(
            f"{node_id} returned {len(values)} outputs; schema declares "
            f"{len(declared)}"
        )
    wrapped = [
        await wrap_output(value, output["type"], output["is_list"])
        for value, output in zip(values, declared, strict=True)
    ]
    return io.NodeOutput(*wrapped, ui=ui_result)


def _needs_raw(node_id: str) -> bool:
    definition = SCHEMAS[node_id]
    input_types = {
        item["type"] for item in definition["inputs"]
        if isinstance(item["type"], str)
    }
    output_types = {item["type"] for item in definition["outputs"]}
    return bool((input_types | output_types) & _RAW_TYPES)


def adapt(
    node_id: str,
    legacy_class: type,
    *,
    method: str | None = None,
    permissions: tuple[str, ...] | None = None,
) -> type[io.ComfyNode]:
    """Create a V2 class around one unchanged, guest-safe legacy method."""
    definition = SCHEMAS[node_id]
    legacy_method = method or definition["method"]

    def define_schema(cls) -> io.Schema:
        return schema_for(node_id)

    async def execute(cls, **kwargs: Any) -> io.NodeOutput:
        converted = {
            name: await materialize(value) for name, value in kwargs.items()
        }
        for hidden in definition.get("hidden", []):
            name = hidden.lower()
            converted[name] = getattr(cls.hidden, name)
        instance = legacy_class()
        result = getattr(instance, legacy_method)(**converted)
        if inspect.isawaitable(result):
            result = await result
        return await node_output(node_id, result)

    requested = permissions
    if requested is None:
        requested = ("raw",) if _needs_raw(node_id) else ()
    generated = type(
        f"{legacy_class.__name__}V2",
        (io.ComfyNode,),
        {
            "__module__": legacy_class.__module__,
            "SDK_REFS": True,
            "SDK_PERMISSIONS": tuple(requested),
            "define_schema": classmethod(define_schema),
            "execute": classmethod(execute),
        },
    )
    module = sys.modules.get(legacy_class.__module__)
    if module is not None:
        setattr(module, generated.__name__, generated)
    return generated


def custom(
    node_id: str,
    execute: Callable[..., Awaitable[io.NodeOutput]],
    *,
    module: str,
    class_name: str,
    permissions: tuple[str, ...] = (),
    required_weights: tuple[sdk.HuggingFaceWeight, ...] = (),
) -> type[io.ComfyNode]:
    """Create a V2 class for an explicit closed-boundary implementation."""

    def define_schema(cls) -> io.Schema:
        return schema_for(node_id)

    generated = type(
        class_name,
        (io.ComfyNode,),
        {
            "__module__": module,
            "SDK_REFS": True,
            "SDK_PERMISSIONS": tuple(permissions),
            "SDK_REQUIRED_WEIGHTS": tuple(required_weights),
            "define_schema": classmethod(define_schema),
            "execute": classmethod(execute),
        },
    )
    owner = sys.modules.get(module)
    if owner is not None:
        setattr(owner, class_name, generated)
    return generated


__all__ = [
    "SCHEMAS",
    "adapt",
    "custom",
    "io",
    "materialize",
    "node_output",
    "schema_for",
    "sdk",
    "wrap_output",
]
