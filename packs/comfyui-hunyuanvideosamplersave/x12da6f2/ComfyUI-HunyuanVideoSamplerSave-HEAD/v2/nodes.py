"""Typed canonical sampling/resize and bounded local motion/zero construction."""
import json,math
from pathlib import Path
import torch
from comfy_api.latest import io,sdk
from ._motion import ImageMotionInfluance as MotionSource
DATA=json.loads((Path(__file__).parent/'schema-data.json').read_text())
DATA['HunyuanVideoSamplerSave']['inputs']['required']['seed'][1]['max']=(1<<64)-1
DISPLAY={'HunyuanVideoSamplerSave':'Hunyuan Video Sampler Save','ResizeImageForHunyuan':'Resize Image For Hunyuan','EmptyVideoLatentForHunyuan':'Empty Video Latent For Hunyuan','ImageMotionInfluance':'Image Motion Influence'}
KINDS={'MODEL':io.Model,'CONDITIONING':io.Conditioning,'LATENT':io.Latent,'IMAGE':io.Image,'INT':io.Int,'FLOAT':io.Float}
def schema(node):
 data=DATA[node];inputs=[]
 for name,spec in data['inputs']['required'].items():
  if isinstance(spec[0],list):inputs.append(io.Combo.Input(name,options=spec[0]))
  else:inputs.append(KINDS[spec[0]].Input(name,**(spec[1] if len(spec)>1 else {})))
 return io.Schema(node_id=node,display_name=DISPLAY[node],category=data['category'],inputs=inputs,outputs=[KINDS[k].Output() for k in data['return_types']])
class HunyuanVideoSamplerSave(io.ComfyNode):
 SDK_REFS=True
 SDK_PERMISSIONS=('sample',)
 FUNCTION='execute'
 @classmethod
 def define_schema(cls):return schema('HunyuanVideoSamplerSave')
 @classmethod
 async def execute(cls,model,video_latents,positive,negative,seed,steps,cfg,sampler_name,scheduler,denoise):
  if not isinstance(model,sdk.ModelRef) or not isinstance(video_latents,sdk.LatentRef):raise TypeError('typed MODEL and LATENT required')
  return io.NodeOutput(await sdk.ctx().sample(video_latents,steps,model=model,positive=positive,negative=negative,seed=seed,cfg=cfg,sampler_name=sampler_name,scheduler=scheduler,denoise=denoise))

class ResizeImageForHunyuan(io.ComfyNode):
 SDK_REFS=True
 SDK_PERMISSIONS=('inspect',)
 FUNCTION='execute'
 @classmethod
 def define_schema(cls):return schema('ResizeImageForHunyuan')
 @classmethod
 async def execute(cls,image,size_preset,upscale_method,crop):
  if not isinstance(size_preset,str) or len(size_preset)>128:raise ValueError('bounded preset required')
  size_part=size_preset.split(' ')[1].strip('()')
  width,height=map(int,size_part.split('x'))
  if min(width,height)<=0 or max(width,height)>2048:raise ValueError('projected resize axes exceeded')
  if upscale_method not in DATA['ResizeImageForHunyuan']['inputs']['required']['upscale_method'][0] or crop not in ('disabled','center'):raise ValueError('closed resize method/crop required')
  description=await image.describe()
  shape=description.get('shape')
  if not isinstance(shape,list) or len(shape)!=4 or any(type(n) is not int for n in shape):raise ValueError('bounded BHWC tensor shape required')
  batch,input_height,input_width,channels=shape
  if not 1<=batch<=64 or not 1<=min(input_width,input_height) or max(input_width,input_height)>4096 or not 1<=channels<=4:raise ValueError('resize input dimensions/batch/channels exceed bounds')
  # No summary-string dtype parsing. Sixteen bytes covers every admitted
  # dense Torch scalar, including complex128, before native type errors.
  input_bytes=math.prod(shape)*16
  output_bytes=batch*width*height*channels*16
  if input_bytes>32*1024*1024 or output_bytes>64*1024*1024 or input_bytes+3*output_bytes>192*1024*1024:raise ValueError('aggregate resize input/output/workspace budget exceeded')
  h,w=await image.spatial_shape()
  print(f'Resizing image from {w}x{h} to {width}x{height} ({size_preset.split()[0]} aspect ratio)')
  return io.NodeOutput(await image.resize(width,height,method=upscale_method,crop=crop))

class EmptyVideoLatentForHunyuan(io.ComfyNode):
 SDK_REFS=False
 SDK_PERMISSIONS=('raw',)
 FUNCTION='execute'
 @classmethod
 def define_schema(cls):return schema('EmptyVideoLatentForHunyuan')
 @classmethod
 def execute(cls,resolution,length,batch_size=1):
  if not isinstance(resolution,str) or len(resolution)>128:raise ValueError('bounded resolution required')
  dimensions=resolution.split(' ')[0]
  width,height=map(int,dimensions.split('x'))
  width=(width//16)*16;height=(height//16)*16
  if type(length) is not int or type(batch_size) is not int:raise TypeError('integer length/batch required')
  if not 1<=length<=16384 or not 1<=batch_size<=4096 or not 0<=min(width,height) or max(width,height)>4096:raise ValueError('latent dimensions/length/batch bounds exceeded')
  shape=[batch_size,16,((length-1)//4)+1,height//8,width//8]
  if math.prod(shape)*8>64*1024*1024:raise ValueError('projected latent byte budget exceeded')
  # Approved CPU-local normalization; no intermediate-device escape.
  return io.NodeOutput({'samples':torch.zeros(shape)})

class ImageMotionInfluance(io.ComfyNode):
 SDK_REFS=False
 SDK_PERMISSIONS=('raw',)
 FUNCTION='execute'
 @classmethod
 def define_schema(cls):return schema('ImageMotionInfluance')
 @classmethod
 def execute(cls,image,move_range_x,frame_num,zoom):
  if not isinstance(image,torch.Tensor) or image.ndim!=4 or image.layout!=torch.strided:raise ValueError('dense BHWC and raw permission required')
  b,h,w,c=image.shape
  if b>64 or max(h,w)>4096 or not 1<=c<=4:raise ValueError('image dimensions exceed bounds')
  if type(move_range_x) is not int or not -150<=move_range_x<=150 or type(frame_num) is not int or not 2<=frame_num<=500:raise ValueError('motion/frame bounds exceeded')
  if type(zoom) not in (int,float) or not math.isfinite(zoom) or not 0<=zoom<=.5:raise ValueError('finite zoom bounds required')
  input_bytes=image.numel()*image.element_size();output_bytes=frame_num*h*w*c*8
  if input_bytes>32*1024*1024 or output_bytes>64*1024*1024 or 6*input_bytes+2*output_bytes>192*1024*1024:raise ValueError('projected motion input/output/workspace budget exceeded')
  return io.NodeOutput(*MotionSource().guide_motion(image,move_range_x,frame_num,zoom))

NODE_CLASS_MAPPINGS={name:globals()[name] for name in DISPLAY}
NODE_DISPLAY_NAME_MAPPINGS=DISPLAY
