"""Secure Nodes V2 conversion of SD3/Flux latent resolution selectors."""

from __future__ import annotations

import math

import torch

from comfy_api.latest import io, sdk


SIZE_ITEMS = [
    ("0.3MP - 4:3 [640x480]", 640, 480),
    ("0.3MP - 16:9 [736x416]", 736, 416),
    ("0.64MP - 1:1 [800x800]", 800, 800),
    ("0.64MP - 4:3 [928x688]", 928, 688),
    ("0.64MP - 3:2 [976x656]", 976, 656),
    ("0.65MP - 16:9 [1072x608]", 1072, 608),
    ("0.9MP (WAN) - 1:1 [960x960]", 960, 960),
    ("0.9MP (WAN) - 2:3 [784x1184]", 784, 1184),
    ("0.9MP (WAN) - 4:3 [1104x832]", 1104, 832),
    ("0.9MP (WAN) - 16:9 [1280x720]", 1280, 720),
    ("0.9MP (WAN) - 21:9 [1472x624]", 1472, 624),
    ("1MP - 1:1 [1024x1024]", 1024, 1024),
    ("1MP - 8:5 [1216x768]", 1216, 768),
    ("1MP - 4:3 [1152x896]", 1152, 896),
    ("1MP - 3:2 [1216x832]", 1216, 832),
    ("1MP - 7:5 [1176x840]", 1176, 840),
    ("1MP - 16:9 [1344x768]", 1344, 768),
    ("1MP - 21:9 [1536x640]", 1536, 640),
    ("1MP - 19:9 [1472x704]", 1472, 704),
    ("1.5MP - 1:1 [1280x1280]", 1280, 1280),
    ("1.5MP - 3:2 [1520x1040]", 1520, 1040),
    ("1.5MP - 4:3 [1440x1120]", 1440, 1120),
    ("1.5MP - 16:9 [1680x960]", 1680, 960),
    ("1.5MP - 21:9 [1920x800]", 1920, 800),
    ("1.7MP - 1:1 [1328x1328]", 1328, 1328),
    ("1.7MP - 3:2 [1584x1056]", 1584, 1056),
    ("1.7MP - 4:3 [1472x1140]", 1472, 1140),
    ("1.7MP - 16:9 [1664x928]", 1664, 928),
    ("2MP - 1:1 [1408x1408]", 1408, 1408),
    ("2MP - 3:2 [1728x1152]", 1728, 1152),
    ("2MP - 4:3 [1664x1216]", 1664, 1216),
    ("2MP - 16:9 [1920x1088]", 1920, 1088),
    ("2MP - 21:9 [2176x960]", 2176, 960),
    ("3MP - 1:1 [1728x1728]", 1728, 1728),
    ("3MP - 3:2 [2112x1408]", 2112, 1408),
    ("3MP - 4:3 [2000x1504]", 2000, 1504),
    ("3MP - 16:9 [2304x1296]", 2304, 1296),
    ("3MP - 21:9 [2640x1136]", 2640, 1136),
    ("4MP - 1:1 [2048x2048]", 2048, 2048),
    ("4MP - 3:2 [2448x1632]", 2448, 1632),
    ("4MP - 4:3 [2304x1728]", 2304, 1728),
    ("4MP - 16:9 [2688x1520]", 2688, 1520),
    ("4MP - 21:9 [3072x1312]", 3072, 1312),
]
SIZE_OPTIONS = [item[0] for item in SIZE_ITEMS]
SIZES = {name: (width, height) for name, width, height in SIZE_ITEMS}
RATIOS = [
    "1:1", "16:9", "9:16", "4:3", "3:4", "4:5", "5:4",
    "3:2", "2:3", "21:9", "9:21", "2:1", "1:2",
]
MEGAPIXELS = [value * 0.5 for value in range(2, 17)]
LATENT_TYPES = ["SD3/Flux/Z-Image/Qwen/etc", "Flux2"]
MAX_LATENT_ELEMENTS = 134_217_728


def _latent(width: int, height: int, batch_size: int, channels: int, divisor: int):
    shape = (batch_size, channels, height // divisor, width // divisor)
    elements = math.prod(shape)
    if elements > MAX_LATENT_ELEMENTS:
        raise ValueError("requested latent exceeds the secure allocation limit")
    return torch.ones(shape) * 0.0609


async def _output(width: int, height: int, samples: torch.Tensor) -> io.NodeOutput:
    latent = await sdk.LatentRef.from_value({"samples": samples})
    return io.NodeOutput(width, height, latent)


class SD3LatentSelectRes(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SD3LatentSelectRes",
            display_name="SD3/Flux Select Latent Resolution",
            category="generate/sd3",
            is_output_node=True,
            inputs=[
                io.Combo.Input("size_selected", options=SIZE_OPTIONS),
                io.Boolean.Input("landscape", default=True),
                io.Int.Input("batch_size", default=1, min=1, max=4096),
            ],
            outputs=[
                io.Int.Output("width", display_name="width"),
                io.Int.Output("height", display_name="height"),
                io.Latent.Output("samples", display_name="samples"),
            ],
        )

    @classmethod
    async def execute(
        cls, size_selected: str, landscape: bool, batch_size: int
    ) -> io.NodeOutput:
        if size_selected not in SIZES:
            raise ValueError("unknown resolution preset")
        width, height = SIZES[size_selected]
        if not landscape:
            width, height = height, width
        return await _output(
            width, height, _latent(width, height, batch_size, 16, 8)
        )


class SD3LatentSelectResV2(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SD3LatentSelectResV2",
            display_name="SD3/Flux Select Latent Resolution V2",
            category="generate/sd3",
            is_output_node=True,
            inputs=[
                io.Combo.Input("aspect_ratio", options=RATIOS, default="1:1"),
                io.Combo.Input("megapixels", options=MEGAPIXELS, default=1.0),
                io.Combo.Input(
                    "latent_type", options=LATENT_TYPES,
                    default="SD3/Flux/Z-Image/Qwen/etc",
                ),
                io.Int.Input("batch_size", default=1, min=1, max=4096),
            ],
            outputs=[
                io.Int.Output("width", display_name="width"),
                io.Int.Output("height", display_name="height"),
                io.Latent.Output("samples", display_name="samples"),
            ],
        )

    @classmethod
    async def execute(
        cls, aspect_ratio: str, megapixels: float,
        latent_type: str, batch_size: int,
    ) -> io.NodeOutput:
        if aspect_ratio not in RATIOS or megapixels not in MEGAPIXELS:
            raise ValueError("unknown resolution option")
        if latent_type not in LATENT_TYPES:
            raise ValueError("unknown latent type")
        width_ratio, height_ratio = map(int, aspect_ratio.split(":"))
        ratio = width_ratio / height_ratio
        target_area = float(megapixels) * 1_048_576
        height = (target_area / ratio) ** 0.5
        width = height * ratio
        width = round(width / 16) * 16
        height = round(height / 16) * 16
        channels, divisor = (128, 16) if latent_type == "Flux2" else (16, 8)
        return await _output(
            width, height,
            _latent(width, height, batch_size, channels, divisor),
        )


NODE_CLASS_MAPPINGS = {
    "SD3LatentSelectRes": SD3LatentSelectRes,
    "SD3LatentSelectResV2": SD3LatentSelectResV2,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "SD3LatentSelectRes": "SD3/Flux Select Latent Resolution",
    "SD3LatentSelectResV2": "SD3/Flux Select Latent Resolution V2",
}
