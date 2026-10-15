"""Original SetLoRAs node bound to the shared sequential owned executor.

WANVIDEOMODEL remains JACK's plain context with existing public references in
its option leaves. This node neither fabricates a MODEL nor changes that wire
contract. Actual file reads, native preprocessing and owned patch validation
are performed by the shared consumer before advancing to the next descriptor.
"""
from comfy_api.latest import io, sdk

from .wan_pending_control_schemas import set_loras_schema


class WanVideoSetLoRAs(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('assets',)

    @classmethod
    def define_schema(cls):
        return set_loras_schema()

    @classmethod
    async def execute(cls, model, lora=None):
        # Native returns the exact incoming model before clone or any access.
        if lora is None:
            return io.NodeOutput(model)
        from .wan_control_consumer_adapters import prepare_set_loras_for_owned_execution

        result = await prepare_set_loras_for_owned_execution(sdk.ctx(), model, lora)
        return io.NodeOutput(result)


NODE_CLASS_MAPPINGS = {'WanVideoSetLoRAs': WanVideoSetLoRAs}
