# Real frozen schemas; original host-only module is not imported.


# Secure V2 boundary: upstream compute above is retained verbatim.
from comfy_api.latest import io, sdk
from .. import _secure_boundary as boundary
from .._secure_schema import schema_for

class PixaromaMusicPrompt(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = []

    @classmethod
    def define_schema(cls):
        return schema_for("PixaromaMusicPrompt")

    @classmethod
    def validate_inputs(cls, **kwargs):
        return "comfyui-pixaroma/PixaromaMusicPrompt is not yet converted to Secure Nodes V2"

    @classmethod
    async def execute(cls, **kwargs):
        raise RuntimeError("comfyui-pixaroma/PixaromaMusicPrompt is not yet converted to Secure Nodes V2: outside the current conversion round")

NODE_CLASS_MAPPINGS = {"PixaromaMusicPrompt": PixaromaMusicPrompt}
NODE_DISPLAY_NAME_MAPPINGS = {"PixaromaMusicPrompt": "Music Prompt Pixaroma"}
