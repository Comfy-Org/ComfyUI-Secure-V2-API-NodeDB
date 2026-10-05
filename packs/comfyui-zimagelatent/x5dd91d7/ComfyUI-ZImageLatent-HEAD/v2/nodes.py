"""Secure Nodes V2 implementation of Z Image Latent."""

from __future__ import annotations

from comfy_api.latest import ComfyExtension, io, sdk


RESOLUTION_OPTIONS = [
    "1024x1024 ( 1:1 )",
    "1152x896 ( 9:7 )",
    "896x1152 ( 7:9 )",
    "1152x864 ( 4:3 )",
    "864x1152 ( 3:4 )",
    "1248x832 ( 3:2 )",
    "832x1248 ( 2:3 )",
    "1280x720 ( 16:9 )",
    "720x1280 ( 9:16 )",
    "1344x576 ( 21:9 )",
    "576x1344 ( 9:21 )",
    "1280x1280 ( 1:1 )",
    "1440x1120 ( 9:7 )",
    "1120x1440 ( 7:9 )",
    "1472x1104 ( 4:3 )",
    "1104x1472 ( 3:4 )",
    "1536x1024 ( 3:2 )",
    "1024x1536 ( 2:3 )",
    "1536x864 ( 16:9 )",
    "864x1536 ( 9:16 )",
    "1680x720 ( 21:9 )",
    "720x1680 ( 9:21 )",
    "1536x1536 ( 1:1 )",
    "1728x1344 ( 9:7 )",
    "1344x1728 ( 7:9 )",
    "1728x1296 ( 4:3 )",
    "1296x1728 ( 3:4 )",
    "1872x1248 ( 3:2 )",
    "1248x1872 ( 2:3 )",
    "2048x1152 ( 16:9 )",
    "1152x2048 ( 9:16 )",
    "2016x864 ( 21:9 )",
    "864x2016 ( 9:21 )",
]


def parse_dimensions(resolution: str) -> tuple[int, int]:
    """Apply the pinned node's exact direct-input parsing and alignment."""
    dimensions = resolution.split(" ")[0]
    width, height = map(int, dimensions.split("x"))
    width = int((width // 16) * 16)
    height = int((height // 16) * 16)
    return width, height


class ZImageLatent(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ZImageLatent",
            display_name="Z Image Latent",
            category="Utilities",
            inputs=[
                io.Combo.Input("resolution", options=RESOLUTION_OPTIONS),
                io.Int.Input("batch_size", default=1, min=1, max=64),
            ],
            outputs=[
                io.Latent.Output("Latent", display_name="Latent"),
                io.Int.Output("Width", display_name="Width"),
                io.Int.Output("Height", display_name="Height"),
            ],
        )

    @classmethod
    async def execute(
        cls, resolution: str, batch_size: int = 1,
    ) -> io.NodeOutput:
        width, height = parse_dimensions(resolution)
        latent = await sdk.LatentRef.empty(
            width=width,
            height=height,
            batch_size=batch_size,
            channels=4,
            spatial_downscale_ratio=8,
        )
        return io.NodeOutput(latent, width, height)


NODE_CLASS_MAPPINGS = {"ZImageLatent": ZImageLatent}
NODE_DISPLAY_NAME_MAPPINGS = {"ZImageLatent": "Z Image Latent"}


class ZImageLatentExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [ZImageLatent]


async def comfy_entrypoint() -> ZImageLatentExtension:
    return ZImageLatentExtension()


__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "RESOLUTION_OPTIONS",
    "ZImageLatent",
    "ZImageLatentExtension",
    "comfy_entrypoint",
    "parse_dimensions",
]
