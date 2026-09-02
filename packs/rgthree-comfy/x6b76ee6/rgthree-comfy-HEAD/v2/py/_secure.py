"""Schema and class helpers for rgthree's Secure Nodes 2.0 port."""
from __future__ import annotations

import copy
import json
import pathlib
import sys
from collections.abc import Awaitable, Callable
from typing import Any

from comfy_api.v0_0_3 import io, sdk


SCHEMAS = json.loads(
    pathlib.Path(__file__).parents[1].joinpath("_schemas.json").read_text()
)

_TYPE_NAMES = {
    "*": "AnyType",
    "BOOLEAN": "Boolean",
    "CLIP": "Clip",
    "CONDITIONING": "Conditioning",
    "CONTROL_NET": "ControlNet",
    "FLOAT": "Float",
    "IMAGE": "Image",
    "INT": "Int",
    "LATENT": "Latent",
    "MASK": "Mask",
    "MODEL": "Model",
    "STRING": "String",
    "VAE": "Vae",
}

_STANDARD_HIDDEN = {item.value for item in io.Hidden}
_HIDDEN_BY_NODE = {
    # Power Puter's node()/nodes()/input_node() helpers use these two inert
    # prompt values. It does not need EXTRA_PNGINFO or the live DYNPROMPT
    # object. (V3's manifest codec separately adds prompt metadata to output
    # nodes as part of the standard output-node protocol.)
    "Power Puter (rgthree)": {
        io.Hidden.unique_id.value,
        io.Hidden.prompt.value,
    },
}
_ACCEPT_ALL = {
    "Any Switch (rgthree)",
    "Context Merge (rgthree)",
    "Context Merge Big (rgthree)",
    "Context Switch (rgthree)",
    "Context Switch Big (rgthree)",
    "Image or Latent Size (rgthree)",
    "Power Lora Loader (rgthree)",
    "Power Primitive (rgthree)",
    "Power Puter (rgthree)",
}


def _type(declared: str):
    name = _TYPE_NAMES.get(declared)
    return getattr(io, name) if name is not None else io.Custom(declared)


def _common(options: dict[str, Any], optional: bool) -> dict[str, Any]:
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
    common = _common(options, definition["optional"])

    if isinstance(declared, list):
        known = {
            "default", "control_after_generate", "tooltip", "display_name",
            "lazy", "rawLink", "advanced",
        }
        extra = {key: value for key, value in options.items() if key not in known}
        remote_route = definition.get("remote")
        remote = None
        if remote_route:
            remote = io.RemoteOptions(
                route=remote_route,
                refresh_button=True,
            )
        return io.Combo.Input(
            name,
            options=declared,
            default=options.get("default", declared[0] if declared else None),
            control_after_generate=options.get("control_after_generate"),
            remote=remote,
            extra_dict=extra,
            **common,
        )

    target = _type(str(declared))
    widget = {
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
            **widget,
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
            **widget,
        )
    if declared == "STRING":
        return target.Input(
            name,
            multiline=bool(options.get("multiline", False)),
            placeholder=options.get("placeholder"),
            dynamic_prompts=options.get("dynamicPrompts"),
            **widget,
        )
    if declared == "BOOLEAN":
        return target.Input(
            name,
            label_on=options.get("label_on"),
            label_off=options.get("label_off"),
            **widget,
        )

    known = {"display_name", "tooltip", "lazy", "rawLink", "advanced"}
    return target.Input(
        name,
        extra_dict={key: value for key, value in options.items() if key not in known},
        **common,
    )


def schema_for(node_id: str) -> io.Schema:
    definition = SCHEMAS[node_id]
    outputs: list[io.Output] = []
    for index, output in enumerate(definition["outputs"]):
        declared = output["type"]
        if isinstance(declared, list):
            item = io.Combo.Output(
                id=f"output_{index}",
                display_name=output["name"],
                options=declared,
                is_output_list=output["is_list"],
            )
        else:
            item = _type(str(declared)).Output(
                id=f"output_{index}",
                display_name=output["name"],
                is_output_list=output["is_list"],
            )
        outputs.append(item)

    # V1 represented this with an unbounded tuple type. Ten is the frontend's
    # own hard limit; fixed wildcard slots retain link-index validation while
    # its widget continues to show only the selected outputs.
    if node_id == "Power Puter (rgthree)":
        outputs = [
            io.AnyType.Output(id=f"output_{index}", display_name="*")
            for index in range(10)
        ]

    allowed_hidden = _HIDDEN_BY_NODE.get(node_id, set())
    hidden = [
        io.Hidden(value)
        for value in definition.get("hidden", [])
        if value in _STANDARD_HIDDEN and value in allowed_hidden
    ]
    return io.Schema(
        node_id=node_id,
        display_name=definition["display_name"],
        category=definition["category"],
        description=definition.get("description", ""),
        inputs=[_input(item) for item in definition["inputs"]],
        outputs=outputs,
        hidden=hidden,
        is_input_list=definition.get("is_input_list", False),
        is_output_node=definition.get("is_output_node", False),
        accept_all_inputs=node_id in _ACCEPT_ALL,
    )


async def materialize(value: Any) -> Any:
    """Materialize buffer-safe refs while retaining opaque engine handles."""
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


def node(
    node_id: str,
    execute: Callable[..., Awaitable[io.NodeOutput]],
    *,
    class_name: str,
    permissions: tuple[str, ...] = (),
    fingerprint: Callable[..., Any] | None = None,
) -> type[io.ComfyNode]:
    """Create and bind one explicit SDK-ref node class."""

    def define_schema(cls) -> io.Schema:
        return schema_for(node_id)

    attrs = {
        "__module__": execute.__module__,
        "SDK_REFS": True,
        "SDK_PERMISSIONS": tuple(permissions),
        "define_schema": classmethod(define_schema),
        "execute": classmethod(execute),
    }
    if fingerprint is not None:
        attrs["fingerprint_inputs"] = classmethod(fingerprint)
    generated = type(class_name, (io.ComfyNode,), attrs)
    owner = sys.modules.get(execute.__module__)
    if owner is not None:
        setattr(owner, class_name, generated)
    return generated


__all__ = ["SCHEMAS", "io", "materialize", "node", "schema_for", "sdk"]
