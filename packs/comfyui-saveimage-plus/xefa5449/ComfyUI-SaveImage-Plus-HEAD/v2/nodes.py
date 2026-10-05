from __future__ import annotations

from typing import Any

from comfy_api.latest import ComfyExtension, io, sdk


FILE_TYPES = ["PNG", "JPEG", "WEBP (lossless)", "WEBP (lossy)"]


class SaveImagePlus(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("output",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SaveImagePlus",
            display_name="Save Image Plus",
            category="image",
            inputs=[
                io.Image.Input("images"),
                io.String.Input("filename_prefix", default="ComfyUI"),
                io.Combo.Input("file_type", options=FILE_TYPES),
                io.Boolean.Input("remove_metadata", default=False),
            ],
            hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo],
            outputs=[],
            is_output_node=True,
        )

    @classmethod
    async def execute(
        cls,
        images: sdk.ImageRef,
        filename_prefix: str = "ComfyUI",
        file_type: str = "PNG",
        remove_metadata: bool = False,
        prompt: Any = None,
        extra_pnginfo: Any = None,
    ) -> io.NodeOutput:
        del prompt, extra_pnginfo
        formats = {
            "PNG": ("png", False),
            "JPEG": ("jpeg", False),
            "WEBP (lossless)": ("webp", True),
            "WEBP (lossy)": ("webp", False),
        }
        if file_type not in formats:
            raise ValueError("unsupported file type")
        if not isinstance(filename_prefix, str):
            raise TypeError("filename_prefix must be a string")
        if type(remove_metadata) is not bool:
            raise TypeError("remove_metadata must be a boolean")
        image_format, lossless = formats[file_type]
        saved = await sdk.ctx().output.save_images(
            images,
            filename_prefix=filename_prefix,
            compress_level=4,
            save_metadata=not remove_metadata,
            image_format=image_format,
            quality=90,
            lossless=lossless,
            jpeg_subsampling="auto",
        )
        return io.NodeOutput(ui=saved)


NODE_CLASS_MAPPINGS = {"SaveImagePlus": SaveImagePlus}
NODE_DISPLAY_NAME_MAPPINGS = {"SaveImagePlus": "Save Image Plus"}


class SaveImagePlusExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [SaveImagePlus]


async def comfy_entrypoint() -> SaveImagePlusExtension:
    return SaveImagePlusExtension()
