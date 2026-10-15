"""CPU noise math reused by the bounded DrawGaussianNoiseOnImage candidate.

GPU/device policy and full release support remain pending. The wrapper's actual
guest/outer CPU dispatch is tested separately, not full node conversion.
"""
import torch
import torch.nn.functional as F
from .secure_tensor_nodes import _bound_payload, MAX_TENSOR_ELEMENTS, MAX_PAYLOAD_BYTES

def _preflight_gaussian(image,mask):
    _bound_payload(image)
    _bound_payload(mask)
    if isinstance(image,torch.Tensor) and image.ndim==4 and isinstance(mask,torch.Tensor) and mask.ndim==3:
        batch,height,width,channels=image.shape
        mask_batch=mask.shape[0]
        repeats=((batch+mask_batch-1)//mask_batch)*mask_batch if mask_batch and batch>mask_batch else mask_batch
        output=batch*height*width*max(channels,3)
        projected_mask=repeats*height*width
        bytes_total=4*output*image.element_size()+2*projected_mask*mask.element_size()+mask.numel()*mask.element_size()
        if max(output,projected_mask)>MAX_TENSOR_ELEMENTS or bytes_total>MAX_PAYLOAD_BYTES:
            raise ValueError('Wan Gaussian CPU projected work exceeds tensor/64 MiB bounds')

def draw_gaussian_noise_cpu(image, mask, seed=0):
    _preflight_gaussian(image, mask)
    B, H, W, C = image.shape
    BM, HM, WM = mask.shape
    processing_device = torch.device('cpu')
    in_masks = mask.clone().to(processing_device)
    in_images = image.clone().to(processing_device)
    if HM != H or WM != W:
        in_masks = F.interpolate(mask.unsqueeze(1), size=(H, W), mode='nearest-exact').squeeze(1)
    if B > BM:
        in_masks = in_masks.repeat((B + BM - 1) // BM, 1, 1)[:B]
    elif BM > B:
        in_masks = in_masks[:B]
    output_images = []
    generator = torch.Generator(device=processing_device).manual_seed(seed)
    for i in range(B):
        curr_mask = in_masks[i]
        img_idx = min(i, B - 1)
        curr_image = in_images[img_idx]
        mask_expanded = curr_mask.unsqueeze(-1).expand(-1, -1, 3)
        subject_mask = mask_expanded > 0.5
        noise = torch.zeros_like(curr_image)
        for c in range(C):
            channel = curr_image[:, :, c]
            channel_mask = subject_mask[:, :, c]
            if channel_mask.sum() > 0:
                subject_pixels = channel[channel_mask]
                mean = subject_pixels.mean()
                std = subject_pixels.std()
                noise[:, :, c] = torch.normal(mean=mean.item(), std=std.item(), size=(H, W), generator=generator, device=processing_device)
        noise = torch.clamp(noise, 0.0, 1.0)
        masked_image = curr_image * mask_expanded + noise * (1 - mask_expanded)
        output_images.append(masked_image)
    if not output_images:
        return (torch.zeros((0, H, W, 3), dtype=image.dtype),)
    out_rgb = torch.stack(output_images, dim=0).cpu()
    return (out_rgb,)
