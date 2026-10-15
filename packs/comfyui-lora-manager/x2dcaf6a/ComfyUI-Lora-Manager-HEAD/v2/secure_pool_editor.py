"""Pool descriptor producer; whole manager registration remains held."""
from comfy_api.latest import io

from .secure_algorithms.bounds import bounded_json


def default_config():
    return {
        'version': 1,
        'filters': {
            'baseModels': [],
            'tags': {'include': [], 'exclude': []},
            'folders': {'include': [], 'exclude': []},
            'favoritesOnly': False,
            'license': {'noCreditRequired': False, 'allowSelling': False},
            'namePatterns': {'include': [], 'exclude': [], 'useRegex': False},
        },
        'preview': {'matchCount': 0, 'lastUpdated': 0},
    }


def descriptor(pool_config):
    # This socket carries closed workflow data, never host objects. Preserve
    # small source malformed-data branches after the before-work tree bound.
    bounded_json(pool_config)
    if not isinstance(pool_config, dict):
        pool_config = default_config()
    if 'version' not in pool_config:
        pool_config['version'] = 1
    return pool_config.get('filters', default_config()['filters'])


class LoraPool(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='Lora Pool (LoraManager)', category='Lora Manager/randomizer',
                         inputs=[io.Custom('LORA_POOL_CONFIG').Input('pool_config')],
                         outputs=[io.Custom('POOL_CONFIG').Output(display_name='POOL_CONFIG')])

    @classmethod
    async def execute(cls, pool_config):
        return io.NodeOutput(descriptor(pool_config))
