# Real frozen schemas; original host-only module is not imported.


# Secure V2 boundary: upstream compute above is retained verbatim.
from comfy_api.latest import io, sdk
from .. import _secure_boundary as boundary
from .._secure_schema import schema_for

class PixaromaPromptReader(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ["assets"]

    @classmethod
    def define_schema(cls):
        return schema_for("PixaromaPromptReader")

    @classmethod
    async def execute(cls, **kwargs):
        from .. import _secure_io
        return await _secure_io.execute("PixaromaPromptReader", kwargs)

    @classmethod
    def validate_inputs(cls, **kwargs):
        return True

    @classmethod
    async def fingerprint_inputs(cls, **kwargs):
        return await boundary.asset_fingerprint(kwargs.get('filename') or kwargs.get('image', ''))

NODE_CLASS_MAPPINGS = {"PixaromaPromptReader": PixaromaPromptReader}
NODE_DISPLAY_NAME_MAPPINGS = {"PixaromaPromptReader": "Prompt Reader Pixaroma"}
