"""Staged original model-loader sockets; trained execution scope is explicit."""
from comfy_api.latest import io, sdk
from .wan_workflow_model_runtime import load_model_context
from .wan_workflow_resources import logical_name

ATTENTION_MODES = ['sdpa', 'flash_attn_2', 'flash_attn_3', 'sageattn', 'sageattn_3',
                   'radial_sage_attention', 'sageattn_compiled', 'sageattn_ultravico', 'comfy']
QUANTIZATIONS = ['disabled', 'fp8_e4m3fn', 'fp8_e4m3fn_fast', 'fp8_e4m3fn_scaled',
                 'fp8_e4m3fn_scaled_fast', 'fp8_e5m2', 'fp8_e5m2_fast',
                 'fp8_e5m2_scaled', 'fp8_e5m2_scaled_fast']


class WanVideoModelLoader(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'assets')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoModelLoader', display_name='WanVideo Model Loader', category='WanVideoWrapper',
            inputs=[io.Combo.Input('model', options=[],
                        tooltip="These models are loaded from the 'ComfyUI/models/diffusion_models' -folder",
                        remote=io.RemoteOptions(route='/models/diffusion_models', refresh_button=True, control_after_refresh='first')),
                    io.Combo.Input('base_precision', options=['fp32', 'bf16', 'fp16', 'fp16_fast'], default='bf16'),
                    io.Combo.Input('quantization', options=QUANTIZATIONS, default='disabled'),
                    io.Combo.Input('load_device', options=['main_device', 'offload_device'], default='offload_device'),
                    io.Combo.Input('attention_mode', options=ATTENTION_MODES, optional=True, default='sdpa'),
                    io.Custom('WANCOMPILEARGS').Input('compile_args', optional=True),
                    io.Custom('BLOCKSWAPARGS').Input('block_swap_args', optional=True),
                    io.Custom('WANVIDLORA').Input('lora', optional=True),
                    io.Custom('VRAM_MANAGEMENTARGS').Input('vram_management_args', optional=True),
                    io.Custom('VACEPATH').Input('extra_model', optional=True),
                    io.Custom('FANTASYTALKINGMODEL').Input('fantasytalking_model', optional=True),
                    io.Custom('MULTITALKMODEL').Input('multitalk_model', optional=True),
                    io.Custom('FANTASYPORTRAITMODEL').Input('fantasyportrait_model', optional=True),
                    io.Combo.Input('rms_norm_function', options=['default', 'pytorch'], optional=True, default='default')],
            outputs=[io.Custom('WANVIDEOMODEL').Output(display_name='model')])

    @classmethod
    def validate_inputs(cls, input_types=None, **kwargs):
        name = kwargs.get('model')
        return True if name is None or logical_name(name) else 'Wan model requires a logical catalogue name'

    @classmethod
    async def execute(cls, model, base_precision, load_device, quantization,
                      compile_args=None, attention_mode='sdpa', block_swap_args=None,
                      lora=None, vram_management_args=None, extra_model=None,
                      fantasytalking_model=None, multitalk_model=None,
                      fantasyportrait_model=None, rms_norm_function='default'):
        return io.NodeOutput(await load_model_context(sdk.current_context(), model,
            base_precision, load_device, quantization, compile_args, attention_mode,
            block_swap_args, lora, vram_management_args, extra_model,
            fantasytalking_model, multitalk_model, fantasyportrait_model, rms_norm_function))


NODE_CLASS_MAPPINGS = {'WanVideoModelLoader': WanVideoModelLoader}
