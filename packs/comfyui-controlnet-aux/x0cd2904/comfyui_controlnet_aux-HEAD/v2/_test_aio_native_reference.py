from enum import Enum
MAX_RESOLUTION=16384
class INPUT(Enum):
    def IMAGE():
        return ("IMAGE",)
    def LATENT():
        return ("LATENT",)
    def MASK():
        return ("MASK",)
    def SEED(default=0):
        return ("INT", dict(default=default, min=0, max=0xffffffffffffffff))
    def RESOLUTION(default=512, min=64, max=MAX_RESOLUTION, step=64): 
        return ("INT", dict(default=default, min=min, max=max, step=step))
    def INT(default=0, min=0, max=MAX_RESOLUTION, step=1): 
        return ("INT", dict(default=default, min=min, max=max, step=step))
    def FLOAT(default=0, min=0, max=1, step=0.01):
        return ("FLOAT", dict(default=default, min=min, max=max, step=step))
    def STRING(default='', multiline=False): 
        return ("STRING", dict(default=default, multiline=multiline))
    def COMBO(values, default=None):
        return (values, dict(default=values[0] if default is None else default))
    def BOOLEAN(default=True):
        return ("BOOLEAN", dict(default=default))
def define_preprocessor_inputs(**arguments):
    return dict(
        required=dict(image=INPUT.IMAGE()),
        optional=arguments
    )
class AIO_Preprocessor:
    @classmethod
    def INPUT_TYPES(s):
        return define_preprocessor_inputs(
            preprocessor=INPUT.COMBO(PREPROCESSOR_OPTIONS, default="none"),
            resolution=INPUT.RESOLUTION()
        )

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "execute"

    CATEGORY = "ControlNet Preprocessors"

    def execute(self, preprocessor, image, resolution=512):
        if preprocessor == "none":
            return (image, )
        else:
            aux_class = AUX_NODE_MAPPINGS[preprocessor]
            input_types = aux_class.INPUT_TYPES()
            input_types = {
                **input_types["required"],
                **(input_types["optional"] if "optional" in input_types else {})
            }
            params = {}
            for name, input_type in input_types.items():
                if name == "image":
                    params[name] = image
                    continue

                if name == "resolution":
                    params[name] = resolution
                    continue

                if len(input_type) == 2 and ("default" in input_type[1]):
                    params[name] = input_type[1]["default"]
                    continue

                default_values = { "INT": 0, "FLOAT": 0.0 }
                if type(input_type[0]) is list:
                    for input_type_value in input_type[0]:
                        if input_type_value in default_values:
                            params[name] = default_values[input_type[0]]
                else:
                    if input_type[0] in default_values:
                        params[name] = default_values[input_type[0]]

            return getattr(aux_class(), aux_class.FUNCTION)(**params)
PREPROCESSOR_OPTIONS=['none', 'TilePreprocessor', 'TTPlanet_TileGF_Preprocessor', 'TTPlanet_TileSimple_Preprocessor', 'AnimeFace_SemSegPreprocessor', 'BinaryPreprocessor', 'Zoe-DepthMapPreprocessor', 'ColorPreprocessor', 'DepthAnythingPreprocessor', 'Zoe_DepthAnythingPreprocessor', 'DensePosePreprocessor', 'OneFormer-COCO-SemSegPreprocessor', 'OneFormer-ADE20K-SemSegPreprocessor', 'M-LSDPreprocessor', 'AnyLineArtPreprocessor_aux', 'DWPreprocessor', 'AnimalPosePreprocessor', 'DSINE-NormalMapPreprocessor', 'MediaPipe-FaceMeshPreprocessor', 'LineArtPreprocessor', 'MiDaS-NormalMapPreprocessor', 'MiDaS-DepthMapPreprocessor', 'DepthAnythingV2Preprocessor', 'CannyEdgePreprocessor', 'ShufflePreprocessor', 'Metric3D-DepthMapPreprocessor', 'Metric3D-NormalMapPreprocessor', 'AnimeLineArtPreprocessor', 'SAMPreprocessor', 'PyraCannyPreprocessor', 'HEDPreprocessor', 'FakeScribblePreprocessor', 'ScribblePreprocessor', 'Scribble_XDoG_Preprocessor', 'Scribble_PiDiNet_Preprocessor', 'PiDiNetPreprocessor', 'OpenposePreprocessor', 'LeReS-DepthMapPreprocessor', 'ImageLuminanceDetector', 'ImageIntensityDetector', 'UniFormer-SemSegPreprocessor', 'SemSegPreprocessor', 'MeshGraphormer-DepthMapPreprocessor', 'Manga2Anime_LineArt_Preprocessor', 'BAE-NormalMapPreprocessor', 'TEEDPreprocessor', 'LineartStandardPreprocessor']

from ._test_original_anyline._native_manga_reference import LineartMangaDetector
from ._test_original_anyline._native_anime_reference import LineartAnimeDetector
from ._test_original_anyline._native_batch_reference import CannyDetector,common_annotator_call as _original_common
def common_annotator_call(model,image,**kwargs):return _original_common(model,image,show_pbar=False,**kwargs)
class Canny_Edge_Preprocessor:

    @classmethod
    def INPUT_TYPES(s):
        return define_preprocessor_inputs(low_threshold=INPUT.INT(default=100, max=255), high_threshold=INPUT.INT(default=200, max=255), resolution=INPUT.RESOLUTION())
    RETURN_TYPES = ('IMAGE',)
    FUNCTION = 'execute'
    CATEGORY = 'ControlNet Preprocessors/Line Extractors'

    def execute(self, image, low_threshold=100, high_threshold=200, resolution=512, **kwargs):
        return (common_annotator_call(CannyDetector(), image, low_threshold=low_threshold, high_threshold=high_threshold, resolution=resolution),)

class Manga2Anime_LineArt_Preprocessor:

    @classmethod
    def INPUT_TYPES(s):
        return define_preprocessor_inputs(resolution=INPUT.RESOLUTION())
    RETURN_TYPES = ('IMAGE',)
    FUNCTION = 'execute'
    CATEGORY = 'ControlNet Preprocessors/Line Extractors'

    def execute(self, image, resolution=512, **kwargs):
        model = LineartMangaDetector.from_pretrained().to('cpu')
        out = common_annotator_call(model, image, resolution=resolution)
        del model
        return (out,)

class AnimeLineArt_Preprocessor:

    @classmethod
    def INPUT_TYPES(s):
        return define_preprocessor_inputs(resolution=INPUT.RESOLUTION())
    RETURN_TYPES = ('IMAGE',)
    FUNCTION = 'execute'
    CATEGORY = 'ControlNet Preprocessors/Line Extractors'

    def execute(self, image, resolution=512, **kwargs):
        model = LineartAnimeDetector.from_pretrained().to('cpu')
        out = common_annotator_call(model, image, resolution=resolution)
        del model
        return (out,)
AUX_NODE_MAPPINGS={'CannyEdgePreprocessor':Canny_Edge_Preprocessor,'Manga2Anime_LineArt_Preprocessor':Manga2Anime_LineArt_Preprocessor,'AnimeLineArtPreprocessor':AnimeLineArt_Preprocessor}
