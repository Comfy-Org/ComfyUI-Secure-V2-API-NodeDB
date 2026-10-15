"""Pinned PIL halftone math with explicitly approved two-value helper unpack."""
import math
import numpy as np
import torch
from PIL import Image,ImageDraw,ImageStat
from comfy_api.latest import io
from .secure_schedules import _guard

def _preflight(values):
    _guard(values)
    image=values['image']
    if not isinstance(image,torch.Tensor) or image.layout!=torch.strided or image.ndim not in (3,4):
        raise ValueError('Halftone input must be bounded dense HWC/BHWC')
    b,h,w,c=(1,*image.shape) if image.ndim==3 else tuple(image.shape)
    if b>16 or h>4096 or w>4096 or c>4:
        raise ValueError('Halftone input dimensions exceed bound')
    input_bytes=image.numel()*image.element_size()
    dot=values['dot_size'];aa=values['antialias_scale']
    if type(dot) is not int or abs(dot)>128 or type(aa) is not int or abs(aa)>4:
        raise ValueError('Halftone dot/antialias scale exceeds bound')
    for key in ('angle_c','angle_m','angle_y','angle_k'):
        angle=values[key]
        if isinstance(angle,bool) or not isinstance(angle,(int,float)) or not math.isfinite(angle) or abs(angle)>36000:
            raise ValueError('Halftone rotation exceeds bound')
    for key in ('dot_shape','resolution'):
        if not isinstance(values[key],str) or len(values[key].encode('utf-8'))>128:
            raise ValueError('Halftone option text exceeds bound')
    resolution_scale=2 if values['resolution']=='hi-res (2x output size)' else 1
    drawing_scale=resolution_scale*(abs(aa) if values['antialias'] else 1)
    side=h+w+4;expanded=2*side*drawing_scale+4
    output=h*w*resolution_scale**2*16
    temporary=expanded**2*4+output*3+input_bytes
    if input_bytes>32*1024*1024 or output>32*1024*1024 or temporary>128*1024*1024 or expanded>32768:
        raise ValueError('Halftone projected rotated output/temporary workload exceeds bound')
    channels=1 if values['greyscale'] else 4
    if dot>0 and math.ceil(side/dot)**2*channels>1048576:
        raise ValueError('Halftone projected dot draw workload exceeds bound')

