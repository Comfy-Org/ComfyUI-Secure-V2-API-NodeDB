"""Refuse BEFORE NEW eager vendor/scientific imports, RPC or allocation."""
from .selection import require_constructor

async def execute(node_id, image, resolution=512, **kwargs):
    require_constructor()
    if node_id == 'Zoe-DepthMapPreprocessor':
        from .wrapper_zoe import Zoe_Depth_Map_Preprocessor
        return Zoe_Depth_Map_Preprocessor().execute(image, resolution=resolution, **kwargs)
    if node_id == 'Zoe_DepthAnythingPreprocessor':
        from .wrapper_depth_anything import Zoe_Depth_Anything_Preprocessor
        return Zoe_Depth_Anything_Preprocessor().execute(image, resolution=resolution, **kwargs)
    raise KeyError(node_id)
