"""Standard and GGUF diffusion-model branches; LoRA Manager's extra scanner roots are not searched.

The GGUF branch mirrors pristine py/nodes/unet_loader.py (UNETLoaderLM._load_gguf_unet) through the public
models.load_gguf_model verb. That verb builds the model with the host's fixed ComfyUI-GGUF module exactly as the
branch does: gguf_sd_loader, GGMLOps, load_diffusion_model_state_dict(..., metadata=...), GGUFModelPatcher.clone.
The original sets ops.Linear.dequant_dtype = getattr(torch, weight_dtype, None), which is None for every option
this node offers (torch has no fp8_* attributes), and leaves patch dtype and patch_on_device untouched, so the verb's
defaults are the original's effective values. Recorded differences: the returned model carries no
cached_patcher_init reload factory; the patch dtype is the default for every load (the original reads the shared
GGMLOps.Linear class, which an earlier ComfyUI-GGUF Advanced load can change); an unknown GGUF name is refused by an
existence check in the diffusion-model roots rather than by the scanner's list; an upper-case ".GGUF" name is refused
at queue time (the original sends it to the standard loader, which cannot read GGUF).
"""
from comfy_api.latest import io, sdk

from .secure_services.managed_library import _logical


class UnetLoader(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('models', 'assets')

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
                        route='/models/diffusion_models',
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
    async def validate_inputs(cls, unet_name, base_model='Any'):
        # The remote list has no static options, so core cannot check membership itself.
        # base_model only narrows the frontend's random pick; any saved value is accepted.
        del base_model
        if type(unet_name) is not str or not unet_name:
            return f'Value not in list: unet_name: {unet_name!r}'
        missing = f"Value not in list: unet_name: '{unet_name}' is not an available diffusion model"
        if unet_name.endswith('.gguf'):
            # Core's diffusion-model list holds PyTorch/SafeTensors files only. Read-only existence check in the same
            # roots the host's GGUF catalogue uses; unsafe names are refused locally, as the Checkpoint Loader does.
            try:
                name = _logical(unet_name)
            except ValueError:
                return missing
            return True if await sdk.ctx().assets.exists('diffusion_models', name) else missing
        if unet_name.lower().endswith('.gguf'):
            return ('GGUF UNet names must end in lower-case ".gguf"; the original sends other spellings to the '
                    'standard loader, which cannot read GGUF')
        if unet_name not in await sdk.ctx().models.list_diffusion_models():
            return missing
        return True

    @classmethod
    async def execute(cls, unet_name: str, weight_dtype: str, base_model: str = 'Any'):
        del base_model
        if unet_name.endswith('.gguf'):
            # weight_dtype has no effect on this branch in the original (see the module docstring).
            try:
                model = await sdk.ctx().models.load_gguf_model(name=unet_name)
            except PermissionError:
                raise
            except Exception as error:
                # pristine unet_loader.py:300-304 wraps every load failure this way.
                raise RuntimeError(f"Failed to load GGUF diffusion model '{unet_name}': {str(error)}") from error
            return io.NodeOutput(model)
        # Native's standard branch silently uses default options for every
        # value other than these three overrides, including unknown values.
        sdk_dtype = weight_dtype if weight_dtype in (
            'fp8_e4m3fn', 'fp8_e4m3fn_fast', 'fp8_e5m2') else 'default'
        model = await sdk.ctx().models.load_diffusion_model(
            name=unet_name, weight_dtype=sdk_dtype)
        return io.NodeOutput(model)
