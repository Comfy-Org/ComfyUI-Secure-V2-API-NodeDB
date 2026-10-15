"""User-ID loader consumers under development; vendor/UI closure is pending.

Not yet in the full extension registration until all remaining consumers close.
No synthetic test-only node IDs: these are actual pinned loader schemas/bodies.
"""
from comfy_api.latest import io
from .secure_services.managed_library import load_managed_loras
from .secure_services.catalogue_cache import validate_stacker_entries


class LoraLoader(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('assets', 'storage', 'raw')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='Lora Loader (LoraManager)', category='Lora Manager/loaders',
            inputs=[io.Model.Input('model'), io.Custom('AUTOCOMPLETE_TEXT_LORAS').Input('text',
                tooltip='Format: <lora:lora_name:strength> separated by spaces or punctuation',
                extra_dict={'placeholder': 'Search LoRAs to add...'}),
                    io.Custom('LORAS').Input('loras'), io.Clip.Input('clip', optional=True),
                    io.Custom('LORA_STACK').Input('lora_stack', optional=True)],
            outputs=[io.Model.Output(display_name='MODEL'), io.Clip.Output(display_name='CLIP'),
                     io.String.Output(display_name='trigger_words'), io.String.Output(display_name='loaded_loras')],
            accept_all_inputs=True)

    @classmethod
    async def validate_inputs(cls, loras=None):
        return await validate_stacker_entries(loras)

    @classmethod
    async def execute(cls, model, text, loras, clip=None, lora_stack=None, **kwargs):
        del text, kwargs
        return io.NodeOutput(*await load_managed_loras(model, clip, loras=loras, lora_stack=lora_stack))


class LoraTextLoader(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('assets', 'storage', 'raw')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='LoRA Text Loader (LoraManager)', category='Lora Manager/loaders',
            inputs=[io.Model.Input('model'), io.String.Input('lora_syntax', force_input=True,
                tooltip='Format: <lora:lora_name:strength> separated by spaces or punctuation'),
                io.Clip.Input('clip', optional=True), io.Custom('LORA_STACK').Input('lora_stack', optional=True)],
            outputs=[io.Model.Output(display_name='MODEL'), io.Clip.Output(display_name='CLIP'),
                io.String.Output(display_name='trigger_words'), io.String.Output(display_name='loaded_loras')])

    @classmethod
    async def execute(cls, model, lora_syntax, clip=None, lora_stack=None):
        return io.NodeOutput(*await load_managed_loras(model, clip, lora_stack=lora_stack, lora_syntax=lora_syntax))
