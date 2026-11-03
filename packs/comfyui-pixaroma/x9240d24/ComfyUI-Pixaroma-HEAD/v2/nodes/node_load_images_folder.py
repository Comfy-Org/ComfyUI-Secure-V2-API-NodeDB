# Real frozen schemas; original host-only module is not imported.


# Secure V2 boundary: upstream compute above is retained verbatim.
from comfy_api.latest import io, sdk
from .. import _secure_boundary as boundary
from .._secure_schema import schema_for

class PixaromaLoadImagesFolder(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = []

    @classmethod
    def define_schema(cls):
        return schema_for("PixaromaLoadImagesFolder")

    @classmethod
    def validate_inputs(cls, **kwargs):
        return "comfyui-pixaroma/PixaromaLoadImagesFolder is not yet converted to Secure Nodes V2"

    @classmethod
    async def execute(cls, **kwargs):
        raise RuntimeError("comfyui-pixaroma/PixaromaLoadImagesFolder is not yet converted to Secure Nodes V2: browser-approved arbitrary host folders and absolute path outputs have no selected guest asset API")

NODE_CLASS_MAPPINGS = {"PixaromaLoadImagesFolder": PixaromaLoadImagesFolder}
NODE_DISPLAY_NAME_MAPPINGS = {"PixaromaLoadImagesFolder": "Load Images from Folder Pixaroma"}
