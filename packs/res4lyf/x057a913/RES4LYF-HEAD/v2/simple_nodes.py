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


class TextBox2V2(io.ComfyNode):
    """nodes_misc.py:77-98 (TextBox2.main returns its two texts unchanged)."""
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return schema_for("TextBox2")

    @classmethod
    async def execute(cls, text1: str = "", text2: str = "") -> io.NodeOutput:
        return io.NodeOutput(text1, text2)


class TextConcatenateV2(io.ComfyNode):
    """nodes_misc.py:316-337 (TextConcatenate.main: ``text_1 + separator + text_2``; unlinked texts are "")."""
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return schema_for("TextConcatenate")

    @classmethod
    async def execute(cls, text_1: str = "", text_2: str = "", separator: str = "") -> io.NodeOutput:
        return io.NodeOutput(text_1 + separator + text_2)


class SetImageSizeV2(io.ComfyNode):
    """nodes_misc.py:8-28 (SetImageSize.main returns its width and height unchanged)."""
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return schema_for("SetImageSize")

    @classmethod
    async def execute(cls, width: int = 1024, height: int = 1024) -> io.NodeOutput:
        return io.NodeOutput(width, height)


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


class SigmasMultV2(io.ComfyNode):
    """sigmas.py:609-633 (sigmas_mult.main: ``sigmas * sigmas2 * multiplier`` or ``sigmas * multiplier``), on the
    exact input tensors in their own dtypes."""
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return schema_for("Sigmas Mult")

    @classmethod
    async def execute(cls, sigmas: Any = None, multiplier: float = 1, sigmas2: Any = None) -> io.NodeOutput:
        if sigmas is None:
            raise OutOfEnvelope("RES4LYF/Sigmas Mult: sigmas must be connected")
        tensor = await sigmas.raw()
        if sigmas2 is not None:
            result = tensor * (await sigmas2.raw()) * multiplier
        else:
            result = tensor * multiplier
        return io.NodeOutput(await sdk.SigmasRef._from_raw(result))


class SeedGeneratorV2(io.ComfyNode):
    """nodes_misc.py:373-390 (SeedGenerator.main returns ``(seed, seed+1)``)."""
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return schema_for("SeedGenerator")

    @classmethod
    async def execute(cls, seed: int = 0) -> io.NodeOutput:
        return io.NodeOutput(seed, seed + 1)


__all__ = ["SeedGeneratorV2", "SetImageSizeV2", "SetImageSizeWithScaleV2", "SigmasMultV2", "SigmasPowerV2",
           "TextBox1V2", "TextBox2V2", "TextConcatenateV2"]
