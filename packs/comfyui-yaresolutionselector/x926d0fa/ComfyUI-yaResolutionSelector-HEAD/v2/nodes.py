import re

from comfy_api.latest import ComfyExtension, io


RATIOS = [
    "1:1",
    "landscape (5:4)",
    "landscape (4:3)",
    "landscape (3:2)",
    "landscape (16:10)",
    "landscape (16:9)",
    "landscape (21:9)",
    "portrait (4:5)",
    "portrait (3:4)",
    "portrait (2:3)",
    "portrait (9:10)",
    "portrait (9:16)",
    "portrait (9:21)",
]


class Dimensions:
    def __init__(self, width, height):
        self.width = width
        self.height = height

    @property
    def width(self) -> int:
        return self._width

    @width.setter
    def width(self, value):
        if value < 64:
            raise ValueError("width of less than 64 pixel")
        self._width = int(value / 2) * 2 if value % 2 else int(value)

    @property
    def height(self) -> int:
        return self._height

    @height.setter
    def height(self, value):
        if value < 64:
            raise ValueError("height of less than 64 pixel")
        self._height = int(value / 2) * 2 if value % 2 else int(value)


def calculate_aspect_ratio(
    base_resolution: int, ratio: float, overextend: bool,
) -> Dimensions:
    width = base_resolution
    height = base_resolution
    if overextend:
        if ratio > 1:
            height *= ratio
        else:
            width /= ratio
    elif ratio > 1:
        width /= ratio
    else:
        height *= ratio
    return Dimensions(width, height)


def calculate_constant_constant_resolution(
    base_resolution: int, ratio: float,
) -> Dimensions:
    pixel_count = base_resolution**2
    new_height = (pixel_count * ratio) ** 0.5
    new_width = new_height / ratio
    return Dimensions(new_width, new_height)


def _result(dimensions: Dimensions, ratio: float) -> io.NodeOutput:
    return io.NodeOutput(
        dimensions.width,
        dimensions.height,
        ui={
            "width": [dimensions.width],
            "height": [dimensions.height],
            "ratio": [ratio],
        },
    )


class YARS(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="YARS",
            display_name="yaResolution Selector",
            category="utils",
            inputs=[
                io.Int.Input(
                    "base_resolution", default=512, min=512, max=8192,
                    step=128,
                ),
                io.Combo.Input("aspect_ratio", options=RATIOS),
                io.Boolean.Input(
                    "overextend", default=False,
                    label_on="yes ", label_off="no ",
                ),
            ],
            outputs=[
                io.Int.Output("width", display_name="width"),
                io.Int.Output("height", display_name="height"),
            ],
        )

    @classmethod
    def execute(
        cls, base_resolution: int, aspect_ratio: str, overextend: bool,
    ) -> io.NodeOutput:
        match = re.search(r"(\d+):(\d+)", aspect_ratio)
        if not match:
            raise ValueError(
                f"Could't find aspect ratio in string `{aspect_ratio}`",
            )
        ratio = int(match.group(2)) / int(match.group(1))
        return _result(
            calculate_aspect_ratio(base_resolution, ratio, overextend), ratio,
        )


class YARSAdv(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="YARSAdv",
            display_name="yaResolution Selector (Advanced)",
            category="utils",
            inputs=[
                io.Int.Input(
                    "base_resolution", default=512, min=512, max=8192,
                    step=128,
                ),
                io.Int.Input(
                    "width_ratio", default=1, min=1, max=1024, step=1,
                ),
                io.Int.Input(
                    "height_ratio", default=1, min=1, max=1024, step=1,
                ),
                io.Boolean.Input(
                    "overextend", default=False,
                    label_on="yes ", label_off="no ",
                ),
                io.Boolean.Input(
                    "constant_resolution", default=False,
                    label_on="yes ", label_off="no ",
                ),
            ],
            outputs=[
                io.Int.Output("width", display_name="width"),
                io.Int.Output("height", display_name="height"),
            ],
        )

    @classmethod
    def execute(
        cls,
        base_resolution: int,
        width_ratio: int,
        height_ratio: int,
        overextend: bool,
        constant_resolution: bool,
    ) -> io.NodeOutput:
        ratio = height_ratio / width_ratio
        dimensions = (
            calculate_constant_constant_resolution(base_resolution, ratio)
            if constant_resolution
            else calculate_aspect_ratio(base_resolution, ratio, overextend)
        )
        return _result(dimensions, width_ratio / height_ratio)


NODE_CLASS_MAPPINGS = {"YARS": YARS, "YARSAdv": YARSAdv}
NODE_DISPLAY_NAME_MAPPINGS = {
    "YARS": "yaResolution Selector",
    "YARSAdv": "yaResolution Selector (Advanced)",
}


class YARSExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [YARS, YARSAdv]


async def comfy_entrypoint() -> YARSExtension:
    return YARSExtension()
