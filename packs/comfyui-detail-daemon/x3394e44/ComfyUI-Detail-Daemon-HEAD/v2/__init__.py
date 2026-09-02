"""Secure Nodes V2 entrypoint for ComfyUI-Detail-Daemon."""

from typing_extensions import override
from comfy_api.latest import ComfyExtension

from .detail_daemon_node import (
    NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS,
    DetailDaemonGraphSigmasNode,
    DetailDaemonSamplerGUINode,
    DetailDaemonSamplerNode,
    LyingSigmaSamplerNode,
    MultiplySigmas,
)


class DetailDaemonExtension(ComfyExtension):
    @override
    async def get_node_list(self):
        return [
            DetailDaemonSamplerNode,
            DetailDaemonSamplerGUINode,
            DetailDaemonGraphSigmasNode,
            MultiplySigmas,
            LyingSigmaSamplerNode,
        ]


async def comfy_entrypoint():
    return DetailDaemonExtension()


WEB_DIRECTORY = "./web"

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY",
    "DetailDaemonExtension",
    "DetailDaemonGraphSigmasNode",
    "DetailDaemonSamplerGUINode",
    "DetailDaemonSamplerNode",
    "LyingSigmaSamplerNode",
    "MultiplySigmas",
    "comfy_entrypoint",
]
