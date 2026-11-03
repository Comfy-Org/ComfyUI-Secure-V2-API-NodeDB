from typing import Literal
import math
from PIL import Image
from . import image_util

SIZE_DICT = {'512 x 512': {'width': 512, 'height': 512}, '512 x 768': {'width': 512, 'height': 768}, '1024 x 1024': {'width': 1024, 'height': 1024}, '768 x 1024': {'width': 768, 'height': 1024}, '832 x 1216': {'width': 832, 'height': 1216}, '1248 x 1632': {'width': 1248, 'height': 1632}}
SIZE_LIST = ['custom', '512 x 512', '512 x 768', '1024 x 1024', '768 x 1024', '832 x 1216', '1248 x 1632']

D2_TResizeMethod = Literal["None", "none", "Floor", "floor", "Ceil", "ceil", "Round", "round"]

RESAMPLE_FILTERS = {
    'nearest': 0,
    'bilinear': 2,
    'bicubic': 3,
    'lanczos': 1
}

def number_adjust(number, method:D2_TResizeMethod='Floor', target_num=8):
    valid_methods = ['round', 'ceil', 'floor', 'none']
    lower_method = str(method).lower()

    if lower_method not in valid_methods:
        raise ValueError(f"Invalid method: {method}. Must be one of {valid_methods}")

    if lower_method == 'round':
        return round(number / target_num) * target_num
    elif lower_method == 'ceil':
        return math.ceil(number / target_num) * target_num
    elif lower_method == 'ceil':
        return math.floor(number / target_num) * target_num
    else:
        return number

def rescale_calc(width, height, rescale_factor=2, method:D2_TResizeMethod='Floor'):
    width = int(width * rescale_factor)
    height = int(height * rescale_factor)

    width = number_adjust(width, method, 8)
    height = number_adjust(height, method, 8)
    return width, height

def get_new_size(
        mode = "rescale", 
        rescale_factor = 2, 
        resize_width = 1024, 
        resize_height = 1024, 
        round_method:D2_TResizeMethod = "Floor", 
        org_width = 0, 
        org_height = 0, 
        preset = "custom"
    ):

    if(mode == "resize"):
        """
        数値指定モード
        """
        if(preset != "custom"):
            new_width = SIZE_DICT.get(preset).get("width", resize_width)
            new_height = SIZE_DICT.get(preset).get("height", resize_height)
        else:
            new_width = resize_width
            new_height = resize_height
        
        # 端数を入力される可能性があるので四捨五入
        new_width, new_height = rescale_calc(new_width, new_height, 1, round_method)

    else:
        """
        倍率指定モード
        """
        new_width, new_height = rescale_calc(org_width, org_height, rescale_factor, round_method)

    return new_width, new_height

def apply_resize_image(
    image: Image.Image, 
    resize_width = 1024, 
    resize_height = 1024, 
    rotate = "None", 
    upscale_model = "None",
    resampling = "lanczos", 
):

    # # UpscaleModelを使う
    if upscale_model != "None":
        raise RuntimeError("d2-nodes-comfyui/D2 Image Resize: upscale_model is not yet converted to Secure Nodes V2")

    # Resize the image using the given resampling filter
    resized_image = image.resize((resize_width, resize_height), resample=Image.Resampling(RESAMPLE_FILTERS[resampling]))

    # 回転
    # resized_image、resize_width、resize_height を更新する
    if rotate == '90 deg':
        resized_image = resized_image.rotate(-90, expand=True)
        resize_width, resize_height = resize_height, resize_width
    elif rotate == '180 deg':
        resized_image = resized_image.rotate(-180, expand=True)
        # 180度回転では幅と高さは変わらない
    elif rotate == '270 deg':
        resized_image = resized_image.rotate(-270, expand=True)
        resize_width, resize_height = resize_height, resize_width

    return resized_image, resize_width, resize_height

def apply_resize_mask(
    mask: Image.Image, 
    resize_width = 1024, 
    resize_height = 1024, 
    rotate = "None", 
    resampling = "lanczos", 
):
    # Resize the mask using the given resampling filter
    resized_mask = mask.resize((resize_width, resize_height), resample=Image.Resampling(RESAMPLE_FILTERS[resampling]))

    # 回転
    # resized_mask、resize_width、resize_height を更新する
    if rotate == '90 deg':
        resized_mask = resized_mask.rotate(-90, expand=True)
        resize_width, resize_height = resize_height, resize_width
    elif rotate == '180 deg':
        resized_mask = resized_mask.rotate(-180, expand=True)
        # 180度回転では幅と高さは変わらない
    elif rotate == '270 deg':
        resized_mask = resized_mask.rotate(-270, expand=True)
        resize_width, resize_height = resize_height, resize_width

    return resized_mask, resize_width, resize_height
