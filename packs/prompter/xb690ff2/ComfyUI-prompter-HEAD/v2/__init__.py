"""Secure Nodes V2 entrypoint for Prompt Saver & Loader."""

from .nodes import PromptSaverNode


WEB_DIRECTORY = "./web"

NODE_CLASS_MAPPINGS = {"PromptSaverNode": PromptSaverNode}
NODE_DISPLAY_NAME_MAPPINGS = {
    "PromptSaverNode": "Prompt Saver & Loader",
}

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY",
]
