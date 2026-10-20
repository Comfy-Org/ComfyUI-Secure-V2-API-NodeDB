from .nodes.string_list_concat import StringListConcat, comfy_entrypoint

__all__ = [
    "StringListConcat",
    "comfy_entrypoint"
]

# Secure V2 discovery: the manifest generator reads the same one-node registration
# that comfy_entrypoint().get_node_list() returns; no node code or schema changes.
NODE_CLASS_MAPPINGS = {"StringListConcat": StringListConcat}
