"""TEST-only consumers; never part of the canonical production conversion."""
import json
import torch
from comfy_api.latest import io, sdk


def checked_image(width, height, expected_width, expected_height):
    if type(width) is not int or type(height) is not int:
        raise AssertionError("Size TEST integer output type differs")
    if (width, height) != (expected_width, expected_height):
        raise AssertionError("Size TEST dimensions differ from actual original result")
    if not (1 <= width <= 2048 and 1 <= height <= 2048 and width * height <= 2097152):
        raise AssertionError("Size TEST image fixture exceeds bounds")
    image = torch.empty((1, height, width, 3), dtype=torch.float32, device="cpu")
    image[..., 0] = 0x12 / 255
    image[..., 1] = 0x34 / 255
    image[..., 2] = 0x56 / 255
    return image


class MoeSizeScalarRenderOracle(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MoeSizeScalarRenderOracle", category="tests/SizeFromPresets",
            inputs=[io.Int.Input("width"), io.Int.Input("height"),
                    io.Int.Input("expected_width"), io.Int.Input("expected_height")],
            outputs=[io.Image.Output()],
        )

    @classmethod
    def execute(cls, width, height, expected_width, expected_height):
        return io.NodeOutput(checked_image(width, height, expected_width, expected_height))


class MoeSizeLatentRenderOracle(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MoeSizeLatentRenderOracle", category="tests/SizeFromPresets",
            inputs=[io.Latent.Input("latent"), io.Int.Input("width"), io.Int.Input("height"),
                    io.Int.Input("expected_width"), io.Int.Input("expected_height"),
                    io.Int.Input("expected_batch"), io.String.Input("expected_dtype")],
            outputs=[io.Image.Output()],
        )

    @classmethod
    async def execute(cls, latent, width, height, expected_width, expected_height,
                      expected_batch, expected_dtype):
        if not isinstance(latent, sdk.LatentRef):
            raise AssertionError("Size TEST did not receive an actual SDK LatentRef")
        value = await latent.value()
        samples = value["samples"]
        if not isinstance(samples, torch.Tensor):
            raise AssertionError("Size TEST latent samples are not a real tensor")
        if type(expected_batch) is not int or expected_batch not in (1, 2):
            raise AssertionError("Size TEST batch fixture exceeds bounds")
        if expected_dtype not in ("float32", "float64"):
            raise AssertionError("Size TEST selected dtype fixture unavailable")
        if tuple(samples.shape) != (expected_batch, 4, expected_height // 8, expected_width // 8):
            raise AssertionError("Size TEST latent floor-to-eight shape differs")
        if samples.device.type != "cpu" or samples.dtype != getattr(torch, expected_dtype):
            raise AssertionError("Size TEST latent CPU/dtype differs from selected target fixture")
        nonzero = torch.count_nonzero(samples).item()
        if nonzero != 0:
            raise AssertionError("Size TEST latent is not all zero")
        image = checked_image(width, height, expected_width, expected_height)
        facts = {"shape": list(samples.shape), "batch": int(samples.shape[0]),
                 "dtype": str(samples.dtype), "device": str(samples.device), "nonzero": int(nonzero),
                 "reported_dimensions": [width, height]}
        return io.NodeOutput(await sdk.ImageRef.from_value(image), ui={"text": [json.dumps(facts, sort_keys=True)]})


NODE_CLASS_MAPPINGS = {
    "MoeSizeScalarRenderOracle": MoeSizeScalarRenderOracle,
    "MoeSizeLatentRenderOracle": MoeSizeLatentRenderOracle,
}
