"""Hard refusal BEFORE NEW eager scientific/vendor imports/RPC/allocation."""
from .selection import require_constructor

async def execute(image, ckpt_name='depth_anything_vitl14.pth', resolution=512):
    require_constructor()
    from .wrapper import Depth_Anything_Preprocessor
    return Depth_Anything_Preprocessor().execute(image, ckpt_name=ckpt_name, resolution=resolution)
