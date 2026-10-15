"""Projected dense CPU workload admission before raw tensor reads."""
import math
import torch
from comfy_api.latest import sdk
MAX_INPUT=32*1024*1024
MAX_OUTPUT=32*1024*1024
MAX_TOTAL=256*1024*1024
MAX_WORK=1_000_000_000
MAX_FONT=2*1024*1024

def geometry(shape):
    if type(shape) not in (list,tuple) or len(shape)>32 or any(type(x) is not int or x<0 for x in shape):
        raise TypeError('Post Processing requires a bounded dense shape')
    count=math.prod(shape)
    if count*16>MAX_INPUT: raise ValueError('Post Processing input byte budget exceeded')
    return tuple(shape),count

def broadcast(a,b):
    result=[]
    for i in range(1,max(len(a),len(b))+1):
        x=a[-i] if i<=len(a) else 1
        y=b[-i] if i<=len(b) else 1
        if x!=y and x!=1 and y!=1: return None
        result.append(y if x==1 else x)
    return tuple(reversed(result))

def plan(node,shapes,values):
    parsed=[geometry(s) for s in shapes]
    counts=[n for _,n in parsed]
    owned=sum(n*16 for n in counts)
    largest=max(counts,default=0)
    output=largest*16
    first=parsed[0][0] if parsed else ()
    frame=math.prod(first[-3:-1]) if len(first)>=3 else largest
    work=largest*64
    workspace=largest*16*12+4_194_304
    # Zero/few-channel inputs can still cause BHW or RGB allocations before a
    # native channel error. Meter these dimensions even when input numel is 0.
    for shape,_ in parsed:
        if len(shape)==4:
            _,n=geometry((*shape[:3],max(shape[3],3)))
            output=max(output,n*16)
            workspace=max(workspace,n*16*12+4_194_304)
    if len(parsed)>1:
        shape=broadcast(parsed[0][0],parsed[1][0])
        if shape is not None:
            _,n=geometry(shape)
            output=max(output,n*16)
            workspace=max(workspace,n*16*12+4_194_304)
    if node=='Blend' and len(parsed)==2 and all(len(p[0])==4 for p in parsed):
        a,b=parsed[0][0],parsed[1][0]
        resized=(b[0],a[1],a[2],b[3])
        _,n=geometry(resized)
        shape=broadcast(a,resized)
        if shape is not None:
            _,n_out=geometry(shape)
            n=max(n,n_out)
        output=max(output,n*16)
        workspace=max(workspace,n*16*12+4_194_304)
    if node=='Vignette' and len(first)==4 and values['vignette']!=0:
        # Native meshgrid is (W,H), retained rather than repairing nonsquares.
        shape=broadcast(first,(1,first[2],first[1],1))
        if shape is not None:
            _,n=geometry(shape)
            output=max(output,n*16)
            workspace=max(workspace,n*16*12+4_194_304)
    radius_name={'Blur':'blur_radius','Glow':'blur_radius','PencilSketch':'blur_radius',
                 'Sharpen':'sharpen_radius','KuwaharaBlur':'blur_radius'}.get(node)
    if radius_name:
        radius=values[radius_name]
        if type(radius) is not int or abs(radius)>511:
            raise ValueError('Post Processing kernel workload exceeded')
        kernel=2*max(0,radius)+1
        work=max(work,largest*kernel*kernel*2)
        workspace+=kernel*kernel*64
    if node=='FilmGrain':
        # Four Perlin octaves: concurrent float64 grids/int64 gradients, noise,
        # interpolation/color temporaries plus snapshot/publication owners.
        workspace=frame*448+largest*32+4_194_304
        work=largest*256
    if node=='PixelSort':
        # Python span tuples/NumPy views and sorting pointer arrays.
        workspace=frame*448+largest*64+4_194_304
        work=largest*max(1,max(first,default=1).bit_length())*16
    if node=='AsciiArt':
        for key in ('char_size','font_size'):
            if type(values[key]) is not int or not 0<=values[key]<=64:
                raise ValueError('Post Processing font/glyph workload exceeded')
        workspace+=MAX_FONT*4+frame*128
    if output>MAX_OUTPUT or owned*4+output*3+workspace>MAX_TOTAL or work>MAX_WORK:
        raise ValueError('Post Processing projected allocation/work budget exceeded')
    return {'input_bytes':owned,'output_bytes':output,'workspace_bytes':workspace,'work':work}

async def describe(value):
    if not isinstance(value,sdk.Ref) or value.kind not in ('IMAGE','MASK','TENSOR'):
        raise TypeError('Post Processing requires a public tensor-data reference')
    return (await value.describe())['shape']

async def raw(value):
    tensor=await (await sdk.TensorRef.from_ref(value)).raw()
    if type(tensor) is not torch.Tensor or tensor.layout!=torch.strided or tensor.is_nested:
        raise TypeError('Post Processing requires a plain dense Torch tensor')
    if tensor.device.type!='cpu' or not tensor.is_contiguous() or tensor.requires_grad:
        raise ValueError('Post Processing admitted profile is contiguous CPU data without autograd')
    if tensor.dtype not in (torch.float16,torch.bfloat16,torch.float32,torch.float64,
                            torch.uint8,torch.int8,torch.int16,torch.int32,torch.int64,torch.bool):
        raise TypeError('Post Processing dtype is outside the admitted profile')
    geometry(tuple(tensor.shape))
    return tensor

async def font_bytes():
    assets=sdk.ctx().assets
    ref=await assets.resolve('input','post-processing/arial.ttf')
    size=await assets.size(ref)
    if type(size) is not int or not 0<=size<=MAX_FONT:
        raise ValueError('Post Processing Arial data byte budget exceeded')
    data=await assets.read_range(ref,0,size)
    tail=await assets.read_range(ref,size,1)
    if type(data) is not bytes or len(data)!=size or tail or await assets.size(ref)!=size:
        raise ValueError('Post Processing Arial input changed during bounded transport')
    return data
