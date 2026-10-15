"""Owned math utility imports; no Core or host model interfaces."""
import torch
import logging
log = logging.getLogger(__name__)

def get_module_memory_mb(module):
    memory = 0
    for param in module.parameters():
        if param.data is not None:
            memory += param.nelement() * param.element_size()
    return memory / (1024 * 1024)

import math
import gc
import torch.fft as fft
from .. import wan_workflow_cpu as mm
from .._wan_full_vae_runtime import print_memory
from .custom_linear import remove_lora_from_module
from .gguf.gguf_utils import GGUFParameter
from .optional_executors import apply_lora
device = offload_device = torch.device('cpu')

class MetaParameter(torch.nn.Parameter):
    def __new__(cls, dtype, quant_type=None):
        data = torch.empty(0, dtype=dtype)
        self = torch.nn.Parameter(data, requires_grad=False)
        self.quant_type = quant_type
        return self

def offload_transformer(transformer, remove_lora=True):
    transformer.teacache_state.clear_all()
    transformer.magcache_state.clear_all()
    transformer.easycache_state.clear_all()

    if transformer.patched_linear:
        for name, param in transformer.named_parameters():
            if "loras" in name or "controlnet" in name:
                continue
            module = transformer
            subnames = name.split('.')
            for subname in subnames[:-1]:
                module = getattr(module, subname)
            attr_name = subnames[-1]
            if param.data.is_floating_point():
                meta_param = torch.nn.Parameter(torch.empty_like(param.data, device='meta'), requires_grad=False)
                setattr(module, attr_name, meta_param)
            elif isinstance(param.data, GGUFParameter):
                quant_type = getattr(param, 'quant_type', None)
                setattr(module, attr_name, MetaParameter(param.data.dtype, quant_type))
            else:
                pass
        if remove_lora:
            remove_lora_from_module(transformer)
    else:
        transformer.to(offload_device)

    for block in transformer.blocks:
        block.kv_cache = None
        if transformer.audio_model is not None and hasattr(block, 'audio_block'):
            block.audio_block = None

    mm.soft_empty_cache()
    gc.collect()

def init_blockswap(transformer, block_swap_args, model):
    if not transformer.patched_linear:
        if block_swap_args is not None:
            for name, param in transformer.named_parameters():
                if "block" not in name or "control_adapter" in name or "face" in name:
                    param.data = param.data.to(device)
                elif block_swap_args["offload_txt_emb"] and "txt_emb" in name:
                    param.data = param.data.to(offload_device)
                elif block_swap_args["offload_img_emb"] and "img_emb" in name:
                    param.data = param.data.to(offload_device)

            transformer.block_swap(
                block_swap_args["blocks_to_swap"] - 1 ,
                block_swap_args["offload_txt_emb"],
                block_swap_args["offload_img_emb"],
                vace_blocks_to_swap = block_swap_args.get("vace_blocks_to_swap", None),
            )
        elif model["auto_cpu_offload"]:
            for module in transformer.modules():
                if hasattr(module, "offload"):
                    module.offload()
                if hasattr(module, "onload"):
                    module.onload()
            for block in transformer.blocks:
                block.modulation = torch.nn.Parameter(block.modulation.to(device))
            transformer.head.modulation = torch.nn.Parameter(transformer.head.modulation.to(device))
        else:
            transformer.to(device)

def get_module_memory_mb_per_device(module):
    memory_per_device = {}
    memory = 0
    for param in module.parameters():
        if param.data is not None:
            device = str(param.device)
            memory += param.nelement() * param.element_size()
            memory_per_device[device] = memory_per_device.get(device, 0) + memory

    memory_per_device = {dev: mem / (1024 * 1024) for dev, mem in memory_per_device.items()}
    return memory_per_device

