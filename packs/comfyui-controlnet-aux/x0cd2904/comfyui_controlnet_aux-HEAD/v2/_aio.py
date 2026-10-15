"""Native AIO parameter/default construction; no runtime/provider imports.

The copied list-default branch intentionally retains the upstream TypeError.
AUX_NODE_IDS is the exact source wrapper registry, including excluded choices.
"""

AUX_NODE_IDS = ('AnimeFace_SemSegPreprocessor', 'AnyLineArtPreprocessor_aux', 'BinaryPreprocessor', 'CannyEdgePreprocessor', 'ColorPreprocessor', 'DensePosePreprocessor', 'DepthAnythingPreprocessor', 'Zoe_DepthAnythingPreprocessor', 'DepthAnythingV2Preprocessor', 'DiffusionEdge_Preprocessor', 'DSINE-NormalMapPreprocessor', 'DWPreprocessor', 'AnimalPosePreprocessor', 'HEDPreprocessor', 'FakeScribblePreprocessor', 'InpaintPreprocessor', 'LeReS-DepthMapPreprocessor', 'LineArtPreprocessor', 'AnimeLineArtPreprocessor', 'LineartStandardPreprocessor', 'Manga2Anime_LineArt_Preprocessor', 'MediaPipe-FaceMeshPreprocessor', 'MeshGraphormer-DepthMapPreprocessor', 'MeshGraphormer+ImpactDetector-DepthMapPreprocessor', 'Metric3D-DepthMapPreprocessor', 'Metric3D-NormalMapPreprocessor', 'MiDaS-NormalMapPreprocessor', 'MiDaS-DepthMapPreprocessor', 'M-LSDPreprocessor', 'BAE-NormalMapPreprocessor', 'OneFormer-COCO-SemSegPreprocessor', 'OneFormer-ADE20K-SemSegPreprocessor', 'OpenposePreprocessor', 'PiDiNetPreprocessor', 'SavePoseKpsAsJsonFile', 'FacialPartColoringFromPoseKps', 'UpperBodyTrackingFromPoseKps', 'RenderPeopleKps', 'RenderAnimalKps', 'PyraCannyPreprocessor', 'ImageLuminanceDetector', 'ImageIntensityDetector', 'ScribblePreprocessor', 'Scribble_XDoG_Preprocessor', 'Scribble_PiDiNet_Preprocessor', 'SAMPreprocessor', 'ShufflePreprocessor', 'TEEDPreprocessor', 'TilePreprocessor', 'TTPlanet_TileGF_Preprocessor', 'TTPlanet_TileSimple_Preprocessor', 'UniFormer-SemSegPreprocessor', 'SemSegPreprocessor', 'Unimatch_OptFlowPreprocessor', 'MaskOptFlow', 'Zoe-DepthMapPreprocessor')


def parameters(input_types, image, resolution):
    input_types = {**input_types['required'], **(input_types['optional'] if 'optional' in input_types else {})}
    params = {}
    for name, input_type in input_types.items():
        if name == 'image':
            params[name] = image
            continue
        if name == 'resolution':
            params[name] = resolution
            continue
        if len(input_type) == 2 and 'default' in input_type[1]:
            params[name] = input_type[1]['default']
            continue
        default_values = {'INT': 0, 'FLOAT': 0.0}
        if type(input_type[0]) is list:
            for input_type_value in input_type[0]:
                if input_type_value in default_values:
                    params[name] = default_values[input_type[0]]
        elif input_type[0] in default_values:
            params[name] = default_values[input_type[0]]
    return params
