"""
ComfyUI Custom Node: Sentence Filter
=====================================
Filters sentences from a text prompt based on user-defined trigger words.
Supports deletion and replacement of matched sentences.

Installation:
    Copy this folder into ComfyUI/custom_nodes/ and restart ComfyUI.
"""

from .sentence_filter_node import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
