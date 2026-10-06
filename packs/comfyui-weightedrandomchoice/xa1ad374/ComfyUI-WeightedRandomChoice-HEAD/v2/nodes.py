"""Seeded weighted choice using only scalar values and opaque typed refs."""

import math
import random

from comfy_api.latest import ComfyExtension, io
from comfy_api.latest import _sdk as sdk

MAX_TEXT_BYTES = 65_536
MAX_ITEMS = 4096
MAX_DEPTH = 32


def _bounded(*values):
    items, text_bytes = 0, 0

    def visit(value, depth):
        nonlocal items, text_bytes
        items += 1
        if items > MAX_ITEMS or depth > MAX_DEPTH:
            raise ValueError("input structure exceeds bounds")
        if value is None or isinstance(value, (bool, sdk.Ref)):
            return
        if isinstance(value, str):
            text_bytes += len(value.encode("utf-8"))
            if text_bytes > MAX_TEXT_BYTES:
                raise ValueError("inputs exceed 64 KiB UTF-8")
        elif isinstance(value, int):
            if abs(value) > 0xFFFFFFFFFFFFFFFF:
                raise ValueError("integer input exceeds bounds")
        elif isinstance(value, float):
            if not math.isfinite(value):
                raise ValueError("number input must be finite")
        elif isinstance(value, (list, tuple)):
            for item in value:
                visit(item, depth + 1)
        elif isinstance(value, dict):
            for key, item in value.items():
                if not isinstance(key, str):
                    raise TypeError("structured input keys must be strings")
                visit(key, depth + 1)
                visit(item, depth + 1)
        else:
            raise TypeError("inputs must be bounded scalars, containers or opaque refs")

    for value in values:
        visit(value, 0)


def get_default_value(example_input):
    if isinstance(example_input, str):
        return ""
    if isinstance(example_input, int):
        return 0
    if isinstance(example_input, float):
        return 0.0
    return ""


class WeightedRandomChoiceNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="WeightedRandomChoice",
            display_name="Weighted Random Choice",
            category="sd",
            inputs=[
                io.Float.Input("chance", default=0.5, min=0.0, max=1.0, step=0.01),
                io.Int.Input("seed", default=0, min=0, max=0xFFFFFFFFFFFFFFFF, step=1),
                io.AnyType.Input("input_a", optional=True, extra_dict={"default": ""}),
                io.AnyType.Input("input_b", optional=True, extra_dict={"default": ""}),
            ],
            outputs=[io.AnyType.Output()],
        )

    @classmethod
    def execute(cls, chance, seed, input_a=None, input_b=None):
        if isinstance(chance, bool) or not isinstance(chance, (int, float)):
            raise TypeError("chance must be a number")
        if not 0 <= chance <= 1:
            raise ValueError("chance exceeds schema bounds")
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise TypeError("seed must be an integer")
        if not 0 <= seed <= 0xFFFFFFFFFFFFFFFF:
            raise ValueError("seed exceeds schema bounds")
        _bounded(input_a, input_b)
        if input_a is not None:
            default_value = get_default_value(input_a)
        elif input_b is not None:
            default_value = get_default_value(input_b)
        else:
            # Normalize the legacy bare empty string into its declared ANY socket.
            return io.NodeOutput("")
        chosen = input_a if chance >= random.Random(seed).random() else input_b
        return io.NodeOutput(default_value if chosen is None else chosen)


NODE_CLASS_MAPPINGS = {"WeightedRandomChoice": WeightedRandomChoiceNode}
NODE_DISPLAY_NAME_MAPPINGS = {"WeightedRandomChoice": "Weighted Random Choice"}


class WeightedRandomChoiceExtension(ComfyExtension):
    async def get_node_list(self):
        return [WeightedRandomChoiceNode]


async def comfy_entrypoint():
    return WeightedRandomChoiceExtension()
