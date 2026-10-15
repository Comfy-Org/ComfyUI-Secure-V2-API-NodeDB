import logging
from pathlib import Path
import numpy as np
import torch
import cv2
from ._image_math import ResizeMode, safe_numpy, get_unique_axis0
from .lvminthin import nake_nms, lvmin_thin
log = logging.getLogger(__name__)
MAX_IMAGEGEN_RESOLUTION = 8192
RESIZE_MODES = [x.value for x in ResizeMode]
here = Path(__file__).parent

class PixelPerfectResolution:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "original_image": ("IMAGE", ),
                "image_gen_width": ("INT", {"default": 512, "min": 64, "max": MAX_IMAGEGEN_RESOLUTION, "step": 8}),
                "image_gen_height": ("INT", {"default": 512, "min": 64, "max": MAX_IMAGEGEN_RESOLUTION, "step": 8}),
                #https://github.com/comfyanonymous/ComfyUI/blob/c910b4a01ca58b04e5d4ab4c747680b996ada02b/nodes.py#L854
                "resize_mode": (RESIZE_MODES, {"default": ResizeMode.RESIZE.value})
            }
        }
    
    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("RESOLUTION (INT)", )
    FUNCTION = "execute"

    CATEGORY = "ControlNet Preprocessors"

    def execute(self, original_image, image_gen_width, image_gen_height, resize_mode):
        _, raw_H, raw_W, _ = original_image.shape

        k0 = float(image_gen_height) / float(raw_H)
        k1 = float(image_gen_width) / float(raw_W)

        if resize_mode == ResizeMode.OUTER_FIT.value:
            estimation = min(k0, k1) * float(min(raw_H, raw_W))
        else:
            estimation = max(k0, k1) * float(min(raw_H, raw_W))

        log.debug(f"Pixel Perfect Computation:")
        log.debug(f"resize_mode = {resize_mode}")
        log.debug(f"raw_H = {raw_H}")
        log.debug(f"raw_W = {raw_W}")
        log.debug(f"target_H = {image_gen_height}")
        log.debug(f"target_W = {image_gen_width}")
        log.debug(f"estimation = {estimation}")

        return (int(np.round(estimation)), )

