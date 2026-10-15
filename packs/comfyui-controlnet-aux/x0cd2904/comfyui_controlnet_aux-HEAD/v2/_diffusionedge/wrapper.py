from .schema_helpers import INPUT, define_preprocessor_inputs
from .._annotator import common_annotator_call
from .detector import DiffusionEdgeDetector
from .selection import validate_selection

class DiffusionEdge_Preprocessor:
    @classmethod
    def INPUT_TYPES(s):
        return define_preprocessor_inputs(
            environment=INPUT.COMBO(["indoor", "urban", "natrual"]),
            patch_batch_size=INPUT.INT(default=4, min=1, max=16),
            resolution=INPUT.RESOLUTION()
        )

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "execute"

    CATEGORY = "ControlNet Preprocessors/Line Extractors"

    def execute(self, image, environment="indoor", patch_batch_size=4, resolution=512, *, selection, **kwargs):
        validate_selection(selection)

        model = DiffusionEdgeDetector \
            .from_managed(filename = f"diffusion_edge_{environment}.pt", selection=selection) \
            .to(selection["device"])
        out = common_annotator_call(model, image, resolution=resolution, patch_batch_size=patch_batch_size)
        del model
        return (out, )
