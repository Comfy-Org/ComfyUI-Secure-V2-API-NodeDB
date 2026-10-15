import os
# Disable NPU device initialization and problematic MMCV ops to prevent RuntimeError
os.environ['NPU_DEVICE_COUNT'] = '0'
os.environ['MMCV_WITH_OPS'] = '0'

from .._annotator import common_annotator_call
from .schema_source import define_preprocessor_inputs, INPUT
from .detector import UniformerSegmentor

class Uniformer_SemSegPreprocessor:
    @classmethod
    def INPUT_TYPES(s):
        return define_preprocessor_inputs(resolution=INPUT.RESOLUTION())

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "semantic_segmentate"

    CATEGORY = "ControlNet Preprocessors/Semantic Segmentation"

    async def semantic_segmentate(self, image, resolution=512, *, selection):

        model = (await UniformerSegmentor.from_managed(selection=selection)).to(selection['device'])
        out = common_annotator_call(model, image, resolution=resolution)
        del model
        return (out, )

NODE_CLASS_MAPPINGS = {
    "UniFormer-SemSegPreprocessor": Uniformer_SemSegPreprocessor,
    "SemSegPreprocessor": Uniformer_SemSegPreprocessor,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "UniFormer-SemSegPreprocessor": "UniFormer Segmentor",
    "SemSegPreprocessor": "Semantic Segmentor (legacy, alias for UniFormer)",
}