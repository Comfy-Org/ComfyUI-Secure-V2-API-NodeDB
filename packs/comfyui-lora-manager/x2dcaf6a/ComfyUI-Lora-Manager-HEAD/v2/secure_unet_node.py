"""Standard diffusion-model branch; native scanner/GGUF closure pending."""
from comfy_api.latest import io, sdk


class UnetLoader(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('models',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Unet Loader (LoraManager)',
            category='Lora Manager/loaders',
            inputs=[
                io.Combo.Input('unet_name', options=[],
                    tooltip='The name of the diffusion model to load. Use '
                            'control_after_generate to pick a random model on every run.',
                    control_after_generate=io.ControlAfterGenerate.fixed,
                    remote=io.RemoteOptions(
                        route='/lora-manager/secure/diffusion-models/standard-names',
                        refresh_button=True)),
                io.Combo.Input('weight_dtype',
                    options=['default', 'fp8_e4m3fn', 'fp8_e4m3fn_fast', 'fp8_e5m2'],
                    tooltip='The dtype to use for the model weights.'),
                io.Combo.Input('base_model', options=['Any'], default='Any',
                    tooltip='Restrict the random selection pool to this base '
                            "model. 'Any' uses the full pool."),
            ],
            outputs=[io.Model.Output(display_name='MODEL',
                tooltip='The model used for denoising latents.')],
        )

    @classmethod
    async def execute(cls, unet_name: str, weight_dtype: str, base_model: str = 'Any'):
        del base_model
        if unet_name.endswith('.gguf'):
            # The public GGUF factory exists, but native dequant operations,
            # metadata, patcher cloning and reload factory parity are unproven.
            raise NotImplementedError(
                'Native LoRA Manager GGUF metadata, patcher and reload-factory '
                'semantics have not been verified against the public GGUF loader.')
        # Native's standard branch silently uses default options for every
        # value other than these three overrides, including unknown values.
        sdk_dtype = weight_dtype if weight_dtype in (
            'fp8_e4m3fn', 'fp8_e4m3fn_fast', 'fp8_e5m2') else 'default'
        model = await sdk.ctx().models.load_diffusion_model(
            name=unet_name, weight_dtype=sdk_dtype)
        return io.NodeOutput(model)
