"""Bounded five-dimensional zero latent allocation, never host device recovery."""
import math
from comfy_api.latest import io
from . import nodes_hunyuan as source

MAX_OUTPUT_BYTES=64*1024*1024
MAX_PROJECTED_BYTES=192*1024*1024

def preflight(resolution,batch_size,length=None):
    if not isinstance(resolution,str) or len(resolution.encode('utf-8'))>1024:raise ValueError('bounded resolution string required')
    # Exact source parsing first: malformed strings retain native error types.
    width,height=map(int,resolution.split(' ')[0].split('x'))
    width=(width//16)*16;height=(height//16)*16
    if type(batch_size) is not int or not 0<=batch_size<=4096:raise ValueError('batch bound exceeded')
    if width<0 or height<0:raise ValueError('negative dimensions are not allowed')
    if width>16384 or height>16384:raise ValueError('projected dimension bound exceeded')
    frames=1;channels=4
    if length is not None:
        if type(length) is not int or not 0<=length<=16384:raise ValueError('length bound exceeded')
        frames=((length-1)//4)+1;channels=16
    # Eight-byte maximum admitted floating construction dtype. Default is f32;
    # conservative accounting does not modify the source's Torch dtype policy.
    output_bytes=math.prod((batch_size,channels,frames,height//8,width//8))*8
    if output_bytes>MAX_OUTPUT_BYTES or 3*output_bytes>MAX_PROJECTED_BYTES:
        raise ValueError('whole latent allocation/transport budget exceeded')

def make_node(node_id,original):
    class SecureEmpty(io.ComfyNode):
        SDK_REFS=False
        SDK_PERMISSIONS=('raw',)
        FUNCTION='execute'

        @classmethod
        def define_schema(cls):
            schema=original.INPUT_TYPES()['required']
            return io.Schema(node_id=node_id,category=original.CATEGORY,
                inputs=[io.Combo.Input(name,options=spec[0]) if isinstance(spec[0],list) else io.Int.Input(name,**spec[1]) for name,spec in schema.items()],
                outputs=[io.Latent.Output()])

        @classmethod
        def execute(cls,resolution,batch_size=1,**inputs):
            if original is source.EmptyHunyuanLatentForVideo:
                if 'length' not in inputs:raise TypeError('missing required length')
                preflight(resolution,batch_size,inputs['length'])
            else:preflight(resolution,batch_size)
            return io.NodeOutput(*original().generate(resolution,batch_size=batch_size,**inputs))
    SecureEmpty.__name__=original.__name__+'Secure'
    SecureEmpty.__qualname__=SecureEmpty.__name__;SecureEmpty.__module__=__name__
    return SecureEmpty

NODE_CLASS_MAPPINGS={}
for node_id,original in source.NODE_CLASS_MAPPINGS.items():
    node=make_node(node_id,original);globals()[node.__name__]=node;NODE_CLASS_MAPPINGS[node_id]=node
