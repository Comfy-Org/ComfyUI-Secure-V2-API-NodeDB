"""Secure Nodes V2 entrypoint for comfyui-cache-cleaner."""

from typing_extensions import override

from comfy_api.latest import ComfyExtension

from .cache_cleaner import CacheCleaner, NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS


class CacheCleanerExtension(ComfyExtension):
    @override
    async def get_node_list(self):
        return [CacheCleaner]


async def comfy_entrypoint():
    return CacheCleanerExtension()


__all__ = [
    "CacheCleaner",
    "CacheCleanerExtension",
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "comfy_entrypoint",
]
