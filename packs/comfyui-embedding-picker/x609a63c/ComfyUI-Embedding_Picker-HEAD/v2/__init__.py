"""Secure Nodes V2 conversion of Embedding Picker."""

from .nodes import EmbeddingPicker


NODE_CLASS_MAPPINGS = {"EmbeddingPicker": EmbeddingPicker}
NODE_DISPLAY_NAME_MAPPINGS = {"EmbeddingPicker": "Embedding Picker"}
WEB_DIRECTORY = "web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
