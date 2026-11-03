"""Scoped Essentials mirror; all pinned node identities retain real schemas."""
from .image import NODE_CLASS_MAPPINGS as IMAGE_CLASS_MAPPINGS
from ._refusals import NODE_CLASS_MAPPINGS as REFUSAL_CLASS_MAPPINGS
from ._v2 import SCHEMAS

WEB_DIRECTORY = None
NODE_CLASS_MAPPINGS = {**REFUSAL_CLASS_MAPPINGS, **IMAGE_CLASS_MAPPINGS}
NODE_DISPLAY_NAME_MAPPINGS = {
    node_id: definition["display_name"] for node_id, definition in SCHEMAS.items()
}
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
