"""Standard-root checkpoint adapter; native scanner closure remains pending.

The remote combo depends on the accompanying owned route being admitted.
Its values are standard public asset names, not LoRA Manager cache records.
Extra scanner roots, authored base-model filters and cache-miss parity are
unfinished; this source adapter is not a whole-node certificate.
"""
from comfy_api.latest import io, sdk


class CheckpointLoader(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('models',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Checkpoint Loader (LoraManager)',
            category='Lora Manager/loaders',
            inputs=[
                io.Combo.Input('ckpt_name', options=[],
                    tooltip='The name of the checkpoint (model) to load. Use '
                            'control_after_generate to pick a random model on every run.',
                    control_after_generate=io.ControlAfterGenerate.fixed,
                    remote=io.RemoteOptions(
                        route='/lora-manager/secure/checkpoints/standard-names',
                        refresh_button=True)),
                io.Combo.Input('base_model', options=['Any'], default='Any',
                    tooltip='Restrict the random selection pool to this base '
                            "model. 'Any' uses the full pool."),
            ],
            outputs=[
                io.Model.Output(display_name='MODEL',
                    tooltip='The model used for denoising latents.'),
                io.Clip.Output(display_name='CLIP',
                    tooltip='The CLIP model used for encoding text prompts.'),
                io.Vae.Output(display_name='VAE',
                    tooltip='The VAE model used for encoding and decoding images '
                            'to and from latent space.'),
            ],
        )

    @classmethod
    async def execute(cls, ckpt_name: str, base_model: str = 'Any'):
        # Native base_model affects only frontend random-pool selection.
        del base_model
        model, clip, vae = await sdk.ctx().models.load_checkpoint(name=ckpt_name)
        return io.NodeOutput(model, clip, vae)
