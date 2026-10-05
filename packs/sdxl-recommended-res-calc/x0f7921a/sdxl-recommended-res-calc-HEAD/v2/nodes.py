"""Secure Nodes V2 implementation of the SDXL resolution calculator."""

from __future__ import annotations

from comfy_api.latest import ComfyExtension, io


# The order is behaviorally significant.  The pinned source keeps the first
# ratio when two candidates are equally close, so this is its exact horizontal,
# vertical, then square traversal order.
ACCEPTED_RESOLUTIONS = (
    (2048, 512, 4.000000000),
    (1984, 512, 3.875000000),
    (1920, 512, 3.750000000),
    (1856, 512, 3.625000000),
    (1792, 576, 3.111111111),
    (1728, 576, 3.000000000),
    (1664, 576, 2.888888889),
    (1600, 640, 2.500000000),
    (1536, 640, 2.400000000),
    (1472, 704, 2.090909091),
    (1408, 704, 2.000000000),
    (1344, 704, 1.909090909),
    (1344, 768, 1.750000000),
    (1280, 768, 1.666666667),
    (1216, 832, 1.461538462),
    (1152, 832, 1.384615385),
    (1152, 896, 1.285714286),
    (1088, 896, 1.214285714),
    (1088, 960, 1.133333333),
    (1024, 960, 1.066666667),
    (960, 1024, 0.937500000),
    (960, 1088, 0.882352941),
    (896, 1088, 0.823529412),
    (896, 1152, 0.777777778),
    (832, 1152, 0.722222222),
    (832, 1216, 0.684210526),
    (768, 1280, 0.600000000),
    (768, 1344, 0.571428571),
    (704, 1344, 0.523809524),
    (704, 1408, 0.500000000),
    (704, 1472, 0.478260870),
    (640, 1536, 0.416666667),
    (640, 1600, 0.400000000),
    (576, 1664, 0.346153846),
    (576, 1728, 0.333333333),
    (576, 1792, 0.321428571),
    (512, 1856, 0.275862069),
    (512, 1920, 0.266666667),
    (512, 1984, 0.258064516),
    (512, 2048, 0.250000000),
    (1024, 1024, 1.000000000),
)


def calculate(desired_width: int, desired_height: int):
    """Return the pinned implementation's nearest bucket and scale values."""
    # Division happens before any validation in the source.  In particular,
    # height=0 intentionally retains its ZeroDivisionError behavior.
    desired_ratio = desired_width / desired_height
    accepted_width, accepted_height, _ = min(
        ACCEPTED_RESOLUTIONS,
        key=lambda item: abs(item[2] - desired_ratio),
    )
    width_factor = desired_width / accepted_width
    height_factor = desired_height / accepted_height
    scaling_factor = round(max(width_factor, height_factor), 9)
    return (
        accepted_width,
        accepted_height,
        scaling_factor,
        round(scaling_factor / 4, 9),
        round(scaling_factor / 2, 9),
    )


class RecommendedResCalc(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="RecommendedResCalc",
            display_name="Recommended Resolution Calculator",
            category="utils",
            inputs=[
                io.Int.Input(
                    "desiredXSIZE", default=1024, min=0, max=8192, step=2,
                ),
                io.Int.Input(
                    "desiredYSIZE", default=1024, min=0, max=8192, step=2,
                ),
            ],
            outputs=[
                io.Int.Output(
                    "recomm_width", display_name="recomm width",
                ),
                io.Int.Output(
                    "recomm_height", display_name="recomm height",
                ),
                io.Float.Output(
                    "upscale_factor", display_name="upscale factor",
                ),
                io.Float.Output(
                    "reverse_upscale_for_4x",
                    display_name="reverse upscale for 4x",
                ),
                io.Float.Output(
                    "reverse_upscale_for_2x",
                    display_name="reverse upscale for 2x",
                ),
            ],
        )

    @classmethod
    def execute(
        cls, desiredXSIZE: int, desiredYSIZE: int,
    ) -> io.NodeOutput:
        return io.NodeOutput(*calculate(desiredXSIZE, desiredYSIZE))


NODE_CLASS_MAPPINGS = {"RecommendedResCalc": RecommendedResCalc}


class RecommendedResolutionExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [RecommendedResCalc]


async def comfy_entrypoint() -> RecommendedResolutionExtension:
    return RecommendedResolutionExtension()


__all__ = [
    "ACCEPTED_RESOLUTIONS",
    "NODE_CLASS_MAPPINGS",
    "RecommendedResCalc",
    "RecommendedResolutionExtension",
    "calculate",
    "comfy_entrypoint",
]
