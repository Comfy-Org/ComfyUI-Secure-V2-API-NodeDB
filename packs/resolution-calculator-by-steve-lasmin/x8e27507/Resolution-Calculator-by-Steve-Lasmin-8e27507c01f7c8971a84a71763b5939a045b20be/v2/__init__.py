async def comfy_entrypoint():
    from ._secure_nodes import Extension
    return Extension()

__all__ = ["comfy_entrypoint"]
