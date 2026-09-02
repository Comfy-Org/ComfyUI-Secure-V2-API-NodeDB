"""Closed-boundary runtime for the pinned Basic Data Handling conversion.

The original pack passes Python containers, sets, bytes, datetimes and
timedeltas directly between nodes.  V2's wire is deliberately narrower, so
those pack-owned socket values use a small tagged representation while they
are on the host.  They are reconstructed before an upstream algorithm runs.
Host refs remain opaque except for tensor/value refs on nodes granted ``raw``.
"""
from __future__ import annotations

import copy
import base64
import datetime as _datetime
import hashlib
import inspect
import json
import pathlib
import re
import sys
from enum import Enum
from typing import Any, Awaitable, Callable

from comfy_api.latest import io, sdk
import torch


SCHEMAS = json.loads(pathlib.Path(__file__).with_name("_schemas.json").read_text())


def _io_class(io_type: str):
    for value in vars(io).values():
        if isinstance(value, type) and getattr(value, "io_type", None) == io_type:
            return value
    return io.Custom(io_type)


def _decode_value(value: Any):
    if isinstance(value, list):
        return [_decode_value(item) for item in value]
    if not isinstance(value, dict):
        return value
    tag = value.get("$type")
    if tag is None:
        return {key: _decode_value(item) for key, item in value.items()}
    if tag == "input":
        return _decode_input(value["value"])
    if tag == "output":
        return _decode_output(value["value"])
    if tag == "dynamic-option":
        return io.DynamicCombo.Option(
            value["key"], [_decode_input(item) for item in value["inputs"]]
        )
    if tag == "match-template":
        return io.MatchType.Template(
            value["template_id"],
            [_io_class(item) for item in value["allowed_types"]],
        )
    if tag == "autogrow-prefix":
        return io.Autogrow.TemplatePrefix(
            _decode_input(value["input"]),
            value["prefix"],
            value["min"],
            value["max"],
        )
    if tag == "autogrow-names":
        return io.Autogrow.TemplateNames(
            _decode_input(value["input"]), value["names"], value["min"]
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
            raise ValueError(f"unknown frozen schema enum {value['enum']!r}")
        return enum_type[value["name"]]
    if tag == "tuple":
        return tuple(_decode_value(item) for item in value["items"])
    raise ValueError(f"unknown frozen schema value tag {tag!r}")


def _decode_input(value: dict):
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
        raise ValueError(f"unknown frozen schema input kind {kind!r}")
    result = object.__new__(cls)
    result.__dict__.update(_decode_value(value["attrs"]))
    return result


def _decode_output(value: dict):
    if value["kind"] == "match-type":
        cls = io.MatchType.Output
    elif value["kind"] == "standard":
        cls = _io_class(value["io_type"]).Output
    else:
        raise ValueError(f"unknown frozen schema output kind {value['kind']!r}")
    result = object.__new__(cls)
    result.__dict__.update(_decode_value(value["attrs"]))
    return result


def schema_for(node_id: str) -> io.Schema:
    value = SCHEMAS[node_id]["schema"]
    attrs = _decode_value(copy.deepcopy(value["attrs"]))
    attrs["inputs"] = [_decode_input(item) for item in value["inputs"]]
    attrs["outputs"] = [_decode_output(item) for item in value["outputs"]]
    attrs["hidden"] = [io.Hidden[name] for name in value["hidden"]]
    return io.Schema(**attrs)


_TAG = "__comfy_secure_basic_data_handling_v1__"


def _decode_pack_value(value: Any) -> Any:
    if isinstance(value, list):
        return [_decode_pack_value(item) for item in value]
    if not isinstance(value, dict) or _TAG not in value:
        if isinstance(value, dict):
            return {key: _decode_pack_value(item) for key, item in value.items()}
        return value
    kind = value[_TAG]
    if kind == "dict":
        return {
            _decode_pack_value(key): _decode_pack_value(item)
            for key, item in value["items"]
        }
    if kind == "set":
        return set(_decode_pack_value(item) for item in value["items"])
    if kind == "frozenset":
        return frozenset(_decode_pack_value(item) for item in value["items"])
    if kind == "tuple":
        return tuple(_decode_pack_value(item) for item in value["items"])
    if kind == "bytes":
        return base64.b64decode(value["base64"], validate=True)
    if kind == "datetime":
        result = _datetime.datetime.fromisoformat(value["iso8601"])
        return result.replace(fold=int(value.get("fold", 0)))
    if kind == "timedelta":
        return _datetime.timedelta(
            days=int(value["days"]),
            seconds=int(value["seconds"]),
            microseconds=int(value["microseconds"]),
        )
    raise ValueError(f"unknown Basic Data Handling wire value {kind!r}")


def _encode_pack_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str, sdk.Ref)):
        return value
    if isinstance(value, bytes):
        return {_TAG: "bytes", "base64": base64.b64encode(value).decode("ascii")}
    if isinstance(value, _datetime.datetime):
        return {_TAG: "datetime", "iso8601": value.isoformat(), "fold": value.fold}
    if isinstance(value, _datetime.timedelta):
        return {
            _TAG: "timedelta",
            "days": value.days,
            "seconds": value.seconds,
            "microseconds": value.microseconds,
        }
    if isinstance(value, dict):
        return {
            _TAG: "dict",
            "items": [
                [_encode_pack_value(key), _encode_pack_value(item)]
                for key, item in value.items()
            ],
        }
    if isinstance(value, set):
        return {_TAG: "set", "items": [_encode_pack_value(item) for item in value]}
    if isinstance(value, frozenset):
        return {
            _TAG: "frozenset",
            "items": [_encode_pack_value(item) for item in value],
        }
    if isinstance(value, tuple):
        return {_TAG: "tuple", "items": [_encode_pack_value(item) for item in value]}
    if isinstance(value, list):
        return [_encode_pack_value(item) for item in value]
    raise TypeError(
        "Basic Data Handling cannot carry value of type "
        f"{type(value).__module__}.{type(value).__qualname__}"
    )


