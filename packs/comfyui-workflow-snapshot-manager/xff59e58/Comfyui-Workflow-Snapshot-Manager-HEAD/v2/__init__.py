from .snapshot_node import SaveSnapshot


NODE_CLASS_MAPPINGS = {"SaveSnapshot": SaveSnapshot}
NODE_DISPLAY_NAME_MAPPINGS = {"SaveSnapshot": "Save Snapshot"}
WEB_DIRECTORY = "./js"

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY",
]
