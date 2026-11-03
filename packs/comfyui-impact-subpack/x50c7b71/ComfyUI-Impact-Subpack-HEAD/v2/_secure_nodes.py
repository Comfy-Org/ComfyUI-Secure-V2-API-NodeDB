"""Secure detector provider for Impact Subpack (fidelity repair r1).

UltralyticsDetectorProvider accepts any model in the host's Ultralytics catalogues, as upstream does, and
returns plain descriptors: the catalogue and name of the selected weight. Impact Pack's v2 reads that weight
through the engine (converted safetensors with Ultralytics metadata), rebuilds the model in its own guest and
runs upstream Impact Subpack detection code there. This provider loads nothing.
"""
from __future__ import annotations

from typing import Any

from ._secure_runtime import SCHEMAS, io, schema_for, sdk

# Impact Subpack modules/subpack_nodes.py, UltralyticsDetectorProvider.doit: the "ultralytics" catalogue first,
# then ultralytics_bbox or ultralytics_segm by the name's "bbox/" or "segm/" prefix.
_PREFIXED = (("bbox/", "ultralytics_bbox"), ("segm/", "ultralytics_segm"))
_MENU = "/models/ultralytics_bbox"


async def _exists(folder: str, name: str) -> bool:
    try:
        return bool(await sdk.ctx().assets.exists(folder, name))
    except PermissionError:
        raise
    except Exception:  # a catalogue this host does not register
        return False


async def _locate(model_name: str) -> tuple[str, str] | None:
    if await _exists("ultralytics", model_name):
        return "ultralytics", model_name
    for prefix, folder in _PREFIXED:
        if model_name.startswith(prefix):
            name = model_name[len(prefix):]
            return (folder, name) if await _exists(folder, name) else None
    # A host menu lists a catalogue's own names and cannot add upstream's "bbox/" prefix, so the menu below
    # offers bare ultralytics_bbox names; a bare name is a bbox model.
    return ("ultralytics_bbox", model_name) if await _exists("ultralytics_bbox", model_name) else None


def _not_found(model_name: str) -> str:
    return f"[Impact Subpack] model file '{model_name}' is not found."


class UltralyticsDetectorProvider(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("assets",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        schema = schema_for("UltralyticsDetectorProvider")
        item = next(entry for entry in schema.inputs if entry.id == "model_name")
        # The host fills this menu from its ultralytics_bbox catalogue. Upstream's own menu is
        # "bbox/<file>" + "segm/<file>"; validate_inputs accepts those saved values too.
        item.options = []
        item.default = None
        item.remote = io.RemoteOptions(route=_MENU, refresh_button=True)
        return schema

    @classmethod
    async def validate_inputs(cls, model_name=None):
        # Naming model_name makes Core skip its menu check, so saved "bbox/..." and "segm/..." values validate;
        # this resolves them the way upstream doit does.
        if model_name is None:
            return True
        return True if await _locate(str(model_name)) is not None else _not_found(str(model_name))

    @classmethod
    async def execute(cls, model_name: str, **_kwargs: Any) -> io.NodeOutput:
        model_name = str(model_name)
        located = await _locate(model_name)
        if located is None:
            raise ValueError(_not_found(model_name))
        folder, name = located
        detector = {"folder": folder, "name": name, "model_name": model_name}
        bbox = {"secure_kind": "impact.ultralytics_bbox", **detector}
        # Upstream: a "bbox..." name gives (UltraBBoxDetector, NO_SEGM_DETECTOR); any other name also gives an
        # UltraSegmDetector over the same model. A bare menu name is a bbox model (see _locate). Here None
        # stands for NO_SEGM_DETECTOR, as before this repair.
        if model_name.startswith("bbox") or (folder == "ultralytics_bbox" and not model_name.startswith("segm/")):
            return io.NodeOutput(bbox, None)
        return io.NodeOutput(bbox, {"secure_kind": "impact.ultralytics_segm", **detector})


NODE_CLASS_MAPPINGS = {
    "UltralyticsDetectorProvider": UltralyticsDetectorProvider,
}

NODE_DISPLAY_NAME_MAPPINGS = {}


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "SCHEMAS"]
