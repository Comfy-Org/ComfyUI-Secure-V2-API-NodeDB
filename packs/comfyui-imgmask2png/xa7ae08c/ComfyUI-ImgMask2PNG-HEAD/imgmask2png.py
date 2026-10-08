from PIL import Image
import torch
import numpy as np
import torch.nn.functional as F


class ImageMask2PNG:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mask": ("MASK",),
                "image": ("IMAGE",),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "remove_background"
    CATEGORY = "🌊ImageMask2PNG"

    def tensor2pil(self, image):
        return Image.fromarray(
            np.clip(255.0 * image.cpu().numpy().squeeze(), 0, 255).astype(np.uint8)
        )

    def pil2tensor(self, image):
        return torch.from_numpy(np.array(image).astype(np.float32) / 255.0).unsqueeze(0)

    def remove_background(self, mask, image):
        processed_images = []

        for img, msk in zip(image, mask):
            orig_image = self.tensor2pil(img)
            orig_mask = self.tensor2pil(msk)
            w, h = orig_image.size

            # 确保图像和掩码的尺寸相同
            if orig_image.size != orig_mask.size:
                print("Resizing mask to match image size")
                orig_mask = orig_mask.resize(orig_image.size, Image.LANCZOS)

            # 将掩码应用到图像上
            orig_image = orig_image.convert("RGBA")
            orig_mask = orig_mask.convert("L")  # 转换掩码为灰度图
            output_image = Image.new("RGBA", orig_image.size)
            output_image.paste(orig_image, (0, 0), orig_mask)

            # 将处理后的图像转换为 PyTorch 张量
            output_image_tensor = self.pil2tensor(output_image)

            processed_images.append(output_image_tensor)

        new_ims = torch.cat(processed_images, dim=0)

        return (new_ims,)


NODE_CLASS_MAPPINGS = {
    "ImageMask2PNG": ImageMask2PNG,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ImageMask2PNG": "🌊ImageMask2PNG",
}
