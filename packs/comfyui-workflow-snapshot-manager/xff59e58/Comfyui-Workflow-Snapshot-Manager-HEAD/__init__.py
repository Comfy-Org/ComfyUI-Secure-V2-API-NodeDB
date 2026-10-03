"""
ComfyUI Snapshot Manager

Automatically snapshots workflow state as you edit, with a sidebar panel
to browse and restore any previous version. Stored in server-side JSON files.
"""

WEB_DIRECTORY = "./js"

# ComfyUI loads custom nodes as packages. Test runners may import this file as
# a standalone module while discovering tests; avoid trying to register routes
# until package-relative imports are available.
if __package__:
    from . import snapshot_routes
    from .snapshot_node import SaveSnapshot

    NODE_CLASS_MAPPINGS = {"SaveSnapshot": SaveSnapshot}
    NODE_DISPLAY_NAME_MAPPINGS = {"SaveSnapshot": "Save Snapshot"}
else:
    NODE_CLASS_MAPPINGS = {}
    NODE_DISPLAY_NAME_MAPPINGS = {}
