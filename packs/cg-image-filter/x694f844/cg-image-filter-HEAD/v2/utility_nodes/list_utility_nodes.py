"""List helpers; all concatenation and selection remains pack-side."""
from __future__ import annotations

from comfy_api.latest import io, sdk
import torch

from .._secure_runtime import image_value, output_image


class BatchFromImageList(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Batch from Image List",
            display_name="Batch from Image List",
            category="image_filter/helpers",
            inputs=[io.Image.Input("images")],
            outputs=[io.Image.Output("image")],
            is_input_list=True,
        )

    @classmethod
    async def execute(cls, images):
        if not isinstance(images, list) or not images:
            raise ValueError("Batch from Image List needs at least one IMAGE")
        values = [await image_value(image) for image in images]
        if any(value is None for value in values):
            raise ValueError("Batch from Image List received an empty IMAGE")
        output = values[0] if len(values) == 1 else torch.cat(values, dim=0)
        return io.NodeOutput(await output_image(output))


class ImageListFromBatch(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Image List From Batch",
            display_name="Image List From Batch",
            category="image_filter/helpers",
            inputs=[io.Image.Input("images")],
            outputs=[io.Image.Output("image", is_output_list=True)],
        )

    @classmethod
    async def execute(cls, images):
        value = await image_value(images)
        if value is None or value.ndim != 4:
            raise ValueError("Image List From Batch needs an IMAGE batch")
        return io.NodeOutput([
            await sdk.ImageRef._from_raw(image.unsqueeze(0)) for image in value
        ])


class PickFromList(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Pick from List",
            display_name="Pick from List",
            category="image_filter/helpers",
            inputs=[
                io.AnyType.Input("anything"),
                io.String.Input("indexes", display_name="indexes", tooltip="comma separated list of indexes. Whitespace stripped. Only these entries will be included. Zero indexed."),
            ],
            # The original backend reports STRING while its frontend retypes
            # this port to the connected input.  Preserve that wire schema and
            # pass the selected opaque refs through unchanged.
            outputs=[io.String.Output("picks", display_name="picks", is_output_list=True)],
            is_input_list=True,
        )

    @classmethod
    async def execute(cls, anything: list, indexes: list[str]):
        if len(anything) == 1 and isinstance(anything[0], list):
            print("cg-image-filter: list of lists received; using anything[0]")
            anything = anything[0]
        index_text = indexes[0] if indexes else ""
        result = []
        for value in [part.strip() for part in str(index_text).split(",")]:
            try:
                result.append(anything[int(value)])
            except (ValueError, IndexError) as error:
                print(f"cg-image-filter: {error} selecting {value!r}")
        return io.NodeOutput(result)
