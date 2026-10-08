"""Bounded tensor-only admission; original three-pass OpenCV math is unchanged."""
import math
import cv2
import numpy as np
import torch
from comfy_api.latest import io
from .nodes.transform import CSTransform

MAX_INPUT_BYTES = 32 * 1024 * 1024
MAX_PROJECTED_BYTES = 192 * 1024 * 1024

def preflight(inputs):
    spec=CSTransform.INPUT_TYPES()['required']
    for name, (kind, options) in spec.items():
        value=inputs[name]
        if kind=='BOOLEAN':
            if type(value) is not bool:raise ValueError('boolean control required')
        else:
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
                raise ValueError('finite numeric control required')
            if kind=='INT' and type(value) is not int:raise ValueError('integer control required')
            if not options['min'] <= value <= options['max']:raise ValueError('control exceeds declared bounds')
    original=CSTransform()
    values={}
    input_bytes=0
    for name in ('image','mask','canvas'):
        value=inputs.get(name)
        if value is None:continue
        if not isinstance(value,(torch.Tensor,np.ndarray)):raise ValueError('dense tensor input required')
        if isinstance(value,torch.Tensor):
            if value.layout!=torch.strided:raise ValueError('dense tensor input required')
            size=value.numel()*value.element_size()
        else:size=value.nbytes
        input_bytes+=size
        if input_bytes>MAX_INPUT_BYTES:raise ValueError('input byte budget exceeded')
        if value.ndim>4:raise ValueError('input rank budget exceeded')
        values[name]=original.to_numpy(value)
    width,height=inputs['canvas_width'],inputs['canvas_height']
    if 'canvas' in values:
        height,width=values['canvas'].shape[:2]
    projected=input_bytes
    for name in ('image','mask'):
        if name not in values:continue
        image=values[name]
        rows,cols=image.shape[:2]
        target_w,target_h=width,height
        if inputs['expand_canvas']:
            # Identical dtype/rounding/geometry to pristine; only four corners.
            corners=np.array([[0,0],[cols,0],[cols,rows],[0,rows]])
            center=np.array([inputs['pivot_x'],inputs['pivot_y']])
            matrix=cv2.getRotationMatrix2D((inputs['pivot_x'],inputs['pivot_y']),inputs['rotation'],inputs['scale'])
            transformed=cv2.transform(np.array([corners-center]),matrix[:,:2])[0]+center
            xs,ys=transformed[:,0],transformed[:,1]
            target_w=max(width,int(max(xs)-min(xs))+abs(inputs['position_x']))
            target_h=max(height,int(max(ys)-min(ys))+abs(inputs['position_y']))
        channels=1 if image.ndim==2 else image.shape[2]
        if target_w>10000 or target_h>10000:raise ValueError('projected dimension budget exceeded')
        # Expansion, three warps, tensor copy/publication and retained arrays.
        projected+=8*max(0,target_w)*max(0,target_h)*channels*image.dtype.itemsize
        if projected>MAX_PROJECTED_BYTES:raise ValueError('projected aggregate byte budget exceeded')

class CSTransformSecure(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    FUNCTION='execute'

    @classmethod
    def define_schema(cls):
        types={'INT':io.Int,'FLOAT':io.Float,'BOOLEAN':io.Boolean,'IMAGE':io.Image,'MASK':io.Mask}
        original=CSTransform.INPUT_TYPES()
        return io.Schema(node_id='CS Transform',category=CSTransform.CATEGORY,
            inputs=[types[value[0]].Input(name,**value[1]) for name,value in original['required'].items()]
                +[types[value[0]].Input(name,optional=True) for name,value in original['optional'].items()],
            outputs=[io.Image.Output(display_name='image'),io.Mask.Output(display_name='mask')])

    @classmethod
    def execute(cls,**inputs):
        preflight(inputs)
        return io.NodeOutput(*CSTransform().execute(**inputs))
