"""Pack-owned VACE frame assembly with bounded public refs and raw compute."""
import torch
from comfy_api.latest import io, sdk
from .secure_tensor_nodes import _bound_payload, MAX_TENSOR_ELEMENTS, MAX_PAYLOAD_BYTES
from ._wan_resize import common_upscale


def _check_projection(elements, bytes_total):
    if elements > MAX_TENSOR_ELEMENTS or bytes_total > MAX_PAYLOAD_BYTES:
        raise ValueError('Wan VACE projected frame/mask output exceeds tensor/64 MiB bounds')


def _preflight_frames(num_frames, start_image, end_image, control_images, inpaint_mask):
    if not isinstance(num_frames, int) or num_frames < 0:
        return  # Leave bounded native malformed-index behavior to the algorithm.
    image = start_image if start_image is not None else end_image
    if image is None:
        image = control_images
    if not isinstance(image, torch.Tensor) or image.ndim != 4:
        return
    _, height, width, channels = image.shape
    frame_elements = num_frames * height * width * (channels if start_image is None and end_image is None else 3)
    mask_elements = num_frames * height * width
    size = max(4, image.element_size())
    _check_projection(max(frame_elements, mask_elements), (frame_elements + mask_elements) * size)
    for extra in (end_image, control_images):
        if isinstance(extra, torch.Tensor) and extra.ndim == 4:
            count = extra.shape[0] * height * width * extra.shape[3]
            _check_projection(count, count * extra.element_size())
    if isinstance(inpaint_mask, torch.Tensor) and inpaint_mask.ndim == 3:
        count = inpaint_mask.shape[0]
        if count:
            repeated = ((num_frames + count - 1) // count) * count
            elements = max(count, repeated) * height * width
            _check_projection(elements, elements * inpaint_mask.element_size())


async def _resize_images(value, width, height):
    return common_upscale(value.movedim(-1, 1), width, height, 'lanczos', 'disabled').movedim(1, -1)


async def _resize_mask(value, width, height):
    # Canonical BHWC single-channel image resize equals the source's BCHW
    # nearest-exact mask path; no interpolation substitution or private ref.
    if value.ndim == 3 and value.shape[0] == 0:
        # Native nearest-exact permits a zero batch, then the source's
        # repeat-factor division fails. The image broker correctly refuses
        # empty IMAGE batches; retain that bounded native mask failure without
        # weakening broker validation or manufacturing a valid mask.
        return value.new_empty((0, height, width))
    return torch.nn.functional.interpolate(value.unsqueeze(1), size=(height, width), mode='nearest-exact').squeeze(1)


class WanVideoVACEStartToEndFrame(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoVACEStartToEndFrame', display_name='WanVideo VACE Start To End Frame',
            category='WanVideoWrapper', description='Helper node to create start/end frame batch and masks for VACE',
            inputs=[io.Int.Input('num_frames', default=81, min=1, max=10000, step=4, tooltip='Number of frames to encode'),
                io.Float.Input('empty_frame_level', default=0.5, min=0.0, max=1.0, step=0.01, tooltip='White level of empty frame to use'),
                io.Image.Input('start_image', optional=True), io.Image.Input('end_image', optional=True),
                io.Image.Input('control_images', optional=True),
                io.Mask.Input('inpaint_mask', optional=True, tooltip='Inpaint mask to use for the empty frames'),
                io.Int.Input('start_index', default=0, min=0, max=10000, step=1, tooltip='Index to start from', optional=True),
                io.Int.Input('end_index', default=-1, min=-10000, max=10000, step=1, tooltip='Index to end at', optional=True)],
            outputs=[io.Image.Output(display_name='images'), io.Mask.Output(display_name='masks')])

    @classmethod
    async def execute(cls, num_frames, empty_frame_level, start_image=None, end_image=None, control_images=None,
            inpaint_mask=None, start_index=0, end_index=-1):
        for value in (start_image, end_image, control_images, inpaint_mask):
            _bound_payload(value)
        _preflight_frames(num_frames, start_image, end_image, control_images, inpaint_mask)
        if start_image is None and end_image is None and control_images is not None:
            if control_images.shape[0] >= num_frames:
                control_images = control_images[:num_frames]
            elif control_images.shape[0] < num_frames:
                padding = torch.ones((num_frames - control_images.shape[0], control_images.shape[1],
                    control_images.shape[2], control_images.shape[3]), device=control_images.device) * empty_frame_level
                control_images = torch.cat([control_images, padding], dim=0)
            images = control_images.cpu().float()
            masks = torch.zeros_like(control_images[:, :, :, 0]).cpu().float()
            return io.NodeOutput(images, masks)
        B, H, W, C = start_image.shape if start_image is not None else end_image.shape
        device = start_image.device if start_image is not None else end_image.device
        if end_index < 0:
            end_index = num_frames + end_index
        out_batch = torch.ones((num_frames, H, W, 3), device=device) * empty_frame_level
        masks = torch.ones((num_frames, H, W), device=device)
        if end_image is not None and (end_image.shape[1] != H or end_image.shape[2] != W):
            end_image = await _resize_images(end_image, W, H)
        if control_images is not None and (control_images.shape[1] != H or control_images.shape[2] != W):
            control_images = await _resize_images(control_images, W, H)
        if start_image is not None:
            frames_to_copy = min(start_image.shape[0], num_frames - start_index)
            if frames_to_copy > 0:
                out_batch[start_index:start_index + frames_to_copy] = start_image[:frames_to_copy]
                masks[start_index:start_index + frames_to_copy] = 0
        if end_image is not None:
            end_start = end_index - end_image.shape[0] + 1
            if end_start < 0:
                end_image = end_image[abs(end_start):]
                end_start = 0
            frames_to_copy = min(end_image.shape[0], num_frames - end_start)
            if frames_to_copy > 0:
                out_batch[end_start:end_start + frames_to_copy] = end_image[:frames_to_copy]
                masks[end_start:end_start + frames_to_copy] = 0
        if control_images is not None:
            empty_frames = masks.sum(dim=(1, 2)) > 0.5 * H * W
            if empty_frames.any():
                control_length = control_images.shape[0]
                for frame_idx in range(num_frames):
                    if empty_frames[frame_idx] and frame_idx < control_length:
                        out_batch[frame_idx] = control_images[frame_idx]
        if inpaint_mask is not None:
            inpaint_mask = (await _resize_mask(inpaint_mask, W, H)).to(device)
            if inpaint_mask.shape[0] > num_frames:
                inpaint_mask = inpaint_mask[:num_frames]
            elif inpaint_mask.shape[0] < num_frames:
                repeat_factor = (num_frames + inpaint_mask.shape[0] - 1) // inpaint_mask.shape[0]
                inpaint_mask = inpaint_mask.repeat(repeat_factor, 1, 1)[:num_frames]
            masks = inpaint_mask * masks
        return io.NodeOutput(out_batch.cpu().float(), masks.cpu().float())


NODE_CLASS_MAPPINGS = {'WanVideoVACEStartToEndFrame': WanVideoVACEStartToEndFrame}