def fourier_filter(x, scale_low=1.0, scale_high=1.5, freq_cutoff=20):
    """
    Apply frequency-dependent scaling to an image tensor using Fourier transforms.

    Parameters:
        x:           Input tensor of shape (B, C, H, W)
        scale_low:   Scaling factor for low-frequency components (default: 1.0)
        scale_high:  Scaling factor for high-frequency components (default: 1.5)
        freq_cutoff: Number of frequency indices around center to consider as low-frequency (default: 20)

    Returns:
        x_filtered: Filtered version of x in spatial domain with frequency-specific scaling applied.
    """
    # Preserve input dtype and device
    dtype, device = x.dtype, x.device

    # Convert to float32 for FFT computations
    x = x.to(torch.float32)

    # 1) Apply FFT and shift low frequencies to center
    x_freq = fft.fftn(x, dim=(-2, -1))
    x_freq = fft.fftshift(x_freq, dim=(-2, -1))

    # 2) Create a mask to scale frequencies differently
    C, B, H, W = x_freq.shape
    crow, ccol = H // 2, W // 2

    # Initialize mask with high-frequency scaling factor
    mask = torch.ones((C, B, H, W), device=device) * scale_high

    # Apply low-frequency scaling factor to center region
    mask[
        ...,
        crow - freq_cutoff : crow + freq_cutoff,
        ccol - freq_cutoff : ccol + freq_cutoff,
    ] = scale_low

    # 3) Apply frequency-specific scaling
    x_freq = x_freq * mask

    # 4) Convert back to spatial domain
    x_freq = fft.ifftshift(x_freq, dim=(-2, -1))
    x_filtered = fft.ifftn(x_freq, dim=(-2, -1)).real

    # 5) Restore original dtype
    x_filtered = x_filtered.to(dtype)

    return x_filtered

def optimized_scale(positive_flat, negative_flat):

    # Calculate dot production
    dot_product = torch.sum(positive_flat * negative_flat, dim=1, keepdim=True)

    # Squared norm of uncondition
    squared_norm = torch.sum(negative_flat ** 2, dim=1, keepdim=True) + 1e-8

    # st_star = v_cond^T * v_uncond / ||v_uncond||^2
    st_star = dot_product / squared_norm

    return st_star

