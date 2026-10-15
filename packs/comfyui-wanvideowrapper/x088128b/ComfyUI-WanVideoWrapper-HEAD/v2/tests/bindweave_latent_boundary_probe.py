"""Unregistered controls for existing public projections/authority separation."""
from comfy_api.latest import io


class JackBindweaveLatentProbe(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()

    @classmethod
    async def execute(cls,latent,mode):
        if mode=='whole':return io.NodeOutput(await latent.value())
        samples=await latent.samples()
        if mode=='raw':return io.NodeOutput(await samples.raw())
        return io.NodeOutput(samples)
