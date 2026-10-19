from __future__ import annotations
from comfy_api.latest import io, sdk
from .._runtime import run, missing_api
from .light_tool_utils import *
from PIL.Image import Resampling


class ResizeImage(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__ResizeImage_42d06fe80c134351a696b8c7', display_name='Light-Tool: Resize Image',
            category='ComfyUI-Light-Tool/image/Resize', description='Crop an image based on its width and height',
            inputs=[
                io.Image.Input('image'),
                io.Int.Input('width', default=512, min=0, max=8192, display_mode=io.NumberDisplay.number),
                io.Int.Input('height', default=512, min=0, max=8192, display_mode=io.NumberDisplay.number),
                io.Combo.Input('resize_method', options=['LANCZOS', 'BICUBIC', 'NEAREST', 'BILINEAR'], default='LANCZOS'),
                io.Combo.Input('mode', options=['RGB', 'RGBA', 'L'], default='RGB'),
            ],
            outputs=[io.Image.Output(display_name='image', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def resize_img(image, width, height, resize_method, mode):
        image_list = []
        for img in image:
            img = tensor2pil(img).convert(mode)
            if width is None and height is None:
                raise ValueError("Either new_width or new_height must be provided.")
            elif width is not None and height is None:
                height = int((width / img.width) * img.height)
            elif height is not None and width is None:
                width = int((height / img.height) * img.width)

            method = {
                "LANCZOS": Image.LANCZOS,
                "BICUBIC": Image.BICUBIC,
                "NEAREST": Image.NEAREST,
                "BILINEAR": Image.BILINEAR
            }

            img_resized = img.resize((width, height), method[resize_method])
            result_img = pil2tensor(img_resized)
            image_list.append(result_img)

        image = torch.cat(image_list, dim=0)
        return (image,)


    @classmethod
    async def execute(cls, **kwargs):
        return await run(cls().resize_img, kwargs, ['IMAGE'], [False])


class ResizeImageV2(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__ResizeImageV2_69fee01c63d957a56237fad0', display_name='Light-Tool: Resize Image V2',
            category='ComfyUI-Light-Tool/image/Resize', description='Reduce the image by a fixed width or height',
            inputs=[
                io.Image.Input('image'),
                io.Int.Input('width', default=512, min=0, max=8192, display_mode=io.NumberDisplay.number),
                io.Int.Input('height', default=512, min=0, max=8192, display_mode=io.NumberDisplay.number),
                io.Combo.Input('base', options=['width', 'height'], default='width'),
                io.Combo.Input('resize_method', options=['LANCZOS', 'BICUBIC', 'NEAREST', 'BILINEAR'], default='LANCZOS'),
                io.Combo.Input('mode', options=['RGB', 'RGBA', 'L'], default='RGB'),
            ],
            outputs=[io.Image.Output(display_name='image', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def resize_img_v2(image, width, height, base, resize_method, mode):
        image_list = []
        for img in image:
            img = tensor2pil(img).convert(mode)

            method = {
                "LANCZOS": Resampling.LANCZOS,
                "BICUBIC": Resampling.BICUBIC,
                "NEAREST": Resampling.NEAREST,
                "BILINEAR": Resampling.BILINEAR
            }

            original_width, original_height = img.size

            if base == 'width':
                w_percent = width / float(original_width)
                new_height = int(float(original_height) * w_percent)
                resized_img = img.resize((width, new_height), method[resize_method])
            else:
                w_percent = height / float(original_height)
                new_width = int(float(original_width) * w_percent)
                resized_img = img.resize((new_width, height), method[resize_method])

            result_img = pil2tensor(resized_img)
            image_list.append(result_img)

        image = torch.cat(image_list, dim=0)
        return (image,)


    @classmethod
    async def execute(cls, **kwargs):
        return await run(cls().resize_img_v2, kwargs, ['IMAGE'], [False])


class ResizeImageByMaxSize(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__ResizeImageByMaxSize_51bdd5f11d105832fe6fe6bb', display_name='Light-Tool: Resize Image By Max Size',
            category='ComfyUI-Light-Tool/image/Resize', description='Resize the image proportionally to ensure its resolution does not exceed the specified maximum size',
            inputs=[
                io.Image.Input('image'),
                io.Int.Input('max_width', default=512, min=0, max=8192, display_mode=io.NumberDisplay.number),
                io.Int.Input('max_height', default=512, min=0, max=8192, display_mode=io.NumberDisplay.number),
                io.Combo.Input('resize_method', options=['LANCZOS', 'BICUBIC', 'NEAREST', 'BILINEAR'], default='LANCZOS'),
                io.Combo.Input('mode', options=['RGB', 'RGBA', 'L'], default='RGB'),
            ],
            outputs=[io.Image.Output(display_name='image', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def resize_img_by_max_size(image, max_width, max_height, resize_method, mode):
        image_list = []
        for img in image:
            img = tensor2pil(img).convert(mode)

            method = {
                "LANCZOS": Resampling.LANCZOS,
                "BICUBIC": Resampling.BICUBIC,
                "NEAREST": Resampling.NEAREST,
                "BILINEAR": Resampling.BILINEAR
            }

            original_width, original_height = img.size
            ratio = min(max_width / original_width, max_height / original_height)

            if ratio >= 1:
                return (pil2tensor(img),)

            new_width = int(original_width * ratio)
            new_height = int(original_height * ratio)

            resized_img = img.resize((new_width, new_height), method[resize_method])
            result_img = pil2tensor(resized_img)
            image_list.append(result_img)

        image = torch.cat(image_list, dim=0)
        return (image,)


    @classmethod
    async def execute(cls, **kwargs):
        return await run(cls().resize_img_by_max_size, kwargs, ['IMAGE'], [False])


class ResizeImageByMinSize(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__ResizeImageByMinSize_bf3ef16d215d263f60f55253', display_name='Light-Tool: Resize Image By Min Size',
            category='ComfyUI-Light-Tool/image/Resize', description='Resize the image proportionally to ensure its resolution does not fall below the specified minimum size',
            inputs=[
                io.Image.Input('image'),
                io.Int.Input('min_width', default=512, min=0, max=8192, display_mode=io.NumberDisplay.number),
                io.Int.Input('min_height', default=512, min=0, max=8192, display_mode=io.NumberDisplay.number),
                io.Combo.Input('resize_method', options=['LANCZOS', 'BICUBIC', 'NEAREST', 'BILINEAR'], default='LANCZOS'),
                io.Combo.Input('mode', options=['RGB', 'RGBA', 'L'], default='RGB'),
            ],
            outputs=[io.Image.Output(display_name='image', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def resize_img_by_min_size(image, min_width, min_height, resize_method, mode):
        image_list = []
        for img in image:
            img = tensor2pil(img).convert(mode)

            method = {
                "LANCZOS": Resampling.LANCZOS,
                "BICUBIC": Resampling.BICUBIC,
                "NEAREST": Resampling.NEAREST,
                "BILINEAR": Resampling.BILINEAR
            }

            original_width, original_height = img.size
            ratio_w = min_width / original_width
            ratio_h = min_height / original_height
            ratio = max(ratio_w, ratio_h)

            if ratio <= 1:
                return (pil2tensor(img),)

            new_width = int(original_width * ratio)
            new_height = int(original_height * ratio)

            resized_img = img.resize((new_width, new_height), method[resize_method])
            result_img = pil2tensor(resized_img)
            image_list.append(result_img)

        image = torch.cat(image_list, dim=0)
        return (image,)


    @classmethod
    async def execute(cls, **kwargs):
        return await run(cls().resize_img_by_min_size, kwargs, ['IMAGE'], [False])


class ResizeImageByRatio(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__ResizeImageByRatio_6686a047fecea49f3fcaae31', display_name='Light-Tool: Resize Image By Ratio',
            category='ComfyUI-Light-Tool/image/Resize', description='Reduce the image by a fixed width or height',
            inputs=[
                io.Image.Input('image'),
                io.Float.Input('ratio', default=0.5, min=0, display_mode=io.NumberDisplay.number),
                io.Combo.Input('resize_method', options=['LANCZOS', 'BICUBIC', 'NEAREST', 'BILINEAR'], default='LANCZOS'),
                io.Combo.Input('mode', options=['RGB', 'RGBA', 'L'], default='RGB'),
            ],
            outputs=[io.Image.Output(display_name='image', is_output_list=False)],
            is_input_list=False, is_output_node=False,
        )

    @staticmethod
    def resize_img_by_ratio(image, ratio, resize_method, mode):
        image_list = []
        for img in image:
            img = tensor2pil(img).convert(mode)

            method = {
                "LANCZOS": Resampling.LANCZOS,
                "BICUBIC": Resampling.BICUBIC,
                "NEAREST": Resampling.NEAREST,
                "BILINEAR": Resampling.BILINEAR
            }

            original_width, original_height = img.size
            new_width = int(original_width * ratio)
            new_height = int(original_height * ratio)
            resized_img = img.resize((new_width, new_height), method[resize_method])
            result_img = pil2tensor(resized_img)
            image_list.append(result_img)

        image = torch.cat(image_list, dim=0)
        return (image,)


    @classmethod
    async def execute(cls, **kwargs):
        return await run(cls().resize_img_by_ratio, kwargs, ['IMAGE'], [False])


class AspectRatioPadder(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Light_Tool__AspectRatioPadder_a000886509bb9882ba15dd80', display_name='Light-Tool: Ratio Padder',
            category='ComfyUI-Light-Tool/image/Resize', description='Resize image to fit target ratio and pad with white background.',
            inputs=[
                io.Image.Input('image'),
                io.Combo.Input('target_ratio', options=['1:1', '9:16', '16:9', '4:3', '3:2', '2:3'], default='1:1'),
                io.String.Input('custom_ratio', default=''),
                io.Int.Input('base_size', default=1024, min=64, max=4096, step=8, display_mode=io.NumberDisplay.number),
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
    def pad_image(image, target_ratio, custom_ratio, base_size, color_hex, use_hex, R, G, B):
        ratio_map = {
            "1:1": 1.0,
            "9:16": 9.0 / 16.0,
            "16:9": 16.0 / 9.0,
            "4:3": 4.0 / 3.0,
            "3:2": 3.0 / 2.0,
            "2:3": 2.0 / 3.0,
            "None": None
        }

        target_w_h_ratio = ratio_map.get(custom_ratio or target_ratio)
        if not target_w_h_ratio:
            out_images = torch.cat([image], dim=0)
            return (out_images,)

        image_list = []

        for img in image:
            pil_img = tensor2pil(img)
            orig_w, orig_h = pil_img.size
            orig_ratio = orig_w / orig_h

            if target_w_h_ratio >= 1.0:  # horizontal image (16:9, 4:3, 3:2)
                target_w = base_size
                target_h = int(base_size / target_w_h_ratio)
            else:  # vertical image or Square Map (9:16, 2:3, 1:1)
                target_h = base_size
                target_w = int(base_size * target_w_h_ratio)

            target_w = (target_w // 8) * 8
            target_h = (target_h // 8) * 8

            if use_hex:
                rgb_background_color = hex_to_rgb(color_hex)
            else:
                rgb_background_color = (R, G, B)
            new_image = Image.new("RGB", (target_w, target_h), rgb_background_color)

            if orig_ratio > target_w_h_ratio:
                scale_ratio = target_w / orig_w
            else:
                scale_ratio = target_h / orig_h

            resize_w = int(orig_w * scale_ratio)
            resize_h = int(orig_h * scale_ratio)

            resize_w = min(resize_w, target_w)
            resize_h = min(resize_h, target_h)

            resized_img = pil_img.resize((resize_w, resize_h), resample=Image.Resampling.LANCZOS)

            paste_x = (target_w - resize_w) // 2
            paste_y = (target_h - resize_h) // 2

            new_image.paste(resized_img, (paste_x, paste_y))

            result_tensor = pil2tensor(new_image)
            image_list.append(result_tensor)

        out_images = torch.cat(image_list, dim=0)
        return (out_images,)


    @classmethod
    async def execute(cls, **kwargs):
        return await run(cls().pad_image, kwargs, ['IMAGE'], [False])
