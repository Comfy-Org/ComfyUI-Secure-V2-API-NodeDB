"""Source grid/PIL math, scoped managed UI previews instead of ambient websocket access."""
import math
import numpy as np
import torch
from PIL import Image,ImageOps
from comfy_api.latest import io,sdk
from .secure_schedules import _guard
from .secure_graphics import tensor2pil,pil2tensor
from .secure_layout import make_grid_panel

def _preflight(node_id,values):
    _guard(values)
    image=values['image']
    if not isinstance(image,torch.Tensor) or image.layout!=torch.strided or image.ndim not in (3,4):
        raise ValueError('Preview grid requires bounded dense HWC/BHWC')
    b,h,w,c=(1,*image.shape) if image.ndim==3 else tuple(image.shape)
    if b>16 or h>4096 or w>4096 or c>4:
        raise ValueError('Preview grid dimensions exceed bound')
    factor=values['rescale_factor']
    if isinstance(factor,bool) or not isinstance(factor,(int,float)) or not math.isfinite(factor) or abs(factor)>4:
        raise ValueError('Preview rescale factor exceeds bound')
    if h==1 or w==1 or c==1:h=w=max(h,w,c)
    rw=int(w*factor);rh=int(h*factor)
    if node_id=='CR Thumbnail Preview':
        count=b if image.ndim==4 else int(image.shape[0]);columns=values['max_columns']
        if type(columns) is not int or abs(columns)>256:raise ValueError('Preview columns exceed bound')
        rw+=2;rh+=2
        rows=(count-1)//columns+1 if columns else 0
        out_w=rw*min(columns,count);out_h=rh*rows
    else:
        option=values['grid_options']
        if not isinstance(option,str) or len(option.encode('utf-8'))>128:
            raise ValueError('Preview grid option text exceeds bound')
        columns=int(option[0]) if option and option[0].isdigit() else 0
        count=columns**2;out_w=rw*columns;out_h=rh*columns
    input_bytes=image.numel()*image.element_size()
    output=max(0,out_w)*max(0,out_h)*16
    repeated=abs(rw*rh)*max(1,count)*16
    if abs(out_w)>8192 or abs(out_h)>8192 or input_bytes>32*1024*1024 or output>32*1024*1024 or input_bytes+output*3+repeated>128*1024*1024:
        raise ValueError('Preview grid projected output/temporary workload exceeds bound')

def apply_resize_image(image: Image.Image, original_width, original_height, rounding_modulus, mode='scale', supersample='true', factor: int=2, width: int=1024, height: int=1024, resample='bicubic'):
    if mode == 'rescale':
        new_width, new_height = (int(original_width * factor), int(original_height * factor))
    else:
        m = rounding_modulus
        original_ratio = original_height / original_width
        height = int(width * original_ratio)
        new_width = width if width % m == 0 else width + (m - width % m)
        new_height = height if height % m == 0 else height + (m - height % m)
    resample_filters = {'nearest': 0, 'bilinear': 2, 'bicubic': 3, 'lanczos': 1}
    if supersample == 'true':
        image = image.resize((new_width * 8, new_height * 8), resample=Image.Resampling(resample_filters[resample]))
    resized_image = image.resize((new_width, new_height), resample=Image.Resampling(resample_filters[resample]))
    return resized_image

class CR_ThumbnailPreview(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw','ui')
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Thumbnail Preview',display_name='📱 CR Thumbnail Preview',category='🧩 Comfyroll Studio/👾 Graphics/📱 Template',is_output_node=True,inputs=[io.Image.Input('image'), io.Float.Input('rescale_factor', default=0.25, min=0.1, max=1.0, step=0.01), io.Int.Input('max_columns', default=5, min=0, max=256)],outputs=[io.String.Output(display_name='show_help')])

    @classmethod
    async def execute(cls, image, rescale_factor, max_columns):
        _preflight('CR Thumbnail Preview', {'image': image, 'rescale_factor': rescale_factor, 'max_columns': max_columns})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Template-Nodes#cr-thumbnail-preview'
        result_images = []
        outline_thickness = 1
        for img in image:
            pil_img = tensor2pil(img)
            original_width, original_height = pil_img.size
            rescaled_img = apply_resize_image(tensor2pil(img), original_width, original_height, 8, 'rescale', 'false', rescale_factor, 256, 'lanczos')
            outlined_img = ImageOps.expand(rescaled_img, outline_thickness, fill='black')
            result_images.append(outlined_img)
        combined_image = make_grid_panel(result_images, max_columns)
        images_out = pil2tensor(combined_image)
        preview = await sdk.ctx().ui.preview_images(await sdk.ImageRef.from_value(images_out))
        return io.NodeOutput(show_help, ui=preview)


class CR_SeamlessChecker(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw','ui')
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Seamless Checker',display_name='📱 CR Seamless Checker',category='🧩 Comfyroll Studio/👾 Graphics/📱 Template',is_output_node=True,inputs=[io.Image.Input('image'), io.Float.Input('rescale_factor', default=0.25, min=0.1, max=1.0, step=0.01), io.Combo.Input('grid_options', options=['2x2', '3x3', '4x4', '5x5', '6x6'])],outputs=[io.String.Output(display_name='show_help')])

    @classmethod
    async def execute(cls, image, rescale_factor, grid_options):
        _preflight('CR Seamless Checker', {'image': image, 'rescale_factor': rescale_factor, 'grid_options': grid_options})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Other-Nodes#cr-seamless-checker'
        outline_thickness = 0
        pil_img = tensor2pil(image)
        original_width, original_height = pil_img.size
        rescaled_img = apply_resize_image(tensor2pil(image), original_width, original_height, 8, 'rescale', 'false', rescale_factor, 256, 'lanczos')
        outlined_img = ImageOps.expand(rescaled_img, outline_thickness, fill='black')
        max_columns = int(grid_options[0])
        repeat_images = [outlined_img] * max_columns ** 2
        combined_image = make_grid_panel(repeat_images, max_columns)
        images_out = pil2tensor(combined_image)
        preview = await sdk.ctx().ui.preview_images(await sdk.ImageRef.from_value(images_out))
        return io.NodeOutput(show_help, ui=preview)


NODE_CLASS_MAPPINGS={'CR Thumbnail Preview': CR_ThumbnailPreview, 'CR Seamless Checker': CR_SeamlessChecker}
NODE_DISPLAY_NAME_MAPPINGS={'CR Thumbnail Preview': '📱 CR Thumbnail Preview', 'CR Seamless Checker': '📱 CR Seamless Checker'}

