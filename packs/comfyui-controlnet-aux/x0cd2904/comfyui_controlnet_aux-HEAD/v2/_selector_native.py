PREPROCESSOR_OPTIONS = ['none', 'TilePreprocessor', 'TTPlanet_TileGF_Preprocessor', 'TTPlanet_TileSimple_Preprocessor', 'AnimeFace_SemSegPreprocessor', 'BinaryPreprocessor', 'Zoe-DepthMapPreprocessor', 'ColorPreprocessor', 'DepthAnythingPreprocessor', 'Zoe_DepthAnythingPreprocessor', 'DensePosePreprocessor', 'OneFormer-COCO-SemSegPreprocessor', 'OneFormer-ADE20K-SemSegPreprocessor', 'M-LSDPreprocessor', 'AnyLineArtPreprocessor_aux', 'DWPreprocessor', 'AnimalPosePreprocessor', 'DSINE-NormalMapPreprocessor', 'MediaPipe-FaceMeshPreprocessor', 'LineArtPreprocessor', 'MiDaS-NormalMapPreprocessor', 'MiDaS-DepthMapPreprocessor', 'DepthAnythingV2Preprocessor', 'CannyEdgePreprocessor', 'ShufflePreprocessor', 'Metric3D-DepthMapPreprocessor', 'Metric3D-NormalMapPreprocessor', 'AnimeLineArtPreprocessor', 'SAMPreprocessor', 'PyraCannyPreprocessor', 'HEDPreprocessor', 'FakeScribblePreprocessor', 'ScribblePreprocessor', 'Scribble_XDoG_Preprocessor', 'Scribble_PiDiNet_Preprocessor', 'PiDiNetPreprocessor', 'OpenposePreprocessor', 'LeReS-DepthMapPreprocessor', 'ImageLuminanceDetector', 'ImageIntensityDetector', 'UniFormer-SemSegPreprocessor', 'SemSegPreprocessor', 'MeshGraphormer-DepthMapPreprocessor', 'Manga2Anime_LineArt_Preprocessor', 'BAE-NormalMapPreprocessor', 'TEEDPreprocessor', 'LineartStandardPreprocessor']

class ControlNetPreprocessorSelector:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "preprocessor": (PREPROCESSOR_OPTIONS,),
            }
        }

    RETURN_TYPES = (PREPROCESSOR_OPTIONS,)
    RETURN_NAMES = ("preprocessor",)
    FUNCTION = "get_preprocessor"

    CATEGORY = "ControlNet Preprocessors"

    def get_preprocessor(self, preprocessor: str):
        return (preprocessor,)
