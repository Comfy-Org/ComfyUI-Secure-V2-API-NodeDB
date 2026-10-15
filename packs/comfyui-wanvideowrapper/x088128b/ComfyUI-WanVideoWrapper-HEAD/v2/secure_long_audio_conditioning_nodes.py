"""Pack-owned MultiTalk/Skyreels window conditioning from pinned 088128b.

These producers preserve the native tensor operations and forward the WANVAE
recipe. They do not load, run, or materialize a model. ``output_path`` names a
logical output subfolder consumed by the sampler's output broker; no host path
or directory access is granted to the pack.
"""
import datetime
import re

import torch
from comfy_api.latest import io
from ._wan_resize import common_upscale
from .secure_tensor_nodes import _bound_payload, MAX_PAYLOAD_BYTES, MAX_TENSOR_ELEMENTS


def _output_namespace(output_path, mode):
    if not output_path:
        return output_path
    if not isinstance(output_path, str):
        raise TypeError('Wan window output namespace must be text')
    if len(output_path.encode('utf-8')) > 512:
        raise ValueError('Wan window output namespace exceeds 512 bytes')
    # The output service already confines subfolders. Validate before carrying
    # one through a graph so no downstream consumer mistakes it for a host path.
    parts = output_path.replace('\\', '/').split('/')
    if (any(part in ('', '.', '..') for part in parts)
            or any(re.search(r'[\x00-\x1f\x7f:]', part) for part in parts)):
        raise ValueError('Wan window output requires a relative output namespace')
    if not isinstance(mode, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', mode):
        raise ValueError('Wan window output mode must be a safe name')
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    return '/'.join(parts + [f'{timestamp}_{mode}_output'])


def _preflight(width, height, start_image, reference_video, clip_embeds):
    _bound_payload((start_image, reference_video, clip_embeds))
    # No model/recipe traversal: the native producer forwards it unchanged.
    # Bound the allocations of actual images, not the whole generated video,
    # which this producer does not allocate.
    total = 0
    for value in (start_image, reference_video):
        if not isinstance(value, torch.Tensor):
            continue
        total += value.numel() * value.element_size()
        if value.ndim != 4 or not isinstance(width, int) or not isinstance(height, int):
            continue  # Native bounded rank/type failure remains in resize.
        if width <= 0 or height <= 0:
            continue  # Preserve Pillow's native invalid-dimension error.
        elements = value.shape[0] * width * height * value.shape[3]
        # Native Lanczos has uint8/Pillow and float32 temporaries, plus two
        # scale/shift temporaries and the final published tensor.
        total += elements * (5 + 4 * value.element_size())
        if elements > MAX_TENSOR_ELEMENTS or total > MAX_PAYLOAD_BYTES:
            raise ValueError('Wan window image preparation exceeds tensor/64 MiB bounds')


_DESCRIPTION = ('Enables Multi/InfiniteTalk long video generation sampling method, the video is created '
                'in windows with overlapping frames. Not compatible or necessary to be used with context '
                'windows and many other features besides Multi/InfiniteTalk.')
_PATH_TOOLTIP = ('Logical output subfolder for each window. Saving windows disables returning the final '
                 'video tensor to save memory; files are published by the output service.')


def _base_inputs(motion_default):
    return [
        io.Custom('WANVAE').Input('vae'),
        io.Int.Input('width', default=832, min=64, max=2048, step=8, tooltip='Width of the generation'),
        io.Int.Input('height', default=480, min=64, max=29048, step=8, tooltip='Height of the generation'),
        io.Int.Input('frame_window_size', default=81, min=1, max=10000, step=4,
                     tooltip='The number of frames to process at once, should be a value the model is generally good at.'),
        io.Int.Input('motion_frame', default=motion_default, min=1, max=10000, step=1,
                     tooltip='Driven frame length used in the long video generation. Basically the overlap length.'),
    ]


def _outputs():
    return [io.Custom('WANVIDIMAGE_EMBEDS').Output(display_name='image_embeds'),
            io.String.Output(display_name='output_path')]


class WanVideoImageToVideoMultiTalk(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoImageToVideoMultiTalk', display_name='WanVideo Long I2V Multi/InfiniteTalk',
            category='WanVideoWrapper', description=_DESCRIPTION,
            inputs=_base_inputs(25) + [
                io.Boolean.Input('force_offload', default=False,
                    tooltip='Whether to force offload the model within the loop for VAE operations, enable if you encounter memory issues.'),
                io.Combo.Input('colormatch', options=['disabled', 'mkl', 'hm', 'reinhard', 'mvgd', 'hm-mvgd-hm', 'hm-mkl-hm'],
                    default='disabled', tooltip='Color matching method to use between the windows'),
                io.Image.Input('start_image', optional=True, tooltip='Images to encode'),
                io.Boolean.Input('tiled_vae', optional=True, default=False, tooltip='Use tiled VAE encoding for reduced memory use'),
                io.Custom('WANVIDIMAGE_CLIPEMBEDS').Input('clip_embeds', optional=True, tooltip='Clip vision encoded image'),
                io.Combo.Input('mode', optional=True, options=['auto', 'multitalk', 'infinitetalk'], default='auto',
                    tooltip='The sampling strategy to use in the long video generation loop, should match the model used'),
                io.String.Input('output_path', optional=True, default='', tooltip=_PATH_TOOLTIP),
            ], outputs=_outputs())

    @classmethod
    def execute(cls, vae, width, height, frame_window_size, motion_frame, force_offload, colormatch,
                start_image=None, tiled_vae=False, clip_embeds=None, mode='multitalk', output_path=''):
        _preflight(width, height, start_image, None, clip_embeds)
        num_frames = ((frame_window_size - 1) // 4) * 4 + 1
        if start_image is not None:
            resized_start_image = common_upscale(start_image.movedim(-1, 1), width, height, 'lanczos', 'disabled').movedim(0, 1)
            resized_start_image = resized_start_image * 2 - 1
            resized_start_image = resized_start_image.unsqueeze(0)
        target_shape = (16, (num_frames - 1) // 4 + 1, height // 8, width // 8)
        output_path = _output_namespace(output_path, mode)
        image_embeds = {
            'multitalk_sampling': True,
            'multitalk_start_image': resized_start_image if start_image is not None else None,
            'frame_window_size': num_frames,
            'motion_frame': motion_frame,
            'target_h': height,
            'target_w': width,
            'tiled_vae': tiled_vae,
            'force_offload': force_offload,
            'vae': vae,
            'target_shape': target_shape,
            'clip_context': clip_embeds.get('clip_embeds', None) if clip_embeds is not None else None,
            'colormatch': colormatch,
            'multitalk_mode': mode,
            'output_path': output_path,
        }
        return io.NodeOutput(image_embeds, output_path)


class WanVideoImageToVideoSkyreelsv3_audio(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoImageToVideoSkyreelsv3_audio', display_name='WanVideo Long SkyReelsV3 A2V',
            category='WanVideoWrapper', description=_DESCRIPTION,
            inputs=_base_inputs(5) + [
                io.Int.Input('drop_frames', default=12, min=0, max=10000, step=1,
                    tooltip='Additional frames to drop when advancing the audio window. Higher values = less overlap = faster generation but potentially less smooth transitions.'),
                io.Boolean.Input('tiled_vae', default=False, tooltip='Use tiled VAE encoding for reduced memory use'),
                io.Boolean.Input('force_offload', default=False,
                    tooltip='Whether to force offload the model within the loop for VAE operations, enable if you encounter memory issues.'),
                io.Combo.Input('colormatch', options=['disabled', 'reinhard_torch', 'mkl', 'hm', 'reinhard', 'mvgd', 'hm-mvgd-hm', 'hm-mkl-hm'],
                    default='disabled', tooltip='Color matching method to use between the windows'),
                io.Image.Input('start_image', optional=True, tooltip='Images to encode'),
                io.Image.Input('reference_video', optional=True,
                    tooltip='Optional: Pre-generated reference video to use for keyframes instead of extracting from first generation. Should be color-matched to source image.'),
                io.Custom('WANVIDIMAGE_CLIPEMBEDS').Input('clip_embeds', optional=True, tooltip='Clip vision encoded image'),
                io.String.Input('output_path', optional=True, default='', tooltip=_PATH_TOOLTIP),
            ], outputs=_outputs())

    @classmethod
    def execute(cls, vae, width, height, frame_window_size, motion_frame, drop_frames, force_offload, colormatch,
                start_image=None, tiled_vae=False, clip_embeds=None, mode='multitalk', output_path='', reference_video=None):
        _preflight(width, height, start_image, reference_video, clip_embeds)
        num_frames = ((frame_window_size - 1) // 4) * 4 + 1
        if start_image is not None:
            resized_start_image = common_upscale(start_image.movedim(-1, 1), width, height, 'lanczos', 'disabled').movedim(0, 1)
            resized_start_image = resized_start_image * 2 - 1
            resized_start_image = resized_start_image.unsqueeze(0)
        target_shape = (16, (num_frames - 1) // 4 + 1, height // 8, width // 8)
        output_path = _output_namespace(output_path, mode)
        processed_reference_video = None
        if reference_video is not None:
            processed_reference_video = common_upscale(reference_video.movedim(-1, 1), width, height, 'lanczos', 'disabled').movedim(0, 1)
            processed_reference_video = processed_reference_video * 2 - 1
        image_embeds = {
            'multitalk_sampling': True,
            'multitalk_start_image': resized_start_image if start_image is not None else None,
            'frame_window_size': num_frames,
            'motion_frame': motion_frame,
            'drop_frames': drop_frames,
            'use_pseudo_frames': True,
            'reference_video': processed_reference_video,
            'target_h': height,
            'target_w': width,
            'tiled_vae': tiled_vae,
            'force_offload': force_offload,
            'vae': vae,
            'target_shape': target_shape,
            'clip_context': clip_embeds.get('clip_embeds', None) if clip_embeds is not None else None,
            'colormatch': colormatch,
            'multitalk_mode': 'skyreelsv3',
            'output_path': output_path,
        }
        return io.NodeOutput(image_embeds, output_path)


NODE_CLASS_MAPPINGS = {
    'WanVideoImageToVideoMultiTalk': WanVideoImageToVideoMultiTalk,
    'WanVideoImageToVideoSkyreelsv3_audio': WanVideoImageToVideoSkyreelsv3_audio,
}
