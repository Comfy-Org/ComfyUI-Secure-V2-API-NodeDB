from .._annotator import common_annotator_call
from .._diffusionedge.schema_helpers import define_preprocessor_inputs, INPUT
import comfy.model_management as model_management

class Depth_Anything_Preprocessor:
    @classmethod
    def INPUT_TYPES(s):
        return define_preprocessor_inputs(
            ckpt_name=INPUT.COMBO(
                ["depth_anything_vitl14.pth", "depth_anything_vitb14.pth", "depth_anything_vits14.pth"]
            ),
            resolution=INPUT.RESOLUTION()
        )

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "execute"

    CATEGORY = "ControlNet Preprocessors/Normal and Depth Estimators"

    def execute(self, image, ckpt_name="depth_anything_vitl14.pth", resolution=512, **kwargs):
        from .selection import require_constructor
        require_constructor()
        from .transformers import DepthAnythingDetector

        model = DepthAnythingDetector.from_pretrained(filename=ckpt_name).to(model_management.get_torch_device())
        out = common_annotator_call(model, image, resolution=resolution)
        del model
        return (out, )

NODE_CLASS_MAPPINGS = {"DepthAnythingPreprocessor": Depth_Anything_Preprocessor}
NODE_DISPLAY_NAME_MAPPINGS = {"DepthAnythingPreprocessor": "Depth Anything"}
