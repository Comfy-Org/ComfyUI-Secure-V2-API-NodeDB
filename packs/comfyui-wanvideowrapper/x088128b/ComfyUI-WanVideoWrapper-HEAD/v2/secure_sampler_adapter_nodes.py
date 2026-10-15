"""Original argument adapters for JACK's single shared sampler.

These staged adapters introduce no sampler, scheduler or model lifecycle.
Full qualification follows the shared producer/sampler execution domain.
"""
from comfy_api.latest import io
from .secure_sampler_settings_nodes import SAMPLER_DEFAULTS
from .secure_tensor_nodes import _bound_payload


class WanVideoSamplerFromSettings(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'assets')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoSamplerFromSettings',
            display_name='WanVideo Sampler From Settings',category='WanVideoWrapper',
            description='Utility node with no other functionality than to look cleaner, useful for the live preview as the main sampler node has become a messy monster',
            inputs=[io.Custom('SAMPLER_ARGS').Input('sampler_inputs')],
            outputs=[io.Latent.Output(display_name='samples'),io.Latent.Output(display_name='denoised_samples')])

    @classmethod
    async def execute(cls, sampler_inputs):
        from .wan_workflow_sampler_nodes import WanVideoSampler
        _bound_payload(sampler_inputs)
        return await WanVideoSampler.execute(**sampler_inputs)


class WanVideoSamplerv2(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'assets')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoSamplerv2',display_name='WanVideo Sampler v2',
            category='WanVideoWrapper',inputs=[
                io.Custom('WANVIDEOMODEL').Input('model'),
                io.Custom('WANVIDIMAGE_EMBEDS').Input('image_embeds'),
                io.Float.Input('cfg',default=6.0,min=0.0,max=30.0,step=0.01),
                io.Int.Input('seed',default=0,min=0,max=0xffffffffffffffff),
                io.Boolean.Input('force_offload',default=True,
                    tooltip='Moves the model to the offload device after sampling'),
                io.Custom('WANVIDEOSCHEDULER').Input('scheduler'),
                io.Custom('WANVIDEOTEXTEMBEDS').Input('text_embeds',optional=True),
                io.Latent.Input('samples',optional=True,tooltip='init Latents to use for video2video process'),
                io.Boolean.Input('add_noise_to_samples',optional=True,default=False,
                    tooltip='Add noise to the samples before sampling, needed for video2video sampling when starting from clean video'),
                io.Custom('WANVIDSAMPLEREXTRAARGS').Input('extra_args',optional=True),
            ],outputs=[io.Latent.Output(display_name='samples'),io.Latent.Output(display_name='denoised_samples')])

    @classmethod
    async def execute(cls, *args, extra_args=None, **kwargs):
        from .wan_workflow_sampler_nodes import WanVideoSampler
        # Native ignores positional and unknown keyword values. Missing
        # required inputs become None; explicit None overrides defaults.
        values = {name:kwargs.get(name,default) for name,default in SAMPLER_DEFAULTS}
        if extra_args is not None:
            values.update(extra_args)
        else:
            values['rope_function'] = 'comfy'
        _bound_payload(values)
        return await WanVideoSampler.execute(**values)


NODE_CLASS_MAPPINGS = {'WanVideoSamplerFromSettings':WanVideoSamplerFromSettings,
                       'WanVideoSamplerv2':WanVideoSamplerv2}
