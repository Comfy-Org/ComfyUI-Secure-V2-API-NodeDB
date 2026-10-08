"""Test-only public boundary probes, never registered as pack nodes."""
from comfy_api.latest import io, sdk

class LatentMetadataProbe(io.ComfyNode):
    @classmethod
    async def execute(cls, latent_image):
        return io.NodeOutput(len(await latent_image.value()))

class ModelInspectionProbe(io.ComfyNode):
    @classmethod
    async def execute(cls, model):
        return io.NodeOutput(await sdk.inspect(model))
