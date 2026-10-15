"""Exact V2 schema factories; node registration awaits complete owned execution."""
from comfy_api.latest import io


def set_loras_schema():
    return io.Schema(
        node_id='WanVideoSetLoRAs', display_name='WanVideo Set LoRAs',
        category='WanVideoWrapper', is_experimental=True,
        description='Sets the LoRA weights to be used directly in linear layers of the model, this does NOT merge LoRAs',
        inputs=[io.Custom('WANVIDEOMODEL').Input('model'),
                io.Custom('WANVIDLORA').Input('lora', optional=True)],
        outputs=[io.Custom('WANVIDEOMODEL').Output(display_name='model')],
    )


def diffusion_forcing_schema():
    return io.Schema(
        node_id='WanVideoDiffusionForcingSampler', category='WanVideoWrapper',
        inputs=[
            io.Custom('WANVIDEOMODEL').Input('model'),
            io.Custom('WANVIDEOTEXTEMBEDS').Input('text_embeds'),
            io.Custom('WANVIDIMAGE_EMBEDS').Input('image_embeds'),
            io.Int.Input('addnoise_condition', default=10, min=0, max=1000,
                tooltip='Improves consistency in long video generation'),
            io.Float.Input('fps', default=24.0, min=1.0, max=120.0, step=0.01),
            io.Int.Input('steps', default=30, min=1),
            io.Float.Input('cfg', default=6.0, min=0.0, max=30.0, step=0.01),
            io.Float.Input('shift', default=8.0, min=0.0, max=1000.0, step=0.01),
            io.Int.Input('seed', default=0, min=0, max=18446744073709551615),
            io.Boolean.Input('force_offload', default=True,
                tooltip='Moves the model to the offload device after sampling'),
            io.Combo.Input('scheduler', options=['unipc', 'unipc/beta', 'euler', 'euler/beta', 'lcm', 'lcm/beta'], default='unipc'),
            io.Latent.Input('samples', optional=True,
                tooltip='init Latents to use for video2video process'),
            io.Latent.Input('prefix_samples', optional=True, tooltip='prefix latents'),
            io.Float.Input('denoise_strength', optional=True, default=1.0, min=0.0, max=1.0, step=0.01),
            io.Custom('CACHEARGS').Input('cache_args', optional=True),
            io.Custom('SLGARGS').Input('slg_args', optional=True),
            io.Combo.Input('rope_function', optional=True, options=['default', 'comfy'], default='comfy',
                tooltip="Comfy's RoPE implementation doesn't use complex numbers and can thus be compiled, that should be a lot faster when using torch.compile"),
            io.Custom('EXPERIMENTALARGS').Input('experimental_args', optional=True),
            io.Custom('UNIANIMATE_POSE').Input('unianimate_poses', optional=True),
        ],
        outputs=[io.Latent.Output(display_name='samples')],
    )
