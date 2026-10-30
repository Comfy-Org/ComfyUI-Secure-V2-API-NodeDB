"""Runtime byte-policy checks and dense CPU allocation projections.

COMFY_SECURE_MAX_STORE_BYTES is a per-reference limit, not a total RSS limit.
The projection reports simultaneous live allocations for the operator's actual
memory envelope; it never fabricates a global cap by treating that per-ref
policy as total process memory. Native convolution workspace is backend-owned. Float32 CPU depthwise may
use oneDNN; float16/float64 CPU can take the native im2col slow path with
kernel-square work buffers. This estimate is not a process-memory admission.
"""
import math
import logging
import os
import torch
from comfy_api.latest import sdk
def asset_bytes(size):
    maximum=int(os.environ.get('COMFY_SECURE_ASSET_READ_MAX',str(64*1024**2)))
    if maximum<0:raise ValueError('Runtime asset-read byte limit must be nonnegative')
    if size>maximum:raise ValueError('Post Processing encoded font exceeds runtime asset-read byte limit')
    return size

def byte_limit():
    limit=int(os.environ.get('COMFY_SECURE_MAX_STORE_BYTES',str(2*1024**3)))
    if limit<=0:raise ValueError('Runtime store byte limit must be positive')
    return limit

def check_bytes(size,label):
    if size>byte_limit():
        raise ValueError(f'Post Processing {label} exceeds runtime store byte limit')

def geometry(shape,itemsize=1):
    if type(shape) not in (list,tuple) or len(shape)>32 or any(type(x) is not int or x<0 for x in shape):
        raise TypeError('Post Processing requires a bounded dense shape')
    count=math.prod(shape)
    check_bytes(count*itemsize,'tensor')
    return tuple(shape),count

def broadcast(a,b):
    result=[]
    for i in range(1,max(len(a),len(b))+1):
        x=a[-i] if i<=len(a) else 1
        y=b[-i] if i<=len(b) else 1
        if x!=y and x!=1 and y!=1: return None
        result.append(y if x==1 else x)
    return tuple(reversed(result))

