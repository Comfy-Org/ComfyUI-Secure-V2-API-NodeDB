"""Authority-free Secure Nodes V2 backend for Radar Weights Node."""

from __future__ import annotations

import math
from typing import Any

from comfy_api.latest import io


MIN_AXES = 3
MAX_AXES = 10
DEFAULT_WEIGHT = 1.0
MIN_WEIGHT = 0.0
MAX_WEIGHT = 2.0
MAX_SYNC_BYTES = 256


def _axes_count(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("axes_count must be an integer")
    if not MIN_AXES <= value <= MAX_AXES:
        raise ValueError(f"axes_count must be between {MIN_AXES} and {MAX_AXES}")
    return value


def parse_weights(value: str, count: int) -> list[float]:
    """Parse frontend state using the legacy node's default-on-error policy."""

    count = _axes_count(count)
    if not isinstance(value, str):
        return [DEFAULT_WEIGHT] * count
    if len(value.encode("utf-8")) > MAX_SYNC_BYTES:
        return [DEFAULT_WEIGHT] * count

    try:
        parsed = [float(item.strip()) for item in value.split(",") if item.strip()]
        if not parsed or any(
            not math.isfinite(item) or item < MIN_WEIGHT or item > MAX_WEIGHT
            for item in parsed
        ):
            raise ValueError("weight outside the radar range")
    except (TypeError, ValueError, OverflowError):
        return [DEFAULT_WEIGHT] * count

    if len(parsed) < count:
        parsed.extend([DEFAULT_WEIGHT] * (count - len(parsed)))
    return parsed[:count]


class RadarWeightsNode(io.ComfyNode):
    """Return the graph-serialized values from an interactive radar widget."""

    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="RadarWeightsNode",
            display_name="Radar Weights Node",
            category="Spider/Widgets",
            inputs=[
                io.Int.Input(
                    "axes_count", default=5, min=MIN_AXES, max=MAX_AXES,
                    step=1, extra_dict={"display": "number"},
                ),
                # V2 makes the legacy custom hidden field an explicit,
                # socketless input. The frontend hides it and owns its value.
                io.String.Input(
                    "_weights_sync", default="", socketless=True,
                    advanced=True,
                ),
            ],
            hidden=[io.Hidden.unique_id],
            outputs=[io.Float.Output(str(index)) for index in range(1, 11)],
        )

    @classmethod
    def fingerprint_inputs(
        cls,
        axes_count: int,
        _weights_sync: str = "",
        unique_id: Any = None,
    ) -> str:
        del cls, unique_id
        return f"{_axes_count(axes_count)}-{_weights_sync}"

    @classmethod
    def execute(
        cls,
        axes_count: int,
        _weights_sync: str = "",
        unique_id: Any = None,
    ) -> io.NodeOutput:
        del cls, unique_id
        count = _axes_count(axes_count)
        values = [round(value, 2) for value in parse_weights(_weights_sync, count)]
        return io.NodeOutput(*(values + [0.0] * (MAX_AXES - count)))


NODE_CLASS_MAPPINGS = {"RadarWeightsNode": RadarWeightsNode}
