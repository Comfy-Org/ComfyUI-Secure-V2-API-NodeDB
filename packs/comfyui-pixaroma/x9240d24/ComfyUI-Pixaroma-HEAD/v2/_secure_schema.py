"""Rebuild the complete, gate-frozen original schemas using the public io API."""
import json
from pathlib import Path

from comfy_api.latest import io

_ROWS = json.loads((Path(__file__).parent / "_frozen_schemas.json").read_text("utf-8"))


def schema_for(node_id):
    row = _ROWS[node_id]
    original = row["schema"]
    attrs = dict(original["attrs"])
    attrs["description"] = row["description"]
    attrs["inputs"] = [_input(value) for value in original["inputs"]]
    attrs["outputs"] = [
        io.Custom(value["io_type"]).Output(**value["attrs"])
        for value in original["outputs"]
    ]
    attrs["hidden"] = [io.Hidden[value] for value in original["hidden"]]
    return io.Schema(**attrs)


def _input(value):
    if value["kind"] != "standard":
        raise ValueError("Unrecognized frozen input kind: " + value["kind"])
    attrs = {key: item for key, item in value["attrs"].items() if item is not None}
    if "rawLink" in attrs:
        attrs["raw_link"] = attrs.pop("rawLink")
    # These are constructor-owned attributes, included by the encoder, rather
    # than keywords accepted by the selected public SDK constructors.
    attrs.pop("widget_type", None)
    attrs.pop("multiselect", None)
    kind = value["io_type"]
    factory = {
        "INT": io.Int, "FLOAT": io.Float, "STRING": io.String,
        "BOOLEAN": io.Boolean, "COMBO": io.Combo,
    }.get(kind)
    if factory is None:
        factory = io.Custom(kind)
    if "display_mode" in attrs:
        display = attrs["display_mode"]
        attrs["display_mode"] = io.NumberDisplay[display["name"]]
    if "upload" in attrs:
        attrs["upload"] = io.UploadType(attrs["upload"])
    if "image_folder" in attrs:
        attrs["image_folder"] = io.FolderType(attrs["image_folder"])
    if "remote" in attrs:
        attrs["remote"] = io.RemoteOptions(**attrs["remote"])
    return factory.Input(**attrs)
