# Real frozen schemas; original host-only module is not imported.


# Secure V2 boundary: upstream compute above is retained verbatim.
from comfy_api.latest import io, sdk
from .. import _secure_boundary as boundary
from .._secure_schema import schema_for

class PixaromaPromptEach(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = []

    @classmethod
    def define_schema(cls):
        return schema_for("PixaromaPromptEach")

    @classmethod
    def validate_inputs(cls, **kwargs):
        return "comfyui-pixaroma/PixaromaPromptEach is not yet converted to Secure Nodes V2"

    @classmethod
    async def execute(cls, **kwargs):
        raise RuntimeError("comfyui-pixaroma/PixaromaPromptEach is not yet converted to Secure Nodes V2: outside the current conversion round")

NODE_CLASS_MAPPINGS = {"PixaromaPromptEach": PixaromaPromptEach}
NODE_DISPLAY_NAME_MAPPINGS = {"PixaromaPromptEach": "Prompt Each Pixaroma"}
