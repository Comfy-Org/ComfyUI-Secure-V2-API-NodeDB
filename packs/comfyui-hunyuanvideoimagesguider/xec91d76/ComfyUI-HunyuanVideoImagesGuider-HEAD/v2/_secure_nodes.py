"""Bounded pack-side motion pixels; no host modules or placement authority."""
import math
import torch
from comfy_api.latest import io
from .image_motion_guider import ImageMotionGuider as Source

def preflight(image,move_range_x,move_range_y,zoom,frame_num,resize_mode,target_width,target_height,center_crop):
    if not isinstance(image,torch.Tensor) or image.layout!=torch.strided or image.ndim!=4:
        raise ValueError('dense BHWC input required; raw permission is necessary')
    b,h,w,c=image.shape
    if b>64 or max(h,w)>4096 or not 1<=c<=4:raise ValueError('image dimensions/batch/channels exceed bounds')
    for label,value,low,high in (('move_range_x',move_range_x,-1,1),('move_range_y',move_range_y,-1,1),('zoom',zoom,0,.5)):
        if type(value) not in (int,float) or not math.isfinite(value) or not low<=value<=high:raise ValueError(label+' finite bounds exceeded')
    if type(frame_num) is not int or not 2<=frame_num<=150:raise ValueError('frame count bounds exceeded')
    if resize_mode not in ('disabled','custom','keep_ratio'):raise ValueError('closed resize mode required')
    if type(center_crop) is not bool:raise ValueError('Boolean crop control required')
    for value in (target_width,target_height):
        if type(value) is not int or not 64<=value<=2048:raise ValueError('target bounds exceeded')
    input_bytes=image.numel()*image.element_size()
    if input_bytes>32*1024*1024:raise ValueError('input byte budget exceeded')
    rw,rh=w,h
    if resize_mode!='disabled':
        rw=target_width
        # Preserve native zero-width division and zero-height interpolation errors.
        rh=int(target_width*h/w) if resize_mode=='keep_ratio' else target_height
    if max(rw,rh)>4096:raise ValueError('projected resized axes exceed bounds')
    resized_bytes=b*rh*rw*c*image.element_size()
    oh,ow=(min(rh,rw),min(rh,rw)) if center_crop else (rh,rw)
    # Source canvas uses CPU default float, not incoming dtype or batch size.
    # Eight-byte accounting also covers trusted local float64 default controls.
    output_bytes=frame_num*oh*ow*c*8
    workspace=input_bytes+12*resized_bytes+2*output_bytes
    if output_bytes>64*1024*1024 or workspace>192*1024*1024:
        raise ValueError('aggregate frame output/workspace budget exceeded')

class ImageMotionGuiderSecure(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    FUNCTION='execute'

    @classmethod
    def define_schema(cls):
        kinds={'IMAGE':io.Image,'FLOAT':io.Float,'INT':io.Int,'BOOLEAN':io.Boolean}
        inputs=[]
        for name,spec in Source.INPUT_TYPES()['required'].items():
            if isinstance(spec[0],list):inputs.append(io.Combo.Input(name,options=spec[0]))
            else:inputs.append(kinds[spec[0]].Input(name,**(spec[1] if len(spec)>1 else {})))
        return io.Schema(node_id='Hunyuan Video Image To Guider',category=Source.CATEGORY,inputs=inputs,outputs=[io.Image.Output()])

    @classmethod
    def execute(cls,**values):
        preflight(**values)
        return io.NodeOutput(*Source().guide_motion(**values))

NODE_CLASS_MAPPINGS={'Hunyuan Video Image To Guider':ImageMotionGuiderSecure}
