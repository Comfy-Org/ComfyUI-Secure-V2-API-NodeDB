"""Secure Nodes V2 entrypoint for H3 Project Suite."""
from __future__ import annotations

from comfy_api.latest import ComfyExtension, io

from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
from .project_nodes import (
    NODE_CLASS_MAPPINGS as PROJECT_NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as PROJECT_NODE_DISPLAY_NAME_MAPPINGS,
)

NODE_CLASS_MAPPINGS.update(PROJECT_NODE_CLASS_MAPPINGS)
NODE_DISPLAY_NAME_MAPPINGS.update(PROJECT_NODE_DISPLAY_NAME_MAPPINGS)
WEB_DIRECTORY = "./web"


class H3ProjectSuiteExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return list(NODE_CLASS_MAPPINGS.values())


async def comfy_entrypoint() -> H3ProjectSuiteExtension:
    return H3ProjectSuiteExtension()


__all__ = [
    "NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY", "comfy_entrypoint",
]
