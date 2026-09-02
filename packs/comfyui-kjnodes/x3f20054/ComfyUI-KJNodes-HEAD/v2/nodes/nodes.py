from __future__ import annotations
from comfy_api.latest import io as _deprecated_compile_aliases_io

class _DeprecatedCompileAliasSecure(_deprecated_compile_aliases_io.ComfyNode):
    SDK_REFS = True
    NODE_ID = ''

    @classmethod
    def define_schema(cls) -> _deprecated_compile_aliases_io.Schema:
        return _deprecated_compile_aliases_io.Schema(node_id=f'{cls.NODE_ID}Secure', display_name=f'{cls.NODE_ID} (Secure V2)', category='KJNodes/deprecated', description='This compatibility node has been replaced by TorchCompileModelAdvanced and passes its input through.', inputs=[_deprecated_compile_aliases_io.AnyType.Input('model')], outputs=[_deprecated_compile_aliases_io.AnyType.Output('model')])

    @classmethod
    async def execute(cls, model) -> _deprecated_compile_aliases_io.NodeOutput:
        return _deprecated_compile_aliases_io.NodeOutput(model)

class TorchCompileModelFluxAdvancedSecure(_DeprecatedCompileAliasSecure):
    NODE_ID = 'TorchCompileModelFluxAdvanced'

class TorchCompileLTXModelSecure(_DeprecatedCompileAliasSecure):
    NODE_ID = 'TorchCompileLTXModel'

class TorchCompileCosmosModelSecure(_DeprecatedCompileAliasSecure):
    NODE_ID = 'TorchCompileCosmosModel'
class TorchCompileModelHyVideoSecure(_DeprecatedCompileAliasSecure):
    NODE_ID = 'TorchCompileModelHyVideo'

class TorchCompileModelQwenImageSecure(_DeprecatedCompileAliasSecure):
    NODE_ID = 'TorchCompileModelQwenImage'

class TorchCompileModelWanVideoSecure(_DeprecatedCompileAliasSecure):
    NODE_ID = 'TorchCompileModelWanVideo'
from comfy_api.latest import io as _intent_a_io

