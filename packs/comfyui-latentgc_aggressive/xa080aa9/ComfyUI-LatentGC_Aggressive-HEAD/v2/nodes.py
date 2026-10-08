"""Bounded local shallow-copy algorithm; managed cleanup stays host-owned."""
import torch
from comfy_api.latest import io, sdk

MAX_BYTES = 67108864
MAX_ITEMS = 4096
MAX_DEPTH = 16

def preflight(value):
    """Admit closed wire values without discarding any metadata."""
    if type(value) is not dict:
        raise TypeError('LATENT must be a plain dictionary')
    items = 0
    size = 0
    ancestors = set()
    def visit(item, depth):
        nonlocal items, size
        items += 1
        if items > MAX_ITEMS or depth > MAX_DEPTH:
            raise ValueError('latent metadata work budget exceeded')
        if isinstance(item, torch.Tensor):
            if item.layout != torch.strided:
                raise TypeError('only dense latent tensor wire values are supported')
            size += max(item.numel() * item.element_size(), item.untyped_storage().nbytes())
        elif type(item) in (str, bytes):
            size += len(item.encode('utf-8') if type(item) is str else item)
        elif item is None or type(item) in (bool, int, float):
            size += 8 if type(item) is not int else max(1,(item.bit_length()+7)//8)
        elif type(item) in (dict, list, tuple):
            if id(item) in ancestors:
                raise ValueError('cyclic latent metadata is not supported')
            ancestors.add(id(item))
            if type(item) is dict:
                for key, entry in item.items():
                    if type(key) is not str:
                        raise TypeError('latent wire dictionary keys must be strings')
                    visit(key, depth+1)
                    visit(entry, depth+1)
            else:
                for entry in item:
                    visit(entry, depth+1)
            ancestors.remove(id(item))
        else:
            raise TypeError('unsupported latent wire value: '+type(item).__name__)
        if size > MAX_BYTES:
            raise ValueError('latent transport byte budget exceeded')
    visit(value, 0)

class LatentGC_Aggressive(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'models.manage')
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='LatentGC', display_name='LatentGC',
                         category='latent', inputs=[io.Latent.Input('samples')],
                         outputs=[io.Latent.Output()])
    @classmethod
    async def execute(cls, samples):
        preflight(samples)
        copied = samples.copy()
        models = sdk.ctx().models
        await models.memory_cleanup(empty_cache=False, collect_cycles=True,
                                    unload_all_models=False)
        await models.memory_cleanup(empty_cache=False, collect_cycles=False,
                                    unload_all_models=True)
        await models.memory_cleanup(empty_cache=True, collect_cycles=False,
                                    unload_all_models=False)
        return io.NodeOutput(copied)

NODE_CLASS_MAPPINGS = {'LatentGC': LatentGC_Aggressive}
