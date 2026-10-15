"""Wan image sizing with bounded values and retained native Core resize."""
import numpy as np
from comfy_api.latest import io
from .secure_tensor_nodes import _bound_payload
from ._wan_resize import common_upscale

VAE_STRIDE=(4,8,8)
PATCH_SIZE=(1,2,2)
MAX_OUTPUT_PIXELS=8388608


class WanVideoImageResizeToClosest(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoImageResizeToClosest',display_name='WanVideo Image Resize To Closest',
            category='WanVideoWrapper',
            description='Resizes image to the closest supported resolution based on aspect ratio and max pixels, according to the original code',
            inputs=[io.Image.Input('image',tooltip='Image to resize'),
                io.Int.Input('generation_width',default=832,min=64,max=8096,step=8,tooltip='Width of the image to encode'),
                io.Int.Input('generation_height',default=480,min=64,max=8096,step=8,tooltip='Height of the image to encode'),
                io.Combo.Input('aspect_ratio_preservation',options=['keep_input','stretch_to_new','crop_to_new'])],
            outputs=[io.Image.Output(display_name='image'),io.Int.Output(display_name='width'),io.Int.Output(display_name='height')])

    @classmethod
    async def execute(cls,image,generation_width,generation_height,aspect_ratio_preservation):
        _bound_payload(image)
        batch,H,W,_=image.shape
        max_area=generation_width*generation_height
        crop='disabled'
        if aspect_ratio_preservation=='keep_input':
            aspect_ratio=H/W
        elif aspect_ratio_preservation=='stretch_to_new' or aspect_ratio_preservation=='crop_to_new':
            aspect_ratio=generation_height/generation_width
            if aspect_ratio_preservation=='crop_to_new':crop='center'
        lat_h=round(np.sqrt(max_area*aspect_ratio)//VAE_STRIDE[1]//PATCH_SIZE[1]*PATCH_SIZE[1])
        lat_w=round(np.sqrt(max_area/aspect_ratio)//VAE_STRIDE[2]//PATCH_SIZE[2]*PATCH_SIZE[2])
        h=lat_h*VAE_STRIDE[1]
        w=lat_w*VAE_STRIDE[2]
        if batch*h*w>MAX_OUTPUT_PIXELS:
            raise ValueError('Wan projected image output exceeds 8388608 pixels')
        resized=common_upscale(image.movedim(-1,1),w,h,'lanczos',crop).movedim(1,-1)
        return io.NodeOutput(resized,w,h)


NODE_CLASS_MAPPINGS={'WanVideoImageResizeToClosest':WanVideoImageResizeToClosest}
