# Real frozen schemas; original host-only module is not imported.


# Secure V2 boundary: upstream compute above is retained verbatim.
from comfy_api.latest import io, sdk
from .. import _secure_boundary as boundary
from .._secure_schema import schema_for

class PixaromaLoraLoader(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ["graph", "assets"]

    @classmethod
    def define_schema(cls):
        return schema_for("PixaromaLoraLoader")

    @classmethod
    async def execute(cls, **kwargs):
        kwargs = await boundary.with_hidden("PixaromaLoraLoader", kwargs)
        from .. import _secure_io
        return await _secure_io.execute("PixaromaLoraLoader", kwargs)

NODE_CLASS_MAPPINGS = {"PixaromaLoraLoader": PixaromaLoraLoader}
NODE_DISPLAY_NAME_MAPPINGS = {"PixaromaLoraLoader": "LoRA Loader Pixaroma"}
