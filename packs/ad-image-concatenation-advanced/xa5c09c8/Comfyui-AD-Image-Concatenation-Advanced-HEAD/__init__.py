import PIL.Image as Image
import torchvision.transforms as t
import torch

class AD_ImageConcatAdvanced:
    def __init__(self):
        pass
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image1": ("IMAGE",),
                "direction": (["horizontal", "vertical"], {"default": "horizontal"}),
                "match_size": ("BOOLEAN", {"default": True}),
                "method": (["lanczos", "bicubic", "bilinear", "nearest"], {"default": "lanczos"}),
                "output_all_concatenations": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                "image2": ("IMAGE",),
                "image3": ("IMAGE",),
                "image4": ("IMAGE",),
                "image5": ("IMAGE",),
            }
        }
    
    RETURN_TYPES = ("IMAGE",)
    OUTPUT_IS_LIST = (True,)
    FUNCTION = "concat_images"
    CATEGORY = "🌻 Addoor/image"

    def concat_images(self, image1, direction="horizontal", match_size=False, method="lanczos", 
                     output_all_concatenations=False, image2=None, image3=None, image4=None, image5=None):
        try:
            # Collect all provided images
            images = [image1]
            for img in [image2, image3, image4, image5]:
                if img is not None:
                    images.append(img)
            
            # If output_all_concatenations is enabled, create cumulative concatenations
            if output_all_concatenations:
                results = []
                for i in range(len(images)):
                    # Concatenate images from 0 to i (inclusive)
                    result = self._concatenate_multiple(
                        images[:i+1], 
                        direction, 
                        match_size, 
                        method
                    )
                    results.append(result)
                
                return (results,)
            else:
                # Single output: concatenate all images
                result = self._concatenate_multiple(images, direction, match_size, method)
                return ([result],)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return ([image1],)

    def _concatenate_multiple(self, images, direction, match_size, method):
        """Concatenate multiple images together."""
        if len(images) == 1:
            return images[0]
        
        # Convert first image to PIL
        result_pil = tensor_to_image(images[0][0])
        
        # Concatenate each subsequent image
        for i in range(1, len(images)):
            img_pil = tensor_to_image(images[i][0])
            result_pil = self._concat_two_images(
                result_pil, 
                img_pil, 
                direction, 
                match_size, 
                method
            )
        
        # Convert back to tensor
        tensor = image_to_tensor(result_pil)
        tensor = tensor.unsqueeze(0)
        tensor = tensor.permute(0, 2, 3, 1)
        
        return tensor

    def _concat_two_images(self, img1, img2, direction, match_size, method):
        """Concatenate two PIL images."""
        # Ensure both images have the same mode
        if img1.mode != img2.mode:
            if 'A' in img1.mode or 'A' in img2.mode:
                img1 = img1.convert('RGBA')
                img2 = img2.convert('RGBA')
            else:
                img1 = img1.convert('RGB')
                img2 = img2.convert('RGB')

        # Match sizes if needed
        if match_size:
            if direction == "horizontal":
                # Horizontal concatenation, match height
                if img1.height != img2.height:
                    new_height = img2.height
                    new_width = int(img1.width * (new_height / img1.height))
                    img1 = img1.resize(
                        (new_width, new_height),
                        get_sampler_by_name(method)
                    )
            else:  # vertical
                # Vertical concatenation, match width
                if img1.width != img2.width:
                    new_width = img2.width
                    new_height = int(img1.height * (new_width / img1.width))
                    img1 = img1.resize(
                        (new_width, new_height),
                        get_sampler_by_name(method)
                    )

        # Create new image canvas
        if direction == "horizontal":
            new_width = img1.width + img2.width
            new_height = max(img1.height, img2.height)
        else:  # vertical
            new_width = max(img1.width, img2.width)
            new_height = img1.height + img2.height

        # Create new canvas
        mode = img1.mode
        new_image = Image.new(mode, (new_width, new_height))

        # Calculate paste positions (center alignment)
        if direction == "horizontal":
            y1 = (new_height - img1.height) // 2
            y2 = (new_height - img2.height) // 2
            new_image.paste(img1, (0, y1))
            new_image.paste(img2, (img1.width, y2))
        else:  # vertical
            x1 = (new_width - img1.width) // 2
            x2 = (new_width - img2.width) // 2
            new_image.paste(img1, (x1, 0))
            new_image.paste(img2, (x2, img1.height))

        return new_image


# Utility functions
def get_sampler_by_name(method: str) -> int:
    """Get PIL resampling method by name."""
    samplers = {
        "lanczos": Image.LANCZOS,
        "bicubic": Image.BICUBIC,
        "hamming": Image.HAMMING,
        "bilinear": Image.BILINEAR,
        "box": Image.BOX,
        "nearest": Image.NEAREST
    }
    return samplers.get(method, Image.LANCZOS)


def tensor_to_image(tensor):
    """Convert tensor to PIL Image."""
    if len(tensor.shape) == 4:
        tensor = tensor.squeeze(0)  # Remove batch dimension
    return t.ToPILImage()(tensor.permute(2, 0, 1))


def image_to_tensor(image):
    """Convert PIL Image to tensor."""
    tensor = t.ToTensor()(image)
    return tensor


# Node registration
NODE_CLASS_MAPPINGS = {
    "AD_image-concat-advanced": AD_ImageConcatAdvanced,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AD_image-concat-advanced": "AD Image Concatenation Advanced",
}
