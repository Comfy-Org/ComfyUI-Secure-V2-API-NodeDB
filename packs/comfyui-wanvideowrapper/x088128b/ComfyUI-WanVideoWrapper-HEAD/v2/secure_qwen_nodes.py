"""Original Qwen loader/extender schemas; genuine trained inference still pending."""
from comfy_api.latest import io
from ._wan_catalogue import valid_catalogue_name
from .qwen.system_prompt import SYSTEM_PROMPT_MAP
from .secure_qwen_runtime import load_qwen_resource, extend_qwen_prompt

SYSTEM_PROMPT_KEYS = [item['label'] for item in SYSTEM_PROMPT_MAP]


class QwenLoader(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'assets', 'models.download')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='QwenLoader', display_name='Qwen Loader', category='WanVideoWrapper',
            inputs=[io.Combo.Input('model', options=[], remote=io.RemoteOptions(
                        route='/models/text_encoders', refresh_button=True, control_after_refresh='first')),
                    io.Combo.Input('load_device', options=['main_device', 'offload_device'], advanced=True),
                    io.Combo.Input('precision', options=['fp16', 'bf16', 'fp32'], default='bf16')],
            outputs=[io.Custom('QWENMODEL').Output()])

    @classmethod
    def validate_inputs(cls, input_types=None, **kwargs):
        model = kwargs.get('model')
        return True if model is None or valid_catalogue_name(model) else 'Qwen requires a confined logical catalogue name'

    @classmethod
    async def execute(cls, model, load_device, precision):
        return io.NodeOutput(await load_qwen_resource(model, load_device, precision))


class WanVideoPromptExtender(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'assets', 'models.download')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoPromptExtender', display_name='Wan Video Prompt Extender', category='WanVideoWrapper',
            inputs=[io.Custom('QWENMODEL').Input('qwen'), io.String.Input('prompt', multiline=True),
                    io.Int.Input('max_new_tokens', default=512, min=1, max=2048, step=1,
                                 tooltip='Maximum number of new tokens to generate.'),
                    io.Combo.Input('device', options=['gpu', 'cpu'], default='gpu',
                                   tooltip='Device to run the model on. Default uses the main device.'),
                    io.Boolean.Input('force_offload', default=True,
                                     tooltip='Force offload the model to the offload device after generation. Useful for large models.'),
                    io.Combo.Input('system_prompt', options=SYSTEM_PROMPT_KEYS, optional=True,
                                   tooltip='System prompt to use for the model.'),
                    io.String.Input('custom_system_prompt', default='', force_input=True, optional=True,
                                    tooltip='Custom system prompt to use instead of the predefined ones.'),
                    io.Int.Input('seed', default=0, min=0, max=0xffffffffffffffff, optional=True)],
            outputs=[io.String.Output()])

    @classmethod
    async def execute(cls, qwen, prompt, device, force_offload, max_new_tokens,
                      system_prompt=None, custom_system_prompt=None, seed=0):
        return io.NodeOutput(await extend_qwen_prompt(qwen, prompt, device, force_offload, max_new_tokens,
                            system_prompt, custom_system_prompt, seed))


NODE_CLASS_MAPPINGS = {'QwenLoader': QwenLoader, 'WanVideoPromptExtender': WanVideoPromptExtender}
