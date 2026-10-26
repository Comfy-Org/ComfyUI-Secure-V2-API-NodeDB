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

# Stable registry identities shared by the extension and canonical authoring.
NODE_CLASS_MAPPINGS = {
    'Cfg_Literal_b9806fcd61fbfa9e078fef8e': CfgLiteral,
    'Checkpoint_Selector_efcbbd2520fd995e676f4966': CheckpointSelector,
    'Int_Literal_01c062f38ae3d7bd4a3894d2': IntLiteral,
    'Sampler_Selector_6652e5ab7bd841db459469db': SamplerSelector,
    'Save_Image_w_Metadata_6be3a4fb3d0e4c56fec9513e': ImageSaveWithMetadata,
    'Scheduler_Selector_a46f37468d203a78b3568bbb': SchedulerSelector,
    'Seed_Generator_04cedd963306933ada265ea6': SeedGenerator,
    'String_Literal_5bb4d668d27398985246d1d5': StringLiteral,
    'Width_Height_Literal_5d88cd3d528e456d6aadd9fa': SizeLiteral,
}
