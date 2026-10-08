"""Bounded image-only admission; original strip/pixel algorithm stays intact."""
import torch
from comfy_api.latest import io
from .Animated_optical_illusions_Zho import AOI_Processing_Zho

MAX_INPUT_BYTES=32*1024*1024
MAX_WORK_BYTES=192*1024*1024
MAX_PIXELS=1024*1024

def preflight(images,width):
    if type(width) is not int or not 1<=width<=100:raise ValueError('width must be an integer in declared bounds')
    if not isinstance(images,torch.Tensor) or images.layout!=torch.strided:raise ValueError('dense image tensor required')
    if images.ndim!=4:raise ValueError('BHWC image tensor required')
    batch,height,columns,channels=images.shape
    if batch>64 or height>4096 or columns>4096:raise ValueError('image dimensions/batch exceed bounds')
    input_bytes=images.numel()*images.element_size()
    if input_bytes>MAX_INPUT_BYTES:raise ValueError('input byte budget exceeded')
    if height*columns>MAX_PIXELS:raise ValueError('output pixel budget exceeded')
    # All converted uint8 frames plus clipping arrays and output conversions;
    # original Python RGBA tuple list is explicitly included in this estimate.
    work=input_bytes+batch*height*columns*channels*12+height*columns*192
    if work>MAX_WORK_BYTES:raise ValueError('projected aggregate workspace exceeded')

class AOISecure(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    FUNCTION='execute'

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='AOI_Processing_Zho',display_name='AOI_Processing_Zho',category=AOI_Processing_Zho.CATEGORY,
            inputs=[io.Image.Input('images'),io.Int.Input('width',**AOI_Processing_Zho.INPUT_TYPES()['required']['width'][1])],
            outputs=[io.Image.Output(display_name='image'),io.Image.Output(display_name='mask')])

    @classmethod
    def execute(cls,images,width):
        preflight(images,width)
        return io.NodeOutput(*AOI_Processing_Zho().aoi_processing(images,width))
