# GGUF Quantization support for native ComfyUI models.
#
# The legacy package guarded its imports on ``import comfy.utils`` so the tree
# could double as a plain library.  A V2 mirror never imports the host at all,
# so the guard has no purpose and the node list is imported directly.
from typing_extensions import override
from comfy_api.latest import ComfyExtension

from .nodes import (
    NODE_CLASS_MAPPINGS,
    UnetLoaderGGUF,
    UnetLoaderGGUFAdvanced,
    CLIPLoaderGGUF,
    DualCLIPLoaderGGUF,
    TripleCLIPLoaderGGUF,
    QuadrupleCLIPLoaderGGUF,
)

# Upstream derived these from each class's ``TITLE``; a V2 schema carries the
# same string as ``display_name``, so the mapping stays identical.
NODE_DISPLAY_NAME_MAPPINGS = {
    node_id: node_class.GET_SCHEMA().display_name
    for node_id, node_class in NODE_CLASS_MAPPINGS.items()
}


class GGUFExtension(ComfyExtension):
    @override
    async def get_node_list(self):
        return [
            UnetLoaderGGUF,
            CLIPLoaderGGUF,
            DualCLIPLoaderGGUF,
            TripleCLIPLoaderGGUF,
            QuadrupleCLIPLoaderGGUF,
            UnetLoaderGGUFAdvanced,
        ]


async def comfy_entrypoint():
    return GGUFExtension()


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
