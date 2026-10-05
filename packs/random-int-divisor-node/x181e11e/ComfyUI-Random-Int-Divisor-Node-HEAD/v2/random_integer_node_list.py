"""Secure Nodes V2 list-based random integer generator."""

from __future__ import annotations

import random

from comfy_api.latest import io


class RandomIntegerNodeList(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="RandomIntegerNodeList",
            display_name="Random Integer Generator Using List",
            category="Custom/Random",
            not_idempotent=True,
            inputs=[
                io.Int.Input("min_value", default=0),
                io.Int.Input("max_value", default=100),
                io.Int.Input("divisor", default=1),
            ],
            outputs=[io.Int.Output("INT", display_name="INT")],
        )

    @classmethod
    def execute(cls, min_value: int, max_value: int, divisor: int) -> io.NodeOutput:
        if min_value > max_value:
            raise ValueError("Minimum value should not be greater than maximum value.")
        if divisor <= 0:
            raise ValueError("Divisor should be a positive integer.")
        start = min_value + (-min_value % divisor)
        end = max_value - (max_value % divisor)
        if start > end:
            raise ValueError("No multiples of the divisor exist within the given range.")
        valid_multiples = list(range(start, end + divisor, divisor))
        return io.NodeOutput(random.choice(valid_multiples))
