"""Exact pinned native Reinhard color math for the owned long-audio loop."""
import torch

def match_and_blend_colors(
    source_chunk: torch.Tensor,  # (C, T, H, W), range [-1, 1]
    reference_image: torch.Tensor,  # (C, 1, H, W), range [-1, 1]
    strength: float,
) -> torch.Tensor:
    import kornia
    if strength == 0.0:
        return source_chunk
    source_chunk = source_chunk.unsqueeze(0)  # (1, C, T, H, W)

    # shapes
    B, C, T, H, W = source_chunk.shape
    input_dtype = source_chunk.dtype

    # [-1,1] -> [0,1]
    src_01 = (source_chunk + 1.0) * 0.5
    ref_01 = (reference_image + 1.0) * 0.5

    src32 = src_01.to(torch.float32)
    ref32 = ref_01.to(torch.float32)

    # (B, C, T, H, W) -> (B*T, C, H, W)
    src_bt = src32.permute(0, 2, 1, 3, 4).contiguous().view(B * T, C, H, W)
    ref_bchw = ref32[:, :, 0, :, :].contiguous()

    # RGB->Lab
    src_lab = kornia.color.rgb_to_lab(src_bt)  # (B*T, C, H, W)
    ref_lab = kornia.color.rgb_to_lab(ref_bchw)  # (B,   C, H, W)

    src_lab_flat = src_lab.view(B * T, C, -1)  # (B*T, C, HW)
    ref_lab_flat = ref_lab.view(B, C, -1)  # (B,   C, HW)
    src_std, src_mean = torch.std_mean(src_lab_flat, dim=-1, keepdim=True, unbiased=False)
    ref_std, ref_mean = torch.std_mean(ref_lab_flat, dim=-1, keepdim=True, unbiased=False)
    src_std = src_std.clamp_min_(1e-6)

    ref_mean_bt = ref_mean.repeat_interleave(T, dim=0)  # (B*T, C, 1)
    ref_std_bt = ref_std.repeat_interleave(T, dim=0)  # (B*T, C, 1)

    corrected_lab_flat = (src_lab_flat - src_mean) * (ref_std_bt / src_std) + ref_mean_bt
    corrected_lab = corrected_lab_flat.view(B * T, C, H, W)

    # Lab->RGB
    corrected_rgb_01 = kornia.color.lab_to_rgb(corrected_lab)  # (B*T, C, H, W)

    blended_rgb_01 = (1.0 - strength) * src_bt + strength * corrected_rgb_01

    # (B, C, T, H, W)
    blended_rgb_01 = blended_rgb_01.view(B, T, C, H, W).permute(0, 2, 1, 3, 4).contiguous()

    # [0,1] -> [-1,1]
    return (blended_rgb_01 * 2.0 - 1.0)[0].to(dtype=input_dtype)
