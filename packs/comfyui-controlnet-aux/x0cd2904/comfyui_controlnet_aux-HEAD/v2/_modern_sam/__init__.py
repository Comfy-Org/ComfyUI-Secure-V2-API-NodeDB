"""Refuse before NEW scientific/vendor imports, asset RPC or model allocation."""
from .selection import require_constructor

async def execute(image, resolution=512):
    require_constructor()
    from .wrapper import SAM_Preprocessor
    return SAM_Preprocessor().execute(image, resolution=resolution)
