"""Secure Nodes V2 backend for the two-image comparison preview."""

from __future__ import annotations

from comfy_api.latest import io, sdk


MAX_DIMENSION = 8192
MAX_PIXELS = 32 * 1024 * 1024


def _first_preview(preview: dict, label: str) -> dict:
    images = preview.get("images")
    if not isinstance(images, (list, tuple)) or len(images) != 1:
        raise RuntimeError(f"{label} preview did not produce exactly one image")
    result = images[0]
    if not isinstance(result, dict):
        raise RuntimeError(f"{label} preview returned malformed image metadata")
    return result


async def _validate_image(image: sdk.ImageRef, label: str) -> None:
    if await image.batch_size() < 1:
        raise ValueError(f"{label} must contain at least one image")
    height, width = await image.spatial_shape()
    if (
        height < 1
        or width < 1
        or height > MAX_DIMENSION
        or width > MAX_DIMENSION
        or height * width > MAX_PIXELS
    ):
        raise ValueError(f"{label} dimensions exceed the comparison preview limit")


class ImageCompareNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("ui",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="ImageCompareNode",
            display_name="Image Compare",
            category="SBCODE",
            is_output_node=True,
            inputs=[
                io.Image.Input("image_a"),
                io.Image.Input("image_b"),
            ],
            outputs=[],
        )

    @classmethod
    async def execute(
        cls,
        image_a: sdk.ImageRef,
        image_b: sdk.ImageRef,
    ) -> io.NodeOutput:
        await _validate_image(image_a, "image_a")
        await _validate_image(image_b, "image_b")
        first_a = await image_a.select_batch([0])
        first_b = await image_b.select_batch([0])
        preview_a = await sdk.ctx().ui.preview_images(first_a)
        preview_b = await sdk.ctx().ui.preview_images(first_b)
        return io.NodeOutput(ui={
            "images": [
                _first_preview(preview_a, "image_a"),
                _first_preview(preview_b, "image_b"),
            ]
        })


NODE_CLASS_MAPPINGS = {"ImageCompareNode": ImageCompareNode}
