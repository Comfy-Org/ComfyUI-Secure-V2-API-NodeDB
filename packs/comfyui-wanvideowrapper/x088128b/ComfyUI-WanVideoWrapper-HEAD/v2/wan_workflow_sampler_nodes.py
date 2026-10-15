"""Staged sampler schema retaining the original socket data and method defaults."""
from comfy_api.latest import io, sdk
from .wan_workflow_sampler_runtime import sample_workflow


def _inputs():
    from .wan_workflow_math.nodes_sampler import WanVideoSampler as OriginalMathSampler
    # The complete retained source supplies static schema data; this does not
    # call a V1 loader, access model folders or construct a neural model.
    schema = OriginalMathSampler.INPUT_TYPES()
    result = []
    widget_types = {'INT': io.Int, 'FLOAT': io.Float, 'BOOLEAN': io.Boolean, 'STRING': io.String}
    for group in ('required', 'optional'):
        for name, description in schema.get(group, {}).items():
            kind = description[0]
            settings = dict(description[1]) if len(description) > 1 else {}
            settings['optional'] = group == 'optional'
            if isinstance(kind, list):
                result.append(io.Combo.Input(name, options=kind, **settings))
            elif kind in widget_types:
                result.append(widget_types[kind].Input(name, **settings))
            else:
                result.append(io.Custom(kind).Input(name, **settings))
    return result


class WanVideoSampler(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'assets')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoSampler', display_name='WanVideo Sampler', category='WanVideoWrapper', inputs=_inputs(),
            outputs=[io.Custom('LATENT').Output(display_name='samples'),
                     io.Custom('LATENT').Output(display_name='denoised_samples')])

    @classmethod
    async def execute(cls, model, image_embeds, shift, steps, cfg, seed, scheduler,
                      riflex_freq_index, text_embeds=None, force_offload=True,
                      samples=None, feta_args=None, denoise_strength=1.0,
                      context_options=None, cache_args=None, teacache_args=None,
                      flowedit_args=None, batched_cfg=False, slg_args=None,
                      rope_function='default', loop_args=None, experimental_args=None,
                      sigmas=None, unianimate_poses=None, fantasytalking_embeds=None,
                      uni3c_embeds=None, multitalk_embeds=None, freeinit_args=None,
                      start_step=0, end_step=-1, add_noise_to_samples=False):
        result = await sample_workflow(sdk.current_context(), model, image_embeds,
            shift=shift, steps=steps, cfg=cfg, seed=seed, scheduler=scheduler,
            riflex_freq_index=riflex_freq_index, text_embeds=text_embeds,
            force_offload=force_offload, samples=samples, feta_args=feta_args,
            denoise_strength=denoise_strength, context_options=context_options,
            cache_args=cache_args, teacache_args=teacache_args, flowedit_args=flowedit_args,
            batched_cfg=batched_cfg, slg_args=slg_args, rope_function=rope_function,
            loop_args=loop_args, experimental_args=experimental_args, sigmas=sigmas,
            unianimate_poses=unianimate_poses, fantasytalking_embeds=fantasytalking_embeds,
            uni3c_embeds=uni3c_embeds, multitalk_embeds=multitalk_embeds,
            freeinit_args=freeinit_args, start_step=start_step, end_step=end_step,
            add_noise_to_samples=add_noise_to_samples)
        return io.NodeOutput(*result)


NODE_CLASS_MAPPINGS = {'WanVideoSampler': WanVideoSampler}
