import numpy as np
from comfy_api.latest import io

MAX_TEXT_BYTES = 1_048_576
MAX_ROWS = 4096


class SizeFromArray(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="SizeFromArray",
            display_name="Retrieve random pair of size from array",
            category="SizeFromArray", description=cls.DESCRIPTION,
            inputs=[io.String.Input("sizes", default="512,512\n512,768\n768,512\n", multiline=True),
                    io.Int.Input("seed", default=0, min=0, max=0xffffffffffffffff)],
            outputs=[io.Int.Output(display_name="width"), io.Int.Output(display_name="height")],
        )
    DESCRIPTION = (
        "\nReturn random pair of width&height from given array  \n\n"
        "For example the default values:  \n512,512\n512,768\n768,512\n  \n"
        "Would return random pair from 512x512, 512x768 or 768x512\n"
    )

    @classmethod
    def execute(cls, sizes, seed):
        random_gen = np.random.default_rng(seed)
        if isinstance(sizes, str) and len(sizes.encode("utf-8")) > MAX_TEXT_BYTES:
            raise ValueError("sizes exceeds the bounded text limit")

        # Filter only empty lines, not whitespace-only lines, exactly as upstream.
        lines = [line for line in sizes.split("\n") if line]
        if len(lines) > MAX_ROWS:
            raise ValueError("sizes exceeds the bounded row limit")
        tuples_array = [tuple(map(int, line.strip().split(","))) for line in lines]

        preset = random_gen.choice(tuples_array)

        return io.NodeOutput(int(preset[0]), int(preset[1]))
