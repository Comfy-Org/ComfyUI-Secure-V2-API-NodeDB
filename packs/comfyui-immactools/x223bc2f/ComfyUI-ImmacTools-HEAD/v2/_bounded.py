"""Pack-local resource planning before raw reads; no host object recovery."""
import math
import re
import torch
from comfy_api.latest import sdk
MAX_OUTPUT = 64 * 1024 * 1024
MAX_TOTAL = 128 * 1024 * 1024
MAX_ELEMENTS = 8_388_608
MAX_SEQUENCE = 4096
SIZES = {'bool':1,'uint8':1,'int8':1,'int16':2,'uint16':2,'float16':2,'bfloat16':2,
         'int32':4,'uint32':4,'float32':4,'int64':8,'uint64':8,'float64':8,'complex64':8,'complex128':16}

def check(output, ownership, work=0):
    if output > MAX_OUTPUT or ownership > MAX_TOTAL or work > 67_108_864:
        raise ValueError('ImmacTools projected allocation/work budget exceeded')

def geometry(shape, itemsize=16):
    if type(shape) not in (list,tuple) or len(shape)>32 or any(type(v) is not int or v<0 for v in shape):
        raise TypeError('admitted dense tensor shape required')
    elements=math.prod(shape)
    if elements>MAX_ELEMENTS: raise ValueError('ImmacTools projected allocation/work budget exceeded')
    return tuple(shape),elements,elements*itemsize

async def description(value):
    if isinstance(value,sdk.Ref):
        if value.kind not in ('SIGMAS','TENSOR','IMAGE','MASK'): raise TypeError('tensor data reference required')
        info=await value.describe()
        # Bounded public diagnostic; unknown future summaries reserve 16 bytes.
        match=re.search(r'dtype=torch\.(\w+)',info.get('summary') or '')
        size=SIZES.get(match[1],16) if match else 16
        return geometry(info['shape'],size),size
    if type(value) in (int,float,bool): return geometry([],8),8
    if type(value) in (list,tuple):
        if len(value)>MAX_SEQUENCE or any(type(x) not in (int,float,bool) for x in value):
            raise TypeError('bounded flat numeric tensor-like sequence required')
        return geometry([len(value)],8),8
    raise TypeError('admitted tensor or numeric source value required')

async def raw(value):
    if isinstance(value,sdk.Ref):
        result=await (await sdk.TensorRef.from_ref(value)).raw()
        if not isinstance(result,torch.Tensor): raise TypeError('source algorithm requires a Torch tensor')
        return result
    return value

def sigma_plan(operation,descriptions,steps=None):
    n=sum(d[0][1] for d in descriptions)
    owned=sum(d[0][2] for d in descriptions)
    if operation=='resample':
        try: s=max(1,int(steps))
        except (TypeError,ValueError,OverflowError): s=1
        shape,_,_=descriptions[0][0]
        out_n=(s+1)*(math.prod(shape[1:]) if shape else 1)
        output=out_n*max(descriptions[0][1],8)
        check(output,3*owned+18*output+16*(s+1)*8+1_048_576,out_n)
    elif operation=='splice':
        output=(2*n+6)*16
        check(output,3*owned+8*output+n*16+1_048_576,n)
    else:
        output=n*16
        check(output,3*owned+5*output+1_048_576,n)

def image_plan(descriptions):
    shapes=[d[0][0] for d in descriptions]
    if any(len(s)!=4 for s in shapes):
        owned=sum(d[0][2] for d in descriptions)
        check(owned,8*owned+4_194_304)
        return
    image,reference=shapes
    output=descriptions[0][0][1]*max(descriptions[0][1],4)
    # Conservative LAB/XYZ/linear/power/stack temporaries plus both snapshots,
    # all out_frames, stack, device output and publication ownership.
    frame=max(math.prod(image[1:]),math.prod(reference[1:]))
    workspace=40*frame*8+8*65536*8
    owned=sum(d[0][2] for d in descriptions)
    check(output,3*owned+5*output+workspace,image[0]*max(frame,1)*16)

async def publish(result,kinds):
    output=[]
    for value,kind in zip(result.result,kinds):
        if isinstance(value,torch.Tensor):
            cls=sdk.ImageRef if kind=='IMAGE' else sdk.TensorRef
            output.append(await cls.from_value(value))
        else: output.append(value)
    return output
