from comfy_api.latest import ComfyExtension, io
from .nodes.d2_audio_nodes import NODE_CLASS_MAPPINGS as d2_audio_nodes_MAPPINGS
from .nodes.d2_image_nodes import NODE_CLASS_MAPPINGS as d2_image_nodes_MAPPINGS
from .nodes.d2_merge_nodes import NODE_CLASS_MAPPINGS as d2_merge_nodes_MAPPINGS
from .nodes.d2_nodes import NODE_CLASS_MAPPINGS as d2_nodes_MAPPINGS
from .nodes.d2_refiner_nodes import NODE_CLASS_MAPPINGS as d2_refiner_nodes_MAPPINGS
from .nodes.d2_size_nodes import NODE_CLASS_MAPPINGS as d2_size_nodes_MAPPINGS
from .nodes.d2_text_nodes import NODE_CLASS_MAPPINGS as d2_text_nodes_MAPPINGS
from .nodes.d2_xy_nodes import NODE_CLASS_MAPPINGS as d2_xy_nodes_MAPPINGS

NODE_CLASS_MAPPINGS = {
    **d2_audio_nodes_MAPPINGS,
    **d2_image_nodes_MAPPINGS,
    **d2_merge_nodes_MAPPINGS,
    **d2_nodes_MAPPINGS,
    **d2_refiner_nodes_MAPPINGS,
    **d2_size_nodes_MAPPINGS,
    **d2_text_nodes_MAPPINGS,
    **d2_xy_nodes_MAPPINGS,
}

class D2Extension(ComfyExtension):
    async def get_node_list(self):
        return list(NODE_CLASS_MAPPINGS.values())

async def comfy_entrypoint():
    return D2Extension()