def plan(node,tensors,values):
    parsed=[geometry(tuple(t.shape),t.element_size()) for t in tensors]
    widths=[t.element_size() for t in tensors]
    counts=[n for _,n in parsed]
    owned=sum(n*width for n,width in zip(counts,widths))
    largest=max(counts,default=0)
    # Most effects preserve/promote the input dtype; native Pillow/OpenCV paths
    # and HSV allocate float32 output. Never charge 16 bytes for every element.
    width=max(widths,default=4)
    if node in ('HSVThresholdMask','CannyEdgeMask','KuwaharaBlur','Quantize','AsciiArt'):
        width=4
    output=largest*width
    first=parsed[0][0] if parsed else ()
    frame=math.prod(first[-3:-1]) if len(first)>=3 else largest
    work=largest*64
    workspace=largest*width*2
    # Zero/few-channel inputs can still cause BHW or RGB allocations before a
    # native channel error. Meter these dimensions even when input numel is 0.
    for shape,_ in parsed:
        if len(shape)==4:
            _,n=geometry((*shape[:3],max(shape[3],3)))
            output=max(output,n*width)
            workspace=max(workspace,n*width*2)
    if len(parsed)>1:
        shape=broadcast(parsed[0][0],parsed[1][0])
        if shape is not None:
            _,n=geometry(shape)
            output=max(output,n*width)
            workspace=max(workspace,n*width*2)
    if node=='Blend' and len(parsed)==2 and all(len(p[0])==4 for p in parsed):
        a,b=parsed[0][0],parsed[1][0]
        resized=(b[0],a[1],a[2],b[3])
        _,n=geometry(resized)
        shape=broadcast(a,resized)
        if shape is not None:
            _,n_out=geometry(shape)
            n=max(n,n_out)
        output=max(output,n*width)
        workspace=max(workspace,n*width*2)
    if node=='Vignette' and len(first)==4 and values['vignette']!=0:
        # Native meshgrid is (W,H), retained rather than repairing nonsquares.
        shape=broadcast(first,(1,first[2],first[1],1))
        if shape is not None:
            _,n=geometry(shape)
            output=max(output,n*width)
            workspace=max(workspace,n*width*2)
    radius_name={'Blur':'blur_radius','Glow':'blur_radius','PencilSketch':'blur_radius',
                 'Sharpen':'sharpen_radius','KuwaharaBlur':'blur_radius'}.get(node)
    if radius_name:
        radius=values[radius_name]
        if type(radius) is not int:
            raise TypeError('Post Processing kernel radius must be an integer')
        kernel=2*max(0,radius)+1
        work=max(work,largest*kernel*kernel*2)
        channels=first[-1] if len(first)==4 else 1
        kernel_bytes=kernel*kernel*max(1,channels)*4
        # groups=channels convolution creates a depthwise kernel and a dense
        # output. It does not materialize B*C*H*W*K*K in Python. Do not charge
        # full im2col storage or use operation counts as a byte-memory cap.
        padded=(first[0]*max(1,channels)*(first[1]+kernel-1)*(first[2]+kernel-1)*width
                if len(first)==4 else 0)
        workspace=max(workspace,padded+largest*width+kernel_bytes)
    if node=='HSVThresholdMask' and len(first)==4:
        output=math.prod(first[:3])*4
        # One frame's uint8 RGB copy, HSV copy, uint8 mask and float32 mask.
        workspace=frame*(3+3+1+4)
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
            if type(values[key]) is not int:
                raise TypeError('Post Processing font/glyph size must be an integer')
            workspace+=max(0,values[key])**2*4 # Native glyph scratch, not a stored ref.
        workspace+=frame*128 # Font bytes/rasterizer workspace are measured separately.
    check_bytes(output,'projected output')
    # Each known dense frame/array is bounded by the same runtime policy.
    # Total concurrent owners are reported separately for cgroup/RSS admission.
    check_bytes(frame*width,'frame')
    report={'input_bytes':owned,'output_bytes':output,'workspace_bytes':workspace,
            'estimated_live_bytes':owned+output+workspace,'work':work,
            'per_reference_limit':byte_limit(),'native_workspace_measured':False}
    logging.getLogger(__name__).info('Post Processing allocation estimate: %s',report)
    return report

async def describe(value):
    if not isinstance(value,sdk.Ref) or value.kind not in ('IMAGE','MASK','TENSOR'):
        raise TypeError('Post Processing requires a public tensor-data reference')
    return (await value.describe())['shape']

async def raw(value):
    if not isinstance(value,sdk.TensorRef):
        raise TypeError('Post Processing requires a typed tensor-data reference')
    tensor=await value.raw()
    if type(tensor) is not torch.Tensor or tensor.layout!=torch.strided or tensor.is_nested:
        raise TypeError('Post Processing requires a plain dense Torch tensor')
    if tensor.device.type!='cpu' or not tensor.is_contiguous() or tensor.requires_grad:
        raise ValueError('Post Processing admitted profile is contiguous CPU data without autograd')
    if tensor.dtype not in (torch.float16,torch.bfloat16,torch.float32,torch.float64,
                            torch.uint8,torch.int8,torch.int16,torch.int32,torch.int64,torch.bool):
        raise TypeError('Post Processing dtype is outside the admitted profile')
    geometry(tuple(tensor.shape),tensor.element_size())
    return tensor

async def font_bytes():
    assets=sdk.ctx().assets
    ref=await assets.resolve('input','post-processing/arial.ttf')
    size=await assets.size(ref)
    if type(size) is not int or size<0:raise ValueError('Post Processing Arial size must be nonnegative')
    asset_bytes(size)
    data=await assets.read_bytes(ref) if size else b''
    if type(data) is not bytes or len(data)!=size or await assets.size(ref)!=size:
        raise ValueError('Post Processing Arial input changed during bounded transport')
    return data
