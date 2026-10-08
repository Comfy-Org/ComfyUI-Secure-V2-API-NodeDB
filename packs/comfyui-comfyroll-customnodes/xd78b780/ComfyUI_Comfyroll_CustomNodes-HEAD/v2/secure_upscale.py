"""Pinned upscale/PIL algorithms stay in pack; host owns only typed model execution."""
import math
import numpy as np
import torch
from PIL import Image
from comfy_api.latest import io,sdk
from .secure_schedules import _guard,_output
from .secure_lora import _name
from .secure_tensors import _preflight as _tensor_preflight

def _inputs(values):
    _guard(values)
    rows=values.get('upscale_stack')
    if isinstance(rows,(list,tuple)) and len(rows)>16:raise ValueError('Upscale stack workload exceeds16 rows')
def _pixels(image):
    _tensor_preflight('CR Upscale Image',{'image':image})
    if image.ndim==4 and image.shape[0]>64:raise ValueError('Upscale batch exceeds64')
async def _load(name):
    return await sdk.ctx().models.load_upscale_model(_name(name))
async def _upscale(model,image):
    _pixels(image)
    ref=await sdk.ImageRef.from_value(image)
    n=int(image.shape[0]) if image.ndim else 1
    out=await model.upscale(ref,per_batch=max(1,n),tile_size=512,precision='float32')
    pixels=await out.raw()
    _pixels(pixels) # Output/workload check AFTER trusted execution, not a host allocation grant.
    return pixels
async def _publish(result,original_ref,original_pixels):
    pixels,help=result
    ref=original_ref if pixels is original_pixels else await sdk.ImageRef.from_value(pixels)
    return io.NodeOutput(ref,help)

def pil2tensor(image):
    return torch.from_numpy(np.array(image).astype(np.float32) / 255.0).unsqueeze(0)

def tensor2pil(image):
    return Image.fromarray(np.clip(255.0 * image.cpu().numpy().squeeze(), 0, 255).astype(np.uint8))

def apply_resize_image(image: Image.Image, original_width, original_height, rounding_modulus, mode='scale', supersample='true', factor: int=2, width: int=1024, height: int=1024, resample='bicubic', *, _batch_count=1):
    if mode == 'rescale':
        new_width, new_height = (int(original_width * factor), int(original_height * factor))
    else:
        m = rounding_modulus
        original_ratio = original_height / original_width
        height = int(width * original_ratio)
        new_width = width if width % m == 0 else width + (m - width % m)
        new_height = height if height % m == 0 else height + (m - height % m)
    if isinstance(new_width, int) and isinstance(new_height, int):
        mult = 8 if supersample == 'true' else 1
        channels = max(1, len(image.getbands()))
        projected = max(0, new_width) * max(0, new_height) * channels
        if new_width > 8192 or new_height > 8192 or new_width * mult > 8192 or (new_height * mult > 8192) or (projected * 4 > 32 * 1024 * 1024) or (projected * 4 * _batch_count > 64 * 1024 * 1024) or (projected * (mult * mult + 8) > 128 * 1024 * 1024) or (projected * (mult * mult + 8 + 4 * _batch_count) > 256 * 1024 * 1024):
            raise ValueError('Upscale PIL target/temporary workload exceeds bound')
    resample_filters = {'nearest': 0, 'bilinear': 2, 'bicubic': 3, 'lanczos': 1}
    if supersample == 'true':
        image = image.resize((new_width * 8, new_height * 8), resample=Image.Resampling(resample_filters[resample]))
    resized_image = image.resize((new_width, new_height), resample=Image.Resampling(resample_filters[resample]))
    return resized_image

