"""Bounded pack-side Mosaic Blur; upstream algorithms remain in algorithms.py."""
import torch
from comfy_api.latest import ComfyExtension, io
from .algorithms import mosaic_images

MAX_BATCH = 64
MAX_AXIS = 8192
MAX_ELEMENTS = 16_777_216
MAX_OUTPUT_ELEMENTS = 16_777_216
MAX_BLOCKS = 1_048_576


def validate(images, method, block_size):
    if method not in ("pillow", "cv2"):
        raise ValueError("method must be pillow or cv2")
    if type(block_size) is not int or not 1 <= block_size <= 100:
        raise ValueError("block_size must be an integer in 1..100")
    if not isinstance(images, torch.Tensor) or images.ndim != 4:
        raise TypeError("images must be a BHWC tensor")
    b, h, w, c = images.shape
    if not 1 <= b <= MAX_BATCH or not 1 <= h <= MAX_AXIS or not 1 <= w <= MAX_AXIS or c not in (1, 2, 3, 4):
        raise ValueError("images exceed bounded dimensions/channels")
    if not images.is_floating_point():
        raise TypeError("images must use a floating dtype")
    output_channels = 4 if method == "pillow" else c
    output_pixels = b * h * w
    compute_h, compute_w = h, w
    if method == "pillow" and (h == 1 or w == 1) and c > 1:
        # Upstream squeeze can interpret the surviving channel axis as width.
        output_pixels *= c
        compute_h, compute_w = max(h, w), c
    blocks = b * ((compute_h + block_size - 1) // block_size) * ((compute_w + block_size - 1) // block_size)
    if images.numel() > MAX_ELEMENTS or output_pixels * output_channels > MAX_OUTPUT_ELEMENTS or blocks > MAX_BLOCKS:
        raise ValueError("images exceed bounded elements/output/work")
    if not torch.isfinite(images).all():
        raise ValueError("images must be finite")


class ImageMosaic(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="ImageMosaic", display_name="Image Mosaic", category="Image/Blur",
            inputs=[io.Image.Input("images"),
                    io.Combo.Input("method", options=["pillow", "cv2"]),
                    io.Int.Input("block_size", default=10, min=1, max=100)],
            outputs=[io.Image.Output()])

    @classmethod
    def execute(cls, images, method, block_size):
        validate(images, method, block_size)
        return io.NodeOutput(*mosaic_images(images, method, block_size))


NODE_CLASS_MAPPINGS = {"ImageMosaic": ImageMosaic}
NODE_DISPLAY_NAME_MAPPINGS = {"ImageMosaic": "Image Mosaic"}


class MosaicExtension(ComfyExtension):
    async def get_node_list(self):
        return [ImageMosaic]


async def comfy_entrypoint():
    return MosaicExtension()
