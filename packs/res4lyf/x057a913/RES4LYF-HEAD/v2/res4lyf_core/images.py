"""V2 subset of upstream images.py (057a913e). The definitions below are copied verbatim, in upstream
order; VENDOR.json records each one's source lines and sha256. Upstream also imports math, torchvision,
kornia and cv2, which these definitions never use, so only their own imports are kept (vendor_res4lyf.py
proves that every global name resolves as upstream). MAX_RESOLUTION is not defined upstream either
(images.py never imports it): image_resize's keep-proportion and pad branches with a zero size raise
NameError here exactly as they do there."""
import torch
import torch.nn.functional as F

import numpy as np

from PIL import Image, ImageFilter, ImageEnhance

from . import _comfy as comfy  # V2: guest-side stand-in (res4lyf_core/_comfy; lanczos is Core's, verbatim)


def tensor2pil(image):
    return Image.fromarray(np.clip(255. * image.cpu().numpy().squeeze(), 0, 255).astype(np.uint8))


def pil2tensor(image):
    return torch.from_numpy(np.array(image).astype(np.float32) / 255.0).unsqueeze(0)


def hard_light_blend(base, blend):
    return torch.where(blend <= 0.5, 
                       2 * base * blend, 
                       1 - 2 * (1 - base) * (1 - blend))


def image_resize(image,
                width,
                height,
                method          = "stretch",
                interpolation   = "nearest",
                condition       = "always",
                multiple_of     = 0,
                keep_proportion = False):
    
    _, oh, ow, _ = image.shape
    x = y = x2 = y2 = 0
    pad_left = pad_right = pad_top = pad_bottom = 0

    if keep_proportion:
        method = "keep proportion"

    if multiple_of > 1:
        width = width - (width % multiple_of)
        height = height - (height % multiple_of)

    if method == 'keep proportion' or method == 'pad':
        if width == 0 and oh < height:
            width = MAX_RESOLUTION
        elif width == 0 and oh >= height:
            width = ow

        if height == 0 and ow < width:
            height = MAX_RESOLUTION
        elif height == 0 and ow >= width:
            height = oh

        ratio = min(width / ow, height / oh)
        new_width = round(ow*ratio)
        new_height = round(oh*ratio)

        if method == 'pad':
            pad_left = (width - new_width) // 2
            pad_right = width - new_width - pad_left
            pad_top = (height - new_height) // 2
            pad_bottom = height - new_height - pad_top

        width = new_width
        height = new_height
    elif method.startswith('fill'):
        width = width if width > 0 else ow
        height = height if height > 0 else oh

        ratio = max(width / ow, height / oh)
        new_width = round(ow*ratio)
        new_height = round(oh*ratio)
        x = (new_width - width) // 2
        y = (new_height - height) // 2
        x2 = x + width
        y2 = y + height
        if x2 > new_width:
            x -= (x2 - new_width)
        if x < 0:
            x = 0
        if y2 > new_height:
            y -= (y2 - new_height)
        if y < 0:
            y = 0
        width = new_width
        height = new_height
    else:
        width = width if width > 0 else ow
        height = height if height > 0 else oh

    if "always" in condition \
        or ("downscale if bigger" == condition and (oh > height or ow > width)) or ("upscale if smaller" == condition and (oh < height or ow < width)) \
        or ("bigger area" in condition and (oh * ow > height * width)) or ("smaller area" in condition and (oh * ow < height * width)):

        outputs = image.permute(0,3,1,2)

        if interpolation == "lanczos":
            outputs = comfy.utils.lanczos(outputs, width, height)
        else:
            outputs = F.interpolate(outputs, size=(height, width), mode=interpolation)

        if method == 'pad':
            if pad_left > 0 or pad_right > 0 or pad_top > 0 or pad_bottom > 0:
                outputs = F.pad(outputs, (pad_left, pad_right, pad_top, pad_bottom), value=0)

        outputs = outputs.permute(0,2,3,1)

        if method.startswith('fill'):
            if x > 0 or y > 0 or x2 > 0 or y2 > 0:
                outputs = outputs[:, y:y2, x:x2, :]
    else:
        outputs = image

    if multiple_of > 1 and (outputs.shape[2] % multiple_of != 0 or outputs.shape[1] % multiple_of != 0):
        width = outputs.shape[2]
        height = outputs.shape[1]
        x = (width % multiple_of) // 2
        y = (height % multiple_of) // 2
        x2 = width - ((width % multiple_of) - x)
        y2 = height - ((height % multiple_of) - y)
        outputs = outputs[:, y:y2, x:x2, :]
    
    outputs = torch.clamp(outputs, 0, 1)

    return outputs


