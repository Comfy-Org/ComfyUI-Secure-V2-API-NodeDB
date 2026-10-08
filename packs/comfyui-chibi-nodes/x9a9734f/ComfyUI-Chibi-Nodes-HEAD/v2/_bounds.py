"""Pack-side allocation/work preflight, not a host profile or GPU grant."""
import math
import torch

TEXT_BYTES=1024*1024
TENSOR_BYTES=64*1024*1024
WORK_BYTES=192*1024*1024
MAX_PIXELS=4*1024*1024

def text(value):
    if not isinstance(value,str):raise TypeError('text must be a string')
    if len(value.encode('utf-8'))>TEXT_BYTES:raise ValueError('text byte budget exceeded')
    return value

def tensor(value):
    if not isinstance(value,torch.Tensor) or value.layout!=torch.strided:
        raise TypeError('dense tensor required')
    size=max(value.numel()*value.element_size(),value.untyped_storage().nbytes())
    if size>TENSOR_BYTES:raise ValueError('tensor byte budget exceeded')
    return size

def image_work(value,width,height):
    size=0 if value is None else tensor(value)
    if isinstance(width,bool) or isinstance(height,bool):raise TypeError('integer dimensions required')
    if width>32768 or height>32768 or width*height>MAX_PIXELS:
        raise ValueError('projected image pixel budget exceeded')
    if size+max(width,0)*max(height,0)*40>WORK_BYTES:
        raise ValueError('image workspace byte budget exceeded')

def latent_work(batch,height,width):
    if any(isinstance(x,bool) or not isinstance(x,int) for x in (batch,height,width)):
        raise TypeError('integer latent dimensions required')
    projected=max(batch,0)*4*max(height//8,0)*max(width//8,0)*torch.empty(()).element_size()
    if projected>TENSOR_BYTES:raise ValueError('latent allocation byte budget exceeded')
