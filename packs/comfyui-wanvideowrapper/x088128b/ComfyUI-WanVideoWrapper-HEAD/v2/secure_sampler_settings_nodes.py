"""Pinned sampler argument assembly only; no sampling/model access."""
from comfy_api.latest import io
from .secure_tensor_nodes import _bound_payload

# Same order/defaults as nodes_sampler.WanVideoSampler.process. In particular
# the direct method default is rope_function='default', not widget 'comfy'.
SAMPLER_DEFAULTS = (
    ("model", None),
    ("image_embeds", None),
    ("shift", None),
    ("steps", None),
    ("cfg", None),
    ("seed", None),
    ("scheduler", None),
    ("riflex_freq_index", None),
    ("text_embeds", None),
    ("force_offload", True),
    ("samples", None),
    ("feta_args", None),
    ("denoise_strength", 1.0),
    ("context_options", None),
    ("cache_args", None),
    ("teacache_args", None),
    ("flowedit_args", None),
    ("batched_cfg", False),
    ("slg_args", None),
    ("rope_function", "default"),
    ("loop_args", None),
    ("experimental_args", None),
    ("sigmas", None),
    ("unianimate_poses", None),
    ("fantasytalking_embeds", None),
    ("uni3c_embeds", None),
    ("multitalk_embeds", None),
    ("freeinit_args", None),
    ("start_step", 0),
    ("end_step", -1),
    ("add_noise_to_samples", False),
)


class WanVideoSamplerSettings(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoSamplerSettings', display_name='WanVideo Sampler Settings',
            category='WanVideoWrapper',
            description='Node to output all settings and inputs for the WanVideoSamplerFromSettings -node',
            inputs=[
                io.Custom('WANVIDEOMODEL').Input('model'),
                io.Custom('WANVIDIMAGE_EMBEDS').Input('image_embeds'),
                io.Int.Input('steps', default=30, min=1),
                io.Float.Input('cfg', default=6.0, min=0.0, max=30.0, step=0.01),
                io.Float.Input('shift', default=5.0, min=0.0, max=1000.0, step=0.01),
                io.Int.Input('seed', default=0, min=0, max=18446744073709551615),
                io.Boolean.Input('force_offload', default=True, tooltip='Moves the model to the offload device after sampling'),
                io.Combo.Input('scheduler', options=['unipc', 'unipc/beta', 'dpm++', 'dpm++/beta', 'dpm++_sde', 'dpm++_sde/beta', 'euler', 'euler/beta', 'longcat_distill_euler', 'deis', 'lcm', 'lcm/beta', 'res_multistep', 'er_sde', 'flowmatch_causvid', 'flowmatch_distill', 'flowmatch_pusa', 'multitalk', 'sa_ode_stable', 'rcm', 'vibt_unipc'], default='unipc'),
                io.Int.Input('riflex_freq_index', default=0, min=0, max=1000, step=1, tooltip='Frequency index for RIFLEX, disabled when 0, default 6. Allows for new frames to be generated after without looping'),
                io.Custom('WANVIDEOTEXTEMBEDS').Input('text_embeds', optional=True),
                io.Latent.Input('samples', tooltip='init Latents to use for video2video process', optional=True),
                io.Float.Input('denoise_strength', default=1.0, min=0.0, max=1.0, step=0.01, optional=True),
                io.Custom('FETAARGS').Input('feta_args', optional=True),
                io.Custom('WANVIDCONTEXT').Input('context_options', optional=True),
                io.Custom('CACHEARGS').Input('cache_args', optional=True),
                io.Custom('FLOWEDITARGS').Input('flowedit_args', tooltip='FlowEdit support has been deprecated', optional=True),
                io.Boolean.Input('batched_cfg', default=False, tooltip='Batch cond and uncond for faster sampling, possibly faster on some hardware, uses more memory', optional=True),
                io.Custom('SLGARGS').Input('slg_args', optional=True),
                io.Combo.Input('rope_function', options=['default', 'comfy', 'comfy_chunked'], default='comfy', tooltip="Comfy's RoPE implementation doesn't use complex numbers and can thus be compiled, that should be a lot faster when using torch.compile. Chunked version has reduced peak VRAM usage when not using torch.compile", optional=True),
                io.Custom('LOOPARGS').Input('loop_args', optional=True),
                io.Custom('EXPERIMENTALARGS').Input('experimental_args', optional=True),
                io.Sigmas.Input('sigmas', optional=True),
                io.Custom('UNIANIMATE_POSE').Input('unianimate_poses', optional=True),
                io.Custom('FANTASYTALKING_EMBEDS').Input('fantasytalking_embeds', optional=True),
                io.Custom('UNI3C_EMBEDS').Input('uni3c_embeds', optional=True),
                io.Custom('MULTITALK_EMBEDS').Input('multitalk_embeds', optional=True),
                io.Custom('FREEINITARGS').Input('freeinit_args', optional=True),
                io.Int.Input('start_step', default=0, min=0, max=10000, step=1, tooltip='Start step for the sampling, 0 means full sampling, otherwise samples only from this step', optional=True),
                io.Int.Input('end_step', default=-1, min=-1, max=10000, step=1, tooltip='End step for the sampling, -1 means full sampling, otherwise samples only until this step', optional=True),
                io.Boolean.Input('add_noise_to_samples', default=False, tooltip='Add noise to the samples before sampling, needed for video2video sampling when starting from clean video', optional=True),
            ], outputs=[io.Custom('SAMPLER_ARGS').Output(display_name='sampler_inputs')])

    @classmethod
    def execute(cls, *args, **kwargs):
        # Upstream ignores positional/unknown keyword values, includes missing
        # required keys as None and retains explicit None and ref identities.
        result = {name: kwargs.get(name, default) for name, default in SAMPLER_DEFAULTS}
        _bound_payload(result)
        return io.NodeOutput(result)


NODE_CLASS_MAPPINGS = {'WanVideoSamplerSettings': WanVideoSamplerSettings}