class ModelPassThroughSecure(_intent_a_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _intent_a_io.Schema:
        return _intent_a_io.Schema(node_id='ModelPassThroughSecure', display_name='🔒 Model Pass Through (secure)', category='KJNodes/misc', description='Simply passes through the model, workaround for Set node not allowing bypassed inputs.', inputs=[_intent_a_io.Model.Input('model', optional=True)], outputs=[_intent_a_io.Model.Output(display_name='model')])

    @classmethod
    async def execute(cls, model=None) -> _intent_a_io.NodeOutput:
        return _intent_a_io.NodeOutput(model)

class CondPassThroughSecure(_intent_a_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _intent_a_io.Schema:
        return _intent_a_io.Schema(node_id='CondPassThroughSecure', display_name='🔒 Cond Pass Through (secure)', category='KJNodes/misc', description='Simply passes through the positive and negative conditioning, workaround for Set node not allowing bypassed inputs.', inputs=[_intent_a_io.Conditioning.Input('positive', optional=True), _intent_a_io.Conditioning.Input('negative', optional=True)], outputs=[_intent_a_io.Conditioning.Output(display_name='positive'), _intent_a_io.Conditioning.Output(display_name='negative')])

    @classmethod
    async def execute(cls, positive=None, negative=None) -> _intent_a_io.NodeOutput:
        return _intent_a_io.NodeOutput(positive, negative)
import time as _intent_timer_time
from comfy_api.latest import io as _intent_timer_io
_intent_timer_Any = _intent_timer_io.Custom('*')
_intent_timer_TimerToken = _intent_timer_io.Custom('TIMER')

class TimerNodeKJSecure(_intent_timer_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _intent_timer_io.Schema:
        return _intent_timer_io.Schema(node_id='TimerNodeKJSecure', display_name='🔒 Timer (secure)', category='KJNodes/misc', description='Measures elapsed milliseconds between a start and a stop node. Pass the timer token from start to stop.', inputs=[_intent_timer_Any.Input('any_input'), _intent_timer_io.Combo.Input('mode', options=['start', 'stop'], default='start'), _intent_timer_io.String.Input('name', default='Timer'), _intent_timer_TimerToken.Input('timer', optional=True)], outputs=[_intent_timer_Any.Output(display_name='any_output'), _intent_timer_TimerToken.Output(display_name='timer'), _intent_timer_io.Int.Output(display_name='time')])

    @classmethod
    async def execute(cls, any_input, mode, name, timer=None) -> _intent_timer_io.NodeOutput:
        if mode == 'start':
            token = {'name': name, 'start_time': _intent_timer_time.time()}
            return _intent_timer_io.NodeOutput(any_input, token, 0, ui={'text': [f"{token['start_time']}"]})
        if not isinstance(timer, dict) or 'start_time' not in timer:
            raise ValueError("Timer 'stop' needs the token from a matching 'start' node; connect the start node's `timer` output to this input.")
        elapsed = int((_intent_timer_time.time() - float(timer['start_time'])) * 1000)
        return _intent_timer_io.NodeOutput(any_input, {'name': timer.get('name', name), 'start_time': None, 'elapsed': elapsed}, elapsed, ui={'text': [f'{elapsed} ms']})
import ast as _remaining_a_ast
import copy as _remaining_a_copy
import pathlib as _remaining_a_pathlib
from comfy_api.latest import io as _remaining_a_io, sdk as _remaining_a_sdk
from . import _packload as _remaining_a_packload
_remaining_a_METHODS = {}
_remaining_a_TREES = {}

def _remaining_a_source_root():
    return _remaining_a_pathlib.Path(_remaining_a_packload.ROOT).resolve()

def _remaining_a_tree(relpath: str):
    cached = _remaining_a_TREES.get(relpath)
    if cached is not None:
        return cached
    path = _remaining_a_source_root().joinpath(*relpath.split('/'))
    text = path.read_text(encoding='utf-8')
    parsed = (path, text, _remaining_a_ast.parse(text, filename=str(path)))
    _remaining_a_TREES[relpath] = parsed
    return parsed

def _remaining_a_upstream(relpath: str, class_name: str, method_name: str, helpers=()):
    key = (relpath, class_name, method_name, tuple(helpers))
    cached = _remaining_a_METHODS.get(key)
    if cached is not None:
        return cached
    path, text, tree = _remaining_a_tree(relpath)
    body = []
    for node in tree.body:
        if isinstance(node, (_remaining_a_ast.FunctionDef, _remaining_a_ast.AsyncFunctionDef)) and node.name in helpers:
            body.append(_remaining_a_copy.deepcopy(node))
        if not isinstance(node, _remaining_a_ast.ClassDef) or node.name != class_name:
            continue
        for item in node.body:
            if isinstance(item, (_remaining_a_ast.FunctionDef, _remaining_a_ast.AsyncFunctionDef)) and item.name == method_name:
                method = _remaining_a_copy.deepcopy(item)
                method.decorator_list = []
                body.append(method)
    if not body or not any((getattr(node, 'name', None) == method_name for node in body)):
        raise RuntimeError(f'{class_name}.{method_name} not found in upstream {path}')
    import torch
    namespace = {'io': _remaining_a_io, 'torch': torch}
    exec(compile(_remaining_a_ast.Module(body=body, type_ignores=[]), f'<kjnodes.{class_name}.{method_name}>', 'exec'), namespace)
    _remaining_a_METHODS[key] = namespace[method_name]
    return namespace[method_name]

async def _remaining_a_read_value(ref):
    value = getattr(ref, 'value', None)
    if value is not None:
        return await value()
    return await ref.raw()

class ConditioningMultiCombineSecure(_remaining_a_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_a_io.Schema:
        return _remaining_a_io.Schema(node_id='ConditioningMultiCombineSecure', display_name='🔒 Conditioning Multi Combine (secure)', category='KJNodes/masking/conditioning', description='Combines multiple conditioning nodes into one', accept_all_inputs=True, inputs=[_remaining_a_io.Int.Input('inputcount', default=2, min=2, max=20, step=1), _remaining_a_io.Combo.Input('operation', options=['combine', 'concat'], default='combine'), _remaining_a_io.Conditioning.Input('conditioning_1'), _remaining_a_io.Conditioning.Input('conditioning_2')], outputs=[_remaining_a_io.Conditioning.Output('combined'), _remaining_a_io.Int.Output('inputcount')])

    @classmethod
    async def execute(cls, inputcount, operation, conditioning_1, conditioning_2, **kwargs) -> _remaining_a_io.NodeOutput:
        conditionings = {'conditioning_1': conditioning_1, 'conditioning_2': conditioning_2, **kwargs}
        combined = conditioning_1
        for index in range(2, inputcount + 1):
            other = conditionings[f'conditioning_{index}']
            if operation == 'combine':
                combined = await combined.combine(other)
            elif operation == 'concat':
                combined = await combined.concat(other)
            else:
                raise ValueError(f'unknown conditioning operation {operation!r}')
        return _remaining_a_io.NodeOutput(combined, inputcount)

def _remaining_a_mask_inputs(count: int):
    inputs = []
    for index in range(1, count + 1):
        inputs.extend([_remaining_a_io.Conditioning.Input(f'positive_{index}'), _remaining_a_io.Conditioning.Input(f'negative_{index}')])
    inputs.extend((_remaining_a_io.Mask.Input(f'mask_{index}') for index in range(1, count + 1)))
    inputs.extend((_remaining_a_io.Float.Input(f'mask_{index}_strength', default=1.0, min=0.0, max=10.0, step=0.01) for index in range(1, count + 1)))
    inputs.append(_remaining_a_io.Combo.Input('set_cond_area', options=['default', 'mask bounds'], default='default'))
    return inputs

class _remaining_a_ConditioningSetMaskBase(_remaining_a_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)
    COUNT = 0
    ORIGINAL = ''
    NODE_ID = ''
    DISPLAY_NAME = ''

    @classmethod
    def define_schema(cls) -> _remaining_a_io.Schema:
        return _remaining_a_io.Schema(node_id=cls.NODE_ID, display_name=cls.DISPLAY_NAME, category='KJNodes/masking/conditioning', description='Bundles multiple conditioning mask and combine nodes into one, with the same behavior as ComfyUI native nodes.', inputs=_remaining_a_mask_inputs(cls.COUNT), outputs=[_remaining_a_io.Conditioning.Output('combined_positive'), _remaining_a_io.Conditioning.Output('combined_negative')])

    @classmethod
    async def execute(cls, **kwargs) -> _remaining_a_io.NodeOutput:
        values = dict(kwargs)
        for index in range(1, cls.COUNT + 1):
            values[f'positive_{index}'] = await kwargs[f'positive_{index}'].value()
            values[f'negative_{index}'] = await kwargs[f'negative_{index}'].value()
            values[f'mask_{index}'] = await kwargs[f'mask_{index}'].raw()
        append = _remaining_a_upstream('nodes/nodes.py', cls.ORIGINAL, 'append', helpers=('append_helper',))
        positive, negative = append(None, **values)
        return _remaining_a_io.NodeOutput(await _remaining_a_sdk.CondRef.from_value(positive), await _remaining_a_sdk.CondRef.from_value(negative))

class ConditioningSetMaskAndCombineSecure(_remaining_a_ConditioningSetMaskBase):
    COUNT = 2
    ORIGINAL = 'ConditioningSetMaskAndCombine'
    NODE_ID = 'ConditioningSetMaskAndCombineSecure'
    DISPLAY_NAME = '🔒 Conditioning Set Mask And Combine (secure)'

class ConditioningSetMaskAndCombine3Secure(_remaining_a_ConditioningSetMaskBase):
    COUNT = 3
    ORIGINAL = 'ConditioningSetMaskAndCombine3'
    NODE_ID = 'ConditioningSetMaskAndCombine3Secure'
    DISPLAY_NAME = '🔒 Conditioning Set Mask And Combine 3 (secure)'

class ConditioningSetMaskAndCombine4Secure(_remaining_a_ConditioningSetMaskBase):
    COUNT = 4
    ORIGINAL = 'ConditioningSetMaskAndCombine4'
    NODE_ID = 'ConditioningSetMaskAndCombine4Secure'
    DISPLAY_NAME = '🔒 Conditioning Set Mask And Combine 4 (secure)'

class ConditioningSetMaskAndCombine5Secure(_remaining_a_ConditioningSetMaskBase):
    COUNT = 5
    ORIGINAL = 'ConditioningSetMaskAndCombine5'
    NODE_ID = 'ConditioningSetMaskAndCombine5Secure'
    DISPLAY_NAME = '🔒 Conditioning Set Mask And Combine 5 (secure)'
_remaining_a_DIMENSION_PRESETS = ['512 x 512 (1:1)', '768 x 512 (1.5:1)', '960 x 512 (1.875:1)', '1024 x 512 (2:1)', '1024 x 576 (1.778:1)', '1536 x 640 (2.4:1)', '1344 x 768 (1.75:1)', '1216 x 832 (1.46:1)', '1152 x 896 (1.286:1)', '1024 x 1024 (1:1)']

class EmptyLatentImagePresetsSecure(_remaining_a_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _remaining_a_io.Schema:
        return _remaining_a_io.Schema(node_id='EmptyLatentImagePresetsSecure', display_name='🔒 Empty Latent Image Presets (secure)', category='KJNodes/latents', inputs=[_remaining_a_io.Combo.Input('dimensions', options=_remaining_a_DIMENSION_PRESETS, default=_remaining_a_DIMENSION_PRESETS[0]), _remaining_a_io.Boolean.Input('invert', default=False), _remaining_a_io.Int.Input('batch_size', default=1, min=1, max=4096)], outputs=[_remaining_a_io.Latent.Output('latent', display_name='Latent'), _remaining_a_io.Int.Output('width', display_name='Width'), _remaining_a_io.Int.Output('height', display_name='Height')])

    @classmethod
    async def execute(cls, dimensions, invert, batch_size) -> _remaining_a_io.NodeOutput:
        import torch
        parts = [part.strip() for part in dimensions.split('x')]
        first = parts[0].split('(')[0].strip()
        second = parts[1].split('(')[0].strip().split(' ')[0]
        width, height = (int(second), int(first)) if invert else (int(first), int(second))
        latent = {'samples': torch.zeros([batch_size, 4, height // 8, width // 8], dtype=torch.float32), 'downscale_ratio_spacial': 8}
        return _remaining_a_io.NodeOutput(await _remaining_a_sdk.LatentRef.from_value(latent), width, height)

class GetTrackRangeSecure(_remaining_a_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _remaining_a_io.Schema:
        return _remaining_a_io.Schema(node_id='GetTrackRangeSecure', display_name='🔒 Get Track Range (secure)', category='conditioning/video_models', inputs=[_remaining_a_io.Tracks.Input('tracks'), _remaining_a_io.Int.Input('start_index', default=24, min=-10000, max=10000, step=1), _remaining_a_io.Int.Input('num_frames', default=10, min=1, max=10000, step=1)], outputs=[_remaining_a_io.Tracks.Output('tracks')])

    @classmethod
    async def execute(cls, tracks, start_index, num_frames) -> _remaining_a_io.NodeOutput:
        execute = _remaining_a_upstream('nodes/nodes.py', 'GetTrackRange', 'execute')
        out = execute(None, await tracks.value(), start_index, num_frames)
        return _remaining_a_io.NodeOutput(await _remaining_a_sdk.ValueRef.from_value(out.result[0]))

class AddNoiseToTrackPathSecure(_remaining_a_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _remaining_a_io.Schema:
        return _remaining_a_io.Schema(node_id='AddNoiseToTrackPathSecure', display_name='🔒 Add Noise To Track (secure)', category='conditioning/video_models', inputs=[_remaining_a_io.Tracks.Input('tracks'), _remaining_a_io.Float.Input('strength', default=1.0, min=0.0, max=100.0, step=0.01), _remaining_a_io.Int.Input('seed', default=0, min=0, max=18446744073709551615, step=1), _remaining_a_io.Float.Input('noise_x_ratio', default=1.0, min=0.0, max=100.0, step=0.01), _remaining_a_io.Float.Input('noise_y_ratio', default=1.0, min=0.0, max=100.0, step=0.01), _remaining_a_io.Float.Input('noise_temporal_ratio', default=1.0, min=0.0, max=100.0, step=0.01)], outputs=[_remaining_a_io.Tracks.Output('tracks')])

    @classmethod
    async def execute(cls, tracks, strength, seed, noise_x_ratio, noise_y_ratio, noise_temporal_ratio) -> _remaining_a_io.NodeOutput:
        execute = _remaining_a_upstream('nodes/nodes.py', 'AddNoiseToTrackPath', 'execute')
        out = execute(None, await tracks.value(), strength, seed, noise_x_ratio, noise_y_ratio, noise_temporal_ratio)
        return _remaining_a_io.NodeOutput(await _remaining_a_sdk.ValueRef.from_value(out.result[0]))

class AudioConcatenateSecure(_remaining_a_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _remaining_a_io.Schema:
        return _remaining_a_io.Schema(node_id='AudioConcatenateSecure', display_name='🔒 Audio Concatenate (secure)', category='KJNodes/audio', description='Concatenates audio1 to audio2 in the specified direction.', inputs=[_remaining_a_io.Audio.Input('audio1'), _remaining_a_io.Audio.Input('audio2'), _remaining_a_io.Combo.Input('direction', options=['right', 'left'], default='right')], outputs=[_remaining_a_io.Audio.Output('audio')])

    @classmethod
    async def execute(cls, audio1, audio2, direction) -> _remaining_a_io.NodeOutput:
        concatenate = _remaining_a_upstream('nodes/nodes.py', 'AudioConcatenate', 'concanate')
        out = concatenate(None, await audio1.value(), await audio2.value(), direction)
        return _remaining_a_io.NodeOutput(await _remaining_a_sdk.AudioRef.from_value(out[0]))
from comfy_api.latest import io as _remaining_e_io, sdk as _remaining_e_sdk
from ._tensor_utils import conditioning_set_values as _remaining_e_conditioning_set_values, wan21_process_out as _remaining_e_wan21_process_out

class VAEDecodeLoopKJSecure(_remaining_e_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _remaining_e_io.Schema:
        return _remaining_e_io.Schema(node_id='VAEDecodeLoopKJSecure', display_name='🔒 VAE Decode Loop KJ (secure)', category='KJNodes/vae', description='Video latent VAE decoding to fix artifacts on loop seams.', inputs=[_remaining_e_io.Latent.Input('samples', tooltip='The latent to be decoded.'), _remaining_e_io.Vae.Input('vae', tooltip='The VAE model used for decoding the latent.'), _remaining_e_io.Int.Input('overlap_latent_frames', default=2, min=2, max=8, step=1, tooltip='Number of frames to blend for seamless loops. Wan 2 uses 2 and HunyuanVideo 1.5 should use 4.')], outputs=[_remaining_e_io.Image.Output('images', tooltip='The decoded images.')])

    @classmethod
    async def execute(cls, samples, vae, overlap_latent_frames) -> _remaining_e_io.NodeOutput:
        import torch
        latent_value = await samples.value()
        latents = latent_value['samples']
        images_ref = await vae.decode(samples)
        images = await images_ref.raw()
        if overlap_latent_frames <= 0:
            if len(images.shape) == 5:
                images = images.reshape(-1, images.shape[-3], images.shape[-2], images.shape[-1])
            return _remaining_e_io.NodeOutput(await _remaining_e_sdk.ImageRef._from_raw(images))
        end_frames = overlap_latent_frames + 1
        start_frames = overlap_latent_frames
        seam_latents = torch.cat([latents[:, :, -end_frames:], latents[:, :, :start_frames]], dim=2)
        seam_ref = await _remaining_e_sdk.LatentRef.from_value({'samples': seam_latents})
        seam_images_ref = await vae.decode(seam_ref)
        seam_images = (await seam_images_ref.raw()).cpu().float()
        total_concat = end_frames + start_frames
        temp_start = total_concat * 2 - 1
        main_start = total_concat + (overlap_latent_frames if overlap_latent_frames > 2 else 0)
        images = torch.cat([seam_images[:, temp_start:].to(images), images[:, main_start:]], dim=1)
        if len(images.shape) == 5:
            images = images.reshape(-1, images.shape[-3], images.shape[-2], images.shape[-1])
        return _remaining_e_io.NodeOutput(await _remaining_e_sdk.ImageRef._from_raw(images))

class WanImageToVideoSVIProSecure(_remaining_e_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _remaining_e_io.Schema:
        return _remaining_e_io.Schema(node_id='WanImageToVideoSVIProSecure', display_name='🔒 Wan Image To Video SVI Pro (secure)', category='conditioning/video_models', inputs=[_remaining_e_io.Conditioning.Input('positive'), _remaining_e_io.Conditioning.Input('negative'), _remaining_e_io.Int.Input('length', default=81, min=1, max=16384, step=4), _remaining_e_io.Latent.Input('anchor_samples'), _remaining_e_io.Latent.Input('prev_samples', optional=True), _remaining_e_io.Int.Input('motion_latent_count', default=1, min=0, max=128, step=1)], outputs=[_remaining_e_io.Conditioning.Output('positive'), _remaining_e_io.Conditioning.Output('negative'), _remaining_e_io.Latent.Output('latent')])

    @classmethod
    async def execute(cls, positive, negative, length, anchor_samples, motion_latent_count, prev_samples=None) -> _remaining_e_io.NodeOutput:
        import torch
        positive_value = await positive.value()
        negative_value = await negative.value()
        anchor_value = await anchor_samples.value()
        prev_value = None if prev_samples is None else await prev_samples.value()
        anchor_latent = anchor_value['samples'].clone()
        batch, channels, _, height, width = anchor_latent.shape
        total_latents = (length - 1) // 4 + 1
        device = anchor_latent.device
        dtype = anchor_latent.dtype
        empty_latent = torch.zeros([batch, 16, total_latents, height, width], device=device)
        if prev_value is None or motion_latent_count == 0:
            padding_size = total_latents - anchor_latent.shape[2]
            image_cond_latent = anchor_latent
        else:
            motion_latent = prev_value['samples'][:, :, -motion_latent_count:].clone()
            padding_size = total_latents - anchor_latent.shape[2] - motion_latent.shape[2]
            image_cond_latent = torch.cat([anchor_latent, motion_latent], dim=2)
        padding = torch.zeros(1, channels, padding_size, height, width, dtype=dtype, device=device)
        padding = _remaining_e_wan21_process_out(padding)
        image_cond_latent = torch.cat([image_cond_latent, padding], dim=2)
        mask = torch.ones((1, 1, total_latents, height, width), device=device, dtype=dtype)
        mask[:, :, :1] = 0.0
        values = {'concat_latent_image': image_cond_latent, 'concat_mask': mask}
        positive_out = _remaining_e_conditioning_set_values(positive_value, values)
        negative_out = _remaining_e_conditioning_set_values(negative_value, values)
        return _remaining_e_io.NodeOutput(await _remaining_e_sdk.CondRef.from_value(positive_out), await _remaining_e_sdk.CondRef.from_value(negative_out), await _remaining_e_sdk.LatentRef.from_value({'samples': empty_latent}))
import math as _remaining_i_math
import torch as _remaining_i_torch
from comfy_api.latest import io as _remaining_i_io, sdk as _remaining_i_sdk
from ._tensor_utils import common_upscale as _remaining_i_common_upscale

def _remaining_i_points(value):
    result = []
    for item in value.rstrip(',\n').split(','):
        frame, angle = item.split(':')
        result.append((int(frame.strip()), float(angle.strip()[1:-1])))
    result.sort(key=lambda item: item[0])
    return result

def _remaining_i_ease(value, mode):
    if mode == 'ease_in':
        return value * value
    if mode == 'ease_out':
        return 1 - (1 - value) * (1 - value)
    if mode == 'ease_in_out':
        return 3 * value * value - 2 * value * value * value
    return value

def _remaining_i_schedule(points, count, interpolation, wrap):
    values = []
    next_point = 1
    for frame in range(count):
        while next_point < len(points) and frame >= points[next_point][0]:
            next_point += 1
        if next_point == len(points):
            next_point -= 1
        previous = max(next_point - 1, 0)
        start_frame, start_value = points[previous]
        end_frame, end_value = points[next_point]
        if end_frame == start_frame:
            values.append(start_value)
            continue
        fraction = _remaining_i_ease((frame - start_frame) / (end_frame - start_frame), interpolation)
        if wrap:
            difference = (end_value - start_value + 540) % 360 - 180
            value = (start_value + fraction * difference + 180) % 360 - 180
        else:
            value = start_value + (end_value - start_value) * fraction
        values.append(value)
    return values

def _remaining_i_camera_embeddings(elevation, azimuth, device, dtype):
    elevation = _remaining_i_torch.as_tensor([elevation], device=device, dtype=dtype)
    azimuth = _remaining_i_torch.as_tensor([azimuth], device=device, dtype=dtype)
    return _remaining_i_torch.stack([_remaining_i_torch.deg2rad(-elevation), _remaining_i_torch.sin(_remaining_i_torch.deg2rad(azimuth)), _remaining_i_torch.cos(_remaining_i_torch.deg2rad(azimuth)), _remaining_i_torch.deg2rad(_remaining_i_torch.full_like(elevation, 90))], dim=-1).unsqueeze(1)

async def _remaining_i_encode_inputs(clip_vision, init_image, vae, width, height):
    output = await clip_vision.encode_image(init_image)
    embeds_ref = await output.image_embeds()
    pooled = (await embeds_ref.raw()).unsqueeze(0)
    image = await init_image.raw()
    pixels = _remaining_i_common_upscale(image.movedim(-1, 1), width, height, 'bilinear', 'center').movedim(1, -1)[..., :3]
    pixels_ref = await _remaining_i_sdk.ImageRef._from_raw(pixels)
    encoded_ref = await vae.encode(pixels_ref)
    encoded = (await encoded_ref.value())['samples']
    return (pooled, encoded)

class GenerateNoiseSecure(_remaining_i_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return _remaining_i_io.Schema(node_id='GenerateNoiseSecure', display_name='🔒 Generate Noise (secure)', category='KJNodes/noise', inputs=[_remaining_i_io.Int.Input('width', default=512, min=16, max=4096, step=1), _remaining_i_io.Int.Input('height', default=512, min=16, max=4096, step=1), _remaining_i_io.Int.Input('batch_size', default=1, min=1, max=4096), _remaining_i_io.Int.Input('seed', default=123, min=0, max=18446744073709551615, step=1), _remaining_i_io.Float.Input('multiplier', default=1.0, min=0.0, max=4096.0, step=0.01), _remaining_i_io.Boolean.Input('constant_batch_noise', default=False), _remaining_i_io.Boolean.Input('normalize', default=False), _remaining_i_io.Model.Input('model', optional=True), _remaining_i_io.Sigmas.Input('sigmas', optional=True), _remaining_i_io.Combo.Input('latent_channels', options=['4', '16'], default='4', optional=True), _remaining_i_io.Combo.Input('shape', options=['BCHW', 'BCTHW', 'BTCHW'], default='BCHW', optional=True)], outputs=[_remaining_i_io.Latent.Output(display_name='latent')])

    @classmethod
    async def execute(cls, width, height, batch_size, seed, multiplier, constant_batch_noise, normalize, model=None, sigmas=None, latent_channels='4', shape='BCHW'):
        generator = _remaining_i_torch.manual_seed(seed)
        channels = int(latent_channels)
        if shape == 'BCHW':
            dimensions = [batch_size, channels, height // 8, width // 8]
        elif shape == 'BCTHW':
            dimensions = [1, channels, batch_size, height // 8, width // 8]
        else:
            dimensions = [1, batch_size, channels, height // 8, width // 8]
        noise = _remaining_i_torch.randn(dimensions, dtype=_remaining_i_torch.float32, layout=_remaining_i_torch.strided, generator=generator, device='cpu')
        if sigmas is not None:
            if model is None:
                raise ValueError('model is required when sigmas are connected')
            sigma_values = await sigmas.raw()
            scale = await model.latent_scale_factor()
            noise *= (sigma_values[0] - sigma_values[-1]) / scale
        noise *= multiplier
        if normalize:
            noise = noise / noise.std()
        if constant_batch_noise:
            noise = noise[0].repeat(batch_size, 1, 1, 1)
        return _remaining_i_io.NodeOutput(await _remaining_i_sdk.LatentRef.from_value({'samples': noise}))

class StableZero123BatchScheduleSecure(_remaining_i_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return _remaining_i_schedule_schema('StableZero123_BatchScheduleSecure', '🔒 Stable Zero123 Batch Schedule (secure)', 256, 1, '0:(0.0),\n7:(1.0),\n15:(0.0)\n', '0:(0.0),\n7:(0.0),\n15:(0.0)\n')

    @classmethod
    async def execute(cls, clip_vision, init_image, vae, width, height, batch_size, azimuth_points_string, elevation_points_string, interpolation):
        pooled, encoded = await _remaining_i_encode_inputs(clip_vision, init_image, vae, width, height)
        azimuths = _remaining_i_schedule(_remaining_i_points(azimuth_points_string), batch_size, interpolation, True)
        elevations = _remaining_i_schedule(_remaining_i_points(elevation_points_string), batch_size, interpolation, True)
        positive_cond = []
        for elevation, azimuth in zip(elevations, azimuths):
            camera = _remaining_i_camera_embeddings(elevation, azimuth, pooled.device, pooled.dtype)
            positive_cond.append(_remaining_i_torch.cat([pooled, camera.repeat((pooled.shape[0], 1, 1))], dim=-1))
        positive = [[_remaining_i_torch.cat(positive_cond, dim=0), {'concat_latent_image': _remaining_i_torch.cat([encoded for _ in range(batch_size)], dim=0)}]]
        negative = [[_remaining_i_torch.cat([_remaining_i_torch.zeros_like(pooled) for _ in range(batch_size)], dim=0), {'concat_latent_image': _remaining_i_torch.cat([_remaining_i_torch.zeros_like(encoded) for _ in range(batch_size)], dim=0)}]]
        latent = {'samples': _remaining_i_torch.zeros([batch_size, 4, height // 8, width // 8])}
        return _remaining_i_io.NodeOutput(await _remaining_i_sdk.CondRef.from_value(positive), await _remaining_i_sdk.CondRef.from_value(negative), await _remaining_i_sdk.LatentRef.from_value(latent))

class SV3DBatchScheduleSecure(_remaining_i_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return _remaining_i_schedule_schema('SV3D_BatchScheduleSecure', '🔒 SV3D Batch Schedule (secure)', 576, 21, '0:(0.0),\n9:(180.0),\n20:(360.0)\n', '0:(0.0),\n9:(0.0),\n20:(0.0)\n')

    @classmethod
    async def execute(cls, clip_vision, init_image, vae, width, height, batch_size, azimuth_points_string, elevation_points_string, interpolation):
        pooled, encoded = await _remaining_i_encode_inputs(clip_vision, init_image, vae, width, height)
        azimuths = _remaining_i_schedule(_remaining_i_points(azimuth_points_string), batch_size, interpolation, False)
        elevations = _remaining_i_schedule(_remaining_i_points(elevation_points_string), batch_size, interpolation, False)
        positive = [[pooled, {'concat_latent_image': encoded, 'elevation': elevations, 'azimuth': azimuths}]]
        negative = [[_remaining_i_torch.zeros_like(pooled), {'concat_latent_image': _remaining_i_torch.zeros_like(encoded), 'elevation': elevations, 'azimuth': azimuths}]]
        latent = {'samples': _remaining_i_torch.zeros([batch_size, 4, height // 8, width // 8])}
        return _remaining_i_io.NodeOutput(await _remaining_i_sdk.CondRef.from_value(positive), await _remaining_i_sdk.CondRef.from_value(negative), await _remaining_i_sdk.LatentRef.from_value(latent))

def _remaining_i_schedule_schema(node_id, display_name, size, batch, azimuth, elevation):
    return _remaining_i_io.Schema(node_id=node_id, display_name=display_name, category='KJNodes/experimental', inputs=[_remaining_i_io.ClipVision.Input('clip_vision'), _remaining_i_io.Image.Input('init_image'), _remaining_i_io.Vae.Input('vae'), _remaining_i_io.Int.Input('width', default=size, min=16, max=16384, step=8), _remaining_i_io.Int.Input('height', default=size, min=16, max=16384, step=8), _remaining_i_io.Int.Input('batch_size', default=batch, min=1, max=4096), _remaining_i_io.Combo.Input('interpolation', options=['linear', 'ease_in', 'ease_out', 'ease_in_out'], default='linear'), _remaining_i_io.String.Input('azimuth_points_string', default=azimuth, multiline=True), _remaining_i_io.String.Input('elevation_points_string', default=elevation, multiline=True)], outputs=[_remaining_i_io.Conditioning.Output('positive', display_name='positive'), _remaining_i_io.Conditioning.Output('negative', display_name='negative'), _remaining_i_io.Latent.Output('latent', display_name='latent')])

class SetShakkerLabsUnionControlNetTypeSecure(_remaining_i_io.ComfyNode):
    SDK_REFS = True
    _TYPES = {'canny': 0, 'tile': 1, 'depth': 2, 'blur': 3, 'pose': 4, 'gray': 5, 'low quality': 6}

    @classmethod
    def define_schema(cls):
        return _remaining_i_io.Schema(node_id='SetShakkerLabsUnionControlNetTypeSecure', display_name='🔒 Set Shakker Labs Union ControlNet Type (secure)', category='conditioning/controlnet', inputs=[_remaining_i_io.ControlNet.Input('control_net'), _remaining_i_io.Combo.Input('type', options=['auto', *cls._TYPES], default='auto')], outputs=[_remaining_i_io.ControlNet.Output(display_name='control_net')])

    @classmethod
    async def execute(cls, control_net, type):
        return _remaining_i_io.NodeOutput(await control_net.with_union_type(cls._TYPES.get(type)))
from comfy_api.latest import io as _remaining_j_io, sdk as _remaining_j_sdk

def _remaining_j_format_value(value, decimals):
    if isinstance(value, float):
        return f'{value:.{decimals}f}'
    return str(value)

def _remaining_j_format_widget_values(values, widget_name, return_all, decimals, target):
    widget_names = [name.strip() for name in widget_name.split(',') if name.strip()]
    if return_all:
        return ', '.join((f'{name}: {_remaining_j_format_value(value, decimals)}' for name, value in values.items()))
    if len(widget_names) == 1:
        name = widget_names[0]
        if name not in values:
            raise NameError(f'Widget not found: {target}.{name}')
        return _remaining_j_format_value(values[name], decimals)
    if len(widget_names) > 1:
        missing = next((name for name in widget_names if name not in values), None)
        if missing is not None:
            raise NameError(f'Widget not found: {target}.{missing}')
        return ', '.join((f'{name}: {_remaining_j_format_value(values[name], decimals)}' for name in widget_names))
    raise NameError(f'Widget not found: {target}.{widget_name}')

class WidgetToStringSecure(_remaining_j_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('graph',)

    @classmethod
    def define_schema(cls) -> _remaining_j_io.Schema:
        return _remaining_j_io.Schema(node_id='WidgetToStringSecure', display_name='🔒 Widget To String (secure)', category='KJNodes/text', description='Selects a node by id, title, or input link and returns one or more of its widget values as a string.', inputs=[_remaining_j_io.Int.Input('id', default=0, min=0, max=100000, step=1), _remaining_j_io.String.Input('widget_name', multiline=False), _remaining_j_io.Boolean.Input('return_all', default=False), _remaining_j_io.AnyType.Input('any_input', optional=True), _remaining_j_io.String.Input('node_title', default='', multiline=False, optional=True), _remaining_j_io.Int.Input('allowed_float_decimals', default=2, min=0, max=10, optional=True, tooltip='Number of decimal places to display for float values.')], outputs=[_remaining_j_io.String.Output()])

    @classmethod
    def fingerprint_inputs(cls, id, node_title='', any_input=None, **kwargs):
        if any_input is not None and (id != 0 or node_title != ''):
            return float('nan')

    @classmethod
    async def execute(cls, id, widget_name, return_all, any_input=None, node_title='', allowed_float_decimals=2) -> _remaining_j_io.NodeOutput:
        values = await _remaining_j_sdk.ctx().graph.widget_values(node_id=id, node_title=node_title, linked_input='any_input')
        target = id if id else node_title or 'linked input'
        result = _remaining_j_format_widget_values(values, widget_name, return_all, allowed_float_decimals, target)
        return _remaining_j_io.NodeOutput(result)
from comfy_api.latest import io as _remaining_l_io

class StyleModelApplyAdvancedSecure(_remaining_l_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_l_io.Schema:
        return _remaining_l_io.Schema(node_id='StyleModelApplyAdvancedSecure', display_name='🔒 Style Model Apply Advanced (secure)', category='KJNodes/experimental', description='StyleModelApply with an adjustable strength.', inputs=[_remaining_l_io.Conditioning.Input('conditioning'), _remaining_l_io.StyleModel.Input('style_model'), _remaining_l_io.ClipVisionOutput.Input('clip_vision_output'), _remaining_l_io.Float.Input('strength', default=1.0, min=-10.0, max=10.0, step=0.001)], outputs=[_remaining_l_io.Conditioning.Output(display_name='conditioning')])

    @classmethod
    async def execute(cls, conditioning, style_model, clip_vision_output, strength=1.0) -> _remaining_l_io.NodeOutput:
        result = await style_model.apply(clip_vision_output, conditioning, strength)
        return _remaining_l_io.NodeOutput(result)
import ast as _remaining_n_ast
import copy as _remaining_n_copy
import pathlib as _remaining_n_pathlib
from comfy_api.latest import io as _remaining_n_io, sdk as _remaining_n_sdk
from . import _packload as _remaining_n_packload
_remaining_n_CAMERA_CLASS = None
_remaining_n_CameraCtrlPoses = _remaining_n_io.Custom('CAMERACTRL_POSES')

def _remaining_n_camera_visualizer_class():
    global _remaining_n_CAMERA_CLASS
    if _remaining_n_CAMERA_CLASS is not None:
        return _remaining_n_CAMERA_CLASS
    path = _remaining_n_pathlib.Path(_remaining_n_packload.ROOT).resolve() / 'nodes' / 'nodes.py'
    tree = _remaining_n_ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    source_class = next((_remaining_n_copy.deepcopy(node) for node in tree.body if isinstance(node, _remaining_n_ast.ClassDef) and node.name == 'CameraPoseVisualizer'), None)
    if source_class is None:
        raise RuntimeError(f'CameraPoseVisualizer not found in {path}')
    import logging
    import time
    from io import BytesIO, StringIO
    import numpy as np
    from PIL import Image

    def open_pose(content, *_args, **_kwargs):
        return StringIO(content)
    namespace = {'BytesIO': BytesIO, 'Image': Image, 'logging': logging, 'np': np, 'open': open_pose, 'time': time}
    module = _remaining_n_ast.fix_missing_locations(_remaining_n_ast.Module(body=[source_class], type_ignores=[]))
    exec(compile(module, f'<kjnodes.CameraPoseVisualizer:{path}>', 'exec'), namespace)
    _remaining_n_CAMERA_CLASS = namespace['CameraPoseVisualizer']
    return _remaining_n_CAMERA_CLASS

async def _remaining_n_value(ref):
    if ref is None:
        return None
    reader = getattr(ref, 'value', None)
    if reader is None:
        return ref
    return await reader()

class EmptyLatentImageCustomPresetsSecure(_remaining_n_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _remaining_n_io.Schema:
        return _remaining_n_io.Schema(node_id='EmptyLatentImageCustomPresetsSecure', display_name='🔒 Empty Latent Image Custom Presets (secure)', category='KJNodes/latents', description="Creates an empty latent from a named custom dimension in the form 'label - width x height'.", inputs=[_remaining_n_io.String.Input('dimensions', default='custom - 512 x 512', tooltip='Named dimensions: label - width x height'), _remaining_n_io.Boolean.Input('invert', default=False), _remaining_n_io.Int.Input('batch_size', default=1, min=1, max=4096, step=1)], outputs=[_remaining_n_io.Latent.Output('latent', display_name='Latent'), _remaining_n_io.Int.Output('width', display_name='Width'), _remaining_n_io.Int.Output('height', display_name='Height')])

    @classmethod
    async def execute(cls, dimensions, invert, batch_size) -> _remaining_n_io.NodeOutput:
        import torch
        _label, value = dimensions.split(' - ')
        width, height = [part.strip() for part in value.split('x')]
        if invert:
            width, height = (height, width)
        width_int = int(width)
        height_int = int(height)
        latent = {'samples': torch.zeros([batch_size, 4, height_int // 8, width_int // 8], dtype=torch.float32), 'downscale_ratio_spacial': 8}
        return _remaining_n_io.NodeOutput(await _remaining_n_sdk.LatentRef.from_value(latent), width_int, height_int)

class CameraPoseVisualizerSecure(_remaining_n_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('assets', 'raw')

    @classmethod
    def define_schema(cls) -> _remaining_n_io.Schema:
        return _remaining_n_io.Schema(node_id='CameraPoseVisualizerSecure', display_name='🔒 Camera Pose Visualizer (secure)', category='KJNodes/misc', description='Visualizes CameraCtrl poses or a user-selected RealEstate pose file without exposing its host path.', inputs=[_remaining_n_io.Combo.Input('pose_file', options=[], default='', upload=_remaining_n_io.UploadType.model, image_folder=_remaining_n_io.FolderType.input, tooltip='Logical name of a pose file in the input folder'), _remaining_n_io.Float.Input('base_xval', default=0.2, min=0.0, max=100.0, step=0.01), _remaining_n_io.Float.Input('zval', default=0.3, min=0.0, max=100.0, step=0.01), _remaining_n_io.Float.Input('scale', default=1.0, min=0.01, max=10.0, step=0.01), _remaining_n_io.Boolean.Input('use_exact_fx', default=False), _remaining_n_io.Boolean.Input('relative_c2w', default=True), _remaining_n_io.Boolean.Input('use_viewer', default=False, tooltip='The sandbox returns the rendered image and does not open a host window.'), _remaining_n_CameraCtrlPoses.Input('cameractrl_poses', optional=True)], outputs=[_remaining_n_io.Image.Output('image')])

    @classmethod
    async def execute(cls, pose_file, base_xval, zval, scale, use_exact_fx, relative_c2w, use_viewer, cameractrl_poses=None) -> _remaining_n_io.NodeOutput:
        pose_content = ''
        if pose_file:
            assets = _remaining_n_sdk.ctx().assets
            asset = await assets.resolve('input', pose_file)
            pose_content = (await assets.read_bytes(asset)).decode('utf-8')
        poses = await _remaining_n_value(cameractrl_poses)
        visualizer = _remaining_n_camera_visualizer_class()()
        try:
            image = visualizer.plot(pose_content, scale, base_xval, zval, use_exact_fx, relative_c2w, False, poses)[0]
        finally:
            import matplotlib.pyplot as plt
            figure = getattr(visualizer, 'fig', None)
            if figure is not None:
                plt.close(figure)
        return _remaining_n_io.NodeOutput(await _remaining_n_sdk.ImageRef._from_raw(image))
from comfy_api.latest import io as _remaining_o_io

class VAEMergeKJSecure(_remaining_o_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls):
        return _remaining_o_io.Schema(node_id='VAEMergeKJSecure', display_name='🔒 VAE Merge KJ (secure)', category='KJNodes/vae', description='Merge two VAEs by weighted-averaging matching weights.', inputs=[_remaining_o_io.Vae.Input('vae_1'), _remaining_o_io.Vae.Input('vae_2'), _remaining_o_io.Float.Input('ratio', default=0.5, min=0.0, max=1.0, step=0.01)], outputs=[_remaining_o_io.Vae.Output(display_name='vae')])

    @classmethod
    async def execute(cls, vae_1, vae_2, ratio):
        return _remaining_o_io.NodeOutput(await vae_1.merge(vae_2, ratio))
import ast as _remaining_t_ast
import pathlib as _remaining_t_pathlib
from io import BytesIO as _remaining_t_BytesIO
from comfy_api.latest import io as _remaining_t_io, sdk as _remaining_t_sdk
from . import _packload as _remaining_t_packload
_remaining_t_PLAY_SOUND_CLASS = None

def _remaining_t_play_sound_class():
    global _remaining_t_PLAY_SOUND_CLASS
    if _remaining_t_PLAY_SOUND_CLASS is not None:
        return _remaining_t_PLAY_SOUND_CLASS
    path = _remaining_t_pathlib.Path(_remaining_t_packload.ROOT).resolve() / 'nodes' / 'nodes.py'
    tree = _remaining_t_ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    source_class = next((node for node in tree.body if isinstance(node, _remaining_t_ast.ClassDef) and node.name == 'PlaySoundKJ'))
    execute = next((node for node in source_class.body if isinstance(node, _remaining_t_ast.FunctionDef) and node.name == 'execute'))
    preview_index = next((index for index, statement in enumerate(execute.body) if isinstance(statement, _remaining_t_ast.Assign) and any((isinstance(target, _remaining_t_ast.Name) and target.id == 'preview' for target in statement.targets))))
    execute.body[preview_index:] = [_remaining_t_ast.Return(value=_remaining_t_ast.Tuple(elts=[_remaining_t_ast.Name(id='audio', ctx=_remaining_t_ast.Load()), _remaining_t_ast.Name(id='any_input', ctx=_remaining_t_ast.Load())], ctx=_remaining_t_ast.Load()))]
    import math
    import torch
    namespace = {'io': _remaining_t_io, 'math': math, 'torch': torch}
    module = _remaining_t_ast.fix_missing_locations(_remaining_t_ast.Module(body=[source_class], type_ignores=[]))
    exec(compile(module, f'<kjnodes.PlaySoundKJ:{path}>', 'exec'), namespace)
    _remaining_t_PLAY_SOUND_CLASS = namespace['PlaySoundKJ']
    return _remaining_t_PLAY_SOUND_CLASS

class PlaySoundKJSecure(_remaining_t_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('assets', 'raw', 'ui')

    @classmethod
    def define_schema(cls) -> _remaining_t_io.Schema:
        return _remaining_t_io.Schema(node_id='PlaySoundKJSecure', display_name='🔒 Play Sound KJ (secure)', category='KJNodes/audio', description='Plays supplied audio, an input-folder audio asset, or the built-in chime in the browser.', inputs=[_remaining_t_io.AnyType.Input('any_input', optional=True), _remaining_t_io.Audio.Input('audio', optional=True), _remaining_t_io.String.Input('audio_path', default='', tooltip='Logical name of an audio asset in the input folder. Host filesystem paths are not accepted.'), _remaining_t_io.Combo.Input('mode', options=['always', 'on_empty_queue', 'on_change'], default='always'), _remaining_t_io.Float.Input('volume', default=0.5, min=0.0, max=1.0, step=0.01), _remaining_t_io.Float.Input('duration', default=5.0, min=0.0, max=300.0, step=0.1)], outputs=[_remaining_t_io.AnyType.Output('any_output', display_name='any_output')], is_output_node=True)

    @classmethod
    def fingerprint_inputs(cls, **kwargs):
        if kwargs.get('mode') == 'on_change':
            return False
        return float('NaN')

    @classmethod
    async def execute(cls, audio=None, audio_path='', mode='always', volume=0.5, duration=5.0, any_input=None) -> _remaining_t_io.NodeOutput:
        audio_value = None if audio is None else await audio.value()
        if audio_value is None:
            source = ''
            if audio_path:
                assets = _remaining_t_sdk.ctx().assets
                asset = await assets.resolve('input', audio_path)
                source = _remaining_t_BytesIO(await assets.read_bytes(asset))
            audio_value, _ = _remaining_t_play_sound_class().execute(audio=None, audio_path=source, mode=mode, volume=volume, duration=duration, any_input=any_input)
            audio = await _remaining_t_sdk.AudioRef.from_value(audio_value)
        ui_result = await _remaining_t_sdk.ctx().ui.preview_audio(audio)
        ui_result['audio_hash'] = [hash(audio_value['waveform'].sum().item())]
        return _remaining_t_io.NodeOutput(any_input, ui=ui_result)
from comfy_api.latest import io as _remaining_x_io, sdk as _remaining_x_sdk

class VRAMDebugSecure(_remaining_x_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('models.manage',)

    @classmethod
    def define_schema(cls):
        return _remaining_x_io.Schema(node_id='VRAMDebugSecure', display_name='VRAM Debug', category='KJNodes/memory', description='Reports free device memory before and after an approved application memory cleanup.', inputs=[_remaining_x_io.Boolean.Input('empty_cache', default=True), _remaining_x_io.Boolean.Input('gc_collect', default=True), _remaining_x_io.Boolean.Input('unload_all_models', default=False), _remaining_x_io.AnyType.Input('any_input', optional=True), _remaining_x_io.Image.Input('image_pass', optional=True), _remaining_x_io.Model.Input('model_pass', optional=True)], outputs=[_remaining_x_io.AnyType.Output('any_output'), _remaining_x_io.Image.Output('image_pass'), _remaining_x_io.Model.Output('model_pass'), _remaining_x_io.Int.Output('freemem_before'), _remaining_x_io.Int.Output('freemem_after')])

    @classmethod
    async def execute(cls, empty_cache, gc_collect, unload_all_models, any_input=None, image_pass=None, model_pass=None):
        before, after = await _remaining_x_sdk.ctx().models.memory_cleanup(empty_cache=bool(empty_cache), collect_cycles=bool(gc_collect), unload_all_models=bool(unload_all_models))
        return _remaining_x_io.NodeOutput(any_input, image_pass, model_pass, before, after, ui={'text': [f'{before:,.0f}x{after:,.0f}']})
from comfy_api.latest import io as _remaining_y_io, sdk as _remaining_y_sdk

class VAELoaderKJSecure(_remaining_y_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('models',)

    @classmethod
    def define_schema(cls):
        return _remaining_y_io.Schema(node_id='VAELoaderKJSecure', display_name='VAELoader KJ', category='KJNodes/vae', inputs=[_remaining_y_io.Combo.Input('vae_name', options=[], remote=_remaining_y_io.RemoteOptions(route='/models/vae/choices', refresh_button=True)), _remaining_y_io.Combo.Input('device', options=['main_device', 'cpu'], default='main_device'), _remaining_y_io.Combo.Input('weight_dtype', options=['bf16', 'fp16', 'fp32'], default='fp32')], outputs=[_remaining_y_io.Vae.Output('vae')])

    @classmethod
    def validate_inputs(cls, vae_name):
        if not isinstance(vae_name, str) or not vae_name:
            return 'vae_name must be a non-empty catalogue name'
        return True

    @classmethod
    async def execute(cls, vae_name, device, weight_dtype):
        vae = await _remaining_y_sdk.ctx().models.load_vae(str(vae_name), device=str(device), weight_dtype=str(weight_dtype))
        return _remaining_y_io.NodeOutput(vae)
from comfy_api.latest import io as _remaining_za_io, sdk as _remaining_za_sdk

class DifferentialDiffusionAdvancedSecure(_remaining_za_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _remaining_za_io.Schema:
        return _remaining_za_io.Schema(node_id='DifferentialDiffusionAdvancedSecure', display_name='🔒 Differential Diffusion Advanced (secure)', category='_for_testing', inputs=[_remaining_za_io.Model.Input('model'), _remaining_za_io.Latent.Input('samples'), _remaining_za_io.Mask.Input('mask'), _remaining_za_io.Float.Input('multiplier', default=1.0, min=-10.0, max=10.0, step=0.001)], outputs=[_remaining_za_io.Model.Output('model'), _remaining_za_io.Latent.Output('samples')])

    @classmethod
    async def execute(cls, model, samples, mask, multiplier) -> _remaining_za_io.NodeOutput:
        sample_value = await samples.value()
        mask_value = await mask.raw()
        multiplier = float(multiplier)
        if multiplier > 0.0:
            mask_value = mask_value * multiplier
        elif multiplier < 0.0:
            mask_value = mask_value.new_ones(mask_value.shape)
        else:
            mask_value = mask_value.new_zeros(mask_value.shape)
        output = sample_value.copy()
        output['noise_mask'] = mask_value.reshape((-1, 1, mask_value.shape[-2], mask_value.shape[-1]))
        patched = await model.patch('differential_diffusion', strength=1.0)
        return _remaining_za_io.NodeOutput(patched, await _remaining_za_sdk.LatentRef.from_value(output))
from comfy_api.latest import io as _remaining_zb_io

class _remaining_zb_RifleXSecure(_remaining_zb_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)
    ARCHITECTURE = ''
    DEFAULT_K = 1

    @classmethod
    def _schema(cls, node_id: str, category: str) -> _remaining_zb_io.Schema:
        return _remaining_zb_io.Schema(node_id=node_id, display_name=f"🔒 {node_id.removesuffix('Secure')} (secure)", category=category, description='Extends temporal rotary-position frequencies with RIFLEx.', is_experimental=True, inputs=[_remaining_zb_io.Model.Input('model'), _remaining_zb_io.Latent.Input('latent', tooltip='Only used to get the latent count'), _remaining_zb_io.Int.Input('k', default=cls.DEFAULT_K, min=1, max=100, step=1, tooltip='Index of the intrinsic frequency')], outputs=[_remaining_zb_io.Model.Output('model')])

    @classmethod
    async def execute(cls, model, latent, k) -> _remaining_zb_io.NodeOutput:
        latent_value = await latent.value()
        num_frames = int(latent_value['samples'].shape[2])
        patched = await model.patch('riflex_rope', architecture=cls.ARCHITECTURE, num_frames=num_frames, intrinsic_frequency=k)
        return _remaining_zb_io.NodeOutput(patched)

class ApplyRifleXRoPEWanVideoSecure(_remaining_zb_RifleXSecure):
    ARCHITECTURE = 'wan'
    DEFAULT_K = 6

    @classmethod
    def define_schema(cls) -> _remaining_zb_io.Schema:
        return cls._schema('ApplyRifleXRoPEWanVideoSecure', 'KJNodes/wan')

class ApplyRifleXRoPEHunuyanVideoSecure(_remaining_zb_RifleXSecure):
    ARCHITECTURE = 'hunyuan'
    DEFAULT_K = 4

    @classmethod
    def define_schema(cls) -> _remaining_zb_io.Schema:
        return cls._schema('ApplyRifleXRoPEHunuyanVideoSecure', 'KJNodes/hunyuanvideo')
from comfy_api.latest import io as _remaining_zc_io, sdk as _remaining_zc_sdk

class ModelSaveKJSecure(_remaining_zc_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('output',)

    @classmethod
    def define_schema(cls):
        return _remaining_zc_io.Schema(node_id='ModelSaveKJSecure', display_name='🔒 Model Save KJ (secure)', category='advanced/model_merging', is_output_node=True, inputs=[_remaining_zc_io.Model.Input('model'), _remaining_zc_io.String.Input('filename_prefix', default='diffusion_models/ComfyUI'), _remaining_zc_io.String.Input('model_key_prefix', default='model.diffusion_model.')])

    @classmethod
    async def execute(cls, model, filename_prefix, model_key_prefix):
        await _remaining_zc_sdk.ctx().output.save_model(model, filename_prefix=filename_prefix, model_key_prefix=model_key_prefix)
        return _remaining_zc_io.NodeOutput()
from comfy_api.latest import io as _remaining_zd_io

class CheckpointPerturbWeightsSecure(_remaining_zd_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_zd_io.Schema:
        return _remaining_zd_io.Schema(node_id='CheckpointPerturbWeightsSecure', display_name='🔒 Checkpoint Perturb Weights (secure)', category='KJNodes/experimental', is_experimental=True, is_output_node=True, inputs=[_remaining_zd_io.Model.Input('model'), _remaining_zd_io.Float.Input('joint_blocks', default=0.02, min=0.001, max=10.0, step=0.001), _remaining_zd_io.Float.Input('final_layer', default=0.02, min=0.001, max=10.0, step=0.001), _remaining_zd_io.Float.Input('rest_of_the_blocks', default=0.02, min=0.001, max=10.0, step=0.001), _remaining_zd_io.Int.Input('seed', default=123, min=0, max=18446744073709551615, step=1)], outputs=[_remaining_zd_io.Model.Output('model')])

    @classmethod
    async def execute(cls, seed, model, joint_blocks, final_layer, rest_of_the_blocks) -> _remaining_zd_io.NodeOutput:
        patched = await model.patch('perturb_weights', joint_blocks=joint_blocks, final_layer=final_layer, rest_of_the_blocks=rest_of_the_blocks, seed=seed)
        return _remaining_zd_io.NodeOutput(patched)
import torch as _remaining_ze_torch
from comfy_api.latest import io as _remaining_ze_io, sdk as _remaining_ze_sdk

class HunyuanVideoEncodeKeyframesToCondSecure(_remaining_ze_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _remaining_ze_io.Schema:
        return _remaining_ze_io.Schema(node_id='HunyuanVideoEncodeKeyframesToCondSecure', display_name='🔒 Hunyuan Video Encode Keyframes To Cond (secure)', category='KJNodes/hunyuanvideo', inputs=[_remaining_ze_io.Model.Input('model'), _remaining_ze_io.Conditioning.Input('positive'), _remaining_ze_io.Vae.Input('vae'), _remaining_ze_io.Image.Input('start_frame'), _remaining_ze_io.Image.Input('end_frame'), _remaining_ze_io.Int.Input('num_frames', default=33, min=2, max=4096, step=1), _remaining_ze_io.Int.Input('tile_size', default=512, min=64, max=4096, step=64), _remaining_ze_io.Int.Input('overlap', default=64, min=0, max=4096, step=32), _remaining_ze_io.Int.Input('temporal_size', default=64, min=8, max=4096, step=4), _remaining_ze_io.Int.Input('temporal_overlap', default=8, min=4, max=4096, step=4), _remaining_ze_io.Conditioning.Input('negative', optional=True)], outputs=[_remaining_ze_io.Model.Output('model'), _remaining_ze_io.Conditioning.Output('positive'), _remaining_ze_io.Conditioning.Output('negative'), _remaining_ze_io.Latent.Output('latent')])

    @classmethod
    async def execute(cls, model, positive, vae, start_frame, end_frame, num_frames, tile_size, overlap, temporal_size, temporal_overlap, negative=None) -> _remaining_ze_io.NodeOutput:
        start = await start_frame.raw()
        end = await end_frame.raw()
        positive_value = await positive.value()
        negative_value = [] if negative is None else await negative.value()
        height = start.shape[1] // 8 * 8
        width = start.shape[2] // 8 * 8
        if start.shape[1] != height or start.shape[2] != width:
            height_offset = start.shape[1] % 8 // 2
            width_offset = start.shape[2] % 8 // 2
            start = start[:, height_offset:height + height_offset, width_offset:width + width_offset, :]
        if end.shape[1] != height or end.shape[2] != width:
            height_offset = start.shape[1] % 8 // 2
            width_offset = start.shape[2] % 8 // 2
            end = end[:, height_offset:height + height_offset, width_offset:width + width_offset, :]
        middle = _remaining_ze_torch.zeros(num_frames - 2, start.shape[1], start.shape[2], start.shape[3], device=start.device, dtype=start.dtype)
        frames = _remaining_ze_torch.cat((start, middle, end), dim=0)
        frame_ref = await _remaining_ze_sdk.ImageRef._from_raw(frames[:, :, :, :3])
        concat_ref = await vae.encode_tiled(frame_ref, tile_x=tile_size, tile_y=tile_size, overlap=overlap, tile_t=temporal_size, overlap_t=temporal_overlap)
        concat_latent = (await concat_ref.value())['samples']

        def add_concat(conditioning):
            output = []
            for tensor, metadata in conditioning:
                updated = metadata.copy()
                updated['concat_latent_image'] = concat_latent
                output.append([tensor, updated])
            return output
        model_out = await model.patch('hunyuan_concat_image')
        positive_out = add_concat(positive_value)
        negative_out = add_concat(negative_value)
        latent_out = {'samples': _remaining_ze_torch.zeros_like(concat_latent)}
        return _remaining_ze_io.NodeOutput(model_out, await _remaining_ze_sdk.CondRef.from_value(positive_out), await _remaining_ze_sdk.CondRef.from_value(negative_out), await _remaining_ze_sdk.LatentRef.from_value(latent_out))

class LatentInpaintTTMSecure(_remaining_ze_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_ze_io.Schema:
        return _remaining_ze_io.Schema(node_id='LatentInpaintTTMSecure', display_name='🔒 Latent Inpaint TTM (secure)', category='KJNodes/experimental', description='Applies Time-To-Move latent inpainting while sampling.', search_aliases=['time to move'], is_experimental=True, inputs=[_remaining_ze_io.Model.Input('model'), _remaining_ze_io.Int.Input('steps', default=7, min=0, max=888, step=1), _remaining_ze_io.Mask.Input('mask', optional=True)], outputs=[_remaining_ze_io.Model.Output('model')])

    @classmethod
    async def execute(cls, model, steps, mask=None) -> _remaining_ze_io.NodeOutput:
        return _remaining_ze_io.NodeOutput(await model.patch('latent_inpaint_ttm', steps=steps, mask=mask))
from comfy_api.latest import io as _remaining_zf_io

class LeapfusionHunyuanI2VPatcherSecure(_remaining_zf_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_zf_io.Schema:
        return _remaining_zf_io.Schema(node_id='LeapfusionHunyuanI2VPatcherSecure', display_name='🔒 Leapfusion Hunyuan I2V Patcher (secure)', category='KJNodes/hunyuanvideo', inputs=[_remaining_zf_io.Model.Input('model'), _remaining_zf_io.Latent.Input('latent'), _remaining_zf_io.Int.Input('index', default=0, min=-1, max=1000, step=1, tooltip='Frame index to replace; -1 selects the last frame'), _remaining_zf_io.Float.Input('start_percent', default=0.0, min=0.0, max=1.0, step=0.01), _remaining_zf_io.Float.Input('end_percent', default=1.0, min=0.0, max=1.0, step=0.01), _remaining_zf_io.Float.Input('strength', default=1.0, min=-10.0, max=10.0, step=0.001)], outputs=[_remaining_zf_io.Model.Output('model')])

    @classmethod
    async def execute(cls, model, latent, index, start_percent, end_percent, strength) -> _remaining_zf_io.NodeOutput:
        return _remaining_zf_io.NodeOutput(await model.patch('leapfusion_hunyuan_i2v', latent=latent, index=index, strength=strength, start_percent=start_percent, end_percent=end_percent))
import math as _remaining_zk_math
import re as _remaining_zk_re
from comfy_api.latest import io as _remaining_zk_io, sdk as _remaining_zk_sdk
_remaining_zk_ControlNetWeights = _remaining_zk_io.Custom('CONTROL_NET_WEIGHTS')
_remaining_zk_TimestepKeyframe = _remaining_zk_io.Custom('TIMESTEP_KEYFRAME')
_remaining_zk_ControlNetWeightsExtras = _remaining_zk_io.Custom('CN_WEIGHTS_EXTRAS')
_remaining_zk_SelectedDitBlocks = _remaining_zk_io.Custom('SELECTEDDITBLOCKS')
_remaining_zk_BLOCK_KEY = _remaining_zk_re.compile('^(double_blocks|single_blocks|blocks)\\.(\\d+)\\.$')
_remaining_zk_BLOCK_LIMITS = {'double_blocks': 20, 'single_blocks': 40, 'blocks': 48}

def _remaining_zk_closed_block_weights(blocks):
    if blocks is None:
        return []
    if not isinstance(blocks, dict):
        raise TypeError('blocks must be a SELECTEDDITBLOCKS mapping')
    result = []
    for key, value in blocks.items():
        match = _remaining_zk_BLOCK_KEY.fullmatch(key) if isinstance(key, str) else None
        if match is None:
            raise ValueError(f'unsupported selected-block key {key!r}')
        family, raw_index = match.groups()
        index = int(raw_index)
        if not 0 <= index < _remaining_zk_BLOCK_LIMITS[family]:
            raise ValueError(f'selected-block index is out of range: {key!r}')
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f'selected-block ratio for {key!r} must be numeric')
        ratio = float(value)
        if not _remaining_zk_math.isfinite(ratio) or not 0.0 <= ratio <= 10000.0:
            raise ValueError(f'selected-block ratio for {key!r} must be in [0, 10000]')
        result.append({'family': family, 'index': index, 'ratio': ratio})
    return result

class CustomControlNetWeightsFluxFromListSecure(_remaining_zk_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_zk_io.Schema:
        return _remaining_zk_io.Schema(node_id='CustomControlNetWeightsFluxFromListSecure', display_name='🔒 Custom ControlNet Weights Flux From List (secure)', category='KJNodes/controlnet', description='Create Advanced-ControlNet weights from a linked list of floating-point values.', inputs=[_remaining_zk_io.Float.Input('list_of_floats', force_input=True), _remaining_zk_io.Float.Input('uncond_multiplier', default=1.0, min=0.0, max=1.0, step=0.01, optional=True), _remaining_zk_ControlNetWeightsExtras.Input('cn_extras', optional=True)], outputs=[_remaining_zk_ControlNetWeights.Output('CN_WEIGHTS', display_name='CN_WEIGHTS'), _remaining_zk_TimestepKeyframe.Output('TK_SHORTCUT', display_name='TK_SHORTCUT')])

    @classmethod
    async def execute(cls, list_of_floats, uncond_multiplier=1.0, cn_extras=None) -> _remaining_zk_io.NodeOutput:
        weights, shortcut = await _remaining_zk_sdk.ControlNetWeightsRef.from_list(list_of_floats, uncond_multiplier=uncond_multiplier, extras={} if cn_extras is None else cn_extras)
        return _remaining_zk_io.NodeOutput(weights, shortcut)

class DiTBlockLoraLoaderSecure(_remaining_zk_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('assets',)

    @classmethod
    def define_schema(cls) -> _remaining_zk_io.Schema:
        return _remaining_zk_io.Schema(node_id='DiTBlockLoraLoaderSecure', display_name='🔒 DiT Block LoRA Loader (secure)', category='KJNodes/lora', description='Apply a catalogue LoRA to selected diffusion blocks. The V2 node accepts logical catalogue names and never absolute paths.', inputs=[_remaining_zk_io.Model.Input('model', tooltip='The diffusion model the LoRA will be applied to.'), _remaining_zk_io.Float.Input('strength_model', default=1.0, min=-100.0, max=100.0, step=0.01, tooltip='How strongly to modify the diffusion model.'), _remaining_zk_io.Combo.Input('lora_name', options=[], remote=_remaining_zk_io.RemoteOptions(route='/models/loras', refresh_button=True), tooltip='A logical name from the LoRA catalogue.'), _remaining_zk_SelectedDitBlocks.Input('blocks', optional=True)], outputs=[_remaining_zk_io.Model.Output('model', display_name='model'), _remaining_zk_io.String.Output('rank', display_name='rank')])

    @classmethod
    def validate_inputs(cls, lora_name):
        if not isinstance(lora_name, str) or not lora_name:
            return 'lora_name must be a non-empty catalogue name'
        return True

    @classmethod
    async def execute(cls, model, strength_model, lora_name, blocks=None) -> _remaining_zk_io.NodeOutput:
        asset = await _remaining_zk_sdk.ctx().assets.resolve('loras', lora_name)
        patched, rank = await model.apply_dit_block_lora(asset, strength_model=strength_model, block_weights=_remaining_zk_closed_block_weights(blocks))
        return _remaining_zk_io.NodeOutput(patched, rank)
from comfy_api.latest import io as _remaining_zq_io, sdk as _remaining_zq_sdk

_SUPERPROMPT_WEIGHT = _remaining_zq_sdk.HuggingFaceWeight(
    repo_id='roborovski/superprompt-v1',
    filename='model.safetensors',
    folder='text_encoders',
    revision='64ec0168f6b14d389bdfa0699eb9beb442bbd60e',
    sha256='4f31e59c0582d4a74aac96ffb4ea9f5d64b268564ae5d1f68e8620dc940127d7',
)

class SuperpromptSecure(_remaining_zq_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('models',)
    SDK_REQUIRED_WEIGHTS = (_SUPERPROMPT_WEIGHT,)

    @classmethod
    def define_schema(cls) -> _remaining_zq_io.Schema:
        return _remaining_zq_io.Schema(node_id='SuperpromptSecure', display_name='Superprompt (secure)', category='KJNodes/text', description='Expand a prompt with the fixed SuperPrompt text model while the tokenizer and weights remain in the trusted process.', is_experimental=True, inputs=[_remaining_zq_io.String.Input('instruction_prompt', default='Expand the following prompt to add more detail', multiline=True), _remaining_zq_io.String.Input('prompt', default='', multiline=True, force_input=True), _remaining_zq_io.Int.Input('max_new_tokens', default=128, min=1, max=4096, step=1)], outputs=[_remaining_zq_io.String.Output()])

    @classmethod
    async def execute(cls, instruction_prompt, prompt, max_new_tokens) -> _remaining_zq_io.NodeOutput:
        input_text = instruction_prompt + ': ' + prompt
        output = await _remaining_zq_sdk.ctx().models.generate_text('superprompt-v1', input_text, max_new_tokens=max_new_tokens, weight=_SUPERPROMPT_WEIGHT.catalogue_name)
        output = output.replace('<pad>', '')
        output = output.replace('</s>', '')
        return _remaining_zq_io.NodeOutput(output)
from comfy_api.latest import io as _scheduled_cfg_io

class ScheduledCFGGuidanceSecure(_scheduled_cfg_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _scheduled_cfg_io.Schema:
        return _scheduled_cfg_io.Schema(node_id='ScheduledCFGGuidanceSecure', display_name='Scheduled CFG Guidance (Secure V2)', category='KJNodes/experimental', description='CFG guidance applies only within the selected sampling range; steps outside it use CFG 1.0.', inputs=[_scheduled_cfg_io.Model.Input('model'), _scheduled_cfg_io.Conditioning.Input('positive'), _scheduled_cfg_io.Conditioning.Input('negative'), _scheduled_cfg_io.Float.Input('cfg', default=6.0, min=0.0, max=100.0, step=0.01), _scheduled_cfg_io.Float.Input('start_percent', default=0.0, min=0.0, max=1.0, step=0.01), _scheduled_cfg_io.Float.Input('end_percent', default=1.0, min=0.0, max=1.0, step=0.01)], outputs=[_scheduled_cfg_io.Guider.Output('guider')])

    @classmethod
    async def execute(cls, model, positive, negative, cfg, start_percent, end_percent) -> _scheduled_cfg_io.NodeOutput:
        guider = await model.scheduled_cfg_guider(positive=positive, negative=negative, cfg=cfg, start_percent=start_percent, end_percent=end_percent)
        return _scheduled_cfg_io.NodeOutput(guider)
import ast as _w3_g_ast
import os as _w3_g_os
import sys as _w3_g_sys
import types as _w3_g_types
from comfy_api.latest import io as _w3_g_io, sdk as _w3_g_sdk
from . import _packload as _w3_g_packload
_w3_g_SOURCE = 'nodes/nodes.py'
_w3_g_REFUSED_MODULES = ('folder_paths', 'node_helpers', 'comfy.model_management', 'comfy.patcher_extension', 'comfy.sampler_helpers', 'comfy.samplers')
_w3_g_REFUSED_MEMBERS = {'comfy.utils': ('ProgressBar', 'load_torch_file', 'save_torch_file')}
_w3_g_MOD = None

def _w3_g_mod():
    global _w3_g_MOD
    if _w3_g_MOD is None:
        try:
            _w3_g_MOD = _w3_g_packload.load(_w3_g_SOURCE)
        except ImportError:
            _w3_g_MOD = _w3_g_without_refused()
    return _w3_g_MOD

def _w3_g_prune_import(stmt):
    """`stmt` minus the names a guest refuses, and the bindings that went.

    Returns `(None, gone)` when nothing is left to import at all.
    """
    if isinstance(stmt, _w3_g_ast.Import):

        def refused(alias) -> bool:
            return alias.name in _w3_g_REFUSED_MODULES

        def bound(alias) -> str:
            return alias.asname or alias.name.split('.')[0]
    elif isinstance(stmt, _w3_g_ast.ImportFrom) and stmt.level == 0:
        members = _w3_g_REFUSED_MEMBERS.get(stmt.module, ())

        def refused(alias) -> bool:
            return stmt.module in _w3_g_REFUSED_MODULES or alias.name in members or f'{stmt.module}.{alias.name}' in _w3_g_REFUSED_MODULES

        def bound(alias) -> str:
            return alias.asname or alias.name
    else:
        return (stmt, set())
    kept = [a for a in stmt.names if not refused(a)]
    gone = {bound(a) for a in stmt.names if refused(a)}
    if not kept:
        return (None, gone)
    stmt.names = kept
    return (stmt, gone)

def _w3_g_import_time_names(node) -> set:
    """Free names a statement evaluates WHEN THE MODULE RUNS.

    A function body is not evaluated then, so it is skipped — that is what keeps
    `rope_riflex`, whose `model_management` call is in its body: it is defined,
    and raises with the name visible if anything calls it. Base classes,
    decorators and default arguments ARE evaluated at import, so they are
    walked: `class Guider_ScheduledCFG(CFGGuider)` cannot be defined at all in a
    guest, and a strip that missed it would leave the module unimportable.
    """
    if isinstance(node, _w3_g_ast.Name):
        return {node.id}
    if isinstance(node, (_w3_g_ast.FunctionDef, _w3_g_ast.AsyncFunctionDef)):
        children = [*node.decorator_list, node.args, *([node.returns] if node.returns is not None else [])]
    elif isinstance(node, _w3_g_ast.Lambda):
        children = [node.args]
    else:
        children = list(_w3_g_ast.iter_child_nodes(node))
    names = set()
    for child in children:
        names |= _w3_g_import_time_names(child)
    return names

def _w3_g_without_refused() -> _w3_g_types.ModuleType:
    """Upstream's module, executed minus what a guest refuses.

    Registered under a name of its own, NOT `…nodes.nodes`: this is a partial
    view of the module, and leaving it in `_packload`'s cache would serve it to
    a caller on a host, where the whole thing is available.
    """
    modname = f'{_w3_g_packload.PKG}.nodes.nodes_without_refused'
    path = _w3_g_os.path.join(_w3_g_packload.ROOT, *_w3_g_SOURCE.split('/'))
    with open(path, encoding='utf-8') as handle:
        source = handle.read()
    tree = _w3_g_ast.parse(source, path)
    dropped, kept = (set(), [])
    for stmt in tree.body:
        stmt, gone = _w3_g_prune_import(stmt)
        dropped |= gone
        if stmt is not None and (not _w3_g_import_time_names(stmt) & dropped):
            kept.append(stmt)
    tree.body = kept
    mod = _w3_g_types.ModuleType(modname)
    mod.__file__ = path
    mod.__package__ = f'{_w3_g_packload.PKG}.nodes'
    _w3_g_sys.modules[modname] = mod
    try:
        exec(compile(tree, path, 'exec'), mod.__dict__)
    except BaseException:
        _w3_g_sys.modules.pop(modname, None)
        raise
    return mod
_w3_g_CUSTOM_SIGMAS_DEFAULT = '14.615, 6.475, 3.861, 2.697, 1.886, 1.396, 0.963, 0.652, 0.399, 0.152, 0.029'
_w3_g_CUSTOM_SIGMAS_DESCRIPTION = "\nCreates a sigmas tensor from a string of comma separated values.  \nExamples: \n   \nNvidia's optimized AYS 10 step schedule for SD 1.5:  \n14.615, 6.475, 3.861, 2.697, 1.886, 1.396, 0.963, 0.652, 0.399, 0.152, 0.029  \nSDXL:   \n14.615, 6.315, 3.771, 2.181, 1.342, 0.862, 0.555, 0.380, 0.234, 0.113, 0.029  \nSVD:  \n700.00, 54.5, 15.886, 7.977, 4.248, 1.789, 0.981, 0.403, 0.173, 0.034, 0.002  \n"

class BOOLConstantSecure(_w3_g_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _w3_g_io.Schema:
        return _w3_g_io.Schema(node_id='BOOLConstantSecure', display_name='🔒 BOOL Constant (secure)', category='KJNodes/constants', search_aliases=['boolean', 'value'], inputs=[_w3_g_io.Boolean.Input('value', default=True)], outputs=[_w3_g_io.Boolean.Output(display_name='value')])

    @classmethod
    async def execute(cls, value) -> _w3_g_io.NodeOutput:
        out = _w3_g_mod().BOOLConstant().get_value(value)
        return _w3_g_io.NodeOutput(out[0])

class AppendStringsToListSecure(_w3_g_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _w3_g_io.Schema:
        return _w3_g_io.Schema(node_id='AppendStringsToListSecure', display_name='🔒 Append Strings To List (secure)', category='KJNodes/text', inputs=[_w3_g_io.String.Input('string1', default='', force_input=True), _w3_g_io.String.Input('string2', default='', force_input=True)], outputs=[_w3_g_io.String.Output()])

    @classmethod
    async def execute(cls, string1, string2) -> _w3_g_io.NodeOutput:
        out = _w3_g_mod().AppendStringsToList().joinstring(string1, string2)
        return _w3_g_io.NodeOutput(out[0])

class CustomSigmasSecure(_w3_g_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_g_io.Schema:
        return _w3_g_io.Schema(node_id='CustomSigmasSecure', display_name='🔒 Custom Sigmas (secure)', category='KJNodes/noise', description=_w3_g_CUSTOM_SIGMAS_DESCRIPTION, inputs=[_w3_g_io.String.Input('sigmas_string', default=_w3_g_CUSTOM_SIGMAS_DEFAULT, multiline=True), _w3_g_io.Int.Input('interpolate_to_steps', default=10, min=0, max=255, step=1)], outputs=[_w3_g_io.Sigmas.Output(display_name='SIGMAS')])

    @classmethod
    async def execute(cls, sigmas_string, interpolate_to_steps) -> _w3_g_io.NodeOutput:
        out = _w3_g_mod().CustomSigmas().customsigmas(sigmas_string, interpolate_to_steps)
        return _w3_g_io.NodeOutput(await _w3_g_sdk.TensorRef._from_raw(out[0]))
import ast as _w3_h_ast
import pathlib as _w3_h_pathlib
from comfy_api.latest import io as _w3_h_io, sdk as _w3_h_sdk
from . import _packload as _w3_h_packload
_w3_h_SOURCE = 'nodes/nodes.py'
_w3_h_METHODS: dict[tuple[str, str], object] = {}
_w3_h_NAMESPACE = None

def _w3_h_namespace() -> dict:
    """Every name an extracted method is allowed to see.

    Deliberately tiny, and deliberately built lazily: this is called from
    `execute`, inside the guest, never from `define_schema`. `torch` is what
    `indexedlatentsfrombatch` indexes with and `np` is what
    `get_sigmas_adjusted` formats with; nothing else in this file has a free
    name at all.
    """
    global _w3_h_NAMESPACE
    if _w3_h_NAMESPACE is None:
        import numpy as np
        import torch
        _w3_h_NAMESPACE = {'np': np, 'torch': torch}
    return _w3_h_NAMESPACE

def _w3_h_upstream(class_name: str, method: str):
    """Upstream's own `class_name.method`, compiled against `_namespace()`.

    Cached, because a guest serves node after node from the same pack and
    re-parsing a 3000-line module per dispatch would re-pay that cost every
    time. The methods are plain instance methods extracted undecorated, so the
    caller supplies `self` as an ordinary first argument; none of the seven
    uses it.
    """
    key = (class_name, method)
    cached = _w3_h_METHODS.get(key)
    if cached is not None:
        return cached
    path = _w3_h_pathlib.Path(_w3_h_packload.ROOT, *_w3_h_SOURCE.split('/'))
    if not path.exists():
        raise FileNotFoundError(f'{path} does not exist; the pack moved or changed shape and the conversion that reads it must be revisited')
    text = path.read_text(encoding='utf-8')
    for node in _w3_h_ast.walk(_w3_h_ast.parse(text, filename=str(path))):
        if not (isinstance(node, _w3_h_ast.ClassDef) and node.name == class_name):
            continue
        for item in node.body:
            if not (isinstance(item, _w3_h_ast.FunctionDef) and item.name == method):
                continue
            ns = dict(_w3_h_namespace())
            exec(compile(_w3_h_ast.parse(_w3_h_ast.get_source_segment(text, item)), f'<kjnodes.{class_name}.{method}>', 'exec'), ns)
            _w3_h_METHODS[key] = ns[method]
            return ns[method]
    raise RuntimeError(f'{class_name}.{method} not found in upstream {_w3_h_SOURCE} — the pack changed shape and this conversion must be revisited')
_w3_h_SelectedDitBlocks = _w3_h_io.Custom('SELECTEDDITBLOCKS')
_w3_h_BLOCK_ALPHA = {'default': 0.0, 'min': 0.0, 'max': 1000.0, 'step': 0.01}

def _w3_h_block_alpha_inputs(double: int, single: int) -> list[_w3_h_io.Input]:
    """Upstream's `INPUT_TYPES` loop, rebuilt from literals.

    `define_schema` runs in the HOST process — at `/object_info` and on the
    prompt-validation path — so it must not import the pack. The counts and the
    widget bounds are the whole of what upstream's loop contributes, and they
    are written out here rather than read from it.
    """
    return [_w3_h_io.Float.Input(f'double_blocks.{i}.', **_w3_h_BLOCK_ALPHA) for i in range(double)] + [_w3_h_io.Float.Input(f'single_blocks.{i}.', **_w3_h_BLOCK_ALPHA) for i in range(single)]

class DummyOutSecure(_w3_h_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _w3_h_io.Schema:
        return _w3_h_io.Schema(node_id='DummyOutSecure', display_name='🔒 Dummy Out (secure)', category='KJNodes/misc', description='\nDoes nothing, used to trigger generic workflow output.\nA way to get previews in the UI without saving anything to disk.\n', inputs=[_w3_h_io.AnyType.Input('any_input')], outputs=[_w3_h_io.AnyType.Output()], is_output_node=True)

    @classmethod
    async def execute(cls, any_input) -> _w3_h_io.NodeOutput:
        out = _w3_h_upstream('DummyOut', 'dummy')(None, any_input)
        return _w3_h_io.NodeOutput(out[0])

class FlipSigmasAdjustedSecure(_w3_h_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_h_io.Schema:
        return _w3_h_io.Schema(node_id='FlipSigmasAdjustedSecure', display_name='🔒 Flip Sigmas Adjusted (secure)', category='KJNodes/noise', inputs=[_w3_h_io.Sigmas.Input('sigmas'), _w3_h_io.Boolean.Input('divide_by_last_sigma', default=False), _w3_h_io.Float.Input('divide_by', default=1, min=1, max=255, step=0.01), _w3_h_io.Int.Input('offset_by', default=1, min=-100, max=100, step=1)], outputs=[_w3_h_io.Sigmas.Output(display_name='SIGMAS'), _w3_h_io.String.Output(display_name='sigmas_string')])

    @classmethod
    async def execute(cls, sigmas, divide_by_last_sigma, divide_by, offset_by) -> _w3_h_io.NodeOutput:
        adjust = _w3_h_upstream('FlipSigmasAdjusted', 'get_sigmas_adjusted')
        adjusted, array_string = adjust(None, await sigmas.raw(), divide_by_last_sigma, divide_by, offset_by)
        return _w3_h_io.NodeOutput(await _w3_h_sdk.TensorRef._from_raw(adjusted), array_string)

class FloatConstantSecure(_w3_h_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _w3_h_io.Schema:
        return _w3_h_io.Schema(node_id='FloatConstantSecure', display_name='🔒 Float Constant (secure)', category='KJNodes/constants', search_aliases=['float', 'value'], inputs=[_w3_h_io.Float.Input('value', default=0.0, min=-18446744073709551615, max=18446744073709551615, step=1e-05)], outputs=[_w3_h_io.Float.Output(display_name='value')])

    @classmethod
    async def execute(cls, value) -> _w3_h_io.NodeOutput:
        out = _w3_h_upstream('FloatConstant', 'get_value')(None, value)
        return _w3_h_io.NodeOutput(out[0])

class FluxBlockLoraSelectSecure(_w3_h_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _w3_h_io.Schema:
        return _w3_h_io.Schema(node_id='FluxBlockLoraSelectSecure', display_name='🔒 Flux Block Lora Select (secure)', category='KJNodes/experimental', description='Select individual block alpha values, value of 0 removes the block altogether', inputs=_w3_h_block_alpha_inputs(19, 38), outputs=[_w3_h_SelectedDitBlocks.Output(display_name='blocks', tooltip='The modified diffusion model.')])

    @classmethod
    async def execute(cls, **kwargs) -> _w3_h_io.NodeOutput:
        out = _w3_h_upstream('FluxBlockLoraSelect', 'load_lora')(None, **kwargs)
        return _w3_h_io.NodeOutput(out[0])

class GetLatentsFromBatchIndexedSecure(_w3_h_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_h_io.Schema:
        return _w3_h_io.Schema(node_id='GetLatentsFromBatchIndexedSecure', display_name='🔒 Get Latents From Batch Indexed (secure)', category='KJNodes/latents', description='\nSelects and returns the latents at the specified indices as an latent batch.\n', inputs=[_w3_h_io.Latent.Input('latents'), _w3_h_io.String.Input('indexes', default='0, 1, 2', multiline=True), _w3_h_io.Combo.Input('latent_format', options=['BCHW', 'BTCHW', 'BCTHW'], default='BCHW')], outputs=[_w3_h_io.Latent.Output()])

    @classmethod
    async def execute(cls, latents, indexes, latent_format) -> _w3_h_io.NodeOutput:
        select = _w3_h_upstream('GetLatentsFromBatchIndexed', 'indexedlatentsfrombatch')
        out = select(None, await latents.value(), indexes, latent_format)
        return _w3_h_io.NodeOutput(await _w3_h_sdk.LatentRef.from_value(out[0]))

class HunyuanVideoBlockLoraSelectSecure(_w3_h_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _w3_h_io.Schema:
        return _w3_h_io.Schema(node_id='HunyuanVideoBlockLoraSelectSecure', display_name='🔒 Hunyuan Video Block Lora Select (secure)', category='KJNodes/hunyuanvideo', description='Select individual block alpha values, value of 0 removes the block altogether', inputs=_w3_h_block_alpha_inputs(20, 40), outputs=[_w3_h_SelectedDitBlocks.Output(display_name='blocks', tooltip='The modified diffusion model.')])

    @classmethod
    async def execute(cls, **kwargs) -> _w3_h_io.NodeOutput:
        out = _w3_h_upstream('HunyuanVideoBlockLoraSelect', 'load_lora')(None, **kwargs)
        return _w3_h_io.NodeOutput(out[0])

class INTConstantSecure(_w3_h_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _w3_h_io.Schema:
        return _w3_h_io.Schema(node_id='INTConstantSecure', display_name='🔒 INT Constant (secure)', category='KJNodes/constants', search_aliases=['integer', 'value'], inputs=[_w3_h_io.Int.Input('value', default=0, min=-18446744073709551615, max=18446744073709551615)], outputs=[_w3_h_io.Int.Output(display_name='value')])

    @classmethod
    async def execute(cls, value) -> _w3_h_io.NodeOutput:
        out = _w3_h_upstream('INTConstant', 'get_value')(None, value)
        return _w3_h_io.NodeOutput(out[0])
import ast as _w3_i_ast
import pathlib as _w3_i_pathlib
from comfy_api.latest import io as _w3_i_io, sdk as _w3_i_sdk
from . import _packload as _w3_i_packload
_w3_i_SOURCE = 'nodes/nodes.py'
_w3_i_METHODS: dict[tuple[str, str], object] = {}
_w3_i_NAMESPACE = None

def _w3_i_namespace() -> dict:
    """Every name an extracted method is allowed to see.

    Two, and built lazily: this is reached from `execute`, inside the guest,
    never from `define_schema`. If upstream grows a dependency on the host
    surface sitting around it in that file, an extracted method raises
    `NameError` naming the symbol rather than resolving it against something
    invented in here.
    """
    global _w3_i_NAMESPACE
    if _w3_i_NAMESPACE is None:
        import torch
        _w3_i_NAMESPACE = {'torch': torch, 'io': _w3_i_io}
    return _w3_i_NAMESPACE

def _w3_i_upstream(class_name: str, method: str):
    """Upstream's own `class_name.method`, compiled against `_namespace()`.

    Cached, because a guest serves node after node from the same pack and
    re-parsing a 3400-line module per dispatch would re-pay that cost every
    time. Methods are extracted undecorated, so the caller supplies the first
    argument itself — `None` for a plain instance method, `cls` for one upstream
    declared a classmethod.
    """
    key = (class_name, method)
    cached = _w3_i_METHODS.get(key)
    if cached is not None:
        return cached
    path = _w3_i_pathlib.Path(_w3_i_packload.ROOT, *_w3_i_SOURCE.split('/'))
    if not path.exists():
        raise FileNotFoundError(f'{path} does not exist; the pack moved or changed shape and the conversion that reads it must be revisited')
    text = path.read_text(encoding='utf-8')
    for node in _w3_i_ast.walk(_w3_i_ast.parse(text, filename=str(path))):
        if not (isinstance(node, _w3_i_ast.ClassDef) and node.name == class_name):
            continue
        for item in node.body:
            if not (isinstance(item, _w3_i_ast.FunctionDef) and item.name == method):
                continue
            ns = dict(_w3_i_namespace())
            exec(compile(_w3_i_ast.Module(body=[_w3_i_ast.parse(_w3_i_ast.get_source_segment(text, item)).body[0]], type_ignores=[]), f'<kjnodes.{class_name}.{method}>', 'exec'), ns)
            _w3_i_METHODS[key] = ns[method]
            return ns[method]
    raise RuntimeError(f'{class_name}.{method} not found in upstream {_w3_i_SOURCE} — the pack changed shape and this conversion must be revisited')
_w3_i_SelectedDitBlocks = _w3_i_io.Custom('SELECTEDDITBLOCKS')
_w3_i_LTX2_BLOCKS = tuple((f'blocks.{i}.' for i in range(48)))

class ImageNoiseAugmentationSecure(_w3_i_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_i_io.Schema:
        return _w3_i_io.Schema(node_id='ImageNoiseAugmentationSecure', display_name='🔒 Image Noise Augmentation (secure)', category='KJNodes/image', description='Add noise to an image.', inputs=[_w3_i_io.Image.Input('image'), _w3_i_io.Float.Input('noise_aug_strength', min=0.0, max=100.0, step=0.001), _w3_i_io.Int.Input('seed', default=123, min=0, max=18446744073709551615, step=1)], outputs=[_w3_i_io.Image.Output()])

    @classmethod
    async def execute(cls, image, noise_aug_strength, seed) -> _w3_i_io.NodeOutput:
        add_noise = _w3_i_upstream('ImageNoiseAugmentation', 'add_noise')
        out = add_noise(None, await image.raw(), noise_aug_strength, seed)
        return _w3_i_io.NodeOutput(await _w3_i_sdk.ImageRef._from_raw(out[0]))

class InjectNoiseToLatentSecure(_w3_i_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_i_io.Schema:
        return _w3_i_io.Schema(node_id='InjectNoiseToLatentSecure', display_name='🔒 Inject Noise To Latent (secure)', category='KJNodes/noise', inputs=[_w3_i_io.Latent.Input('latents'), _w3_i_io.Float.Input('strength', default=0.1, min=0.0, max=200.0, step=0.0001), _w3_i_io.Latent.Input('noise'), _w3_i_io.Boolean.Input('normalize', default=False), _w3_i_io.Boolean.Input('average', default=False), _w3_i_io.Mask.Input('mask', optional=True), _w3_i_io.Float.Input('mix_randn_amount', default=0.0, min=0.0, max=1000.0, step=0.001, optional=True), _w3_i_io.Int.Input('seed', default=123, min=0, max=18446744073709551615, step=1, optional=True)], outputs=[_w3_i_io.Latent.Output()])

    @classmethod
    async def execute(cls, latents, strength, noise, normalize, average, mix_randn_amount=0, seed=None, mask=None) -> _w3_i_io.NodeOutput:
        injectnoise = _w3_i_upstream('InjectNoiseToLatent', 'injectnoise')
        out = injectnoise(None, await latents.value(), strength, await noise.value(), normalize, average, mix_randn_amount, seed, None if mask is None else await mask.raw())
        return _w3_i_io.NodeOutput(await _w3_i_sdk.LatentRef.from_value(out[0]))

class JoinStringsSecure(_w3_i_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _w3_i_io.Schema:
        return _w3_i_io.Schema(node_id='JoinStringsSecure', display_name='🔒 Join Strings (secure)', category='KJNodes/text', inputs=[_w3_i_io.String.Input('delimiter', default=' '), _w3_i_io.String.Input('string1', default='', force_input=True, optional=True), _w3_i_io.String.Input('string2', default='', force_input=True, optional=True)], outputs=[_w3_i_io.String.Output()])

    @classmethod
    async def execute(cls, delimiter, string1='', string2='') -> _w3_i_io.NodeOutput:
        joinstring = _w3_i_upstream('JoinStrings', 'joinstring')
        return _w3_i_io.NodeOutput(joinstring(None, delimiter, string1, string2)[0])

class JoinStringMultiSecure(_w3_i_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _w3_i_io.Schema:
        return _w3_i_io.Schema(node_id='JoinStringMultiSecure', display_name='🔒 Join String Multi (secure)', category='KJNodes/text', description='Creates single string, or a list of strings, from\nmultiple input strings.\nYou can set how many inputs the node has,\nwith the **inputcount** and clicking update.', inputs=[_w3_i_io.Int.Input('inputcount', default=2, min=2, max=1000, step=1), _w3_i_io.String.Input('string_1', default='', force_input=True), _w3_i_io.String.Input('delimiter', default=' '), _w3_i_io.Boolean.Input('return_list', default=False), _w3_i_io.String.Input('string_2', default='', force_input=True, optional=True)], outputs=[_w3_i_io.String.Output(display_name='string')])

    @classmethod
    async def execute(cls, inputcount, string_1, delimiter, return_list, string_2='') -> _w3_i_io.NodeOutput:
        combine = _w3_i_upstream('JoinStringMulti', 'combine')
        out = combine(None, inputcount, delimiter, string_1=string_1, return_list=return_list, string_2=string_2)
        return _w3_i_io.NodeOutput(out[0])

class LTX2BlockLoraSelectSecure(_w3_i_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _w3_i_io.Schema:
        return _w3_i_io.Schema(node_id='LTX2BlockLoraSelectSecure', display_name='🔒 LTX2 Block Lora Select (secure)', category='KJNodes/ltxv', description='Select individual block alpha values, value of 0 removes the block altogether', inputs=[_w3_i_io.Float.Input(name, default=0.0, min=0.0, max=10000.0, step=0.01) for name in _w3_i_LTX2_BLOCKS], outputs=[_w3_i_SelectedDitBlocks.Output(display_name='blocks', tooltip='The modified diffusion model.')])

    @classmethod
    async def execute(cls, **blocks) -> _w3_i_io.NodeOutput:
        load_lora = _w3_i_upstream('LTX2BlockLoraSelect', 'load_lora')
        return _w3_i_io.NodeOutput(load_lora(None, **blocks)[0])

class LazySwitchKJSecure(_w3_i_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _w3_i_io.Schema:
        return _w3_i_io.Schema(node_id='LazySwitchKJSecure', display_name='🔒 Lazy Switch KJ (secure)', category='KJNodes/misc', description='Controls flow of execution based on a boolean switch.', inputs=[_w3_i_io.Boolean.Input('switch'), _w3_i_io.AnyType.Input('on_false', lazy=True), _w3_i_io.AnyType.Input('on_true', lazy=True)], outputs=[_w3_i_io.AnyType.Output()])

    @classmethod
    def check_lazy_status(cls, switch, on_false=None, on_true=None) -> list[str]:
        if switch and on_true is None:
            return ['on_true']
        if not switch and on_false is None:
            return ['on_false']
        return []

    @classmethod
    async def execute(cls, switch, on_false=None, on_true=None) -> _w3_i_io.NodeOutput:
        switch_branch = _w3_i_upstream('LazySwitchKJ', 'switch')
        return _w3_i_io.NodeOutput(switch_branch(None, switch, on_false, on_true)[0])

class PreviewLatentNoiseMaskSecure(_w3_i_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_i_io.Schema:
        return _w3_i_io.Schema(node_id='PreviewLatentNoiseMaskSecure', display_name='🔒 Preview Latent Noise Mask (secure)', category='KJNodes/latents', description='Previews the latent noise mask', inputs=[_w3_i_io.Latent.Input('latent')], outputs=[_w3_i_io.Mask.Output(display_name='mask')])

    @classmethod
    async def execute(cls, latent) -> _w3_i_io.NodeOutput:
        upstream_execute = _w3_i_upstream('PreviewLatentNoiseMask', 'execute')
        out = upstream_execute(cls, await latent.value())
        return _w3_i_io.NodeOutput(await _w3_i_sdk.MaskRef._from_raw(out.result[0]))
import ast as _w3_j_ast
import logging as _w3_j_logging
import math as _w3_j_math
import pathlib as _w3_j_pathlib
import re as _w3_j_re
import time as _w3_j_time
from comfy_api.latest import io as _w3_j_io
from . import _packload as _w3_j_packload
_w3_j_SOURCE = 'nodes/nodes.py'
_w3_j_METHODS: dict[tuple[str, str], object] = {}
_w3_j_NAMESPACE = None

def _w3_j_namespace() -> dict:
    """Every name an extracted method is allowed to see.

    All five are ordinary stdlib or the V2 API itself; none is host surface,
    which is the whole reason these eight classes are convertible while their
    900 module-mates are not.

    `io` is `comfy_api.latest.io` — upstream binds it with
    `from comfy_api.latest import io, ui`, and NOT with the module's other
    `from io import BytesIO`, which binds only `BytesIO`. `SimpleCalculatorKJ`
    needs it at compile time, for the `-> io.NodeOutput` annotation on its own
    `def` line.
    """
    global _w3_j_NAMESPACE
    if _w3_j_NAMESPACE is None:
        _w3_j_NAMESPACE = {'io': _w3_j_io, 'logging': _w3_j_logging, 'math': _w3_j_math, 're': _w3_j_re, 'time': _w3_j_time}
    return _w3_j_NAMESPACE

def _w3_j_upstream(class_name: str, method: str):
    """Upstream's own `class_name.method`, compiled against `_namespace()`.

    Cached, because a guest serves node after node from the same pack and
    re-parsing a 3000-line module per dispatch would re-pay that cost every
    time. Methods are extracted UNDECORATED — `ast.get_source_segment` on a
    `FunctionDef` starts at `def`, not at the decorator — so the caller supplies
    the first argument itself: `self` for the seven legacy nodes, and `cls` for
    `SimpleCalculatorKJ`, which is already a V2 classmethod. None of the eight
    reads it.
    """
    key = (class_name, method)
    cached = _w3_j_METHODS.get(key)
    if cached is not None:
        return cached
    path = _w3_j_pathlib.Path(_w3_j_packload.ROOT, *_w3_j_SOURCE.split('/'))
    if not path.exists():
        raise FileNotFoundError(f'{path} does not exist; the pack moved or changed shape and the conversion that reads it must be revisited')
    text = path.read_text(encoding='utf-8')
    for node in _w3_j_ast.walk(_w3_j_ast.parse(text, filename=str(path))):
        if not (isinstance(node, _w3_j_ast.ClassDef) and node.name == class_name):
            continue
        for item in node.body:
            if not (isinstance(item, _w3_j_ast.FunctionDef) and item.name == method):
                continue
            ns = dict(_w3_j_namespace())
            exec(compile(_w3_j_ast.Module(body=[_w3_j_ast.parse(_w3_j_ast.get_source_segment(text, item)).body[0]], type_ignores=[]), f'<kjnodes.{class_name}.{method}>', 'exec'), ns)
            _w3_j_METHODS[key] = ns[method]
            return ns[method]
    raise RuntimeError(f'{class_name}.{method} not found in upstream {_w3_j_SOURCE} — the pack changed shape and this conversion must be revisited')

class ScaleBatchPromptScheduleSecure(_w3_j_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _w3_j_io.Schema:
        return _w3_j_io.Schema(node_id='ScaleBatchPromptScheduleSecure', display_name='🔒 Scale Batch Prompt Schedule (secure)', category='KJNodes/misc', description="Scales a batch schedule from Fizz' nodes BatchPromptSchedule to a different frame count.", inputs=[_w3_j_io.String.Input('input_str', force_input=True, default='0:(0.0),\n7:(1.0),\n15:(0.0)\n'), _w3_j_io.Int.Input('old_frame_count', force_input=True, default=1, min=1, max=4096, step=1), _w3_j_io.Int.Input('new_frame_count', force_input=True, default=1, min=1, max=4096, step=1)], outputs=[_w3_j_io.String.Output(display_name='STRING')])

    @classmethod
    async def execute(cls, input_str, old_frame_count, new_frame_count) -> _w3_j_io.NodeOutput:
        scale = _w3_j_upstream('ScaleBatchPromptSchedule', 'scaleschedule')
        out = scale(None, old_frame_count, input_str, new_frame_count)
        return _w3_j_io.NodeOutput(out[0])

class SimpleCalculatorKJSecure(_w3_j_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _w3_j_io.Schema:
        template = _w3_j_io.Autogrow.TemplateNames(input=_w3_j_io.MultiType.Input('var', [_w3_j_io.Int, _w3_j_io.Float, _w3_j_io.Boolean], optional=True), names=['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k'], min=2)
        return _w3_j_io.Schema(node_id='SimpleCalculatorKJSecure', display_name='🔒 Simple Calculator KJ (secure)', category='KJNodes/misc', description='\nCalculator node that evaluates a mathematical expression using inputs a and b.\n    Supported operations: +, -, *, /, //, %, **, <<, >>, unary +/-\n    Supported comparisons: ==, !=, <, <=, >, >=\n    Supported logic: and, or, not\n    Supported functions: abs(), round(), min(), max(), pow(), sqrt(), sin(), cos(), tan(), log(), log10(), exp(), floor(), ceil()\n    Supported constants: pi, euler, True, False\n', search_aliases=['math', 'arithmetic', 'expression', 'logic'], inputs=[_w3_j_io.String.Input('expression', default='a + b', multiline=True), _w3_j_io.Autogrow.Input('variables', template=template)], outputs=[_w3_j_io.Float.Output(), _w3_j_io.Int.Output(), _w3_j_io.Boolean.Output()])

    @classmethod
    async def execute(cls, variables, expression, a=None, b=None) -> _w3_j_io.NodeOutput:
        calculate = _w3_j_upstream('SimpleCalculatorKJ', 'execute')
        return calculate(None, variables, expression, a, b)

class SleepSecure(_w3_j_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _w3_j_io.Schema:
        return _w3_j_io.Schema(node_id='SleepSecure', display_name='🔒 Sleep (secure)', category='KJNodes/misc', description='Delays the execution for the input amount of time.', inputs=[_w3_j_io.AnyType.Input('input'), _w3_j_io.Int.Input('minutes', default=0, min=0, max=1439), _w3_j_io.Float.Input('seconds', default=0.0, min=0.0, max=59.99, step=0.01)], outputs=[_w3_j_io.AnyType.Output(display_name='*')])

    @classmethod
    async def execute(cls, input, minutes, seconds) -> _w3_j_io.NodeOutput:
        delay = _w3_j_upstream('Sleep', 'sleepdelay')
        out = delay(None, input, minutes, seconds)
        return _w3_j_io.NodeOutput(out[0])

class SomethingToStringSecure(_w3_j_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _w3_j_io.Schema:
        return _w3_j_io.Schema(node_id='SomethingToStringSecure', display_name='🔒 Something To String (secure)', category='KJNodes/text', description='Converts any type to a string.', inputs=[_w3_j_io.AnyType.Input('input'), _w3_j_io.String.Input('prefix', default='', optional=True), _w3_j_io.String.Input('suffix', default='', optional=True)], outputs=[_w3_j_io.String.Output(display_name='STRING')])

    @classmethod
    async def execute(cls, input, prefix='', suffix='') -> _w3_j_io.NodeOutput:
        stringify = _w3_j_upstream('SomethingToString', 'stringify')
        out = stringify(None, input, prefix, suffix)
        return _w3_j_io.NodeOutput(out[0])

class SoundReactiveSecure(_w3_j_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _w3_j_io.Schema:
        return _w3_j_io.Schema(node_id='SoundReactiveSecure', display_name='🔒 Sound Reactive (secure)', category='KJNodes/audio', description='Reacts to the sound level of the input.\nUses your browsers sound input options and requires.\nMeant to be used with realtime diffusion with autoqueue.', inputs=[_w3_j_io.Float.Input('sound_level', default=1.0, min=0.0, max=99999, step=0.01), _w3_j_io.Int.Input('start_range_hz', default=150, min=0, max=9999, step=1), _w3_j_io.Int.Input('end_range_hz', default=2000, min=0, max=9999, step=1), _w3_j_io.Float.Input('multiplier', default=1.0, min=0.01, max=99999, step=0.01), _w3_j_io.Float.Input('smoothing_factor', default=0.5, min=0.0, max=1.0, step=0.01), _w3_j_io.Boolean.Input('normalize', default=False)], outputs=[_w3_j_io.Float.Output(display_name='sound_level'), _w3_j_io.Int.Output(display_name='sound_level_int')])

    @classmethod
    async def execute(cls, sound_level, start_range_hz, end_range_hz, multiplier, smoothing_factor, normalize) -> _w3_j_io.NodeOutput:
        react = _w3_j_upstream('SoundReactive', 'react')
        out = react(None, sound_level, start_range_hz, end_range_hz, smoothing_factor, multiplier, normalize)
        return _w3_j_io.NodeOutput(out[0], out[1])

class StringConstantSecure(_w3_j_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _w3_j_io.Schema:
        return _w3_j_io.Schema(node_id='StringConstantSecure', display_name='🔒 String Constant (secure)', category='KJNodes/constants', search_aliases=['text', 'value'], inputs=[_w3_j_io.String.Input('string', default='', multiline=False)], outputs=[_w3_j_io.String.Output(display_name='STRING')])

    @classmethod
    async def execute(cls, string) -> _w3_j_io.NodeOutput:
        passtring = _w3_j_upstream('StringConstant', 'passtring')
        return _w3_j_io.NodeOutput(passtring(None, string)[0])

class StringConstantMultilineSecure(_w3_j_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _w3_j_io.Schema:
        return _w3_j_io.Schema(node_id='StringConstantMultilineSecure', display_name='🔒 String Constant Multiline (secure)', category='KJNodes/constants', search_aliases=['text', 'value'], inputs=[_w3_j_io.String.Input('string', default='', multiline=True), _w3_j_io.Boolean.Input('strip_newlines', default=True)], outputs=[_w3_j_io.String.Output(display_name='STRING')])

    @classmethod
    async def execute(cls, string, strip_newlines) -> _w3_j_io.NodeOutput:
        stringify = _w3_j_upstream('StringConstantMultiline', 'stringify')
        out = stringify(None, string, strip_newlines)
        return _w3_j_io.NodeOutput(out[0])

class StringToFloatListSecure(_w3_j_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _w3_j_io.Schema:
        return _w3_j_io.Schema(node_id='StringToFloatListSecure', display_name='🔒 String to Float List (secure)', category='KJNodes/misc', inputs=[_w3_j_io.String.Input('string', default='1, 2, 3', multiline=True)], outputs=[_w3_j_io.Float.Output(display_name='FLOAT')])

    @classmethod
    async def execute(cls, string) -> _w3_j_io.NodeOutput:
        createlist = _w3_j_upstream('StringToFloatList', 'createlist')
        out = createlist(None, string)
        return _w3_j_io.NodeOutput(out[0])
import ast as _w3_k_ast
import pathlib as _w3_k_pathlib
from comfy_api.latest import io as _w3_k_io, sdk as _w3_k_sdk
from . import _packload as _w3_k_packload
_w3_k_SOURCE = 'nodes/nodes.py'
_w3_k_SelectedDitBlocks = _w3_k_io.Custom('SELECTEDDITBLOCKS')
_w3_k_METHODS: dict[tuple[str, str], object] = {}
_w3_k_NAMESPACE = None

def _w3_k_namespace() -> dict:
    """Every name an extracted method is allowed to see.

    All four are ordinary libraries or the V2 API itself; none is host surface.
    Built lazily because this is called from `execute`, inside the guest, never
    from `define_schema`.

    `io` is `comfy_api.latest.io` — upstream binds it with
    `from comfy_api.latest import io, ui`, and separately binds `BytesIO` alone
    with `from io import BytesIO`. `VisualizeSigmasKJ` needs both: `BytesIO` in
    its body, and `io` at compile time for the `-> io.NodeOutput` annotation on
    its own `def` line.
    """
    global _w3_k_NAMESPACE
    if _w3_k_NAMESPACE is None:
        from io import BytesIO
        import numpy as np
        import torch
        _w3_k_NAMESPACE = {'BytesIO': BytesIO, 'io': _w3_k_io, 'np': np, 'torch': torch}
    return _w3_k_NAMESPACE

def _w3_k_upstream(class_name: str, method: str):
    """Upstream's own `class_name.method`, compiled against `_namespace()`.

    Cached, because a guest serves node after node from the same pack and
    re-parsing a 3000-line module per dispatch would re-pay that cost every
    time. Methods are extracted UNDECORATED — `ast.get_source_segment` on a
    `FunctionDef` starts at `def`, not at the decorator — so the caller supplies
    the first argument itself: `self` for `Wan21BlockLoraSelect`, `cls` for
    `VisualizeSigmasKJ`, which is already a V2 classmethod. Neither reads it.
    """
    key = (class_name, method)
    cached = _w3_k_METHODS.get(key)
    if cached is not None:
        return cached
    path = _w3_k_pathlib.Path(_w3_k_packload.ROOT, *_w3_k_SOURCE.split('/'))
    if not path.exists():
        raise FileNotFoundError(f'{path} does not exist; the pack moved or changed shape and the conversion that reads it must be revisited')
    text = path.read_text(encoding='utf-8')
    for node in _w3_k_ast.walk(_w3_k_ast.parse(text, filename=str(path))):
        if not (isinstance(node, _w3_k_ast.ClassDef) and node.name == class_name):
            continue
        for item in node.body:
            if not (isinstance(item, _w3_k_ast.FunctionDef) and item.name == method):
                continue
            ns = dict(_w3_k_namespace())
            exec(compile(_w3_k_ast.Module(body=[_w3_k_ast.parse(_w3_k_ast.get_source_segment(text, item)).body[0]], type_ignores=[]), f'<kjnodes.{class_name}.{method}>', 'exec'), ns)
            _w3_k_METHODS[key] = ns[method]
            return ns[method]
    raise RuntimeError(f'{class_name}.{method} not found in upstream {_w3_k_SOURCE} — the pack changed shape and this conversion must be revisited')

class VisualizeSigmasKJSecure(_w3_k_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _w3_k_io.Schema:
        return _w3_k_io.Schema(node_id='VisualizeSigmasKJSecure', display_name='🔒 Visualize Sigmas KJ (secure)', category='KJNodes/misc', inputs=[_w3_k_io.Sigmas.Input('sigmas'), _w3_k_io.Int.Input('start_step', default=0, min=-1, max=1000, step=1, tooltip='Step index to mark as the start of a range (inclusive). Set to -1 to disable.'), _w3_k_io.Int.Input('end_step', default=-1, min=-1, max=1000, step=1, tooltip='Step index to mark as the end of a range (inclusive). Set to - 1 to disable.')], outputs=[_w3_k_io.Sigmas.Output(display_name='sigmas_out'), _w3_k_io.Image.Output(display_name='image')])

    @classmethod
    async def execute(cls, sigmas, start_step=0, end_step=-1) -> _w3_k_io.NodeOutput:
        visualize = _w3_k_upstream('VisualizeSigmasKJ', 'execute')
        sigmas_out, image = visualize(None, await sigmas.raw(), start_step, end_step).result
        return _w3_k_io.NodeOutput(await _w3_k_sdk.TensorRef._from_raw(sigmas_out), await _w3_k_sdk.ImageRef._from_raw(image))

class Wan21BlockLoraSelectSecure(_w3_k_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _w3_k_io.Schema:
        return _w3_k_io.Schema(node_id='Wan21BlockLoraSelectSecure', display_name='🔒 Wan21 Block Lora Select (secure)', category='KJNodes/wan', description='Select individual block alpha values, value of 0 removes the block altogether', inputs=[_w3_k_io.Float.Input(f'blocks.{i}.', default=0.0, min=0.0, max=1000.0, step=0.01) for i in range(40)], outputs=[_w3_k_SelectedDitBlocks.Output(display_name='blocks', tooltip='The modified diffusion model.')])

    @classmethod
    async def execute(cls, **kwargs) -> _w3_k_io.NodeOutput:
        select = _w3_k_upstream('Wan21BlockLoraSelect', 'load_lora')
        out = select(None, **kwargs)
        return _w3_k_io.NodeOutput(out[0])

NODE_CLASS_MAPPINGS = {
    'TorchCompileModelFluxAdvancedSecure': TorchCompileModelFluxAdvancedSecure,
    'TorchCompileLTXModelSecure': TorchCompileLTXModelSecure,
    'TorchCompileCosmosModelSecure': TorchCompileCosmosModelSecure,
    'TorchCompileModelHyVideoSecure': TorchCompileModelHyVideoSecure,
    'TorchCompileModelQwenImageSecure': TorchCompileModelQwenImageSecure,
    'TorchCompileModelWanVideoSecure': TorchCompileModelWanVideoSecure,
    'ModelPassThroughSecure': ModelPassThroughSecure,
    'CondPassThroughSecure': CondPassThroughSecure,
    'TimerNodeKJSecure': TimerNodeKJSecure,
    'ConditioningMultiCombineSecure': ConditioningMultiCombineSecure,
    'ConditioningSetMaskAndCombineSecure': ConditioningSetMaskAndCombineSecure,
    'ConditioningSetMaskAndCombine3Secure': ConditioningSetMaskAndCombine3Secure,
    'ConditioningSetMaskAndCombine4Secure': ConditioningSetMaskAndCombine4Secure,
    'ConditioningSetMaskAndCombine5Secure': ConditioningSetMaskAndCombine5Secure,
    'EmptyLatentImagePresetsSecure': EmptyLatentImagePresetsSecure,
    'GetTrackRangeSecure': GetTrackRangeSecure,
    'AddNoiseToTrackPathSecure': AddNoiseToTrackPathSecure,
    'AudioConcatenateSecure': AudioConcatenateSecure,
    'VAEDecodeLoopKJSecure': VAEDecodeLoopKJSecure,
    'WanImageToVideoSVIProSecure': WanImageToVideoSVIProSecure,
    'GenerateNoiseSecure': GenerateNoiseSecure,
    'StableZero123_BatchScheduleSecure': StableZero123BatchScheduleSecure,
    'SV3D_BatchScheduleSecure': SV3DBatchScheduleSecure,
    'SetShakkerLabsUnionControlNetTypeSecure': SetShakkerLabsUnionControlNetTypeSecure,
    'WidgetToStringSecure': WidgetToStringSecure,
    'StyleModelApplyAdvancedSecure': StyleModelApplyAdvancedSecure,
    'CameraPoseVisualizerSecure': CameraPoseVisualizerSecure,
    'EmptyLatentImageCustomPresetsSecure': EmptyLatentImageCustomPresetsSecure,
    'VAEMergeKJSecure': VAEMergeKJSecure,
    'PlaySoundKJSecure': PlaySoundKJSecure,
    'VRAMDebugSecure': VRAMDebugSecure,
    'VAELoaderKJSecure': VAELoaderKJSecure,
    'DifferentialDiffusionAdvancedSecure': DifferentialDiffusionAdvancedSecure,
    'ApplyRifleXRoPEWanVideoSecure': ApplyRifleXRoPEWanVideoSecure,
    'ApplyRifleXRoPEHunuyanVideoSecure': ApplyRifleXRoPEHunuyanVideoSecure,
    'ModelSaveKJSecure': ModelSaveKJSecure,
    'CheckpointPerturbWeightsSecure': CheckpointPerturbWeightsSecure,
    'HunyuanVideoEncodeKeyframesToCondSecure': HunyuanVideoEncodeKeyframesToCondSecure,
    'LatentInpaintTTMSecure': LatentInpaintTTMSecure,
    'LeapfusionHunyuanI2VPatcherSecure': LeapfusionHunyuanI2VPatcherSecure,
    'CustomControlNetWeightsFluxFromListSecure': CustomControlNetWeightsFluxFromListSecure,
    'DiTBlockLoraLoaderSecure': DiTBlockLoraLoaderSecure,
    'SuperpromptSecure': SuperpromptSecure,
    'ScheduledCFGGuidanceSecure': ScheduledCFGGuidanceSecure,
    'BOOLConstantSecure': BOOLConstantSecure,
    'AppendStringsToListSecure': AppendStringsToListSecure,
    'CustomSigmasSecure': CustomSigmasSecure,
    'DummyOutSecure': DummyOutSecure,
    'FlipSigmasAdjustedSecure': FlipSigmasAdjustedSecure,
    'FloatConstantSecure': FloatConstantSecure,
    'FluxBlockLoraSelectSecure': FluxBlockLoraSelectSecure,
    'GetLatentsFromBatchIndexedSecure': GetLatentsFromBatchIndexedSecure,
    'HunyuanVideoBlockLoraSelectSecure': HunyuanVideoBlockLoraSelectSecure,
    'INTConstantSecure': INTConstantSecure,
    'ImageNoiseAugmentationSecure': ImageNoiseAugmentationSecure,
    'InjectNoiseToLatentSecure': InjectNoiseToLatentSecure,
    'JoinStringsSecure': JoinStringsSecure,
    'JoinStringMultiSecure': JoinStringMultiSecure,
    'LTX2BlockLoraSelectSecure': LTX2BlockLoraSelectSecure,
    'LazySwitchKJSecure': LazySwitchKJSecure,
    'PreviewLatentNoiseMaskSecure': PreviewLatentNoiseMaskSecure,
    'ScaleBatchPromptScheduleSecure': ScaleBatchPromptScheduleSecure,
    'SimpleCalculatorKJSecure': SimpleCalculatorKJSecure,
    'SleepSecure': SleepSecure,
    'SomethingToStringSecure': SomethingToStringSecure,
    'SoundReactiveSecure': SoundReactiveSecure,
    'StringConstantSecure': StringConstantSecure,
    'StringConstantMultilineSecure': StringConstantMultilineSecure,
    'StringToFloatListSecure': StringToFloatListSecure,
    'VisualizeSigmasKJSecure': VisualizeSigmasKJSecure,
    'Wan21BlockLoraSelectSecure': Wan21BlockLoraSelectSecure,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    'TorchCompileModelFluxAdvancedSecure': 'TorchCompileModelFluxAdvanced (Secure V2)',
    'TorchCompileLTXModelSecure': 'TorchCompileLTXModel (Secure V2)',
    'TorchCompileCosmosModelSecure': 'TorchCompileCosmosModel (Secure V2)',
    'TorchCompileModelHyVideoSecure': 'TorchCompileModelHyVideo (Secure V2)',
    'TorchCompileModelQwenImageSecure': 'TorchCompileModelQwenImage (Secure V2)',
    'TorchCompileModelWanVideoSecure': 'TorchCompileModelWanVideo (Secure V2)',
    'ModelPassThroughSecure': '🔒 Model Pass Through (secure)',
    'CondPassThroughSecure': '🔒 Cond Pass Through (secure)',
    'TimerNodeKJSecure': '🔒 Timer (secure)',
    'ConditioningMultiCombineSecure': '🔒 Conditioning Multi Combine (secure)',
    'ConditioningSetMaskAndCombineSecure': '🔒 Conditioning Set Mask And Combine (secure)',
    'ConditioningSetMaskAndCombine3Secure': '🔒 Conditioning Set Mask And Combine 3 (secure)',
    'ConditioningSetMaskAndCombine4Secure': '🔒 Conditioning Set Mask And Combine 4 (secure)',
    'ConditioningSetMaskAndCombine5Secure': '🔒 Conditioning Set Mask And Combine 5 (secure)',
    'EmptyLatentImagePresetsSecure': '🔒 Empty Latent Image Presets (secure)',
    'GetTrackRangeSecure': '🔒 Get Track Range (secure)',
    'AddNoiseToTrackPathSecure': '🔒 Add Noise To Track (secure)',
    'AudioConcatenateSecure': '🔒 Audio Concatenate (secure)',
    'VAEDecodeLoopKJSecure': '🔒 VAE Decode Loop KJ (secure)',
    'WanImageToVideoSVIProSecure': '🔒 Wan Image To Video SVI Pro (secure)',
    'GenerateNoiseSecure': '🔒 Generate Noise (secure)',
    'StableZero123_BatchScheduleSecure': '🔒 Stable Zero123 Batch Schedule (secure)',
    'SV3D_BatchScheduleSecure': '🔒 SV3D Batch Schedule (secure)',
    'SetShakkerLabsUnionControlNetTypeSecure': '🔒 Set Shakker Labs Union ControlNet Type (secure)',
    'WidgetToStringSecure': '🔒 Widget To String (secure)',
    'StyleModelApplyAdvancedSecure': '🔒 Style Model Apply Advanced (secure)',
    'CameraPoseVisualizerSecure': '🔒 Camera Pose Visualizer (secure)',
    'EmptyLatentImageCustomPresetsSecure': '🔒 Empty Latent Image Custom Presets (secure)',
    'VAEMergeKJSecure': '🔒 VAE Merge KJ (secure)',
    'PlaySoundKJSecure': '🔒 Play Sound KJ (secure)',
    'VRAMDebugSecure': 'VRAM Debug (Secure V2)',
    'VAELoaderKJSecure': 'VAELoader KJ (Secure V2)',
    'DifferentialDiffusionAdvancedSecure': '🔒 Differential Diffusion Advanced (secure)',
    'ApplyRifleXRoPEWanVideoSecure': '🔒 ApplyRifleXRoPEWanVideo (secure)',
    'ApplyRifleXRoPEHunuyanVideoSecure': '🔒 ApplyRifleXRoPEHunuyanVideo (secure)',
    'ModelSaveKJSecure': '🔒 Model Save KJ (secure)',
    'CheckpointPerturbWeightsSecure': '🔒 Checkpoint Perturb Weights (secure)',
    'HunyuanVideoEncodeKeyframesToCondSecure': '🔒 Hunyuan Video Encode Keyframes To Cond (secure)',
    'LatentInpaintTTMSecure': '🔒 Latent Inpaint TTM (secure)',
    'LeapfusionHunyuanI2VPatcherSecure': '🔒 Leapfusion Hunyuan I2V Patcher (secure)',
    'CustomControlNetWeightsFluxFromListSecure': '🔒 Custom ControlNet Weights Flux From List (secure)',
    'DiTBlockLoraLoaderSecure': '🔒 DiT Block LoRA Loader (secure)',
    'SuperpromptSecure': 'Superprompt (secure)',
    'ScheduledCFGGuidanceSecure': 'Scheduled CFG Guidance (Secure V2)',
    'BOOLConstantSecure': '🔒 BOOL Constant (secure)',
    'AppendStringsToListSecure': '🔒 Append Strings To List (secure)',
    'CustomSigmasSecure': '🔒 Custom Sigmas (secure)',
    'DummyOutSecure': '🔒 Dummy Out (secure)',
    'FlipSigmasAdjustedSecure': '🔒 Flip Sigmas Adjusted (secure)',
    'FloatConstantSecure': '🔒 Float Constant (secure)',
    'FluxBlockLoraSelectSecure': '🔒 Flux Block Lora Select (secure)',
    'GetLatentsFromBatchIndexedSecure': '🔒 Get Latents From Batch Indexed (secure)',
    'HunyuanVideoBlockLoraSelectSecure': '🔒 Hunyuan Video Block Lora Select (secure)',
    'INTConstantSecure': '🔒 INT Constant (secure)',
    'ImageNoiseAugmentationSecure': '🔒 Image Noise Augmentation (secure)',
    'InjectNoiseToLatentSecure': '🔒 Inject Noise To Latent (secure)',
    'JoinStringsSecure': '🔒 Join Strings (secure)',
    'JoinStringMultiSecure': '🔒 Join String Multi (secure)',
    'LTX2BlockLoraSelectSecure': '🔒 LTX2 Block Lora Select (secure)',
    'LazySwitchKJSecure': '🔒 Lazy Switch KJ (secure)',
    'PreviewLatentNoiseMaskSecure': '🔒 Preview Latent Noise Mask (secure)',
    'ScaleBatchPromptScheduleSecure': '🔒 Scale Batch Prompt Schedule (secure)',
    'SimpleCalculatorKJSecure': '🔒 Simple Calculator KJ (secure)',
    'SleepSecure': '🔒 Sleep (secure)',
    'SomethingToStringSecure': '🔒 Something To String (secure)',
    'SoundReactiveSecure': '🔒 Sound Reactive (secure)',
    'StringConstantSecure': '🔒 String Constant (secure)',
    'StringConstantMultilineSecure': '🔒 String Constant Multiline (secure)',
    'StringToFloatListSecure': '🔒 String to Float List (secure)',
    'VisualizeSigmasKJSecure': '🔒 Visualize Sigmas KJ (secure)',
    'Wan21BlockLoraSelectSecure': '🔒 Wan21 Block Lora Select (secure)',
}
