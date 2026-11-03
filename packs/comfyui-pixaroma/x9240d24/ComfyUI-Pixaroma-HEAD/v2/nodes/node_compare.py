# Real frozen schemas; original host-only module is not imported.


# Secure V2 boundary: upstream compute above is retained verbatim.
from comfy_api.latest import io, sdk
from .. import _secure_boundary as boundary
from .._secure_schema import schema_for

class PixaromaCompare(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ["raw", "ui"]

    @classmethod
    def define_schema(cls):
        return schema_for("PixaromaCompare")

    @classmethod
    async def execute(cls, **kwargs):
        from .. import _secure_io
        return await _secure_io.execute("PixaromaCompare", kwargs)

NODE_CLASS_MAPPINGS = {"PixaromaCompare": PixaromaCompare}
NODE_DISPLAY_NAME_MAPPINGS = {"PixaromaCompare": "Image Compare Pixaroma"}
