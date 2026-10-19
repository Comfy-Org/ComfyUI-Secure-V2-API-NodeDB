"""Source-extracted node computations; host operations use the public SDK."""
from __future__ import annotations
import torch
import numpy as np
import random
from PIL import Image, ImageDraw, ImageFont
from comfy_api.latest import sdk
from ._ops import *

class ttN_pipeLoader_v2:
    version = '2.1.0'

    async def adv_pipeloader(self, ckpt_name, config_name, vae_name, clip_skip, loras, positive, positive_token_normalization, positive_weight_interpretation, negative, negative_token_normalization, negative_weight_interpretation, empty_latent_aspect, empty_latent_width, empty_latent_height, batch_size, seed, model_override=None, clip_override=None, optional_lora_stack=None, optional_controlnet_stack=None, prepend_positive=None, prepend_negative=None, prompt=None, my_unique_id=None):
        model = None
        clip = None
        vae = None
        loader.clear_cache(prompt)
        model, clip, vae = await loader.load_main3(ckpt_name, config_name, vae_name, loras, clip_skip, model_override, clip_override, optional_lora_stack, my_unique_id)
        sd3 = True if await sampler.get_model_type(model) in ['FLUX', 'FLOW'] else False
        latent = sampler.emptyLatent(empty_latent_aspect, batch_size, empty_latent_width, empty_latent_height, sd3)
        samples = {'samples': latent}
        positive_embedding = await loader.embedding_encode(positive, positive_token_normalization, positive_weight_interpretation, clip, seed=seed, title='pipeLoader Positive', my_unique_id=my_unique_id, prepend_text=prepend_positive)
        negative_embedding = await loader.embedding_encode(negative, negative_token_normalization, negative_weight_interpretation, clip, seed=seed, title='pipeLoader Negative', my_unique_id=my_unique_id, prepend_text=prepend_negative)
        if optional_controlnet_stack is not None and len(optional_controlnet_stack) > 0:
            for cnt in optional_controlnet_stack:
                positive_embedding, negative_embedding = await loader.load_controlNet(positive_embedding, negative_embedding, cnt[0], cnt[1], cnt[2], cnt[3], cnt[4])
        image = None
        pipe = {'model': model, 'positive': positive_embedding, 'negative': negative_embedding, 'vae': vae, 'clip': clip, 'samples': samples, 'images': image, 'seed': seed, 'loader_settings': None}
        final_positive = (prepend_positive + ' ' if prepend_positive else '') + (positive + ' ' if positive else '')
        final_negative = (prepend_negative + ' ' if prepend_negative else '') + (negative + ' ' if negative else '')
        return (pipe, model, positive_embedding, negative_embedding, samples, vae, clip, seed, empty_latent_width, empty_latent_height, final_positive, final_negative)

class ttN_pipeKSampler_v2:
    version = '2.3.1'

    def __init__(self):
        pass

    async def sample(self, pipe, lora_name, lora_strength, steps, cfg, sampler_name, scheduler, image_output, save_prefix, file_type, embed_workflow, denoise=1.0, optional_model=None, optional_positive=None, optional_negative=None, optional_latent=None, optional_vae=None, optional_clip=None, input_image_override=None, seed=None, adv_xyPlot=None, upscale_model_name=None, upscale_method=None, factor=None, rescale=None, percent=None, width=None, height=None, longer_side=None, crop=None, prompt=None, extra_pnginfo=None, my_unique_id=None, start_step=None, last_step=None, force_full_denoise=False, disable_noise=False):
        my_unique_id = int(my_unique_id)
        ttN_save = ttNsave(my_unique_id, prompt, extra_pnginfo)
        samp_model = optional_model if optional_model is not None else pipe['model']
        samp_positive = optional_positive if optional_positive is not None else pipe['positive']
        samp_negative = optional_negative if optional_negative is not None else pipe['negative']
        samp_samples = optional_latent if optional_latent is not None else pipe['samples']
        samp_images = input_image_override if input_image_override is not None else pipe['images']
        samp_vae = optional_vae if optional_vae is not None else pipe['vae']
        samp_clip = optional_clip if optional_clip is not None else pipe['clip']
        if seed in (None, 'undefined'):
            samp_seed = pipe['seed']
        else:
            samp_seed = seed
        del pipe

        async def process_sample_state(samp_model, samp_images, samp_clip, samp_samples, samp_vae, samp_seed, samp_positive, samp_negative, lora_name, lora_model_strength, lora_clip_strength, upscale_model_name, upscale_method, factor, rescale, percent, width, height, longer_side, crop, steps, cfg, sampler_name, scheduler, denoise, image_output, save_prefix, file_type, embed_workflow, prompt, extra_pnginfo, my_unique_id, preview_latent, start_step=start_step, last_step=last_step, force_full_denoise=force_full_denoise, disable_noise=disable_noise):
            if lora_name not in (None, 'None'):
                samp_model, samp_clip = await loader.load_lora(lora_name, samp_model, samp_clip, lora_model_strength, lora_clip_strength)
            if upscale_method != 'None':
                samp_samples = await sampler.handle_upscale(samp_samples, upscale_method, factor, crop, upscale_model_name, samp_vae, samp_images, rescale, percent, width, height, longer_side)
            samp_samples = await sampler.common_ksampler(samp_model, samp_seed, steps, cfg, sampler_name, scheduler, samp_positive, samp_negative, samp_samples, denoise=denoise, preview_latent=preview_latent, start_step=start_step, last_step=last_step, force_full_denoise=force_full_denoise, disable_noise=disable_noise)
            results = list()
            if image_output != 'Disabled':
                latent = samp_samples['samples']
                samp_images = await vae_decode(samp_vae, latent)
                results = await ttN_save.images(samp_images, save_prefix, image_output, embed_workflow, file_type)
            new_pipe = {'model': samp_model, 'positive': samp_positive, 'negative': samp_negative, 'vae': samp_vae, 'clip': samp_clip, 'samples': samp_samples, 'images': samp_images, 'seed': samp_seed, 'loader_settings': None}
            if image_output in ('Hide', 'Hide/Save', 'Disabled'):
                return (*sampler.get_output(new_pipe), None)
            return {'ui': {'images': results}, 'result': (*sampler.get_output(new_pipe), None)}

        async def process_xyPlot(samp_model, samp_clip, samp_samples, samp_vae, samp_seed, samp_positive, samp_negative, lora_name, lora_model_strength, lora_clip_strength, steps, cfg, sampler_name, scheduler, denoise, image_output, save_prefix, file_type, embed_workflow, prompt, extra_pnginfo, my_unique_id, preview_latent, adv_xyPlot):
            raise RuntimeError('Embedded XY plotting through this sampler is unavailable in the current secure profile. Disconnect adv_xyPlot for ordinary sampling, or use the separate advanced branch plot within its supported scope.')
        preview_latent = True
        if image_output in ('Hide', 'Hide/Save', 'Disabled'):
            preview_latent = False
        if adv_xyPlot is None:
            return await process_sample_state(samp_model, samp_images, samp_clip, samp_samples, samp_vae, samp_seed, samp_positive, samp_negative, lora_name, lora_strength, lora_strength, upscale_model_name, upscale_method, factor, rescale, percent, width, height, longer_side, crop, steps, cfg, sampler_name, scheduler, denoise, image_output, save_prefix, file_type, embed_workflow, prompt, extra_pnginfo, my_unique_id, preview_latent)
        else:
            return await process_xyPlot(samp_model, samp_clip, samp_samples, samp_vae, samp_seed, samp_positive, samp_negative, lora_name, lora_strength, lora_strength, steps, cfg, sampler_name, scheduler, denoise, image_output, save_prefix, file_type, embed_workflow, prompt, extra_pnginfo, my_unique_id, preview_latent, adv_xyPlot)

