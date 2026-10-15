from .._annotator import common_annotator_call
from .._diffusionedge.schema_helpers import define_preprocessor_inputs, INPUT
import comfy.model_management as model_management

class Zoe_Depth_Anything_Preprocessor:
    @classmethod
    def INPUT_TYPES(s):
        return define_preprocessor_inputs(
            environment=INPUT.COMBO(["indoor", "outdoor"]),
            resolution=INPUT.RESOLUTION()
        )

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "execute"

    CATEGORY = "ControlNet Preprocessors/Normal and Depth Estimators"

    def execute(self, image, environment="indoor", resolution=512, **kwargs):
        from .selection import require_constructor
        require_constructor()
        from .transformers import ZoeDepthAnythingDetector
        ckpt_name = "depth_anything_metric_depth_indoor.pt" if environment == "indoor" else "depth_anything_metric_depth_outdoor.pt"
        model = ZoeDepthAnythingDetector.from_pretrained(filename=ckpt_name).to(model_management.get_torch_device())
        out = common_annotator_call(model, image, resolution=resolution)
        del model
        return (out, )

NODE_CLASS_MAPPINGS = {"Zoe_DepthAnythingPreprocessor": Zoe_Depth_Anything_Preprocessor}
NODE_DISPLAY_NAME_MAPPINGS = {"Zoe_DepthAnythingPreprocessor": "Zoe Depth Anything"}
