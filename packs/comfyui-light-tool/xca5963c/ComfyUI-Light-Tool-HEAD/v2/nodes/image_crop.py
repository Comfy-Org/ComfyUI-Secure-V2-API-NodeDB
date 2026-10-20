from __future__ import annotations
from comfy_api.latest import io, sdk
from .._light_eight_runtime import run
from .light_tool_utils import *


class CropImage(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__CropImage_14f4a4b6d22416fe0c72d244', display_name='Light-Tool: Crop Image',
            category='ComfyUI-Light-Tool/image/Crop', description='Crop an image based on its left/top/right/bottom margin',
            inputs=[
                io.Image.Input('image'),
                io.Int.Input('left_margin', default=100, min=0, display_mode=io.NumberDisplay.number),
                io.Int.Input('top_margin', default=100, min=0, display_mode=io.NumberDisplay.number),
                io.Int.Input('right_margin', default=100, min=0, display_mode=io.NumberDisplay.number),
                io.Int.Input('bottom_margin', default=100, min=0, display_mode=io.NumberDisplay.number),
            ],
            outputs=[io.Image.Output(display_name='image', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def crop_img(image, left_margin, top_margin, right_margin, bottom_margin):
        img = tensor2pil(image)
        width, height = img.size

        left = left_margin
        top = top_margin
        right = width - right_margin
        bottom = height - bottom_margin

        if left >= right or top >= bottom:
            raise ValueError("Light-Tool: Margin settings result in an invalid cropping region. "
                             "Please check if the left/right or top/bottom margins are too large.")

        cropped_img = img.crop((left, top, right, bottom))
        result_img = pil2tensor(cropped_img)
        return (result_img,)


    @classmethod
    async def execute(cls, **kwargs):
        return await run(cls().crop_img, kwargs, ['IMAGE'], [False])


class SafeImageCrop(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__SafeImageCrop_71fcf836774a9d2829586717', display_name='Light-Tool: Safe Image Crop',
            category='ComfyUI-Light-Tool/image/Crop', description='Crops image from center to the nearest multiple (e.g., 64) to ensure compatibility with VAE/Latent space.',
            inputs=[
                io.Image.Input('image'),
                io.Combo.Input('multiple_of', options=['8', '16', '32', '64', '128', '256', '512', '1024'], default='64'),
            ],
            outputs=[io.Image.Output(display_name='IMAGE', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    def safe_crop(self, image, multiple_of):
        multiple_of = int(multiple_of)

        height = image.shape[1]
        width = image.shape[2]

        target_height = (height // multiple_of) * multiple_of
        target_width = (width // multiple_of) * multiple_of

        if target_height == 0 or target_width == 0:
            print(f"Warning: Image size ({width}x{height}) is too small for multiple of {multiple_of}.")
            return (image,)

        y_start = (height - target_height) // 2
        x_start = (width - target_width) // 2

        cropped_image = image[:, y_start:y_start + target_height, x_start:x_start + target_width, :]

        return (cropped_image,)


    @classmethod
    async def execute(cls, **kwargs):
        return await run(cls().safe_crop, kwargs, ['IMAGE'], [False])