class ttN_pipeKSamplerAdvanced_v2:
    version = '2.3.0'

    def __init__(self):
        pass

    async def adv_sample(self, pipe, lora_name, lora_strength, add_noise, steps, cfg, sampler_name, scheduler, image_output, save_prefix, file_type, embed_workflow, noise, noise_seed=None, optional_model=None, optional_positive=None, optional_negative=None, optional_latent=None, optional_vae=None, optional_clip=None, input_image_override=None, adv_xyPlot=None, upscale_method=None, upscale_model_name=None, factor=None, rescale=None, percent=None, width=None, height=None, longer_side=None, crop=None, prompt=None, extra_pnginfo=None, my_unique_id=None, start_at_step=None, end_at_step=None, return_with_leftover_noise=False):
        force_full_denoise = True
        if return_with_leftover_noise == 'enable':
            force_full_denoise = False
        disable_noise = False
        if add_noise == 'disable':
            disable_noise = True
        return await ttN_pipeKSampler_v2.sample(self, pipe, lora_name, lora_strength, steps, cfg, sampler_name, scheduler, image_output, save_prefix, file_type, embed_workflow, noise, optional_model, optional_positive, optional_negative, optional_latent, optional_vae, optional_clip, input_image_override, noise_seed, adv_xyPlot, upscale_model_name, upscale_method, factor, rescale, percent, width, height, longer_side, crop, prompt, extra_pnginfo, my_unique_id, start_at_step, end_at_step, force_full_denoise, disable_noise)