class CR_HalftoneFilter(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Halftone Filter',display_name='🎨 Halftone Filter',category='🧩 Comfyroll Studio/👾 Graphics/🎨 Filter',inputs=[io.Image.Input('image'), io.Int.Input('dot_size', default=5, min=1, max=30, step=1), io.Combo.Input('dot_shape', default='ellipse', options=['ellipse', 'rectangle']), io.Combo.Input('resolution', default='normal', options=['normal', 'hi-res (2x output size)']), io.Int.Input('angle_c', default=75, min=0, max=360, step=1), io.Int.Input('angle_m', default=45, min=0, max=360, step=1), io.Int.Input('angle_y', default=15, min=0, max=360, step=1), io.Int.Input('angle_k', default=0, min=0, max=360, step=1), io.Boolean.Input('greyscale', default=True), io.Boolean.Input('antialias', default=True), io.Int.Input('antialias_scale', default=2, min=1, max=4, step=1), io.Boolean.Input('border_blending', default=False)],outputs=[io.Image.Output(display_name='IMAGE'),io.String.Output(display_name='show_help')])

    @classmethod
    def __init__(cls):
        pass


    @classmethod
    def tensor_to_pil(cls, tensor):
        if tensor.ndim == 4 and tensor.shape[0] == 1:
            tensor = tensor.squeeze(0)
        if tensor.dtype == torch.float32:
            tensor = tensor.mul(255).byte()
        elif tensor.dtype != torch.uint8:
            tensor = tensor.byte()
        numpy_image = tensor.cpu().numpy()
        if tensor.ndim == 3:
            if tensor.shape[2] == 1:
                mode = 'L'
            elif tensor.shape[2] == 3:
                mode = 'RGB'
            elif tensor.shape[2] == 4:
                mode = 'RGBA'
            else:
                raise ValueError(f'Unsupported channel number: {tensor.shape[2]}')
        else:
            raise ValueError(f'Unexpected tensor shape: {tensor.shape}')
        pil_image = Image.fromarray(numpy_image, mode)
        return pil_image


    @classmethod
    def pil_to_tensor(cls, pil_image):
        numpy_image = np.array(pil_image)
        tensor = torch.from_numpy(numpy_image).float().div(255)
        tensor = tensor.unsqueeze(0)
        return tensor


    @classmethod
    def execute(cls, image, dot_size, dot_shape, resolution, angle_c, angle_m, angle_y, angle_k, greyscale, antialias, border_blending, antialias_scale):
        _preflight({'image': image, 'dot_size': dot_size, 'dot_shape': dot_shape, 'resolution': resolution, 'angle_c': angle_c, 'angle_m': angle_m, 'angle_y': angle_y, 'angle_k': angle_k, 'greyscale': greyscale, 'antialias': antialias, 'border_blending': border_blending, 'antialias_scale': antialias_scale})
        sample = dot_size
        shape = dot_shape
        resolution_to_scale = {'normal': 1, 'hi-res (2x output size)': 2}
        scale = resolution_to_scale.get(resolution, 1)
        if isinstance(image, torch.Tensor):
            image = cls.tensor_to_pil(image)
        if not isinstance(image, Image.Image):
            raise TypeError('The provided image is neither a PIL Image nor a PyTorch tensor.')
        pil_image = image
        if greyscale:
            pil_image = pil_image.convert('L')
            channel_images = [pil_image]
            angles = [angle_k]
        else:
            pil_image = pil_image.convert('CMYK')
            channel_images = list(pil_image.split())
            angles = [angle_c, angle_m, angle_y, angle_k]
        halftone_images, show_help = cls._halftone_pil(pil_image, channel_images, sample, scale, angles, antialias, border_blending, antialias_scale, shape)
        if greyscale:
            new_image = halftone_images[0].convert('RGB')
        else:
            new_image = Image.merge('CMYK', halftone_images).convert('RGB')
        result_tensor = cls.pil_to_tensor(new_image)
        print('Final tensor shape:', result_tensor.shape)
        return io.NodeOutput(result_tensor, show_help)


    @classmethod
    def _halftone_pil(cls, im, cmyk, sample, scale, angles, antialias, border_blending, antialias_scale, shape):
        antialias_res = antialias_scale if antialias else 1
        scale = scale * antialias_res
        dots = []
        for channel_index, (channel, angle) in enumerate(zip(cmyk, angles)):
            channel = channel.rotate(angle, expand=1)
            size = (channel.size[0] * scale, channel.size[1] * scale)
            half_tone = Image.new('L', size)
            draw = ImageDraw.Draw(half_tone)
            for x in range(0, channel.size[0], sample):
                for y in range(0, channel.size[1], sample):
                    if border_blending and angle % 90 != 0 and (x < sample or y < sample or x > channel.size[0] - sample or (y > channel.size[1] - sample)):
                        neighboring_pixels = channel.crop((max(x - 1, 0), max(y - 1, 0), min(x + 2, channel.size[0]), min(y + 2, channel.size[1])))
                        pixels = list(neighboring_pixels.getdata())
                        weights = [0.5 if i in [0, len(pixels) - 1] else 1 for i in range(len(pixels))]
                        weighted_mean = sum((p * w for p, w in zip(pixels, weights))) / sum(weights)
                        mean = weighted_mean
                    else:
                        box = channel.crop((x, y, x + sample, y + sample))
                        mean = ImageStat.Stat(box).mean[0]
                    size = (mean / 255) ** 0.5
                    box_size = sample * scale
                    draw_size = size * box_size
                    box_x, box_y = (x * scale, y * scale)
                    x1 = box_x + (box_size - draw_size) / 2
                    y1 = box_y + (box_size - draw_size) / 2
                    x2 = x1 + draw_size
                    y2 = y1 + draw_size
                    draw_method = getattr(draw, shape, None)
                    if draw_method:
                        draw_method([(x1, y1), (x2, y2)], fill=255)
            half_tone = half_tone.rotate(-angle, expand=1)
            width_half, height_half = half_tone.size
            xx1 = (width_half - im.size[0] * scale) / 2
            yy1 = (height_half - im.size[1] * scale) / 2
            xx2 = xx1 + im.size[0] * scale
            yy2 = yy1 + im.size[1] * scale
            half_tone = half_tone.crop((xx1, yy1, xx2, yy2))
            if antialias:
                w = int((xx2 - xx1) / antialias_scale)
                h = int((yy2 - yy1) / antialias_scale)
                half_tone = half_tone.resize((w, h), resample=Image.LANCZOS)
            dots.append(half_tone)
            show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Filter-Nodes#cr-halftone-filter'
        return (dots, show_help)


NODE_CLASS_MAPPINGS={'CR Halftone Filter':CR_HalftoneFilter}
NODE_DISPLAY_NAME_MAPPINGS={'CR Halftone Filter': '🎨 Halftone Filter'}

