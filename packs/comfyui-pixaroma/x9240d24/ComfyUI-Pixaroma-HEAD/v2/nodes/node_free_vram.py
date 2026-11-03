# Real frozen schemas; original host-only module is not imported.


# Secure V2 boundary: upstream compute above is retained verbatim.
from comfy_api.latest import io, sdk
from .. import _secure_boundary as boundary
from .._secure_schema import schema_for

class PixaromaFreeVram(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = []

    @classmethod
    def define_schema(cls):
        return schema_for("PixaromaFreeVram")

    @classmethod
    def validate_inputs(cls, **kwargs):
        return "comfyui-pixaroma/PixaromaFreeVram is not yet converted to Secure Nodes V2"

    @classmethod
    async def execute(cls, **kwargs):
        raise RuntimeError("comfyui-pixaroma/PixaromaFreeVram is not yet converted to Secure Nodes V2: memory_cleanup cannot preserve forced cache-emptying semantics and step order")

NODE_CLASS_MAPPINGS = {"PixaromaFreeVram": PixaromaFreeVram}
NODE_DISPLAY_NAME_MAPPINGS = {"PixaromaFreeVram": "Free VRAM Pixaroma"}
