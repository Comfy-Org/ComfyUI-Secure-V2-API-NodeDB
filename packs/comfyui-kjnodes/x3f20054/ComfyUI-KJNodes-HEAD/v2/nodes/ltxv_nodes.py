from __future__ import annotations
from comfy_api.latest import io as _ffn_chunking_io

class LTXVChunkFeedForwardSecure(_ffn_chunking_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _ffn_chunking_io.Schema:
        return _ffn_chunking_io.Schema(node_id='LTXVChunkFeedForwardSecure', display_name='LTXV Chunk FeedForward (Secure V2)', category='KJNodes/ltxv', description='EXPERIMENTAL AND MAY CHANGE THE MODEL OUTPUT!! Chunks feedforward activations to reduce peak VRAM usage.', is_experimental=True, inputs=[_ffn_chunking_io.Model.Input('model'), _ffn_chunking_io.Int.Input('chunks', default=2, min=1, max=100, step=1, tooltip='Number of chunks to split the feedforward activations into to reduce peak VRAM usage.'), _ffn_chunking_io.Int.Input('dim_threshold', default=4096, min=0, max=16384, step=256, tooltip='Dimension threshold above which to apply chunking.')], outputs=[_ffn_chunking_io.Model.Output('model', display_name='model')])

    @classmethod
    async def execute(cls, model, chunks, dim_threshold) -> _ffn_chunking_io.NodeOutput:
        if chunks == 1:
            return _ffn_chunking_io.NodeOutput(model)
        patched = await model.patch('ffn_chunking', chunks=int(chunks), dim_threshold=int(dim_threshold), target='ltx_transformer_ff')
        return _ffn_chunking_io.NodeOutput(patched)
import ast as _ltxv_ast
import os as _ltxv_os
import numpy as _ltxv_np
import torch as _ltxv_torch
from comfy_api.latest import io as _ltxv_io, sdk as _ltxv_sdk
from . import _packload as _ltxv_packload
_ltxv_SOURCE = _ltxv_os.path.join(_ltxv_packload.ROOT, 'nodes', 'ltxv_nodes.py')
_ltxv_EXECUTE = None

def _ltxv_upstream_execute():
    """`LTXVAudioVideoMask.execute`, compiled out of upstream's own source.

    The namespace it is given holds `torch`, `np` and `io` and NOTHING else,
    which is the whole safety argument: those three are the function's entire
    set of free names today, and if upstream grows a dependency on the host
    surface sitting around it in that file, this raises `NameError` naming the
    symbol rather than resolving it against something invented in here.
    """
    global _ltxv_EXECUTE
    if _ltxv_EXECUTE is not None:
        return _ltxv_EXECUTE
    source = open(_ltxv_SOURCE).read()
    tree = _ltxv_ast.parse(source)
    fn_src = None
    for node in _ltxv_ast.walk(tree):
        if isinstance(node, _ltxv_ast.ClassDef) and node.name == 'LTXVAudioVideoMask':
            for item in node.body:
                if isinstance(item, _ltxv_ast.FunctionDef) and item.name == 'execute':
                    fn_src = _ltxv_ast.get_source_segment(source, item)
    if fn_src is None:
        raise RuntimeError(f'LTXVAudioVideoMask.execute not found in {_ltxv_SOURCE} — the pack changed shape and this conversion must be revisited')
    ns = {'torch': _ltxv_torch, 'np': _ltxv_np, 'io': _ltxv_io}
    exec(compile(_ltxv_ast.parse(fn_src), '<kjnodes.LTXVAudioVideoMask.execute>', 'exec'), ns)
    _ltxv_EXECUTE = ns['execute']
    return _ltxv_EXECUTE

class LTXVAudioVideoMaskSecure(_ltxv_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _ltxv_io.Schema:
        return _ltxv_io.Schema(node_id='LTXVAudioVideoMaskSecure', display_name='🔒 LTXVAudioVideoMask (secure)', category='KJNodes/ltxv', description='Creates noise masks for video and audio latents based on specified time ranges. New content is generated within these masked regions', inputs=[_ltxv_io.Latent.Input('video_latent', optional=True), _ltxv_io.Latent.Input('audio_latent', optional=True), _ltxv_io.Float.Input('video_fps', default=25, min=0.0, max=100.0, step=0.01), _ltxv_io.Float.Input('video_start_time', default=0.0, min=0.0, max=10000.0, step=0.01, tooltip='Start time in seconds for the video mask.'), _ltxv_io.Float.Input('video_end_time', default=5.0, min=0.0, max=10000.0, step=0.01, tooltip='End time in seconds for the video mask.'), _ltxv_io.Float.Input('audio_start_time', default=0.0, min=0.0, max=10000.0, step=0.01, tooltip='Start time in seconds for the audio mask.'), _ltxv_io.Float.Input('audio_end_time', default=5.0, min=0.0, max=10000.0, step=0.01, tooltip='End time in seconds for the audio mask.'), _ltxv_io.Combo.Input('max_length', options=['truncate', 'pad', 'partial'], default='truncate', tooltip="'truncate': cut latent to end_time length. 'pad': extend latent to end_time. 'partial': mask range within existing latent."), _ltxv_io.Combo.Input('existing_mask_mode', options=['add', 'subtract', 'overwrite'], optional=True, default='add', tooltip="How to combine with existing noise masks if present. 'add' will take the max of existing and new mask, 'overwrite' will replace with new mask. 'subtract' will set the masked region to 0 instead of 1, effectively unmasking it.")], outputs=[_ltxv_io.Latent.Output(display_name='video_latent'), _ltxv_io.Latent.Output(display_name='audio_latent')])

    @classmethod
    async def execute(cls, video_fps, video_start_time, video_end_time, audio_start_time, audio_end_time, max_length='truncate', existing_mask_mode='add', video_latent=None, audio_latent=None) -> _ltxv_io.NodeOutput:
        video_value = None if video_latent is None else await video_latent.value()
        audio_value = None if audio_latent is None else await audio_latent.value()
        out = _ltxv_upstream_execute()(cls, video_fps, video_start_time, video_end_time, audio_start_time, audio_end_time, max_length, existing_mask_mode, video_value, audio_value)
        video_out, audio_out = out.result
        return _ltxv_io.NodeOutput(None if video_out is None else await _ltxv_sdk.LatentRef.from_value(video_out), None if audio_out is None else await _ltxv_sdk.LatentRef.from_value(audio_out))
import torch as _remaining_m_torch
from comfy_api.latest import io as _remaining_m_io, sdk as _remaining_m_sdk
from ._ltx_utils import GuideOps as _remaining_m_GuideOps, append_guide_attention_entry as _remaining_m_append_guide_attention_entry, get_noise_mask as _remaining_m_get_noise_mask
from ._tensor_utils import common_upscale as _remaining_m_common_upscale

def _remaining_m_guide_helpers():
    return (_remaining_m_GuideOps, _remaining_m_get_noise_mask, _remaining_m_append_guide_attention_entry)

async def _remaining_m_structured(value):
    if isinstance(value, _remaining_m_sdk.ValueRef):
        return await value.value()
    return value

async def _remaining_m_scale_factors(vae):
    factors = await vae.downscale_index_formula()
    if factors is None:
        raise ValueError('this VAE does not define a downscale_index_formula')
    return factors

async def _remaining_m_encode(vae, latent_width, latent_height, images, scale_factors):
    time_scale_factor, width_scale_factor, height_scale_factor = scale_factors
    frame_count = (images.shape[0] - 1) // time_scale_factor * time_scale_factor + 1
    images = images[:frame_count]
    target_width = int(latent_width * width_scale_factor)
    target_height = int(latent_height * height_scale_factor)
    pixels = _remaining_m_common_upscale(images.movedim(-1, 1), target_width, target_height, 'bilinear', crop='center').movedim(1, -1)
    encode_pixels = pixels[..., :3]
    image_ref = await _remaining_m_sdk.ImageRef._from_raw(encode_pixels)
    latent_ref = await vae.encode(image_ref)
    samples = (await latent_ref.value())['samples']
    return (encode_pixels, samples)

def _remaining_m_guide_options(image_optional, index_name):
    options = []
    for count in range(1, 21):
        inputs = []
        for index in range(1, count + 1):
            inputs.extend([_remaining_m_io.Image.Input(f'image_{index}', optional=image_optional), _remaining_m_io.Int.Input(f'{index_name}_{index}', default=0, min=-9999, max=9999, step=1, optional=image_optional), _remaining_m_io.Float.Input(f'strength_{index}', default=1.0, min=0.0, max=10.0 if index_name == 'frame_idx' else 1.0, step=0.01)])
        options.append(_remaining_m_io.DynamicCombo.Option(key=str(count), inputs=inputs))
    return options

class LTXVAddGuideMultiSecure(_remaining_m_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return _remaining_m_io.Schema(node_id='LTXVAddGuideMultiSecure', display_name='🔒 LTXV Add Guide Multi (secure)', category='KJNodes/ltxv', description='Add multiple guide images at specified frame indices and strengths.', inputs=[_remaining_m_io.Conditioning.Input('positive'), _remaining_m_io.Conditioning.Input('negative'), _remaining_m_io.Vae.Input('vae'), _remaining_m_io.Latent.Input('latent'), _remaining_m_io.DynamicCombo.Input('num_guides', options=_remaining_m_guide_options(False, 'frame_idx'), display_name='Number of Guides')], outputs=[_remaining_m_io.Conditioning.Output('positive', display_name='positive'), _remaining_m_io.Conditioning.Output('negative', display_name='negative'), _remaining_m_io.Latent.Output('latent', display_name='latent')])

    @classmethod
    async def execute(cls, positive, negative, vae, latent, num_guides):
        guide_ops, _remaining_m_get_noise_mask, append_attention = _remaining_m_guide_helpers()
        positive_value = await positive.value()
        negative_value = await negative.value()
        latent_value = await latent.value()
        guides = await _remaining_m_structured(num_guides)
        scale_factors = await _remaining_m_scale_factors(vae)
        latent_image = latent_value['samples']
        noise_mask = _remaining_m_get_noise_mask(latent_value)
        _, _, latent_length, latent_height, latent_width = latent_image.shape
        image_keys = sorted((key for key in guides if key.startswith('image_')))
        for image_key in image_keys:
            index = image_key.split('_')[1]
            image = guides[image_key]
            frame_index = guides[f'frame_idx_{index}']
            strength = guides[f'strength_{index}']
            encoded_pixels, guiding_latent = await _remaining_m_encode(vae, latent_width, latent_height, image, scale_factors)
            frame_index, latent_index = guide_ops.get_latent_index(positive_value, latent_length, len(encoded_pixels), frame_index, scale_factors)
            if latent_index + guiding_latent.shape[2] > latent_length:
                raise AssertionError('Conditioning frames exceed the length of the latent sequence.')
            positive_value, negative_value, latent_image, noise_mask = guide_ops.append_keyframe(positive_value, negative_value, frame_index, latent_image, noise_mask, guiding_latent, strength, scale_factors)
            latent_shape = list(guiding_latent.shape[2:])
            token_count = guiding_latent.shape[2] * guiding_latent.shape[3] * guiding_latent.shape[4]
            positive_value, negative_value = append_attention(positive_value, negative_value, token_count, latent_shape, strength=strength)
        return _remaining_m_io.NodeOutput(await _remaining_m_sdk.CondRef.from_value(positive_value), await _remaining_m_sdk.CondRef.from_value(negative_value), await _remaining_m_sdk.LatentRef.from_value({'samples': latent_image, 'noise_mask': noise_mask}))

class LTXVAddGuidesFromBatchSecure(_remaining_m_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return _remaining_m_io.Schema(node_id='LTXVAddGuidesFromBatchSecure', display_name='🔒 LTXV Add Guides From Batch (secure)', category='conditioning/ltxv', description='Use each non-black batch image as an LTX guide at its batch frame index.', inputs=[_remaining_m_io.Conditioning.Input('positive'), _remaining_m_io.Conditioning.Input('negative'), _remaining_m_io.Vae.Input('vae'), _remaining_m_io.Latent.Input('latent'), _remaining_m_io.Image.Input('images'), _remaining_m_io.Float.Input('strength', default=1.0, min=0.0, max=10.0, step=0.01)], outputs=[_remaining_m_io.Conditioning.Output('positive', display_name='positive'), _remaining_m_io.Conditioning.Output('negative', display_name='negative'), _remaining_m_io.Latent.Output('latent', display_name='latent')])

    @classmethod
    async def execute(cls, positive, negative, vae, latent, images, strength):
        guide_ops, _remaining_m_get_noise_mask, append_attention = _remaining_m_guide_helpers()
        positive_value = await positive.value()
        negative_value = await negative.value()
        latent_value = await latent.value()
        image_batch = await images.raw()
        scale_factors = await _remaining_m_scale_factors(vae)
        latent_image = latent_value['samples']
        noise_mask = _remaining_m_get_noise_mask(latent_value)
        _, _, latent_length, latent_height, latent_width = latent_image.shape
        for index in range(image_batch.shape[0]):
            image = image_batch[index:index + 1]
            if image.max() <= 0.001:
                continue
            encoded_pixels, guiding_latent = await _remaining_m_encode(vae, latent_width, latent_height, image, scale_factors)
            frame_index, latent_index = guide_ops.get_latent_index(positive_value, latent_length, len(encoded_pixels), index, scale_factors)
            if latent_index + guiding_latent.shape[2] > latent_length:
                print(f'Warning: Skipping guide at index {index} - conditioning frames exceed latent sequence length')
                continue
            positive_value, negative_value, latent_image, noise_mask = guide_ops.append_keyframe(positive_value, negative_value, frame_index, latent_image, noise_mask, guiding_latent, strength, scale_factors)
            latent_shape = list(guiding_latent.shape[2:])
            token_count = guiding_latent.shape[2] * guiding_latent.shape[3] * guiding_latent.shape[4]
            positive_value, negative_value = append_attention(positive_value, negative_value, token_count, latent_shape, strength=strength)
        return _remaining_m_io.NodeOutput(await _remaining_m_sdk.CondRef.from_value(positive_value), await _remaining_m_sdk.CondRef.from_value(negative_value), await _remaining_m_sdk.LatentRef.from_value({'samples': latent_image, 'noise_mask': noise_mask}))

class LTXVImgToVideoInplaceKJSecure(_remaining_m_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return _remaining_m_io.Schema(node_id='LTXVImgToVideoInplaceKJSecure', display_name='🔒 LTXV Img To Video Inplace KJ (secure)', category='KJNodes/ltxv', description='Replace selected video latent frames with encoded images.', inputs=[_remaining_m_io.Vae.Input('vae'), _remaining_m_io.Latent.Input('latent'), _remaining_m_io.DynamicCombo.Input('num_images', options=_remaining_m_guide_options(True, 'index'), display_name='Number of Images')], outputs=[_remaining_m_io.Latent.Output(display_name='latent')])

    @classmethod
    async def execute(cls, vae, latent, num_images):
        latent_value = await latent.value()
        images = await _remaining_m_structured(num_images)
        scale_factors = await _remaining_m_scale_factors(vae)
        samples = latent_value['samples'].clone()
        _, height_scale_factor, width_scale_factor = scale_factors
        batch, _, latent_frames, latent_height, latent_width = samples.shape
        width = latent_width * width_scale_factor
        height = latent_height * height_scale_factor
        if 'noise_mask' in latent_value:
            noise_mask = latent_value['noise_mask'].clone()
        else:
            noise_mask = _remaining_m_torch.ones((batch, 1, latent_frames, 1, 1), dtype=_remaining_m_torch.float32, device=samples.device)
        image_keys = sorted((key for key in images if key.startswith('image_')))
        for image_key in image_keys:
            index = image_key.split('_')[1]
            image = images[image_key]
            frame_index = images.get(f'index_{index}')
            if image is None or frame_index is None:
                continue
            strength = images[f'strength_{index}']
            if image.shape[1] != height or image.shape[2] != width:
                pixels = _remaining_m_common_upscale(image.movedim(-1, 1), width, height, 'bilinear', 'center').movedim(1, -1)
            else:
                pixels = image
            image_ref = await _remaining_m_sdk.ImageRef._from_raw(pixels[..., :3])
            encoded_ref = await vae.encode(image_ref)
            encoded = (await encoded_ref.value())['samples']
            time_scale_factor = scale_factors[0]
            pixel_frame_count = (latent_frames - 1) * time_scale_factor + 1
            if frame_index < 0:
                frame_index = pixel_frame_count + frame_index
            latent_index = frame_index // time_scale_factor
            latent_index = max(0, min(latent_index, latent_frames - 1))
            end_index = min(latent_index + encoded.shape[2], latent_frames)
            length = end_index - latent_index
            samples[:, :, latent_index:end_index] = encoded[:, :, :length]
            noise_mask[:, :, latent_index:end_index] = 1.0 - strength
        return _remaining_m_io.NodeOutput(await _remaining_m_sdk.LatentRef.from_value({'samples': samples, 'noise_mask': noise_mask}))

class _remaining_m_VaeFormulaProbe:
    SDK_REFS = True

    @classmethod
    async def execute(cls, vae):
        formula = await vae.downscale_index_formula()
        return _remaining_m_io.NodeOutput(formula, isinstance(formula, tuple))
from comfy_api.latest import io as _remaining_zaa_io, sdk as _remaining_zaa_sdk

class LTX2SamplingPreviewOverrideSecure(_remaining_zaa_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_zaa_io.Schema:
        return _remaining_zaa_io.Schema(node_id='LTX2SamplingPreviewOverrideSecure', display_name='🔒 LTX2 Sampling Preview Override (secure)', description='Attaches the trusted LTX2 sampling preview policy while the model, optional VAE, upscaler, callbacks, and UI stay on the host.', category='KJNodes/ltxv', is_experimental=True, inputs=[_remaining_zaa_io.Model.Input('model', tooltip='The model to add preview override to.'), _remaining_zaa_io.MultiType.Input(_remaining_zaa_io.Float.Input('preview_rate', default=8.0, min=1.0, max=60.0, step=0.01, tooltip='Preview frame rate.'), [_remaining_zaa_io.Int]), _remaining_zaa_io.LatentUpscaleModel.Input('latent_upscale_model', optional=True, tooltip='Optional upscale model for higher resolution previews.'), _remaining_zaa_io.Vae.Input('vae', optional=True, tooltip='VAE used to normalize latents for the upscale model.')], outputs=[_remaining_zaa_io.Model.Output(tooltip='The model with Sampling Preview Override.')])

    @classmethod
    async def execute(cls, model, preview_rate, latent_upscale_model=None, vae=None) -> _remaining_zaa_io.NodeOutput:
        result = await _remaining_zaa_sdk.ctx().preview_override.attach_ltx2(model, preview_rate=preview_rate, latent_upscale_model=latent_upscale_model, vae=vae)
        return _remaining_zaa_io.NodeOutput(result)
from comfy_api.latest import io as _remaining_zo_io

class LTX2AudioLatentNormalizingSamplingSecure(_remaining_zo_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_zo_io.Schema:
        return _remaining_zo_io.Schema(node_id='LTX2AudioLatentNormalizingSamplingSecure', display_name='🔒 LTX2 Audio Latent Normalizing Sampling (secure)', category='KJNodes/ltxv', description='Normalizes LTX2 audio latents at selected sampling steps.', is_experimental=True, inputs=[_remaining_zo_io.Model.Input('model'), _remaining_zo_io.String.Input('audio_normalization_factors', default='1,1,0.25,1,1,0.25,1,1')], outputs=[_remaining_zo_io.Model.Output('model')])

    @classmethod
    async def execute(cls, model, audio_normalization_factors) -> _remaining_zo_io.NodeOutput:
        factors = [float(value) for value in audio_normalization_factors.strip().split(',')]
        return _remaining_zo_io.NodeOutput(await model.patch('ltx2_audio_normalization', factors=factors))
from comfy_api.latest import io as _remaining_zp_io

class LTX2NAGSecure(_remaining_zp_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_zp_io.Schema:
        return _remaining_zp_io.Schema(node_id='LTX2NAGSecure', display_name='🔒 LTX2 NAG (secure)', category='KJNodes/ltxv', description='Applies normalized-attention guidance to LTX2.', is_experimental=True, inputs=[_remaining_zp_io.Model.Input('model'), _remaining_zp_io.Float.Input('nag_scale', default=11.0, min=0.0, max=100.0, step=0.001), _remaining_zp_io.Float.Input('nag_alpha', default=0.25, min=0.0, max=1.0, step=0.001), _remaining_zp_io.Float.Input('nag_tau', default=2.5, min=0.0, max=10.0, step=0.001), _remaining_zp_io.Conditioning.Input('nag_cond_video', optional=True), _remaining_zp_io.Conditioning.Input('nag_cond_audio', optional=True), _remaining_zp_io.Boolean.Input('inplace', default=True, optional=True)], outputs=[_remaining_zp_io.Model.Output('model')])

    @classmethod
    async def execute(cls, model, nag_scale, nag_alpha, nag_tau, nag_cond_video=None, nag_cond_audio=None, inplace=True) -> _remaining_zp_io.NodeOutput:
        return _remaining_zp_io.NodeOutput(await model.patch('ltx2_nag', nag_scale=nag_scale, nag_alpha=nag_alpha, nag_tau=nag_tau, video_conditioning=nag_cond_video, audio_conditioning=nag_cond_audio, inplace=inplace))
import math as _remaining_zt_math
import re as _remaining_zt_re
from comfy_api.latest import io as _remaining_zt_io, sdk as _remaining_zt_sdk
_remaining_zt_SelectedDitBlocks = _remaining_zt_io.Custom('SELECTEDDITBLOCKS')
_remaining_zt_BLOCK_KEY = _remaining_zt_re.compile('^blocks\\.(\\d+)\\.$')

def _remaining_zt_closed_ltx2_blocks(blocks):
    if blocks is None:
        return []
    if not isinstance(blocks, dict):
        raise TypeError('blocks must be a SELECTEDDITBLOCKS mapping')
    result = []
    for key, value in blocks.items():
        match = _remaining_zt_BLOCK_KEY.fullmatch(key) if isinstance(key, str) else None
        if match is None:
            raise ValueError(f'unsupported LTX2 block key {key!r}')
        index = int(match.group(1))
        if not 0 <= index < 48:
            raise ValueError(f'LTX2 block index is out of range: {key!r}')
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f'LTX2 block ratio for {key!r} must be numeric')
        ratio = float(value)
        if not _remaining_zt_math.isfinite(ratio) or not 0.0 <= ratio <= 10000.0:
            raise ValueError(f'LTX2 block ratio for {key!r} must be in [0, 10000]')
        result.append({'family': 'blocks', 'index': index, 'ratio': ratio})
    return result

class LTX2LoraLoaderAdvancedSecure(_remaining_zt_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('assets',)

    @classmethod
    def define_schema(cls) -> _remaining_zt_io.Schema:
        return _remaining_zt_io.Schema(node_id='LTX2LoraLoaderAdvancedSecure', display_name='🔒 LTX2 LoRA Loader Advanced (secure)', category='KJNodes/ltxv', description='Apply a catalogue LoRA with per-block and per-layer LTX2 strengths. V2 accepts a logical catalogue name instead of an absolute opt_lora_path.', is_experimental=True, inputs=[_remaining_zt_io.Combo.Input('lora_name', options=[], remote=_remaining_zt_io.RemoteOptions(route='/models/loras', refresh_button=True), tooltip='A logical name from the LoRA catalogue.'), _remaining_zt_io.Model.Input('model', tooltip='The diffusion model the LoRA will be applied to.'), _remaining_zt_io.Float.Input('strength_model', default=1.0, min=-100.0, max=100.0, step=0.01, tooltip='How strongly to modify the diffusion model.'), _remaining_zt_SelectedDitBlocks.Input('blocks', optional=True, tooltip='Selected LTX2 block configuration.'), _remaining_zt_io.Float.Input('video', default=1.0, min=0.0, max=1.0, step=0.01), _remaining_zt_io.Float.Input('video_to_audio', default=1.0, min=0.0, max=1.0, step=0.01), _remaining_zt_io.Float.Input('audio', default=1.0, min=0.0, max=1.0, step=0.01), _remaining_zt_io.Float.Input('audio_to_video', default=1.0, min=0.0, max=1.0, step=0.01), _remaining_zt_io.Float.Input('other', default=1.0, min=0.0, max=1.0, step=0.01)], outputs=[_remaining_zt_io.Model.Output('model', display_name='model'), _remaining_zt_io.String.Output('rank', display_name='rank'), _remaining_zt_io.String.Output('loaded_keys_info', display_name='loaded_keys_info')])

    @classmethod
    def validate_inputs(cls, lora_name):
        if not isinstance(lora_name, str) or not lora_name:
            return 'lora_name must be a non-empty catalogue name'
        return True

    @classmethod
    async def execute(cls, lora_name, model, strength_model, video, video_to_audio, audio, audio_to_video, other, blocks=None) -> _remaining_zt_io.NodeOutput:
        asset = await _remaining_zt_sdk.ctx().assets.resolve('loras', lora_name)
        patched, rank, loaded_keys_info = await model.apply_ltx2_lora(asset=asset, strength_model=strength_model, block_weights=_remaining_zt_closed_ltx2_blocks(blocks), video=video, video_to_audio=video_to_audio, audio=audio, audio_to_video=audio_to_video, other=other)
        return _remaining_zt_io.NodeOutput(patched, rank, loaded_keys_info)
from comfy_api.latest import io as _remaining_zv_io

def _remaining_zv_blocks(value: str) -> list[int]:
    if not isinstance(value, str):
        raise TypeError('blocks must be a comma-separated string')
    if not value.strip():
        return []
    try:
        return [int(item) for item in value.strip().split(',')]
    except ValueError as error:
        raise ValueError('blocks must contain comma-separated integers') from error

class LTX2AttentionTunerPatchSecure(_remaining_zv_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_zv_io.Schema:
        return _remaining_zv_io.Schema(node_id='LTX2AttentionTunerPatchSecure', display_name='🔒 LTX2 Attention Tuner Patch (secure)', category='KJNodes/ltxv', description='Scale the four LTX2 audio/video attention paths.', is_experimental=True, inputs=[_remaining_zv_io.Model.Input('model'), _remaining_zv_io.String.Input('blocks', default=''), _remaining_zv_io.Float.Input('video_scale', default=1.0, min=0.0, max=100.0, step=0.01), _remaining_zv_io.Float.Input('audio_scale', default=1.0, min=0.0, max=100.0, step=0.01), _remaining_zv_io.Float.Input('audio_to_video_scale', default=1.0, min=0.0, max=100.0, step=0.01), _remaining_zv_io.Float.Input('video_to_audio_scale', default=1.0, min=0.0, max=100.0, step=0.01), _remaining_zv_io.Boolean.Input('triton_kernels', default=True)], outputs=[_remaining_zv_io.Model.Output('model')])

    @classmethod
    async def execute(cls, model, blocks, video_scale, audio_scale, audio_to_video_scale, video_to_audio_scale, triton_kernels) -> _remaining_zv_io.NodeOutput:
        return _remaining_zv_io.NodeOutput(await model.patch('ltx2_attention_tuner', blocks=_remaining_zv_blocks(blocks), video_scale=video_scale, audio_scale=audio_scale, audio_to_video_scale=audio_to_video_scale, video_to_audio_scale=video_to_audio_scale, triton_kernels=triton_kernels))
from comfy_api.latest import io as _remaining_zx_io

class LTX2MemoryEfficientSageAttentionPatchSecure(_remaining_zx_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_zx_io.Schema:
        return _remaining_zx_io.Schema(node_id='LTX2MemoryEfficientSageAttentionPatchSecure', display_name='🔒 LTX2 Memory Efficient Sage Attention (secure)', category='KJNodes/ltxv', is_experimental=True, inputs=[_remaining_zx_io.Model.Input('model'), _remaining_zx_io.Boolean.Input('triton_kernels', default=True)], outputs=[_remaining_zx_io.Model.Output('model')])

    @classmethod
    async def execute(cls, model, triton_kernels) -> _remaining_zx_io.NodeOutput:
        return _remaining_zx_io.NodeOutput(await model.patch('memory_efficient_sage', architecture='ltx2', triton_kernels=triton_kernels))

class WanVideoMemoryEfficientSageAttentionPatchSecure(_remaining_zx_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_zx_io.Schema:
        return _remaining_zx_io.Schema(node_id='WanVideoMemoryEfficientSageAttentionPatchSecure', display_name='🔒 Wan Memory Efficient Sage Attention (secure)', category='KJNodes/wan', is_experimental=True, inputs=[_remaining_zx_io.Model.Input('model')], outputs=[_remaining_zx_io.Model.Output('model')])

    @classmethod
    async def execute(cls, model) -> _remaining_zx_io.NodeOutput:
        return _remaining_zx_io.NodeOutput(await model.patch('memory_efficient_sage', architecture='wan', triton_kernels=False))
from comfy_api.latest import io as _remaining_zz_io

class MiniMaxH3MemoryEfficientSageAttentionPatchSecure(_remaining_zz_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_zz_io.Schema:
        return _remaining_zz_io.Schema(node_id='MiniMaxH3MemoryEfficientSageAttentionPatchSecure', display_name='MiniMax H3 Mem Eff Sage Attention Patch (Secure V2)', category='KJNodes/minimax', description='Activates host-owned memory-efficient SageAttention for MiniMax H3 self-attention.', is_experimental=True, inputs=[_remaining_zz_io.Model.Input('model')], outputs=[_remaining_zz_io.Model.Output(display_name='model')])

    @classmethod
    async def execute(cls, model) -> _remaining_zz_io.NodeOutput:
        return _remaining_zz_io.NodeOutput(await model.patch('memory_efficient_sage', architecture='minimax', triton_kernels=False))

NODE_CLASS_MAPPINGS = {
    'LTXVChunkFeedForwardSecure': LTXVChunkFeedForwardSecure,
    'LTXVAudioVideoMaskSecure': LTXVAudioVideoMaskSecure,
    'LTXVAddGuideMultiSecure': LTXVAddGuideMultiSecure,
    'LTXVAddGuidesFromBatchSecure': LTXVAddGuidesFromBatchSecure,
    'LTXVImgToVideoInplaceKJSecure': LTXVImgToVideoInplaceKJSecure,
    'LTX2SamplingPreviewOverrideSecure': LTX2SamplingPreviewOverrideSecure,
    'LTX2AudioLatentNormalizingSamplingSecure': LTX2AudioLatentNormalizingSamplingSecure,
    'LTX2NAGSecure': LTX2NAGSecure,
    'LTX2LoraLoaderAdvancedSecure': LTX2LoraLoaderAdvancedSecure,
    'LTX2AttentionTunerPatchSecure': LTX2AttentionTunerPatchSecure,
    'LTX2MemoryEfficientSageAttentionPatchSecure': LTX2MemoryEfficientSageAttentionPatchSecure,
    'WanVideoMemoryEfficientSageAttentionPatchSecure': WanVideoMemoryEfficientSageAttentionPatchSecure,
    'MiniMaxH3MemoryEfficientSageAttentionPatchSecure': MiniMaxH3MemoryEfficientSageAttentionPatchSecure,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    'LTXVChunkFeedForwardSecure': 'LTXV Chunk FeedForward (Secure V2)',
    'LTXVAudioVideoMaskSecure': '🔒 LTXVAudioVideoMask (secure)',
    'LTXVAddGuideMultiSecure': '🔒 LTXV Add Guide Multi (secure)',
    'LTXVAddGuidesFromBatchSecure': '🔒 LTXV Add Guides From Batch (secure)',
    'LTXVImgToVideoInplaceKJSecure': '🔒 LTXV Img To Video Inplace KJ (secure)',
    'LTX2SamplingPreviewOverrideSecure': '🔒 LTX2 Sampling Preview Override (secure)',
    'LTX2AudioLatentNormalizingSamplingSecure': '🔒 LTX2 Audio Latent Normalizing Sampling (secure)',
    'LTX2NAGSecure': '🔒 LTX2 NAG (secure)',
    'LTX2LoraLoaderAdvancedSecure': '🔒 LTX2 LoRA Loader Advanced (secure)',
    'LTX2AttentionTunerPatchSecure': '🔒 LTX2 Attention Tuner Patch (secure)',
    'LTX2MemoryEfficientSageAttentionPatchSecure': '🔒 LTX2 Memory Efficient Sage Attention (secure)',
    'WanVideoMemoryEfficientSageAttentionPatchSecure': '🔒 Wan Memory Efficient Sage Attention (secure)',
    'MiniMaxH3MemoryEfficientSageAttentionPatchSecure': 'MiniMax H3 Mem Eff Sage Attention Patch (Secure V2)',
}
