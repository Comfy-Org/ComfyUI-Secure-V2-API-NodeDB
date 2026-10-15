"""Selection/setup refusal before any NEW scientific import or asset RPC."""
from .selection import selected_construction, sealed_buffers, construction

async def execute(image, environment="indoor", patch_batch_size=4, resolution=512, **kwargs):
    selected = selected_construction(environment)
    buffers = await sealed_buffers(selected)
    with construction(selected, buffers):
        from .wrapper import DiffusionEdge_Preprocessor
        return DiffusionEdge_Preprocessor().execute(image, environment, patch_batch_size, resolution, selection=selected, **kwargs)
