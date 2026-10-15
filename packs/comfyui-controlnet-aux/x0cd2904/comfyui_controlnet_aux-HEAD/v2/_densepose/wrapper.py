from .._annotator import common_annotator_call
from .schema_source import INPUT, define_preprocessor_inputs
from .detector import DenseposeDetector

class DensePose_Preprocessor:
    @classmethod
    def INPUT_TYPES(s):
        return define_preprocessor_inputs(
            model=INPUT.COMBO(["densepose_r50_fpn_dl.torchscript", "densepose_r101_fpn_dl.torchscript"]),
            cmap=INPUT.COMBO(["Viridis (MagicAnimate)", "Parula (CivitAI)"]),
            resolution=INPUT.RESOLUTION()
        )

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "execute"

    CATEGORY = "ControlNet Preprocessors/Faces and Poses Estimators"

    async def execute(self, image, model="densepose_r50_fpn_dl.torchscript", cmap="Viridis (MagicAnimate)", resolution=512, *, selection):
        model = (await DenseposeDetector.from_managed(filename=model, selection=selection)).to(selection['device'])
        return (common_annotator_call(model, image, cmap="viridis" if "Viridis" in cmap else "parula", resolution=resolution), )


NODE_CLASS_MAPPINGS = {
    "DensePosePreprocessor": DensePose_Preprocessor
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "DensePosePreprocessor": "DensePose Estimator"
}