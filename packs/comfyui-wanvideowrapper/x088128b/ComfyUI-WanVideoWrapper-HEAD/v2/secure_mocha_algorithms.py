"""Unregistered MoCha pack math; no model/device/compile authority.

CPU raw-value fixtures and recording VAE outputs test this stage. MochaEmbeds
remains unregistered and release-pending until managed WANVAE ownership,
residency and physical workload policy are available. No trained inference.
"""
import math
import torch
from .secure_tensor_nodes import _bound_payload, MAX_TENSOR_ELEMENTS, MAX_PAYLOAD_BYTES


def _cpu_values(*values):
    _bound_payload(values)
    for value in values:
        if isinstance(value, torch.Tensor) and (value.device.type != "cpu" or value.layout != torch.strided):
            raise ValueError("Wan MoCha staged math requires dense CPU values")


def _projected(elements, byte_count):
    if elements > MAX_TENSOR_ELEMENTS or byte_count > MAX_PAYLOAD_BYTES:
        raise ValueError("Wan MoCha projected work exceeds tensor/64 MiB bounds")


def prepare_mocha_inputs(input_video, ref1, dtype, ref2=None):
    """Prepare exact BCTHW encoder arguments, without resolving any model."""
    _cpu_values(input_video, ref1, ref2)
    tensors = [x for x in (input_video, ref1, ref2) if isinstance(x, torch.Tensor)]
    size = dtype.itemsize
    _projected(sum(x.numel() for x in tensors),
        sum(x.numel() * (x.element_size() + 4 * size) for x in tensors))
    W = input_video.shape[2]
    H = input_video.shape[1]
    F = input_video.shape[0]
    F = (F - 1) // 4 * 4 + 1
    input_video = input_video.clone()[:F]
    input_video = input_video.clone()[..., :3].to("cpu", dtype).unsqueeze(0).permute(0, 4, 1, 2, 3)
    ref1 = ref1.clone()[..., :3].to("cpu", dtype).unsqueeze(0).permute(0, 4, 1, 2, 3)
    if ref2 is not None:
        ref2 = ref2.clone()[..., :3].to("cpu", dtype).unsqueeze(0).permute(0, 4, 1, 2, 3)
    return {"input_video": input_video * 2.0 - 1.0, "ref1": ref1 * 2.0 - 1.0,
        "ref2": ref2 * 2.0 - 1.0 if ref2 is not None else None,
        "num_frames": F, "height": H, "width": W}


