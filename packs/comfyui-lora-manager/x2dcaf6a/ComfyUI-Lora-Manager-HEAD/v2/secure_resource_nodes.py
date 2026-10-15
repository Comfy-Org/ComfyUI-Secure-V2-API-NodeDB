"""Syntax-to-resource user-ID consumer; absolute host-path parity remains pending."""
from __future__ import annotations

from comfy_api.latest import io, sdk
from .secure_algorithms.lora_requests import parse_lora_syntax
from .secure_services.managed_library import _logical, _match


class LoraSyntaxToResource(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('assets',)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='LoRA Syntax → Path (LoraManager)', category='Lora Manager/utils',
            inputs=[io.String.Input('lora_syntax', force_input=True, multiline=True,
                tooltip='<lora:name:strength> formatted text from loaded_loras / active_loras output')],
            outputs=[io.String.Output(display_name='paths')])

    @classmethod
    async def execute(cls, lora_syntax: str):
        if not lora_syntax or not lora_syntax.strip():
            return io.NodeOutput('')
        # Strength conversion occurs even though weights do not affect identity.
        # Preserve native float errors and accepted nan/inf syntax: not returned.
        parsed = parse_lora_syntax(lora_syntax)
        if not parsed:
            return io.NodeOutput('')
        catalogue = await sdk.ctx().assets.list('loras')
        catalogue = [_logical(name) for name in catalogue]
        paths = []
        for entry in parsed:
            name = entry['name']
            try:
                selected = _match(name, catalogue)
            except ValueError:
                # Original resolver returns an unknown name verbatim. This
                # inert text is not an asset selector or filesystem authority.
                paths.append(name)
                continue
            try:
                await sdk.ctx().assets.resolve('loras', selected)
            except FileNotFoundError:
                paths.append(name)
                continue
            paths.append(selected)
        result = '\n'.join(paths)
        return io.NodeOutput(result)

