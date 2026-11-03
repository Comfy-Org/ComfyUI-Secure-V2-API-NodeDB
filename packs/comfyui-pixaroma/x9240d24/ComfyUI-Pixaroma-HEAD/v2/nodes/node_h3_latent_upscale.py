# Real frozen schemas; original host-only module is not imported.


# Secure V2 boundary: upstream compute above is retained verbatim.
from comfy_api.latest import io, sdk
from .. import _secure_boundary as boundary
from .._secure_schema import schema_for

class PixaromaH3LatentUpscale(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = []

    @classmethod
    def define_schema(cls):
        return schema_for("PixaromaH3LatentUpscale")

    @classmethod
    def validate_inputs(cls, **kwargs):
        return "comfyui-pixaroma/PixaromaH3LatentUpscale is not yet converted to Secure Nodes V2"

    @classmethod
    async def execute(cls, **kwargs):
        raise RuntimeError("comfyui-pixaroma/PixaromaH3LatentUpscale is not yet converted to Secure Nodes V2: outside the current conversion round")

NODE_CLASS_MAPPINGS = {"PixaromaH3LatentUpscale": PixaromaH3LatentUpscale}
NODE_DISPLAY_NAME_MAPPINGS = {"PixaromaH3LatentUpscale": "H3 Latent Upscale Pixaroma"}
