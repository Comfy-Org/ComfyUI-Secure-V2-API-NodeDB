"""Frozen-schema runtime for the comfyui-art-venture Secure Nodes V2 pack.

_frozen_nodes.json holds every node declaration of upstream comfyui-art-venture 210dc072, frozen in the gate from
the original package (tests/freeze_artv.py). All are V1 nodes (INPUT_TYPES/RETURN_TYPES); ``v1_schema`` turns them
into V3 schemas. Model menus were found at freeze time with probe files in every model folder: such a menu keeps its
static entries and is filled from the host's model folder (``/models/<folder>``), never from the pack.
``tests/test_artv_schemas.py`` checks the served node info against the original's.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import keyword
import pathlib
import re
from typing import Any

from comfy_api.latest import io

_DATA = json.loads(pathlib.Path(__file__).with_name("_frozen_nodes.json").read_text())
FROZEN = _DATA["nodes"]
MENUS = _DATA.get("model_menus", {})
_PROBE = re.compile(r"^__probe_[A-Za-z0-9_.-]+__(\.[A-Za-z0-9]+)?$")


def decode(value: Any) -> Any:
    if isinstance(value, list):
        return [decode(item) for item in value]
    if not isinstance(value, dict):
        return value
    if "$float" in value:
        return float(value["$float"])
    if "$tuple" in value:
        return tuple(decode(item) for item in value["$tuple"])
    if "$list" in value:
        return [decode(item) for item in value["$list"]]
    if "$dict" in value:
        return {decode(k): decode(v) for k, v in value["$dict"]}
    if "$enum" in value:
        enum_type = getattr(io, value["$enum"])
        return enum_type[value["name"]]
    if "$opaque" in value:
        raise ValueError(f"frozen value {value['$opaque']} is opaque")
    if any(isinstance(key, str) and key.startswith("$") for key in value):
        raise ValueError(f"unknown frozen tag {sorted(value)}")
    return {key: decode(item) for key, item in value.items()}


def _without_probes(options) -> list:
    return [o for o in options if not (isinstance(o, str) and _PROBE.match(o))]


_HIDDEN = {member.value: member for member in io.Hidden}


def _common(opts: dict, optional: bool) -> dict:
    return {
        "optional": optional,
        "tooltip": opts.pop("tooltip", None),
        "lazy": opts.pop("lazy", None),
        "display_name": opts.pop("display_name", None),
        "raw_link": opts.pop("rawLink", None),
        "advanced": opts.pop("advanced", None),
    }


def v1_input(node_id: str, name: str, spec, optional: bool):
    spec = list(spec) if isinstance(spec, (list, tuple)) else [spec]
    type_ = spec[0]
    opts = dict(spec[1]) if len(spec) > 1 and isinstance(spec[1], dict) else {}
    common = _common(opts, optional)
    if isinstance(type_, (list, tuple)):
        menu = MENUS.get(node_id, {}).get(name)
        options = _without_probes(type_) if menu else list(type_)
        item = io.Combo.Input(name, options=options, default=opts.pop("default", None),
                              control_after_generate=opts.pop("control_after_generate", None),
                              extra_dict=opts, **common)
        if menu:  # filled by the host from its model folder (packdb model menus)
            item.remote = io.RemoteOptions(route=f"/models/{menu['folders'][0]}", refresh_button=True)
        return item
    if type_ == "INT":
        display = opts.pop("display", None)
        return io.Int.Input(name, default=opts.pop("default", None), min=opts.pop("min", None),
                            max=opts.pop("max", None), step=opts.pop("step", None),
                            control_after_generate=opts.pop("control_after_generate", None),
                            display_mode=io.NumberDisplay(display) if display is not None else None,
                            force_input=opts.pop("forceInput", None), extra_dict=opts, **common)
    if type_ == "FLOAT":
        return io.Float.Input(name, default=opts.pop("default", None), min=opts.pop("min", None),
                              max=opts.pop("max", None), step=opts.pop("step", None), round=opts.pop("round", None),
                              display_mode=opts.pop("display", None), force_input=opts.pop("forceInput", None),
                              extra_dict=opts, **common)
    if type_ == "STRING":
        return io.String.Input(name, multiline=opts.pop("multiline", None), placeholder=opts.pop("placeholder", None),
                               default=opts.pop("default", None), dynamic_prompts=opts.pop("dynamicPrompts", None),
                               force_input=opts.pop("forceInput", None), extra_dict=opts, **common)
    if type_ == "BOOLEAN":
        return io.Boolean.Input(name, default=opts.pop("default", None), label_on=opts.pop("label_on", None),
                                label_off=opts.pop("label_off", None), force_input=opts.pop("forceInput", None),
                                extra_dict=opts, **common)
    return io.Custom(str(type_)).Input(name, extra_dict=opts, **common)


def v1_schema(node_id: str, entry: dict) -> io.Schema:
    v1 = decode(entry["v1"])
    types = v1["INPUT_TYPES"]
    inputs = []
    for section in ("required", "optional"):
        for name, spec in (types.get(section) or {}).items():
            inputs.append(v1_input(node_id, name, spec, section == "optional"))
    hidden = [_HIDDEN[value if isinstance(value, str) else value[0]] for value in (types.get("hidden") or {}).values()]
    returns = list(v1.get("RETURN_TYPES", ()))
    names = list(v1.get("RETURN_NAMES", ()) or ())
    is_list = list(v1.get("OUTPUT_IS_LIST", ()) or ())
    tips = list(v1.get("OUTPUT_TOOLTIPS", ()) or ())
    outputs = []
    for index, rtype in enumerate(returns):
        kwargs = {
            "display_name": names[index] if index < len(names) else None,
            "tooltip": tips[index] if index < len(tips) else None,
            "is_output_list": bool(is_list[index]) if index < len(is_list) else False,
        }
        if isinstance(rtype, (list, tuple)):
            # A model-folder list output cannot be declared statically; it stays a generic COMBO (see
            # SECURE_CONVERSION.md). Static choice lists keep their options.
            outputs.append(io.Combo.Output(options=_without_probes(rtype), **kwargs))
        else:
            outputs.append(io.Custom(str(rtype)).Output(**kwargs))
    return io.Schema(
        node_id=node_id,
        display_name=entry.get("display_name") or node_id,
        category=v1.get("CATEGORY", "sd"),
        inputs=inputs,
        outputs=outputs,
        hidden=hidden,
        description=v1.get("DESCRIPTION", "") or "",
        search_aliases=list(v1.get("SEARCH_ALIASES", []) or []),
        is_input_list=bool(v1.get("INPUT_IS_LIST", False)),
        is_output_node=bool(v1.get("OUTPUT_NODE", False)),
        is_deprecated=bool(v1.get("DEPRECATED", False)),
        is_experimental=bool(v1.get("EXPERIMENTAL", False)),
        not_idempotent=bool(v1.get("NOT_IDEMPOTENT", False)),
    )


def schema_for(node_id: str) -> io.Schema:
    return v1_schema(node_id, FROZEN[node_id])


# --------------------------------------------------------------------------------------------------------------- #
# Registered-but-not-converted nodes: a schema-faithful class whose execute refuses by name
# --------------------------------------------------------------------------------------------------------------- #
def _input_names(entry: dict) -> list:
    """Declared input names in schema order, read from the frozen data without building the schema."""
    types = entry["v1"]["INPUT_TYPES"]
    sections = dict(types["$dict"]) if isinstance(types, dict) and "$dict" in types else types
    names = []
    for section in ("required", "optional"):
        value = sections.get(section) or {}
        pairs = value["$dict"] if isinstance(value, dict) and "$dict" in value else list(value.items())
        names.extend(name for name, _spec in pairs)
    return names


def _validation_argument(node_id: str) -> str | None:
    """One declared input to name in validate_inputs, so core reports the refusal once per node."""
    for name in _input_names(FROZEN[node_id]):
        if isinstance(name, str) and name.isidentifier() and not keyword.iskeyword(name) and name != "cls":
            return name
    return None


REFUSAL_REASON = "not in the converted V2 set"
# Used ids that stay refused, each with its reason (SECURE_CONVERSION.md, Known differences).
REFUSAL_REASONS = {
    "MergeModels": "it merges two models' weights, and the guest SDK has no model-merge operation",
    "Fooocus_KSampler": "it patches Core's UNet forward and SDXL conditioning for the whole process while it samples",
    "Fooocus_KSamplerAdvanced": "it patches Core's UNet forward and SDXL conditioning for the whole process while it "
                                "samples",
    "AV_ControlNetPreprocessor": "its preprocessors are another pack's code (comfyui_controlnet_aux)",
    "LaMaInpaint": "the LaMa model is a TorchScript archive, which V2 does not load",
    "LoadLaMaModel": "the LaMa model is a TorchScript archive, which V2 does not load",
}


def refusal_class_name(node_id: str) -> str:
    safe = re.sub(r"\W+", "_", node_id).strip("_")
    return f"Refused_{safe}_{hashlib.sha1(node_id.encode('utf-8')).hexdigest()[:8]}"


def refusing_node(node_id: str, reason: str = REFUSAL_REASON) -> type[io.ComfyNode]:
    message = f"comfyui-art-venture/{node_id}: not converted to Secure Nodes V2 yet ({reason}); see SECURE_CONVERSION.md"

    def define_schema(cls) -> io.Schema:
        return schema_for(node_id)

    def validate_inputs(cls, **_kwargs: Any):
        return message  # refused at queue time, before anything runs

    async def execute(cls, **_kwargs: Any) -> io.NodeOutput:
        raise NotImplementedError(message)

    attrs = {
        "__module__": __name__,
        "SDK_REFS": True,
        "SDK_PERMISSIONS": (),
        "define_schema": classmethod(define_schema),
        "execute": classmethod(execute),
    }
    argument = _validation_argument(node_id)
    if argument is not None:  # a node without a nameable input is refused when it runs
        validate_inputs.__signature__ = inspect.Signature([
            inspect.Parameter("cls", inspect.Parameter.POSITIONAL_OR_KEYWORD),
            inspect.Parameter(argument, inspect.Parameter.POSITIONAL_OR_KEYWORD, default=None),
        ])
        attrs["validate_inputs"] = classmethod(validate_inputs)
    return type(refusal_class_name(node_id), (io.ComfyNode,), attrs)


# Every refusal class exists as soon as THIS module is imported. The production guest imports only the module a
# manifest row names, inside a bare namespace package (the pack's __init__.py does not run), then looks the class up
# by name. tests/test_production_load.py checks every manifest row that way.
REFUSED = {node_id: refusing_node(node_id, REFUSAL_REASONS.get(node_id, REFUSAL_REASON)) for node_id in sorted(FROZEN)}
globals().update({cls.__name__: cls for cls in REFUSED.values()})

__all__ = ["FROZEN", "MENUS", "REFUSED", "decode", "refusal_class_name", "refusing_node", "schema_for", "v1_schema"]
