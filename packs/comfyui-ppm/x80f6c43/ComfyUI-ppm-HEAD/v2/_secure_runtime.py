"""Frozen-schema helpers for the pinned ComfyUI-ppm Secure Nodes V2 pack."""
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


def _decode_value(value: Any) -> Any:
    if isinstance(value, list):
        return [_decode_value(item) for item in value]
    if not isinstance(value, dict):
        return value
    tag = value.get("$type")
    if tag is None:
        return {key: _decode_value(item) for key, item in value.items()}
    if tag == "input":
        return _input(value["value"])
    if tag == "output":
        return _output(value["value"])
    if tag == "dynamic-option":
        return io.DynamicCombo.Option(
            value["key"], [_input(item) for item in value["inputs"]]
        )
    if tag == "match-template":
        return io.MatchType.Template(
            value["template_id"],
            [_io_class(item) for item in value["allowed_types"]],
        )
    if tag == "autogrow-prefix":
        return io.Autogrow.TemplatePrefix(
            _input(value["input"]),
            value["prefix"],
            value["min"],
            value["max"],
        )
    if tag == "autogrow-names":
        return io.Autogrow.TemplateNames(
            _input(value["input"]), value["names"], value["min"]
        )
    if tag == "remote-options":
        remote = object.__new__(io.RemoteOptions)
        remote.__dict__.update(_decode_value(value["attrs"]))
        return remote
    if tag == "io-class":
        return _io_class(value["io_type"])
    if tag == "enum":
        enum_type = getattr(io, value["enum"], None)
        if not isinstance(enum_type, type) or not issubclass(enum_type, Enum):
            raise ValueError(f"unknown frozen enum {value['enum']!r}")
        return enum_type[value["name"]]
    if tag == "tuple":
        return tuple(_decode_value(item) for item in value["items"])
    raise ValueError(f"unknown frozen schema tag {tag!r}")


def _input(value: dict[str, Any]):
    kind = value["kind"]
    if kind == "dynamic-combo":
        cls = io.DynamicCombo.Input
    elif kind == "autogrow":
        cls = io.Autogrow.Input
    elif kind == "match-type":
        cls = io.MatchType.Input
    elif kind == "multi-type":
        cls = io.MultiType.Input
    elif kind == "standard":
        cls = _io_class(value["io_type"]).Input
    else:
        raise ValueError(f"unknown frozen input kind {kind!r}")
    attrs = _decode_value(copy.deepcopy(value["attrs"]))
    # The source's legacy declarations use ``(IO.COMBO,
    # {"options": [...]})``.  The mechanical freezer preserves those keys in
    # ``extra_dict``; normalize them back to the equivalent V3 Combo fields so
    # the secure host renders and validates the same dropdown choices.
    if kind == "standard" and value["io_type"] == "COMBO":
        extras = dict(attrs.get("extra_dict") or {})
        if attrs.get("options") is None and isinstance(extras.get("options"), list):
            attrs["options"] = extras.pop("options")
        if attrs.get("default") is None and "default" in extras:
            attrs["default"] = extras.pop("default")
        attrs["extra_dict"] = extras
    result = object.__new__(cls)
    result.__dict__.update(attrs)
    return result


def _output(value: dict[str, Any]):
    if value["kind"] == "match-type":
        cls = io.MatchType.Output
    elif value["kind"] == "standard":
        cls = _io_class(value["io_type"]).Output
    else:
        raise ValueError(f"unknown frozen output kind {value['kind']!r}")
    result = object.__new__(cls)
    result.__dict__.update(_decode_value(copy.deepcopy(value["attrs"])))
    return result


def schema_for(node_id: str) -> io.Schema:
    value = SCHEMAS[node_id]["schema"]
    attrs = _decode_value(copy.deepcopy(value["attrs"]))
    attrs["inputs"] = [_input(item) for item in value["inputs"]]
    attrs["outputs"] = [_output(item) for item in value["outputs"]]
    attrs["hidden"] = [io.Hidden[name] for name in value["hidden"]]

    # Upstream's two JS-grown input surfaces predate io.Autogrow and omit the
    # extra sockets from their static schemas.  The V2 guest must still receive
    # those host-validated inputs after the iframe extension materializes them.
    if node_id in {"AttentionCouplePPM", "MaskCompositePPM"}:
        attrs["accept_all_inputs"] = True
    return io.Schema(**attrs)


async def _wrap(value: Any, io_type: str, is_list: bool) -> Any:
    if value is None or isinstance(value, sdk.Ref):
        return value
    if is_list:
        if not isinstance(value, (tuple, list)):
            raise TypeError(f"{io_type} list output must be a list")
        return [await _wrap(item, io_type, False) for item in value]
    if io_type == "IMAGE":
        return await sdk.ImageRef._from_raw(value)
    if io_type == "MASK":
        return await sdk.MaskRef._from_raw(value)
    if io_type == "LATENT":
        return await sdk.LatentRef.from_value(value)
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


Handler = Callable[..., Awaitable[Any] | Any]


def bind_node(
    node_id: str,
    handler: Handler,
    *,
    permissions: tuple[str, ...] = (),
    always_changed: bool = False,
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
    attrs: dict[str, Any] = {
        "__module__": handler.__module__,
        "SDK_REFS": True,
        "SDK_PERMISSIONS": tuple(permissions),
        "SDK_REQUIRED_WEIGHTS": (),
        "define_schema": classmethod(define_schema),
        "execute": classmethod(execute),
    }
    if always_changed:
        # A closure is prompt-scoped.  Returning NaN makes the host rerun this
        # attachment node for every prompt instead of reusing a MODEL/CLIP/
        # SAMPLER whose sandbox function was released with an older prompt.
        def fingerprint_inputs(cls, **_kwargs: Any) -> float:
            return float("nan")

        attrs["fingerprint_inputs"] = classmethod(fingerprint_inputs)
    generated = type(f"{class_name}Secure_{suffix}", (io.ComfyNode,), attrs)
    owner = sys.modules.get(handler.__module__)
    if owner is not None:
        setattr(owner, generated.__name__, generated)
    return generated


__all__ = ["SCHEMAS", "bind_node", "io", "schema_for", "sdk"]
