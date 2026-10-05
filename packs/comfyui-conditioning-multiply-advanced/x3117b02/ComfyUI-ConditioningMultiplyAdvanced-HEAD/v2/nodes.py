"""Secure Nodes V2 wrapper for Conditioning Multiply Advanced."""

from __future__ import annotations

import torch
from comfy_api.latest import ComfyExtension, io, sdk

from . import _algorithm as algorithm

MAX_DEPTH = 32
MAX_ITEMS = 100_000
MAX_TENSOR_ELEMENTS = 67_108_864


def _validate_structure(value, depth=0, budget=None):
    if budget is None:
        budget = [0]
    if depth > MAX_DEPTH:
        raise ValueError("conditioning structure is too deeply nested")
    budget[0] += 1
    if budget[0] > MAX_ITEMS:
        raise ValueError("conditioning structure contains too many items")
    if isinstance(value, torch.Tensor):
        if value.numel() > MAX_TENSOR_ELEMENTS:
            raise ValueError("conditioning tensor exceeds the secure size bound")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _validate_structure(key, depth + 1, budget)
            _validate_structure(item, depth + 1, budget)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _validate_structure(item, depth + 1, budget)


class ConditioningMultiplyAdvanced(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ConditioningMultiplyAdvanced",
            display_name="Conditioning Multiply Advanced",
            category="advanced/conditioning",
            description=(
                "Multiply selected floating conditioning tensors while preserving "
                "integer token-id tensors such as Anima t5xxl_ids."
            ),
            search_aliases=[
                "multiply conditioning",
                "scale conditioning",
                "conditioning strength",
                "prompt strength",
            ],
            inputs=[
                io.Conditioning.Input(
                    "conditioning", tooltip="Conditioning payload to scale."
                ),
                io.Float.Input(
                    "start_multiplier",
                    default=1.0,
                    min=-1_000_000_000.0,
                    max=1_000_000_000.0,
                    step=0.01,
                    round=False,
                    tooltip=(
                        "Multiplier used at start_percent and before the window "
                        "when outside_window is hold."
                    ),
                ),
                io.Float.Input(
                    "end_multiplier",
                    default=1.0,
                    min=-1_000_000_000.0,
                    max=1_000_000_000.0,
                    step=0.01,
                    round=False,
                    tooltip=(
                        "Multiplier used at end_percent and after the window "
                        "when outside_window is hold."
                    ),
                ),
                io.Float.Input(
                    "start_percent",
                    default=0.0,
                    min=0.0,
                    max=1.0,
                    step=0.001,
                    tooltip=(
                        "Denoise progress where the multiplier transition window "
                        "starts."
                    ),
                ),
                io.Float.Input(
                    "end_percent",
                    default=1.0,
                    min=0.0,
                    max=1.0,
                    step=0.001,
                    tooltip=(
                        "Denoise progress where the multiplier transition window ends."
                    ),
                ),
                io.Combo.Input(
                    "curve",
                    options=algorithm.CURVE_CHOICES,
                    default="linear",
                    tooltip=(
                        "Curve used to interpolate from start_multiplier to "
                        "end_multiplier inside the timestep window."
                    ),
                ),
                io.Combo.Input(
                    "outside_window",
                    options=algorithm.OUTSIDE_WINDOW_CHOICES,
                    default="hold",
                    tooltip=(
                        "hold uses start_multiplier before the window and "
                        "end_multiplier after it. baseline uses 1.0 outside the "
                        "window. linear_extrapolate continues a linear multiplier "
                        "trend outside the window."
                    ),
                ),
                io.Int.Input(
                    "segments",
                    default=16,
                    min=1,
                    max=256,
                    step=1,
                    tooltip=(
                        "Number of conditioning ranges used to approximate the "
                        "multiplier curve inside the window."
                    ),
                ),
                io.Combo.Input(
                    "tensor_scope",
                    options=algorithm.FLOAT_TENSOR_SCOPE_CHOICES,
                    default=algorithm.FLOAT_TENSOR_SCOPE_MAIN_AND_METADATA,
                    tooltip=(
                        "Controls which floating tensors are multiplied. The "
                        "default scales the main conditioning tensor plus selected "
                        "float metadata such as pooled_output and t5xxl_weights."
                    ),
                ),
                io.Combo.Input(
                    "non_float_behavior",
                    options=algorithm.NON_FLOAT_BEHAVIOR_CHOICES,
                    default=algorithm.NON_FLOAT_BEHAVIOR_PRESERVE,
                    tooltip=(
                        "preserve leaves integer/bool tensors unchanged. error "
                        "raises when a non-floating tensor is encountered."
                    ),
                ),
                io.String.Input(
                    "metadata_keys",
                    default="pooled_output,t5xxl_weights",
                    multiline=False,
                    tooltip=(
                        "Comma-separated metadata tensor keys to scale when "
                        "tensor_scope includes metadata. Integer token ids such as "
                        "t5xxl_ids should not be listed."
                    ),
                ),
                io.Boolean.Input(
                    "log_summary",
                    default=False,
                    tooltip="Print how many tensors were multiplied or preserved.",
                ),
            ],
            outputs=[io.Conditioning.Output("conditioning")],
        )

    @classmethod
    async def execute(
        cls,
        conditioning,
        start_multiplier,
        end_multiplier,
        start_percent,
        end_percent,
        curve,
        outside_window,
        segments,
        tensor_scope=algorithm.FLOAT_TENSOR_SCOPE_MAIN_AND_METADATA,
        non_float_behavior=algorithm.NON_FLOAT_BEHAVIOR_PRESERVE,
        metadata_keys="pooled_output,t5xxl_weights",
        log_summary=False,
    ) -> io.NodeOutput:
        value = await conditioning.value()
        _validate_structure(value)
        legacy = algorithm.ConditioningMultiplyAdvanced()
        result = legacy.multiply(
            value,
            start_multiplier,
            end_multiplier,
            start_percent,
            end_percent,
            curve,
            outside_window,
            segments,
            tensor_scope,
            non_float_behavior,
            metadata_keys,
            log_summary,
        )[0]
        _validate_structure(result)
        return io.NodeOutput(await sdk.CondRef.from_value(result))


NODE_CLASS_MAPPINGS = {"ConditioningMultiplyAdvanced": ConditioningMultiplyAdvanced}
NODE_DISPLAY_NAME_MAPPINGS = {
    "ConditioningMultiplyAdvanced": "Conditioning Multiply Advanced"
}


class ConditioningMultiplyExtension(ComfyExtension):
    async def get_node_list(self):
        return [ConditioningMultiplyAdvanced]


async def comfy_entrypoint() -> ConditioningMultiplyExtension:
    return ConditioningMultiplyExtension()
