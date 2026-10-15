"""Explicit bounded local workload admission, never host object recovery."""
import numpy as np
import torch
MAX_PIXELS = 4_194_304
MAX_INPUT_BYTES = 32 * 1024 * 1024
MAX_OUTPUT_BYTES = 96 * 1024 * 1024
MAX_TEXT = 4096

def pixels(width, height, label='image'):
    if type(width) is not int or type(height) is not int:
        raise ValueError(label+' dimensions must be integers')
    if width < 0 or height < 0 or width * height > MAX_PIXELS:
        raise ValueError(label+' pixel workload exceeded')

def qr_pixels(modules, factor, border):
    # Match raster integer scaling, including numeric scalar/string inputs
    # accepted by native PNG. Invalid native borders retain native failure.
    factor = int(factor)
    if border is None: border = 2 if modules < 21 else 4
    parsed_border = int(border)
    if parsed_border != border or parsed_border < 0 or factor <= 0: return
    side = (modules + 2 * parsed_border) * factor
    pixels(side, side, 'QR intermediate')

def dense(value):
    if isinstance(value, torch.Tensor):
        if value.layout != torch.strided or value.is_nested or value.ndim > 32:
            raise ValueError('dense tensor profile required')
        size = value.numel() * value.element_size()
    elif isinstance(value, np.ndarray):
        if value.dtype.kind not in 'buifc' or value.ndim > 32:
            raise ValueError('numeric dense ndarray profile required')
        size = value.nbytes
    else: raise ValueError('numeric tensor input required under raw capability')
    if size > MAX_INPUT_BYTES: raise ValueError('input tensor byte workload exceeded')
    return size

def value_work(value):
    stack = [(value,0)]; items = 0; text = 0; buffers = 0
    while stack:
        current,depth = stack.pop(); items += 1
        if items > 4096 or depth > 32: raise ValueError('display tree workload exceeded')
        if isinstance(current, (torch.Tensor, np.ndarray)):
            buffers += dense(current)
        elif type(current) is str: text += len(current.encode('utf8'))
        elif type(current) in (list, tuple):
            if items+len(stack)+len(current)>4096: raise ValueError('display tree workload exceeded')
            stack.extend((child,depth+1) for child in current)
        elif type(current) is dict:
            if items+len(stack)+2*len(current)>4096: raise ValueError('display tree workload exceeded')
            for key, child in current.items():
                if type(key) not in (str,int,float,bool,type(None)):
                    raise ValueError('display plain key profile required')
                stack.extend(((key,depth+1),(child,depth+1)))
        elif type(current) in (int,float,bool,type(None)):
            if type(current) is int and current.bit_length() > 4096:
                raise ValueError('display integer workload exceeded')
        elif isinstance(current, np.generic):
            if current.dtype.kind not in 'buifc': raise ValueError('display numeric scalar profile required')
            buffers += current.dtype.itemsize
        else: raise ValueError('display bounded plain value profile required')
        if text > 65536 or buffers > MAX_INPUT_BYTES:
            raise ValueError('display aggregate workload exceeded')

def preflight(source, values):
    for name, value in values.items():
        if type(value) is str and len(value.encode('utf8')) > MAX_TEXT:
            raise ValueError(name+' text workload exceeded')
        if isinstance(value, (torch.Tensor,np.ndarray)): dense(value)
    if 'width' in values and 'height' in values:
        pixels(values['width'], values['height'], 'output')
        if values['width'] * values['height'] * 32 > MAX_OUTPUT_BYTES:
            raise ValueError('output aggregate byte workload exceeded')
    im = values.get('image')
    if im is not None:
        shape = tuple(int(n) for n in im.shape if n != 1)
        if len(shape) in (2,3):
            h,w = shape[:2]; pixels(w,h,'input')
            logo_width = values.get('width_height_logo')
            if type(logo_width) is int and w:
                pixels(logo_width,int(h*(logo_width/float(w))),'logo')
            if source.__name__ == 'CreateCornerFrame':
                pixels(w+values['frame_size'],h+values['frame_size'],'frame')
            elif source.__name__ == 'CreateSolidFrame':
                pixels(w+2*values['frame_size'],h+2*values['frame_size'],'frame')
            elif source.__name__ == 'CreateTextFrame':
                pixels(w+values['frame_size'],int(h*1.25)+values['frame_size'],'frame')
                pixels(1024,1408,'fixed text frame')
    elif 'width_height_logo' in values:
        side=values['width_height_logo']; pixels(side,side,'logo')
    if source.__name__ == 'QRCodesSimpleBW':
        import qrcode
        qr=qrcode.QRCode(); qr.add_data(values['text']); qr.make()
        qr_pixels(qr.modules_count,qr.box_size,qr.border)
