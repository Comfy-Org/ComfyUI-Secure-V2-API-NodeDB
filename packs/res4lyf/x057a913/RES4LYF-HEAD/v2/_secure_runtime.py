"""Frozen-schema runtime for the RES4LYF Secure Nodes V2 pack.

_frozen_nodes.json holds every node declaration of upstream RES4LYF 057a913e, frozen in the gate from the
original package (tests/freeze_all.py) on ComfyUI core 6257422b, except the ids core registers itself
(meta.core_owned, checked by tests/test_core_ids.py):
- V1 nodes (INPUT_TYPES/RETURN_TYPES) become V3 schemas through ``v1_schema``.
- The seven V3 nodes are rebuilt from their frozen Input/Output objects.
``tests/test_res4lyf_schemas.py`` checks both against the original's served node info.

Importing this module alone defines the refusal class of every registered id (``REFUSED``) at module level,
under the class name its manifest row names. The guest imports only that module; the pack's __init__.py never
runs there. ``tests/test_production_load.py`` checks every manifest row that way.
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

FROZEN = json.loads(pathlib.Path(__file__).with_name("_frozen_nodes.json").read_text())["nodes"]


# --------------------------------------------------------------------------------------------------------------- #
# Tagged JSON -> Python values
# --------------------------------------------------------------------------------------------------------------- #
def _io_class(info: dict):
    """Resolve a frozen io class. Core's comfytype decorator clones each nested Input/Output class, so its
    qualname is the generic base's (e.g. "ComfyTypeIO.Output"); the owning comfytype is recorded separately."""
    qual = info["qualname"]
    parent = info.get("parent")
    parent_io = info.get("parent_io_type")
    role = qual.rsplit(".", 1)[-1]
    if parent is not None:
        owner = getattr(io, parent, None)
        if owner is not None and getattr(owner, "io_type", None) == parent_io:
            return getattr(owner, role)
        return getattr(io.Custom(parent_io), role)  # io.Custom(<type>) classes are created per call
    obj = io
    for part in qual.split("."):
        obj = getattr(obj, part)
    return obj


def decode(value: Any) -> Any:
    if isinstance(value, list):
        return [decode(item) for item in value]
    if not isinstance(value, dict):
        return value
    if "$float" in value:
        return float(value["$float"])
    if "$tuple" in value:
        return tuple(decode(item) for item in value["$tuple"])
    if "$list" in value:  # list subclasses (RES4LYF's DualFormatList) cross as plain lists; see SECURE_CONVERSION.md
        return [decode(item) for item in value["$list"]]
    if "$dict" in value:
        return {decode(k): decode(v) for k, v in value["$dict"]}
    if "$enum" in value:
        enum_type = getattr(io, value["$enum"])
        return enum_type[value["name"]]
    if "$io" in value:
        cls = _io_class(value["$io"])
        obj = object.__new__(cls)
        obj.__dict__.update({k: decode(v) for k, v in value["attrs"].items()})
        return obj
    if "$opaque" in value:
        raise ValueError(f"frozen value {value['$opaque']} is opaque")
    if any(isinstance(key, str) and key.startswith("$") for key in value):
        raise ValueError(f"unknown frozen tag {sorted(value)}")
    # untagged containers are the freezer's own records; their values are encoded
    return {key: decode(item) for key, item in value.items()}


# --------------------------------------------------------------------------------------------------------------- #
# V1 declaration -> V3 schema
# --------------------------------------------------------------------------------------------------------------- #
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


def v1_input(name: str, spec, optional: bool):
    spec = list(spec) if isinstance(spec, (list, tuple)) else [spec]
    type_ = spec[0]
    opts = dict(spec[1]) if len(spec) > 1 and isinstance(spec[1], dict) else {}
    common = _common(opts, optional)
    # Choice lists: RES4LYF declares some as tuples (e.g. NOISE_GENERATOR_NAMES); the server serves both as lists.
    if isinstance(type_, (list, tuple)):
        return io.Combo.Input(name, options=list(type_), default=opts.pop("default", None),
                              control_after_generate=opts.pop("control_after_generate", None),
                              extra_dict=opts, **common)
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
        # multiline stays None (pruned) unless declared, as the original serves it
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
            inputs.append(v1_input(name, spec, section == "optional"))
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
        if isinstance(rtype, list):
            outputs.append(io.Combo.Output(options=list(rtype), **kwargs))
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


