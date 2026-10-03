from .nodes.panel_layout_provider import PanelLayoutProvider
from .nodes.panel_compositor import PanelCompositor
from .nodes.list_utils import ListGetItem, TupleUnpack

# Secure V2 deliberately registers no pack HTTP routes. Built-ins are immutable
# pack data, user layouts live in per-user frontend storage, and a selected
# custom layout is embedded into the existing layout_preset workflow value.

NODE_CLASS_MAPPINGS = {
    "PanelLayoutProvider": PanelLayoutProvider,
    "PanelCompositor": PanelCompositor,
    "ListGetItem": ListGetItem,
    "TupleUnpack": TupleUnpack,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PanelLayoutProvider": "Panel Layout Provider (PanelComposer)",
    "PanelCompositor": "Panel Compositor (PanelComposer)",
    "ListGetItem": "List Get Item",
    "TupleUnpack": "Tuple Unpack",
}

WEB_DIRECTORY = "web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
