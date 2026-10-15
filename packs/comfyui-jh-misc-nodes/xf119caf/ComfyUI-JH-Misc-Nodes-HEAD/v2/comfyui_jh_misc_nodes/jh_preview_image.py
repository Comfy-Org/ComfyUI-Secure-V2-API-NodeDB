"""Managed temp PNG preview, preserving source quantization and IMAGE passthrough."""
import random
import numpy as np
from PIL import Image
import torch
from comfy_api.latest import io,sdk

def preflight(images):
    if not isinstance(images,torch.Tensor) or images.layout!=torch.strided or images.ndim!=4:raise ValueError('dense BHWC image required')
    b,h,w,c=images.shape
    if b>64 or max(h,w)>4096:raise ValueError('image dimensions/batch exceed bounds')
    byte_count=images.numel()*images.element_size()
    if byte_count>32*1024*1024:raise ValueError('input byte budget exceeded')
    if byte_count+images.numel()*16+b*h*w*4*8>192*1024*1024:raise ValueError('projected aggregate workspace exceeded')
    # Source indexes images[0] before looping; preserve empty-batch IndexError.
    images[0]
    for image in images:
        Image.fromarray(np.clip(255.0*image.cpu().numpy(),0,255).astype(np.uint8))

class JHPreviewImage(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=('raw','output')
    FUNCTION='execute'

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='JHPreviewImage',display_name='Preview Image',category='JH Misc Nodes',is_output_node=True,is_experimental=True,
            inputs=[io.Image.Input('images')],hidden=[io.Hidden.prompt,io.Hidden.extra_pnginfo],outputs=[io.Image.Output()])

    @classmethod
    async def execute(cls,images,filename_prefix='ComfyUI',prompt=None,extra_pnginfo=None):
        value=await images.raw()
        preflight(value)
        if not isinstance(filename_prefix,str) or len(filename_prefix.encode('utf-8'))>1024:raise ValueError('bounded logical prefix required')
        if '/' in filename_prefix or '\\' in filename_prefix or any(ord(c)<32 for c in filename_prefix) or filename_prefix in ('','.', '..'):raise ValueError('immediate logical prefix required')
        # Ephemeral prefix is intentionally per dispatch, not process/node-global.
        rng=random.Random()
        prefix=filename_prefix+'_temp_'+''.join(rng.choice('abcdefghijklmnopqrstupvxyz') for _ in range(5))
        saved=await sdk.ctx().output.save_images(images,filename_prefix=prefix,compress_level=1,save_metadata=False,folder_type='temp')
        return io.NodeOutput(images,ui=saved)
