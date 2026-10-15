"""Actual Stacker user-ID consumer; full registration/release remains pending."""
from comfy_api.latest import io
from .secure_services.managed_stack import stack_managed_loras
from .secure_services.catalogue_cache import validate_stacker_entries


class LoraStacker(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('assets', 'storage', 'raw')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='Lora Stacker (LoraManager)', category='Lora Manager/stackers',
            inputs=[io.Custom('AUTOCOMPLETE_TEXT_LORAS').Input('text',
                tooltip='Format: <lora:lora_name:strength> separated by spaces or punctuation',
                extra_dict={'placeholder': 'Search LoRAs to add...'}), io.Custom('LORAS').Input('loras')],
            outputs=[io.Custom('LORA_STACK').Output(display_name='LORA_STACK'),
                io.String.Output(display_name='trigger_words'), io.String.Output(display_name='active_loras')],
            accept_all_inputs=True)

    @classmethod
    async def validate_inputs(cls, loras=None):
        return await validate_stacker_entries(loras)

    @classmethod
    async def execute(cls, text, loras, **kwargs):
        del text
        return io.NodeOutput(*await stack_managed_loras(loras, kwargs.get('lora_stack')))
