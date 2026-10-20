from __future__ import annotations
from comfy_api.latest import io, sdk
from .._runtime import run, missing_api, materialize
from .._light_eight_runtime import run as run_eight
from .._light_url_assets import load_image_from_url as load_url_image, load_metadata_from_url as load_url_metadata
from .light_tool_utils import *
import json
import io as bytes_io
import uuid
import cv2
from torchvision.transforms import functional
from PIL import ImageSequence, ImageOps
from typing import Any, Tuple
from .image_upscale import UpscaleMode, upscale_image
from .image_scale import ScaleMode, scale_image
from .._assets import load_image, load_images, save_metadata
from .._aliyun_oss import save_to_aliyun


class LoadImage(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('assets', 'raw')

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__LoadImage_56c891ed1c47a848d12d2f1e', display_name='Light-Tool: Load Image',
            category='ComfyUI-Light-Tool/image/LoadImage', description='Load image',
            inputs=[
                io.Combo.Input('image', options=[], upload=io.UploadType.image, image_folder=io.FolderType.input),
                io.Boolean.Input('keep_alpha_channel', default=False, label_on='enabled', label_off='disabled'),
            ],
            outputs=[io.Image.Output(display_name='image', is_output_list=False), io.Mask.Output(display_name='mask', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    async def load_image(image, keep_alpha_channel):
        return await load_image(image, keep_alpha_channel)


    @classmethod
    async def execute(cls, **kwargs):
        return await run_eight(cls().load_image, kwargs, ['IMAGE', 'MASK'], [False, False])

    @classmethod
    async def fingerprint_inputs(cls, image, **kwargs):
        asset = await sdk.ctx().assets.resolve("input", image)
        return await sdk.ctx().assets.digest(asset)


class LoadImageFromURL(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw', 'assets', 'assets.import_url')

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__LoadImageFromURL_07dd7d8345483f376b5224e5', display_name='Light-Tool: Load Image From URL',
            category='ComfyUI-Light-Tool/image/LoadImage', description='Load image From URL',
            inputs=[
                io.String.Input('url', default='https://www.comfy.org/images/ComfyUI_00000.png', multiline=True),
                io.Boolean.Input('keep_alpha_channel', default=False, label_on='enabled', label_off='disabled'),
            ],
            outputs=[io.Image.Output(display_name='image', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    async def load_image_from_url(url, keep_alpha_channel):
        return await load_url_image(url, keep_alpha_channel)

    @classmethod
    async def execute(cls, **kwargs):
        return await run_eight(cls().load_image_from_url, kwargs, ['IMAGE'], [False])


class LoadImagesFromDir(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('assets', 'raw')

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__LoadImagesFromDir_b63677a201924e4650263f03', display_name='Light-Tool: Load Image List',
            category='ComfyUI-Light-Tool/image/LoadImage', description='Load image From image directory',
            inputs=[
                io.String.Input('directory', default='please input your image dir path'),
                io.Int.Input('image_load_num', optional=True, default=0, min=0, step=1),
                io.Int.Input('start_index', optional=True, default=0, min=0, step=1),
                io.Boolean.Input('load_always', optional=True, default=False, label_on='enabled', label_off='disabled'),
                io.Boolean.Input('keep_alpha_channel', optional=True, default=False, label_on='enabled', label_off='disabled'),
            ],
            outputs=[io.Image.Output(display_name='IMAGE', is_output_list=True), io.Mask.Output(display_name='MASK', is_output_list=True), io.String.Output(display_name='FILE PATH', is_output_list=True)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    async def load_images(directory, image_load_num=0, start_index=0, keep_alpha_channel=False, load_always=False):
        return await load_images(directory, image_load_num, start_index, keep_alpha_channel, load_always)


    @classmethod
    async def execute(cls, **kwargs):
        return await run_eight(cls().load_images, kwargs, ['IMAGE', 'MASK', 'STRING'], [True, True, True])

    @classmethod
    def fingerprint_inputs(cls, **kwargs):
        return float("nan") if kwargs.get("load_always") else hash(frozenset(kwargs))


class ImageMaskApply(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__ImageMaskApply_cae968ccd431811f99fd874a', display_name='Light-Tool: Extract Transparent Image',
            category='ComfyUI-Light-Tool/image/compositing', description='Extract the transparent image using a mask to separate the subject from the background',
            inputs=[
                io.Image.Input('image'),
                io.Image.Input('mask'),
                io.Boolean.Input('invert', default=False),
            ],
            outputs=[io.Image.Output(display_name='image', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def run(image, mask, invert):
        image_list = []
        for _image, _mask in zip(image, mask):
            image_pil = tensor2pil(_image).convert('RGB')
            mask_pil = tensor2pil(_mask).convert('L')
            image_size = image_pil.size
            mask_size = mask_pil.size
            if mask_pil.size != image_pil.size:
                raise ValueError(f"ImageMaskApply(Light-Tool): Images must have the same size. "
                                 f"{image_size}and{mask_size} is not match")
            if invert:
                inverted_mask = invert_mask(mask_pil)
                image_pil = rgb2rgba(image_pil, inverted_mask)
            else:
                image_pil = rgb2rgba(image_pil, mask_pil)
            image = pil2tensor(image_pil)
            image_list.append(image)
        image = torch.cat(image_list, dim=0)
        return (image,)


    @classmethod
    async def execute(cls, **kwargs):
        return await run_eight(cls().run, kwargs, ['IMAGE'], [False])


class MaskToImage(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__MaskToImage_6c4a91b60775091935421bf2', display_name='Light-Tool: Mask to Image',
            category='ComfyUI-Light-Tool/image/mask', description='Convert mask to image',
            inputs=[
                io.Mask.Input('mask'),
            ],
            outputs=[io.Image.Output(display_name='image', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def mask_to_image(mask):
        image_list = []
        for _mask in mask:
            result = _mask.reshape((-1, 1, _mask.shape[-2], _mask.shape[-1])).movedim(1, -1).expand(-1, -1, -1, 3)
            image_list.append(result)
        image = torch.cat(image_list, dim=0)
        return (image,)


    @classmethod
    async def execute(cls, **kwargs):
        return await run_eight(cls().mask_to_image, kwargs, ['IMAGE'], [False])


class ImageToMask(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__ImageToMask_511ea9ac4287ea711d29e706', display_name='Light-Tool: Image to Mask',
            category='ComfyUI-Light-Tool/image/mask', description='Convert image to mask',
            inputs=[
                io.Image.Input('image'),
                io.Combo.Input('channel', options=['red', 'green', 'blue', 'alpha'], default='red'),
            ],
            outputs=[io.Mask.Output(display_name='mask', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def image_to_mask(image, channel):
        mask_list = []
        for img in image:
            channels = ["red", "green", "blue", "alpha"]
            if channel == "alpha":
                img = np.array(tensor2pil(img).convert("RGBA"))
            else:
                img = np.array(tensor2pil(img).convert("RGB"))
            mask = np2tensor(img[:, :, channels.index(channel)])
            mask_list.append(mask)
        mask = torch.cat(mask_list, dim=0)
        return (mask,)


    @classmethod
    async def execute(cls, **kwargs):
        return await run_eight(cls().image_to_mask, kwargs, ['MASK'], [False])


class MaskImageToTransparent(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__MaskImageToTransparent_3f5bcd3f28ad97edee65a7a4', display_name='Light-Tool: Mask Background to Transparent',
            category='ComfyUI-Light-Tool/image/mask', description='Convert the non-masked areas of an image to transparency',
            inputs=[
                io.Image.Input('image'),
            ],
            outputs=[io.Image.Output(display_name='image', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def mask2Transparent(image):
        image_list = []
        for img in image:
            gray_image = tensor2pil(img).convert("L")
            gray_image_with_alpha = Image.new('RGBA', gray_image.size, (255, 255, 255, 0))
            gray_image_with_alpha.paste(gray_image, mask=gray_image)
            transparent_image = pil2tensor(gray_image_with_alpha)
            image_list.append(transparent_image)
        transparent_image = torch.cat(image_list, dim=0)
        return (transparent_image,)


    @classmethod
    async def execute(cls, **kwargs):
        return await run_eight(cls().mask2Transparent, kwargs, ['IMAGE'], [False])


class BoundingBoxCropping(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__BoundingBoxCropping_57d21cd42c4a91e7075a1619', display_name='Light-Tool: Bounding Box Cropping',
            category='ComfyUI-Light-Tool/image/ImageCrop', description='Cut out an image based on the smallest bounding rectangle of the transparent object within it',
            inputs=[
                io.Image.Input('image'),
            ],
            outputs=[io.Image.Output(display_name='image', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def image_crop(image):
        image_list = []
        for img in image:
            img = tensor2pil(img).convert("RGBA")
            img = np.array(img)
            alpha_channel = img[:, :, 3]
            bbox = cv2.boundingRect(alpha_channel)
            x, y, w, h = bbox
            cropped_img_array = img[y:y + h, x:x + w]
            cropped_img_array = cv2.cvtColor(cropped_img_array, cv2.COLOR_RGB2RGBA)
            crop_image = np2tensor(cropped_img_array)
            image_list.append(crop_image)
        crop_image = torch.cat(image_list, dim=0)
        return (crop_image,)


    @classmethod
    async def execute(cls, **kwargs):
        return await run_eight(cls().image_crop, kwargs, ['IMAGE'], [False])


class MaskBoundingBoxCropping(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__MaskBoundingBoxCropping_1c4e7c4c5d48567c17549339', display_name='Light-Tool: Mask Bounding Box Cropping',
            category='ComfyUI-Light-Tool/image/ImageCrop', description='Cut out an mask image based on the smallest bounding rectangle of the transparent object within it',
            inputs=[
                io.Image.Input('image'),
            ],
            outputs=[io.Image.Output(display_name='image', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def mask_image_crop(image):
        image_list = []
        for img in image:
            gray_image = tensor2pil(img).convert("L")

            gray_image_with_alpha = Image.new('RGBA', gray_image.size, (255, 255, 255, 0))
            gray_image_with_alpha.paste(gray_image, mask=gray_image)

            img_array = np.array(gray_image_with_alpha)
            if img_array.shape[2] != 4:
                raise ValueError("MaskBoundingBoxCropping(Light-Tool): Input image must have an alpha channel")
            alpha_channel = img_array[:, :, 3]
            bbox = cv2.boundingRect(alpha_channel)
            x, y, w, h = bbox
            img_array = img_array[y:y + h, x:x + w]

            cropped_image = Image.fromarray(img_array, 'RGBA')
            black_background = Image.new('RGBA', cropped_image.size, (0, 0, 0, 255))
            cropped_image = Image.alpha_composite(black_background, cropped_image)
            crop_image = pil2tensor(cropped_image)

            image_list.append(crop_image)
        crop_image = torch.cat(image_list, dim=0)
        return (crop_image,)


    @classmethod
    async def execute(cls, **kwargs):
        return await run_eight(cls().mask_image_crop, kwargs, ['IMAGE'], [False])


class InvertMask(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__InvertMask_ae99e58376ef36618f9741bc', display_name='Light-Tool: Invert Mask',
            category='ComfyUI-Light-Tool/image/mask', description='Invert the colors between the masked and unmasked regions of an image',
            inputs=[
                io.Image.Input('image'),
            ],
            outputs=[io.Image.Output(display_name='image', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def invert_mask(image):
        inverted_mask_list = []
        for img in image:
            mask_image = tensor2pil(img).convert('L')
            pixels = mask_image.load()
            width, height = mask_image.size
            for y in range(height):
                for x in range(width):
                    current_value = pixels[x, y]
                    new_value = 255 - current_value
                    pixels[x, y] = new_value
            inverted_mask = pil2tensor(mask_image)
            inverted_mask_list.append(inverted_mask)
        inverted_mask = torch.cat(inverted_mask_list, dim=0)
        return (inverted_mask,)


    @classmethod
    async def execute(cls, **kwargs):
        return await run_eight(cls().invert_mask, kwargs, ['IMAGE'], [False])


class AddBackground(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__AddBackground_130d24f9cf18fc2e96ecd25c', display_name='Light-Tool: Add solid color background',
            category='ComfyUI-Light-Tool/image/compositing', description='Add solid color background to transparent image',
            inputs=[
                io.Image.Input('image'),
                io.String.Input('color_hex', default='#FFFFFF', multiline=False),
                io.Boolean.Input('use_hex', default=True),
                io.Int.Input('R', default=255, min=0, max=255, display_mode=io.NumberDisplay.number),
                io.Int.Input('G', default=255, min=0, max=255, display_mode=io.NumberDisplay.number),
                io.Int.Input('B', default=255, min=0, max=255, display_mode=io.NumberDisplay.number),
            ],
            outputs=[io.Image.Output(display_name='image', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def add_background(image, color_hex, use_hex, R, G, B):
        if use_hex and not (color_hex.startswith("#") and len(color_hex) == 7):
            raise ValueError("AddBackground(Light-Tool): Invalid hexadecimal color value")
        image_list = []
        for img_tensor in image:
            img = tensor2pil(img_tensor)

            if use_hex:
                rgb_background_color = hex_to_rgb(color_hex)
            else:
                rgb_background_color = (R, G, B)
            background = Image.new("RGB", img.size, rgb_background_color)
            img_array = np.array(img)[:, :, :3]
            alpha_array = np.array(img)[:, :, 3] / 255.0
            bg_array = np.array(background)
            result_array = (img_array * alpha_array[:, :, np.newaxis] + bg_array * (
                    1 - alpha_array[:, :, np.newaxis])).astype(np.uint8)

            result_img = Image.fromarray(result_array)
            new_image = pil2tensor(result_img)
            image_list.append(new_image)

        new_image = torch.cat(image_list, dim=0)
        return (new_image,)


    @classmethod
    async def execute(cls, **kwargs):
        return await run_eight(cls().add_background, kwargs, ['IMAGE'], [False])


class ImageOverlay(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__ImageOverlay_69b83681b448ad92645ffd5c', display_name='Light-Tool: Image Overlay',
            category='ComfyUI-Light-Tool/image/compositing', description='Overlay one image on top of another to create a composite image',
            inputs=[
                io.Image.Input('origin_image'),
                io.Image.Input('overlay_image'),
                io.Image.Input('overlay_mask'),
            ],
            outputs=[io.Image.Output(display_name='IMAGE', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def combine_images(origin_image: torch.Tensor, overlay_image: torch.Tensor, overlay_mask: torch.Tensor):
        image_list = []
        for img in origin_image:
            image = tensor2pil(overlay_image).convert('RGB')
            bg = tensor2pil(img).convert('RGB')
            alpha = tensor2pil(overlay_mask).convert('L')

            if image.size != bg.size:
                raise ValueError(f"ImageOverlay(Light-Tool): Images must have the same size. "
                                 f"{image.size}and{bg.size} is not match")

            image = functional.to_tensor(image)
            bg = functional.to_tensor(bg)
            bg = functional.resize(bg, image.shape[-2:])
            alpha = functional.to_tensor(alpha)
            new_image = image * alpha + bg * (1 - alpha)
            new_image = new_image.squeeze(0).permute(1, 2, 0).numpy()
            image_list.append(pil2tensor(np2pil(new_image)))
        images = torch.cat(image_list, dim=0)
        return (images,)


    @classmethod
    async def execute(cls, **kwargs):
        return await run_eight(cls().combine_images, kwargs, ['IMAGE'], [False])


class SimpleImageOverlay(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__SimpleImageOverlay_1b6c44cbc816372ad8f28138', display_name='Light-Tool: Simple Image Overlay',
            category='ComfyUI-Light-Tool/image/compositing', description='Overlay one image on top of another to create a composite image',
            inputs=[
                io.Image.Input('foreground'),
                io.Image.Input('background'),
                io.Boolean.Input('center', default=True),
                io.Int.Input('left', default=0, min=0, step=1, display_mode=io.NumberDisplay.number),
                io.Int.Input('top', default=0, min=0, step=1, display_mode=io.NumberDisplay.number),
            ],
            outputs=[io.Image.Output(display_name='IMAGE', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def combine_images(foreground: torch.Tensor, background: torch.Tensor, center, left, top):
        image_list = []
        for bg in background:
            foreground_pil = tensor2pil(foreground)
            if foreground_pil.mode != "RGBA":
                foreground_pil = foreground_pil.convert("RGBA")
            background_pil = tensor2pil(bg)

            if center:
                bg_width, bg_height = background_pil.size
                fg_width, fg_height = foreground_pil.size
                left = (bg_width - fg_width) // 2
                top = (bg_height - fg_height) // 2

            background_pil.paste(foreground_pil, (left, top), foreground_pil)
            result = pil2tensor(background_pil)
            image_list.append(result)
        images = torch.cat(image_list, dim=0)
        return (images,)


    @classmethod
    async def execute(cls, **kwargs):
        return await run_eight(cls().combine_images, kwargs, ['IMAGE'], [False])


class AddBackgroundV2(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__AddBackgroundV2_700eb92506c08c31df65dfb0', display_name='Light-Tool: Add solid color background V2',
            category='ComfyUI-Light-Tool/image/compositing', description='Add solid color background to transparent image',
            inputs=[
                io.Image.Input('image'),
                io.String.Input('color_hex', default='#FFFFFF', multiline=False),
                io.Boolean.Input('use_hex', default=True),
                io.Int.Input('R', default=255, min=0, max=255, display_mode=io.NumberDisplay.number),
                io.Int.Input('G', default=255, min=0, max=255, display_mode=io.NumberDisplay.number),
                io.Int.Input('B', default=255, min=0, max=255, display_mode=io.NumberDisplay.number),
                io.Boolean.Input('square', default=False),
                io.Int.Input('left_margin', default=0, min=0, step=1, display_mode=io.NumberDisplay.number),
                io.Int.Input('right_margin', default=0, min=0, step=1, display_mode=io.NumberDisplay.number),
                io.Int.Input('top_margin', default=0, min=0, step=1, display_mode=io.NumberDisplay.number),
                io.Int.Input('bottom_margin', default=0, min=0, step=1, display_mode=io.NumberDisplay.number),
            ],
            outputs=[io.Image.Output(display_name='image', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def add_background_v2(image, color_hex, use_hex, R, G, B, square, left_margin, right_margin, top_margin,
                          bottom_margin):

        if use_hex and not (color_hex.startswith("#") and len(color_hex) == 7):
            raise ValueError("AddBackgroundV2(Light-Tool): Invalid hexadecimal color value")

        image_list = []
        for img in image:
            overlay = tensor2pil(img)

            if overlay.mode != 'RGBA':
                overlay = overlay.convert('RGBA')

            width, height = overlay.size
            if square:
                if width > height:
                    top_margin += (width - height) // 2
                    bottom_margin += (width - height) // 2
                else:
                    left_margin += (height - width) // 2
                    right_margin += (height - width) // 2

            background_width = width + left_margin + right_margin
            background_height = height + top_margin + bottom_margin
            if use_hex:
                rgb_background_color = hex_to_rgb(color_hex)
            else:
                rgb_background_color = (R, G, B)

            background = Image.new('RGB', (background_width, background_height), rgb_background_color)
            background.paste(overlay, (left_margin, top_margin), overlay)
            new_image = pil2tensor(background)
            image_list.append(new_image)

        new_image = torch.cat(image_list, dim=0)
        return (new_image,)


    @classmethod
    async def execute(cls, **kwargs):
        return await run_eight(cls().add_background_v2, kwargs, ['IMAGE'], [False])


class IsTransparent(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__IsTransparent_ca95dc01ade3d5bda6cf0b7e', display_name='Light-Tool: Is Transparent',
            category='ComfyUI-Light-Tool/image/ImageInfo', description='Detect if an image is transparent',
            inputs=[
                io.Image.Input('image'),
                io.Float.Input('threshold', default=0.01, min=0.01, max=0.99, display_mode=io.NumberDisplay.slider),
            ],
            outputs=[io.Boolean.Output(display_name='BOOLEAN', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def is_transparent(image: torch.Tensor, threshold: float):
        img = tensor2pil(image)
        if img.mode == 'RGBA':
            img_array = np.array(img)
            alpha_channel = img_array[:, :, 3] / 255.0
            transparency_ratio = np.mean(alpha_channel < 1)
            return (transparency_ratio > threshold,)
        elif img.mode == 'P':
            try:
                transparent_index = img.info['transparency']
                color = img.getcolor(transparent_index)
                return (color[3] == 0,)
            except KeyError:
                return (False,)
        else:
            return (False,)


    @classmethod
    async def execute(cls, **kwargs):
        return await run_eight(cls().is_transparent, kwargs, ['BOOLEAN'], [False])


class PhantomTankEffect(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__PhantomTankEffect_fe73fad5f87131408245770b', display_name='Light-Tool: Generate PhantomTankEffect',
            category='ComfyUI-Light-Tool/image/compositing', description="Creates a 'Phantom Tank' effect image",
            inputs=[
                io.Image.Input('image1'),
                io.Image.Input('image2'),
                io.Int.Input('offset', default=128, min=0, max=255, display_mode=io.NumberDisplay.slider),
                io.Int.Input('alpha_min', default=1, min=0, max=255, display_mode=io.NumberDisplay.slider),
                io.Int.Input('alpha_max', default=255, min=0, max=255, display_mode=io.NumberDisplay.slider),
                io.Int.Input('v_min', default=0, min=0, max=255, display_mode=io.NumberDisplay.slider),
                io.Int.Input('v_max', default=255, min=0, max=255, display_mode=io.NumberDisplay.slider),
                io.Combo.Input('gray_method', options=['luminosity', 'average', 'max', 'min', 'custom'], default='luminosity'),
            ],
            outputs=[io.Image.Output(display_name='image', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def process_images(image1: torch.Tensor, image2: torch.Tensor, offset: int, alpha_min: int, alpha_max: int,
                       v_min: int, v_max: int, gray_method: int):

        img1 = tensor2pil(image1)
        img2 = tensor2pil(image2)

        width = max(img1.width, img2.width)
        height = max(img1.height, img2.height)

        img1_gray = to_gray(img1, method=gray_method)
        img2_gray = to_gray(img2, method=gray_method)

        result_img = Image.new("RGBA", (width, height))

        pixels1: Any = img1_gray.load()
        pixels2: Any = img2_gray.load()
        pixels_result: Any = result_img.load()

        for y in range(height):
            for x in range(width):
                v1 = pixels1[x, y] / 2
                v2 = pixels2[x, y] / 2 + offset
                v1 = max(alpha_min, v1)
                v2 = min(alpha_max - 1, v2)
                a = alpha_max - v2 + v1
                a = min(alpha_max, max(alpha_min, a))
                v = v1 * v_max / a
                v = min(v_max, max(v_min, v))
                pixels_result[x, y] = (int(v), int(v), int(v), int(a))

        result_img = pil2tensor(result_img)
        return (result_img,)


    @classmethod
    async def execute(cls, **kwargs):
        return await run_eight(cls().process_images, kwargs, ['IMAGE'], [False])


class MaskContourExtractor(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__MaskContourExtractor_c7668a17ab51e220887f7bb0', display_name='Light-Tool: MaskContourExtractor',
            category='ComfyUI-Light-Tool/image/ImageInfo', description='Extract contour points of the mask in the image',
            inputs=[
                io.Image.Input('image'),
                io.String.Input('color_hex', default='#FF0000', multiline=False),
                io.Boolean.Input('use_hex', default=True),
                io.Int.Input('R', default=255, min=0, max=255, display_mode=io.NumberDisplay.number),
                io.Int.Input('G', default=255, min=0, max=255, display_mode=io.NumberDisplay.number),
                io.Int.Input('B', default=255, min=0, max=255, display_mode=io.NumberDisplay.number),
            ],
            outputs=[io.Image.Output(display_name='image', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def contour_extractor(image, color_hex, use_hex, R, G, B):

        image_pil = tensor2pil(image).convert('L')
        image = np.array(image_pil).astype(np.uint8)

        if use_hex:
            rgb_background_color = hex_to_rgb(color_hex)
        else:
            rgb_background_color = (R, G, B)

        _, binary_image = cv2.threshold(image, 127, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(binary_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        contour_points = []
        for contour in contours:
            for point in contour:
                contour_points.append(list(point[0]))

        contour_image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        cv2.drawContours(contour_image, contours, -1, rgb_background_color, 1)
        result_img = np2tensor(contour_image)
        return (result_img,)


    @classmethod
    async def execute(cls, **kwargs):
        return await run_eight(cls().contour_extractor, kwargs, ['IMAGE'], [False])


class AdvancedSolidColorBackground(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__SolidColorBackground_518e94278457ebd64f28097d', display_name='Light-Tool: SolidColorBackground',
            category='ComfyUI-Light-Tool/image/compositing', description='Generate solid color background',
            inputs=[
                io.Int.Input('width', default=1024, min=0, display_mode=io.NumberDisplay.number),
                io.Int.Input('height', default=1024, min=0, display_mode=io.NumberDisplay.number),
                io.String.Input('color_hex', default='#FF0000', multiline=False),
                io.Boolean.Input('use_hex', default=True),
                io.Int.Input('R', default=255, min=0, max=255, display_mode=io.NumberDisplay.number),
                io.Int.Input('G', default=255, min=0, max=255, display_mode=io.NumberDisplay.number),
                io.Int.Input('B', default=255, min=0, max=255, display_mode=io.NumberDisplay.number),
                io.Combo.Input('mode', options=['RGB', 'RGBA', 'L'], default='RGB'),
                io.Int.Input('alpha', default=255, min=0, max=255, display_mode=io.NumberDisplay.number),
            ],
            outputs=[io.Image.Output(display_name='image', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def generate_bg(color_hex, use_hex, width, height, R, G, B, mode, alpha):

        if use_hex:
            rgb_background_color = hex_to_rgb(color_hex)
        else:
            rgb_background_color = (R, G, B)

        if 'A' in mode:
            alpha_channel = alpha
            rgb_background_color += (alpha_channel,)

        image = Image.new(mode, (width, height), rgb_background_color)
        result_img = pil2tensor(image)
        return (result_img,)


    @classmethod
    async def execute(cls, **kwargs):
        return await run_eight(cls().generate_bg, kwargs, ['IMAGE'], [False])


class RGB2RGBA(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__RGB2RGBA_df99dcd33d7441c34d209c6d', display_name='Light-Tool: RGB To RGBA',
            category='ComfyUI-Light-Tool/image/transform', description='Convert an RGB image to RGBA format',
            inputs=[
                io.Image.Input('image'),
            ],
            outputs=[io.Image.Output(display_name='image', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def rgb2rgba(image):
        image_list = []
        for img in image:
            img = tensor2pil(img).convert("RGBA")
            result_img = pil2tensor(img)
            image_list.append(result_img)
        new_image = torch.cat(image_list, dim=0)
        return (new_image,)


    @classmethod
    async def execute(cls, **kwargs):
        return await run_eight(cls().rgb2rgba, kwargs, ['IMAGE'], [False])


class RGBA2RGB(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__RGBA2RGB_512d1840be0f13948e3565d3', display_name='Light-Tool: RGBa To RGB',
            category='ComfyUI-Light-Tool/image/transform', description='Convert an RGBA image to RGB format',
            inputs=[
                io.Image.Input('image'),
            ],
            outputs=[io.Image.Output(display_name='image', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def rgba2rgb(image):
        image_list = []
        for img in image:
            img = tensor2pil(img).convert("RGB")
            result_img = pil2tensor(img)
            image_list.append(result_img)
        new_image = torch.cat(image_list, dim=0)
        return (new_image,)


    @classmethod
    async def execute(cls, **kwargs):
        return await run_eight(cls().rgba2rgb, kwargs, ['IMAGE'], [False])


class InputText(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__InputText_da29169f12d2bc0114fffc41', display_name='Light-Tool: Input Text',
            category='ComfyUI-Light-Tool/Text', description='Input string text ',
            inputs=[
                io.String.Input('input_text', multiline=True, placeholder='Please input text'),
            ],
            outputs=[io.String.Output(display_name='text', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def input_text(input_text):
        input_text = '' if not input_text else input_text.strip()
        return (input_text,)


    @classmethod
    async def execute(cls, **kwargs):
        return await run(cls().input_text, kwargs, ['STRING'], [False])


class ShowText(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__ShowText_e50e80d2eddf1f698f3de946', display_name='Light-Tool: Show Text',
            category='ComfyUI-Light-Tool/Text', description='Show output Text',
            inputs=[
                io.AnyType.Input('text', extra_dict={'multiline': True}),
            ],
            outputs=[io.String.Output(display_name='text', is_output_list=True)],
            is_input_list=True, is_output_node=True,
        )

    @staticmethod
    def show_text(text):
        output = text[0] if isinstance(text[0], list) else text
        return {"ui": {"text": output}, "result": (output,)}


    @classmethod
    async def execute(cls, **kwargs):
        return await run_eight(cls().show_text, kwargs, ['STRING'], [True])


class ShowAnything(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__ShowAnything_ccee18ec28ae9a83a98ccb75', display_name='Light-Tool: Show Anything',
            category='ComfyUI-Light-Tool/Utility', description='Show anything - displays any type of data in a readable format',
            inputs=[
                io.AnyType.Input('anything'),
            ],
            outputs=[io.AnyType.Output(display_name='output', is_output_list=False)],
            is_input_list=False, is_output_node=True,
        )

    @staticmethod
    def show_anything(anything):

        def format_value(value):
            """Convert various types to readable string format"""
            if isinstance(value, str):
                return value

            if isinstance(value, (list, tuple, dict)):
                try:
                    return json.dumps(value, indent=2, ensure_ascii=False, default=str)
                except Exception as e:
                    print(e)
                    return str(value)

        output_text = format_value(anything)
        if isinstance(anything, np.bool_):
            anything = bool(anything)

        return {"ui": {"text": [output_text]}, "result": (anything,)}


    @classmethod
    async def execute(cls, **kwargs):
        value = kwargs['anything']
        result = cls.show_anything(await materialize(value))
        # Keep the original dataflow handles; only the diagnostic reads a private value.
        return io.NodeOutput(value, ui=result['ui'])


class PreviewVideo(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('assets', 'assets.import_url', 'ui')

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__PreviewVideo_24e01362ad662b2739c9444e', display_name='Light-Tool: Preview Video',
            category='ComfyUI-Light-Tool/Video', description='Preview video from video url',
            inputs=[
                io.String.Input('video_url', multiline=True, placeholder='Please input video url'),
            ],
            outputs=[],
            is_input_list=False, is_output_node=True,
        )

    @classmethod
    async def execute(cls, **kwargs):
        from .._video import preview_video
        values = await materialize(kwargs)
        return await preview_video(**values)


class LoadVideo(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('assets', 'assets.import_url')

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__LoadVideo_41718ce804fa917453f0cecc', display_name='Light-Tool: Load Video',
            category='ComfyUI-Light-Tool/Video', description='Load the video from video url and save to your directory',
            inputs=[
                io.String.Input('video_url'),
                io.String.Input('server', default='', placeholder='server address'),
                io.String.Input('save_dir', default=''),
            ],
            outputs=[io.String.Output(display_name='video_name', is_output_list=False), io.String.Output(display_name='video_path', is_output_list=False), io.String.Output(display_name='video_url', is_output_list=False)],
            is_input_list=False, is_output_node=True,
        )

    @classmethod
    async def execute(cls, **kwargs):
        from .._video import load_video
        values = await materialize(kwargs)
        return await load_video(**values)


class SaveVideo(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('assets', 'assets.import_url', 'output', 'ui')

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__SaveVideo_ccbc535096781f2841cdca37', display_name='Light-Tool: Save Video',
            category='ComfyUI-Light-Tool/Video', description='Saves the video by video url to your directory',
            inputs=[
                io.String.Input('video_url'),
                io.String.Input('server', default='', placeholder='server address'),
                io.String.Input('save_dir', default=''),
            ],
            outputs=[],
            is_input_list=False, is_output_node=True,
        )

    @classmethod
    async def execute(cls, **kwargs):
        from .._video import save_video
        values = await materialize(kwargs)
        return await save_video(**values)


class SaveToAliyunOSS(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('assets', 'assets.import_url', 'integrations.aliyun_oss')

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__SaveToAliyunOSS_45558535f40d4f0fd1919891', display_name='Light-Tool: Save File To Aliyun OSS',
            category='ComfyUI-Light-Tool/OSS', description='Saves the file to aliyun OSS',
            inputs=[
                io.String.Input('file'),
                io.String.Input('save_name', default=''),
                io.String.Input('endpoint', default=''),
                io.String.Input('bucket', default=''),
                io.String.Input('oss_access_key_id', default=''),
                io.String.Input('oss_access_key_secret', default=''),
                io.String.Input('oss_session_token', default=''),
                io.String.Input('visit_endpoint', default=''),
                io.Boolean.Input('use_cname', default=False, label_on='enabled', label_off='disabled'),
                io.Boolean.Input('sign', default=False, label_on='enabled', label_off='disabled'),
                io.Int.Input('timeout', default=0),
            ],
            outputs=[io.String.Output(display_name='file_url', is_output_list=False)],
            is_input_list=False, is_output_node=True,
        )

    @classmethod
    async def execute(cls, **kwargs):
        return io.NodeOutput(*(await save_to_aliyun(**kwargs)))


class GetImageSize(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__GetImageSize_1ad654de2777bc24636affdb', display_name='Light-Tool: Get Image Size',
            category='ComfyUI-Light-Tool/image/ImageInfo', description='Get image base info',
            inputs=[
                io.Image.Input('image'),
                io.Boolean.Input('output_size', default=False, label_on='enabled', label_off='disabled'),
            ],
            outputs=[io.Int.Output(display_name='width', is_output_list=False), io.Int.Output(display_name='height', is_output_list=False), io.Int.Output(display_name='size', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def image_size(image, output_size):
        image = tensor2pil(image)
        file_size = 0
        if output_size:
            encoded = bytes_io.BytesIO()
            image.save(encoded, format="PNG")
            file_size = len(encoded.getvalue())
            print(f"The size of the image file is: {file_size} bytes")
        return image.width, image.height, file_size


    @classmethod
    async def execute(cls, **kwargs):
        return await run(cls().image_size, kwargs, ['INT', 'INT', 'INT'], [False, False, False])


class ImageConcat(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__ImageConcat_d4aba0f18a7397494b0eee57', display_name='Light-Tool: Image Concat',
            category='ComfyUI-Light-Tool/image/compositing', description='Concatenates the N input images into a 1xN or Nx1 grid',
            inputs=[
                io.Image.Input('image1'),
                io.Image.Input('image2'),
                io.Combo.Input('direction', options=['horizontal', 'vertical'], default='horizontal'),
                io.Image.Input('image3', optional=True),
                io.Image.Input('image4', optional=True),
                io.Image.Input('image5', optional=True),
            ],
            outputs=[io.Image.Output(display_name='image', is_output_list=False), io.Mask.Output(display_name='mask', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def image_concat(direction, **kwargs):
        images = [tensor2pil(x) for x in kwargs.values()]

        if direction == 'horizontal':
            height = images[0].height
            for img in images:
                if img.height != height:
                    raise ValueError(
                        f"(Light-Tool/ImageConcat) All images must have the same height. {img.height} and {height}"
                    )
            total_width = sum(img.width for img in images)
            new_image = Image.new('RGB', (total_width, height))
        elif direction == 'vertical':
            width = images[0].width
            for img in images:
                if img.width != width:
                    raise ValueError(
                        f"(Light-Tool/ImageConcat) All images must have the same width. {img.width} and {width}"
                    )
            total_height = sum(img.height for img in images)
            new_image = Image.new('RGB', (width, total_height))
        else:
            raise ValueError("(Light-Tool/ImageConcat) Direction must be 'horizontal' or 'vertical'.")

        x_offset = 0
        y_offset = 0
        for img in images:
            if direction == 'horizontal':
                new_image.paste(img, (x_offset, 0))
                x_offset += img.width
            elif direction == 'vertical':
                new_image.paste(img, (0, y_offset))
                y_offset += img.height

        result_img = pil2tensor(new_image)
        mask = np2tensor(np.array(new_image)[:, :, 0])
        return result_img, mask


    @classmethod
    async def execute(cls, **kwargs):
        return await run_eight(cls().image_concat, kwargs, ['IMAGE', 'MASK'], [False, False])


class TextConnect(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__TextConnect_1a1a984d35bb73b403988b4a', display_name='Light-Tool: Connect Text Strings',
            category='ComfyUI-Light-Tool/Text', description='Connect multiple text strings',
            inputs=[
                io.AnyType.Input('string_list', optional=True, extra_dict={'default': ''}),
                io.String.Input('string_1', optional=True),
                io.String.Input('string_2', optional=True),
                io.String.Input('string_3', optional=True),
                io.String.Input('string_4', optional=True),
                io.String.Input('string_5', optional=True),
                io.String.Input('string_6', optional=True),
                io.String.Input('string_7', optional=True),
                io.String.Input('string_8', optional=True),
                io.String.Input('delimiter', optional=True, default=''),
            ],
            outputs=[io.String.Output(display_name='text', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def text_connect(delimiter, **kwargs):
        string_list1 = kwargs.get('string_list')
        string_list2 = [x for x in kwargs.values() if x and not isinstance(x, list)]
        all_string_list = string_list1 + string_list2 if string_list1 else string_list2
        return (delimiter.join(all_string_list),)


    @classmethod
    async def execute(cls, **kwargs):
        return await run(cls().text_connect, kwargs, ['STRING'], [False])


class SimpleTextConnect(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__SimpleTextConnect_c157e1fe6a76baf88bb19477', display_name='Light-Tool: Simple Connect Text Strings',
            category='ComfyUI-Light-Tool/Text', description='Connect multiple text strings',
            inputs=[
                io.AnyType.Input('string1', extra_dict={'default': ''}),
                io.String.Input('string2', default='', multiline=True),
                io.String.Input('delimiter', default=''),
            ],
            outputs=[io.AnyType.Output(display_name='text', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def text_connect(string1, string2, delimiter):
        if type(string1) == list:
            connect_result = []
            for str1 in string1:
                result = str1 + delimiter + string2
                connect_result.append(result)
        else:
            connect_result = string1 + delimiter + string2
        return (connect_result,)


    @classmethod
    async def execute(cls, **kwargs):
        return await run(cls().text_connect, kwargs, ['*'], [False])


class InputTextList(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__InputTextList_af8369a68564dafa2106e64e', display_name='Light-Tool: Input Text List',
            category='ComfyUI-Light-Tool/Text', description='Connect multiple text strings',
            inputs=[
                io.String.Input('string_1', optional=True),
                io.String.Input('string_2', optional=True),
                io.String.Input('string_3', optional=True),
                io.String.Input('string_4', optional=True),
            ],
            outputs=[io.AnyType.Output(display_name='strings', is_output_list=True)],
            is_input_list=False, is_output_node=True,
        )

    @staticmethod
    def input_text_list(**kwargs):
        return ([[x for x in kwargs.values() if x]],)


    @classmethod
    async def execute(cls, **kwargs):
        return await run(cls().input_text_list, kwargs, ['*'], [True])


class MorphologicalTF(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__MorphologicalTF_1c405f37e93d765e50e10b94', display_name='Light-Tool: Morphological Transform',
            category='ComfyUI-Light-Tool/image/transform', description='Perform morphological transformations on images',
            inputs=[
                io.Image.Input('image'),
                io.Combo.Input('option', options=['dilate', 'erode'], default='dilate'),
                io.Int.Input('kernel_x', default=3, min=0, display_mode=io.NumberDisplay.number),
                io.Int.Input('kernel_y', default=3, min=0, display_mode=io.NumberDisplay.number),
                io.Int.Input('iterations', default=1, min=0, display_mode=io.NumberDisplay.number),
            ],
            outputs=[io.Image.Output(display_name='image', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def morphology_process(image, option, kernel_x, kernel_y, iterations):

        image_pil = tensor2pil(image).convert('L')
        image = np.array(image_pil).astype(np.uint8)
        if option == "dilate":
            result_image = dilate_image(image, (kernel_x, kernel_y), iterations)
        else:
            result_image = erode_image(image, (kernel_x, kernel_y), iterations)
        result_img = np2tensor(result_image)
        return (result_img,)


    @classmethod
    async def execute(cls, **kwargs):
        return await run_eight(cls().morphology_process, kwargs, ['IMAGE'], [False])


class Hex2RGB(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__Hex2RGB_6338f8e72af3cc2fb93e36a2', display_name='Light-Tool: Hex to RGB',
            category='ComfyUI-Light-Tool/image/Color', description='Hex color code convert to RGB code',
            inputs=[
                io.String.Input('color_hex', default='#FFFFFF', multiline=False),
            ],
            outputs=[io.Int.Output(display_name='R', is_output_list=False), io.Int.Output(display_name='G', is_output_list=False), io.Int.Output(display_name='B', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def hex2rgb(color_hex):
        if "#000000" == color_hex:
            return 0, 0, 0
        elif "#ffffff".lower() == color_hex:
            return 255, 255, 255
        else:
            return hex_to_rgb(color_hex)


    @classmethod
    async def execute(cls, **kwargs):
        return await run(cls().hex2rgb, kwargs, ['INT', 'INT', 'INT'], [False, False, False])


class RGB2Hex(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__RGB2Hex_3b5eadaecb6b83e684b1f031', display_name='Light-Tool: RGB to Hex',
            category='ComfyUI-Light-Tool/image/Color', description='RGB code convert to Hex color code',
            inputs=[
                io.Int.Input('R', default='255', min=0, max=255, display_mode=io.NumberDisplay.number),
                io.Int.Input('G', default='0', min=0, max=255, display_mode=io.NumberDisplay.number),
                io.Int.Input('B', default='0', min=0, max=255, display_mode=io.NumberDisplay.number),
            ],
            outputs=[io.String.Output(display_name='hex_color', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def rgb2hex(R, G, B):
        if not (0 <= int(R) <= 255 and 0 <= int(G) <= 255 and 0 <= int(B) <= 255):
            raise ValueError("RGB values must be between 0 and 255")

        return "#{:02X}{:02X}{:02X}".format(int(R), int(G), int(B)),


    @classmethod
    async def execute(cls, **kwargs):
        return await run(cls().rgb2hex, kwargs, ['STRING'], [False])


class ScaleImage(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__ScaleImage_f829880c9370480e0aec02d4', display_name='Light-Tool: Scale Image',
            category='ComfyUI-Light-Tool/image/transform', description='',
            inputs=[
                io.Image.Input('image'),
                io.Int.Input('width', default=1024, min=0, display_mode=io.NumberDisplay.number),
                io.Int.Input('height', default=1024, min=0, display_mode=io.NumberDisplay.number),
                io.Combo.Input('mode', options=['AUTO', 'STRETCH', 'FILL', 'PAD'], default='AUTO'),
                io.Int.Input('R', default=255, min=0, max=255, display_mode=io.NumberDisplay.number),
                io.Int.Input('G', default=255, min=0, max=255, display_mode=io.NumberDisplay.number),
                io.Int.Input('B', default=255, min=0, max=255, display_mode=io.NumberDisplay.number),
                io.Int.Input('A', default=255, min=0, max=255, display_mode=io.NumberDisplay.number),
                io.Combo.Input('align', options=['center', 'top-left', 'top-right', 'bottom-left', 'bottom-right'], default='center'),
                io.Combo.Input('resample', options=['LANCZOS', 'NEAREST', 'BILINEAR', 'BICUBIC', 'BOX', 'HAMMING'], default='LANCZOS'),
                io.Float.Input('aspect_tolerance', default=0.01, min=0, display_mode=io.NumberDisplay.number),
            ],
            outputs=[io.Image.Output(display_name='image', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def scale_image(
            image, width, height, mode, R, G, B, A, align, resample, aspect_tolerance):

        image_pil = tensor2pil(image)
        sale_mode_dict = {
            "AUTO": ScaleMode.AUTO,
            "STRETCH": ScaleMode.STRETCH,
            "FILL": ScaleMode.FILL,
            "PAD": ScaleMode.PAD
        }

        resample_dict = {
            "LANCZOS": Image.Resampling.LANCZOS,
            "NEAREST": Image.Resampling.NEAREST,
            "BILINEAR": Image.Resampling.BILINEAR,
            "BICUBIC": Image.Resampling.BICUBIC,
            "BOX": Image.Resampling.BOX,
            "HAMMING": Image.Resampling.HAMMING
        }

        scale_img = scale_image(
            image_pil,
            (width, height),
            background=(R, G, B, A),
            mode=sale_mode_dict[mode],
            align=align,
            resample=resample_dict[resample],
            aspect_tolerance=aspect_tolerance
        )
        result_img = pil2tensor(scale_img)
        return (result_img,)


    @classmethod
    async def execute(cls, **kwargs):
        return await run_eight(cls().scale_image, kwargs, ['IMAGE'], [False])


class UpscaleImage(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__UpscaleImage_0daf5dc29035d748807c7d8f', display_name='Light-Tool: Upscale Image',
            category='ComfyUI-Light-Tool/image/transform', description='',
            inputs=[
                io.Image.Input('image'),
                io.Int.Input('width', default=1024, min=0, display_mode=io.NumberDisplay.number),
                io.Int.Input('height', default=1024, min=0, display_mode=io.NumberDisplay.number),
                io.Combo.Input('mode', options=['AUTO', 'STRETCH', 'FILL', 'PAD'], default='AUTO'),
                io.Int.Input('R', default=255, min=0, max=255, display_mode=io.NumberDisplay.number),
                io.Int.Input('G', default=255, min=0, max=255, display_mode=io.NumberDisplay.number),
                io.Int.Input('B', default=255, min=0, max=255, display_mode=io.NumberDisplay.number),
                io.Int.Input('A', default=255, min=0, max=255, display_mode=io.NumberDisplay.number),
                io.Combo.Input('align', options=['center', 'top-left', 'top-right', 'bottom-left', 'bottom-right'], default='center'),
                io.Combo.Input('resample', options=['LANCZOS', 'NEAREST', 'BILINEAR', 'BICUBIC', 'BOX', 'HAMMING'], default='LANCZOS'),
                io.Float.Input('aspect_tolerance', default=0.01, min=0, display_mode=io.NumberDisplay.number),
                io.Boolean.Input('sharpen', default=True),
            ],
            outputs=[io.Image.Output(display_name='image', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def upscale_image(
            image, width, height, mode, R, G, B, A, align, resample, aspect_tolerance, sharpen):

        image_pil = tensor2pil(image)
        upsale_mode_dict = {
            "AUTO": UpscaleMode.AUTO,
            "STRETCH": UpscaleMode.STRETCH,
            "FILL": UpscaleMode.FILL,
            "PAD": UpscaleMode.PAD
        }

        resample_dict = {
            "LANCZOS": Image.Resampling.LANCZOS,
            "NEAREST": Image.Resampling.NEAREST,
            "BILINEAR": Image.Resampling.BILINEAR,
            "BICUBIC": Image.Resampling.BICUBIC,
            "BOX": Image.Resampling.BOX,
            "HAMMING": Image.Resampling.HAMMING
        }

        upscale_img = upscale_image(
            image_pil,
            (width, height),
            background=(R, G, B, A),
            mode=upsale_mode_dict[mode],
            align=align,
            resample=resample_dict[resample],
            aspect_tolerance=aspect_tolerance,
            sharpen=sharpen
        )
        result_img = pil2tensor(upscale_img)
        return (result_img,)


    @classmethod
    async def execute(cls, **kwargs):
        return await run_eight(cls().upscale_image, kwargs, ['IMAGE'], [False])


class LoadMetadataFromURL(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('assets', 'assets.import_url', 'assets.import_url.manage')

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__LoadMetadataFromURL_852a57ca4994bdfbb94df386', display_name='Light-Tool: Load Metadata From URL',
            category='ComfyUI-Light-Tool/image/ImageInfo', description='Load metadata from image',
            inputs=[
                io.String.Input('image_url'),
            ],
            outputs=[io.String.Output(display_name='metadata', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    async def load_metadata(image_url):
        return await load_url_metadata(image_url)

    @classmethod
    async def execute(cls, **kwargs):
        return await run_eight(cls().load_metadata, kwargs, ['STRING'], [False])


class SaveMetadata(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('output', 'raw')

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__SaveMetadata_2572a523d9c9956362d36425', display_name='Light-Tool: Save Metadata',
            category='ComfyUI-Light-Tool/image/ImageInfo', description='Add metadata to image',
            inputs=[
                io.Image.Input('image'),
                io.String.Input('metadata', multiline=True),
            ],
            outputs=[],
            is_input_list=False, is_output_node=True,
        )

    @staticmethod
    async def add_metadata_to_image(image, metadata):
        return await save_metadata(image, metadata)


    @classmethod
    async def execute(cls, **kwargs):
        return await run(cls().add_metadata_to_image, kwargs, [], [])


class GetImagesCount(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__GetImagesCount_12d2cf10e623fd97942be26a', display_name='Light-Tool: Get Images Count',
            category='ComfyUI-Light-Tool/image/other', description='Get images count',
            inputs=[
                io.Image.Input('image'),
            ],
            outputs=[io.AnyType.Output(display_name='count', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def get_count(image):
        return (len(image),)


    @classmethod
    async def execute(cls, **kwargs):
        return await run(cls().get_count, kwargs, ['*'], [False])


class GetSideLength(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__GetSideLength_fca8ca2373f35ffc7db755c0', display_name='Light-Tool: Get Side Length',
            category='ComfyUI-Light-Tool/image/other', description='Get longest side',
            inputs=[
                io.Image.Input('image'),
                io.Combo.Input('mode', options=['longest', 'shortest'], default='longest'),
            ],
            outputs=[io.AnyType.Output(display_name='length', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def get_side_length(image, mode):
        img = tensor2pil(image)
        width, height = img.size
        if mode == "shortest":
            length = min(width, height)
        else:
            length = max(width, height)
        return (length,)


    @classmethod
    async def execute(cls, **kwargs):
        return await run(cls().get_side_length, kwargs, ['*'], [False])


class TextReplace(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__TextReplace_d60eef3f9de89c0c1768f87b', display_name='Light-Tool: Text Replace',
            category='ComfyUI-Light-Tool/Text', description='Replace text with simple or regex patterns',
            inputs=[
                io.String.Input('text', multiline=True, placeholder='Input text to process'),
                io.String.Input('search', multiline=False, placeholder='Text to search'),
                io.String.Input('replace', multiline=False, placeholder='Replacement text'),
                io.Boolean.Input('use_regex', default=False, label_on='enabled', label_off='disabled'),
                io.Boolean.Input('case_sensitive', default=True, label_on='enabled', label_off='disabled'),
            ],
            outputs=[io.String.Output(display_name='text', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def text_replace(text, search, replace, use_regex, case_sensitive):
        import re

        if not search:
            return (text,)

        try:
            result = text
            if use_regex:
                flags = re.S | (0 if case_sensitive else re.IGNORECASE)
                match_result = re.findall(search, text, flags)
                for i in match_result:
                    result = result.replace(i, replace)
            else:
                if case_sensitive:
                    result = result.replace(search, replace)
                else:
                    pattern = re.compile(re.escape(search), re.IGNORECASE)
                    result = pattern.sub(replace, text)

            return (result,)
        except re.error as e:
            raise ValueError(f"TextReplace(Light-Tool): Invalid regex pattern: {e}")
        except Exception as e:
            raise ValueError(f"TextReplace(Light-Tool): Error during replacement: {e}")


    @classmethod
    async def execute(cls, **kwargs):
        return await run(cls().text_replace, kwargs, ['STRING'], [False])
