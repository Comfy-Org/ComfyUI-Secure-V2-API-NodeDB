# Real frozen schemas; original host-only module is not imported.


# Secure V2 boundary: upstream compute above is retained verbatim.
from comfy_api.latest import io, sdk
from .. import _secure_boundary as boundary
from .._secure_schema import schema_for

class PixaromaSaveImage(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ["graph", "raw", "ui", "assets", "graph.metadata", "output"]

    @classmethod
    def define_schema(cls):
        return schema_for("PixaromaSaveImage")

    @classmethod
    async def execute(cls, **kwargs):
        kwargs = await boundary.with_hidden("PixaromaSaveImage", kwargs)
        from .. import _secure_io
        return await _secure_io.execute("PixaromaSaveImage", kwargs)

    @classmethod
    async def fingerprint_inputs(cls, **kwargs):
        kwargs = await boundary.with_hidden("PixaromaSaveImage", kwargs)
        return float("nan")

NODE_CLASS_MAPPINGS = {"PixaromaSaveImage": PixaromaSaveImage}
NODE_DISPLAY_NAME_MAPPINGS = {"PixaromaSaveImage": "Save Image Pixaroma"}