class ttN_pipeLoaderSDXL_v2:
    version = '2.1.0'

    async def sdxl_pipeloader(self, ckpt_name, config_name, vae_name, clip_skip, loras, refiner_ckpt_name, refiner_config_name, conditioning_aspect, conditioning_width, conditioning_height, crop_width, crop_height, target_aspect, target_width, target_height, positive_g, positive_l, negative_g, negative_l, positive_ascore, negative_ascore, empty_latent_aspect, empty_latent_width, empty_latent_height, batch_size, seed, model_override=None, clip_override=None, optional_lora_stack=None, optional_controlnet_stack=None, refiner_model_override=None, refiner_clip_override=None, prepend_positive_g=None, prepend_positive_l=None, prepend_negative_g=None, prepend_negative_l=None, prompt=None, my_unique_id=None):
        model = None
        clip = None
        vae = None
        loader.clear_cache(prompt)
        model, clip, vae = await loader.load_main3(ckpt_name, config_name, vae_name, loras, clip_skip, model_override, clip_override, optional_lora_stack, my_unique_id)
        sd3 = True if await sampler.get_model_type(model) in ['FLUX', 'FLOW'] else False
        latent = sampler.emptyLatent(empty_latent_aspect, batch_size, empty_latent_width, empty_latent_height, sd3)
        samples = {'samples': latent}
        if refiner_ckpt_name not in ['None', None]:
            refiner_model, refiner_clip, refiner_vae = await loader.load_main3(refiner_ckpt_name, refiner_config_name, vae_name, None, clip_skip, refiner_model_override, refiner_clip_override)
        else:
            refiner_model, refiner_clip, refiner_vae = (None, None, None)
        if empty_latent_aspect and empty_latent_aspect != 'width x height [custom]':
            empty_latent_width, empty_latent_height = empty_latent_aspect.replace(' ', '').split('[')[0].split('x')
        if conditioning_aspect and conditioning_aspect != 'width x height [custom]':
            conditioning_factor = conditioning_aspect.split('x')[0]
            conditioning_width = int(conditioning_factor) * int(empty_latent_width)
            conditioning_height = int(conditioning_factor) * int(empty_latent_height)
        if target_aspect and target_aspect != 'width x height [custom]':
            target_factor = target_aspect.split('x')[0]
            target_width = int(target_factor) * int(empty_latent_width)
            target_height = int(target_factor) * int(empty_latent_height)
        positive_embedding, refiner_positive_embedding = await loader.embedding_encodeXL(positive_g, clip, seed=seed, title='pipeLoaderSDXL Positive', my_unique_id=my_unique_id, prepend_text=prepend_positive_g, text2=positive_l, prepend_text2=prepend_positive_l, width=conditioning_width, height=conditioning_height, crop_width=crop_width, crop_height=crop_height, target_width=target_width, target_height=target_height, refiner_clip=refiner_clip, ascore=positive_ascore)
        negative_embedding, refiner_negative_embedding = await loader.embedding_encodeXL(negative_g, clip, seed=seed, title='pipeLoaderSDXL Negative', my_unique_id=my_unique_id, prepend_text=prepend_negative_g, text2=negative_l, prepend_text2=prepend_negative_l, width=conditioning_width, height=conditioning_height, crop_width=crop_width, crop_height=crop_height, target_width=target_width, target_height=target_height, refiner_clip=refiner_clip, ascore=negative_ascore)
        if optional_controlnet_stack is not None:
            for cnt in optional_controlnet_stack:
                positive_embedding, negative_embedding = await loader.load_controlNet(positive_embedding, negative_embedding, cnt[0], cnt[1], cnt[2], cnt[3], cnt[4])
        image = None
        sdxl_pipe = {'model': model, 'positive': positive_embedding, 'negative': negative_embedding, 'vae': vae, 'clip': clip, 'refiner_model': refiner_model, 'refiner_positive': refiner_positive_embedding, 'refiner_negative': refiner_negative_embedding, 'refiner_clip': refiner_clip, 'samples': samples, 'images': image, 'seed': seed, 'loader_settings': None}
        final_positive = (prepend_positive_g + ' ' if prepend_positive_g else '') + (positive_g + ' ' if positive_g else '') + (prepend_positive_l + ' ' if prepend_positive_l else '') + (positive_l + ' ' if positive_l else '')
        final_negative = (prepend_negative_g + ' ' if prepend_negative_g else '') + (negative_g + ' ' if negative_g else '') + (prepend_negative_l + ' ' if prepend_negative_l else '') + (negative_l + ' ' if negative_l else '')
        return (sdxl_pipe, model, positive_embedding, negative_embedding, vae, clip, refiner_model, refiner_positive_embedding, refiner_negative_embedding, refiner_clip, samples, seed, empty_latent_width, empty_latent_height, final_positive, final_negative)

