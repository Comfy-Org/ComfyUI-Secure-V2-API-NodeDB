from comfy_api.latest import ComfyExtension
from .nodes import (
    CheckpointSelector, ImageSaveWithMetadata, SamplerSelector, SchedulerSelector,
    SeedGenerator, StringLiteral, SizeLiteral, CfgLiteral, IntLiteral,
)

WEB_DIRECTORY = "./web"

class ImageSaverExtension(ComfyExtension):
    async def get_node_list(self):
        return [CheckpointSelector, ImageSaveWithMetadata, SamplerSelector,
                SchedulerSelector, SeedGenerator, StringLiteral, SizeLiteral,
                CfgLiteral, IntLiteral]

async def comfy_entrypoint():
    return ImageSaverExtension()

# The original NODE_CLASS_MAPPINGS keys (nodes.py:269-279), unchanged and in order.
NODE_CLASS_MAPPINGS = {
    "Checkpoint Selector": CheckpointSelector,
    "Save Image w/Metadata": ImageSaveWithMetadata,
    "Sampler Selector": SamplerSelector,
    "Scheduler Selector": SchedulerSelector,
    "Seed Generator": SeedGenerator,
    "String Literal": StringLiteral,
    "Width/Height Literal": SizeLiteral,
    "Cfg Literal": CfgLiteral,
    "Int Literal": IntLiteral,
}
