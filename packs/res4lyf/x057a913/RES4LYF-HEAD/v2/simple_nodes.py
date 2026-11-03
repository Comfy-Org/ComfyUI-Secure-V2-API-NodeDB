"""Secure Nodes V2: RES4LYF's small value nodes, ported exactly (bodies copied from upstream 057a913e).

Each class serves the original's frozen schema (_secure_runtime.schema_for) and computes what the original computes,
in the same types and dtypes. Inputs the original passes on, but a V2 output cannot carry, are refused by name.
"""
from __future__ import annotations

from typing import Any

from comfy_api.latest import io, sdk

from ._secure_runtime import schema_for
from .res4lyf_core._comfy._refuse import OutOfEnvelope


class TextBox1V2(io.ComfyNode):
    """nodes_misc.py:55-75 (TextBox1.main returns its text unchanged)."""
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return schema_for("TextBox1")

    @classmethod
    async def execute(cls, text1: str = "") -> io.NodeOutput:
        return io.NodeOutput(text1)


class SetImageSizeWithScaleV2(io.ComfyNode):
    """nodes_misc.py:31-52 (SetImageSizeWithScale.main)."""
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return schema_for("SetImageSizeWithScale")

    @classmethod
    async def execute(cls, width: int = 1024, height: int = 1024, scale_by: float = 1.0) -> io.NodeOutput:
        return io.NodeOutput(width, height, int(width * scale_by), int(height * scale_by))


class SigmasPowerV2(io.ComfyNode):
    """sigmas.py:695-713 (sigmas_power.main: ``sigmas ** power``), on the exact input tensor in its own dtype."""
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return schema_for("Sigmas Power")

    @classmethod
    async def execute(cls, sigmas: Any = None, power: float = 1.0) -> io.NodeOutput:
        if sigmas is None:
            raise OutOfEnvelope("RES4LYF/Sigmas Power: sigmas must be connected")
        tensor = await sigmas.raw()
        result = tensor ** power
        return io.NodeOutput(await sdk.SigmasRef._from_raw(result))


__all__ = ["SetImageSizeWithScaleV2", "SigmasPowerV2", "TextBox1V2"]