class ttN_pipeKSamplerSDXL_v2:
    version = '2.3.1'

    def __init__(self):
        pass

    async def sample(self, sdxl_pipe, lora_name, lora_strength, base_steps, refiner_steps, cfg, denoise, refiner_cfg, refiner_denoise, sampler_name, scheduler, image_output, save_prefix, file_type, embed_workflow, optional_model=None, optional_positive=None, optional_negative=None, optional_latent=None, optional_vae=None, optional_clip=None, input_image_override=None, adv_xyPlot=None, seed=None, upscale_model_name=None, upscale_method=None, factor=None, rescale=None, percent=None, width=None, height=None, longer_side=None, crop=None, prompt=None, extra_pnginfo=None, my_unique_id=None, force_full_denoise=False, disable_noise=False, optional_refiner_model=None, optional_refiner_positive=None, optional_refiner_negative=None):
        my_unique_id = int(my_unique_id)
        ttN_save = ttNsave(my_unique_id, prompt, extra_pnginfo)
        sdxl_model = optional_model if optional_model is not None else sdxl_pipe['model']
        sdxl_positive = optional_positive if optional_positive is not None else sdxl_pipe['positive']
        sdxl_negative = optional_negative if optional_negative is not None else sdxl_pipe['negative']
        sdxl_samples = optional_latent if optional_latent is not None else sdxl_pipe['samples']
        sdxl_images = input_image_override if input_image_override is not None else sdxl_pipe['images']
        sdxl_vae = optional_vae if optional_vae is not None else sdxl_pipe['vae']
        sdxl_clip = optional_clip if optional_clip is not None else sdxl_pipe['clip']
        sdxl_refiner_model = optional_refiner_model if optional_refiner_model is not None else sdxl_pipe['refiner_model']
        sdxl_refiner_positive = optional_refiner_positive if optional_refiner_positive is not None else sdxl_pipe['refiner_positive']
        sdxl_refiner_negative = optional_refiner_negative if optional_refiner_negative is not None else sdxl_pipe['refiner_negative']
        sdxl_refiner_clip = sdxl_pipe['refiner_clip']
        if seed in (None, 'undefined'):
            sdxl_seed = sdxl_pipe['seed']
        else:
            sdxl_seed = seed
        del sdxl_pipe

        async def process_sample_state(sdxl_model, sdxl_images, sdxl_clip, sdxl_samples, sdxl_vae, sdxl_seed, sdxl_positive, sdxl_negative, lora_name, lora_model_strength, lora_clip_strength, sdxl_refiner_model, sdxl_refiner_positive, sdxl_refiner_negative, sdxl_refiner_clip, upscale_model_name, upscale_method, factor, rescale, percent, width, height, longer_side, crop, base_steps, refiner_steps, cfg, sampler_name, scheduler, denoise, refiner_denoise, image_output, save_prefix, file_type, embed_workflow, prompt, my_unique_id, preview_latent, force_full_denoise=force_full_denoise, disable_noise=disable_noise):
            if lora_name not in (None, 'None'):
                sdxl_model, sdxl_clip = await loader.load_lora(lora_name, sdxl_model, sdxl_clip, lora_model_strength, lora_clip_strength)
            total_steps = base_steps + refiner_steps
            if upscale_method != 'None':
                sdxl_samples = await sampler.handle_upscale(sdxl_samples, upscale_method, factor, crop, upscale_model_name, sdxl_vae, sdxl_images, rescale, percent, width, height, longer_side)
            if refiner_steps > 0 and sdxl_refiner_model not in [None, 'None']:
                sdxl_samples = await sampler.common_ksampler(sdxl_model, sdxl_seed, total_steps, cfg, sampler_name, scheduler, sdxl_positive, sdxl_negative, sdxl_samples, denoise=denoise, preview_latent=preview_latent, start_step=0, last_step=base_steps, force_full_denoise=force_full_denoise, disable_noise=disable_noise)
                sdxl_samples = await sampler.common_ksampler(sdxl_refiner_model, sdxl_seed, total_steps, refiner_cfg, sampler_name, scheduler, sdxl_refiner_positive, sdxl_refiner_negative, sdxl_samples, denoise=refiner_denoise, preview_latent=preview_latent, start_step=base_steps, last_step=10000, force_full_denoise=True, disable_noise=True)
            else:
                sdxl_samples = await sampler.common_ksampler(sdxl_model, sdxl_seed, base_steps, cfg, sampler_name, scheduler, sdxl_positive, sdxl_negative, sdxl_samples, denoise=denoise, preview_latent=preview_latent, start_step=0, last_step=base_steps, force_full_denoise=True, disable_noise=disable_noise)
            results = list()
            if image_output != 'Disabled':
                latent = sdxl_samples['samples']
                sdxl_images = await vae_decode(sdxl_vae, latent)
                results = await ttN_save.images(sdxl_images, save_prefix, image_output, embed_workflow, file_type)
            new_sdxl_pipe = {'model': sdxl_model, 'positive': sdxl_positive, 'negative': sdxl_negative, 'vae': sdxl_vae, 'clip': sdxl_clip, 'refiner_model': sdxl_refiner_model, 'refiner_positive': sdxl_refiner_positive, 'refiner_negative': sdxl_refiner_negative, 'refiner_clip': sdxl_refiner_clip, 'samples': sdxl_samples, 'images': sdxl_images, 'seed': sdxl_seed, 'loader_settings': None}
            pipe = {'model': sdxl_model, 'positive': sdxl_positive, 'negative': sdxl_negative, 'vae': sdxl_vae, 'clip': sdxl_clip, 'samples': sdxl_samples, 'images': sdxl_images, 'seed': sdxl_seed, 'loader_settings': None}
            if image_output in ('Hide', 'Hide/Save', 'Disabled'):
                return (*sampler.get_output_sdxl(new_sdxl_pipe, pipe), None)
            return {'ui': {'images': results}, 'result': (*sampler.get_output_sdxl(new_sdxl_pipe, pipe), None)}

        async def process_xyPlot(sdxl_model, sdxl_clip, sdxl_samples, sdxl_vae, sdxl_seed, sdxl_positive, sdxl_negative, lora_name, lora_model_strength, lora_clip_strength, base_steps, refiner_steps, cfg, sampler_name, scheduler, denoise, image_output, save_prefix, file_type, embed_workflow, prompt, extra_pnginfo, my_unique_id, preview_latent, adv_xyPlot):
            raise RuntimeError('Embedded XY plotting through this sampler is unavailable in the current secure profile. Disconnect adv_xyPlot for ordinary sampling, or use the separate advanced branch plot within its supported scope.')
        preview_latent = True
        if image_output in ('Hide', 'Hide/Save', 'Disabled'):
            preview_latent = False
        if adv_xyPlot is None:
            return await process_sample_state(sdxl_model, sdxl_images, sdxl_clip, sdxl_samples, sdxl_vae, sdxl_seed, sdxl_positive, sdxl_negative, lora_name, lora_strength, lora_strength, sdxl_refiner_model, sdxl_refiner_positive, sdxl_refiner_negative, sdxl_refiner_clip, upscale_model_name, upscale_method, factor, rescale, percent, width, height, longer_side, crop, base_steps, refiner_steps, cfg, sampler_name, scheduler, denoise, refiner_denoise, image_output, save_prefix, file_type, embed_workflow, prompt, my_unique_id, preview_latent)
        else:
            return await process_xyPlot(sdxl_model, sdxl_clip, sdxl_samples, sdxl_vae, sdxl_seed, sdxl_positive, sdxl_negative, lora_name, lora_strength, lora_strength, base_steps, refiner_steps, cfg, sampler_name, scheduler, denoise, image_output, save_prefix, file_type, embed_workflow, prompt, extra_pnginfo, my_unique_id, preview_latent, adv_xyPlot)

