"""Bounded source time concatenation and logistic mask; no host device recovery."""
import math
import torch
from comfy_api.latest import io
from .source_algorithm import HunyuanImageLatentToVideoLatent as Source

def _tree_bytes(value,depth=0,counter=None):
    if counter is None:counter=[0]
    counter[0]+=1
    if depth>8 or counter[0]>4096:raise ValueError('latent metadata tree bound exceeded')
    if isinstance(value,torch.Tensor):
        if value.layout!=torch.strided:raise ValueError('dense latent metadata tensors required')
        return value.numel()*value.element_size()
    if isinstance(value,str):
        size=len(value.encode('utf-8'))
        if size>64*1024:raise ValueError('latent metadata text bound exceeded')
        return size
    if value is None or type(value) in (bool,int,float):return 16
    if type(value) is dict:
        if any(type(key) is not str for key in value):raise ValueError('logical latent metadata keys required')
        return sum(_tree_bytes(key,depth+1,counter)+_tree_bytes(item,depth+1,counter) for key,item in value.items())
    if type(value) in (list,tuple):return sum(_tree_bytes(item,depth+1,counter) for item in value)
    raise ValueError('plain tensor/metadata LATENT required')

def preflight(length,latent,use_noise_mask,noise_s,noise_o,noise_w):
    if type(length) is not int or not 0<=length<=40000:raise ValueError('length bounds exceeded')
    if type(use_noise_mask) is not bool:raise ValueError('Boolean mask control required')
    for name,value,low,high in (('noise_s',noise_s,0,100),('noise_o',noise_o,-2,2),('noise_w',noise_w,0,2)):
        if type(value) not in (int,float) or not math.isfinite(value) or not low<=value<=high:raise ValueError(name+' finite bounds exceeded')
    if not isinstance(latent,dict):raise TypeError('LATENT dictionary required')
    samples=latent['samples']
    if not isinstance(samples,torch.Tensor) or samples.layout!=torch.strided or samples.ndim!=5:raise ValueError('dense five-dimensional latent samples required')
    if samples.shape[0]>64 or any(axis>4096 for axis in samples.shape[1:]):raise ValueError('latent dimensions/batch exceed bounds')
    input_bytes=_tree_bytes(latent)
    if input_bytes>32*1024*1024:raise ValueError('input byte budget exceeded')
    copies=((length-1)//4)+1
    samples_bytes=samples.numel()*samples.element_size()*copies
    # Source torch.ones uses the CPU default floating dtype, not sample dtype.
    # Eight-byte accounting covers f32 and trusted local f64 controls exactly.
    mask_bytes=samples.numel()*copies*8 if use_noise_mask else 0
    output_bytes=samples_bytes+mask_bytes
    work=input_bytes+3*samples_bytes+3*mask_bytes+samples.numel()*8+copies*256
    if output_bytes>64*1024*1024 or work>192*1024*1024:raise ValueError('whole temporal sample/mask workspace budget exceeded')

class HunyuanConvertSecure(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    FUNCTION='execute'

    @classmethod
    def define_schema(cls):
        kinds={'INT':io.Int,'LATENT':io.Latent,'BOOLEAN':io.Boolean,'FLOAT':io.Float}
        inputs=[kinds[spec[0]].Input(name,**spec[1]) for name,spec in Source.INPUT_TYPES()['required'].items()]
        return io.Schema(node_id='HunyuanImageLatentToVideoLatent',display_name='Hunyuan Image Latent To Video Latent',category=Source.CATEGORY,description=Source.DESCRIPTION,inputs=inputs,outputs=[io.Latent.Output()])

    @classmethod
    def execute(cls,length,latent,use_noise_mask,noise_s,noise_o,noise_w):
        preflight(length,latent,use_noise_mask,noise_s,noise_o,noise_w)
        return io.NodeOutput(*Source().run_node(length,latent,use_noise_mask,noise_s,noise_o,noise_w))
