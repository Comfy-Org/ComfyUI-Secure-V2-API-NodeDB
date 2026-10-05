"""Secure Nodes V2 implementation of ComfyUI Simple Switch."""

from __future__ import annotations

from typing import Any

from comfy_api.latest import io, sdk

_INPUT_IDS = tuple(f"input{index:02d}" for index in range(1, 7))


def _schema(
    node_id: str,
    display_name: str,
    input_type: type,
    output_type: type,
) -> io.Schema:
    return io.Schema(
        node_id=node_id,
        display_name=display_name,
        category="Simple Switch",
        inputs=[input_type.Input(name, optional=True) for name in _INPUT_IDS],
        outputs=[output_type.Output("output", display_name="output")],
    )


async def _materialize(value: Any) -> Any:
    if isinstance(value, sdk.ValueRef):
        return await value.value()
    return value


async def _is_none(value: Any) -> bool:
    if value is None:
        return True
    materialized = await _materialize(value)
    if (
        type(materialized) is dict
        and "model" in materialized
        and "clip" in materialized
    ):
        return not materialized or all(
            item is None for item in materialized.values()
        )
    return False


def _latent_details(value: Any) -> tuple[Any, Any, bool, Any]:
    if type(value) is not dict:
        return None, None, False, None
    samples = value.get("samples")
    nested = bool(getattr(samples, "is_nested", False))
    ndim = getattr(samples, "ndim", None)
    # NestedTensor deliberately raises when its shape property is read. The
    # upstream accepts nested AV values before formatting diagnostics, so do
    # the same and never probe that unsupported property.
    shape = None if nested else getattr(samples, "shape", None)
    return samples, ndim, nested, shape


def _describe_latent(value: Any, index: int) -> str:
    if type(value) is not dict:
        return f"input{index:02d}=non-latent:{type(value).__name__}"
    samples, ndim, nested, shape = _latent_details(value)
    if samples is None:
        return f"input{index:02d}=latent-without-samples"
    latent_type = value.get("type", "unknown")
    return (
        f"input{index:02d}=type:{latent_type},nested:{nested},"
        f"ndim:{ndim},shape:{tuple(shape) if shape is not None else 'unknown'}"
    )


class SimpleSwitch(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return _schema(
            "SimpleSwitch",
            "Simple Switch (6 Inputs)",
            io.AnyType,
            io.AnyType,
        )

    @classmethod
    async def execute(cls, **inputs: Any) -> io.NodeOutput:
        for name in _INPUT_IDS:
            candidate = inputs.get(name)
            if not await _is_none(candidate):
                return io.NodeOutput(candidate)
        return io.NodeOutput(None)


class SimpleLatentSwitch(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return _schema(
            "SimpleLatentSwitch",
            "Simple Latent Switch (6 Inputs)",
            io.Latent,
            io.Latent,
        )

    @classmethod
    def execute(cls, **inputs: Any) -> io.NodeOutput:
        for name in _INPUT_IDS:
            candidate = inputs.get(name)
            if isinstance(candidate, sdk.LatentRef):
                return io.NodeOutput(candidate)
            if type(candidate) is dict and candidate.get("samples") is not None:
                return io.NodeOutput(candidate)
        return io.NodeOutput(None)


class _TypedLatentSwitch(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)
    NODE_ID = ""
    DISPLAY_NAME = ""
    EXPECTED = ""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return _schema(cls.NODE_ID, cls.DISPLAY_NAME, io.Latent, io.Latent)

    @classmethod
    def accepts(cls, value: Any) -> bool:
        raise NotImplementedError

    @classmethod
    async def execute(cls, **inputs: Any) -> io.NodeOutput:
        rejected = []
        for index, name in enumerate(_INPUT_IDS, start=1):
            candidate = inputs.get(name)
            if candidate is None:
                continue
            materialized = await _materialize(candidate)
            if await _is_none(materialized):
                continue
            if cls.accepts(materialized):
                return io.NodeOutput(candidate)
            rejected.append(_describe_latent(materialized, index))
        if rejected:
            raise ValueError(
                f"No compatible {cls.EXPECTED} latent found. "
                f"{cls.error_hint()} Rejected candidates: {', '.join(rejected)}"
            )
        return io.NodeOutput(None)

    @classmethod
    def error_hint(cls) -> str:
        raise NotImplementedError


class SimpleAudioLatentSwitch(_TypedLatentSwitch):
    NODE_ID = "SimpleAudioLatentSwitch"
    DISPLAY_NAME = "Simple Audio Latent Switch (6 Inputs)"
    EXPECTED = "audio"

    @classmethod
    def accepts(cls, value: Any) -> bool:
        samples, ndim, nested, _shape = _latent_details(value)
        if samples is None:
            return False
        return nested or (
            ndim == 4
            and (value.get("type") == "audio" or "sample_rate" in value)
        )

    @classmethod
    def error_hint(cls) -> str:
        return (
            "Expected an LTX audio latent (`type='audio'`) or a nested AV latent."
        )


class SimpleVideoLatentSwitch(_TypedLatentSwitch):
    NODE_ID = "SimpleVideoLatentSwitch"
    DISPLAY_NAME = "Simple Video Latent Switch (6 Inputs)"
    EXPECTED = "video"

    @classmethod
    def accepts(cls, value: Any) -> bool:
        samples, ndim, nested, _shape = _latent_details(value)
        return samples is not None and not nested and ndim == 5

    @classmethod
    def error_hint(cls) -> str:
        return "Expected a non-nested 5D video latent."


NODE_CLASS_MAPPINGS = {
    "SimpleSwitch": SimpleSwitch,
    "SimpleLatentSwitch": SimpleLatentSwitch,
    "SimpleAudioLatentSwitch": SimpleAudioLatentSwitch,
    "SimpleVideoLatentSwitch": SimpleVideoLatentSwitch,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    node_id: node_class.GET_SCHEMA().display_name
    for node_id, node_class in NODE_CLASS_MAPPINGS.items()
}