class ttN_pipe_EDIT:
    version = '1.1.1'

    def __init__(self):
        pass

    def flush(self, pipe=None, model=None, pos=None, neg=None, latent=None, vae=None, clip=None, image=None, seed=None, my_unique_id=None):
        model = model or pipe.get('model')
        if model is None:
            ttNl('Model missing from pipeLine').t(f'pipeEdit[{my_unique_id}]').warn().p()
        pos = pos or pipe.get('positive')
        if pos is None:
            ttNl('Positive conditioning missing from pipeLine').t(f'pipeEdit[{my_unique_id}]').warn().p()
        neg = neg or pipe.get('negative')
        if neg is None:
            ttNl('Negative conditioning missing from pipeLine').t(f'pipeEdit[{my_unique_id}]').warn().p()
        samples = latent or pipe.get('samples')
        if samples is None:
            ttNl('Latent missing from pipeLine').t(f'pipeEdit[{my_unique_id}]').warn().p()
        vae = vae or pipe.get('vae')
        if vae is None:
            ttNl('VAE missing from pipeLine').t(f'pipeEdit[{my_unique_id}]').warn().p()
        clip = clip or pipe.get('clip')
        if clip is None:
            ttNl('Clip missing from pipeLine').t(f'pipeEdit[{my_unique_id}]').warn().p()
        image = image or pipe.get('images')
        if image is None:
            ttNl('Image missing from pipeLine').t(f'pipeEdit[{my_unique_id}]').warn().p()
        seed = seed or pipe.get('seed')
        if seed is None:
            ttNl('Seed missing from pipeLine').t(f'pipeEdit[{my_unique_id}]').warn().p()
        new_pipe = {'model': model, 'positive': pos, 'negative': neg, 'vae': vae, 'clip': clip, 'samples': samples, 'images': image, 'seed': seed, 'loader_settings': pipe['loader_settings']}
        del pipe
        return (new_pipe, model, pos, neg, latent, vae, clip, image, seed)

class ttN_pipe_2BASIC:
    version = '1.1.0'

    def __init__(self):
        pass

    def flush(self, pipe):
        basic_pipe = (pipe.get('model'), pipe.get('clip'), pipe.get('vae'), pipe.get('positive'), pipe.get('negative'))
        return (basic_pipe, pipe)

class ttN_pipe_2DETAILER:
    version = '1.2.0'

    def flush(self, pipe, bbox_detector, wildcard, sam_model_opt=None, segm_detector_opt=None, detailer_hook=None):
        detailer_pipe = (pipe.get('model'), pipe.get('clip'), pipe.get('vae'), pipe.get('positive'), pipe.get('negative'), wildcard, bbox_detector, segm_detector_opt, sam_model_opt, detailer_hook, None, None, None, None)
        return (detailer_pipe, pipe)

class ttN_pipeEncodeConcat:
    version = '1.0.2'

    async def concat(self, toggle, positive_token_normalization, positive_weight_interpretation, negative_token_normalization, negative_weight_interpretation, pipe=None, positive='', negative='', seed=None, my_unique_id=None, optional_positive_from=None, optional_negative_from=None, optional_clip=None):
        if toggle == False:
            return (pipe, pipe['positive'], pipe['negative'], pipe['clip'])
        positive_from = optional_positive_from if optional_positive_from is not None else pipe['positive']
        negative_from = optional_negative_from if optional_negative_from is not None else pipe['negative']
        samp_clip = optional_clip if optional_clip is not None else pipe['clip']
        new_text = ''

        async def enConcatConditioning(text, token_normalization, weight_interpretation, conditioning_from, new_text):
            out = []
            if '__' in text:
                text = await loader.nsp_parse(text, pipe['seed'], title='encodeConcat', my_unique_id=my_unique_id)
                new_text += text
            conditioning_to, pooled = await advanced_encode(samp_clip, text, token_normalization, weight_interpretation, w_max=1.0, apply_to_pooled='enable')
            conditioning_to = [[conditioning_to, {'pooled_output': pooled}]]
            if len(conditioning_from) > 1:
                ttNl('encode and concat conditioning_from contains more than 1 cond, only the first one will actually be applied to conditioning_to').t(f'pipeEncodeConcat[{my_unique_id}]').warn().p()
            cond_from = conditioning_from[0][0]
            for i in range(len(conditioning_to)):
                t1 = conditioning_to[i][0]
                tw = torch.cat((t1, cond_from), 1)
                n = [tw, conditioning_to[i][1].copy()]
                out.append(n)
            return out
        pos, neg = (None, None)
        if positive not in ['', None, ' ']:
            pos = await enConcatConditioning(positive, positive_token_normalization, positive_weight_interpretation, positive_from, new_text)
        if negative not in ['', None, ' ']:
            neg = await enConcatConditioning(negative, negative_token_normalization, negative_weight_interpretation, negative_from, new_text)
        pos = pos if pos is not None else pipe['positive']
        neg = neg if neg is not None else pipe['negative']
        new_pipe = {'model': pipe['model'], 'positive': pos, 'negative': neg, 'vae': pipe['vae'], 'clip': samp_clip, 'samples': pipe['samples'], 'images': pipe['images'], 'seed': pipe['seed'], 'loader_settings': pipe['loader_settings']}
        del pipe
        return (new_pipe, new_pipe['positive'], new_pipe['negative'], samp_clip, {'ui': {'string': new_text}})

