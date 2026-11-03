"""Secure Nodes V2: RES4LYF's sigma nodes Sigmas From Text, Sigmas Split Value, Sigmas Rescale, Sigmas Easing and
Sigmas Resample (upstream 057a913e).

Each runs upstream's own class, copied verbatim into res4lyf_core (sigmas_values.py and sigmas_resample.py; see
VENDOR.json), on the exact input schedule in its own dtype, and returns what upstream returns. Sigmas Resample's
"model" mode trains upstream's small network from torch's global random generator, which upstream never seeds. Here
that is the guest's generator, not the host's (see SECURE_CONVERSION.md). Given the same generator state, both
versions return the same schedule.

sigmas_resample.py imports scipy at module level, as upstream's sigmas.py does, so Sigmas Resample imports it only
when it runs. scipy is in the pack's declared dependency profile (pyproject.toml).
"""
from __future__ import annotations

from typing import Any

from comfy_api.latest import io, sdk

from ._secure_runtime import schema_for
from .res4lyf_core import sigmas_values
from .res4lyf_core._comfy._refuse import OutOfEnvelope


async def _schedule(node_id: str, sigmas: Any):
    if sigmas is None:
        raise OutOfEnvelope(f"RES4LYF/{node_id}: sigmas must be connected")
    return await sigmas.raw()


class SigmasFromTextV2(io.ComfyNode):
    """sigmas.py:339-362 (sigmas_from_text.main), verbatim, in the guest."""
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return schema_for("Sigmas From Text")

    @classmethod
    async def execute(cls, text: str = "") -> io.NodeOutput:
        (sigmas,) = sigmas_values.sigmas_from_text().main(text=text)
        return io.NodeOutput(await sdk.SigmasRef._from_raw(sigmas))


class SigmasSplitValueV2(io.ComfyNode):
    """sigmas.py:3998-4057 (sigmas_split_value.main), verbatim, in the guest."""
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return schema_for("Sigmas Split Value")

    @classmethod
    async def execute(cls, sigmas: Any = None, split_value: float = 0.875, bias_split_up: bool = False
                      ) -> io.NodeOutput:
        schedule = await _schedule("Sigmas Split Value", sigmas)
        high, low = sigmas_values.sigmas_split_value().main(sigmas=schedule, split_value=split_value,
                                                            bias_split_up=bias_split_up)
        return io.NodeOutput(await sdk.SigmasRef._from_raw(high), await sdk.SigmasRef._from_raw(low))


class SigmasRescaleV2(io.ComfyNode):
    """sigmas.py:774-800 (sigmas_rescale.main), verbatim, in the guest."""
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return schema_for("Sigmas Rescale")

    @classmethod
    async def execute(cls, start: float = 1.0, end: float = 0.0, sigmas: Any = None) -> io.NodeOutput:
        schedule = await _schedule("Sigmas Rescale", sigmas)
        (result,) = sigmas_values.sigmas_rescale().main(start=start, end=end, sigmas=schedule)
        return io.NodeOutput(await sdk.SigmasRef._from_raw(result))


class SigmasEasingV2(io.ComfyNode):
    """sigmas.py:1480-1655 (sigmas_easing.main), verbatim, in the guest."""
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return schema_for("Sigmas Easing")

    @classmethod
    async def execute(cls, sigmas: Any = None, easing_type: str = "cubic", easing_mode: str = "in_out",
                      normalize_input: bool = True, normalize_output: bool = True, strength: float = 1.0
                      ) -> io.NodeOutput:
        schedule = await _schedule("Sigmas Easing", sigmas)
        (result,) = sigmas_values.sigmas_easing().main(sigmas=schedule, easing_type=easing_type,
                                                       easing_mode=easing_mode, normalize_input=normalize_input,
                                                       normalize_output=normalize_output, strength=strength)
        return io.NodeOutput(await sdk.SigmasRef._from_raw(result))


class SigmasResampleV2(io.ComfyNode):
    """sigmas.py:122-270 (sigmas_interpolate.main, registered as "Sigmas Resample"), verbatim, in the guest."""
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return schema_for("Sigmas Resample")

    @classmethod
    async def execute(cls, sigmas_in: Any = None, output_length: int = 0, mode: str = "linear", order: int = 8,
                      rescale_after: bool = True) -> io.NodeOutput:
        from .res4lyf_core import sigmas_resample  # imports scipy, as upstream's sigmas.py does

        schedule = await _schedule("Sigmas Resample", sigmas_in)
        (result,) = sigmas_resample.sigmas_interpolate().main(sigmas_in=schedule, output_length=output_length,
                                                              mode=mode, order=order, rescale_after=rescale_after)
        return io.NodeOutput(await sdk.SigmasRef._from_raw(result))


CONVERTED = {
    "Sigmas Easing": SigmasEasingV2,
    "Sigmas From Text": SigmasFromTextV2,
    "Sigmas Resample": SigmasResampleV2,
    "Sigmas Rescale": SigmasRescaleV2,
    "Sigmas Split Value": SigmasSplitValueV2,
}

__all__ = ["CONVERTED", "SigmasEasingV2", "SigmasFromTextV2", "SigmasResampleV2", "SigmasRescaleV2",
           "SigmasSplitValueV2"]
