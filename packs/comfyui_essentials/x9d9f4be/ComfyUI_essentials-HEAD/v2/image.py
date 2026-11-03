"""Public IMAGE boundaries around the selected pinned pack compute."""
from comfy_api.latest import io, sdk
from . import _image_compute
from ._refusals import EssentialsPurposeRefusal
from ._v2 import schema_for


async def _image_output(node_id, pixels):
    try:
        return await sdk.ImageRef.from_value(pixels)
    except (TypeError, ValueError) as error:
        raise EssentialsPurposeRefusal(
            f"comfyui_essentials/{node_id} output cannot cross the selected public IMAGE boundary: {error}"
        ) from error


class ImageResize(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return schema_for("ImageResize+")

    @classmethod
    async def execute(cls, image, width, height, method="stretch", interpolation="nearest", condition="always", multiple_of=0, keep_proportion=False):
        result = _image_compute.ImageResize().execute(
            await image.raw(), width, height, method=method,
            interpolation=interpolation, condition=condition,
            multiple_of=multiple_of, keep_proportion=keep_proportion,
        )
        return io.NodeOutput(await _image_output("ImageResize+", result[0]), *result[1:])


class ImageBatchMultiple(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return schema_for("ImageBatchMultiple+")

    @classmethod
    async def execute(cls, image_1, method, image_2=None, image_3=None, image_4=None, image_5=None):
        if image_2 is None and image_3 is None and image_4 is None and image_5 is None:
            return io.NodeOutput(image_1)
        result = _image_compute.ImageBatchMultiple().execute(
            await image_1.raw(), method,
            image_2=None if image_2 is None else await image_2.raw(),
            image_3=None if image_3 is None else await image_3.raw(),
            image_4=None if image_4 is None else await image_4.raw(),
            image_5=None if image_5 is None else await image_5.raw(),
        )
        return io.NodeOutput(await _image_output("ImageBatchMultiple+", result[0]))


class GetImageSize(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return schema_for("GetImageSize+")

    @classmethod
    async def execute(cls, image):
        return io.NodeOutput(*_image_compute.GetImageSize().execute(await image.raw()))


NODE_CLASS_MAPPINGS = {
    "ImageBatchMultiple+": ImageBatchMultiple,
    "GetImageSize+": GetImageSize,
}
