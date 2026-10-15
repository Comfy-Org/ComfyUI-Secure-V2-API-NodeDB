"""Source-faithful AnyLine composition, using managed pack-owned detectors.

Morphology operates on HWC masks, including connectivity across channels,
exactly as the original wrapper. No host model loader or runtime installer.
"""
import numpy as np
import torch
from skimage import morphology
from comfy_api.latest import sdk
from . import _teed, _lineart, _manga
from ._annotator import common_annotator_call
from ._detectors import LineartStandardDetector

MTEED = sdk.HuggingFaceWeight(
    repo_id='TheMistoAI/MistoLine', filename='Anyline/MTEED.pth',
    revision='1d9d0b3d48b295cf70d80a0f839a3055672f8393',
    sha256='a3c2d8a8ce9422555c787160bd46362d761325a565333c0e3f6a53e0bae2abdb',
    folder='controlnet')
REQUIRED_WEIGHTS = (MTEED, _lineart.FINE, _lineart.COARSE, _lineart.ANIME, _manga.WEIGHT)

def get_intensity_mask(image_array, lower_bound, upper_bound):
    mask = image_array[:, :, 0]
    mask = np.where((mask >= lower_bound) & (mask <= upper_bound), mask, 0)
    mask = np.expand_dims(mask, 2).repeat(3, axis=2)
    return mask

def combine_layers(base_layer, top_layer):
    mask = top_layer.astype(bool)
    temp = 1 - (1 - top_layer) * (1 - base_layer)
    result = base_layer * (~mask) + temp * mask
    return result


async def execute(image, merge_with_lineart='lineart_standard', resolution=512,
                  lineart_lower_bound=0, lineart_upper_bound=1,
                  object_min_size=36, object_connectivity=1):
    # Keep the original two-detector ordering and each detector's native
    # quantization/resizing, including manga's rounding to multiples of 256.
    mteed_result = (await _teed.execute(image, resolution=resolution,
                                      declaration=MTEED)).numpy()
    if merge_with_lineart == 'lineart_standard':
        lineart_result = common_annotator_call(
            LineartStandardDetector(), image, guassian_sigma=2,
            intensity_threshold=3, resolution=resolution, show_pbar=False).numpy()
    else:
        mode = dict(lineart_realisitic='LineArtPreprocessor',
                    lineart_anime='AnimeLineArtPreprocessor',
                    manga_line='Manga2Anime_LineArt_Preprocessor')[merge_with_lineart]
        if mode == 'Manga2Anime_LineArt_Preprocessor':
            lineart_result = (await _manga.execute(image, resolution=resolution)).numpy()
        else:
            lineart_result = (await _lineart.execute(mode, image,
                                                   resolution=resolution)).numpy()
    return _combine_results(image,mteed_result,lineart_result,lineart_lower_bound,lineart_upper_bound,object_min_size,object_connectivity)

def _combine_results(image,mteed_result,lineart_result,lineart_lower_bound=0,lineart_upper_bound=1,object_min_size=36,object_connectivity=1):
    final_result = []
    for i in range(len(image)):
        _lineart_result = get_intensity_mask(lineart_result[i], lower_bound=lineart_lower_bound, upper_bound=lineart_upper_bound)
        _cleaned = morphology.remove_small_objects(_lineart_result.astype(bool), min_size=object_min_size, connectivity=object_connectivity)
        _lineart_result = _lineart_result * _cleaned
        _mteed_result = mteed_result[i]
        final_result.append(torch.from_numpy(combine_layers(_mteed_result, _lineart_result)))
    return torch.stack(final_result)

def _render_loaded(states,image,merge_with_lineart='lineart_standard',resolution=512,lineart_lower_bound=0,lineart_upper_bound=1,object_min_size=36,object_connectivity=1):
    mteed_result=_teed._render_loaded(states[MTEED.filename],image,resolution=resolution).numpy()
    if merge_with_lineart=='lineart_standard':
        lineart_result=common_annotator_call(LineartStandardDetector(),image,guassian_sigma=2,intensity_threshold=3,resolution=resolution,show_pbar=False).numpy()
    elif merge_with_lineart=='manga_line':
        lineart_result=_manga._render_loaded(states[_manga.WEIGHT.filename],image,resolution=resolution).numpy()
    else:
        mode=dict(lineart_realisitic='LineArtPreprocessor',lineart_anime='AnimeLineArtPreprocessor')[merge_with_lineart]
        lineart_result=_lineart._render_loaded(mode,states,image,resolution=resolution).numpy()
    return _combine_results(image,mteed_result,lineart_result,lineart_lower_bound,lineart_upper_bound,object_min_size,object_connectivity)
