"""Source motion algorithm retained pack-side, bounded before allocation."""
import math
import torch
from comfy_api.latest import io
from .nodes_images import ImageMotionGuider as Source

def preflight(image,move_range_x,frame_num,zoom):
 if not isinstance(image,torch.Tensor) or image.layout!=torch.strided or image.ndim!=4:
  raise ValueError('dense BHWC input required; raw permission necessary')
 b,h,w,c=image.shape
 if b>64 or max(h,w)>4096 or not 1<=c<=4:raise ValueError('batch/axes/channels bounds exceeded')
 if type(move_range_x) is not int or not -150<=move_range_x<=150:raise ValueError('motion range bounds exceeded')
 if type(frame_num) is not int or not 2<=frame_num<=150:raise ValueError('frame count bounds exceeded')
 if type(zoom) not in (int,float) or not math.isfinite(zoom) or not 0<=zoom<=.5:raise ValueError('zoom finite bounds exceeded')
 input_bytes=image.numel()*image.element_size()
 # Mirrored/zoomed work includes all input rows although the source outputs only row zero.
 output_bytes=frame_num*h*w*c*8
 if input_bytes>32*1024*1024:raise ValueError('input byte budget exceeded')
 if output_bytes>64*1024*1024 or 12*input_bytes+2*output_bytes>192*1024*1024:
  raise ValueError('frame output/workspace budget exceeded')

class ImageMotionGuiderSecure(io.ComfyNode):
 SDK_REFS=False
 SDK_PERMISSIONS=('raw',)
 FUNCTION='execute'
 @classmethod
 def define_schema(cls):
  kinds={'IMAGE':io.Image,'INT':io.Int,'FLOAT':io.Float}
  inputs=[kinds[spec[0]].Input(name,**(spec[1] if len(spec)>1 else {})) for name,spec in Source.INPUT_TYPES()['required'].items()]
  return io.Schema(node_id='ImageMotionGuider',category=Source.CATEGORY,inputs=inputs,outputs=[io.Image.Output()])
 @classmethod
 def execute(cls,**values):
  preflight(**values)
  return io.NodeOutput(*Source().guide_motion(**values))
NODE_CLASS_MAPPINGS={'ImageMotionGuider':ImageMotionGuiderSecure}
