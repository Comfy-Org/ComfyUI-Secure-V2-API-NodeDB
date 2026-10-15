"""Pinned scientific cache algorithms, staged for actual Wan execution.

Function bodies and call order are exact native source. State classes are
re-exported from the stdlib-only pack module at the existing import location.
This module requires actual provisioned Torch; it is never a tensor facade.
"""
from ..secure_cache_logging import log
from ..secure_cache_states import TeaCacheState, MagCacheState, EasyCacheState
import torch

def set_transformer_cache_method(transformer, timesteps, cache_args=None):      
    transformer.cache_device = cache_args["cache_device"]
    if cache_args["cache_type"] == "TeaCache":
        log.info(f"TeaCache: Using cache device: {transformer.cache_device}")
        transformer.teacache_state.clear_all()
        transformer.enable_teacache = True
        transformer.rel_l1_thresh = cache_args["rel_l1_thresh"]
        transformer.teacache_start_step = cache_args["start_step"]
        transformer.teacache_end_step = len(timesteps)-1 if cache_args["end_step"] == -1 else cache_args["end_step"]
        transformer.teacache_use_coefficients = cache_args["use_coefficients"]
        transformer.teacache_mode = cache_args["mode"]
    elif cache_args["cache_type"] == "MagCache":
        log.info(f"MagCache: Using cache device: {transformer.cache_device}")
        transformer.magcache_state.clear_all()
        transformer.enable_magcache = True
        transformer.magcache_start_step = cache_args["start_step"]
        transformer.magcache_end_step = len(timesteps)-1 if cache_args["end_step"] == -1 else cache_args["end_step"]
        transformer.magcache_thresh = cache_args["magcache_thresh"]
        transformer.magcache_K = cache_args["magcache_K"]
    elif cache_args["cache_type"] == "EasyCache":
        log.info(f"EasyCache: Using cache device: {transformer.cache_device}")
        transformer.easycache_state.clear_all()
        transformer.enable_easycache = True
        transformer.easycache_start_step = cache_args["start_step"]
        transformer.easycache_end_step = len(timesteps)-1 if cache_args["end_step"] == -1 else cache_args["end_step"]
        transformer.easycache_thresh = cache_args["easycache_thresh"]
    return transformer


def relative_l1_distance(last_tensor, current_tensor):
    l1_distance = torch.abs(last_tensor.to(current_tensor.device) - current_tensor).mean()
    norm = torch.abs(last_tensor).mean()
    relative_l1_distance = l1_distance / norm
    return relative_l1_distance.to(torch.float32).to(current_tensor.device)


def cache_report(transformer, cache_args):
    cache_type = cache_args["cache_type"]
    states = (
        transformer.teacache_state.states if cache_type == "TeaCache" else
        transformer.magcache_state.states if cache_type == "MagCache" else
        transformer.easycache_state.states if cache_type == "EasyCache" else
        None
    )
    state_names = {
        0: "conditional",
        1: "unconditional"
    }
    for pred_id, state in states.items():
        name = state_names.get(pred_id, f"prediction_{pred_id}")
        if 'skipped_steps' in state:
            log.info(f"{cache_type} skipped: {len(state['skipped_steps'])} {name} steps: {state['skipped_steps']}")
    transformer.teacache_state.clear_all()
    transformer.magcache_state.clear_all()
    transformer.easycache_state.clear_all()
    del states