def assemble_mocha_embeds(latents, ref_latents, mask, *, num_frames, height, width,
        upsampling_factor, dtype, ref2_latents=None):
    """Assemble already-encoded values, not a substitute for VAE execution."""
    _cpu_values(latents, ref_latents, ref2_latents, mask)
    lat_h = height // upsampling_factor
    lat_w = width // upsampling_factor
    tensors = [x for x in (latents, ref_latents, ref2_latents, mask) if isinstance(x, torch.Tensor)]
    if isinstance(mask, torch.Tensor) and mask.ndim == 3 and lat_h >= 0 and lat_w >= 0:
        mask_elements = mask.shape[0] * 16 * lat_h * lat_w
        encoded_elements = sum(x.numel() for x in (latents, ref_latents, ref2_latents) if isinstance(x, torch.Tensor))
        encoded_bytes = sum(x.numel() * x.element_size() for x in (latents, ref_latents, ref2_latents) if isinstance(x, torch.Tensor))
        # Repeated mask, thresholds, ref concat and final concat coexist.
        _projected(mask_elements + encoded_elements,
            sum(x.numel() * x.element_size() for x in tensors) + 4 * mask_elements * dtype.itemsize + 2 * encoded_bytes)
    num_refs = 1
    if ref2_latents is not None:
        ref_latents = torch.cat([ref_latents, ref2_latents], dim=2)
        num_refs = 2
    input_latent_mask = torch.nn.functional.interpolate(mask.unsqueeze(1).to(dtype), size=(lat_h, lat_w), mode='nearest').unsqueeze(1)
    input_latent_mask = input_latent_mask.repeat(1, 16, 1, 1, 1).to("cpu", dtype)
    input_latent_mask[input_latent_mask <= 0.5] = 0
    input_latent_mask[input_latent_mask > 0.5] = 1
    input_latent_mask[input_latent_mask == 0] = -1
    mocha_embeds = torch.cat([latents, input_latent_mask, ref_latents], dim=2)
    mocha_embeds = mocha_embeds[0]
    target_shape = (16, (num_frames - 1) // 4 + 1, lat_h, lat_w)
    seq_len = (target_shape[1] * 2 + 1 + num_refs) * (target_shape[2] * target_shape[3] // 4)
    return {"seq_len": seq_len, "mocha_embeds": mocha_embeds, "num_frames": num_frames,
        "target_shape": target_shape, "mocha_num_refs": num_refs}


def _preflight_rope_params(max_seq_len, dim, start):
    if all(isinstance(x, (int, float)) for x in (max_seq_len, dim, start)):
        if not all(math.isfinite(x) for x in (max_seq_len, dim, start)):
            raise ValueError("Wan MoCha frequency dimensions must be finite")
        half = max(0, math.ceil(dim / 2))
        count = max(0, math.ceil(max_seq_len - start))
        # Include the exponent/inverse-frequency vectors even when rows=0.
        _projected(max(count * half, half), count * half * 64 + half * 32)


def _preflight_rope_apply(x, grid_sizes, freqs):
    _cpu_values(x, grid_sizes, freqs)
    tensors = [v for v in (x, grid_sizes, freqs) if isinstance(v, torch.Tensor)]
    if isinstance(x, torch.Tensor) and x.ndim == 4:
        # Complex products + per-batch cat + final stack; bound before math.
        _projected(x.numel(), sum(v.numel() * v.element_size() for v in tensors) + x.numel() * max(x.element_size(), 8) * 12)
    if isinstance(grid_sizes, torch.Tensor) and grid_sizes.ndim == 2 and grid_sizes.shape[1] == 3:
        if grid_sizes.shape[0] > 64:
            raise ValueError("Wan MoCha grid batch exceeds64")
        for row in grid_sizes:
            values = row.tolist()
            if all(isinstance(v, int) and v >= 0 for v in values):
                count = math.prod(values)
                if count > 1000000:
                    raise ValueError("Wan MoCha projected grid exceeds1000000")


def rope_params_mocha(max_seq_len, dim, theta=10000, L_test=25, k=0, start=0):
    _preflight_rope_params(max_seq_len, dim, start)
    assert dim % 2 == 0
    exponents = torch.arange(0, dim, 2, dtype=torch.float64).div(dim)
    inv_theta_pow = 1.0 / torch.pow(theta, exponents)
    
    if k > 0:
        print(f"RifleX: Using {k}th freq")
        inv_theta_pow[k-1] = 0.9 * 2 * torch.pi / L_test
        
    freqs = torch.outer(torch.arange(start, max_seq_len), inv_theta_pow)
    freqs = torch.polar(torch.ones_like(freqs), freqs)
    return freqs

def rope_apply_mocha(x, grid_sizes, freqs):
    _preflight_rope_apply(x, grid_sizes, freqs)
    n, c = x.size(2), x.size(3) // 2

    split_size_1 = c - 2 * (c // 3)
    split_size_2 = c // 3
    split_size_3 = c // 3
    freqs_0, freqs_1, freqs_2 = freqs.split([split_size_1, split_size_2, split_size_3], dim=1)

    batch_size = grid_sizes.size(0)
    outputs = []
    
    for i in range(batch_size):
        f, h, w = grid_sizes[i].tolist()
        seq_len = f * h * w

        x_i = torch.view_as_complex(x[i, :seq_len].reshape(seq_len, n, -1, 2))

        sf = (f - 2) // 2

        freq0_start, freq0_end = 1, 1 + sf
        freq1_start, freq1_end = 1, 1 + h
        freq2_start, freq2_end = 1, 1 + w
        
        repeat_freqs = torch.cat([
            freqs_0[freq0_start:freq0_end].view(sf, 1, 1, -1).expand(sf, h, w, -1),
            freqs_1[freq1_start:freq1_end].view(1, h, 1, -1).expand(sf, h, w, -1),
            freqs_2[freq2_start:freq2_end].view(1, 1, w, -1).expand(sf, h, w, -1)
        ], dim=-1)

        mask_freqs = torch.cat([
            freqs_0[1:2].view(1, 1, 1, -1).expand(1, h, w, -1),
            freqs_1[freq1_start:freq1_end].view(1, h, 1, -1).expand(1, h, w, -1),
            freqs_2[freq2_start:freq2_end].view(1, 1, w, -1).expand(1, h, w, -1)
        ], dim=-1)

        img_freqs = torch.cat([
            freqs_0[0:1].view(1, 1, 1, -1).expand(1, h, w, -1),
            freqs_1[freq1_start:freq1_end].view(1, h, 1, -1).expand(1, h, w, -1),
            freqs_2[freq2_start:freq2_end].view(1, 1, w, -1).expand(1, h, w, -1)
        ], dim=-1)
    
        if f == 2 * sf + 2:
            freqs_i = torch.cat([repeat_freqs, repeat_freqs, mask_freqs, img_freqs], dim=0)
        else:
            bias_freqs = torch.cat([
                freqs_0[0:1].view(1, 1, 1, -1).expand(1, h, w, -1),
                freqs_1[(h+1):(2*h+1)].view(1, h, 1, -1).expand(1, h, w, -1),
                freqs_2[(w+1):(2*w+1)].view(1, 1, w, -1).expand(1, h, w, -1)
            ], dim=-1)
            freqs_i = torch.cat([repeat_freqs, repeat_freqs, mask_freqs, img_freqs, bias_freqs], dim=0)
        
        freqs_i = freqs_i.reshape(f * h * w, 1, -1).to(x.device)
        
        # Apply rotary embedding
        x_i = torch.view_as_real(x_i * freqs_i).flatten(2)
        x_i = torch.cat([x_i, x[i, seq_len:]], dim=0)

        outputs.append(x_i)
    
    return torch.stack(outputs).to(x.dtype)
