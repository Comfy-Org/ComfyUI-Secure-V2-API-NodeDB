"""Staged V3 schemas for Wan T5 loading and main text encoding."""
from comfy_api.latest import io, sdk
from .wan_workflow_resources import logical_name
from .wan_workflow_text_runtime import load_text_context, encode_main


class LoadWanVideoT5TextEncoder(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'assets')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='LoadWanVideoT5TextEncoder', display_name='WanVideo T5 Text Encoder Loader', category='WanVideoWrapper',
            description="Loads Wan text_encoder model from 'ComfyUI/models/LLM'",
            inputs=[io.Combo.Input('model_name', options=[],
                        tooltip="These models are loaded from 'ComfyUI/models/text_encoders'",
                        remote=io.RemoteOptions(route='/models/text_encoders', refresh_button=True, control_after_refresh='first')),
                    io.Combo.Input('precision', options=['fp32', 'bf16'], default='bf16'),
                    io.Combo.Input('load_device', options=['main_device', 'offload_device'], optional=True, default='offload_device'),
                    io.Combo.Input('quantization', options=['disabled', 'fp8_e4m3fn'], optional=True, default='disabled', tooltip='optional quantization method')],
            outputs=[io.Custom('WANTEXTENCODER').Output(display_name='wan_t5_model')])

    @classmethod
    def validate_inputs(cls, input_types=None, **kwargs):
        name = kwargs.get('model_name')
        return True if name is None or logical_name(name) else 'Wan T5 requires a logical catalogue name'

    @classmethod
    async def execute(cls, model_name, precision, load_device='offload_device', quantization='disabled'):
        return io.NodeOutput(await load_text_context(sdk.current_context(), model_name,
                                                    precision, load_device, quantization))


class WanVideoTextEncode(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'assets', 'storage')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoTextEncode', display_name='WanVideo TextEncode', category='WanVideoWrapper',
            description="Encodes text prompts into text embeddings. For rudimentary prompt travel you can input multiple prompts separated by '|', they will be equally spread over the video length",
            inputs=[io.String.Input('positive_prompt', default='', multiline=True),
                    io.String.Input('negative_prompt', default='', multiline=True),
                    io.Custom('WANTEXTENCODER').Input('t5', optional=True),
                    io.Boolean.Input('force_offload', optional=True, default=True),
                    io.Custom('WANVIDEOMODEL').Input('model_to_offload', optional=True,
                        tooltip='Model to move to offload_device before encoding'),
                    io.Boolean.Input('use_disk_cache', optional=True, default=False,
                        tooltip='Cache text embeddings for faster re-use'),
                    io.Combo.Input('device', options=['gpu', 'cpu'], optional=True, default='gpu',
                        tooltip='Device to run the text encoding on.')],
            outputs=[io.Custom('WANVIDEOTEXTEMBEDS').Output(display_name='text_embeds')])

    @classmethod
    async def execute(cls, positive_prompt, negative_prompt, t5=None, force_offload=True,
                      model_to_offload=None, use_disk_cache=False, device='gpu'):
        return io.NodeOutput(await encode_main(positive_prompt, negative_prompt,
            sdk.current_context(), t5, force_offload, model_to_offload, use_disk_cache, device))


NODE_CLASS_MAPPINGS = {'LoadWanVideoT5TextEncoder': LoadWanVideoT5TextEncoder,
                       'WanVideoTextEncode': WanVideoTextEncode}
