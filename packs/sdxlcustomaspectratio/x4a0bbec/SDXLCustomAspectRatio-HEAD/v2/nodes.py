"""Bounded scalar preset parsing, using the exact pack-owned algorithm."""

from comfy_api.latest import ComfyExtension, io

from . import algorithm

MAX_TEXT_BYTES = 65_536
MAX_DIMENSION_VALUE = 0x7FFFFFFFFFFFFFFF
OPTIONS = tuple(algorithm.SDXLAspectRatio.INPUT_TYPES()["required"]["aspectRatio"][0])


class SDXLAspectRatio(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="SDXLAspectRatio",
            display_name="SDXL Aspect Ratio",
            category="image",
            inputs=[io.Combo.Input("aspectRatio", options=list(OPTIONS))],
            outputs=[
                io.Int.Output(display_name="Width"),
                io.Int.Output(display_name="Height"),
            ],
        )

    @classmethod
    def execute(cls, aspectRatio):
        if not isinstance(aspectRatio, str):
            raise TypeError("aspectRatio must be a string")
        if len(aspectRatio.encode("utf-8")) > MAX_TEXT_BYTES:
            raise ValueError("aspectRatio exceeds 64 KiB UTF-8")
        result = algorithm.SDXLAspectRatio().SDXL_AspectRatio(aspectRatio)
        if any(value > MAX_DIMENSION_VALUE for value in result):
            raise ValueError("parsed integer exceeds the bounded output range")
        return io.NodeOutput(*result)


NODE_CLASS_MAPPINGS = {"SDXLAspectRatio": SDXLAspectRatio}
NODE_DISPLAY_NAME_MAPPINGS = {"SDXLAspectRatio": "SDXL Aspect Ratio"}


class SDXLAspectRatioExtension(ComfyExtension):
    async def get_node_list(self):
        return [SDXLAspectRatio]


async def comfy_entrypoint():
    return SDXLAspectRatioExtension()