async def materialize(value: Any, *, tensors: bool = True) -> Any:
    if isinstance(value, sdk.TensorRef):
        return await value.raw() if tensors else value
    if isinstance(value, sdk.ValueRef):
        return await materialize(await value.value(), tensors=tensors)
    if isinstance(value, list):
        result = [await materialize(item, tensors=tensors) for item in value]
        return _decode_pack_value(result)
    if isinstance(value, tuple):
        result = tuple([await materialize(item, tensors=tensors) for item in value])
        return _decode_pack_value(result)
    if isinstance(value, dict):
        result = {
            key: await materialize(item, tensors=tensors)
            for key, item in value.items()
        }
        return _decode_pack_value(result)
    return _decode_pack_value(value)


async def wrap_output(value: Any, io_type: str, is_list: bool = False) -> Any:
    if value is None or isinstance(value, sdk.Ref):
        return value
    if is_list:
        return [await wrap_output(item, io_type) for item in value]
    if isinstance(value, torch.Tensor):
        if io_type == "IMAGE":
            return await sdk.ImageRef._from_raw(value)
        if io_type == "MASK":
            return await sdk.MaskRef._from_raw(value)
        return await sdk.TensorRef._from_raw(value)
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
    return _encode_pack_value(value)


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
            f"{node_id} returned {len(values)} outputs; schema declares "
            f"{len(outputs)}"
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
    check_lazy_status: Handler | None = None,
    fingerprint_inputs: Handler | None = None,
    validate_inputs: Handler | None = None,
    module: str | None = None,
) -> type[io.ComfyNode]:
    definition = SCHEMAS[node_id]

    def define_schema(cls) -> io.Schema:
        return schema_for(node_id)

    async def execute(cls, **kwargs: Any) -> io.NodeOutput:
        hidden = getattr(cls, "hidden", None)
        for name in definition.get("hidden_parameters", ()):
            kwargs[name] = getattr(hidden, name, None)
        result = await handler(**kwargs)
        return await node_output(node_id, result)

    async def check_lazy(cls, **kwargs: Any):
        result = check_lazy_status(**kwargs)
        return await result if inspect.isawaitable(result) else result

    async def fingerprint(cls, **kwargs: Any):
        result = fingerprint_inputs(**kwargs)
        return await result if inspect.isawaitable(result) else result

    async def validate(cls, **kwargs: Any):
        result = validate_inputs(**kwargs)
        return await result if inspect.isawaitable(result) else result

    class_name = re.sub(r"\W+", "_", definition["class"])
    suffix = hashlib.sha1(node_id.encode("utf-8")).hexdigest()[:10]
    class_name = f"{class_name}Secure_{suffix}"
    owner = module or handler.__module__
    attrs = {
        "__module__": owner,
        "SDK_REFS": True,
        "SDK_PERMISSIONS": tuple(permissions),
        "SDK_REQUIRED_WEIGHTS": tuple(required_weights),
        "define_schema": classmethod(define_schema),
        "execute": classmethod(execute),
    }
    if check_lazy_status is not None:
        attrs["check_lazy_status"] = classmethod(check_lazy)
    if fingerprint_inputs is not None:
        attrs["fingerprint_inputs"] = classmethod(fingerprint)
    if validate_inputs is not None:
        attrs["validate_inputs"] = classmethod(validate)
    generated = type(
        class_name,
        (io.ComfyNode,),
        attrs,
    )
    target = sys.modules.get(owner)
    if target is not None:
        setattr(target, class_name, generated)
    return generated


def unsupported(node_id: str, reason: str) -> Handler:
    async def execute(**_kwargs):
        raise RuntimeError(f"{node_id} is not available in this secure build: {reason}")

    return execute


__all__ = [
    "SCHEMAS",
    "bind_node",
    "io",
    "materialize",
    "node_output",
    "schema_for",
    "sdk",
    "unsupported",
    "wrap_output",
]
