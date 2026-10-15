import cv2,numpy as np,torch,functools
import torch.nn as nn
from einops import rearrange
from PIL import Image
from ._native_batch_reference import HWC3,resize_image_with_pad,common_input_validate,common_annotator_call
HF_MODEL_NAME='lllyasviel/Annotators'
BDS_MODEL_NAME='bdsqlsz/qinglong_controlnet-lllite'
STATES={}
from ._native_progress_reference import ProgressBar as _reference_progress_bar
from ._native_mteed_reference import TEDDetector
from ._native_lineart_reference import LineartDetector
from ._native_anime_reference import LineartAnimeDetector
from ._native_manga_reference import LineartMangaDetector
from ._native_standard_reference import LineartStandardDetector
def get_intensity_mask(image_array, lower_bound, upper_bound):
    mask = image_array[:, :, 0]
    mask = np.where((mask >= lower_bound) & (mask <= upper_bound), mask, 0)
    mask = np.expand_dims(mask, 2).repeat(3, axis=2)
    return mask
def combine_layers(base_layer, top_layer):
    mask = top_layer.astype(bool)
    temp = 1 - (1 - top_layer) * (1 - base_layer)
    result = base_layer * ~mask + temp * mask
    return result
def native_anyline(self, image, merge_with_lineart='lineart_standard', resolution=512, lineart_lower_bound=0, lineart_upper_bound=1, object_min_size=36, object_connectivity=1):
    from skimage import morphology
    pbar = _reference_progress_bar(3)
    mteed_model = TEDDetector.from_pretrained('TheMistoAI/MistoLine', 'MTEED.pth', subfolder='Anyline').to(self.device)
    mteed_result = common_annotator_call(mteed_model, image, resolution=resolution, show_pbar=False)
    mteed_result = mteed_result.numpy()
    del mteed_model
    pbar.update(1)
    if merge_with_lineart == 'lineart_standard':
        lineart_standard_detector = LineartStandardDetector()
        lineart_result = common_annotator_call(lineart_standard_detector, image, guassian_sigma=2, intensity_threshold=3, resolution=resolution, show_pbar=False).numpy()
        del lineart_standard_detector
    else:
        lineart_detector = dict(lineart_realisitic=LineartDetector, lineart_anime=LineartAnimeDetector, manga_line=LineartMangaDetector)[merge_with_lineart]
        lineart_detector = lineart_detector.from_pretrained().to(self.device)
        lineart_result = common_annotator_call(lineart_detector, image, resolution=resolution, show_pbar=False).numpy()
        del lineart_detector
    pbar.update(1)
    final_result = []
    for i in range(len(image)):
        _lineart_result = get_intensity_mask(lineart_result[i], lower_bound=lineart_lower_bound, upper_bound=lineart_upper_bound)
        _cleaned = morphology.remove_small_objects(_lineart_result.astype(bool), min_size=object_min_size, connectivity=object_connectivity)
        _lineart_result = _lineart_result * _cleaned
        _mteed_result = mteed_result[i]
        final_result.append(torch.from_numpy(combine_layers(_mteed_result, _lineart_result)))
    pbar.update(1)
    return (torch.stack(final_result),)
