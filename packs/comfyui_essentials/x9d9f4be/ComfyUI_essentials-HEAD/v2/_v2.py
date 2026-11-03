"""Frozen schema plumbing for all 85 pinned Essentials node identities.

Only standard library and public SDK imports are used.
"""
from __future__ import annotations

import copy
import inspect
import json
import pathlib
import sys
from typing import Any, Awaitable, Callable

from comfy_api.latest import io, sdk


SCHEMAS = json.loads(pathlib.Path(__file__).with_name("_schemas.json").read_text())

_TYPE_NAMES = {
    "*": "AnyType",
    "AUDIO": "Audio",
    "BOOLEAN": "Boolean",
    "CLIP": "Clip",
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


