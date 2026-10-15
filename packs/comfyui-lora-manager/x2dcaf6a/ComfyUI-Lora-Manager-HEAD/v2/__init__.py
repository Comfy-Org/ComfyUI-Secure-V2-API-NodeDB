"""LoRA Manager full-pack conversion in progress; not release-ready.

No legacy service initialization, routes, Vue build, or metadata hooks run here.
The full21/17/406 disposition ledger remains pending in SECURE_CONVERSION.md.
"""
from comfy_api.latest import ComfyExtension
from .secure_nodes import LoraPool, LoraStackCombiner, TriggerWordToggle
from .secure_durable_text_node import Text
from .secure_durable_prompt_node import Prompt

from .secure_loader_nodes import LoraLoader, LoraTextLoader
from .secure_stack_nodes import LoraStacker
from .secure_pool_nodes import LoraRandomizer, LoraCycler
from .secure_resource_nodes import LoraSyntaxToResource
from .secure_image_metadata_node import LoadImageMetadata

from .secure_info_node import LoraInfo

from .secure_metadata_overwrite_node import MetadataOverwrite

from .secure_checkpoint_node import CheckpointLoader

from .secure_unet_node import UnetLoader

from .secure_hook_node import CreateHookLoraLM

from .secure_debug_metadata_node import DebugMetadataLM

from .secure_save_image_node import SaveImageLM

from .secure_wan_selectors import WanVideoLoraSelectLM, WanVideoLoraTextSelectLM

NODE_CLASS_MAPPINGS = {
    'WanVideo Lora Select (LoraManager)': WanVideoLoraSelectLM,
    'WanVideo Lora Select From Text (LoraManager)': WanVideoLoraTextSelectLM,
    'Save Image (LoraManager)': SaveImageLM,
    'Debug Metadata (LoraManager)': DebugMetadataLM,
    'Create Hook LoRA (LoraManager)': CreateHookLoraLM,
    'Unet Loader (LoraManager)': UnetLoader,
    'Checkpoint Loader (LoraManager)': CheckpointLoader,
    'Lora Pool (LoraManager)': LoraPool,
    'Lora Stack Combiner (LoraManager)': LoraStackCombiner,
    'TriggerWord Toggle (LoraManager)': TriggerWordToggle,
    'Text (LoraManager)': Text,
    'Prompt (LoraManager)': Prompt,
    'Lora Loader (LoraManager)': LoraLoader,
    'LoRA Text Loader (LoraManager)': LoraTextLoader,
    'Lora Stacker (LoraManager)': LoraStacker,
    'Lora Randomizer (LoraManager)': LoraRandomizer,
    'Lora Cycler (LoraManager)': LoraCycler,
    'LoRA Syntax → Path (LoraManager)': LoraSyntaxToResource,
    'Load Image Metadata (LoraManager)': LoadImageMetadata,
    'Lora Info (LoraManager)': LoraInfo,
    'Metadata Overwrite (LoraManager)': MetadataOverwrite,
}
NODE_DISPLAY_NAME_MAPPINGS = {name: name for name in NODE_CLASS_MAPPINGS}
WEB_DIRECTORY = "./secure_web"


class LoraManagerExtension(ComfyExtension):
    async def get_node_list(self):
        return list(NODE_CLASS_MAPPINGS.values())


async def comfy_entrypoint():
    return LoraManagerExtension()
