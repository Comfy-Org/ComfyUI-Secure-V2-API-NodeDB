import numpy as np
import folder_paths
import torch
from PIL import Image
# 🧩 1. Aspect Ratio Image Size Calculator
class AspectRatioImageSize:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "width": ("INT", {
                    "default": 512, "min": 64, "max": 4096, "step": 8
                }),
                "aspect_ratio": ([
                    "1:1", "16:9", "5:4", "4:3", "3:2",
                    "2.39:1", "21:9", "18:9", "17:9", "1.85:1"
                ], {"default": "1:1"}),
                "direction": (["Horizontal", "Vertical"], {"default": "Horizontal"}),
                "info": ("STRING", {
                    "multiline": True,
                    "default": "Example widths: 512, 768, 1024, 1280, 1920",
                    "editable": False
                })
            }
        }

    RETURN_TYPES = ("INT", "INT", "STRING")
    RETURN_NAMES = ("width", "height", "resolution_label")
    FUNCTION = "calculate_size"
    CATEGORY = "utils"

    def calculate_size(self, width, aspect_ratio, direction, info):
        ratios = {
            "1:1": (1, 1), "16:9": (16, 9), "5:4": (5, 4), "4:3": (4, 3),
            "3:2": (3, 2), "2.39:1": (2.39, 1), "21:9": (21, 9),
            "18:9": (18, 9), "17:9": (17, 9), "1.85:1": (1.85, 1)
        }
        w, h = ratios.get(aspect_ratio, (1, 1))
        if direction == "Vertical":
            w, h = h, w
        height = int(round(width * h / w))
        return width, height, f"{width}x{height}"

import numpy as np
from PIL import Image
import folder_paths

class AspectRatioResizeImage:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "width": ("INT", {"default": 512, "min": 64, "max": 4096, "step": 8}),
                "aspect_ratio": ([
                    "1:1", "16:9", "5:4", "4:3", "3:2",
                    "2.39:1", "21:9", "18:9", "17:9", "1.85:1"
                ], {"default": "1:1"}),
                "direction": (["Horizontal", "Vertical"], {"default": "Horizontal"}),
                "crop_method": (["Stretch", "Crop"], {"default": "Stretch"}),
                "info": ("STRING", {
                    "multiline": True,
                    "default": "Example widths: 512, 768, 1024, 1280, 1920",
                    "editable": False
                })
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("resized_image", "resolution_label")
    FUNCTION = "resize_image"
    CATEGORY = "image/resize"

    def resize_image(self, image, width, aspect_ratio, direction, crop_method, info):
        # Aspect ratio dictionary
        ratios = {
            "1:1": (1, 1), "16:9": (16, 9), "5:4": (5, 4), "4:3": (4, 3),
            "3:2": (3, 2), "2.39:1": (2.39, 1), "21:9": (21, 9),
            "18:9": (18, 9), "17:9": (17, 9), "1.85:1": (1.85, 1)
        }

        w_ratio, h_ratio = ratios.get(aspect_ratio, (1, 1))
        if direction == "Vertical":
            w_ratio, h_ratio = h_ratio, w_ratio

        target_height = int(round(width * h_ratio / w_ratio))
        target_width = width

        # ComfyUI image format is BHWC (batch, height, width, channels)
        # Extract the first image from the batch
        image_tensor = image[0]  # Shape: (H, W, C)
        
        # Convert tensor to numpy array (already in HWC format)
        image_np = image_tensor.cpu().numpy()
        
        # Convert from [0,1] float to [0,255] uint8
        image_np = np.clip(image_np * 255.0, 0, 255).astype(np.uint8)

        pil_image = Image.fromarray(image_np)
        original_width, original_height = pil_image.size

        if crop_method == "Crop":
            # Calculate the aspect ratio of the original image
            original_aspect_ratio = original_width / original_height
            target_aspect_ratio = target_width / target_height

            if original_aspect_ratio > target_aspect_ratio:
                # Original is wider than target, need to crop width to match target aspect ratio
                # Calculate new width based on original height and target aspect ratio
                new_width = int(original_height * target_aspect_ratio)
                left = (original_width - new_width) // 2
                right = left + new_width
                cropped_image = pil_image.crop((left, 0, right, original_height))
            else:
                # Original is taller than target, need to crop height to match target aspect ratio
                # Calculate new height based on original width and target aspect ratio
                new_height = int(original_width / target_aspect_ratio)
                top = (original_height - new_height) // 2
                bottom = top + new_height
                cropped_image = pil_image.crop((0, top, original_width, bottom))
            
            # Now resize the cropped image to the target dimensions without stretching
            pil_image = cropped_image.resize((target_width, target_height), Image.LANCZOS)
        else: # Stretch
            pil_image = pil_image.resize((target_width, target_height), Image.LANCZOS)

        # Convert back to tensor format for ComfyUI (BHWC)
        resized_np = np.array(pil_image).astype(np.float32) / 255.0
        
        # Add batch dimension back: (H, W, C) -> (1, H, W, C)
        resized_tensor = torch.from_numpy(resized_np).unsqueeze(0)

        return (resized_tensor, f"{target_width}x{target_height}")

# Node mapping for ComfyUI
NODE_CLASS_MAPPINGS = {
    "AspectRatioResizeImage": AspectRatioResizeImage
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AspectRatioResizeImage": "Aspect Ratio Resize Image"
}

# Node mapping for ComfyUI
NODE_CLASS_MAPPINGS = {
    "AspectRatioResizeImage": AspectRatioResizeImage
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AspectRatioResizeImage": "Aspect Ratio Resize Image"
}


# Node mapping for ComfyUI
NODE_CLASS_MAPPINGS = {
    "AspectRatioResizeImage": AspectRatioResizeImage
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AspectRatioResizeImage": "Aspect Ratio Resize Image"
}

# 📄 3. Markdown Link Generator (optional example)
class MarkdownModelNote:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "url": ("STRING", {"default": ""}),
                "filename": ("STRING", {"default": "model.safetensors"}),
                "folder": ("STRING", {"default": "App\\ComfyUI\\models\\clip"})
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("markdown_note",)
    FUNCTION = "create_markdown"
    CATEGORY = "utils"

    def create_markdown(self, url, filename, folder):
        note = f"""### Model: [{filename}]({url})  
**Output folder:**  
`{folder}`

---"""
        return (note,)


# 🔗 Register all nodes here
NODE_CLASS_MAPPINGS = {
    "AspectRatioImageSize": AspectRatioImageSize,
    "AspectRatioResizeImage": AspectRatioResizeImage,
    "MarkdownModelNote": MarkdownModelNote,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AspectRatioImageSize": "🧩 Aspect Ratio Image Size",
    "AspectRatioResizeImage": "🖼️ Resize to Aspect Ratio",
    "MarkdownModelNote": "📄 Markdown Link Generator",
}
