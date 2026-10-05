"""Secure Nodes V2 conversion of mittimi Recalculate Size."""

from comfy_api.latest import ComfyExtension, io


class RecalculateSizeMittimi01(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="RecalculateSizeMittimi01",
            display_name="RecalculateSize01",
            category="mittimiTools",
            inputs=[
                io.Int.Input("Width", default=512, min=1, max=2_147_483_647),
                io.Int.Input("Height", default=512, min=1, max=2_147_483_647),
                io.Float.Input(
                    "Magnification",
                    default=1.0,
                    min=0.01,
                    max=9999.99,
                    step=0.01,
                ),
            ],
            outputs=[
                io.Int.Output("width", display_name="width"),
                io.Int.Output("height", display_name="height"),
            ],
        )

    @classmethod
    def execute(cls, Width, Height, Magnification) -> io.NodeOutput:
        return io.NodeOutput(int(Width * Magnification), int(Height * Magnification))


NODE_CLASS_MAPPINGS = {"RecalculateSizeMittimi01": RecalculateSizeMittimi01}
NODE_DISPLAY_NAME_MAPPINGS = {"RecalculateSizeMittimi01": "RecalculateSize01"}


class MittimiRecalculateSizeExtension(ComfyExtension):
    async def get_node_list(self):
        return [RecalculateSizeMittimi01]


async def comfy_entrypoint() -> MittimiRecalculateSizeExtension:
    return MittimiRecalculateSizeExtension()
