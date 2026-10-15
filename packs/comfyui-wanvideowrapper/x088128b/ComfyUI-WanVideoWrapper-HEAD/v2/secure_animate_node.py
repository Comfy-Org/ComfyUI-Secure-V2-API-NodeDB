"""Wan Animate wrapper over the original algorithm and digest-bound VAE."""
import torch
from comfy_api.latest import io
from .secure_tensor_nodes import _bound_payload
from .secure_full_vae_nodes import rebuild_full_vae
from .secure_full_vae_encode import _image
from .secure_animate_algorithm import animate_embeds


def animate_boundary(width, height, num_frames, frame_window_size, images, mask, clip_embeds):
    _bound_payload((images, mask, clip_embeds))
    if any(type(value) is not int for value in (width, height, num_frames, frame_window_size)):
        raise ValueError('Wan Animate requires integer output and window dimensions')
    if (not 64 <= width <= 512 or not 64 <= height <= 512
            or not 1 <= num_frames <= 64 or not 1 <= frame_window_size <= 10000):
        raise ValueError('Wan Animate exceeds the current bounded CPU dimensions')
    for value in images:
        if value is not None:
            _image(value)
    if mask is not None and (not isinstance(mask, torch.Tensor) or mask.device.type != 'cpu'
            or mask.layout != torch.strided or mask.ndim != 3
            or not 1 <= mask.shape[0] <= 64 or not all(1 <= value <= 512 for value in mask.shape[1:])):
        raise ValueError('Wan Animate requires bounded dense CPU THW masks')
    refs, pose, face, background, start = images
    normalized_frames = ((num_frames-1)//4)*4+1
    num_refs = 0 if refs is None else refs.shape[0]
    looping = normalized_frames > frame_window_size or start is not None
    # Bound actual projected resize/padding storage before model construction.
    count = sum(0 if value is None else value.shape[0] for value in (refs,pose,background,start))
    if not looping and background is None:
        count += normalized_frames+3*num_refs
    pixel_work = count*(width//16*16)*(height//16*16)*3*4*3
    if face is not None:
        pixel_work += face.shape[0]*512*512*3*4*3
    if pixel_work > 64*1024*1024:
        raise ValueError('Wan Animate projected image work exceeds 64 MiB')


class WanVideoAnimateEmbeds(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'assets', 'models.download')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoAnimateEmbeds', display_name='WanVideo Animate Embeds', category='WanVideoWrapper',
            inputs=[io.Custom('WANVAE').Input('vae'),
                io.Int.Input('width', default=832, min=64, max=8096, step=8, tooltip='Width of the image to encode'),
                io.Int.Input('height', default=480, min=64, max=8096, step=8, tooltip='Height of the image to encode'),
                io.Int.Input('num_frames', default=81, min=1, max=10000, step=4, tooltip='Number of frames to encode'),
                io.Boolean.Input('force_offload', default=True),
                io.Int.Input('frame_window_size', default=77, min=1, max=10000, step=1, tooltip='Number of frames to use for temporal attention window'),
                io.Combo.Input('colormatch', options=['disabled', 'mkl', 'hm', 'reinhard', 'mvgd', 'hm-mvgd-hm', 'hm-mkl-hm'], default='disabled', tooltip='Color matching method to use between the windows'),
                io.Float.Input('pose_strength', default=1.0, min=0.0, max=10.0, step=0.001, tooltip='Additional multiplier for the pose'),
                io.Float.Input('face_strength', default=1.0, min=0.0, max=10.0, step=0.001, tooltip='Additional multiplier for the face'),
                io.Custom('WANVIDIMAGE_CLIPEMBEDS').Input('clip_embeds', tooltip='Clip vision encoded image', optional=True),
                io.Image.Input('ref_images', tooltip='Image to encode', optional=True),
                io.Image.Input('pose_images', tooltip='end frame', optional=True),
                io.Image.Input('face_images', tooltip='end frame', optional=True),
                io.Image.Input('bg_images', tooltip='background images', optional=True),
                io.Mask.Input('mask', tooltip='mask', optional=True),
                io.Image.Input('start_ref_image', tooltip='start ref image', optional=True),
                io.Boolean.Input('tiled_vae', default=False, tooltip='Use tiled VAE encoding for reduced memory use', optional=True)],
            outputs=[io.Custom('WANVIDIMAGE_EMBEDS').Output(display_name='image_embeds')])

    @classmethod
    async def execute(cls, vae, width, height, num_frames, force_offload, frame_window_size, colormatch, pose_strength, face_strength,
            ref_images=None, pose_images=None, face_images=None, clip_embeds=None, tiled_vae=False, bg_images=None, mask=None, start_ref_image=None):
        animate_boundary(width, height, num_frames, frame_window_size,
            (ref_images, pose_images, face_images, bg_images, start_ref_image), mask, clip_embeds)
        model, recipe = await rebuild_full_vae(vae)
        with torch.inference_mode():
            result = animate_embeds(model, width, height, num_frames, force_offload, frame_window_size,
                colormatch, pose_strength, face_strength, ref_images, pose_images, face_images,
                clip_embeds, tiled_vae, bg_images, mask, start_ref_image)
        # Original downstream metadata carries this exact VAE. Across guest
        # boundaries its already validated immutable recipe preserves identity.
        result['vae'] = recipe
        _bound_payload(result)
        return io.NodeOutput(result)


NODE_CLASS_MAPPINGS = {'WanVideoAnimateEmbeds': WanVideoAnimateEmbeds}