class ttN_pipeLoraStack:
    version = '1.1.1'

    def __init__(self):
        pass

    async def stack(self, toggle, mode, num_loras, optional_pipe=None, lora_stack=None, model_override=None, clip_override=None, **kwargs):
        if toggle in [False, None, 'False'] or not kwargs:
            return (optional_pipe, None)
        loras = []
        if lora_stack is not None:
            loras.extend([l for l in lora_stack if l[0] != 'None'])
        for i in range(1, num_loras + 1):
            lora_name = kwargs.get(f'lora_{i}_name')
            if not lora_name or lora_name == 'None':
                continue
            if mode == 'simple':
                lora_strength = float(kwargs.get(f'lora_{i}_strength'))
                loras.append((lora_name, lora_strength, lora_strength))
            elif mode == 'advanced':
                model_strength = float(kwargs.get(f'lora_{i}_model_strength'))
                clip_strength = float(kwargs.get(f'lora_{i}_clip_strength'))
                loras.append((lora_name, model_strength, clip_strength))
        if not loras:
            return (optional_pipe, None)
        if loras and (not optional_pipe):
            return (optional_pipe, loras)
        model = model_override or optional_pipe.get('model')
        clip = clip_override or optional_pipe.get('clip')
        if not model or not clip:
            return (optional_pipe, loras)
        for lora in loras:
            model, clip = await loader.load_lora(lora[0], model, clip, lora[1], lora[2])
        new_pipe = {'model': model, 'positive': optional_pipe['positive'], 'negative': optional_pipe['negative'], 'vae': optional_pipe['vae'], 'clip': clip, 'samples': optional_pipe['samples'], 'images': optional_pipe['images'], 'seed': optional_pipe['seed'], 'loader_settings': optional_pipe['loader_settings']}
        del optional_pipe
        return (new_pipe, loras)

class ttN_conditioning:
    version = '1.0.2'

    async def condition(self, model, clip, loras, positive, positive_token_normalization, positive_weight_interpretation, negative, negative_token_normalization, negative_weight_interpretation, zero_out_empty, optional_lora_stack=None, prepend_positive=None, prepend_negative=None, my_unique_id=None):
        if optional_lora_stack is not None:
            for lora in optional_lora_stack:
                model, clip = await loader.load_lora(lora[0], model, clip, lora[1], lora[2])
        if loras not in [None, 'None']:
            model, clip = await loader.load_lora_text(loras, model, clip)
        positive_embedding = await loader.embedding_encode(positive, positive_token_normalization, positive_weight_interpretation, clip, title='ttN Conditioning Positive', my_unique_id=my_unique_id, prepend_text=prepend_positive, zero_out=zero_out_empty)
        negative_embedding = await loader.embedding_encode(negative, negative_token_normalization, negative_weight_interpretation, clip, title='ttN Conditioning Negative', my_unique_id=my_unique_id, prepend_text=prepend_negative, zero_out=zero_out_empty)
        final_positive = (prepend_positive + ' ' if prepend_positive else '') + (positive if positive else '')
        final_negative = (prepend_negative + ' ' if prepend_negative else '') + (negative if negative else '')
        return (model, positive_embedding, negative_embedding, clip, final_positive, final_negative)

class ttN_KSampler_v2:
    version = '2.3.1'

    def __init__(self):
        pass

    async def sample(self, model, positive, negative, latent, vae, lora_name, lora_strength, steps, cfg, sampler_name, scheduler, image_output, save_prefix, file_type, embed_workflow, denoise=1.0, input_image_override=None, clip=None, seed=None, adv_xyPlot=None, upscale_model_name=None, upscale_method=None, factor=None, rescale=None, percent=None, width=None, height=None, longer_side=None, crop=None, prompt=None, extra_pnginfo=None, my_unique_id=None, start_step=None, last_step=None, force_full_denoise=False, disable_noise=False):
        my_unique_id = int(my_unique_id)
        ttN_save = ttNsave(my_unique_id, prompt, extra_pnginfo)

        async def process_sample_state(model, images, clip, samples, vae, seed, positive, negative, lora_name, lora_model_strength, lora_clip_strength, upscale_model_name, upscale_method, factor, rescale, percent, width, height, longer_side, crop, steps, cfg, sampler_name, scheduler, denoise, image_output, save_prefix, file_type, embed_workflow, prompt, extra_pnginfo, my_unique_id, preview_latent, start_step=start_step, last_step=last_step, force_full_denoise=force_full_denoise, disable_noise=disable_noise):
            if lora_name not in (None, 'None'):
                if clip == None:
                    raise ValueError(f'tinyKSampler [{my_unique_id}] - Lora requires CLIP model')
                model, clip = await loader.load_lora(lora_name, model, clip, lora_model_strength, lora_clip_strength)
            if upscale_method != 'None':
                samples = await sampler.handle_upscale(samples, upscale_method, factor, crop, upscale_model_name, vae, images, rescale, percent, width, height, longer_side)
            samples = await sampler.common_ksampler(model, seed, steps, cfg, sampler_name, scheduler, positive, negative, samples, denoise=denoise, preview_latent=preview_latent, start_step=start_step, last_step=last_step, force_full_denoise=force_full_denoise, disable_noise=disable_noise)
            results = list()
            if image_output != 'Disabled':
                latent = samples['samples']
                images = await vae_decode(vae, latent)
                results = await ttN_save.images(images, save_prefix, image_output, embed_workflow, file_type)
            if image_output in ('Hide', 'Hide/Save', 'Disabled'):
                return (model, positive, negative, samples, vae, clip, images, seed, None)
            return {'ui': {'images': results}, 'result': (model, positive, negative, samples, vae, clip, images, seed, None)}

        async def process_xyPlot(model, clip, samp_samples, vae, seed, positive, negative, lora_name, lora_model_strength, lora_clip_strength, steps, cfg, sampler_name, scheduler, denoise, image_output, save_prefix, file_type, embed_workflow, prompt, extra_pnginfo, my_unique_id, preview_latent, adv_xyPlot):
            raise RuntimeError('Embedded XY plotting through this sampler is unavailable in the current secure profile. Disconnect adv_xyPlot for ordinary sampling, or use the separate advanced branch plot within its supported scope.')
        preview_latent = True
        if image_output in ('Hide', 'Hide/Save', 'Disabled'):
            preview_latent = False
        if adv_xyPlot is None:
            return await process_sample_state(model, input_image_override, clip, latent, vae, seed, positive, negative, lora_name, lora_strength, lora_strength, upscale_model_name, upscale_method, factor, rescale, percent, width, height, longer_side, crop, steps, cfg, sampler_name, scheduler, denoise, image_output, save_prefix, file_type, embed_workflow, prompt, extra_pnginfo, my_unique_id, preview_latent)
        else:
            return await process_xyPlot(model, clip, latent, vae, seed, positive, negative, lora_name, lora_strength, lora_strength, steps, cfg, sampler_name, scheduler, denoise, image_output, save_prefix, file_type, embed_workflow, prompt, extra_pnginfo, my_unique_id, preview_latent, adv_xyPlot)

