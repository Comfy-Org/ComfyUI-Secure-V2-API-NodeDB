"""Public SDK registration for the unchanged upstream aspect-ratio calculation."""

from comfy_api.latest import io

from .aspect_ratio_node import SimpleAspectRatio as _OriginalSimpleAspectRatio


class SimpleAspectRatio(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        required = _OriginalSimpleAspectRatio.INPUT_TYPES()["required"]
        return io.Schema(
            node_id="SimpleAspectRatio",
            display_name="Simple Aspect Ratio",
            category=_OriginalSimpleAspectRatio.CATEGORY,
            inputs=[
                io.Combo.Input("aspectRatio", options=required["aspectRatio"][0]),
                io.Combo.Input("orientation", options=required["orientation"][0]),
            ],
            outputs=[io.Int.Output("width"), io.Int.Output("height")],
        )

    @classmethod
    def execute(cls, aspectRatio, orientation):
        return io.NodeOutput(
            *_OriginalSimpleAspectRatio().get_size(aspectRatio, orientation)
        )


NODE_CLASS_MAPPINGS = {"SimpleAspectRatio": SimpleAspectRatio}
NODE_DISPLAY_NAME_MAPPINGS = {"SimpleAspectRatio": "Simple Aspect Ratio"}
