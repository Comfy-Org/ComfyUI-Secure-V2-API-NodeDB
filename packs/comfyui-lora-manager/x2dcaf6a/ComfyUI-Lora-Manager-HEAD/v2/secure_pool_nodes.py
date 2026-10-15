"""Full randomizer/cycler consumers; registration remains held for whole pack."""
from comfy_api.latest import io
from .secure_services.pool_catalogue import randomize_pool, cycle_pool
from .secure_services.catalogue_cache import validate_stacker_entries


class LoraRandomizer(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('assets', 'storage')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='Lora Randomizer (LoraManager)', category='Lora Manager/randomizer',
            inputs=[io.Custom('RANDOMIZER_CONFIG').Input('randomizer_config'),
                    io.Custom('LORAS').Input('loras'),
                    io.Custom('POOL_CONFIG').Input('pool_config', optional=True)],
            outputs=[io.Custom('LORA_STACK').Output(display_name='LORA_STACK')])

    @classmethod
    async def validate_inputs(cls, loras=None):
        return await validate_stacker_entries(loras)

    @classmethod
    async def execute(cls, randomizer_config, loras, pool_config=None):
        result = await randomize_pool(randomizer_config, loras, pool_config)
        return io.NodeOutput(*result['result'], ui=result['ui'])


class LoraCycler(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('assets', 'storage')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='Lora Cycler (LoraManager)', category='Lora Manager/randomizer',
            inputs=[io.Custom('CYCLER_CONFIG').Input('cycler_config'),
                    io.Custom('POOL_CONFIG').Input('pool_config', optional=True)],
            outputs=[io.Custom('LORA_STACK').Output(display_name='LORA_STACK')])

    @classmethod
    async def execute(cls, cycler_config, pool_config=None):
        result = await cycle_pool(cycler_config, pool_config)
        return io.NodeOutput(*result['result'], ui=result['ui'])
