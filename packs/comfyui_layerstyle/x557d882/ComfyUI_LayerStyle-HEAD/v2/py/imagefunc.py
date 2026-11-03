"""Exact source spans for the qualified image purposes; see extraction proof.

The eleven OpenCV/skimage branches of chop_image and nonzero SciPy growth
remain unqualified and are rejected before these helpers execute.
"""
from typing import List
import copy
import numpy as np
import torch
from PIL import Image, ImageChops, ImageFilter

def log(message:str, message_type:str='info'):
    name = 'LayerStyle'

    if message_type == 'error':
        message = '\033[1;41m' + message + '\033[m'
    elif message_type == 'warning':
        message = '\033[1;31m' + message + '\033[m'
    elif message_type == 'finish':
        message = '\033[1;32m' + message + '\033[m'
    else:
        message = '\033[1;33m' + message + '\033[m'
    print(f"# 😺dzNodes: {name} -> {message}")


def pil2tensor(image:Image) -> torch.Tensor:
    return torch.from_numpy(np.array(image).astype(np.float32) / 255.0).unsqueeze(0)


def tensor2np(tensor: torch.Tensor) -> List[np.ndarray]:
    if len(tensor.shape) == 3:  # Single image
        return np.clip(255.0 * tensor.cpu().numpy(), 0, 255).astype(np.uint8)
    else:  # Batch of images
        return [np.clip(255.0 * t.cpu().numpy(), 0, 255).astype(np.uint8) for t in tensor]


def tensor2pil(t_image: torch.Tensor)  -> Image:
    if t_image.dtype != torch.float32:
        t_image = t_image.float()
    return Image.fromarray(
        np.clip(
            255.0 * t_image.cpu().numpy().squeeze(),
            0,
            255
        ).astype(np.uint8)
    )


def image2mask(image:Image) -> torch.Tensor:
    if image.mode == 'L':
        return torch.tensor([pil2tensor(image)[0, :, :].tolist()])
    else:
        image = image.convert('RGB').split()[0]
        return torch.tensor([pil2tensor(image)[0, :, :].tolist()])


def mask2image(mask:torch.Tensor)  -> Image:
    masks = tensor2np(mask)
    for m in masks:
        _mask = Image.fromarray(m).convert("L")
        _image = Image.new("RGBA", _mask.size, color='white')
        _image = Image.composite(
            _image, Image.new("RGBA", _mask.size, color='black'), _mask)
    return _image


def shift_image(image:Image, distance_x:int, distance_y:int, background_color:str='#000000', cyclic:bool=False) -> Image:
    width = image.width
    height = image.height
    ret_image = Image.new('RGB', size=(width, height), color=background_color)
    for x in range(width):
        for y in range(height):
            if cyclic:
                    orig_x = x + distance_x
                    if orig_x > width-1 or orig_x < 0:
                        orig_x = abs(orig_x % width)
                    orig_y = y + distance_y
                    if orig_y > height-1 or orig_y < 0:
                        orig_y = abs(orig_y % height)

                    pixel = image.getpixel((orig_x, orig_y))
                    ret_image.putpixel((x, y), pixel)
            else:
                if x > -distance_x and y > -distance_y:  # 防止回转
                    if x + distance_x < width and y + distance_y < height:  # 防止越界
                        pixel = image.getpixel((x + distance_x, y + distance_y))
                        ret_image.putpixel((x, y), pixel)
    return ret_image


def chop_image(background_image:Image, layer_image:Image, blend_mode:str, opacity:int) -> Image:
    ret_image = background_image
    if blend_mode == 'normal':
        ret_image = copy.deepcopy(layer_image)
    if blend_mode == 'multply':
        ret_image = ImageChops.multiply(background_image,layer_image)
    if blend_mode == 'screen':
        ret_image = ImageChops.screen(background_image, layer_image)
    if blend_mode == 'add':
        ret_image = ImageChops.add(background_image, layer_image, 1, 0)
    if blend_mode == 'subtract':
        ret_image = ImageChops.subtract(background_image, layer_image, 1, 0)
    if blend_mode == 'difference':
        ret_image = ImageChops.difference(background_image, layer_image)
    if blend_mode == 'darker':
        ret_image = ImageChops.darker(background_image, layer_image)
    if blend_mode == 'lighter':
        ret_image = ImageChops.lighter(background_image, layer_image)
    if blend_mode == 'color_burn':
        ret_image = blend_color_burn(background_image, layer_image)
    if blend_mode == 'color_dodge':
        ret_image = blend_color_dodge(background_image, layer_image)
    if blend_mode == 'linear_burn':
        ret_image = blend_linear_burn(background_image, layer_image)
    if blend_mode == 'linear_dodge':
        ret_image = blend_linear_dodge(background_image, layer_image)
    if blend_mode == 'overlay':
        ret_image = blend_overlay(background_image, layer_image)
    if blend_mode == 'soft_light':
        ret_image = blend_soft_light(background_image, layer_image)
    if blend_mode == 'hard_light':
        ret_image = blend_hard_light(background_image, layer_image)
    if blend_mode == 'vivid_light':
        ret_image = blend_vivid_light(background_image, layer_image)
    if blend_mode == 'pin_light':
        ret_image = blend_pin_light(background_image, layer_image)
    if blend_mode == 'linear_light':
        ret_image = blend_linear_light(background_image, layer_image)
    if blend_mode == 'hard_mix':
        ret_image = blend_hard_mix(background_image, layer_image)
    # opacity
    if opacity == 0:
        ret_image = background_image
    elif opacity < 100:
        alpha = 1.0 - float(opacity) / 100
        ret_image = Image.blend(ret_image, background_image, alpha)
    return ret_image