class CR_UpscaleImage(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=('models', 'raw')
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Upscale Image',display_name='🔍 CR Upscale Image',category='🧩 Comfyroll Studio/✨ Essential/🔍 Upscale',inputs=[io.Image.Input('image'),io.Combo.Input('upscale_model',options=[],remote=io.RemoteOptions(route='/secure-nodes/models/upscale_models', refresh_button=True)),io.Combo.Input('mode',options=['rescale', 'resize']),io.Float.Input('rescale_factor',default=2,min=0.01,max=16.0,step=0.01),io.Int.Input('resize_width',default=1024,min=1,max=48000,step=1),io.Combo.Input('resampling_method',options=['lanczos', 'nearest', 'bilinear', 'bicubic']),io.Combo.Input('supersample',options=['true', 'false']),io.Int.Input('rounding_modulus',default=8,min=8,max=1024,step=8)],outputs=[io.Image.Output(display_name='IMAGE'),io.String.Output(display_name='show_help')])

    @classmethod
    async def execute(cls, image, upscale_model, rounding_modulus=8, loops=1, mode='rescale', supersample='true', resampling_method='lanczos', rescale_factor=2, resize_width=1024):
        _inputs({'image': image, 'upscale_model': upscale_model, 'rounding_modulus': rounding_modulus, 'loops': loops, 'mode': mode, 'supersample': supersample, 'resampling_method': resampling_method, 'rescale_factor': rescale_factor, 'resize_width': resize_width})
        _original_ref = image
        image = await image.raw()
        _original_pixels = image
        _pixels(image)
        up_model = await _load(upscale_model)
        up_image = await _upscale(up_model, image)
        for img in image:
            pil_img = tensor2pil(img)
            original_width, original_height = pil_img.size
        for img in up_image:
            pil_img = tensor2pil(img)
            upscaled_width, upscaled_height = pil_img.size
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Upscale-Nodes#cr-upscale-image'
        if upscaled_width == original_width and rescale_factor == 1:
            return await _publish((up_image, show_help), _original_ref, _original_pixels)
        scaled_images = []
        for img in up_image:
            scaled_images.append(pil2tensor(apply_resize_image(tensor2pil(img), original_width, original_height, rounding_modulus, mode, supersample, rescale_factor, resize_width, resampling_method, _batch_count=int(up_image.shape[0]))))
        images_out = torch.cat(scaled_images, dim=0)
        return await _publish((images_out, show_help), _original_ref, _original_pixels)

class CR_MultiUpscaleStack(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Multi Upscale Stack',display_name='🔍 CR Multi Upscale Stack',category='🧩 Comfyroll Studio/✨ Essential/🔍 Upscale',inputs=[io.Combo.Input('switch_1',options=['On', 'Off']),io.Combo.Input('upscale_model_1',options=['None'],remote=io.RemoteOptions(route='/secure-nodes/models/upscale_models', refresh_button=True, static_options=['None'])),io.Float.Input('rescale_factor_1',default=2,min=0.01,max=16.0,step=0.01),io.Combo.Input('switch_2',options=['On', 'Off']),io.Combo.Input('upscale_model_2',options=['None'],remote=io.RemoteOptions(route='/secure-nodes/models/upscale_models', refresh_button=True, static_options=['None'])),io.Float.Input('rescale_factor_2',default=2,min=0.01,max=16.0,step=0.01),io.Combo.Input('switch_3',options=['On', 'Off']),io.Combo.Input('upscale_model_3',options=['None'],remote=io.RemoteOptions(route='/secure-nodes/models/upscale_models', refresh_button=True, static_options=['None'])),io.Float.Input('rescale_factor_3',default=2,min=0.01,max=16.0,step=0.01),io.Custom('UPSCALE_STACK').Input('upscale_stack',optional=True)],outputs=[io.Custom('UPSCALE_STACK').Output(display_name='UPSCALE_STACK'),io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, switch_1, upscale_model_1, rescale_factor_1, switch_2, upscale_model_2, rescale_factor_2, switch_3, upscale_model_3, rescale_factor_3, upscale_stack=None):
        _inputs({'switch_1': switch_1, 'upscale_model_1': upscale_model_1, 'rescale_factor_1': rescale_factor_1, 'switch_2': switch_2, 'upscale_model_2': upscale_model_2, 'rescale_factor_2': rescale_factor_2, 'switch_3': switch_3, 'upscale_model_3': upscale_model_3, 'rescale_factor_3': rescale_factor_3, 'upscale_stack': upscale_stack})
        upscale_list = list()
        if upscale_stack is not None:
            upscale_list.extend([l for l in upscale_stack if l[0] != 'None'])
        if upscale_model_1 != 'None' and switch_1 == 'On':
            (upscale_list.extend([(upscale_model_1, rescale_factor_1)]),)
        if upscale_model_2 != 'None' and switch_2 == 'On':
            (upscale_list.extend([(upscale_model_2, rescale_factor_2)]),)
        if upscale_model_3 != 'None' and switch_3 == 'On':
            (upscale_list.extend([(upscale_model_3, rescale_factor_3)]),)
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Upscale-Nodes#cr-multi-upscale-stack'
        return _output((upscale_list, show_help))

class CR_ApplyMultiUpscale(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=('models', 'raw')
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Apply Multi Upscale',display_name='🔍 CR Apply Multi Upscale',category='🧩 Comfyroll Studio/✨ Essential/🔍 Upscale',inputs=[io.Image.Input('image'),io.Combo.Input('resampling_method',options=['lanczos', 'nearest', 'bilinear', 'bicubic']),io.Combo.Input('supersample',options=['true', 'false']),io.Int.Input('rounding_modulus',default=8,min=8,max=1024,step=8),io.Custom('UPSCALE_STACK').Input('upscale_stack')],outputs=[io.Image.Output(display_name='IMAGE'),io.String.Output(display_name='show_help')])

    @classmethod
    async def execute(cls, image, resampling_method, supersample, rounding_modulus, upscale_stack):
        _inputs({'image': image, 'resampling_method': resampling_method, 'supersample': supersample, 'rounding_modulus': rounding_modulus, 'upscale_stack': upscale_stack})
        _original_ref = image
        image = await image.raw()
        _original_pixels = image
        _pixels(image)
        pil_img = tensor2pil(image)
        original_width, original_height = pil_img.size
        params = list()
        params.extend(upscale_stack)
        for tup in params:
            upscale_model, rescale_factor = tup
            print(f'[Info] CR Apply Multi Upscale: Applying {upscale_model} and rescaling by factor {rescale_factor}')
            up_model = await _load(upscale_model)
            up_image = await _upscale(up_model, image)
            pil_img = tensor2pil(up_image)
            upscaled_width, upscaled_height = pil_img.size
            if upscaled_width == original_width and rescale_factor == 1:
                image = up_image
            else:
                scaled_images = []
                mode = 'rescale'
                resize_width = 1024
                for img in up_image:
                    scaled_images.append(pil2tensor(apply_resize_image(tensor2pil(img), original_width, original_height, rounding_modulus, mode, supersample, rescale_factor, resize_width, resampling_method, _batch_count=int(up_image.shape[0]))))
                image = torch.cat(scaled_images, dim=0)
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Upscale-Nodes#cr-apply-multi-upscale'
        return await _publish((image, show_help), _original_ref, _original_pixels)

NODE_CLASS_MAPPINGS={'CR Upscale Image':CR_UpscaleImage,'CR Multi Upscale Stack':CR_MultiUpscaleStack,'CR Apply Multi Upscale':CR_ApplyMultiUpscale}
NODE_DISPLAY_NAME_MAPPINGS={'CR Upscale Image': '🔍 CR Upscale Image', 'CR Multi Upscale Stack': '🔍 CR Multi Upscale Stack', 'CR Apply Multi Upscale': '🔍 CR Apply Multi Upscale'}
