import torch
from PIL import Image, ImageOps
from .utils.image_utils import tensor2pil, pil2tensor
from .utils.torch_utils import tensors2common, tensor2mask, tensor2batch

class KMCDEV_Image_Blend_Mask:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image_a": ("IMAGE",),
                "image_b": ("IMAGE",),
                "mask": ("IMAGE",),
                "blend_percentage": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "image_blend_mask"

    CATEGORY = "KMC DEV/Image"

    def image_blend_mask(self, image_a, image_b, mask, blend_percentage):

        # Convert images to PIL
        img_a = tensor2pil(image_a)
        img_b = tensor2pil(image_b)
        mask = ImageOps.invert(tensor2pil(mask).convert('L'))

        # Mask image
        masked_img = Image.composite(img_a, img_b, mask.resize(img_a.size))

        # Blend image
        blend_mask = Image.new(mode="L", size=img_a.size,
                               color=(round(blend_percentage * 255)))
        blend_mask = ImageOps.invert(blend_mask)
        img_result = Image.composite(img_a, masked_img, blend_mask)

        del img_a, img_b, blend_mask, mask

        return (pil2tensor(img_result), )


# IMAGE BLANK NOE


class KMCDEV_Image_Blank_Alpha:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "width": ("INT", {"default": 512, "min": 8, "max": 4096, "step": 1}),
                "height": ("INT", {"default": 512, "min": 8, "max": 4096, "step": 1}),
                "red": ("INT", {"default": 255, "min": 0, "max": 255, "step": 1}),
                "green": ("INT", {"default": 255, "min": 0, "max": 255, "step": 1}),
                "blue": ("INT", {"default": 255, "min": 0, "max": 255, "step": 1}),
                "alpha": ("INT", {"default": 255, "min": 0, "max": 255, "step": 1}),
            }
        }
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "blank_image_alpha"

    CATEGORY = "KMC DEV/Image"

    def blank_image_alpha(self, width, height, red, green, blue, alpha):
        # Ensure multiples
        width = (width // 8) * 8
        height = (height // 8) * 8

        # Create RGBA image with alpha channel
        blank = Image.new(mode="RGBA", size=(width, height),
                         color=(red, green, blue, alpha))

        # Convert to tensor format
        return (pil2tensor(blank),)

class KMCDEV_Mix_Color_By_Mask:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "r": ("INT", {"default": 0, "min": 0, "max": 255, "step": 1}),
                "g": ("INT", {"default": 0, "min": 0, "max": 255, "step": 1}),
                "b": ("INT", {"default": 0, "min": 0, "max": 255, "step": 1}),
                "mask": ("MASK",),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "mix"
    CATEGORY = "KMC DEV/Image"

    def mix(self, image, r, g, b, mask):
        # Normalize RGB values to 0-1 range
        r, g, b = r / 255., g / 255., b / 255.

        # Get image dimensions
        batch_size, height, width, channels = image.shape

        # Create color tensor matching image dimensions
        color_tensor = torch.tensor([r, g, b], device=image.device)
        color_tensor = color_tensor.view(1, 1, 1, 3).expand(batch_size, height, width, 3)

        # Ensure mask has correct dimensions for broadcasting
        mask = mask.unsqueeze(-1).expand(-1, -1, -1, 3)

        # Perform the blend operation
        result = image * (1 - mask) + color_tensor * mask

        return (result,)
