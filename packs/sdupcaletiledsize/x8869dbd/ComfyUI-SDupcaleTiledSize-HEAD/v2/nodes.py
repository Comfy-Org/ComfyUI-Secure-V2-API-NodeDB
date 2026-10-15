"""Tile-size arithmetic with opaque, unchanged image passthrough."""
import math
from comfy_api.latest import io, sdk

MAX_EDGE = 16384
MAX_NEGATIVE_FACTOR = 1_000_000


def _parameters(tiled_block, upscale_by):
    if isinstance(tiled_block, bool) or not isinstance(tiled_block, int):
        raise TypeError("tiled_block must be an integer")
    if not 1 <= tiled_block <= 2048:
        raise ValueError("tiled_block exceeds the bounded positive range")
    if isinstance(upscale_by, bool) or not isinstance(upscale_by, (int, float)):
        raise TypeError("upscale_by must be a real number")
    if not math.isfinite(upscale_by) or upscale_by < -MAX_NEGATIVE_FACTOR:
        raise ValueError("upscale_by exceeds the finite scalar bounds")


def uov_tiled_size(width, height, upscale_by, tiled_block=2048):
    # Preserve the source's int-before-ceil/int-before-16-rounding sequence.
    tiled_size = lambda x, p: int(x*p) if int(x*p) < tiled_block else int(int(x*p)/math.ceil(int(x*p)/tiled_block))
    upscale_by = upscale_by if upscale_by < 4.0 else 4.0
    tiled_width = ((tiled_size(width, upscale_by) + 15) // 16) * 16
    tiled_height = ((tiled_size(height, upscale_by) + 15) // 16) * 16
    return upscale_by, tiled_width, tiled_height


class SDupscaleTiledSize(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="SDupscaleTiledSize", display_name="SDupscaleTiledSize", category="image/upscaling",
            inputs=[io.Image.Input("image"),
                    io.Int.Input("tiled_block", default=1536, min=512, max=2048, step=256),
                    io.Float.Input("upscale_by", default=1.0, min=.5, max=4.0, step=.1)],
            outputs=[io.Image.Output(display_name="output_image"), io.Float.Output(display_name="upscale_by"),
                     io.Int.Output(display_name="tiled_width"), io.Int.Output(display_name="tiled_height")])

    @classmethod
    async def execute(cls, image, tiled_block, upscale_by):
        _parameters(tiled_block, upscale_by)
        if not isinstance(image, sdk.ImageRef):
            raise TypeError("image must be an opaque IMAGE ref")
        height, width = await image.spatial_shape()
        if not 1 <= height <= MAX_EDGE or not 1 <= width <= MAX_EDGE:
            raise ValueError("image dimensions exceed bounded metadata limits")
        factor, tiled_width, tiled_height = uov_tiled_size(width, height, upscale_by, tiled_block)
        # No pixel access, copying, resize, device move, or image allocation.
        return io.NodeOutput(image, factor, tiled_width, tiled_height)


NODE_CLASS_MAPPINGS = {"SDupscaleTiledSize": SDupscaleTiledSize}
NODE_DISPLAY_NAME_MAPPINGS = {"SDupscaleTiledSize": "SDupscaleTiledSize"}
