"""Original loader schemas with typed digest-bound resources; unintegrated."""
from comfy_api.latest import io, sdk

from .wan_control_context import describe_control_resource, describe_uni3c_resource
from .wan_workflow_resources import logical_name


def model_input():
    return io.Combo.Input('model', options=[],
        tooltip="These models are loaded from the 'ComfyUI/models/controlnet' -folder",
        remote=io.RemoteOptions(route='/models/controlnet', refresh_button=True, control_after_refresh='first'))


def validate_selection(input_types=None, **kwargs):
    name = kwargs.get('model')
    return True if name is None or logical_name(name) else 'Wan ControlNet requires a confined logical catalogue name'


class WanVideoControlnetLoader(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('assets',)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoControlnetLoader', display_name='WanVideo Controlnet Loader', category='WanVideoWrapper',
            description="Loads ControlNet model from 'https://huggingface.co/collections/TheDenk/wan21-controlnets-68302b430411dafc0d74d2fc'",
            inputs=[model_input(),
                io.Combo.Input('base_precision', options=['fp32', 'bf16', 'fp16'], default='bf16'),
                io.Combo.Input('quantization', options=['disabled', 'fp8_e4m3fn', 'fp8_e4m3fn_fast', 'fp8_e5m2', 'fp8_e4m3fn_fast_no_ffn'],
                               default='disabled', tooltip='optional quantization method'),
                io.Combo.Input('load_device', options=['main_device', 'offload_device'], default='main_device',
                    tooltip='Initial device to load the model to, NOT recommended with the larger models unless you have 48GB+ VRAM')],
            outputs=[io.Custom('WANVIDEOCONTROLNET').Output(display_name='controlnet')])

    @classmethod
    def validate_inputs(cls, input_types=None, **kwargs):
        return validate_selection(input_types, **kwargs)

    @classmethod
    async def execute(cls, model, base_precision, load_device, quantization):
        resource = await describe_control_resource(sdk.current_context().assets,
            model, base_precision, load_device, quantization)
        return io.NodeOutput(resource)


class WanVideoUni3C_ControlnetLoader(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('assets',)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoUni3C_ControlnetLoader', display_name='WanVideo Uni3C Controlnet Loader', category='WanVideoWrapper',
            inputs=[model_input(),
                io.Combo.Input('base_precision', options=['fp32', 'bf16', 'fp16'], default='fp16'),
                io.Combo.Input('quantization', options=['disabled', 'fp8_e4m3fn', 'fp8_e5m2'],
                               default='disabled', tooltip='optional quantization method'),
                io.Combo.Input('load_device', options=['main_device', 'offload_device'], default='offload_device',
                    tooltip='Initial device to load the model to, NOT recommended with the larger models unless you have 48GB+ VRAM'),
                io.Combo.Input('attention_mode', options=['sdpa', 'sageattn'], default='sdpa'),
                io.Custom('WANCOMPILEARGS').Input('compile_args', optional=True)],
            outputs=[io.Custom('WANVIDEOCONTROLNET').Output(display_name='controlnet')])

    @classmethod
    def validate_inputs(cls, input_types=None, **kwargs):
        return validate_selection(input_types, **kwargs)

    @classmethod
    async def execute(cls, model, base_precision, load_device, quantization, attention_mode, compile_args=None):
        resource = await describe_uni3c_resource(sdk.current_context().assets,
            model, base_precision, load_device, quantization, attention_mode, compile_args)
        return io.NodeOutput(resource)


NODE_CLASS_MAPPINGS = {'WanVideoControlnetLoader': WanVideoControlnetLoader,
                       'WanVideoUni3C_ControlnetLoader': WanVideoUni3C_ControlnetLoader}
