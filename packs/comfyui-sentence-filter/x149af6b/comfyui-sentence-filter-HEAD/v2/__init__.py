"""Sentence Filter: scalar V3 extension preserving the pinned original algorithm."""

from comfy_api.latest import ComfyExtension

from .secure_sentence_filter import SentenceFilterNode

NODE_CLASS_MAPPINGS = {"SentenceFilterNode": SentenceFilterNode}
NODE_DISPLAY_NAME_MAPPINGS = {"SentenceFilterNode": "Sentence Filter ✂️"}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "comfy_entrypoint"]


class SentenceFilterExtension(ComfyExtension):
    async def get_node_list(self):
        return [SentenceFilterNode]


async def comfy_entrypoint():
    return SentenceFilterExtension()
