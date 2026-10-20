import math

from comfy_api.latest import ComfyExtension, io


class FindPerfectResolution(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("inspect",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="FindPerfectResolution",
            display_name="Find Perfect Resolution",
            category="utils",
            inputs=[
                io.Image.Input("image"),
                io.Int.Input("desired_width", default=512, min=64, max=4096, step=1),
                io.Int.Input("desired_height", default=512, min=64, max=4096, step=1),
                io.Int.Input("divisible_by", default=16, min=1, max=64, step=1),
            ],
            outputs=[
                io.Int.Output(display_name="width"),
                io.Int.Output(display_name="height"),
            ],
        )

    @classmethod
    async def execute(cls, image, desired_width, desired_height, divisible_by) -> io.NodeOutput:
        # Get original image dimensions
        _, orig_height, orig_width, _ = (await image.describe(max_value_chars=32))["shape"]

        # Calculate original aspect ratio
        aspect_ratio = orig_width / orig_height  # a/b where a=width, b=height

        # Calculate number of pixels (c = a * b)
        num_pixels = desired_width * desired_height

        # Calculate new height: round(sqrt((c * b) / a) / divisible_by) * divisible_by
        new_height = round(math.sqrt((num_pixels * orig_height) / orig_width) / divisible_by) * divisible_by

        # Calculate new width: round(((a / b) * sqrt((c * b) / a)) / divisible_by) * divisible_by
        new_width = round((aspect_ratio * math.sqrt((num_pixels * orig_height) / orig_width)) / divisible_by) * divisible_by

        return io.NodeOutput(int(new_width), int(new_height))


NODE_CLASS_MAPPINGS = {"FindPerfectResolution": FindPerfectResolution}
NODE_DISPLAY_NAME_MAPPINGS = {"FindPerfectResolution": "Find Perfect Resolution"}


class FindPerfectResolutionExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [FindPerfectResolution]


async def comfy_entrypoint() -> ComfyExtension:
    return FindPerfectResolutionExtension()