class ttN_advanced_XYPlot:
    version = '1.2.1'
    plotPlaceholder = "_PLOT\nExample:\n\n<axis number:label1>\n[node_ID:widget_Name='value']\n\n<axis number2:label2>\n[node_ID:widget_Name='value2']\n[node_ID:widget2_Name='value']\n[node_ID2:widget_Name='value']\n\netc..."

    def get_plot_points(plot_data, unique_id, plot_Line):
        if plot_data is None or plot_data.strip() == '':
            return None
        else:
            try:
                axis_dict = {}
                lines = plot_data.split('<')
                new_lines = []
                temp_line = ''
                for line in lines:
                    if line.startswith('lora'):
                        temp_line += '<' + line
                        new_lines[-1] = temp_line
                    else:
                        new_lines.append(line)
                        temp_line = line
                for line in new_lines:
                    if line:
                        values_label = []
                        line = line.split('>', 1)
                        num, label = line[0].split(':', 1)
                        axis_dict[num] = {'label': label}
                        for point in line[1].split("']"):
                            if point.strip() == '':
                                continue
                            node_id = point.split(':', 1)[0].split('[')[1]
                            axis_dict[num].setdefault(node_id, {})
                            input_name = point.split(':', 1)[1].split('=', 1)[0]
                            value = point.split("'", 1)[1]
                            values_label.append((value, input_name, node_id))
                            axis_dict[num][node_id][input_name] = value
                        if label in ['v_label', 'tv_label', 'idtv_label']:
                            new_label = []
                            for value, input_name, node_id in values_label:
                                if label == 'v_label':
                                    new_label.append(value)
                                elif label == 'tv_label':
                                    new_label.append(f'{input_name}: {value}')
                                elif label == 'idtv_label':
                                    new_label.append(f'[{node_id}] {input_name}: {value}')
                            axis_dict[num]['label'] = ', '.join(new_label)
            except ValueError:
                ttNl('Invalid Plot - defaulting to None...').t(f'advanced_XYPlot[{unique_id}] {plot_Line} Axis').warn().p()
                return None
            return axis_dict

    def __init__(self):
        pass

    def plot(self, grid_spacing, save_individuals, flip_xy, x_plot=None, y_plot=None, z_plot=None, my_unique_id=None, invert_background=False):
        x_plot = ttN_advanced_XYPlot.get_plot_points(x_plot, my_unique_id, 'X')
        y_plot = ttN_advanced_XYPlot.get_plot_points(y_plot, my_unique_id, 'Y')
        z_plot = ttN_advanced_XYPlot.get_plot_points(z_plot, my_unique_id, 'Z')
        if x_plot == {}:
            x_plot = None
        if y_plot == {}:
            y_plot = None
        if flip_xy == True:
            x_plot, y_plot = (y_plot, x_plot)
        xy_plot = {'x_plot': x_plot, 'y_plot': y_plot, 'z_plot': z_plot, 'grid_spacing': grid_spacing, 'save_individuals': save_individuals, 'invert_bg': invert_background}
        return (xy_plot,)

class ttN_advPlot_range:
    version = '1.1.0'

    def __init__(self):
        pass

    def plot(self, node, widget, range_mode, start, step, stop, include_stop, num_steps, label_type):
        if '[' in node and ']' in node:
            nodeid = node.split('[', 1)[1].split(']', 1)[0]
        else:
            return {'ui': {'text': ''}, 'result': ('',)}
        label_map = {'Values': 'v_label', 'Title and Values': 'tv_label', 'ID, Title and Values': 'idtv_label'}
        label = label_map[label_type]
        plot_text = []
        vals = []
        if range_mode.startswith('step_'):
            for num in range(1, num_steps + 1):
                vals.append(start + step * (num - 1))
        if range_mode.startswith('num_steps'):
            vals = np.linspace(start, stop, num_steps, endpoint=include_stop).tolist()
        for i, val in enumerate(vals):
            if range_mode.endswith('int'):
                val = int(round(val, 0))
            else:
                val = round(val, 2)
            line = f"[{nodeid}:{widget}='{val}']"
            plot_text.append(f'<{i + 1}:{label}>')
            plot_text.append(line)
        out = '\n'.join(plot_text)
        return {'ui': {'text': out}, 'result': (out,)}

class ttN_advPlot_string:
    version = '1.1.0'

    def __init__(self):
        pass

    def plot(self, node, widget, replace_mode, search_string, text, delimiter, label_type):
        if '[' in node and ']' in node:
            nodeid = node.split('[', 1)[1].split(']', 1)[0]
        else:
            return {'ui': {'text': ''}, 'result': ('',)}
        label_map = {'Values': 'v_label', 'Title and Values': 'tv_label', 'ID, Title and Values': 'idtv_label'}
        label = label_map[label_type]
        plot_text = []
        delimiter = delimiter.replace('\\n', '\n')
        vals = text.split(delimiter)
        for i, val in enumerate(vals):
            if val.strip() == '':
                continue
            if replace_mode:
                line = f"[{nodeid}:{widget}='%{search_string};{val}%']"
            else:
                line = f"[{nodeid}:{widget}='{val}']"
            plot_text.append(f'<{i + 1}:{label}>')
            plot_text.append(line)
        out = '\n'.join(plot_text)
        return {'ui': {'text': out}, 'result': (out,)}