class Film_Grain: 
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image":              ("IMAGE",),
                "density":            ("FLOAT", {"default": 1.0, "min": 0.01, "max": 1.0, "step": 0.01}),
                "intensity":          ("FLOAT", {"default": 1.0, "min": 0.01, "max": 1.0, "step": 0.01}),
                "highlights":         ("FLOAT", {"default": 1.0, "min": 0.01, "max": 255.0, "step": 0.01}),
                "supersample_factor": ("INT",   {"default": 4, "min": 1, "max": 8, "step": 1}),
                "repeats":            ("INT",   {"default": 1, "min": 1, "max": 1000, "step": 1})
            }
        }
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "main"

    CATEGORY = "RES4LYF/images"

    def main(self, image, density, intensity, highlights, supersample_factor, repeats=1):
        image = image.repeat(repeats, 1, 1, 1)
        return (self.apply_film_grain(image, density, intensity, highlights, supersample_factor), )

    def apply_film_grain(self, img, density=0.1, intensity=1.0, highlights=1.0, supersample_factor=4):

        img_batch = img.clone()
        img_list = []
        for i in range(img_batch.shape[0]):
            img = img_batch[i].unsqueeze(0)
            img = tensor2pil(img)
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
            # apply grayscale noise with specified density/intensity/highlights to PIL image
            img_gray = img.convert('L')
            original_size = img.size
            img_gray = img_gray.resize(
                ((img.size[0] * supersample_factor), (img.size[1] * supersample_factor)), Image.Resampling(2))
            num_pixels = int(density * img_gray.size[0] * img_gray.size[1])

            img_gray_tensor = torch.from_numpy(np.array(img_gray).astype(np.float32) / 255.0).to(device)
            img_gray_flat = img_gray_tensor.view(-1)
            num_pixels = int(density * img_gray_flat.numel())
            indices = torch.randint(0, img_gray_flat.numel(), (num_pixels,), device=img_gray_flat.device)
            values = torch.randint(0, 256, (num_pixels,), device=img_gray_flat.device, dtype=torch.float32) / 255.0
            
            img_gray_flat[indices] = values
            img_gray = img_gray_flat.view(img_gray_tensor.shape)
            
            img_gray_np = (img_gray.cpu().numpy() * 255).astype(np.uint8)
            img_gray = Image.fromarray(img_gray_np)

            img_noise = img_gray.convert('RGB')
            img_noise = img_noise.filter(ImageFilter.GaussianBlur(radius=0.125))
            img_noise = img_noise.resize(original_size, Image.Resampling(1))
            img_noise = img_noise.filter(ImageFilter.EDGE_ENHANCE_MORE)
            img_final = Image.blend(img, img_noise, intensity)
            enhancer = ImageEnhance.Brightness(img_final)
            img_highlights = enhancer.enhance(highlights)
            
            img_list.append(pil2tensor(img_highlights).squeeze(dim=0))
            
        img_highlights = torch.stack(img_list, dim=0)
        return img_highlights


class Image_Grain_Add: 
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "weight": ("FLOAT", {"default": 0.5, "min": -10000.0, "max": 10000.0, "step": 0.01}),
                #"density": ("FLOAT", {"default": 1.0, "min": 0.01, "max": 1.0, "step": 0.01}),
                #"intensity": ("FLOAT", {"default": 1.0, "min": 0.01, "max": 1.0, "step": 0.01}),
                #"highlights": ("FLOAT", {"default": 1.0, "min": 0.01, "max": 255.0, "step": 0.01}),
                #"supersample_factor": ("INT", {"default": 4, "min": 1, "max": 8, "step": 1}),
                #"repeats": ("INT", {"default": 1, "min": 1, "max": 1000, "step": 1})
            }
        }
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "main"

    CATEGORY = "RES4LYF/images"

    def main(self, image, weight=0.5, density=1.0, intensity=1.0, highlights=1.0, supersample_factor=1.0, repeats=1):
        image = image.repeat(repeats, 1, 1, 1)
        image_grain = self.apply_film_grain(image, density, intensity, highlights, supersample_factor)
        
        return (image + weight * (hard_light_blend(image_grain, image) - image), )


    def apply_film_grain(self, img, density=0.1, intensity=1.0, highlights=1.0, supersample_factor=4):

        img_batch = img.clone()
        img_list = []
        for i in range(img_batch.shape[0]):
            img = img_batch[i].unsqueeze(0)
            img = tensor2pil(img)
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
            # apply grayscale noise with specified density/intensity/highlights to PIL image
            img_gray = img.convert('L')
            original_size = img.size
            img_gray = img_gray.resize(
                ((img.size[0] * supersample_factor), (img.size[1] * supersample_factor)), Image.Resampling(2))
            num_pixels = int(density * img_gray.size[0] * img_gray.size[1])

            img_gray_tensor = torch.from_numpy(np.array(img_gray).astype(np.float32) / 255.0).to(device)
            img_gray_flat = img_gray_tensor.view(-1)
            num_pixels = int(density * img_gray_flat.numel())
            indices = torch.randint(0, img_gray_flat.numel(), (num_pixels,), device=img_gray_flat.device)
            values = torch.randint(0, 256, (num_pixels,), device=img_gray_flat.device, dtype=torch.float32) / 255.0
            
            img_gray_flat[indices] = values
            img_gray = img_gray_flat.view(img_gray_tensor.shape)
            
            img_gray_np = (img_gray.cpu().numpy() * 255).astype(np.uint8)
            img_gray = Image.fromarray(img_gray_np)

            img_noise = img_gray.convert('RGB')
            img_noise = img_noise.filter(ImageFilter.GaussianBlur(radius=0.125))
            img_noise = img_noise.resize(original_size, Image.Resampling(1))
            img_noise = img_noise.filter(ImageFilter.EDGE_ENHANCE_MORE)
            img_final = Image.blend(img, img_noise, intensity)
            enhancer = ImageEnhance.Brightness(img_final)
            img_highlights = enhancer.enhance(highlights)
            
            img_list.append(pil2tensor(img_highlights).squeeze(dim=0))
            
        img_highlights = torch.stack(img_list, dim=0)
        return img_highlights


class Frames_Slice:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {

            "required": {
                "frames": ("IMAGE",),
                "start":  ("INT",  {"default": 0, "min": 0, "max": 10000}),
                "stop":   ("INT",  {"default": 1, "min": 1, "max": 10000}),
            },
            "optional": {
            },
        }
        
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION     = "main"
    CATEGORY     = "RES4LYF/images"

    def main(self, frames=None, start=0, stop=1):
        frames_slice = frames[start:stop].clone()
        return (frames_slice,)
