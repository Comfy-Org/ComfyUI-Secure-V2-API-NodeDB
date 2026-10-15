"""Cache settings are data, including the requested placement policy.

The native cache_device object is replaced by its original closed UI label.

No host device is discovered or allocated here. The receiving sampler must

resolve this policy in its own admitted model/device context before cache

execution. Native legacy samplers are not activated by this conversion.
"""
from comfy_api.latest import io

class WanVideoTeaCache(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoTeaCache', display_name='WanVideo TeaCache',
            category='WanVideoWrapper', description='\nPatch WanVideo model to use TeaCache. Speeds up inference by caching the output and  \napplying it instead of doing the step.  Best results are achieved by choosing the  \nappropriate coefficients for the model. Early steps should never be skipped, with too  \naggressive values this can happen and the motion suffers. Starting later can help with that too.   \nWhen NOT using coefficients, the threshold value should be  \nabout 10 times smaller than the value used with coefficients.  \n\nOfficial recommended values https://github.com/ali-vilab/TeaCache/tree/main/TeaCache4Wan2.1\n',
            is_experimental=False,
            inputs=[io.Float.Input('rel_l1_thresh', default=0.3, min=0.0, max=1.0, step=0.001, tooltip='Higher values will make TeaCache more aggressive, faster, but may cause artifacts. Good value range for 1.3B: 0.05 - 0.08, for other models 0.15-0.30'), io.Int.Input('start_step', default=1, min=0, max=9999, step=1, tooltip='Start percentage of the steps to apply TeaCache'), io.Int.Input('end_step', default=-1, min=-1, max=9999, step=1, tooltip='End steps to apply TeaCache'), io.Combo.Input('cache_device', options=['main_device', 'offload_device'], default='offload_device', tooltip='Device to cache to'), io.Boolean.Input('use_coefficients', default=True, tooltip='Use calculated coefficients for more accuracy. When enabled therel_l1_thresh should be about 10 times higher than without'), io.Combo.Input('mode', options=['e', 'e0'], default='e', tooltip='Choice between using e (time embeds, default) or e0 (modulated time embeds)', optional=True)],
            outputs=[io.Custom("CACHEARGS").Output(display_name="cache_args")])
    @classmethod
    def execute(cls, rel_l1_thresh, start_step, end_step, cache_device, use_coefficients, mode='e'):
        if cache_device not in ('main_device', 'offload_device'):
            raise ValueError('Wan cache placement must be main_device or offload_device')
        cache_args = {'cache_type': 'TeaCache', 'rel_l1_thresh': rel_l1_thresh, 'start_step': start_step, 'end_step': end_step, 'cache_device': cache_device, 'use_coefficients': use_coefficients, 'mode': mode}
        return io.NodeOutput(cache_args)


class WanVideoMagCache(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoMagCache', display_name='WanVideo MagCache',
            category='WanVideoWrapper', description='MagCache for WanVideoWrapper, source https://github.com/Zehong-Ma/MagCache',
            is_experimental=True,
            inputs=[io.Float.Input('magcache_thresh', default=0.02, min=0.0, max=0.3, step=0.001, tooltip='How strongly to cache the output of diffusion model. This value must be non-negative.'), io.Int.Input('magcache_K', default=4, min=0, max=6, step=1, tooltip='The maxium skip steps of MagCache.'), io.Int.Input('start_step', default=1, min=0, max=9999, step=1, tooltip='Step to start applying MagCache'), io.Int.Input('end_step', default=-1, min=-1, max=9999, step=1, tooltip='Step to end applying MagCache'), io.Combo.Input('cache_device', options=['main_device', 'offload_device'], default='offload_device', tooltip='Device to cache to')],
            outputs=[io.Custom("CACHEARGS").Output(display_name="cache_args")])
    @classmethod
    def execute(cls, magcache_thresh, magcache_K, start_step, end_step, cache_device):
        if cache_device not in ('main_device', 'offload_device'):
            raise ValueError('Wan cache placement must be main_device or offload_device')
        cache_args = {'cache_type': 'MagCache', 'magcache_thresh': magcache_thresh, 'magcache_K': magcache_K, 'start_step': start_step, 'end_step': end_step, 'cache_device': cache_device}
        return io.NodeOutput(cache_args)


class WanVideoEasyCache(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoEasyCache', display_name='WanVideo EasyCache',
            category='WanVideoWrapper', description='EasyCache for WanVideoWrapper, source https://github.com/H-EmbodVis/EasyCache',
            is_experimental=True,
            inputs=[io.Float.Input('easycache_thresh', default=0.015, min=0.0, max=1.0, step=0.001, tooltip='How strongly to cache the output of diffusion model. This value must be non-negative.'), io.Int.Input('start_step', default=10, min=0, max=9999, step=1, tooltip='Step to start applying EasyCache'), io.Int.Input('end_step', default=-1, min=-1, max=9999, step=1, tooltip='Step to end applying EasyCache'), io.Combo.Input('cache_device', options=['main_device', 'offload_device'], default='offload_device', tooltip='Device to cache to')],
            outputs=[io.Custom("CACHEARGS").Output(display_name="cache_args")])
    @classmethod
    def execute(cls, easycache_thresh, start_step, end_step, cache_device):
        if cache_device not in ('main_device', 'offload_device'):
            raise ValueError('Wan cache placement must be main_device or offload_device')
        cache_args = {'cache_type': 'EasyCache', 'easycache_thresh': easycache_thresh, 'start_step': start_step, 'end_step': end_step, 'cache_device': cache_device}
        return io.NodeOutput(cache_args)


NODE_CLASS_MAPPINGS = {'WanVideoTeaCache': WanVideoTeaCache, 'WanVideoMagCache': WanVideoMagCache, 'WanVideoEasyCache': WanVideoEasyCache}
