"""Top-level package for immac_tools."""

from typing_extensions import override
from comfy_api.latest import ComfyExtension, io

from .src.immac_tools.nodes import (
    ConcatenateSigmasNode,
    SpliceSigmasAtNode,
    ResampleSigmas,
    SkipEveryNthImages,
    MatchContrastNode,
    SwitchNode,
)
from .src.immac_tools.forwarding_nodes import (
    ForwardAnyNode,
    ForwardConditioningNode,
    ForwardModelNode,
)

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY",
    "ImmacToolsExtension",
    "comfy_entrypoint",
]

__author__ = """Immac"""
__email__ = "immac.gm@gmail.com"
__version__ = "0.1.0"
__title__ = "Immac Tools"
__description__ = "A collection of Nodes for personal use."
__icon_ = "🧰"

# New ComfyExtension pattern
class ImmacToolsExtension(ComfyExtension):
    @override
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [
            ConcatenateSigmasNode,
            SpliceSigmasAtNode,
            ResampleSigmas,
            SkipEveryNthImages,
            MatchContrastNode,
            SwitchNode,
            ForwardAnyNode,
            ForwardConditioningNode,
            ForwardModelNode,
        ]


async def comfy_entrypoint() -> ImmacToolsExtension:
    """Entrypoint for ComfyUI to load the extension."""
    return ImmacToolsExtension()


# Legacy node mappings for backward compatibility
NODE_CLASS_MAPPINGS = {
    "ConcatenateSigmasImmacTools": ConcatenateSigmasNode,
    "SpliceSigmasAtImmacTools": SpliceSigmasAtNode,
    "ResampleSigmasImmacTools": ResampleSigmas,
    "SkipEveryNthImagesImmacTools": SkipEveryNthImages,
    "MatchContrastImmacTools": MatchContrastNode,
    "SwitchImmacTools": SwitchNode,
    "ForwardAnyImmacTools": ForwardAnyNode,
    "ForwardConditioningImmacTools": ForwardConditioningNode,
    "ForwardModelImmacTools": ForwardModelNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ConcatenateSigmasImmacTools": "Concatenate Sigmas Node",
    "SpliceSigmasAtImmacTools": "Splice Sigmas At Node",
    "ResampleSigmasImmacTools": "Resample Sigmas",
    "SkipEveryNthImagesImmacTools": "Skip Every Nth Image",
    "MatchContrastImmacTools": "Match Contrast",
    "SwitchImmacTools": "Switch",
    "ForwardAnyImmacTools": "Forward Any",
    "ForwardConditioningImmacTools": "Forward Conditioning",
    "ForwardModelImmacTools": "Forward Model",
}

WEB_DIRECTORY = "./web/js"


