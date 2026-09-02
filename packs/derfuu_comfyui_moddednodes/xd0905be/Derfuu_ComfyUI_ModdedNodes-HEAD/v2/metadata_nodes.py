"""Debug and conditioning metadata behavior that needs raw ref materialization."""
from __future__ import annotations

import logging
from typing import Any

from comfy_api.latest import io, sdk


TREE_MAIN = "Derfuu_Nodes"
TREE_DEBUG = TREE_MAIN + "/Debug"
TREE_COND = TREE_MAIN + "/Modded nodes/Conditions"


def _conditioning_input(name: str):
    value = io.Conditioning.Input(name)
    value.extra_dict["forceInput"] = False
    return value


async def _materialize(value: Any) -> Any:
    if isinstance(value, sdk.TensorRef):
        return await value.raw()
    if isinstance(value, sdk.ValueRef):
        return await value.value()
    if isinstance(value, list):
        return [await _materialize(item) for item in value]
    if isinstance(value, tuple):
        return tuple([await _materialize(item) for item in value])
    if isinstance(value, dict):
        return {
            key: await _materialize(item) for key, item in value.items()
        }
    # Live engine refs deliberately remain opaque. Their stable safe
    # representation is the only string form available to untrusted code.
    return value


class ShowDataDebug(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DF_To_text_(Debug)",
            display_name="To text (Debug)",
            category=TREE_DEBUG,
            inputs=[io.AnyType.Input(
                "ANY", extra_dict={"forceInput": False}
            )],
            outputs=[
                io.AnyType.Output(
                    "output_0", display_name="SAME AS INPUT"
                ),
                io.String.Output("output_1", display_name="STRING"),
            ],
            is_output_node=True,
        )

    @classmethod
    def fingerprint_inputs(cls, **kwargs):
        return float("NaN")

    @classmethod
    async def execute(cls, ANY=None):
        # Capability/broker failures must propagate. V1's try/except guarded
        # only local string conversion and logging; it was never an authority
        # bypass, so do not turn a denied ref read into a successful result.
        display_value = await _materialize(ANY)
        try:
            text = str(display_value)
            logging.info("\x1b[38;5;12m[DEBUG]: %s\x1b[0m", display_value)
        except Exception as error:
            text = str(error)
            logging.info(
                "\x1b[38;5;1m[DEBUG-EXCEPTION]: %s\x1b[0m", error
            )
        return io.NodeOutput(ANY, text, ui={"text": [text]})


class ConditioningAreaScale_Ratio(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        limit = __import__("sys").float_info.max
        return io.Schema(
            node_id="DF_Conditioning_area_scale_by_ratio",
            display_name="Conditioning area scale by ratio",
            category=TREE_COND,
            inputs=[
                _conditioning_input("conditioning"),
                io.Float.Input(
                    "modifier",
                    default=1,
                    min=-limit,
                    max=limit,
                    step=0.01,
                    force_input=False,
                ),
                io.Float.Input(
                    "strength_modifier",
                    default=1,
                    min=-limit,
                    max=limit,
                    step=0.01,
                    force_input=False,
                ),
            ],
            outputs=[io.Conditioning.Output(
                "output_0", display_name="CONDITIONING"
            )],
        )

    @classmethod
    async def execute(
        cls,
        conditioning: sdk.CondRef,
        modifier,
        strength_modifier,
        min_sigma=0.0,
        max_sigma=99.0,
    ):
        source = await conditioning.value()
        output = []
        for item in source:
            row = [item[0], item[1].copy()]
            try:
                area = row[1]["area"]
                width = area[1]
                height = area[0]
                x_offset = area[3]
                y_offset = area[2]
            except Exception:
                output.append(row)
                continue

            height = int(height * 8 * modifier)
            width = int(width * 8 * modifier)
            y_offset = int(y_offset * 8 * modifier)
            x_offset = int(x_offset * 8 * modifier)
            row[1]["area"] = (
                height // 8,
                width // 8,
                y_offset // 8,
                x_offset // 8,
            )
            row[1]["strength"] *= strength_modifier
            row[1]["min_sigma"] = min_sigma
            row[1]["max_sigma"] = max_sigma
            output.append(row)

        return io.NodeOutput(await sdk.CondRef.from_value(output))


__all__ = ["ConditioningAreaScale_Ratio", "ShowDataDebug"]
