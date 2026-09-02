"""Compatibility exports for the pinned pack's original module paths."""

from ._secure_nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS


def node(node_id: str):
    return (
        NODE_CLASS_MAPPINGS[node_id],
        {node_id: NODE_CLASS_MAPPINGS[node_id]},
        {node_id: NODE_DISPLAY_NAME_MAPPINGS[node_id]},
    )
