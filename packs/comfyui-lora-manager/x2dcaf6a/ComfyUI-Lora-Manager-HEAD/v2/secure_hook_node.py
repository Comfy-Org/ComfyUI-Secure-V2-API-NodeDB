"""Pinned original Hook caller using genuine host HookGroups and owned records."""
from __future__ import annotations

from comfy_api.latest import io

from .secure_remaining_schemas import create_hook_schema
from .secure_services.hooks import create_managed_hooks, validate_hook_entries


class CreateHookLoraLM(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('models', 'assets', 'storage')

    @classmethod
    def define_schema(cls) -> io.Schema:
        return create_hook_schema()

    @classmethod
    async def validate_inputs(cls, loras=None) -> bool | str:
        return await validate_hook_entries(loras)

    @classmethod
    async def execute(cls, text, loras, **kwargs) -> io.NodeOutput:
        return io.NodeOutput(*await create_managed_hooks(text, loras,
            prev_hooks=kwargs.get('prev_hooks')))