def v3_schema(node_id: str, entry: dict) -> io.Schema:
    frozen = entry["schema"]
    attrs = {k: decode(v) for k, v in frozen["attrs"].items()}
    attrs["inputs"] = [decode(item) for item in frozen["inputs"]]
    attrs["outputs"] = [decode(item) for item in frozen["outputs"]]
    attrs["hidden"] = [io.Hidden[name] for name in frozen["hidden"]]
    return io.Schema(**attrs)


def schema_for(node_id: str) -> io.Schema:
    entry = FROZEN[node_id]
    return v3_schema(node_id, entry) if entry["api"] == "v3" else v1_schema(node_id, entry)


# --------------------------------------------------------------------------------------------------------------- #
# Registered-but-not-converted nodes: a schema-faithful class whose execute refuses by name
# --------------------------------------------------------------------------------------------------------------- #
def _input_names(entry: dict) -> list:
    """Declared input names in schema order, read from the frozen data without building the schema."""
    if entry["api"] == "v3":
        return [item["attrs"].get("id") for item in entry["schema"]["inputs"]]
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
# Used ids that stay refused for a reason of their own
REFUSAL_REASONS = {
    "Image Sharpen FS": (
        "it blurs with OpenCV (cv2.medianBlur / cv2.GaussianBlur, images.py:816 and :844), which the guest does not "
        "have, and it moves its frequency-separation blend to CUDA unconditionally (images.py:472-475 and :701-704), "
        "so the original fails on any host without CUDA"),
    "ReSDPatcher": (
        "it patches the model by swapping the classes of the diffusion model's own modules for RES4LYF's "
        "(models.py:622-647), which is not a model transform the SDK offers, and its style code moves tensors to "
        "CUDA unconditionally (style_transfer.py:428), so the original fails on any host without CUDA"),
    "SigmasPreview": (
        "it draws its plot with matplotlib (helper_sigma_preview_image_preproc.py:126-139), which the guest does "
        "not have, and no byte-exact drawing without it exists yet"),
    "Image Gaussian Blur": (
        "it blurs with OpenCV (cv2.GaussianBlur, images.py:844), which the guest does not have"),
    "Latent to Cuda": (
        "it moves the latent's tensors to a device it names, CUDA or the CPU (nodes_latents.py:707-750); where a V2 "
        "latent lives is the host's choice, and on a host without CUDA the original fails"),
}


def refusal_class_name(node_id: str) -> str:
    safe = re.sub(r"\W+", "_", node_id).strip("_")
    return f"Refused_{safe}_{hashlib.sha1(node_id.encode('utf-8')).hexdigest()[:8]}"


def refusing_node(node_id: str, reason: str = REFUSAL_REASON) -> type[io.ComfyNode]:
    message = f"RES4LYF/{node_id}: not converted to Secure Nodes V2 yet ({reason}); see SECURE_CONVERSION.md"

    def define_schema(cls) -> io.Schema:
        return schema_for(node_id)

    def validate_inputs(cls, **_kwargs: Any):
        # Refuse at queue time, before anything runs. Core forwards only the one input named in the signature
        # below and keeps its own checks for the others.
        return message

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
# manifest row names, inside a bare namespace package (the pack's __init__.py does not run;
# guest/__init__.py:1315-1360), then looks the class up by name (:1484-1490).
REFUSED = {node_id: refusing_node(node_id, REFUSAL_REASONS.get(node_id, REFUSAL_REASON)) for node_id in sorted(FROZEN)}
globals().update({cls.__name__: cls for cls in REFUSED.values()})

__all__ = ["FROZEN", "REFUSED", "decode", "refusal_class_name", "refusing_node", "schema_for", "v1_schema",
           "v3_schema"]
