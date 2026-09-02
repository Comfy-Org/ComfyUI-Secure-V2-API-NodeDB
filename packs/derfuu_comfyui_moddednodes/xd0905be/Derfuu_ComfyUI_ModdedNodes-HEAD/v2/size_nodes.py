"""Size probes expressed through typed V2 ref operations."""
from __future__ import annotations

from comfy_api.latest import io, sdk


TREE_FUNCTIONS = "Derfuu_Nodes/Functions"


def _ref_input(kind, name: str):
    return kind.Input(name, extra_dict={"forceInput": False})


class GetLatentSize(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DF_Get_latent_size",
            display_name="Get latent size",
            category=TREE_FUNCTIONS,
            inputs=[
                _ref_input(io.Latent, "latent"),
                io.Combo.Input("original", options=[False, True]),
            ],
            outputs=[
                io.Int.Output("output_0", display_name="WIDTH"),
                io.Int.Output("output_1", display_name="HEIGHT"),
            ],
        )

    @classmethod
    async def execute(cls, latent: sdk.LatentRef, original):
        height, width = await latent.spatial_shape()
        if not original:
            width *= 8
            height *= 8
        return io.NodeOutput(width, height)


class GetImageSize(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DF_Get_image_size",
            display_name="Get image size",
            category=TREE_FUNCTIONS,
            inputs=[_ref_input(io.Image, "image")],
            outputs=[
                io.Int.Output("output_0", display_name="WIDTH"),
                io.Int.Output("output_1", display_name="HEIGHT"),
            ],
        )

    @classmethod
    async def execute(cls, image: sdk.ImageRef):
        height, width = await image.spatial_shape()
        return io.NodeOutput(width, height)


__all__ = ["GetImageSize", "GetLatentSize"]