class HintImageEnchance:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "hint_image": ("IMAGE", ),
                "image_gen_width": ("INT", {"default": 512, "min": 64, "max": MAX_IMAGEGEN_RESOLUTION, "step": 8}),
                "image_gen_height": ("INT", {"default": 512, "min": 64, "max": MAX_IMAGEGEN_RESOLUTION, "step": 8}),
                #https://github.com/comfyanonymous/ComfyUI/blob/c910b4a01ca58b04e5d4ab4c747680b996ada02b/nodes.py#L854
                "resize_mode": (RESIZE_MODES, {"default": ResizeMode.RESIZE.value})
            }
        }
    
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "execute"

    CATEGORY = "ControlNet Preprocessors"
    def execute(self, hint_image, image_gen_width, image_gen_height, resize_mode):
        outs = []
        for single_hint_image in hint_image:
            np_hint_image = np.asarray(single_hint_image * 255., dtype=np.uint8)

            if resize_mode == ResizeMode.RESIZE.value:
                np_hint_image = self.execute_resize(np_hint_image, image_gen_width, image_gen_height)
            elif resize_mode == ResizeMode.OUTER_FIT.value:
                np_hint_image = self.execute_outer_fit(np_hint_image, image_gen_width, image_gen_height)
            else:
                np_hint_image = self.execute_inner_fit(np_hint_image, image_gen_width, image_gen_height)
            
            outs.append(torch.from_numpy(np_hint_image.astype(np.float32) / 255.0))
        
        return (torch.stack(outs, dim=0),)
    
    def execute_resize(self, detected_map, w, h):
        detected_map = self.high_quality_resize(detected_map, (w, h))
        detected_map = safe_numpy(detected_map)
        return detected_map
    
    def execute_outer_fit(self, detected_map, w, h):
        old_h, old_w, _ = detected_map.shape
        old_w = float(old_w)
        old_h = float(old_h)
        k0 = float(h) / old_h
        k1 = float(w) / old_w
        safeint = lambda x: int(np.round(x))
        k = min(k0, k1)
        
        borders = np.concatenate([detected_map[0, :, :], detected_map[-1, :, :], detected_map[:, 0, :], detected_map[:, -1, :]], axis=0)
        high_quality_border_color = np.median(borders, axis=0).astype(detected_map.dtype)
        if len(high_quality_border_color) == 4:
            # Inpaint hijack
            high_quality_border_color[3] = 255
        high_quality_background = np.tile(high_quality_border_color[None, None], [h, w, 1])
        detected_map = self.high_quality_resize(detected_map, (safeint(old_w * k), safeint(old_h * k)))
        new_h, new_w, _ = detected_map.shape
        pad_h = max(0, (h - new_h) // 2)
        pad_w = max(0, (w - new_w) // 2)
        high_quality_background[pad_h:pad_h + new_h, pad_w:pad_w + new_w] = detected_map
        detected_map = high_quality_background
        detected_map = safe_numpy(detected_map)
        return detected_map
    
    def execute_inner_fit(self, detected_map, w, h):
        old_h, old_w, _ = detected_map.shape
        old_w = float(old_w)
        old_h = float(old_h)
        k0 = float(h) / old_h
        k1 = float(w) / old_w
        safeint = lambda x: int(np.round(x))
        k = max(k0, k1)

        detected_map = self.high_quality_resize(detected_map, (safeint(old_w * k), safeint(old_h * k)))
        new_h, new_w, _ = detected_map.shape
        pad_h = max(0, (new_h - h) // 2)
        pad_w = max(0, (new_w - w) // 2)
        detected_map = detected_map[pad_h:pad_h+h, pad_w:pad_w+w]
        detected_map = safe_numpy(detected_map)
        return detected_map

    def high_quality_resize(self, x, size):
        # Written by lvmin
        # Super high-quality control map up-scaling, considering binary, seg, and one-pixel edges

        inpaint_mask = None
        if x.ndim == 3 and x.shape[2] == 4:
            inpaint_mask = x[:, :, 3]
            x = x[:, :, 0:3]

        if x.shape[0] != size[1] or x.shape[1] != size[0]:
            new_size_is_smaller = (size[0] * size[1]) < (x.shape[0] * x.shape[1])
            new_size_is_bigger = (size[0] * size[1]) > (x.shape[0] * x.shape[1])
            unique_color_count = len(get_unique_axis0(x.reshape(-1, x.shape[2])))
            is_one_pixel_edge = False
            is_binary = False
            if unique_color_count == 2:
                is_binary = np.min(x) < 16 and np.max(x) > 240
                if is_binary:
                    xc = x
                    xc = cv2.erode(xc, np.ones(shape=(3, 3), dtype=np.uint8), iterations=1)
                    xc = cv2.dilate(xc, np.ones(shape=(3, 3), dtype=np.uint8), iterations=1)
                    one_pixel_edge_count = np.where(xc < x)[0].shape[0]
                    all_edge_count = np.where(x > 127)[0].shape[0]
                    is_one_pixel_edge = one_pixel_edge_count * 2 > all_edge_count

            if 2 < unique_color_count < 200:
                interpolation = cv2.INTER_NEAREST
            elif new_size_is_smaller:
                interpolation = cv2.INTER_AREA
            else:
                interpolation = cv2.INTER_CUBIC  # Must be CUBIC because we now use nms. NEVER CHANGE THIS

            y = cv2.resize(x, size, interpolation=interpolation)
            if inpaint_mask is not None:
                inpaint_mask = cv2.resize(inpaint_mask, size, interpolation=interpolation)

            if is_binary:
                y = np.mean(y.astype(np.float32), axis=2).clip(0, 255).astype(np.uint8)
                if is_one_pixel_edge:
                    y = nake_nms(y)
                    _, y = cv2.threshold(y, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                    y = lvmin_thin(y, prunings=new_size_is_bigger)
                else:
                    _, y = cv2.threshold(y, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                y = np.stack([y] * 3, axis=2)
        else:
            y = x

        if inpaint_mask is not None:
            inpaint_mask = (inpaint_mask > 127).astype(np.float32) * 255.0
            inpaint_mask = inpaint_mask[:, :, None].clip(0, 255).astype(np.uint8)
            y = np.concatenate([y, inpaint_mask], axis=2)

        return y

class ImageGenResolutionFromImage:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": { "image": ("IMAGE", ) }
        }
    
    RETURN_TYPES = ("INT", "INT")
    RETURN_NAMES = ("IMAGE_GEN_WIDTH (INT)", "IMAGE_GEN_HEIGHT (INT)")
    FUNCTION = "execute"

    CATEGORY = "ControlNet Preprocessors"

    def execute(self, image):
        _, H, W, _ = image.shape
        return (W, H)

class ImageGenResolutionFromLatent:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": { "latent": ("LATENT", ) }
        }
    
    RETURN_TYPES = ("INT", "INT")
    RETURN_NAMES = ("IMAGE_GEN_WIDTH (INT)", "IMAGE_GEN_HEIGHT (INT)")
    FUNCTION = "execute"

    CATEGORY = "ControlNet Preprocessors"

    def execute(self, latent):
        _, _, H, W = latent["samples"].shape
        return (W * 8, H * 8)
class Canny_Edge_Preprocessor:
    @classmethod
    def INPUT_TYPES(s):
        return define_preprocessor_inputs(
            low_threshold=INPUT.INT(default=100, max=255),
            high_threshold=INPUT.INT(default=200, max=255),
            resolution=INPUT.RESOLUTION()
        )

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "execute"

    CATEGORY = "ControlNet Preprocessors/Line Extractors"

    def execute(self, image, low_threshold=100, high_threshold=200, resolution=512, **kwargs):
        from ._detectors import CannyDetector

        return (common_annotator_call(CannyDetector(), image, low_threshold=low_threshold, high_threshold=high_threshold, resolution=resolution), )
class Binary_Preprocessor:
    @classmethod
    def INPUT_TYPES(s):
        return define_preprocessor_inputs(
            bin_threshold=INPUT.INT(default=100, max=255),
            resolution=INPUT.RESOLUTION()
        )

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "execute"

    CATEGORY = "ControlNet Preprocessors/Line Extractors"

    def execute(self, image, bin_threshold=100, resolution=512, **kwargs):
        from ._detectors import BinaryDetector

        return (common_annotator_call(BinaryDetector(), image, bin_threshold=bin_threshold, resolution=resolution), )
class Color_Preprocessor:
    @classmethod
    def INPUT_TYPES(s):
        return define_preprocessor_inputs(resolution=INPUT.RESOLUTION())

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "execute"

    CATEGORY = "ControlNet Preprocessors/T2IAdapter-only"

    def execute(self, image, resolution=512, **kwargs):
        from ._detectors import ColorDetector

        return (common_annotator_call(ColorDetector(), image, resolution=resolution), )
class ImageLuminanceDetector:
    @classmethod
    def INPUT_TYPES(s):
        #https://github.com/Mikubill/sd-webui-controlnet/blob/416c345072c9c2066101e225964e3986abe6945e/scripts/processor.py#L1229
        return define_preprocessor_inputs(
            gamma_correction=INPUT.FLOAT(default=1.0, min=0.1, max=2.0),
            resolution=INPUT.RESOLUTION()
        )

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "execute"

    CATEGORY = "ControlNet Preprocessors/Recolor"

    def execute(self, image, gamma_correction=1.0, resolution=512, **kwargs):
        from ._detectors import Recolorizer
        return (common_annotator_call(Recolorizer(), image, mode="luminance", gamma_correction=gamma_correction , resolution=resolution), )

class ImageIntensityDetector:
    @classmethod
    def INPUT_TYPES(s):
        #https://github.com/Mikubill/sd-webui-controlnet/blob/416c345072c9c2066101e225964e3986abe6945e/scripts/processor.py#L1229
        return define_preprocessor_inputs(
            gamma_correction=INPUT.FLOAT(default=1.0, min=0.1, max=2.0),
            resolution=INPUT.RESOLUTION()
        )

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "execute"

    CATEGORY = "ControlNet Preprocessors/Recolor"

    def execute(self, image, gamma_correction=1.0, resolution=512, **kwargs):
        from ._detectors import Recolorizer
        return (common_annotator_call(Recolorizer(), image, mode="intensity", gamma_correction=gamma_correction , resolution=resolution), )
class InpaintPreprocessor:
    @classmethod
    def INPUT_TYPES(s):
        return dict(
            required=dict(image=INPUT.IMAGE(), mask=INPUT.MASK()),
            optional=dict(black_pixel_for_xinsir_cn=INPUT.BOOLEAN(False))
        )
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "preprocess"

    CATEGORY = "ControlNet Preprocessors/others"

    def preprocess(self, image, mask, black_pixel_for_xinsir_cn=False):
        mask = torch.nn.functional.interpolate(mask.reshape((-1, 1, mask.shape[-2], mask.shape[-1])), size=(image.shape[1], image.shape[2]), mode="bilinear")
        mask = mask.movedim(1,-1).expand((-1,-1,-1,3))
        image = image.clone()
        if black_pixel_for_xinsir_cn:
            masked_pixel = 0.0
        else:
            masked_pixel = -1.0
        image[mask > 0.5] = masked_pixel
        return (image,)
class Lineart_Standard_Preprocessor:
    @classmethod
    def INPUT_TYPES(s):
        return define_preprocessor_inputs(
            guassian_sigma=INPUT.FLOAT(default=6.0, max=100.0),
            intensity_threshold=INPUT.INT(default=8, max=16),
            resolution=INPUT.RESOLUTION()
        )

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "execute"

    CATEGORY = "ControlNet Preprocessors/Line Extractors"

    def execute(self, image, guassian_sigma=6, intensity_threshold=8, resolution=512, **kwargs):
        from ._detectors import LineartStandardDetector
        return (common_annotator_call(LineartStandardDetector(), image, guassian_sigma=guassian_sigma, intensity_threshold=intensity_threshold, resolution=resolution), )
class Scribble_Preprocessor:
    @classmethod
    def INPUT_TYPES(s):
        return define_preprocessor_inputs(resolution=INPUT.RESOLUTION())

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "execute"

    CATEGORY = "ControlNet Preprocessors/Line Extractors"

    def execute(self, image, resolution=512, **kwargs):
        from ._detectors import ScribbleDetector

        model = ScribbleDetector()
        return (common_annotator_call(model, image, resolution=resolution), )

class Scribble_XDoG_Preprocessor:
    @classmethod
    def INPUT_TYPES(s):
        return define_preprocessor_inputs(
            threshold=INPUT.INT(default=32, min=1, max=64),
            resolution=INPUT.RESOLUTION()
        )

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "execute"

    CATEGORY = "ControlNet Preprocessors/Line Extractors"

    def execute(self, image, threshold=32, resolution=512, **kwargs):
        from ._detectors import ScribbleXDog_Detector

        model = ScribbleXDog_Detector()
        return (common_annotator_call(model, image, resolution=resolution, thr_a=threshold), )
class PyraCanny_Preprocessor:
    @classmethod
    def INPUT_TYPES(s):
        return define_preprocessor_inputs(
            low_threshold=INPUT.INT(default=64, max=255),
            high_threshold=INPUT.INT(default=128, max=255),
            resolution=INPUT.RESOLUTION()
        )

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "execute"

    CATEGORY = "ControlNet Preprocessors/Line Extractors"

    def execute(self, image, low_threshold=64, high_threshold=128, resolution=512, **kwargs):
        from ._detectors import PyraCannyDetector

        return (common_annotator_call(PyraCannyDetector(), image, low_threshold=low_threshold, high_threshold=high_threshold, resolution=resolution), )

from enum import Enum
MAX_RESOLUTION = 16384
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

from ._annotator import common_annotator_call
class Tile_Preprocessor:
    @classmethod
    def INPUT_TYPES(s):
        return define_preprocessor_inputs(
            pyrUp_iters=INPUT.INT(default=3, min=1, max=10),
            resolution=INPUT.RESOLUTION()
        )
        

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "execute"

    CATEGORY = "ControlNet Preprocessors/tile"

    def execute(self, image, pyrUp_iters, resolution=512, **kwargs):
        from ._detectors import TileDetector

        return (common_annotator_call(TileDetector(), image, pyrUp_iters=pyrUp_iters, resolution=resolution),)

class TTPlanet_TileGF_Preprocessor:
    @classmethod
    def INPUT_TYPES(s):
        return define_preprocessor_inputs(
            scale_factor=INPUT.FLOAT(default=1.00, min=1.000, max=8.00),
            blur_strength=INPUT.FLOAT(default=2.0, min=1.0, max=10.0),
            radius=INPUT.INT(default=7, min=1, max=20),
            eps=INPUT.FLOAT(default=0.01, min=0.001, max=0.1, step=0.001),
            resolution=INPUT.RESOLUTION()
        )
    
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "execute"

    CATEGORY = "ControlNet Preprocessors/tile"

    def execute(self, image, scale_factor, blur_strength, radius, eps, **kwargs):
        from ._detectors import TTPlanet_Tile_Detector_GF

        return (common_annotator_call(TTPlanet_Tile_Detector_GF(), image, scale_factor=scale_factor, blur_strength=blur_strength, radius=radius, eps=eps),)

class TTPlanet_TileSimple_Preprocessor:
    @classmethod
    def INPUT_TYPES(s):
        return define_preprocessor_inputs(
            scale_factor=INPUT.FLOAT(default=1.00, min=1.000, max=8.00),
            blur_strength=INPUT.FLOAT(default=2.0, min=1.0, max=10.0),
        )
    
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "execute"

    CATEGORY = "ControlNet Preprocessors/tile"

    def execute(self, image, scale_factor, blur_strength):
        from ._detectors import TTPLanet_Tile_Detector_Simple

        return (common_annotator_call(TTPLanet_Tile_Detector_Simple(), image, scale_factor=scale_factor, blur_strength=blur_strength),)
class Shuffle_Preprocessor:
    @classmethod
    def INPUT_TYPES(s):
        return define_preprocessor_inputs(
            resolution=INPUT.RESOLUTION(),
            seed=INPUT.SEED()
        )
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "preprocess"

    CATEGORY = "ControlNet Preprocessors/T2IAdapter-only"

    def preprocess(self, image, resolution=512, seed=0):
        from ._detectors import ContentShuffleDetector

        return (common_annotator_call(ContentShuffleDetector(), image, resolution=resolution, seed=seed), )

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

class ControlNetAuxSimpleAddText:
    @classmethod
    def INPUT_TYPES(s):
        return dict(
            required=dict(image=INPUT.IMAGE(), text=INPUT.STRING())
        )
    
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "execute"
    CATEGORY = "ControlNet Preprocessors"
    def execute(self, image, text):
        from PIL import Image, ImageDraw, ImageFont
        import numpy as np
        import torch

        from ._font_resource import font_source
        font = ImageFont.truetype(font_source(here / "NotoSans-Regular.ttf"), 40)
        img = Image.fromarray(image[0].cpu().numpy().__mul__(255.).astype(np.uint8))
        ImageDraw.Draw(img).text((0,0), text, fill=(0,255,0), font=font)
        return (torch.from_numpy(np.array(img)).unsqueeze(0) / 255.,)

IMPLEMENTED = {
    'PixelPerfectResolution': PixelPerfectResolution,
    'ImageGenResolutionFromImage': ImageGenResolutionFromImage,
    'ImageGenResolutionFromLatent': ImageGenResolutionFromLatent,
    'HintImageEnchance': HintImageEnchance,
    'CannyEdgePreprocessor': Canny_Edge_Preprocessor,
    'BinaryPreprocessor': Binary_Preprocessor,
    'ColorPreprocessor': Color_Preprocessor,
    'ImageLuminanceDetector': ImageLuminanceDetector,
    'ImageIntensityDetector': ImageIntensityDetector,
    'InpaintPreprocessor': InpaintPreprocessor,
    'LineartStandardPreprocessor': Lineart_Standard_Preprocessor,
    'ScribblePreprocessor': Scribble_Preprocessor,
    'Scribble_XDoG_Preprocessor': Scribble_XDoG_Preprocessor,
    'PyraCannyPreprocessor': PyraCanny_Preprocessor,
    'TilePreprocessor': Tile_Preprocessor,
    'TTPlanet_TileGF_Preprocessor': TTPlanet_TileGF_Preprocessor,
    'TTPlanet_TileSimple_Preprocessor': TTPlanet_TileSimple_Preprocessor,
}
IMPLEMENTED.update(ControlNetPreprocessorSelector=ControlNetPreprocessorSelector, ControlNetAuxSimpleAddText=ControlNetAuxSimpleAddText)
IMPLEMENTED.update(ShufflePreprocessor=Shuffle_Preprocessor)
