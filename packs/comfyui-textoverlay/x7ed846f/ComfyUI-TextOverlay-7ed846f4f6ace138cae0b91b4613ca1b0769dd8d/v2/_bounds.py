"""Before-buffer/read/render admission for the local dense image/font profile."""
import math
import unicodedata
import torch
from comfy_api.latest import sdk

MAX_FONT=2*1024*1024
MAX_INPUT=32*1024*1024
MAX_OUTPUT=32*1024*1024
MAX_TOTAL=256*1024*1024
MAX_GLYPH_WORK=16_777_216
MAX_TEXT=4096

class ProfileError(ValueError):
    pass

def font_label(value):
    if type(value) is not str or not value or len(value)>255 or len(value.encode('utf-8'))>255:
        raise ProfileError('TextOverlay font label budget')
    if value in ('.','..') or any(char in '/\\:' or unicodedata.category(char)=='Cc' for char in value):
        raise ProfileError('TextOverlay requires a logical font basename')
    return 'textoverlay/'+value

def geometry(shape):
    if type(shape) not in (tuple,list) or len(shape) not in (3,4) or any(type(x) is not int or x<0 for x in shape):
        raise ProfileError('TextOverlay local dense HWC/BHWC geometry profile')
    shape=tuple(shape);count=math.prod(shape)
    b,h,w,c=(1,*shape) if len(shape)==3 else shape
    if any(axis>16384 for axis in shape) or b>64:
        raise ProfileError('TextOverlay geometry axis/batch budget')
    # Also reserve image-plane workspace for zero/few-channel inputs, before
    # any decoder/native error: a zero numel does not imply zero image work.
    expanded=b*h*w*max(c,4)
    if count*16>MAX_INPUT or expanded*4>MAX_OUTPUT:
        raise ProfileError('TextOverlay image byte budget')
    return shape,count,expanded,b

def plan(shape,values):
    _,count,expanded,b=geometry(shape)
    for key in ('text','fill_color_hex','stroke_color_hex'):
        if type(values[key]) is not str:
            raise ProfileError('TextOverlay requires plain strings')
    text=values['text'];size=values['font_size']
    if len(text)>MAX_TEXT or len(text.encode('utf-8'))>MAX_TEXT:
        raise ProfileError('TextOverlay text budget')
    if type(size) is not int or not 1<=size<=9999:
        raise ProfileError('TextOverlay font-size profile')
    for key in ('padding','x_shift','y_shift'):
        if type(values[key]) is not int or abs(values[key])>128:
            raise ProfileError('TextOverlay geometry scalar profile')
    for key in ('stroke_thickness','line_spacing'):
        value=values[key]
        if type(value) not in (int,float) or not math.isfinite(value):
            raise ProfileError('TextOverlay finite layout scalar profile')
    if not 0<=values['stroke_thickness']<=1 or not 0<=values['line_spacing']<=50:
        raise ProfileError('TextOverlay layout scalar budget')
    for key in ('fill_color_hex','stroke_color_hex'):
        if len(values[key])>64 or len(values[key].encode())>64:
            raise ProfileError('TextOverlay color string budget')
    if type(values['horizontal_alignment']) is not str or type(values['vertical_alignment']) is not str or values['horizontal_alignment'] not in ('left','center','right') or values['vertical_alignment'] not in ('top','middle','bottom'):
        raise ProfileError('TextOverlay alignment profile')
    font_label(values['font'])
    # Native wrapping textlength repeatedly measures a growing line: use the
    # quadratic worst case, plus per-image glyph raster and multiline extent.
    length=len(text)+1
    glyph_work=length*length*size+length*size*size*max(1,b)
    glyph_workspace=length*(size+64)*(size+64)*4
    workspace=count*16*3+expanded*16*8+MAX_FONT*4+glyph_workspace+4_194_304
    if glyph_work>MAX_GLYPH_WORK or workspace>MAX_TOTAL:
        raise ProfileError('TextOverlay projected glyph/workspace budget')
    return dict(input_bytes=count*16,output_bytes=expanded*4,workspace_bytes=workspace,glyph_work=glyph_work)

async def describe(image):
    if not isinstance(image,sdk.Ref) or image.kind not in ('IMAGE','TENSOR'):
        raise TypeError('TextOverlay requires a public image-data reference')
    return (await image.describe())['shape']

async def raw(image):
    value=await (await sdk.TensorRef.from_ref(image)).raw()
    if type(value) is not torch.Tensor or value.layout!=torch.strided or value.is_nested:
        raise ProfileError('TextOverlay requires a plain dense Torch tensor')
    if value.device.type!='cpu' or not value.is_contiguous() or value.requires_grad:
        raise ProfileError('TextOverlay local CPU contiguous/no-autograd profile')
    geometry(tuple(value.shape))
    return value

async def font_bytes(name):
    label=font_label(name);assets=sdk.ctx().assets
    # Only a genuine admitted missing asset invokes the native fallback.
    # Permissions/security/resource/unknown broker failures are never caught.
    if not await assets.exists('input',label):
        return None
    asset=await assets.resolve('input',label)
    size=await assets.size(asset)
    if type(size) is not int or not 0<=size<=MAX_FONT:
        raise ProfileError('TextOverlay font byte budget')
    value=await assets.read_range(asset,0,size)
    tail=await assets.read_range(asset,size,1)
    if type(value) is not bytes or len(value)!=size or tail or await assets.size(asset)!=size:
        raise ProfileError('TextOverlay font changed during bounded transport')
    return value
