import cv2
import numpy as np
import warnings
from PIL import Image
from ._image_math import HWC3, safer_memory, common_input_validate, resize_image_with_pad, get_upscale_method, make_noise_disk
from ._guided_filter import FastGuidedFilter

class CannyDetector:
    def __call__(self, input_image=None, low_threshold=100, high_threshold=200, detect_resolution=512, output_type=None, upscale_method="INTER_CUBIC", **kwargs):
        input_image, output_type = common_input_validate(input_image, output_type, **kwargs)
        detected_map, remove_pad = resize_image_with_pad(input_image, detect_resolution, upscale_method)
        detected_map = cv2.Canny(detected_map, low_threshold, high_threshold)
        detected_map = HWC3(remove_pad(detected_map))
        
        if output_type == "pil":
            detected_map = Image.fromarray(detected_map)
            
        return detected_map
class BinaryDetector:
    def __call__(self, input_image=None, bin_threshold=0, detect_resolution=512, output_type=None, upscale_method="INTER_CUBIC", **kwargs):
        if "img" in kwargs:
            warnings.warn("img is deprecated, please use `input_image=...` instead.", DeprecationWarning)
            input_image = kwargs.pop("img")
        
        if input_image is None:
            raise ValueError("input_image must be defined.")

        if not isinstance(input_image, np.ndarray):
            input_image = np.array(input_image, dtype=np.uint8)
            output_type = output_type or "pil"
        else:
            output_type = output_type or "np"
        
        detected_map, remove_pad = resize_image_with_pad(input_image, detect_resolution, upscale_method)

        img_gray = cv2.cvtColor(detected_map, cv2.COLOR_RGB2GRAY)
        if bin_threshold == 0 or bin_threshold == 255:
        # Otsu's threshold
            otsu_threshold, img_bin = cv2.threshold(img_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            print("Otsu threshold:", otsu_threshold)
        else:
            _, img_bin = cv2.threshold(img_gray, bin_threshold, 255, cv2.THRESH_BINARY_INV)
        
        detected_map = cv2.cvtColor(img_bin, cv2.COLOR_GRAY2RGB)
        detected_map = HWC3(remove_pad(255 - detected_map))
        
        if output_type == "pil":
            detected_map = Image.fromarray(detected_map)
            
        return detected_map
def cv2_resize_shortest_edge(image, size):
    h, w = image.shape[:2]
    if h < w:
        new_h = size
        new_w = int(round(w / h * size))
    else:
        new_w = size
        new_h = int(round(h / w * size))
    resized_image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return resized_image

def apply_color(img, res=512):
    img = cv2_resize_shortest_edge(img, res)
    h, w = img.shape[:2]

    input_img_color = cv2.resize(img, (w//64, h//64), interpolation=cv2.INTER_CUBIC)  
    input_img_color = cv2.resize(input_img_color, (w, h), interpolation=cv2.INTER_NEAREST)
    return input_img_color

class ColorDetector:
    def __call__(self, input_image=None, detect_resolution=512, output_type=None, **kwargs):
        input_image, output_type = common_input_validate(input_image, output_type, **kwargs)
        input_image = HWC3(input_image)
        detected_map = HWC3(apply_color(input_image, detect_resolution))
        
        if output_type == "pil":
            detected_map = Image.fromarray(detected_map)
            
        return detected_map
def recolor_luminance(img, thr_a=1.0):
    result = cv2.cvtColor(HWC3(img), cv2.COLOR_BGR2LAB)
    result = result[:, :, 0].astype(np.float32) / 255.0
    result = result ** thr_a
    result = (result * 255.0).clip(0, 255).astype(np.uint8)
    result = cv2.cvtColor(result, cv2.COLOR_GRAY2RGB)
    return result

def recolor_intensity(img, thr_a=1.0):
    result = cv2.cvtColor(HWC3(img), cv2.COLOR_BGR2HSV)
    result = result[:, :, 2].astype(np.float32) / 255.0
    result = result ** thr_a
    result = (result * 255.0).clip(0, 255).astype(np.uint8)
    result = cv2.cvtColor(result, cv2.COLOR_GRAY2RGB)
    return result

recolor_methods = {"luminance": recolor_luminance, "intensity": recolor_intensity}
class Recolorizer:
    def __call__(self, input_image=None, mode="luminance", gamma_correction=1.0, detect_resolution=512, output_type=None, upscale_method="INTER_CUBIC", **kwargs):
        input_image, output_type = common_input_validate(input_image, output_type, **kwargs)
        input_image, remove_pad = resize_image_with_pad(input_image, detect_resolution, upscale_method)
        assert mode in recolor_methods.keys()
        detected_map = recolor_methods[mode](input_image, gamma_correction)
        detected_map = HWC3(remove_pad(detected_map))
        if output_type == "pil":
            detected_map = Image.fromarray(detected_map)
        return detected_map
class LineartStandardDetector:
    def __call__(self, input_image=None, guassian_sigma=6.0, intensity_threshold=8, detect_resolution=512, output_type=None, upscale_method="INTER_CUBIC", **kwargs):
        input_image, output_type = common_input_validate(input_image, output_type, **kwargs)
        input_image, remove_pad = resize_image_with_pad(input_image, detect_resolution, upscale_method)
        
        x = input_image.astype(np.float32)
        g = cv2.GaussianBlur(x, (0, 0), guassian_sigma)
        intensity = np.min(g - x, axis=2).clip(0, 255)
        intensity /= max(16, np.median(intensity[intensity > intensity_threshold]))
        intensity *= 127
        detected_map = intensity.clip(0, 255).astype(np.uint8)
        
        detected_map = HWC3(remove_pad(detected_map))
        if output_type == "pil":
            detected_map = Image.fromarray(detected_map)
        return detected_map
class ScribbleDetector:
    def __call__(self, input_image=None, detect_resolution=512, output_type=None, upscale_method="INTER_AREA", **kwargs):
        input_image, output_type = common_input_validate(input_image, output_type, **kwargs)
        input_image, remove_pad = resize_image_with_pad(input_image, detect_resolution, upscale_method)

        detected_map = np.zeros_like(input_image, dtype=np.uint8)
        detected_map[np.min(input_image, axis=2) < 127] = 255
        detected_map = 255 - detected_map

        detected_map = remove_pad(detected_map)
        
        if output_type == "pil":
            detected_map = Image.fromarray(detected_map)
            
        return detected_map

class ScribbleXDog_Detector:
    def __call__(self, input_image=None, detect_resolution=512, thr_a=32, output_type=None, upscale_method="INTER_CUBIC", **kwargs):
        input_image, output_type = common_input_validate(input_image, output_type, **kwargs)
        input_image, remove_pad = resize_image_with_pad(input_image, detect_resolution, upscale_method)

        g1 = cv2.GaussianBlur(input_image.astype(np.float32), (0, 0), 0.5)
        g2 = cv2.GaussianBlur(input_image.astype(np.float32), (0, 0), 5.0)
        dog = (255 - np.min(g2 - g1, axis=2)).clip(0, 255).astype(np.uint8)
        result = np.zeros_like(input_image, dtype=np.uint8)
        result[2 * (255 - dog) > thr_a] = 255
        #result = 255 - result

        detected_map = HWC3(remove_pad(result))
        
        if output_type == "pil":
            detected_map = Image.fromarray(detected_map)
            
        return detected_map
def centered_canny(x: np.ndarray, canny_low_threshold, canny_high_threshold):
    assert isinstance(x, np.ndarray)
    assert x.ndim == 2 and x.dtype == np.uint8

    y = cv2.Canny(x, int(canny_low_threshold), int(canny_high_threshold))
    y = y.astype(np.float32) / 255.0
    return y

def centered_canny_color(x: np.ndarray, canny_low_threshold, canny_high_threshold):
    assert isinstance(x, np.ndarray)
    assert x.ndim == 3 and x.shape[2] == 3

    result = [centered_canny(x[..., i], canny_low_threshold, canny_high_threshold) for i in range(3)]
    result = np.stack(result, axis=2)
    return result

def pyramid_canny_color(x: np.ndarray, canny_low_threshold, canny_high_threshold):
    assert isinstance(x, np.ndarray)
    assert x.ndim == 3 and x.shape[2] == 3

    H, W, C = x.shape
    acc_edge = None

    for k in [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
        Hs, Ws = int(H * k), int(W * k)
        small = cv2.resize(x, (Ws, Hs), interpolation=cv2.INTER_AREA)
        edge = centered_canny_color(small, canny_low_threshold, canny_high_threshold)
        if acc_edge is None:
            acc_edge = edge
        else:
            acc_edge = cv2.resize(acc_edge, (edge.shape[1], edge.shape[0]), interpolation=cv2.INTER_LINEAR)
            acc_edge = acc_edge * 0.75 + edge * 0.25

    return acc_edge

def norm255(x, low=4, high=96):
    assert isinstance(x, np.ndarray)
    assert x.ndim == 2 and x.dtype == np.float32

    v_min = np.percentile(x, low)
    v_max = np.percentile(x, high)

    x -= v_min
    x /= v_max - v_min

    return x * 255.0

def canny_pyramid(x, canny_low_threshold, canny_high_threshold):
    # For some reasons, SAI's Control-lora Canny seems to be trained on canny maps with non-standard resolutions.
    # Then we use pyramid to use all resolutions to avoid missing any structure in specific resolutions.

    color_canny = pyramid_canny_color(x, canny_low_threshold, canny_high_threshold)
    result = np.sum(color_canny, axis=2)

    return norm255(result, low=1, high=99).clip(0, 255).astype(np.uint8)

class PyraCannyDetector:
    def __call__(self, input_image=None, low_threshold=100, high_threshold=200, detect_resolution=512, output_type=None, upscale_method="INTER_CUBIC", **kwargs):
        input_image, output_type = common_input_validate(input_image, output_type, **kwargs)
        detected_map, remove_pad = resize_image_with_pad(input_image, detect_resolution, upscale_method)
        detected_map = canny_pyramid(detected_map, low_threshold, high_threshold)
        detected_map = HWC3(remove_pad(detected_map))
        
        if output_type == "pil":
            detected_map = Image.fromarray(detected_map)
            
        return detected_map
class TileDetector:
    def __call__(self, input_image=None, pyrUp_iters=3, output_type=None, upscale_method="INTER_AREA", **kwargs):
        input_image, output_type = common_input_validate(input_image, output_type, **kwargs)
        H, W, _ = input_image.shape
        H = int(np.round(H / 64.0)) * 64
        W = int(np.round(W / 64.0)) * 64
        detected_map = cv2.resize(input_image, (W // (2 ** pyrUp_iters), H // (2 ** pyrUp_iters)),
                                  interpolation=get_upscale_method(upscale_method))
        detected_map = HWC3(detected_map)

        for _ in range(pyrUp_iters):
            detected_map = cv2.pyrUp(detected_map)

        if output_type == "pil":
            detected_map = Image.fromarray(detected_map)

        return detected_map

def apply_gaussian_blur(image_np, ksize=5, sigmaX=1.0):
    if ksize % 2 == 0:
        ksize += 1  # ksize must be odd
    blurred_image = cv2.GaussianBlur(image_np, (ksize, ksize), sigmaX=sigmaX)
    return blurred_image

def apply_guided_filter(image_np, radius, eps, scale):
    filter = FastGuidedFilter(image_np, radius, eps, scale)
    return filter.filter(image_np)

class TTPlanet_Tile_Detector_GF:
    def __call__(self, input_image, scale_factor, blur_strength, radius, eps, output_type=None, **kwargs):
        input_image, output_type = common_input_validate(input_image, output_type, **kwargs)
        img_np = input_image[:, :, ::-1] # RGB to BGR
        
        # Apply Gaussian blur
        img_np = apply_gaussian_blur(img_np, ksize=int(blur_strength), sigmaX=blur_strength / 2)            

        # Apply Guided Filter
        img_np = apply_guided_filter(img_np, radius, eps, scale_factor)

        # Resize image
        height, width = img_np.shape[:2]
        new_width = int(width / scale_factor)
        new_height = int(height / scale_factor)
        resized_down = cv2.resize(img_np, (new_width, new_height), interpolation=cv2.INTER_AREA)
        resized_img = cv2.resize(resized_down, (width, height), interpolation=cv2.INTER_CUBIC)
        detected_map = HWC3(resized_img[:, :, ::-1]) # BGR to RGB
        
        if output_type == "pil":
            detected_map = Image.fromarray(detected_map)
        
        return detected_map

class TTPLanet_Tile_Detector_Simple:
    def __call__(self, input_image, scale_factor, blur_strength, output_type=None, **kwargs):
        input_image, output_type = common_input_validate(input_image, output_type, **kwargs)
        img_np = input_image[:, :, ::-1] # RGB to BGR
        
        # Resize image first if you want blur to apply after resizing
        height, width = img_np.shape[:2]
        new_width = int(width / scale_factor)
        new_height = int(height / scale_factor)
        resized_down = cv2.resize(img_np, (new_width, new_height), interpolation=cv2.INTER_AREA)
        resized_img = cv2.resize(resized_down, (width, height), interpolation=cv2.INTER_LANCZOS4)
    
        # Apply Gaussian blur after resizing
        img_np = apply_gaussian_blur(resized_img, ksize=int(blur_strength), sigmaX=blur_strength / 2)
        detected_map = HWC3(img_np[:, :, ::-1]) # BGR to RGB
        
        if output_type == "pil":
            detected_map = Image.fromarray(detected_map)
        
        return detected_map
class ContentShuffleDetector:
    def __call__(self, input_image, h=None, w=None, f=None, detect_resolution=512, output_type="pil", upscale_method="INTER_CUBIC", seed=-1, **kwargs):
        input_image, output_type = common_input_validate(input_image, output_type, **kwargs)
        input_image, remove_pad = resize_image_with_pad(input_image, detect_resolution, upscale_method)

        H, W, C = input_image.shape
        if h is None:
            h = H
        if w is None:
            w = W
        if f is None:
            f = 256
        rng = np.random.default_rng(seed) if seed else None
        x = make_noise_disk(h, w, 1, f, rng=rng) * float(W - 1)
        y = make_noise_disk(h, w, 1, f, rng=rng) * float(H - 1)
        flow = np.concatenate([x, y], axis=2).astype(np.float32)
        detected_map = cv2.remap(input_image, flow, None, cv2.INTER_LINEAR)
        detected_map = remove_pad(detected_map)

        if output_type == "pil":
            detected_map = Image.fromarray(detected_map)

        return detected_map
