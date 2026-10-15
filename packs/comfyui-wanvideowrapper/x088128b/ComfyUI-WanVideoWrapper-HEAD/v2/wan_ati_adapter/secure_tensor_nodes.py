"""Static pack-owned Wan settings/parser nodes; full pack remains pending."""
from comfy_api.latest import io

MAX_TEXT_BYTES = 65536
MAX_BLOCK_ENTRIES = 10001

def _bound_strings(values):
    for value in values:
        if isinstance(value, str) and len(value.encode('utf-8', errors='surrogatepass')) > MAX_TEXT_BYTES:
            raise ValueError('Wan configuration text exceeds 64 KiB')

import logging
import torch
import torch.nn.functional as F
import numpy as np
import math
log = logging.getLogger(__name__)
MAX_TENSOR_ELEMENTS = 16777216
MAX_CONTAINER_ITEMS = 4096
MAX_PAYLOAD_BYTES = 67108864
MAX_PAYLOAD_VISITS = 8192
VAE_STRIDE = (4, 8, 8)

def _bound_payload(value, depth=0, budget=None):
    if budget is None:
        budget = [0, 0]
    budget[0] += 1
    if budget[0] > MAX_PAYLOAD_VISITS:
        raise ValueError('Wan structured input exceeds 8192 visited values')
    if depth > 16:
        raise ValueError('Wan structured input depth exceeds 16')
    if isinstance(value, torch.Tensor):
        if value.numel() > MAX_TENSOR_ELEMENTS:
            raise ValueError('Wan tensor input exceeds 16777216 elements')
        budget[1] += value.numel() * value.element_size()
    elif isinstance(value, np.ndarray):
        if value.dtype.kind not in 'bifu':
            raise TypeError('Wan NumPy inputs must have non-object numeric dtype')
        if value.size > MAX_TENSOR_ELEMENTS:
            raise ValueError('Wan array input exceeds 16777216 elements')
        budget[1] += value.nbytes
    elif isinstance(value, dict):
        if len(value) > MAX_CONTAINER_ITEMS:
            raise ValueError('Wan structured input exceeds 4096 items')
        for item in value.values():
            _bound_payload(item, depth + 1, budget)
    elif isinstance(value, (list, tuple)):
        if len(value) > MAX_CONTAINER_ITEMS:
            raise ValueError('Wan structured input exceeds 4096 items')
        for item in value:
            _bound_payload(item, depth + 1, budget)
    elif isinstance(value, str):
        _bound_strings([value])
        budget[1] += len(value.encode('utf-8', errors='surrogatepass'))
    if budget[1] > MAX_PAYLOAD_BYTES:
        raise ValueError('Wan structured input exceeds 64 MiB of tensor/text data')

