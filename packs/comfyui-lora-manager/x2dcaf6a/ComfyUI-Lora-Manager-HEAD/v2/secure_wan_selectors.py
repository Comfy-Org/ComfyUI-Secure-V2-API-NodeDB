"""Original WAN node IDs over owned native metadata and logical asset names."""
from comfy_api.latest import io

from .secure_remaining_schemas import wan_widget_schema, wan_text_schema
from .secure_services.hooks import validate_hook_entries
from .secure_services.wan_cache_owner import select_owned_widget, select_owned_text


class WanVideoLoraSelectLM(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('assets', 'storage')

    @classmethod
    def define_schema(cls):
        return wan_widget_schema()

    @classmethod
    async def validate_inputs(cls, loras=None):
        return await validate_hook_entries(loras)

    @classmethod
    async def execute(cls, text, loras, low_mem_load=False, merge_loras=True, **kwargs):
        del text
        return io.NodeOutput(*await select_owned_widget(loras, low_mem_load, merge_loras, **kwargs))


class WanVideoLoraTextSelectLM(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('assets', 'storage')

    @classmethod
    def define_schema(cls):
        return wan_text_schema()

    @classmethod
    async def execute(cls, lora_syntax, low_mem_load=False, merge_lora=True, **kwargs):
        return io.NodeOutput(*await select_owned_text(lora_syntax, low_mem_load, merge_lora, **kwargs))