def fit_resize_image(image:Image, target_width:int, target_height:int, fit:str, resize_sampler:str, background_color:str = '#000000') -> Image:
    image = image.convert('RGB')
    orig_width, orig_height = image.size
    if image is not None:
        if fit == 'letterbox':
            if orig_width / orig_height > target_width / target_height:  # 更宽，上下留黑
                fit_width = target_width
                fit_height = int(target_width / orig_width * orig_height)
            else:  # 更瘦，左右留黑
                fit_height = target_height
                fit_width = int(target_height / orig_height * orig_width)
            fit_image = image.resize((fit_width, fit_height), resize_sampler)
            ret_image = Image.new('RGB', size=(target_width, target_height), color=background_color)
            ret_image.paste(fit_image, box=((target_width - fit_width)//2, (target_height - fit_height)//2))
        elif fit == 'crop':
            if orig_width / orig_height > target_width / target_height:  # 更宽，裁左右
                fit_width = int(orig_height * target_width / target_height)
                fit_image = image.crop(
                    ((orig_width - fit_width)//2, 0, (orig_width - fit_width)//2 + fit_width, orig_height))
            else:   # 更瘦，裁上下
                fit_height = int(orig_width * target_height / target_width)
                fit_image = image.crop(
                    (0, (orig_height-fit_height)//2, orig_width, (orig_height-fit_height)//2 + fit_height))
            ret_image = fit_image.resize((target_width, target_height), resize_sampler)
        else:
            ret_image = image.resize((target_width, target_height), resize_sampler)
    return  ret_image


def __rotate_expand(image:Image, angle:float, SSAA:int=0, method:str="lanczos") -> Image:
    images = pil2tensor(image)
    expand = "true"
    height, width = images[0, :, :, 0].shape

    def rotate_tensor(tensor):
        resize_sampler = Image.LANCZOS
        rotate_sampler = Image.BICUBIC
        if method == "bicubic":
            resize_sampler = Image.BICUBIC
            rotate_sampler = Image.BICUBIC
        elif method == "hamming":
            resize_sampler = Image.HAMMING
            rotate_sampler = Image.BILINEAR
        elif method == "bilinear":
            resize_sampler = Image.BILINEAR
            rotate_sampler = Image.BILINEAR
        elif method == "box":
            resize_sampler = Image.BOX
            rotate_sampler = Image.NEAREST
        elif method == "nearest":
            resize_sampler = Image.NEAREST
            rotate_sampler = Image.NEAREST
        img = tensor2pil(tensor)
        if SSAA > 1:
            img_us_scaled = img.resize((width * SSAA, height * SSAA), resize_sampler)
            img_rotated = img_us_scaled.rotate(angle, rotate_sampler, expand == "true", fillcolor=(0, 0, 0, 0))
            img_down_scaled = img_rotated.resize((img_rotated.width // SSAA, img_rotated.height // SSAA), resize_sampler)
            result = pil2tensor(img_down_scaled)
        else:
            img_rotated = img.rotate(angle, rotate_sampler, expand == "true", fillcolor=(0, 0, 0, 0))
            result = pil2tensor(img_rotated)
        return result

    if angle == 0.0 or angle == 360.0:
        return tensor2pil(images)
    else:
        rotated_tensor = torch.stack([rotate_tensor(images[i]) for i in range(len(images))])
        return tensor2pil(rotated_tensor).convert('RGB')


def image_rotate_extend_with_alpha(image:Image, angle:float, alpha:Image=None, method:str="lanczos", SSAA:int=0) -> tuple:
    _image = __rotate_expand(image.convert('RGB'), angle, SSAA, method)
    if angle is not None:
        _alpha = __rotate_expand(alpha.convert('RGB'), angle, SSAA, method)
        ret_image = RGB2RGBA(_image, _alpha)
    else:
        ret_image = _image
    return (_image, _alpha.convert('L'), ret_image)


def image_channel_merge(channels:tuple, mode = 'RGB' ) -> Image:
    channel1 = channels[0].convert('L')
    channel2 = channels[1].convert('L')
    channel3 = channels[2].convert('L')
    channel4 = Image.new('L', size=channel1.size, color='white')
    if mode == 'RGBA':
        if len(channels) > 3:
            channel4 = channels[3].convert('L')
        ret_image = Image.merge('RGBA',[channel1, channel2, channel3, channel4])
    elif mode == 'RGB':
        ret_image = Image.merge('RGB', [channel1, channel2, channel3])
    elif mode == 'YCbCr':
        ret_image = Image.merge('YCbCr', [channel1, channel2, channel3]).convert('RGB')
    elif mode == 'LAB':
        ret_image = Image.merge('LAB', [channel1, channel2, channel3]).convert('RGB')
    elif mode == 'HSV':
        ret_image = Image.merge('HSV', [channel1, channel2, channel3]).convert('RGB')
    return ret_image


def image_gray_offset(image:Image, offset:int) -> Image:
    image = image.convert('L')
    image_array = np.array(image, dtype=np.int16)
    image_array = np.clip(image_array + offset, 0, 255).astype(np.uint8)
    ret_image = Image.fromarray(image_array, mode='L')
    return ret_image


def image_hue_offset(image:Image, offset:int) -> Image:
    image = image.convert('L')
    image_array = np.array(image, dtype=np.int16)
    image_array = (image_array + offset) % 256
    image_array = image_array.astype(np.uint8)
    ret_image = Image.fromarray(image_array, mode='L')

    return ret_image


def expand_mask(mask:torch.Tensor, grow:int, blur:int) -> torch.Tensor:
    # grow
    c = 0
    kernel = np.array([[c, 1, c],
                       [1, 1, 1],
                       [c, 1, c]])
    growmask = mask.reshape((-1, mask.shape[-2], mask.shape[-1]))
    out = []
    for m in growmask:
        output = m.numpy()
        for _ in range(abs(grow)):
            if grow < 0:
                output = scipy.ndimage.grey_erosion(output, footprint=kernel)
            else:
                output = scipy.ndimage.grey_dilation(output, footprint=kernel)
        output = torch.from_numpy(output)
        out.append(output)
    # blur
    for idx, tensor in enumerate(out):
        pil_image = tensor2pil(tensor.cpu().detach())
        pil_image = pil_image.filter(ImageFilter.GaussianBlur(blur))
        out[idx] = pil2tensor(pil_image)
    ret_mask = torch.cat(out, dim=0)
    return ret_mask


def RGB2RGBA(image:Image, mask:Image) -> Image:
    (R, G, B) = image.convert('RGB').split()
    return Image.merge('RGBA', (R, G, B, mask.convert('L')))


def is_valid_mask(tensor:torch.Tensor) -> bool:
    return not bool(torch.all(tensor == 0).item())


def num_round_up_to_multiple(number: int, multiple: int) -> int:
    remainder = number % multiple
    if remainder == 0:
        return number
    else:
        factor = (number + multiple - 1) // multiple  # 向上取整的计算方式
        return factor * multiple


chop_mode = [
    'normal',
    'multply',
    'screen',
    'add',
    'subtract',
    'difference',
    'darker',
    'lighter',
    'color_burn',
    'color_dodge',
    'linear_burn',
    'linear_dodge',
    'overlay',
    'soft_light',
    'hard_light',
    'vivid_light',
    'pin_light',
    'linear_light',
    'hard_mix'
    ]


from .._dependencies import probe_scope, refuse

_source_log = log
_source_chop_image = chop_image
_source_expand_mask = expand_mask


def log(message: str, message_type: str = 'info'):
    if not probe_scope.get():
        return _source_log(message, message_type)


def chop_image(background_image: Image, layer_image: Image, blend_mode: str, opacity: int) -> Image:
    if blend_mode in {'color_burn', 'color_dodge', 'linear_burn', 'linear_dodge', 'overlay',
                      'soft_light', 'hard_light', 'vivid_light', 'pin_light', 'linear_light', 'hard_mix'}:
        refuse(f'blend_mode={blend_mode!r} requires unqualified OpenCV and scikit-image dependencies')
    return _source_chop_image(background_image, layer_image, blend_mode, opacity)


def expand_mask(mask: torch.Tensor, grow: int, blur: int) -> torch.Tensor:
    if grow != 0:
        refuse('grow!=0 requires the unqualified SciPy dependency')
    return _source_expand_mask(mask, grow, blur)