def _preflight_unilumos(num_frames, width, height, foreground_latents, background_latents):
    shape = (16, (num_frames - 1) // 4 + 1, height // 8, width // 8)
    if all(isinstance(value, int) and value >= 0 for value in shape):
        elements = math.prod(shape)
        missing = int(foreground_latents is None) + int(background_latents is None)
        if missing and (elements > MAX_TENSOR_ELEMENTS or elements * 4 * missing > MAX_PAYLOAD_BYTES):
            raise ValueError('Wan UniLumos projected output exceeds tensor/64 MiB bounds')

def _preflight_phantom(values):
    tensors = [value.get('samples') for value in values if isinstance(value, dict)]
    if tensors and all(isinstance(value, torch.Tensor) and value.ndim == 5
            and value.shape[0] == 1 for value in tensors):
        elements = sum(value.numel() for value in tensors)
        bytes_total = sum(value.numel() * value.element_size() for value in tensors)
        if elements > MAX_TENSOR_ELEMENTS or bytes_total > MAX_PAYLOAD_BYTES:
            raise ValueError('Wan Phantom projected output exceeds tensor/64 MiB bounds')

def _preflight_ovi_empty(length):
    if isinstance(length, int):
        elements = max(0, length) * 20
        if elements > MAX_TENSOR_ELEMENTS or elements * 4 > MAX_PAYLOAD_BYTES:
            raise ValueError('Wan Ovi projected output exceeds tensor/64 MiB bounds')

def _preflight_onetoall_pose(pose_images, pose_prefix_image):
    tensors=[value for value in (pose_images,pose_prefix_image) if isinstance(value,torch.Tensor)]
    if tensors:
        elements=sum(value.numel() for value in tensors)
        bytes_total=sum(value.numel()*value.element_size() for value in tensors)
        if elements>MAX_TENSOR_ELEMENTS or 2*bytes_total>MAX_PAYLOAD_BYTES:
            raise ValueError('Wan OneToAll projected pose/prefix exceeds tensor/64 MiB bounds')

def _preflight_onetoall_extend(pose_images, window_size, overlap, frames_processed, policy):
    if isinstance(pose_images,torch.Tensor) and pose_images.ndim==4 and all(isinstance(v,int) for v in (window_size,overlap,frames_processed)):
        count,height,width,channels=pose_images.shape
        start=max(0,frames_processed-overlap)
        end=start+window_size
        if start<count and end>count and policy=='pad_with_last':
            elements=end*height*width*min(channels,3)
            # Full clone, repeated tail, concat and view share bounded lifetime.
            bytes_total=(pose_images.numel()+2*elements)*pose_images.element_size()
            if elements>MAX_TENSOR_ELEMENTS or bytes_total>MAX_PAYLOAD_BYTES:
                raise ValueError('Wan OneToAll projected continuation padding exceeds tensor/64 MiB bounds')

def _preflight_realis(smpl_latent, hamer_latent):
    tensors = [value.get('samples') for value in (smpl_latent, hamer_latent) if isinstance(value, dict)]
    if tensors and all(isinstance(value, torch.Tensor) for value in tensors):
        elements = sum(value.numel() for value in tensors) * (2 if len(tensors) == 1 else 1)
        dtype = tensors[0].dtype
        for tensor in tensors[1:]:
            dtype = torch.promote_types(dtype, tensor.dtype)
        size = dtype.itemsize
        if elements > MAX_TENSOR_ELEMENTS or elements * size > MAX_PAYLOAD_BYTES:
            raise ValueError('Wan RealisDance projected output exceeds tensor/64 MiB bounds')

def _preflight_svi(anchor_samples, num_frames, prev_samples, motion_latent_count):
    tensor = anchor_samples.get('samples') if isinstance(anchor_samples, dict) else None
    if isinstance(tensor, torch.Tensor) and tensor.ndim == 5 and isinstance(num_frames, int):
        _, channels, _, height, width = tensor.shape
        y_elements = channels * max(0, (num_frames - 1) // 4 + 1) * height * width
        mask_elements = max(0, num_frames + 3) * height * width
        prev_tensor = prev_samples.get('samples') if isinstance(prev_samples, dict) else None
        dtype = torch.promote_types(tensor.dtype, prev_tensor.dtype) if isinstance(prev_tensor, torch.Tensor) and motion_latent_count != 0 else tensor.dtype
        if (max(y_elements, mask_elements) > MAX_TENSOR_ELEMENTS
                or y_elements * dtype.itemsize + mask_elements * tensor.element_size() > MAX_PAYLOAD_BYTES):
            raise ValueError('Wan SVI projected output exceeds tensor/64 MiB bounds')

def _preflight_s2v(embeds, audio_encoder_output, frame_window_size):
    layers = audio_encoder_output.get('encoded_audio_all_layers') if isinstance(audio_encoder_output, dict) else None
    if (isinstance(layers, (list, tuple)) and layers
            and all(isinstance(value, torch.Tensor) and value.shape == layers[0].shape for value in layers)):
        dtype = layers[0].dtype
        for tensor in layers[1:]:
            dtype = torch.promote_types(dtype, tensor.dtype)
        stacked_elements = len(layers) * layers[0].numel()
        if stacked_elements > MAX_TENSOR_ELEMENTS or stacked_elements * dtype.itemsize > MAX_PAYLOAD_BYTES:
            raise ValueError('Wan S2V projected stack exceeds tensor/64 MiB bounds')
    if (isinstance(layers, (list, tuple)) and layers
            and all(isinstance(value, torch.Tensor) and (value.ndim == 2 and value.shape[0] != 1
                    or value.ndim == 3 and value.shape[0] == 1)
                and value.shape == layers[0].shape for value in layers)
            and isinstance(embeds, dict) and isinstance(embeds.get('num_frames'), int)
            and embeds['num_frames'] >= 0 and isinstance(frame_window_size, int) and frame_window_size > 0):
        frames = min(int(layers[0].shape[-2] / 50 * 30), embeds['num_frames'] * 30 // 16)
        repeats = int(frames / (frame_window_size * (30 / 16))) + 1
        buckets = repeats * frame_window_size
        elements = buckets * len(layers) * layers[0].shape[-1]
        dtype = layers[0].dtype
        for tensor in layers[1:]:
            dtype = torch.promote_types(dtype, tensor.dtype)
        # Source creates an intermediate per-frame Python list and final cat;
        # bound that work as well as the projected tensor before either occurs.
        if buckets > 10001 or elements > MAX_TENSOR_ELEMENTS or elements * dtype.itemsize > MAX_PAYLOAD_BYTES:
            raise ValueError('Wan S2V projected output exceeds bucket/tensor/64 MiB bounds')

def _s2v_sample_indices(original_fps, total_frames, target_fps, num_sample, fixed_start=None):
    required_duration = num_sample / target_fps
    required_origin_frames = int(np.ceil(required_duration * original_fps))
    if required_duration > total_frames / original_fps:
        raise ValueError('required_duration must be less than video length')
    if not fixed_start is None and fixed_start >= 0:
        start_frame = fixed_start
    else:
        max_start = total_frames - required_origin_frames
        if max_start < 0:
            raise ValueError('video length is too short')
        start_frame = np.random.randint(0, max_start + 1)
    start_time = start_frame / original_fps
    end_time = start_time + required_duration
    time_points = np.linspace(start_time, end_time, num_sample, endpoint=False)
    frame_indices = np.round(np.array(time_points) * original_fps).astype(int)
    frame_indices = np.clip(frame_indices, 0, total_frames - 1)
    return frame_indices
def _s2v_interpolate(features, input_fps, output_fps, output_len=None):
    """
    features: shape=[1, T, 512]
    input_fps: fps for audio, f_a
    output_fps: fps for video, f_m
    output_len: video length
    """
    features = features.transpose(1, 2)
    seq_len = features.shape[2] / float(input_fps)
    if output_len is None:
        output_len = int(seq_len * output_fps)
    output_features = F.interpolate(features, size=output_len, align_corners=True, mode='linear')
    return output_features.transpose(1, 2)
def _s2v_audio_bucket(audio_embed, fps=16, batch_frames=81, m=0):
    num_layers, audio_frame_num, audio_dim = audio_embed.shape
    if num_layers > 1:
        return_all_layers = True
    else:
        return_all_layers = False
    scale = 30 / fps
    min_batch_num = int(audio_frame_num / (batch_frames * scale)) + 1
    bucket_num = min_batch_num * batch_frames
    padd_audio_num = math.ceil(min_batch_num * batch_frames / fps * 30) - audio_frame_num
    batch_idx = _s2v_sample_indices(original_fps=30, total_frames=audio_frame_num + padd_audio_num, target_fps=fps, num_sample=bucket_num, fixed_start=0)
    batch_audio_eb = []
    audio_sample_stride = int(30 / fps)
    for bi in batch_idx:
        if bi < audio_frame_num:
            chosen_idx = list(range(bi - m * audio_sample_stride, bi + (m + 1) * audio_sample_stride, audio_sample_stride))
            chosen_idx = [0 if c < 0 else c for c in chosen_idx]
            chosen_idx = [audio_frame_num - 1 if c >= audio_frame_num else c for c in chosen_idx]
            if return_all_layers:
                frame_audio_embed = audio_embed[:, chosen_idx].flatten(start_dim=-2, end_dim=-1)
            else:
                frame_audio_embed = audio_embed[0][chosen_idx].flatten()
        else:
            frame_audio_embed = torch.zeros([audio_dim * (2 * m + 1)], device=audio_embed.device) if not return_all_layers else torch.zeros([num_layers, audio_dim * (2 * m + 1)], device=audio_embed.device)
        batch_audio_eb.append(frame_audio_embed)
    batch_audio_eb = torch.cat([c.unsqueeze(0) for c in batch_audio_eb], dim=0)
    return (batch_audio_eb, min_batch_num)

class WanVideoApplyNAG(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoApplyNAG', display_name='WanVideo Apply NAG',
            category='WanVideoWrapper', description="Adds NAG prompt embeds to original prompt embeds: 'https://github.com/ChenDarYen/Normalized-Attention-Guidance'",
            is_experimental=False,
            inputs=[
                io.Custom('WANVIDEOTEXTEMBEDS').Input('original_text_embeds'),
                io.Custom('WANVIDEOTEXTEMBEDS').Input('nag_text_embeds'),
                io.Float.Input('nag_scale', default=11.0, min=0.0, max=100.0, step=0.1),
                io.Float.Input('nag_tau', default=2.5, min=0.0, max=10.0, step=0.1),
                io.Float.Input('nag_alpha', default=0.25, min=0.0, max=1.0, step=0.01),
                io.Boolean.Input('inplace', default=True, tooltip='If true, modifies tensors in place to save memory. Leads to different numerical results which may change the output slightly.', optional=True)
            ], outputs=[io.Custom('WANVIDEOTEXTEMBEDS').Output(display_name='text_embeds')],
        )

    @classmethod
    def execute(cls, original_text_embeds, nag_text_embeds, nag_scale, nag_tau, nag_alpha, inplace=True):
        _bound_payload(inplace)
        _bound_payload(nag_alpha)
        _bound_payload(nag_tau)
        _bound_payload(nag_scale)
        _bound_payload(nag_text_embeds)
        _bound_payload(original_text_embeds)
        _bound_strings([original_text_embeds, nag_text_embeds, nag_scale, nag_tau, nag_alpha, inplace])
        prompt_embeds_dict_copy = original_text_embeds.copy()
        prompt_embeds_dict_copy.update({'nag_prompt_embeds': nag_text_embeds['prompt_embeds'], 'nag_params': {'nag_scale': nag_scale, 'nag_tau': nag_tau, 'nag_alpha': nag_alpha, 'inplace': inplace}})
        return io.NodeOutput(prompt_embeds_dict_copy)

class WanVideoContextOptions(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoContextOptions', display_name='WanVideo Context Options',
            category='WanVideoWrapper', description='Context options for WanVideo, allows splitting the video into context windows and attemps blending them for longer generations than the model and memory otherwise would allow.',
            is_experimental=False,
            inputs=[
                io.Combo.Input('context_schedule', options=['uniform_standard', 'uniform_looped', 'static_standard']),
                io.Int.Input('context_frames', default=81, min=2, max=1000, step=1, tooltip='Number of pixel frames in the context, NOTE: the latent space has 4 frames in 1'),
                io.Int.Input('context_stride', default=4, min=4, max=100, step=1, tooltip='Context stride as pixel frames, NOTE: the latent space has 4 frames in 1'),
                io.Int.Input('context_overlap', default=16, min=4, max=100, step=1, tooltip='Context overlap as pixel frames, NOTE: the latent space has 4 frames in 1'),
                io.Boolean.Input('freenoise', default=True, tooltip='Shuffle the noise'),
                io.Boolean.Input('verbose', default=False, tooltip='Print debug output'),
                io.Combo.Input('fuse_method', options=['linear', 'pyramid'], default='linear', tooltip='Window weight function: linear=ramps at edges only, pyramid=triangular weights peaking in middle', optional=True),
                io.Latent.Input('reference_latent', tooltip='Image to be used as init for I2V models for windows where first frame is not the actual first frame. Mostly useful with MAGREF model', optional=True)
            ], outputs=[io.Custom('WANVIDCONTEXT').Output(display_name='context_options')],
        )

    @classmethod
    def execute(cls, context_schedule, context_frames, context_stride, context_overlap, freenoise, verbose, image_cond_start_step=6, image_cond_window_count=2, vae=None, fuse_method='linear', reference_latent=None):
        _bound_payload(reference_latent)
        _bound_payload(fuse_method)
        _bound_payload(vae)
        _bound_payload(image_cond_window_count)
        _bound_payload(image_cond_start_step)
        _bound_payload(verbose)
        _bound_payload(freenoise)
        _bound_payload(context_overlap)
        _bound_payload(context_stride)
        _bound_payload(context_frames)
        _bound_payload(context_schedule)
        _bound_strings([context_schedule, context_frames, context_stride, context_overlap, freenoise, verbose, image_cond_start_step, image_cond_window_count, vae, fuse_method, reference_latent])
        context_options = {'context_schedule': context_schedule, 'context_frames': context_frames, 'context_stride': context_stride, 'context_overlap': context_overlap, 'freenoise': freenoise, 'verbose': verbose, 'fuse_method': fuse_method, 'reference_latent': reference_latent['samples'] if reference_latent is not None else None}
        return io.NodeOutput(context_options)

class WanVideoAddStandInLatent(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoAddStandInLatent', display_name='WanVideo Add StandIn Latent',
            category='WanVideoWrapper', description='',
            is_experimental=False,
            inputs=[
                io.Custom('WANVIDIMAGE_EMBEDS').Input('embeds'),
                io.Latent.Input('ip_image_latent', tooltip='Reference image to encode'),
                io.Int.Input('freq_offset', default=1, min=0, max=100, step=1, tooltip='EXPERIMENTAL: RoPE frequency offset between the reference and rest of the sequence')
            ], outputs=[io.Custom('WANVIDIMAGE_EMBEDS').Output(display_name='image_embeds')],
        )

    @classmethod
    def execute(cls, embeds, ip_image_latent, freq_offset):
        _bound_payload(freq_offset)
        _bound_payload(ip_image_latent)
        _bound_payload(embeds)
        _bound_strings([embeds, ip_image_latent, freq_offset])
        new_entry = {'ip_image_latent': ip_image_latent['samples'], 'freq_offset': freq_offset}
        updated = dict(embeds)
        updated['standin_input'] = new_entry
        return io.NodeOutput(updated)

class WanVideoAddExtraLatent(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoAddExtraLatent', display_name='WanVideo Add Extra Latent',
            category='WanVideoWrapper', description='',
            is_experimental=False,
            inputs=[
                io.Custom('WANVIDIMAGE_EMBEDS').Input('embeds'),
                io.Latent.Input('extra_latents'),
                io.Int.Input('latent_index', default=0, min=-1000, max=1000, step=1, tooltip='Index to insert the extra latents at in latent space')
            ], outputs=[io.Custom('WANVIDIMAGE_EMBEDS').Output(display_name='image_embeds')],
        )

    @classmethod
    def execute(cls, embeds, extra_latents, latent_index):
        _bound_payload(latent_index)
        _bound_payload(extra_latents)
        _bound_payload(embeds)
        _bound_strings([embeds, extra_latents, latent_index])
        new_entry = {'samples': extra_latents['samples'], 'index': latent_index}
        prev_extra_latents = embeds.get('extra_latents', None)
        if prev_extra_latents is None:
            extra_latents_list = [new_entry]
        elif isinstance(prev_extra_latents, list):
            extra_latents_list = prev_extra_latents + [new_entry]
        else:
            extra_latents_list = [prev_extra_latents, new_entry]
        updated = dict(embeds)
        updated['extra_latents'] = extra_latents_list
        return io.NodeOutput(updated)

class WanVideoAddLucyEditLatents(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoAddLucyEditLatents', display_name='WanVideo Add LucyEdit Latents',
            category='WanVideoWrapper', description='',
            is_experimental=False,
            inputs=[
                io.Custom('WANVIDIMAGE_EMBEDS').Input('embeds'),
                io.Latent.Input('extra_latents')
            ], outputs=[io.Custom('WANVIDIMAGE_EMBEDS').Output(display_name='image_embeds')],
        )

    @classmethod
    def execute(cls, embeds, extra_latents):
        _bound_payload(extra_latents)
        _bound_payload(embeds)
        _bound_strings([embeds, extra_latents])
        updated = dict(embeds)
        updated['extra_channel_latents'] = extra_latents['samples']
        return io.NodeOutput(updated)

class WanVideoMiniMaxRemoverEmbeds(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoMiniMaxRemoverEmbeds', display_name='WanVideo MiniMax Remover Embeds',
            category='WanVideoWrapper', description='',
            is_experimental=False,
            inputs=[
                io.Int.Input('width', default=832, min=64, max=8096, step=8, tooltip='Width of the image to encode'),
                io.Int.Input('height', default=480, min=64, max=8096, step=8, tooltip='Height of the image to encode'),
                io.Int.Input('num_frames', default=81, min=1, max=10000, step=4, tooltip='Number of frames to encode'),
                io.Latent.Input('latents', tooltip='Encoded latents to use as control signals'),
                io.Latent.Input('mask_latents', tooltip='Encoded latents to use as mask')
            ], outputs=[io.Custom('WANVIDIMAGE_EMBEDS').Output(display_name='image_embeds')],
        )

    @classmethod
    def execute(cls, num_frames, width, height, latents, mask_latents):
        _bound_payload(mask_latents)
        _bound_payload(latents)
        _bound_payload(height)
        _bound_payload(width)
        _bound_payload(num_frames)
        _bound_strings([num_frames, width, height, latents, mask_latents])
        target_shape = (16, (num_frames - 1) // VAE_STRIDE[0] + 1, height // VAE_STRIDE[1], width // VAE_STRIDE[2])
        embeds = {'target_shape': target_shape, 'num_frames': num_frames, 'minimax_latents': latents['samples'].squeeze(0), 'minimax_mask_latents': mask_latents['samples'].squeeze(0)}
        return io.NodeOutput(embeds)

class WanVideoControlEmbeds(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoControlEmbeds', display_name='WanVideo Control Embeds',
            category='WanVideoWrapper', description='',
            is_experimental=False,
            inputs=[
                io.Float.Input('start_percent', default=0.0, min=0.0, max=1.0, step=0.01, tooltip='Start percent of the control signal'),
                io.Float.Input('end_percent', default=1.0, min=0.0, max=1.0, step=0.01, tooltip='End percent of the control signal'),
                io.Latent.Input('latents', tooltip='Encoded latents to use as control signals'),
                io.Latent.Input('fun_ref_image', tooltip='Reference latent for the Fun 1.1 -model', optional=True)
            ], outputs=[io.Custom('WANVIDIMAGE_EMBEDS').Output(display_name='image_embeds')],
        )

    @classmethod
    def execute(cls, latents, start_percent, end_percent, fun_ref_image=None):
        _bound_payload(fun_ref_image)
        _bound_payload(end_percent)
        _bound_payload(start_percent)
        _bound_payload(latents)
        _bound_strings([latents, start_percent, end_percent, fun_ref_image])
        samples = latents['samples'].squeeze(0)
        C, T, H, W = samples.shape
        num_frames = (T - 1) * 4 + 1
        seq_len = math.ceil(H * W / 4 * ((num_frames - 1) // 4 + 1))
        embeds = {'max_seq_len': seq_len, 'target_shape': samples.shape, 'num_frames': num_frames, 'control_embeds': {'control_images': samples, 'start_percent': start_percent, 'end_percent': end_percent, 'fun_ref_image': fun_ref_image['samples'][:, :, 0] if fun_ref_image is not None else None}}
        return io.NodeOutput(embeds)

class WanVideoAddControlEmbeds(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoAddControlEmbeds', display_name='WanVideo Add Control Embeds',
            category='WanVideoWrapper', description='',
            is_experimental=False,
            inputs=[
                io.Custom('WANVIDIMAGE_EMBEDS').Input('embeds'),
                io.Float.Input('start_percent', default=0.0, min=0.0, max=1.0, step=0.01, tooltip='Start percent of the control signal'),
                io.Float.Input('end_percent', default=1.0, min=0.0, max=1.0, step=0.01, tooltip='End percent of the control signal'),
                io.Latent.Input('latents', tooltip='Encoded latents to use as control signals', optional=True),
                io.Latent.Input('fun_ref_image', tooltip='Reference latent for the Fun 1.1 -model', optional=True)
            ], outputs=[io.Custom('WANVIDIMAGE_EMBEDS').Output(display_name='image_embeds')],
        )

    @classmethod
    def execute(cls, embeds, start_percent, end_percent, fun_ref_image=None, latents=None):
        _bound_payload(latents)
        _bound_payload(fun_ref_image)
        _bound_payload(end_percent)
        _bound_payload(start_percent)
        _bound_payload(embeds)
        _bound_strings([embeds, start_percent, end_percent, fun_ref_image, latents])
        new_entry = {'control_images': latents['samples'].squeeze(0) if latents is not None else None, 'start_percent': start_percent, 'end_percent': end_percent, 'fun_ref_image': fun_ref_image['samples'][:, :, 0] if fun_ref_image is not None else None}
        updated = dict(embeds)
        updated['control_embeds'] = new_entry
        return io.NodeOutput(updated)

class WanVideoAddPusaNoise(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoAddPusaNoise', display_name='WanVideo Add Pusa Noise',
            category='WanVideoWrapper', description='Adds latent and timestep noise multipliers when using flowmatch_pusa',
            is_experimental=False,
            inputs=[
                io.Custom('WANVIDIMAGE_EMBEDS').Input('embeds'),
                io.Float.Input('noise_multipliers', default=0.0, min=0.0, max=100.0, step=0.01, tooltip='Noise multipliers for Pusa, can be a list of floats'),
                io.Int.Input('noisy_steps', default=-1, min=-1, max=1000, tooltip='Number steps to apply the extra noise')
            ], outputs=[io.Custom('WANVIDIMAGE_EMBEDS').Output(display_name='image_embeds')],
        )

    @classmethod
    def execute(cls, embeds, noise_multipliers, noisy_steps):
        _bound_payload(noisy_steps)
        _bound_payload(noise_multipliers)
        _bound_payload(embeds)
        _bound_strings([embeds, noise_multipliers, noisy_steps])
        updated = dict(embeds)
        updated['pusa_noise_multipliers'] = noise_multipliers
        updated['pusa_noisy_steps'] = noisy_steps
        return io.NodeOutput(updated)

class WanVideoEmptyEmbeds(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoEmptyEmbeds', display_name='WanVideo Empty Embeds',
            category='WanVideoWrapper', description='',
            is_experimental=False,
            inputs=[
                io.Int.Input('width', default=832, min=64, max=8096, step=8, tooltip='Width of the image to encode'),
                io.Int.Input('height', default=480, min=64, max=8096, step=8, tooltip='Height of the image to encode'),
                io.Int.Input('num_frames', default=81, min=1, max=10000, step=4, tooltip='Number of frames to encode'),
                io.Custom('WANVIDIMAGE_EMBEDS').Input('control_embeds', tooltip='control signal for the Fun -model', optional=True),
                io.Latent.Input('extra_latents', tooltip='First latent to use for the Pusa -model', optional=True)
            ], outputs=[io.Custom('WANVIDIMAGE_EMBEDS').Output(display_name='image_embeds')],
        )

    @classmethod
    def execute(cls, num_frames, width, height, control_embeds=None, extra_latents=None):
        _bound_payload(extra_latents)
        _bound_payload(control_embeds)
        _bound_payload(height)
        _bound_payload(width)
        _bound_payload(num_frames)
        _bound_strings([num_frames, width, height, control_embeds, extra_latents])
        target_shape = (16, (num_frames - 1) // VAE_STRIDE[0] + 1, height // VAE_STRIDE[1], width // VAE_STRIDE[2])
        embeds = {'target_shape': target_shape, 'num_frames': num_frames, 'control_embeds': control_embeds['control_embeds'] if control_embeds is not None else None}
        if extra_latents is not None:
            embeds['extra_latents'] = [{'samples': extra_latents['samples'], 'index': 0}]
        return io.NodeOutput(embeds)

class WanVideoUniLumosEmbeds(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoUniLumosEmbeds', display_name='WanVideo UniLumos Embeds',
            category='WanVideoWrapper', description='',
            is_experimental=False,
            inputs=[
                io.Int.Input('width', default=832, min=64, max=8096, step=8, tooltip='Width of the image to encode'),
                io.Int.Input('height', default=480, min=64, max=8096, step=8, tooltip='Height of the image to encode'),
                io.Int.Input('num_frames', default=81, min=1, max=10000, step=4, tooltip='Number of frames to encode'),
                io.Latent.Input('foreground_latents', tooltip='Video foreground latents', optional=True),
                io.Latent.Input('background_latents', tooltip='Video background latents', optional=True)
            ], outputs=[io.Custom('WANVIDIMAGE_EMBEDS').Output(display_name='image_embeds')],
        )

    @classmethod
    def execute(cls, num_frames, width, height, foreground_latents=None, background_latents=None):
        _preflight_unilumos(num_frames, width, height, foreground_latents, background_latents)
        _bound_payload(background_latents)
        _bound_payload(foreground_latents)
        _bound_payload(height)
        _bound_payload(width)
        _bound_payload(num_frames)
        _bound_strings([num_frames, width, height, foreground_latents, background_latents])
        target_shape = (16, (num_frames - 1) // VAE_STRIDE[0] + 1, height // VAE_STRIDE[1], width // VAE_STRIDE[2])
        embeds = {'target_shape': target_shape, 'num_frames': num_frames}
        if foreground_latents is not None:
            embeds['foreground_latents'] = foreground_latents['samples'][0]
        else:
            embeds['foreground_latents'] = torch.zeros(target_shape[0], target_shape[1], target_shape[2], target_shape[3], device=torch.device('cpu'), dtype=torch.float32)
        if background_latents is not None:
            embeds['background_latents'] = background_latents['samples'][0]
        else:
            embeds['background_latents'] = torch.zeros(target_shape[0], target_shape[1], target_shape[2], target_shape[3], device=torch.device('cpu'), dtype=torch.float32)
        return io.NodeOutput(embeds)

class WanVideoPhantomEmbeds(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoPhantomEmbeds', display_name='WanVideo Phantom Embeds',
            category='WanVideoWrapper', description='',
            is_experimental=False,
            inputs=[
                io.Int.Input('num_frames', default=81, min=1, max=10000, step=4, tooltip='Number of frames to encode'),
                io.Latent.Input('phantom_latent_1', tooltip='reference latents for the phantom model'),
                io.Float.Input('phantom_cfg_scale', default=5.0, min=0.0, max=10.0, step=0.01, tooltip='CFG scale for the extra phantom cond pass'),
                io.Float.Input('phantom_start_percent', default=0.0, min=0.0, max=1.0, step=0.01, tooltip='Start percent of the phantom model'),
                io.Float.Input('phantom_end_percent', default=1.0, min=0.0, max=1.0, step=0.01, tooltip='End percent of the phantom model'),
                io.Latent.Input('phantom_latent_2', tooltip='reference latents for the phantom model', optional=True),
                io.Latent.Input('phantom_latent_3', tooltip='reference latents for the phantom model', optional=True),
                io.Latent.Input('phantom_latent_4', tooltip='reference latents for the phantom model', optional=True),
                io.Custom('WANVIDIMAGE_EMBEDS').Input('vace_embeds', tooltip='VACE embeds', optional=True)
            ], outputs=[io.Custom('WANVIDIMAGE_EMBEDS').Output(display_name='image_embeds')],
        )

    @classmethod
    def execute(cls, num_frames, phantom_cfg_scale, phantom_start_percent, phantom_end_percent, phantom_latent_1, phantom_latent_2=None, phantom_latent_3=None, phantom_latent_4=None, vace_embeds=None):
        _preflight_phantom([phantom_latent_1, phantom_latent_2, phantom_latent_3, phantom_latent_4])
        _bound_payload(vace_embeds)
        _bound_payload(phantom_latent_4)
        _bound_payload(phantom_latent_3)
        _bound_payload(phantom_latent_2)
        _bound_payload(phantom_latent_1)
        _bound_payload(phantom_end_percent)
        _bound_payload(phantom_start_percent)
        _bound_payload(phantom_cfg_scale)
        _bound_payload(num_frames)
        _bound_strings([num_frames, phantom_cfg_scale, phantom_start_percent, phantom_end_percent, phantom_latent_1, phantom_latent_2, phantom_latent_3, phantom_latent_4, vace_embeds])
        samples = phantom_latent_1['samples'].squeeze(0)
        if phantom_latent_2 is not None:
            samples = torch.cat([samples, phantom_latent_2['samples'].squeeze(0)], dim=1)
        if phantom_latent_3 is not None:
            samples = torch.cat([samples, phantom_latent_3['samples'].squeeze(0)], dim=1)
        if phantom_latent_4 is not None:
            samples = torch.cat([samples, phantom_latent_4['samples'].squeeze(0)], dim=1)
        C, T, H, W = samples.shape
        log.info(f'Phantom latents shape: {samples.shape}')
        target_shape = (16, (num_frames - 1) // VAE_STRIDE[0] + 1, H * 8 // VAE_STRIDE[1], W * 8 // VAE_STRIDE[2])
        embeds = {'target_shape': target_shape, 'num_frames': num_frames, 'phantom_latents': samples, 'phantom_cfg_scale': phantom_cfg_scale, 'phantom_start_percent': phantom_start_percent, 'phantom_end_percent': phantom_end_percent}
        if vace_embeds is not None:
            vace_input = {'vace_context': vace_embeds['vace_context'], 'vace_scale': vace_embeds['vace_scale'], 'has_ref': vace_embeds['has_ref'], 'vace_start_percent': vace_embeds['vace_start_percent'], 'vace_end_percent': vace_embeds['vace_end_percent'], 'vace_seq_len': vace_embeds['vace_seq_len'], 'additional_vace_inputs': vace_embeds['additional_vace_inputs']}
            embeds.update(vace_input)
        return io.NodeOutput(embeds)

class WanVideoRealisDanceLatents(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoRealisDanceLatents', display_name='WanVideo RealisDance Latents',
            category='WanVideoWrapper', description='',
            is_experimental=False,
            inputs=[
                io.Latent.Input('ref_latent', tooltip='Reference image to encode'),
                io.Float.Input('pose_cond_start_percent', default=0.0, min=0.0, max=1.0, step=0.01, tooltip='Start percent of the SMPL model'),
                io.Float.Input('pose_cond_end_percent', default=1.0, min=0.0, max=1.0, step=0.01, tooltip='End percent of the SMPL model'),
                io.Latent.Input('smpl_latent', tooltip='SMPL pose image to encode', optional=True),
                io.Latent.Input('hamer_latent', tooltip='Hamer hand pose image to encode', optional=True)
            ], outputs=[io.Custom('ADD_COND_LATENTS').Output(display_name='add_cond_latents')],
        )

    @classmethod
    def execute(cls, ref_latent, pose_cond_start_percent, pose_cond_end_percent, hamer_latent=None, smpl_latent=None):
        _preflight_realis(smpl_latent, hamer_latent)
        _bound_payload(smpl_latent)
        _bound_payload(hamer_latent)
        _bound_payload(pose_cond_end_percent)
        _bound_payload(pose_cond_start_percent)
        _bound_payload(ref_latent)
        _bound_strings([ref_latent, pose_cond_start_percent, pose_cond_end_percent, hamer_latent, smpl_latent])
        if smpl_latent is None and hamer_latent is None:
            raise Exception('At least one of smpl_latent or hamer_latent must be provided')
        if smpl_latent is None:
            smpl = torch.zeros_like(hamer_latent['samples'])
        else:
            smpl = smpl_latent['samples']
        if hamer_latent is None:
            hamer = torch.zeros_like(smpl_latent['samples'])
        else:
            hamer = hamer_latent['samples']
        pose_latent = torch.cat((smpl, hamer), dim=1)
        add_cond_latents = {'ref_latent': ref_latent['samples'], 'pose_latent': pose_latent, 'pose_cond_start_percent': pose_cond_start_percent, 'pose_cond_end_percent': pose_cond_end_percent}
        return io.NodeOutput(add_cond_latents)

class WanVideoAddMTVMotion(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoAddMTVMotion', display_name='WanVideo MTV Crafter Motion',
            category='WanVideoWrapper', description='',
            is_experimental=False,
            inputs=[
                io.Custom('WANVIDIMAGE_EMBEDS').Input('embeds'),
                io.Custom('MTVCRAFTERMOTION').Input('mtv_crafter_motion'),
                io.Float.Input('strength', default=1.0, min=0.0, max=100.0, step=0.01, tooltip='Strength of the MTV motion'),
                io.Float.Input('start_percent', default=0.0, min=0.0, max=1.0, step=0.01, tooltip='Start percent to apply the ref '),
                io.Float.Input('end_percent', default=1.0, min=0.0, max=1.0, step=0.01, tooltip='End percent to apply the ref ')
            ], outputs=[io.Custom('WANVIDIMAGE_EMBEDS').Output(display_name='image_embeds')],
        )

    @classmethod
    def execute(cls, embeds, mtv_crafter_motion, strength, start_percent, end_percent):
        _bound_payload(end_percent)
        _bound_payload(start_percent)
        _bound_payload(strength)
        _bound_payload(mtv_crafter_motion)
        _bound_payload(embeds)
        _bound_strings([embeds, mtv_crafter_motion, strength, start_percent, end_percent])
        new_entry = {'mtv_motion_tokens': mtv_crafter_motion['mtv_motion_tokens'], 'strength': strength, 'start_percent': start_percent, 'end_percent': end_percent, 'global_mean': mtv_crafter_motion['global_mean'], 'global_std': mtv_crafter_motion['global_std']}
        updated = dict(embeds)
        updated['mtv_crafter_motion'] = new_entry
        return io.NodeOutput(updated)

class WanVideoSVIProEmbeds(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoSVIProEmbeds', display_name='WanVideo SVIPro Embeds',
            category='WanVideoWrapper', description='',
            is_experimental=False,
            inputs=[
                io.Latent.Input('anchor_samples', tooltip='Initial start image encoded'),
                io.Int.Input('num_frames', default=81, min=1, max=10000, step=4, tooltip='Number of frames to encode'),
                io.Latent.Input('prev_samples', tooltip='Last latent from previous generation', optional=True),
                io.Int.Input('motion_latent_count', default=1, min=0, max=100, step=1, tooltip='Number of latents used to continue', optional=True)
            ], outputs=[io.Custom('WANVIDIMAGE_EMBEDS').Output(display_name='image_embeds')],
        )

    @classmethod
    def execute(cls, anchor_samples, num_frames, prev_samples=None, motion_latent_count=1):
        _preflight_svi(anchor_samples, num_frames, prev_samples, motion_latent_count)
        _bound_payload(motion_latent_count)
        _bound_payload(prev_samples)
        _bound_payload(num_frames)
        _bound_payload(anchor_samples)
        _bound_strings([anchor_samples, num_frames, prev_samples, motion_latent_count])
        anchor_latent = anchor_samples['samples'][0].clone()
        C, T, H, W = anchor_latent.shape
        total_latents = (num_frames - 1) // 4 + 1
        device = anchor_latent.device
        dtype = anchor_latent.dtype
        if prev_samples is None or motion_latent_count == 0:
            padding_size = total_latents - anchor_latent.shape[1]
            padding = torch.zeros(C, padding_size, H, W, dtype=dtype, device=device)
            y = torch.concat([anchor_latent, padding], dim=1)
        else:
            prev_latent = prev_samples['samples'][0].clone()
            motion_latent = prev_latent[:, -motion_latent_count:]
            padding_size = total_latents - anchor_latent.shape[1] - motion_latent.shape[1]
            padding = torch.zeros(C, padding_size, H, W, dtype=dtype, device=device)
            y = torch.concat([anchor_latent, motion_latent, padding], dim=1)
        msk = torch.ones(1, num_frames, H, W, device=device, dtype=dtype)
        msk[:, 1:] = 0
        msk = torch.concat([torch.repeat_interleave(msk[:, 0:1], repeats=4, dim=1), msk[:, 1:]], dim=1)
        msk = msk.view(1, msk.shape[1] // 4, 4, H, W)
        msk = msk.transpose(1, 2)[0]
        image_embeds = {'image_embeds': y, 'num_frames': num_frames, 'lat_h': H, 'lat_w': W, 'mask': msk}
        return io.NodeOutput(image_embeds)

class WanVideoAddTTMLatents(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoAddTTMLatents', display_name='WanVideo Add TTMLatents',
            category='WanVideoWrapper', description='https://github.com/time-to-move/TTM',
            is_experimental=False,
            inputs=[
                io.Custom('WANVIDIMAGE_EMBEDS').Input('embeds'),
                io.Latent.Input('reference_latents', tooltip='Latents used as reference for TTM'),
                io.Mask.Input('mask', tooltip='Mask used for TTM'),
                io.Int.Input('start_step', default=0, min=-1, max=1000, step=1, tooltip='Start step for whole denoising process'),
                io.Int.Input('end_step', default=1, min=1, max=1000, step=1, tooltip='The step to stop applying TTM')
            ], outputs=[io.Custom('WANVIDIMAGE_EMBEDS').Output(display_name='image_embeds')],
        )

    @classmethod
    def execute(cls, embeds, reference_latents, mask, start_step, end_step):
        _bound_payload(end_step)
        _bound_payload(start_step)
        _bound_payload(mask)
        _bound_payload(reference_latents)
        _bound_payload(embeds)
        _bound_strings([embeds, reference_latents, mask, start_step, end_step])
        if end_step < max(0, start_step):
            raise ValueError(f'`end_step` ({end_step}) must be >= `start_step` ({start_step}).')
        mask_sampled = mask[::4]
        mask_sampled = mask_sampled.unsqueeze(1).unsqueeze(0)
        vae_upscale_factor = 8
        if reference_latents['samples'].shape[1] == 48:
            vae_upscale_factor = 16
        H_latent = mask_sampled.shape[-2] // vae_upscale_factor
        W_latent = mask_sampled.shape[-1] // vae_upscale_factor
        mask_latent = F.interpolate(mask_sampled.float(), size=(mask_sampled.shape[2], H_latent, W_latent), mode='nearest')
        updated = dict(embeds)
        updated['ttm_reference_latents'] = reference_latents['samples'].squeeze(0)
        updated['ttm_mask'] = mask_latent.squeeze(0).movedim(1, 0)
        updated['ttm_start_step'] = start_step
        updated['ttm_end_step'] = end_step
        return io.NodeOutput(updated)

class ExtractStartFramesForContinuations(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='ExtractStartFramesForContinuations', display_name='Extract Start Frames For Continuations',
            category='WanVideoWrapper', description='Extracts the first N frames from a video sequence for continuations.',
            is_experimental=False,
            inputs=[
                io.Image.Input('input_video_frames', tooltip='Input video frames to extract the start frames from.'),
                io.Int.Input('num_frames', default=10, min=1, max=1024, step=1, tooltip='Number of frames to get from the start of the video.')
            ], outputs=[io.Image.Output(display_name='start_frames')],
        )

    @classmethod
    def execute(cls, input_video_frames, num_frames):
        _bound_payload(num_frames)
        _bound_payload(input_video_frames)
        _bound_strings([input_video_frames, num_frames])
        if input_video_frames is None or input_video_frames.shape[0] == 0:
            log.warning('Input video frames are empty. Returning an empty tensor.')
            if input_video_frames is not None:
                return io.NodeOutput(torch.empty((0,) + input_video_frames.shape[1:], dtype=input_video_frames.dtype))
            else:
                return io.NodeOutput(torch.empty((0, 64, 64, 3), dtype=torch.float32))
        total_frames = input_video_frames.shape[0]
        num_to_get = min(num_frames, total_frames)
        if num_to_get < num_frames:
            log.warning(f'Requested {num_frames} frames, but input video only has {total_frames} frames. Returning first {num_to_get} frames.')
        start_frames = input_video_frames[:num_to_get]
        return io.NodeOutput(start_frames.cpu().float())

class WanVideoLatentReScale(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoLatentReScale', display_name='WanVideo Latent ReScale',
            category='WanVideoWrapper', description='Rescale latents to match the expected range for encoding or decoding between native ComfyUI VAE and the WanVideoWrapper VAE.',
            is_experimental=False,
            inputs=[
                io.Latent.Input('samples'),
                io.Combo.Input('direction', options=['comfy_to_wrapper', 'wrapper_to_comfy'], tooltip='Direction to rescale latents, from comfy to wrapper or vice versa')
            ], outputs=[io.Latent.Output(display_name='samples')],
        )

    @classmethod
    def execute(cls, samples, direction):
        _bound_payload(direction)
        _bound_payload(samples)
        _bound_strings([samples, direction])
        samples = samples.copy()
        latents = samples['samples']
        if latents.shape[1] == 48:
            mean = [-0.2289, -0.0052, -0.1323, -0.2339, -0.2799, 0.0174, 0.1838, 0.1557, -0.1382, 0.0542, 0.2813, 0.0891, 0.157, -0.0098, 0.0375, -0.1825, -0.2246, -0.1207, -0.0698, 0.5109, 0.2665, -0.2108, -0.2158, 0.2502, -0.2055, -0.0322, 0.1109, 0.1567, -0.0729, 0.0899, -0.2799, -0.123, -0.0313, -0.1649, 0.0117, 0.0723, -0.2839, -0.2083, -0.052, 0.3748, 0.0152, 0.1957, 0.1433, -0.2944, 0.3573, -0.0548, -0.1681, -0.0667]
            std = [0.4765, 1.0364, 0.4514, 1.1677, 0.5313, 0.499, 0.4818, 0.5013, 0.8158, 1.0344, 0.5894, 1.0901, 0.6885, 0.6165, 0.8454, 0.4978, 0.5759, 0.3523, 0.7135, 0.6804, 0.5833, 1.4146, 0.8986, 0.5659, 0.7069, 0.5338, 0.4889, 0.4917, 0.4069, 0.4999, 0.6866, 0.4093, 0.5709, 0.6065, 0.6415, 0.4944, 0.5726, 1.2042, 0.5458, 1.6887, 0.3971, 1.06, 0.3943, 0.5537, 0.5444, 0.4089, 0.7468, 0.7744]
        else:
            mean = [-0.7571, -0.7089, -0.9113, 0.1075, -0.1745, 0.9653, -0.1517, 1.5508, 0.4134, -0.0715, 0.5517, -0.3632, -0.1922, -0.9497, 0.2503, -0.2921]
            std = [2.8184, 1.4541, 2.3275, 2.6558, 1.2196, 1.7708, 2.6052, 2.0743, 3.2687, 2.1526, 2.8652, 1.5579, 1.6382, 1.1253, 2.8251, 1.916]
        mean = torch.tensor(mean).view(1, latents.shape[1], 1, 1, 1)
        std = torch.tensor(std).view(1, latents.shape[1], 1, 1, 1)
        inv_std = (1.0 / std).view(1, latents.shape[1], 1, 1, 1)
        if direction == 'comfy_to_wrapper':
            latents = (latents - mean.to(latents)) * inv_std.to(latents)
        elif direction == 'wrapper_to_comfy':
            latents = latents / inv_std.to(latents) + mean.to(latents)
        samples['samples'] = latents
        return io.NodeOutput(samples)

class WanVideoPassImagesFromSamples(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoPassImagesFromSamples', display_name='WanVideo Pass Images From Samples',
            category='WanVideoWrapper', description='Gets possible already decoded images from the samples dictionary, used with Multi/InfiniteTalk sampling',
            is_experimental=False,
            inputs=[
                io.Latent.Input('samples')
            ], outputs=[io.Image.Output(display_name='images', tooltip='Decoded images from the samples dictionary'), io.String.Output(display_name='output_path', tooltip='Output path if provided in the samples dictionary')],
        )

    @classmethod
    def execute(cls, samples):
        _bound_payload(samples)
        _bound_strings([samples])
        video = samples.get('video', None)
        video.clamp_(-1.0, 1.0)
        video.add_(1.0).div_(2.0)
        return io.NodeOutput(video.cpu().float(), samples.get('output_path', ''))

class WanVideoPreviewEmbeds(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoPreviewEmbeds', display_name='WanVideo Preview Embeds',
            category='WanVideoWrapper', description='',
            is_experimental=False,
            inputs=[
                io.Custom('WANVIDIMAGE_EMBEDS').Input('embeds')
            ], outputs=[io.Latent.Output(display_name='image_embeds'), io.Mask.Output(display_name='mask')],
        )

    @classmethod
    def execute(cls, embeds):
        _bound_payload(embeds)
        _bound_strings([embeds])
        latents = embeds.get('image_embeds', None)
        mask = embeds.get('mask', None)
        if mask is not None:
            mask = mask[0].float().cpu()
        return io.NodeOutput({'samples': latents.unsqueeze(0)}, mask)

class WanVideoCombineEmbeds(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoCombineEmbeds', display_name='WanVideo Combine Embeds',
            category='WanVideoWrapper', description='',
            is_experimental=True,
            inputs=[
                io.Custom('WANVIDIMAGE_EMBEDS').Input('embeds_1'),
                io.Custom('WANVIDIMAGE_EMBEDS').Input('embeds_2')
            ], outputs=[io.Custom('WANVIDIMAGE_EMBEDS').Output(display_name='image_embeds')],
        )

    @classmethod
    def execute(cls, embeds_1, embeds_2):
        _bound_payload(embeds_2)
        _bound_payload(embeds_1)
        _bound_strings([embeds_1, embeds_2])
        combined = {**embeds_1, **embeds_2}
        return io.NodeOutput(combined)

class WanVideoAddOviAudioToLatents(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoAddOviAudioToLatents', display_name='WanVideo Add MMAudio To Latents',
            category='WanVideoWrapper/Ovi', description='',
            is_experimental=False,
            inputs=[
                io.Latent.Input('original_samples'),
                io.Latent.Input('audio_samples')
            ], outputs=[io.Latent.Output(display_name='samples')],
        )

    @classmethod
    def execute(cls, original_samples, audio_samples):
        _bound_payload(audio_samples)
        _bound_payload(original_samples)
        _bound_strings([original_samples, audio_samples])
        samples = original_samples.copy()
        samples.update(audio_samples)
        return io.NodeOutput(samples)

class WanVideoEmptyMMAudioLatents(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoEmptyMMAudioLatents', display_name='WanVideo Empty MMAudio Latents',
            category='WanVideoWrapper/Ovi', description='',
            is_experimental=False,
            inputs=[
                io.Int.Input('length', default=157, min=1, max=10000, step=1, tooltip='Length of the audio latent sequence')
            ], outputs=[io.Latent.Output(display_name='samples')],
        )

    @classmethod
    def execute(cls, length):
        _preflight_ovi_empty(length)
        _bound_payload(length)
        _bound_strings([length])
        audio_latents = torch.zeros((length, 20), device=torch.device('cpu'), dtype=torch.float32)
        return io.NodeOutput({'latent_ovi_audio': audio_latents})

class WanVideoOviCFG(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoOviCFG', display_name='WanVideo Ovi CFG',
            category='WanVideoWrapper/Ovi', description='Adds Ovi negative text embeddings and audio CFG scale to the text embeddings dictionary',
            is_experimental=False,
            inputs=[
                io.Custom('WANVIDEOTEXTEMBEDS').Input('original_text_embeds'),
                io.Float.Input('ovi_audio_cfg', default=3.0, min=0.0, max=100.0, step=0.01),
                io.Custom('WANVIDEOTEXTEMBEDS').Input('ovi_negative_text_embeds', optional=True)
            ], outputs=[io.Custom('WANVIDEOTEXTEMBEDS').Output(display_name='text_embeds')],
        )

    @classmethod
    def execute(cls, original_text_embeds, ovi_audio_cfg, ovi_negative_text_embeds=None):
        _bound_payload(ovi_negative_text_embeds)
        _bound_payload(ovi_audio_cfg)
        _bound_payload(original_text_embeds)
        _bound_strings([original_text_embeds, ovi_audio_cfg, ovi_negative_text_embeds])
        negative_text_embeds = None
        if ovi_negative_text_embeds is not None:
            negative_text_embeds = ovi_negative_text_embeds.get('prompt_embeds', None)
        if negative_text_embeds is None:
            negative_text_embeds = original_text_embeds['prompt_embeds']
            log.info('WanVideoOviCFG: Ovi negative text embeddings not provided, using original prompt embeddings as negative embeddings')
        else:
            log.info('WanVideoOviCFG: Using provided Ovi audio negative text embeddings')
        log.info('WanVideoOviCFG: negative text embedding shape: {}'.format(negative_text_embeds[0].shape))
        prompt_embeds_dict_copy = original_text_embeds.copy()
        prompt_embeds_dict_copy.update({'ovi_negative_prompt_embeds': negative_text_embeds, 'ovi_audio_cfg': ovi_audio_cfg})
        return io.NodeOutput(prompt_embeds_dict_copy)

class WanVideoAddSteadyDancerEmbeds(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoAddSteadyDancerEmbeds', display_name='WanVideo Add SteadyDancer Embeds',
            category='WanVideoWrapper', description='',
            is_experimental=False,
            inputs=[
                io.Custom('WANVIDIMAGE_EMBEDS').Input('embeds'),
                io.Latent.Input('pose_latents_positive'),
                io.Float.Input('pose_strength_spatial', default=1.0, min=0.0, max=100.0, step=0.01, tooltip='Strength of the pose embedding'),
                io.Float.Input('pose_strength_temporal', default=1.0, min=0.0, max=100.0, step=0.01, tooltip='Strength of the pose embedding'),
                io.Float.Input('start_percent', default=0.0, min=0.0, max=1.0, step=0.01, tooltip='Start percentage of the embedding application'),
                io.Float.Input('end_percent', default=1.0, min=0.0, max=1.0, step=0.01, tooltip='End percentage of the embedding application'),
                io.Latent.Input('pose_latents_negative', optional=True),
                io.Custom('WANVIDIMAGE_CLIPEMBEDS').Input('clip_vision_embeds', optional=True)
            ], outputs=[io.Custom('WANVIDIMAGE_EMBEDS').Output(display_name='image_embeds')],
        )

    @classmethod
    def execute(cls, embeds, pose_latents_positive, pose_strength_spatial, pose_strength_temporal, start_percent=0.0, end_percent=1.0, pose_latents_negative=None, clip_vision_embeds=None):
        _bound_payload(clip_vision_embeds)
        _bound_payload(pose_latents_negative)
        _bound_payload(end_percent)
        _bound_payload(start_percent)
        _bound_payload(pose_strength_temporal)
        _bound_payload(pose_strength_spatial)
        _bound_payload(pose_latents_positive)
        _bound_payload(embeds)
        _bound_strings([embeds, pose_latents_positive, pose_strength_spatial, pose_strength_temporal, start_percent, end_percent, pose_latents_negative, clip_vision_embeds])
        sdancer_embeds = {'cond_pos': pose_latents_positive['samples'][0], 'cond_neg': pose_latents_negative['samples'][0] if pose_latents_negative else None, 'pose_strength_spatial': pose_strength_spatial, 'pose_strength_temporal': pose_strength_temporal, 'start_percent': start_percent, 'end_percent': end_percent, 'clip_fea': clip_vision_embeds}
        updated = dict(embeds)
        updated['sdancer_embeds'] = sdancer_embeds
        return io.NodeOutput(updated)

class WanVideoAddFlashVSRInput(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoAddFlashVSRInput', display_name='WanVideo Add FlashVSR Input',
            category='WanVideoWrapper', description='',
            is_experimental=False,
            inputs=[
                io.Custom('WANVIDIMAGE_EMBEDS').Input('embeds'),
                io.Image.Input('images', tooltip='Low-res video frames to enhance'),
                io.Float.Input('strength', default=1.0, min=0.0, max=2.0, step=0.01, tooltip='Strength to apply the FlashVSR latent')
            ], outputs=[io.Custom('WANVIDIMAGE_EMBEDS').Output(display_name='image_embeds')],
        )

    @classmethod
    def execute(cls, embeds, images, strength):
        _bound_payload(strength)
        _bound_payload(images)
        _bound_payload(embeds)
        _bound_strings([embeds, images, strength])
        updated = dict(embeds)
        updated['flashvsr_LQ_images'] = images
        updated['flashvsr_strength'] = strength
        return io.NodeOutput(updated)

class WanVideoAddS2VEmbeds(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoAddS2VEmbeds', display_name='WanVideo Add S2V Embeds',
            category='WanVideoWrapper', description='',
            is_experimental=False,
            inputs=[
                io.Custom('WANVIDIMAGE_EMBEDS').Input('embeds'),
                io.Int.Input('frame_window_size', default=80, min=1, max=100000, step=1, tooltip='Number of frames in a single window'),
                io.Float.Input('audio_scale', default=1.0, min=0.0, max=10.0, step=0.1, tooltip='Scale factor for audio embeddings'),
                io.Float.Input('pose_start_percent', default=0.0, min=0.0, max=1.0, step=0.01, tooltip='Start percentage for pose embeddings'),
                io.Float.Input('pose_end_percent', default=1.0, min=0.0, max=1.0, step=0.01, tooltip='End percentage for pose embeddings'),
                io.Custom('AUDIO_ENCODER_OUTPUT').Input('audio_encoder_output', optional=True),
                io.Latent.Input('ref_latent', optional=True),
                io.Latent.Input('pose_latent', optional=True),
                io.Custom('WANVAE').Input('vae', optional=True),
                io.Boolean.Input('enable_framepack', default=False, tooltip='Enable Framepack sampling loop, not compatible with context windows', optional=True)
            ], outputs=[io.Custom('WANVIDIMAGE_EMBEDS').Output(display_name='image_embeds'), io.Int.Output(display_name='audio_frame_count')],
        )

    @classmethod
    def execute(cls, embeds, frame_window_size, audio_encoder_output=None, audio_scale=1.0, ref_latent=None, pose_latent=None, vae=None, pose_start_percent=0.0, pose_end_percent=1.0, enable_framepack=False):
        _preflight_s2v(embeds, audio_encoder_output, frame_window_size)
        _bound_payload(enable_framepack)
        _bound_payload(pose_end_percent)
        _bound_payload(pose_start_percent)
        _bound_payload(vae)
        _bound_payload(pose_latent)
        _bound_payload(ref_latent)
        _bound_payload(audio_scale)
        _bound_payload(audio_encoder_output)
        _bound_payload(frame_window_size)
        _bound_payload(embeds)
        _bound_strings([embeds, frame_window_size, audio_encoder_output, audio_scale, ref_latent, pose_latent, vae, pose_start_percent, pose_end_percent, enable_framepack])
        audio_frame_count = 0
        if audio_encoder_output is not None:
            all_layers = audio_encoder_output['encoded_audio_all_layers']
            audio_feat = torch.stack(all_layers, dim=0).squeeze(1)
            print('audio_feat in', audio_feat.shape)
            input_fps = 50
            output_fps = 30
            bucket_fps = 16
            if input_fps != output_fps:
                audio_feat = _s2v_interpolate(audio_feat, input_fps=input_fps, output_fps=output_fps)
            print('audio_feat after interpolation', audio_feat.shape)
            audio_feat = audio_feat[:, :embeds['num_frames'] * output_fps // bucket_fps, :]
            print('audio_feat after trim', audio_feat.shape)
            audio_embed_bucket, num_repeat = _s2v_audio_bucket(audio_feat, fps=bucket_fps, batch_frames=frame_window_size)
            print('audio_embed_bucket', audio_embed_bucket.shape)
            audio_embed_bucket = audio_embed_bucket.unsqueeze(0)
            if len(audio_embed_bucket.shape) == 3:
                audio_embed_bucket = audio_embed_bucket.permute(0, 2, 1)
            elif len(audio_embed_bucket.shape) == 4:
                audio_embed_bucket = audio_embed_bucket.permute(0, 2, 3, 1)
            audio_frame_count = audio_embed_bucket.shape[-1]
            print('audio_embed_bucket', audio_embed_bucket.shape)
        new_entry = {'audio_embed_bucket': audio_embed_bucket if audio_encoder_output is not None else None, 'num_repeat': num_repeat if audio_encoder_output is not None else None, 'ref_latent': ref_latent['samples'] if ref_latent is not None else None, 'pose_latent': pose_latent['samples'] if pose_latent is not None else None, 'audio_scale': audio_scale, 'vae': vae, 'pose_start_percent': pose_start_percent, 'pose_end_percent': pose_end_percent, 'enable_framepack': enable_framepack, 'frame_window_size': frame_window_size}
        updated = dict(embeds)
        updated['audio_embeds'] = new_entry
        return io.NodeOutput(updated, audio_frame_count)

class WanVideoAddOneToAllPoseEmbeds(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoAddOneToAllPoseEmbeds', display_name='WanVideo Add OneToAll Pose Embeds',
            category='WanVideoWrapper', description='',
            is_experimental=False,
            inputs=[
                io.Custom('WANVIDIMAGE_EMBEDS').Input('embeds'),
                io.Image.Input('pose_images', tooltip='Pose images for the entire video'),
                io.Float.Input('strength', default=1.0, min=0.0, max=10.0, step=0.01, tooltip='Strength of the pose control'),
                io.Float.Input('start_percent', default=0.0, min=0.0, max=1.0, step=0.01, tooltip='Start percentage of the pose control application'),
                io.Float.Input('end_percent', default=1.0, min=0.0, max=1.0, step=0.01, tooltip='End percentage of the pose control application'),
                io.Image.Input('pose_prefix_image', optional=True),
                io.Float.Input('pose_cfg_scale', default=1.5, min=0.0, max=10.0, step=0.01, tooltip='CFG scale for the pose control, has no effect if main cfg scale is 1.0', optional=True)
            ], outputs=[io.Custom('WANVIDIMAGE_EMBEDS').Output(display_name='image_embeds')],
        )

    @classmethod
    def execute(cls, embeds, pose_images, strength, pose_prefix_image=None, start_percent=0.0, end_percent=1.0, pose_cfg_scale=1.5):
        _preflight_onetoall_pose(pose_images, pose_prefix_image)
        _bound_payload(pose_cfg_scale)
        _bound_payload(end_percent)
        _bound_payload(start_percent)
        _bound_payload(pose_prefix_image)
        _bound_payload(strength)
        _bound_payload(pose_images)
        _bound_payload(embeds)
        _bound_strings([embeds, pose_images, strength, pose_prefix_image, start_percent, end_percent, pose_cfg_scale])
        updated = dict(embeds)
        updated.setdefault('one_to_all_embeds', {})
        pose_images_in = pose_images[..., :3].unsqueeze(0).permute(0, 4, 1, 2, 3) * 2 - 1
        updated['one_to_all_embeds']['pose_images'] = pose_images_in
        if pose_prefix_image is not None:
            updated['one_to_all_embeds']['pose_prefix_image'] = pose_prefix_image.unsqueeze(0).permute(0, 4, 1, 2, 3) * 2 - 1
        else:
            updated['one_to_all_embeds']['pose_prefix_image'] = pose_images_in[:, :, :1]
        updated['one_to_all_embeds']['controlnet_strength'] = strength
        updated['one_to_all_embeds']['controlnet_start_percent'] = start_percent
        updated['one_to_all_embeds']['controlnet_end_percent'] = end_percent
        updated['one_to_all_embeds']['pose_cfg_scale'] = pose_cfg_scale
        return io.NodeOutput(updated)

class WanVideoAddOneToAllExtendEmbeds(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoAddOneToAllExtendEmbeds', display_name='WanVideo Add OneToAll Extend Embeds',
            category='WanVideoWrapper', description='',
            is_experimental=False,
            inputs=[
                io.Custom('WANVIDIMAGE_EMBEDS').Input('embeds'),
                io.Latent.Input('prev_latents', tooltip='Previous latents to be used to continue generation'),
                io.Int.Input('window_size', default=81, min=1, max=256, step=1, tooltip='Number of new frames to generate'),
                io.Int.Input('overlap', default=5, min=0, max=64, step=1, tooltip='Number of overlapping frames between previous and new frames'),
                io.Int.Input('frames_processed', default=0, min=0, max=10000, step=1, tooltip='Number of frames already processed in the video'),
                io.Combo.Input('if_not_enough_frames', options=['pad_with_last', 'error'], default='pad_with_last', tooltip='What to do if there are not enough frames in pose_images for the window'),
                io.Image.Input('pose_images', tooltip='Pose images for the entire video', optional=True)
            ], outputs=[io.Custom('WANVIDIMAGE_EMBEDS').Output(display_name='image_embeds'), io.Image.Output(display_name='pose_slice')],
        )

    @classmethod
    def execute(cls, embeds, prev_latents, if_not_enough_frames, window_size=81, overlap=5, frames_processed=0, pose_images=None):
        _preflight_onetoall_extend(pose_images, window_size, overlap, frames_processed, if_not_enough_frames)
        _bound_payload(pose_images)
        _bound_payload(frames_processed)
        _bound_payload(overlap)
        _bound_payload(window_size)
        _bound_payload(if_not_enough_frames)
        _bound_payload(prev_latents)
        _bound_payload(embeds)
        _bound_strings([embeds, prev_latents, if_not_enough_frames, window_size, overlap, frames_processed, pose_images])
        updated = dict(embeds)
        updated.setdefault('one_to_all_embeds', {})
        updated['one_to_all_embeds']['prev_latents'] = prev_latents['samples'][0]
        if pose_images is not None:
            pose_images_in = pose_images.clone()[..., :3]
            start = max(0, frames_processed - overlap)
            end = start + window_size
            log.info(f'Extracting pose images from {start} to {end}')
            if start >= pose_images_in.shape[0]:
                raise ValueError(f'start index {start} exceeds pose images length {pose_images_in.shape[0]}')
            if end > pose_images_in.shape[0]:
                if if_not_enough_frames == 'pad_with_last':
                    padding_needed = end - pose_images_in.shape[0]
                    pose_images_in = torch.cat([pose_images_in, pose_images_in[-1:].repeat(padding_needed, 1, 1, 1)], dim=0)
                    log.info(f'Not enough frames, padding with {padding_needed} frames to reach {end} total frames')
                else:
                    raise ValueError(f'end index {end} exceeds pose images length {pose_images.shape[0]}')
            pose_slice = pose_images_in[start:end]
        else:
            pose_slice = torch.zeros((1, 64, 64, 3))
        return io.NodeOutput(updated, pose_slice)

NODE_CLASS_MAPPINGS = {
    'WanVideoApplyNAG': WanVideoApplyNAG,
    'WanVideoContextOptions': WanVideoContextOptions,
    'WanVideoAddStandInLatent': WanVideoAddStandInLatent,
    'WanVideoAddExtraLatent': WanVideoAddExtraLatent,
    'WanVideoAddLucyEditLatents': WanVideoAddLucyEditLatents,
    'WanVideoMiniMaxRemoverEmbeds': WanVideoMiniMaxRemoverEmbeds,
    'WanVideoControlEmbeds': WanVideoControlEmbeds,
    'WanVideoAddControlEmbeds': WanVideoAddControlEmbeds,
    'WanVideoAddPusaNoise': WanVideoAddPusaNoise,
    'WanVideoEmptyEmbeds': WanVideoEmptyEmbeds,
    'WanVideoUniLumosEmbeds': WanVideoUniLumosEmbeds,
    'WanVideoPhantomEmbeds': WanVideoPhantomEmbeds,
    'WanVideoRealisDanceLatents': WanVideoRealisDanceLatents,
    'WanVideoAddMTVMotion': WanVideoAddMTVMotion,
    'WanVideoSVIProEmbeds': WanVideoSVIProEmbeds,
    'WanVideoAddTTMLatents': WanVideoAddTTMLatents,
    'ExtractStartFramesForContinuations': ExtractStartFramesForContinuations,
    'WanVideoLatentReScale': WanVideoLatentReScale,
    'WanVideoPassImagesFromSamples': WanVideoPassImagesFromSamples,
    'WanVideoPreviewEmbeds': WanVideoPreviewEmbeds,
    'WanVideoCombineEmbeds': WanVideoCombineEmbeds,
    'WanVideoAddOviAudioToLatents': WanVideoAddOviAudioToLatents,
    'WanVideoEmptyMMAudioLatents': WanVideoEmptyMMAudioLatents,
    'WanVideoOviCFG': WanVideoOviCFG,
    'WanVideoAddSteadyDancerEmbeds': WanVideoAddSteadyDancerEmbeds,
    'WanVideoAddFlashVSRInput': WanVideoAddFlashVSRInput,
    'WanVideoAddS2VEmbeds': WanVideoAddS2VEmbeds,
    'WanVideoAddOneToAllPoseEmbeds': WanVideoAddOneToAllPoseEmbeds,
    'WanVideoAddOneToAllExtendEmbeds': WanVideoAddOneToAllExtendEmbeds,
}