class ttN_advPlot_merge:
    version = '1.0.0'

    def __init__(self):
        pass

    def plot(self, label_type, plot_text1='', plot_text2=''):
        label_map = {'Values': 'v_label', 'Title and Values': 'tv_label', 'ID, Title and Values': 'idtv_label'}
        label = label_map.get(label_type, 'v_label')
        text1 = plot_text1.split('<') if plot_text1 else []
        text2 = plot_text2.split('<') if plot_text2 else []
        number_of_lines = max(len(text1) - 1, len(text2) - 1, 0)
        if number_of_lines == 0:
            return ''
        lines = []
        for num in range(1, number_of_lines + 1):
            lines.append(f'<{num}:{label}>\n')
            for text in (text1, text2):
                if num < len(text):
                    parts = text[num].split('>\n', 1)
                    if len(parts) == 2:
                        lines.append(parts[1])
                        if not parts[1].endswith('\n'):
                            lines.append('\n')
        out = ''.join(lines)
        return {'ui': {'text': out}, 'result': (out,)}

class ttN_text:
    version = '1.0.0'

    def __init__(self):
        pass

    @staticmethod
    def conmeow(text):
        return (text,)

class ttN_concat:
    version = '1.0.0'

    def __init__(self):
        pass
    '\n    Concatenate 2 strings\n    '

    def conmeow(self, text1='', text2='', text3='', delimiter=''):
        text1 = '' if text1 == 'undefined' else text1
        text2 = '' if text2 == 'undefined' else text2
        text3 = '' if text3 == 'undefined' else text3
        if delimiter == '\\n':
            delimiter = '\n'
        concat = delimiter.join([text1, text2, text3])
        return (concat,)

class ttN_text3BOX_3WAYconcat:
    version = '1.0.0'

    def __init__(self):
        pass
    '\n    Concatenate 3 strings, in various ways.\n    '

    def conmeow(self, text1='', text2='', text3='', delimiter=''):
        text1 = '' if text1 == 'undefined' else text1
        text2 = '' if text2 == 'undefined' else text2
        text3 = '' if text3 == 'undefined' else text3
        if delimiter == '\\n':
            delimiter = '\n'
        t_1n2 = delimiter.join([text1, text2])
        t_1n3 = delimiter.join([text1, text3])
        t_2n3 = delimiter.join([text2, text3])
        concat = delimiter.join([text1, text2, text3])
        return (text1, text2, text3, t_1n2, t_1n3, t_2n3, concat)

class ttN_text7BOX_concat:
    version = '1.0.0'

    def __init__(self):
        pass
    '\n    Concatenate many strings\n    '

    def conmeow(self, text1, text2, text3, text4, text5, text6, text7, delimiter):
        text1 = '' if text1 == 'undefined' else text1
        text2 = '' if text2 == 'undefined' else text2
        text3 = '' if text3 == 'undefined' else text3
        text4 = '' if text4 == 'undefined' else text4
        text5 = '' if text5 == 'undefined' else text5
        text6 = '' if text6 == 'undefined' else text6
        text7 = '' if text7 == 'undefined' else text7
        if delimiter == '\\n':
            delimiter = '\n'
        texts = [text1, text2, text3, text4, text5, text6, text7]
        concat = delimiter.join((text for text in texts if text))
        return (text1, text2, text3, text4, text5, text6, text7, concat)

class ttN_textCycleLine:
    version = '1.0.0'

    def __init__(self):
        pass

    def cycle(self, text, index, index_control='randomized'):
        lines = text.split('\n')
        if index >= len(lines):
            index = len(lines) - 1
        return (lines[index],)

class ttN_textOUPUT:
    version = '1.0.1'

    def __init__(self):
        pass

    async def output(self, text_output, text, output_path, save_prefix, number_padding, file_type, overwrite_existing, prompt, extra_pnginfo, my_unique_id):
        if text_output == 'Save':
            ttN_save = ttNsave(my_unique_id, prompt, extra_pnginfo, number_padding, overwrite_existing, output_path)
            await ttN_save.textfile(text, save_prefix, file_type)
        return {'ui': {'text': text}, 'result': (text,)}

class ttN_INT:
    version = '1.0.0'

    def __init__(self):
        pass

    @staticmethod
    def convert(int):
        return (int, float(int), str(int))

class ttN_FLOAT:
    version = '1.0.0'

    def __init__(self):
        pass

    @staticmethod
    def convert(float):
        return (float, int(float), str(float))

class ttN_SEED:
    version = '1.0.0'

    def __init__(self):
        pass

    @staticmethod
    def plant(seed):
        return (seed,)

class ttN_imageOUPUT:
    version = '1.2.0'

    def __init__(self):
        pass

    async def output(self, image, image_output, output_path, save_prefix, number_padding, file_type, overwrite_existing, embed_workflow, prompt, extra_pnginfo, my_unique_id):
        ttN_save = ttNsave(my_unique_id, prompt, extra_pnginfo, number_padding, overwrite_existing, output_path)
        results = await ttN_save.images(image, save_prefix, image_output, embed_workflow, file_type)
        if image_output in ('Hide', 'Hide/Save'):
            return (image,)
        return {'ui': {'images': results}, 'result': (image,)}
