"""TEST-only scalar observer; never part of the production SwapAndScale pack."""
import torch
from comfy_api.latest import io


class MervynSwapAndScaleScalarTestObserver(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MervynSwapAndScaleScalarTestObserver",
            category="tests/SwapAndScale",
            inputs=[
                io.Int.Input("actual_height"),
                io.Int.Input("actual_width"),
                io.Int.Input("expected_height"),
                io.Int.Input("expected_width"),
            ],
            outputs=[io.Image.Output()],
        )

    @classmethod
    def execute(cls, actual_height, actual_width, expected_height, expected_width):
        if any(type(value) is not int for value in (
            actual_height, actual_width, expected_height, expected_width,
        )):
            raise AssertionError("SwapAndScale TEST observer requires strict integers")
        if (expected_height, expected_width) != (704, 1440):
            raise AssertionError("SwapAndScale TEST observer literals changed")
        if (actual_height, actual_width) != (expected_height, expected_width):
            raise AssertionError("SwapAndScale TEST scalar result differs")
        image = torch.empty((1, 64, 64, 3), dtype=torch.float32, device="cpu")
        image[..., 0] = 0x12 / 255
        image[..., 1] = 0x34 / 255
        image[..., 2] = 0x56 / 255
        return io.NodeOutput(image)
