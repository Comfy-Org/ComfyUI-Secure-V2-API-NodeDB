"""Frozen node schemas for ComfyUI_Mira (pin dfb1c847), decoded for the guest.

_frozen_schemas.json holds each registered node's schema exactly as the secure-node manifest encodes it
(comfy_secure_nodes.packmanifest.encode_schema), frozen in the lane gate from the original classes.
The decoder below is a copy of that module's decoder (packmanifest.py, live overlay, sha256
4c6772a301c48c7ae224ac1eb715e14881c4dc19b95694b788b11097e21f16d2: _io_class, _decode_value,
_decode_input, _decode_output, decode_schema), so a schema read here is the one the host reads from
secure-nodes.json. It uses only the public `io` module.
"""
import json
import pathlib
from enum import Enum

from comfy_api.latest import io

_SCHEMAS = json.loads(pathlib.Path(__file__).with_name("_frozen_schemas.json").read_text(encoding="utf-8"))


def _io_class(io_type: str):
    for value in vars(io).values():
        if isinstance(value, type) and getattr(value, "io_type", None) == io_type:
            return value
    return io.Custom(io_type)


def _decode_value(value):
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
            value["key"], [_decode_input(item) for item in value["inputs"]])
    if tag == "match-template":
        return io.MatchType.Template(
            value["template_id"],
            [_io_class(item) for item in value["allowed_types"]],
        )
    if tag == "autogrow-prefix":
        return io.Autogrow.TemplatePrefix(
            _decode_input(value["input"]), value["prefix"],
            value["min"], value["max"])
    if tag == "autogrow-names":
        return io.Autogrow.TemplateNames(
            _decode_input(value["input"]), value["names"], value["min"])
    if tag == "remote-options":
        remote = object.__new__(io.RemoteOptions)
        remote.__dict__.update(_decode_value(value["attrs"]))
        return remote
    if tag == "io-class":
        return _io_class(value["io_type"])
    if tag == "enum":
        enum_type = getattr(io, value["enum"], None)
        if not isinstance(enum_type, type) or not issubclass(enum_type, Enum):
            raise ValueError(f"unknown manifest enum {value['enum']!r}")
        return enum_type[value["name"]]
    if tag == "tuple":
        return tuple(_decode_value(item) for item in value["items"])
    raise ValueError(f"unknown manifest value tag {tag!r}")


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
        raise ValueError(f"unknown manifest input kind {kind!r}")
    result = object.__new__(cls)
    result.__dict__.update(_decode_value(value["attrs"]))
    return result


def _decode_output(value: dict):
    if value["kind"] == "match-type":
        cls = io.MatchType.Output
    elif value["kind"] == "standard":
        cls = _io_class(value["io_type"]).Output
    else:
        raise ValueError(f"unknown manifest output kind {value['kind']!r}")
    result = object.__new__(cls)
    result.__dict__.update(_decode_value(value["attrs"]))
    return result


def decode_schema(value: dict):
    attrs = _decode_value(value["attrs"])
    attrs["inputs"] = [_decode_input(item) for item in value["inputs"]]
    attrs["outputs"] = [_decode_output(item) for item in value["outputs"]]
    attrs["hidden"] = [io.Hidden[name] for name in value["hidden"]]
    return io.Schema(**attrs)


def schema_for(node_id: str):
    """A fresh io.Schema for one registered node."""
    return decode_schema(_SCHEMAS[node_id])
