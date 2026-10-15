"""Opaque-preserving settings composition; never materializes model refs."""
from comfy_api.latest import io
from .secure_tensor_nodes import _bound_payload, _bound_strings


class WanVideoSamplerExtraArgs(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoSamplerExtraArgs', display_name='WanVideoSampler v2 Extra Args',
            category='WanVideoWrapper', inputs=[
                io.Int.Input('riflex_freq_index', default=0, min=0, max=1000, step=1, optional=True,
                    tooltip='Frequency index for RIFLEX, disabled when 0, default 6. Allows for new frames to be generated after without looping'),
                io.Custom('FETAARGS').Input('feta_args', optional=True),
                io.Custom('WANVIDCONTEXT').Input('context_options', optional=True),
                io.Custom('CACHEARGS').Input('cache_args', optional=True),
                io.Custom('SLGARGS').Input('slg_args', optional=True),
                io.Combo.Input('rope_function', options=['default','comfy','comfy_chunked'], default='comfy', optional=True,
                    tooltip="Comfy's RoPE implementation doesn't use complex numbers and can thus be compiled, that should be a lot faster when using torch.compile. Chunked version has reduced peak VRAM usage when not using torch.compile"),
                io.Custom('LOOPARGS').Input('loop_args', optional=True),
                io.Custom('EXPERIMENTALARGS').Input('experimental_args', optional=True),
                io.Custom('UNIANIMATE_POSE').Input('unianimate_poses', optional=True),
                io.Custom('FANTASYTALKING_EMBEDS').Input('fantasytalking_embeds', optional=True),
                io.Custom('UNI3C_EMBEDS').Input('uni3c_embeds', optional=True),
                io.Custom('MULTITALK_EMBEDS').Input('multitalk_embeds', optional=True)],
            outputs=[io.Custom('WANVIDSAMPLEREXTRAARGS').Output(display_name='extra_args')])

    @classmethod
    def execute(cls, *args, **kwargs):
        # As upstream, positional arguments are unused and only supplied keys
        # are returned. Bounds inspect plain metadata, never resolve refs.
        _bound_strings(kwargs.keys())
        _bound_payload(kwargs)
        return io.NodeOutput(kwargs)


NODE_CLASS_MAPPINGS = {'WanVideoSamplerExtraArgs': WanVideoSamplerExtraArgs}
