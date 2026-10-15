"""Bounded existing NLF pose raster math; no NLF model or detector inference."""
import math
import numpy as np
import torch
from comfy_api.latest import io
from .MTV.draw_pose import get_control_conditions
from .secure_tensor_nodes import _bound_payload, MAX_PAYLOAD_BYTES, MAX_TENSOR_ELEMENTS

def _preflight(poses,width,height,stick_width,point_radius):
    _bound_payload(poses)
    if isinstance(width,(int,float)) and (not math.isfinite(width) or abs(width)>2048):
        raise ValueError('Wan NLF raster width exceeds2048')
    if isinstance(height,(int,float)) and (not math.isfinite(height) or abs(height)>2048):
        raise ValueError('Wan NLF raster height exceeds2048')
    for value in (stick_width,point_radius):
        if isinstance(value,(int,float)) and (not math.isfinite(value) or abs(value)>1000):
            raise ValueError('Wan NLF raster radius/stick exceeds bounded work')
    if isinstance(poses,(list,tuple,dict,np.ndarray,torch.Tensor)):
        if len(poses)>512:
            raise ValueError('Wan NLF raster exceeds512 frames')
        draw_calls=0
        for value in poses:
            if isinstance(value,torch.Tensor) and (value.device.type!='cpu' or value.layout!=torch.strided):
                raise ValueError('Wan NLF raster requires dense CPU coordinates')
            if isinstance(value,(np.ndarray,torch.Tensor)) and value.ndim>=2 and value.shape[-2]>1024:
                raise ValueError('Wan NLF raster exceeds1024 joints/frame')
            if isinstance(value,(np.ndarray,torch.Tensor)) and value.ndim>=2:
                draw_calls+=int(value.shape[-2])+24
        if draw_calls>250000:
            raise ValueError('Wan NLF projected drawing exceeds250000 operations')
        if isinstance(width,int) and isinstance(height,int):
            elements=len(poses)*max(0,width)*max(0,height)*3
            if elements>MAX_TENSOR_ELEMENTS or elements*32>MAX_PAYLOAD_BYTES:
                raise ValueError('Wan NLF projected canvas/stack exceeds tensor/64MiB bounds')

class DrawNLFPoses(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='DrawNLFPoses',display_name='Draw NLF Poses',category='WanVideoWrapper',
            inputs=[io.Custom('NLFPRED').Input('poses',tooltip='Input poses for the model'),
                io.Int.Input('width',default=512),io.Int.Input('height',default=512),
                io.Float.Input('stick_width',default=4.0,min=0.0,max=1000.0,step=0.01,optional=True,tooltip='Stick width multiplier'),
                io.Int.Input('point_radius',default=5,min=1,max=10,step=1,optional=True,tooltip='Point radius for drawing the pose'),
                io.Combo.Input('style',options=['original','scail'],default='original',optional=True,tooltip='style of the pose drawing')],
            outputs=[io.Image.Output(display_name='image')])
    @classmethod
    def execute(cls,poses,width,height,stick_width=1.0,point_radius=2,style='original'):
        _bound_payload(poses)
        if isinstance(poses, dict):
            pose_input = poses['joints3d_nonparam'][0] if 'joints3d_nonparam' in poses else poses
        else:
            pose_input = poses
        _preflight(pose_input,width,height,stick_width,point_radius)
        control_conditions = get_control_conditions(pose_input,height,width,stick_width=stick_width,point_radius=point_radius,style=style)
        return io.NodeOutput(control_conditions)

NODE_CLASS_MAPPINGS={'DrawNLFPoses':DrawNLFPoses}