def find_closest_valid_dim(fixed_dim, var_dim, block_size):
    for delta in range(1, 17):
        for sign in [-1, 1]:
            candidate = var_dim + sign * delta
            if candidate > 0 and ((fixed_dim * candidate) // 4) % block_size == 0:
                return candidate
    return var_dim

def setup_radial_attention(transformer, transformer_options, latent, seq_len, latent_video_length, context_options=None):
    if context_options is not None:
        context_frames =  (context_options["context_frames"] - 1) // 4 + 1

    dense_timesteps = transformer_options.get("dense_timesteps", 1)
    dense_blocks = transformer_options.get("dense_blocks", 1)
    dense_vace_blocks = transformer_options.get("dense_vace_blocks", 1)
    decay_factor = transformer_options.get("decay_factor", 0.2)
    dense_attention_mode = transformer_options.get("dense_attention_mode", "sageattn")
    block_size = transformer_options.get("block_size", 128)

    # Calculate closest valid latent sizes
    if latent.shape[2] % (block_size/8) != 0 or latent.shape[3] % (block_size/8) != 0:
        block_div = int(block_size // 8)
        closest_h = round(latent.shape[2] / block_div) * block_div
        closest_w = round(latent.shape[3] / block_div) * block_div
        raise Exception(
            f"Radial attention mode only supports image size divisible by block size. "
            f"Got {latent.shape[3] * 8}x{latent.shape[2] * 8} with block size {block_size}.\n"
            f"Closest valid sizes: {closest_w * 8}x{closest_h * 8} (width x height in pixels)."
        )
    tokens_per_frame = (latent.shape[2] * latent.shape[3]) // 4
    if tokens_per_frame % block_size != 0:
        closest_latent_h = find_closest_valid_dim(latent.shape[3], latent.shape[2], block_size)
        closest_latent_w = find_closest_valid_dim(latent.shape[2], latent.shape[3], block_size)
        raise Exception(
            f"Radial attention mode requires tokens per frame ((latent_h * latent_w) // 4) to be divisible by block size ({block_size}).\n"
            f"Current size in latent space:{latent.shape[3]}x{latent.shape[2]}, pixel space: {latent.shape[3]*8}x{latent.shape[2]*8} tokens_per_frame={tokens_per_frame}.\n"
            f"Try adjusting to one of these latent sizes (in pixels):\n"
            f"  Height: {latent.shape[2]*8} -> {closest_latent_h * 8}\n"
            f"  Width: {latent.shape[3]*8} -> {closest_latent_w * 8}\n"
            f"Or choose another resolution so that (latent_h * latent_w) // 4 is divisible by {block_size}."
        )

    from .wanvideo.radial_attention.attn_mask import MaskMap
    for i, block in enumerate(transformer.blocks):
        block.self_attn.mask_map = block.dense_attention_mode = block.dense_timesteps = block.self_attn.decay_factor = None
        if isinstance(dense_blocks, list):
            block.dense_block = i in dense_blocks
        else:
            block.dense_block = i < dense_blocks
        block.self_attn.mask_map = MaskMap(video_token_num=seq_len, num_frame=latent_video_length if context_options is None else context_frames, block_size=block_size)
        block.dense_attention_mode = dense_attention_mode
        block.dense_timesteps = dense_timesteps
        block.self_attn.decay_factor = decay_factor
    if transformer.vace_layers is not None:
        for i, block in enumerate(transformer.vace_blocks):
            block.self_attn.mask_map = block.dense_attention_mode = block.dense_timesteps = block.self_attn.decay_factor = None
            if isinstance(dense_vace_blocks, list):
                block.dense_block = i in dense_vace_blocks
            else:
                block.dense_block = i < dense_vace_blocks
            block.self_attn.mask_map = MaskMap(video_token_num=seq_len, num_frame=latent_video_length if context_options is None else context_frames, block_size=block_size)
            block.dense_attention_mode = dense_attention_mode
            block.dense_timesteps = dense_timesteps
            block.self_attn.decay_factor = decay_factor

    log.info(f"Radial attention mode enabled.")
    log.info(f"dense_attention_mode: {dense_attention_mode}, dense_timesteps: {dense_timesteps}, decay_factor: {decay_factor}")
    log.info(f"dense_blocks: {[i for i, block in enumerate(transformer.blocks) if getattr(block, 'dense_block', False)]})")

def list_to_device(tensor_list, device, dtype=None):
    """
    Move all tensors in a list to the specified device and optionally cast to dtype.
    """
    return [t.to(device, dtype=dtype) if dtype is not None else t.to(device) for t in tensor_list]

def dict_to_device(tensor_dict, device, dtype=None):
    """
    Move all tensors (and tensor lists) in a dict to the specified device and optionally cast to dtype.
    Supports values that are tensors or lists of tensors.
    """
    result = {}
    for k, v in tensor_dict.items():
        if isinstance(v, torch.Tensor):
            result[k] = v.to(device, dtype=dtype) if dtype is not None else v.to(device)
        elif isinstance(v, list) and all(isinstance(t, torch.Tensor) for t in v):
            result[k] = list_to_device(v, device, dtype)
        else:
            result[k] = v
    return result

def compile_model(transformer, compile_args=None):
    if compile_args is None:
        return transformer
    if hasattr(torch, '_dynamo') and hasattr(torch._dynamo, 'config'):
        torch._dynamo.config.cache_size_limit = compile_args["dynamo_cache_size_limit"]
        torch._dynamo.config.force_parameter_static_shapes = compile_args["force_parameter_static_shapes"]
        try:
            if hasattr(torch._dynamo.config, 'allow_unspec_int_on_nn_module'):
                torch._dynamo.config.allow_unspec_int_on_nn_module = True
        except Exception as e:
            log.warning(f"Could not set allow_unspec_int_on_nn_module: {e}")
        try:
            torch._dynamo.config.recompile_limit = compile_args["dynamo_recompile_limit"]
        except Exception as e:
            log.warning(f"Could not set recompile_limit: {e}")

    if compile_args["compile_transformer_blocks_only"]:
        for i, block in enumerate(transformer.blocks):
            if hasattr(block, "_orig_mod"):
                block = block._orig_mod
            transformer.blocks[i] = torch.compile(block, fullgraph=compile_args["fullgraph"], dynamic=compile_args["dynamic"], backend=compile_args["backend"], mode=compile_args["mode"])
        if transformer.vace_layers is not None:
            for i, block in enumerate(transformer.vace_blocks):
                if hasattr(block, "_orig_mod"):
                    block = block._orig_mod
                transformer.vace_blocks[i] = torch.compile(block, fullgraph=compile_args["fullgraph"], dynamic=compile_args["dynamic"], backend=compile_args["backend"], mode=compile_args["mode"])
    else:
        transformer = torch.compile(transformer, fullgraph=compile_args["fullgraph"], dynamic=compile_args["dynamic"], backend=compile_args["backend"], mode=compile_args["mode"])
    return transformer

def tangential_projection(pred_cond: torch.Tensor, pred_uncond: torch.Tensor) -> torch.Tensor:
    cond_dtype = pred_cond.dtype
    preds = torch.stack([pred_cond, pred_uncond], dim=1).float()
    orig_shape = preds.shape[2:]
    preds_flat = preds.flatten(2)
    U, S, Vh = torch.linalg.svd(preds_flat, full_matrices=False)
    Vh_modified = Vh.clone()
    Vh_modified[:, 1] = 0
    recon = U @ torch.diag_embed(S) @ Vh_modified
    return recon[:, 1].view(pred_uncond.shape).to(cond_dtype)

def get_raag_guidance(noise_pred_cond, noise_pred_uncond, w_max, alpha=1.0, eps=1e-8):
    delta = noise_pred_cond - noise_pred_uncond
    norm_delta = torch.norm(delta.flatten(1), dim=1, keepdim=True)
    norm_uncond = torch.norm(noise_pred_uncond.flatten(1), dim=1, keepdim=True)
    ratio = norm_delta / (norm_uncond + eps)
    ratio_mean = ratio.mean().item()
    adaptive_w = 1.0 + (w_max - 1.0) * math.exp(-alpha * ratio_mean)
    return adaptive_w

def tensor_pingpong_pad(video, target_len):
    """
    Pads a video tensor along the frame dimension (dim=2) in a ping-pong fashion.
    video: torch.Tensor of shape [B, C, F, H, W]
    target_len: desired number of frames
    Returns: padded tensor of shape [B, C, target_len, H, W]
    """
    in_dims = len(video.shape)
    if in_dims == 4:
        video = video.unsqueeze(0)
    B, C, F, H, W = video.shape
    idx = 0
    flip = False
    indices = []
    while len(indices) < target_len:
        indices.append(idx)
        if flip:
            idx -= 1
        else:
            idx += 1
        if idx == 0 or idx == F - 1:
            flip = not flip
    indices = indices[:target_len]
    padded_video = video[:, :, indices, :, :]
    if in_dims == 4:
        padded_video = padded_video.squeeze(0)
    return padded_video

def temporal_score_rescaling(model_output, sample, timestep, k=1.0, tsr_sigma=0.1):
    t = (timestep / 1000)
    if t == 0.0:
        ratio = k
    else:
        snr_t = (1 - t)**2 / t**2
        ratio = (snr_t * tsr_sigma**2 + 1) / (snr_t * tsr_sigma**2 / k + 1)

    if not t == 1.0:
        model_output = (ratio * ((1-t) * model_output + sample) - sample) / (1 - t)
    return model_output
