# src/resolution_list/__init__.py
from .flux_quicksize import QuickSizeFluxNode
from .qwen_quicksize import QuickSizeQwenNode
from .wan_quicksize import QuickSizeWanNode
from .sd15_quicksize import QuickSizeSD15Node
from .sdxl_quicksize import QuickSizeSDXLNode

NODE_CLASS_MAPPINGS = {
    "QuickSizeFluxNode": QuickSizeFluxNode,
    "QuickSizeQwenNode": QuickSizeQwenNode,
    "QuickSizeWanNode": QuickSizeWanNode,
    "QuickSizeSD15Node": QuickSizeSD15Node,
    "QuickSizeSDXLNode": QuickSizeSDXLNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "QuickSizeFluxNode": "Quick Size (Flux)",
    "QuickSizeQwenNode": "Quick Size (Qwen)",
    "QuickSizeWanNode": "Quick Size (Wan)",
    "QuickSizeSD15Node": "Quick Size (SD15)",
    "QuickSizeSDXLNode": "Quick Size (SDXL)",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]

