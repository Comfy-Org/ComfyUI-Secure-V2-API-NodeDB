"""Exact original diffusion-forcing argument binder; no sampler execution.

JACK must publish the owned lifecycle consumer before a production node
can delegate this binding. This module does not register a placeholder.
"""

def forcing_arguments(model, text_embeds, image_embeds, shift, fps, steps, addnoise_condition, cfg, seed, scheduler, force_offload=True, samples=None, prefix_samples=None, denoise_strength=1.0, slg_args=None, rope_function='default', cache_args=None, teacache_args=None, experimental_args=None, unianimate_poses=None):
    return {'model': model, 'text_embeds': text_embeds, 'image_embeds': image_embeds, 'shift': shift, 'fps': fps, 'steps': steps, 'addnoise_condition': addnoise_condition, 'cfg': cfg, 'seed': seed, 'scheduler': scheduler, 'force_offload': force_offload, 'samples': samples, 'prefix_samples': prefix_samples, 'denoise_strength': denoise_strength, 'slg_args': slg_args, 'rope_function': rope_function, 'cache_args': cache_args, 'teacache_args': teacache_args, 'experimental_args': experimental_args, 'unianimate_poses': unianimate_poses}
