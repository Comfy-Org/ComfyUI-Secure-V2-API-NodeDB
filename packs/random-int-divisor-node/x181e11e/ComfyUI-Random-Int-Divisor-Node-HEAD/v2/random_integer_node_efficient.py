"""Secure Nodes V2 efficient random integer generator."""

from __future__ import annotations

import random

from comfy_api.latest import io


class RandomIntegerNodeEfficient(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="RandomIntegerNodeEfficient",
            display_name="Efficient Random Integer Generator",
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
            raise ValueError("min_value should not be greater than max_value.")
        if divisor <= 0:
            raise ValueError("divisor must be a positive integer.")

        if min_value % divisor == 0:
            min_multiple = min_value
        else:
            min_multiple = min_value + (divisor - (min_value % divisor))
        max_multiple = max_value - (max_value % divisor)
        if min_multiple > max_multiple:
            raise ValueError(
                f"No multiples of {divisor} within the range "
                f"[{min_value}, {max_value}]."
            )
        count = ((max_multiple - min_multiple) // divisor) + 1
        return io.NodeOutput(min_multiple + random.randint(0, count - 1) * divisor)
