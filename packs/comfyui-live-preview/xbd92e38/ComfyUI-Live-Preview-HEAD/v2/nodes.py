"""Secure backend for the Live Preview activation node."""

from __future__ import annotations

from comfy_api.latest import ComfyExtension, io, sdk


class LivePreview(io.ComfyNode):
    """Pass an image reference through while enabling the frontend overlay."""

    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="LivePreview",
            display_name="Live Preview (Large)",
            category="image",
            description=(
                "Pass-through node that activates the large live preview overlay window."
            ),
            inputs=[io.Image.Input("images")],
            outputs=[io.Image.Output("images")],
        )

    @classmethod
    def execute(cls, images: sdk.ImageRef) -> io.NodeOutput:
        return io.NodeOutput(images)


NODE_CLASS_MAPPINGS = {"LivePreview": LivePreview}


class LivePreviewExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [LivePreview]


async def comfy_entrypoint() -> LivePreviewExtension:
    return LivePreviewExtension()
