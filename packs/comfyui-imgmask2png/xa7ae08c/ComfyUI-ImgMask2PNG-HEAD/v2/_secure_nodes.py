"""Bounded tensor admission; original Pillow paste/Lanczos math is unchanged."""
import torch
from comfy_api.latest import io
from .imgmask2png import ImageMask2PNG

MAX_INPUT_BYTES=32*1024*1024
MAX_OUTPUT_BYTES=64*1024*1024
MAX_WORK_BYTES=192*1024*1024

def preflight(mask,image):
    for name,value,rank in (('image',image,4),('mask',mask,3)):
        if not isinstance(value,torch.Tensor) or value.layout!=torch.strided:raise ValueError('dense '+name+' tensor required')
        if value.ndim!=rank:raise ValueError('BHWC image/BHW mask required')
        if value.shape[0]>64 or any(axis>4096 for axis in value.shape[1:3]):raise ValueError('dimensions/batch exceed bounds')
    input_bytes=sum(value.numel()*value.element_size() for value in (mask,image))
    if input_bytes>MAX_INPUT_BYTES:raise ValueError('input byte budget exceeded')
    batch=min(mask.shape[0],image.shape[0]);height,columns=image.shape[1:3]
    output_bytes=batch*height*columns*4*4
    if output_bytes>MAX_OUTPUT_BYTES:raise ValueError('output byte budget exceeded')
    # Includes both clipping/multiply arrays, input uint8 copies, PIL RGBA/mask,
    # every retained float32 output and the final concatenated output.
    work=input_bytes+sum(value.numel()*16 for value in (mask,image))+output_bytes*3+height*columns*32
    if work>MAX_WORK_BYTES:raise ValueError('projected aggregate workspace exceeded')

class ImageMaskSecure(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    FUNCTION='execute'

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='ImageMask2PNG',display_name='🌊ImageMask2PNG',category=ImageMask2PNG.CATEGORY,
            inputs=[io.Mask.Input('mask'),io.Image.Input('image')],outputs=[io.Image.Output(display_name='image')])

    @classmethod
    def execute(cls,mask,image):
        preflight(mask,image)
        return io.NodeOutput(*ImageMask2PNG().remove_background(mask,image))
